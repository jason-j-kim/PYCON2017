// 정책 아이디어 평가 — Cloudflare Workers 배포판
//
// 경로
//   GET  /*             정적 프런트(web/) — [assets] 바인딩이 처리
//   GET  /api/evaluate  가용 자료원 상태
//   POST /api/evaluate  축 B(선례 검증) 실행
//   POST /api/claude    Anthropic 프록시 (문답·채점용, 브라우저가 호출)
//   POST /api/extract   .txt/.json 텍스트 추출 (docx/pdf 미지원)
//
// Vercel판과 동일한 프롬프트·판정 규칙을 쓴다. 다른 점은 코퍼스가 파일이 아니라
// D1이고, KDI 통로에 kdinov가 없다는 것뿐이다(README 참조).

import { SPEC_EXTRACTOR_SYSTEM, PRECEDENT_JUDGE_SYSTEM, ORIGINALITY_GRADER_SYSTEM, SPEC_SCHEMA } from './prompts.js';
import { doLookups, judgeLookupView, sourcesStatus } from './lookups.js';

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';
const DEFAULT_MODEL = 'claude-opus-5';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...CORS },
  });

// ─────────────────────────────────────────── Claude 호출

/** 도구 사용을 강제해 유효한 JSON만 받는다(Vercel판 call_claude_json과 동일 전략). */
async function callClaudeJson(env, systemPrompt, userPrompt, apiKey, schema) {
  const body = {
    model: env.CLAUDE_MODEL || DEFAULT_MODEL,
    max_tokens: 4000,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  };
  if (schema) {
    body.tools = [{
      name: 'record',
      description: '결과를 이 도구의 입력(JSON)으로 제출한다.',
      input_schema: schema,
    }];
    body.tool_choice = { type: 'tool', name: 'record' };
  }

  const r = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': ANTHROPIC_VERSION,
    },
    body: JSON.stringify(body),
  });

  const data = await r.json();
  if (!r.ok) {
    const msg = data?.error?.message || `Anthropic ${r.status}`;
    throw new Error(msg);
  }
  const blocks = data.content || [];
  if (schema) {
    const tool = blocks.find((b) => b.type === 'tool_use');
    if (!tool) throw new Error(`도구 호출이 없습니다 (stop_reason=${data.stop_reason})`);
    return tool.input;
  }
  const text = blocks.filter((b) => b.type === 'text').map((b) => b.text).join('');
  if (!text) throw new Error(`빈 응답 (stop_reason=${data.stop_reason})`);
  return JSON.parse(stripFence(text));
}

function stripFence(s) {
  return String(s || '').trim()
    .replace(/^```[a-zA-Z]*\s*/, '')
    .replace(/\s*```$/, '');
}

// ─────────────────────────────────────────── 축 B 단계

async function extractSpec(env, transcript, apiKey) {
  const r = await callClaudeJson(
    env, SPEC_EXTRACTOR_SYSTEM,
    `<대화 로그>\n${transcript}\n</대화 로그>`,
    apiKey, SPEC_SCHEMA
  );
  // 누락 필드는 실패시키지 않고 기본값으로 채운다(조회는 queries만 있으면 된다).
  const out = r.spec ? r : { spec: r };
  if (!out.policy_type) out.policy_type = '미분류';
  if (!Array.isArray(out.claimed_precedents)) out.claimed_precedents = [];
  if (typeof out.queries !== 'object' || !out.queries) out.queries = {};
  for (const k of ['fiscal', 'prism', 'bill', 'overseas']) {
    if (!Array.isArray(out.queries[k])) out.queries[k] = [];
  }
  return out;
}

async function judgeByKnowledge(env, specResult, apiKey) {
  return callClaudeJson(
    env, PRECEDENT_JUDGE_SYSTEM,
    `<정책 명세>\n${JSON.stringify(specResult, null, 2)}\n</정책 명세>`,
    apiKey
  );
}

async function gradeOriginality(env, specResult, judge, hits, apiKey) {
  const parts = [
    `<정책 명세>\n${JSON.stringify(specResult, null, 2)}\n</정책 명세>`,
    `<지식 판정>\n${JSON.stringify(judge, null, 2)}\n</지식 판정>`,
  ];
  // 미실행 통로가 빈 배열로 넘어가면 '조회했는데 0건'으로 읽힌다 — 문자열로 바꿔 보낸다.
  parts.push(`<조회 결과>\n${JSON.stringify(judgeLookupView(hits), null, 2)}\n</조회 결과>`);
  return callClaudeJson(env, ORIGINALITY_GRADER_SYSTEM, parts.join('\n\n'), apiKey);
}

async function originalityAxis(env, transcript, apiKey) {
  const spec = await extractSpec(env, transcript, apiKey);
  // 지식 판정과 조회를 동시에 — 서로 의존하지 않는다.
  const [judge, hits] = await Promise.all([
    judgeByKnowledge(env, spec, apiKey),
    doLookups(env, spec).catch(() => null),
  ]);
  const grade = await gradeOriginality(env, spec, judge, hits, apiKey);
  return { spec, judge, lookup: hits, originality: grade };
}

// ─────────────────────────────────────────── 라우팅

async function handleClaudeProxy(env, request) {
  const p = await request.json();
  const apiKey = (p.api_key || '').trim();
  if (!apiKey) return json({ error: 'Claude API 키를 입력하세요.' }, 400);

  const body = {
    model: env.CLAUDE_MODEL || DEFAULT_MODEL,
    max_tokens: p.max_tokens || 2000,
    system: p.system || '',
    messages: [{ role: 'user', content: p.prompt || '' }],
  };
  if (p.force_json) {
    body.tools = [{
      name: 'record',
      description: '결과를 이 도구의 입력(JSON)으로 제출한다.',
      input_schema: p.schema || { type: 'object', additionalProperties: true },
    }];
    body.tool_choice = { type: 'tool', name: 'record' };
  }

  const r = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': ANTHROPIC_VERSION,
    },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) return json({ error: data?.error?.message || `Anthropic ${r.status}` }, r.status);

  const blocks = data.content || [];
  if (p.force_json) {
    const tool = blocks.find((b) => b.type === 'tool_use');
    if (!tool) return json({ error: `도구 호출이 없습니다 (stop_reason=${data.stop_reason})` }, 502);
    return json({ json: tool.input });
  }
  const text = blocks.filter((b) => b.type === 'text').map((b) => b.text).join('');
  if (!text) return json({ error: `빈 응답 (stop_reason=${data.stop_reason})` }, 502);
  return json({ text });
}

async function handleExtract(request) {
  const p = await request.json();
  const name = (p.filename || '').toLowerCase();
  const b64 = p.content_b64 || '';
  if (name.endsWith('.docx') || name.endsWith('.pdf')) {
    return json({
      error: 'Workers 배포에서는 Word·PDF 추출을 지원하지 않습니다. '
           + '텍스트(.txt)나 저장한 문답(.json)으로 올려 주세요.',
    }, 415);
  }
  try {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const text = new TextDecoder('utf-8').decode(bytes);
    return json({ text });
  } catch {
    return json({ error: '파일을 읽지 못했습니다.' }, 400);
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS });

    try {
      if (path === '/api/evaluate') {
        if (request.method === 'GET') {
          return json({ sources: await sourcesStatus(env) });
        }
        if (request.method === 'POST') {
          const p = await request.json();
          const transcript = (p.transcript || p.policy || '').trim();
          const apiKey = (p.api_key || '').trim();
          if (!transcript) return json({ error: '대화 로그가 비어 있습니다.' }, 400);
          if (!apiKey) return json({ error: 'Claude API 키를 입력하세요.' }, 400);
          const result = await originalityAxis(env, transcript, apiKey);
          return json({ ...result, sources: await sourcesStatus(env) });
        }
      }

      if (path === '/api/claude' && request.method === 'POST') {
        return handleClaudeProxy(env, request);
      }

      if (path === '/api/extract' && request.method === 'POST') {
        return handleExtract(request);
      }

      // 그 외는 정적 자산(web/)으로 넘긴다.
      if (env.ASSETS) return env.ASSETS.fetch(request);
      return new Response('Not found', { status: 404 });
    } catch (err) {
      return json({ error: String(err?.message || err) }, 500);
    }
  },
};

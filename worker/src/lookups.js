// 축 B — 네 통로 조회. Python판(web/api/evaluate.py)의 판정 로직을 그대로 옮겼다.
//   ① 재정 · ② 정책연구(KDI) · ④ 해외(OPSI)  →  D1
//   ③ 국회 의안                              →  외부 API

// ─────────────────────────────────────────── 공통

const STOPWORDS = new Set([
  '지원', '사업', '정책', '제도', '방안', '개선', '확대', '강화', '추진', '및', '등',
  '관한', '관련', '대한', '위한', '통한', '그리고', '또는',
]);

// OPSI 사례 거의 전부에 등장해 변별력이 없는 초일반어.
const OPSI_STOP = new Set([
  'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was', 'has', 'have',
  'not', 'but', 'all', 'any', 'can', 'will', 'new', 'use', 'using', 'used', 'based',
  'into', 'per', 'via', 'its', 'their', 'our', 'your', 'more', 'most', 'such', 'than',
  'then', 'they', 'them', 'also', 'may', 'one', 'two', 'who', 'how', 'what', 'when',
  'where', 'which', 'while', 'been', 'being', 'were', 'would', 'could', 'should',
  'about', 'over', 'under', 'between', 'within', 'across', 'through',
  'public', 'government', 'governmental', 'service', 'services', 'sector', 'innovation',
  'innovative', 'project', 'programme', 'program', 'initiative', 'national', 'citizen',
  'citizens', 'people', 'community', 'development', 'management',
]);

const KDI_STOP = new Set([
  '및', '등', '관한', '관련', '대한', '위한', '통한', '그리고', '또는',
  'the', 'and', 'for', 'with', 'of', 'in', 'on', 'to', 'study', '연구',
  '정책', '방안', '분석', '제도', '개선', '방향', '과제',
]);

/** 인접 구절 보너스 + 제목 가중 공통 채점기. */
function scoreRow(toks, title, hay) {
  let score = 0;
  for (const t of toks) {
    if (title.includes(t)) score += 3;
    else if (hay.includes(t)) score += 1;
  }
  for (let i = 0; i + 1 < toks.length; i++) {
    if (hay.includes(`${toks[i]} ${toks[i + 1]}`)) score += 3;
  }
  return score;
}

/** LIKE 조건과 파라미터를 만든다. */
function likeClause(toks, cols) {
  const per = cols.map((c) => `${c} LIKE ?`).join(' OR ');
  const where = toks.map(() => `(${per})`).join(' OR ');
  const params = [];
  for (const t of toks) for (let i = 0; i < cols.length; i++) params.push(`%${t}%`);
  return { where, params };
}

function dedup(items, key) {
  const seen = new Set();
  const out = [];
  for (const it of items) {
    const k = it[key];
    if (k && !seen.has(k)) { seen.add(k); out.push(it); }
  }
  return out;
}

// ─────────────────────────────────────────── ① 재정

/** Python _keyword_hit 과 동일: 전체 포함이거나, 의미어 2개 이상 포함. */
function keywordHit(query, hay) {
  const q = (query || '').trim();
  if (!q || !hay) return false;
  if (hay.includes(q)) return true;
  let meaningful = q.split(/\s+/).filter((t) => t.length >= 2 && !STOPWORDS.has(t));
  if (!meaningful.length) meaningful = q.split(/\s+/).filter(Boolean);
  const present = meaningful.filter((t) => hay.includes(t)).length;
  return meaningful.length >= 2 ? present >= 2 : present >= 1;
}

export async function fiscalLookup(db, query) {
  const q = (query || '').trim();
  if (!q) return [];
  // 후보를 넉넉히 끌어온 뒤 _keyword_hit 규칙으로 거른다(정확한 이식).
  let toks = q.split(/\s+/).filter((t) => t.length >= 2 && !STOPWORDS.has(t));
  if (!toks.length) toks = q.split(/\s+/).filter(Boolean);
  if (!toks.length) return [];
  const { where, params } = likeClause(toks.slice(0, 6), ['name']);
  const rs = await db.prepare(
    `SELECT name, ministry, max_amt, series FROM fiscal WHERE ${where} ORDER BY max_amt DESC LIMIT 200`
  ).bind(...params).all();

  return (rs.results || [])
    .filter((r) => keywordHit(q, r.name || ''))
    .slice(0, 5)
    .map((r) => ({
      name: r.name,
      ministry: r.ministry,
      series: safeJson(r.series, []),
    }));
}

function safeJson(s, fallback) {
  try { return JSON.parse(s); } catch { return fallback; }
}

// ─────────────────────────────────────────── ② 정책연구 (KDI)

/**
 * Python _kdi_naive_lookup 이식.
 * 주의: kdinov(대상×수단×영역 2차원 판정)는 Python 패키지라 Workers에서 동작하지
 * 않는다. 이 통로는 Vercel/터널판이 kdinov 부재 시 쓰는 폴백과 동일한 수준이며,
 * 중첩도(N0~N4)·역할(실행/경합/근거/선례) 판정은 제공되지 않는다.
 */
export async function kdiLookup(db, query) {
  const raw = (query || '').toLowerCase().match(/[0-9a-z가-힣][\w가-힣-]{1,}/g) || [];
  let toks = raw.filter((t) => !KDI_STOP.has(t) && t.length >= 2);
  if (!toks.length) toks = raw;
  if (!toks.length) return [];

  const { where, params } = likeClause(toks.slice(0, 8), ['content', 'title', 'keywords']);
  const rs = await db.prepare(
    `SELECT id,title,kind,year,keywords,content,url FROM kdi WHERE ${where} LIMIT 120`
  ).bind(...params).all();

  const scored = [];
  for (const d of rs.results || []) {
    const title = (d.title || '').toLowerCase();
    const hay = `${title} ${(d.keywords || '').toLowerCase()} ${(d.content || '').toLowerCase()}`;
    const s = scoreRow(toks, title, hay);
    if (s) scored.push([s, d]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, 5).map(([, d]) => ({
    title: d.title,
    org: d.kind || null,
    period: d.year || null,
    summary: (d.content || '').slice(0, 500),
    url: d.url || null,
  }));
}

// ─────────────────────────────────────────── ④ 해외 (OPSI)

export async function opsiLookup(db, query) {
  const raw = (query || '').toLowerCase().match(/[a-z][a-z0-9-]{2,}/g) || [];
  let toks = raw.filter((t) => !OPSI_STOP.has(t));
  if (!toks.length) toks = raw;
  if (!toks.length) return [];

  const { where, params } = likeClause(toks.slice(0, 8), ['content', 'title', 'country']);
  const rs = await db.prepare(
    `SELECT id,title,country,year,sector,level,content,url FROM opsi WHERE ${where} LIMIT 120`
  ).bind(...params).all();

  const scored = [];
  for (const d of rs.results || []) {
    const title = (d.title || '').toLowerCase();
    const hay = `${title} ${(d.content || '').toLowerCase()}`;
    const s = scoreRow(toks, title, hay);
    if (s) scored.push([s, d]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, 5).map(([, d]) => ({
    title: d.title, country: d.country, year: d.year, sector: d.sector,
    level: d.level, summary: (d.content || '').slice(0, 500), url: d.url,
  }));
}

// ─────────────────────────────────────────── ③ 국회 의안

const LAW_SUFFIX = /(법|법률|기본법|특별법|진흥법|지원법)$/;

function billTokens(query) {
  const toks = (query || '').split(/\s+/).filter(Boolean);
  const distinct = toks.filter((t) => t.length >= 2 && !STOPWORDS.has(t));
  return distinct.length ? distinct : toks;
}

export async function billLookup(query, assemblyKey) {
  if (!assemblyKey) return [];
  const terms = billTokens(query).slice(0, 3);
  if (!terms.length) return [];
  const out = [];
  const seen = new Set();

  for (const term of terms) {
    const url = 'https://open.assembly.go.kr/portal/openapi/ALLBILL'
      + `?KEY=${encodeURIComponent(assemblyKey)}&Type=json&pIndex=1&pSize=20`
      + `&BILL_NAME=${encodeURIComponent(term)}`;
    let data;
    try {
      const r = await fetch(url, { cf: { cacheTtl: 300 } });
      if (!r.ok) continue;
      data = await r.json();
    } catch { continue; }

    const rows = findRows(data);
    for (const row of rows) {
      const name = row.BILL_NAME || row.BILL_NM;
      if (!name || seen.has(name)) continue;
      if (!terms.some((t) => name.includes(t))) continue;
      seen.add(name);
      out.push({
        name,
        result: row.PROC_RESULT_CD || row.PROC_RESULT || '계류',
        proposer: row.PROPOSER || row.PPSR_NM || null,
        date: row.PROPOSE_DT || row.PPSL_DT || null,
        summary: null,   // 본문 조회는 응답 지연이 커 Worker에서는 생략
      });
      if (out.length >= 5) return out;
    }
  }
  return out.slice(0, 5);
}

/** 국회 API 응답에서 행 배열을 찾는다(스키마가 버전마다 달라 탐색한다). */
function findRows(obj) {
  if (Array.isArray(obj)) {
    if (obj.length && typeof obj[0] === 'object' && ('BILL_NAME' in obj[0] || 'BILL_NM' in obj[0])) return obj;
    for (const v of obj) { const r = findRows(v); if (r.length) return r; }
    return [];
  }
  if (obj && typeof obj === 'object') {
    if ('row' in obj) return findRows(obj.row);
    for (const v of Object.values(obj)) { const r = findRows(v); if (r.length) return r; }
  }
  return [];
}

// ─────────────────────────────────────────── 통합

export function profileBits(hits, on) {
  const bit = (s) => (on[s] ? (hits[s] && hits[s].length ? 1 : 0) : null);
  return { exec: bit('fiscal'), review: bit('prism'), law: bit('bill'), intl: bit('overseas') };
}

const SOURCE_LABEL = {
  fiscal: '재정(집행)', prism: 'KDI 연구(검토)',
  bill: '국회 의안(입법)', overseas: '해외 OPSI(시행)',
};
const PROFILE_KEY = { fiscal: 'exec', prism: 'review', bill: 'law', overseas: 'intl' };

/** 판정가에게 넘길 조회 결과 표현(터널판 socratic/engine.py와 동일 규칙).
 *
 * 미실행 통로를 빈 배열로 넘기면 '조회했는데 0건'과 구분되지 않아, 판정문이
 * 미실행을 부재로 단정한다. 미실행 통로는 배열 대신 문자열로 바꿔 셀 수 없게
 * 하고 coverage로 실행 여부를 못 박는다. */
export function judgeLookupView(hits) {
  if (!hits) return '미실행 — 어느 통로도 조회하지 않았다. 0건이 아니다.';
  const prof = hits.profile || {};
  const view = { ...hits };
  const queries = { ...(hits.queries || {}) };
  const coverage = {};
  for (const [src, pkey] of Object.entries(PROFILE_KEY)) {
    const label = SOURCE_LABEL[src];
    if (prof[pkey] == null) {
      view[src] = '미실행(조회하지 않음)';
      queries[src] = '미실행';
      coverage[label] = '미실행 — 조회기가 없어 돌리지 않았다. 0건이 아니며 부재의 근거가 될 수 없다.';
    } else {
      const nq = ((hits.queries || {})[src] || []).length;
      coverage[label] = `실행 — 질의 ${nq}개, 히트 ${(hits[src] || []).length}건`;
    }
  }
  view.queries = queries;
  view.coverage = coverage;
  return view;
}

/** 명세의 질의어로 가용한 통로를 모두 조회한다. */
export async function doLookups(env, spec) {
  const db = env.CORPUS || null;
  const on = {
    fiscal: !!db,
    prism: !!db,
    bill: !!env.ASSEMBLY_KEY,
    overseas: !!db,
  };
  if (!Object.values(on).some(Boolean)) return null;

  const queries = {};
  for (const s of ['fiscal', 'prism', 'bill', 'overseas']) {
    queries[s] = on[s] ? (spec.queries?.[s] || []).slice(0, 3) : [];
  }

  const run = async (fn, qs) => {
    const lists = await Promise.all(qs.map((q) => fn(q).catch(() => [])));
    return lists.flat();
  };

  const [fiscal, prism, bill, overseas] = await Promise.all([
    on.fiscal ? run((q) => fiscalLookup(db, q), queries.fiscal) : [],
    on.prism ? run((q) => kdiLookup(db, q), queries.prism) : [],
    on.bill ? run((q) => billLookup(q, env.ASSEMBLY_KEY), queries.bill) : [],
    on.overseas ? run((q) => opsiLookup(db, q), queries.overseas) : [],
  ]);

  const hits = {
    fiscal: dedup(fiscal, 'name').slice(0, 5),
    prism: dedup(prism, 'title').slice(0, 5),
    bill: dedup(bill, 'name').slice(0, 5),
    overseas: dedup(overseas, 'url').slice(0, 5),
  };
  hits.queries = queries;
  hits.profile = profileBits(hits, on);
  return hits;
}

export async function sourcesStatus(env) {
  const db = env.CORPUS || null;
  let fiscal = false, kdi = false, opsi = false;
  if (db) {
    const chk = async (t) => {
      try {
        const r = await db.prepare(`SELECT COUNT(*) AS n FROM ${t}`).first();
        return (r?.n || 0) > 0;
      } catch { return false; }
    };
    [fiscal, kdi, opsi] = await Promise.all([chk('fiscal'), chk('kdi'), chk('opsi')]);
  }
  return { fiscal, prism: kdi, bill: !!env.ASSEMBLY_KEY, overseas: opsi };
}

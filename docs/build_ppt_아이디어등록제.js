// 온 국민 아이디어 등록제 — 정책 아이디어 평가 시스템 설명자료
// 정부 업무보고 스타일 (우석진 패턴) · 16:9
const PptxGenJS = require('pptxgenjs');

const C = {
  PRIMARY: '2563EB', DARK_BG: '1E1E2E', HEADER_BG: '1A1A2E', WHITE: 'FFFFFF',
  TEXT_DARK: '1E293B', TEXT_SUB: '64748B', CARD_BORDER: 'E5E7EB',
  CARD_ALT_BG: 'F8FAFC', TAB_INACTIVE: 'F1F5F9', TAG_BG: '333344',
  LIGHT_BLUE: 'EBF5FF', RED: 'C0392B', GREEN: '2E7D4F', AMBER: 'B7791F',
};
const F = '맑은 고딕';          // 한국어 본문
const FB = '맑은 고딕';         // 한국어 제목(굵게 처리)

const TABS = ['개요', '필요성', '시스템', '대화·채점', '검증 통로', '신뢰성·운영'];
const TOTAL = 28;
const HDR = '온 국민 아이디어 등록제 — 정책 아이디어 평가 시스템';

const pres = new PptxGenJS();
pres.layout = 'LAYOUT_16x9';
let pageNo = 0;

// ─────────── 헬퍼 ───────────
function contentSlide(tabIdx) {
  const s = pres.addSlide();
  pageNo += 1;
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.55, fill: { color: C.HEADER_BG } });
  s.addText(HDR, { x: 0.4, y: 0, w: 7.6, h: 0.55, fontSize: 12, fontFace: F, bold: true,
    color: C.WHITE, valign: 'middle', margin: 0 });
  s.addText(`${pageNo} / ${TOTAL}`, { x: 8.4, y: 0, w: 1.2, h: 0.55, fontSize: 11, fontFace: F,
    color: C.WHITE, align: 'right', valign: 'middle', margin: 0 });
  const tw = 10 / TABS.length;
  TABS.forEach((label, i) => {
    const on = i === tabIdx;
    s.addShape(pres.shapes.RECTANGLE, { x: i * tw, y: 0.55, w: tw, h: 0.35,
      fill: { color: on ? C.PRIMARY : C.TAB_INACTIVE }, line: { color: C.CARD_BORDER, width: 0.5 } });
    s.addText(label, { x: i * tw, y: 0.55, w: tw, h: 0.35, fontSize: 9.5, fontFace: F,
      color: on ? C.WHITE : C.TEXT_SUB, align: 'center', valign: 'middle', margin: 0 });
  });
  return s;
}
function tagline(s, text, y = 1.08) {
  s.addText(text, { x: 0.4, y, w: 9.2, h: 0.26, fontSize: 12, fontFace: F, color: C.PRIMARY, margin: 0 });
}
function sectionTitle(s, text, y = 1.36) {
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.06, h: 0.34, fill: { color: C.PRIMARY } });
  s.addText(text, { x: 0.56, y: y - 0.04, w: 9, h: 0.42, fontSize: 21, fontFace: FB, bold: true,
    color: C.TEXT_DARK, margin: 0 });
}
function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h,
    fill: { color: o.fill || C.WHITE },
    line: { color: o.border || C.CARD_BORDER, width: o.lw || 1 },
    shadow: o.shadow === false ? undefined
      : { type: 'outer', color: '000000', blur: 4, offset: 1, angle: 135, opacity: 0.08 } });
}
function bottomBar(s, text, y = 4.95) {
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 9.2, h: 0.46, fill: { color: C.LIGHT_BLUE } });
  s.addText(text, { x: 0.5, y, w: 9, h: 0.46, fontSize: 12.5, fontFace: F, bold: true,
    color: C.PRIMARY, align: 'center', valign: 'middle', margin: 0 });
}
function txt(s, text, opts) {
  s.addText(text, Object.assign({ fontFace: F, color: C.TEXT_DARK, margin: 0 }, opts));
}
// 불릿 목록
function bullets(s, items, x, y, w, size = 11, gap = 0.235, color = '333333') {
  items.forEach((t, i) => {
    s.addText('•', { x, y: y + i * gap, w: 0.14, h: gap, fontSize: size, fontFace: F,
      color: C.PRIMARY, margin: 0, valign: 'top' });
    s.addText(t, { x: x + 0.15, y: y + i * gap, w: w - 0.15, h: gap, fontSize: size, fontFace: F,
      color, margin: 0, valign: 'top' });
  });
}

// ═══════════ 1. 표지 ═══════════
{
  const s = pres.addSlide();
  pageNo = 1;
  s.background = { color: C.DARK_BG };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 5.625, fill: { color: C.PRIMARY } });
  txt(s, '온 국민 아이디어 등록제', { x: 0.55, y: 0.55, w: 8, h: 0.35, fontSize: 15, color: C.PRIMARY, bold: true });
  txt(s, '대화와 데이터로', { x: 0.55, y: 1.05, w: 9, h: 0.72, fontSize: 40, bold: true, color: C.WHITE });
  txt(s, '검증하는 정책 아이디어 평가', { x: 0.55, y: 1.78, w: 9, h: 0.72, fontSize: 40, bold: true, color: C.WHITE });
  txt(s, '국민 제안을 소크라테스식 문답으로 구조화하고, 국가 데이터 4종으로 선례를 확인합니다',
    { x: 0.55, y: 2.72, w: 8.8, h: 0.4, fontSize: 14, color: 'C7D2E5' });
  const tags = ['12문답 · 5단계', '이원 채점', '검증 통로 4개', 'KDI 발간물 7,362건', 'OPSI 1,015건'];
  tags.forEach((t, i) => {
    const w = 1.78, gap = 0.09, x = 0.55 + i * (w + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.38, w, h: 0.42,
      fill: { color: C.TAG_BG }, rectRadius: 0.08, line: { color: '4A4A5E', width: 0.5 } });
    txt(s, t, { x, y: 3.38, w, h: 0.42, fontSize: 10, color: C.WHITE, align: 'center', valign: 'middle' });
  });
  txt(s, '외부 연구자·정책 담당자 설명자료', { x: 0.55, y: 4.35, w: 6, h: 0.3, fontSize: 12, color: '8A93A8' });
  txt(s, '2026', { x: 7.6, y: 4.3, w: 1.9, h: 0.45, fontSize: 26, bold: true, color: C.PRIMARY, align: 'right' });
}

// ═══════════ 2. 한 장 요약 ═══════════
{
  const s = contentSlide(0);
  tagline(s, 'EXECUTIVE SUMMARY');
  sectionTitle(s, '한 장 요약');
  const rows = [
    ['무엇을', '국민이 제안한 정책 아이디어를 AI가 문답으로 캐묻고, 국가 데이터로 선례를 확인해 평가'],
    ['왜', '제안은 대량으로 접수되지만, 선례 확인과 성의 있는 회신은 담당자 개인 역량에 의존'],
    ['어떻게', '① 소크라테스 문답 12개 → ② 이원 채점 → ③ 검증 통로 4개로 실질 독창성 판정'],
    ['결과', '점수 하나가 아니라 근거·확신도·철회조건이 붙은 판정과 다음 행동 제시'],
  ];
  let y = 1.95;
  rows.forEach((r, i) => {
    card(s, 0.4, y, 9.2, 0.62, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE, shadow: false });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.045, h: 0.62, fill: { color: C.PRIMARY } });
    txt(s, r[0], { x: 0.62, y, w: 1.05, h: 0.62, fontSize: 13, bold: true, color: C.PRIMARY, valign: 'middle' });
    txt(s, r[1], { x: 1.72, y, w: 7.7, h: 0.62, fontSize: 11.5, valign: 'middle' });
    y += 0.7;
  });
  bottomBar(s, '핵심 원칙 —  먼저 대화하고, 그 대화를 근거로 평가한다');
}

// ═══════════ 3. 목차 ═══════════
{
  const s = contentSlide(0);
  tagline(s, 'CONTENTS');
  sectionTitle(s, '설명 순서');
  const items = [
    ['01', '왜 필요한가', '등록제의 구조적 병목'],
    ['02', '무엇인가', '2단계 · 두 개의 축'],
    ['03', '대화와 채점', '12문답과 이원 채점'],
    ['04', '검증 통로 4개', '재정·KDI·의안·해외'],
    ['05', '왜 믿을 수 있나', '근거 등급과 오판 방지'],
    ['06', '구축과 운영', '구성 · 비용 · 다음 단계'],
  ];
  const w = 2.93, h = 1.28, gx = 0.2, gy = 0.2;
  items.forEach((it, i) => {
    const x = 0.4 + (i % 3) * (w + gx), y = 1.95 + Math.floor(i / 3) * (h + gy);
    card(s, x, y, w, h);
    txt(s, it[0], { x: x + 0.16, y: y + 0.12, w: 1, h: 0.42, fontSize: 22, bold: true, color: C.PRIMARY });
    txt(s, it[1], { x: x + 0.16, y: y + 0.56, w: w - 0.3, h: 0.3, fontSize: 14, bold: true });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.16, y: y + 0.88, w: w - 0.32, h: 0.012,
      fill: { color: C.CARD_BORDER } });
    txt(s, it[2], { x: x + 0.16, y: y + 0.94, w: w - 0.3, h: 0.28, fontSize: 10.5, color: C.TEXT_SUB });
  });
}

// ═══════════ 4. 병목 ═══════════
{
  const s = contentSlide(1);
  tagline(s, '01. 왜 필요한가');
  sectionTitle(s, '등록제의 구조적 병목');
  txt(s, '제안은 국민 단위로 들어오는데, 검증은 담당자 한 사람의 시간과 기억에 의존합니다.',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 12.5, color: C.TEXT_SUB });
  const stats = [
    ['접수', '대량', '국민 누구나 상시 제안'],
    ['검증', '수작업', '선례 확인은 개인 검색에 의존'],
    ['회신', '지연·형식', '근거 없는 회신 → 제안자 이탈'],
    ['축적', '흩어짐', '판정 이력이 자산으로 남지 않음'],
  ];
  const w = 2.2, gx = 0.19;
  stats.forEach((st, i) => {
    const x = 0.4 + i * (w + gx);
    const first = i === 0;
    card(s, x, 2.35, w, 1.5, { fill: first ? C.PRIMARY : C.WHITE, border: first ? C.PRIMARY : C.CARD_BORDER });
    txt(s, st[0], { x, y: 2.5, w, h: 0.26, fontSize: 11, color: first ? 'CFE0FF' : C.TEXT_SUB, align: 'center' });
    txt(s, st[1], { x, y: 2.78, w, h: 0.5, fontSize: 21, bold: true,
      color: first ? C.WHITE : C.PRIMARY, align: 'center' });
    txt(s, st[2], { x: x + 0.12, y: 3.32, w: w - 0.24, h: 0.45, fontSize: 9.5,
      color: first ? 'E4EEFF' : C.TEXT_SUB, align: 'center' });
  });
  card(s, 0.4, 4.02, 9.2, 0.78, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '병목의 본질', { x: 0.6, y: 4.13, w: 1.6, h: 0.28, fontSize: 12, bold: true, color: C.PRIMARY });
  txt(s, '"이미 있는 정책인가?"를 확인하려면 예산·연구·입법·해외를 각각 뒤져야 하는데,\n' +
        '이 작업은 제안 한 건마다 반복되며 사람의 기억으로는 재현되지 않습니다.',
    { x: 2.2, y: 4.1, w: 7.2, h: 0.6, fontSize: 11, color: C.TEXT_DARK, lineSpacingMultiple: 1.2 });
}

// ═══════════ 5. 세 한계 (VS) ═══════════
{
  const s = contentSlide(1);
  tagline(s, '01. 왜 필요한가');
  sectionTitle(s, '지금 방식의 세 가지 한계');
  // 헤더
  card(s, 0.4, 1.95, 4.5, 0.44, { fill: '8A93A8', border: '8A93A8', shadow: false });
  txt(s, '현재 (사람 손)', { x: 0.4, y: 1.95, w: 4.5, h: 0.44, fontSize: 12.5, bold: true,
    color: C.WHITE, align: 'center', valign: 'middle' });
  card(s, 5.1, 1.95, 4.5, 0.44, { fill: C.PRIMARY, border: C.PRIMARY, shadow: false });
  txt(s, '제안 시스템 (대화 + 데이터)', { x: 5.1, y: 1.95, w: 4.5, h: 0.44, fontSize: 12.5, bold: true,
    color: C.WHITE, align: 'center', valign: 'middle' });
  const rows = [
    ['제안서를 끝까지 읽어야 뜻을 안다', '문답으로 대상·수단·재원을 끌어냄'],
    ['선례 확인이 담당자 검색 역량에 좌우', '4개 국가 데이터를 동일한 절차로 조회'],
    ['"검토 후 회신" 식 형식적 답변', '근거·확신도·다음 행동을 문서로 제시'],
  ];
  let y = 2.5;
  rows.forEach((r, i) => {
    card(s, 0.4, y, 4.5, 0.62, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE, shadow: false });
    txt(s, '✕', { x: 0.55, y, w: 0.3, h: 0.62, fontSize: 13, bold: true, color: C.RED, valign: 'middle' });
    txt(s, r[0], { x: 0.9, y, w: 3.9, h: 0.62, fontSize: 11, valign: 'middle' });
    txt(s, '▶', { x: 4.9, y, w: 0.22, h: 0.62, fontSize: 11, color: C.PRIMARY, valign: 'middle', align: 'center' });
    card(s, 5.1, y, 4.5, 0.62, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE, shadow: false });
    txt(s, '✓', { x: 5.25, y, w: 0.3, h: 0.62, fontSize: 13, bold: true, color: C.GREEN, valign: 'middle' });
    txt(s, r[1], { x: 5.6, y, w: 3.9, h: 0.62, fontSize: 11, valign: 'middle' });
    y += 0.7;
  });
  bottomBar(s, '자동 채점기가 아니라, 캐묻는 대화 + 근거 있는 선례 확인이 필요합니다');
}

// ═══════════ 6. 해법의 방향 ═══════════
{
  const s = contentSlide(1);
  tagline(s, '01. 왜 필요한가');
  sectionTitle(s, '그래서 무엇이 필요한가');
  const cols = [
    ['01', '캐묻는 대화', ['제안자가 스스로 설계를 진술하게', '대상·수단·전달경로·재원을 확보',
      '반증 조건까지 답하게 유도', '짧은 제안서의 공백을 메움']],
    ['02', '데이터 대조', ['예산·연구·입법·해외를 교차 확인', '조회 절차와 판정 규칙을 문서로 고정',
      '조회 근거를 인용 가능한 형태로', '중복 제안을 초기에 식별']],
    ['03', '판정의 절제', ['찾은 범위까지만 말한다', '확신도와 철회조건을 함께 제시',
      '미발견을 독창성 확정으로 쓰지 않음', '최종 결정은 사람이']],
  ];
  const w = 2.93, gx = 0.2;
  cols.forEach((c, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.85);
    txt(s, c[0], { x: x + 0.18, y: 2.08, w: 1, h: 0.4, fontSize: 22, bold: true, color: C.PRIMARY });
    txt(s, c[1], { x: x + 0.18, y: 2.52, w: w - 0.36, h: 0.32, fontSize: 14.5, bold: true });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.18, y: 2.9, w: w - 0.36, h: 0.012, fill: { color: C.CARD_BORDER } });
    bullets(s, c[2], x + 0.18, 3.02, w - 0.36, 10.2, 0.4);
  });
  txt(s, '"평가의 목적은 등수를 매기는 것이 아니라, 제안을 다음 단계로 보낼 수 있게 만드는 것"',
    { x: 0.4, y: 4.97, w: 9.2, h: 0.4, fontSize: 13, italic: true, color: C.PRIMARY, align: 'center' });
}

// ═══════════ 7. 대원칙 ═══════════
{
  const s = contentSlide(2);
  tagline(s, '02. 무엇인가');
  sectionTitle(s, '대원칙 — 먼저 대화, 그 다음 평가');
  card(s, 0.4, 1.95, 4.5, 1.35, { fill: 'FDF2F2', border: 'F0C0C0' });
  txt(s, '하지 않는 것', { x: 0.6, y: 2.08, w: 3, h: 0.3, fontSize: 12, bold: true, color: C.RED });
  txt(s, '아이디어 문장만 보고\n곧바로 선례를 검색해 판정', { x: 0.6, y: 2.42, w: 4.1, h: 0.7,
    fontSize: 12.5, color: C.TEXT_DARK, lineSpacingMultiple: 1.25 });
  card(s, 5.1, 1.95, 4.5, 1.35, { fill: 'F0F9F3', border: 'B8DCC6' });
  txt(s, '하는 것', { x: 5.3, y: 2.08, w: 3, h: 0.3, fontSize: 12, bold: true, color: C.GREEN });
  txt(s, '12문답으로 설계를 끌어낸 뒤\n그 대화 내용을 근거로 조회·판정', { x: 5.3, y: 2.42, w: 4.1, h: 0.7,
    fontSize: 12.5, color: C.TEXT_DARK, lineSpacingMultiple: 1.25 });
  card(s, 0.4, 3.45, 9.2, 1.35, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '왜 이 순서인가', { x: 0.62, y: 3.58, w: 3, h: 0.3, fontSize: 12.5, bold: true, color: C.PRIMARY });
  bullets(s, [
    '짧은 제안문에는 대상·전달경로·재원이 대개 빠져 있어, 그대로 검색하면 엉뚱한 선례가 걸린다',
    '대화를 거치면 "무엇이 실제로 새로운 부분인지"가 특정되어, 조회 질의가 정확해진다',
    '제안자가 스스로 약점을 말하게 되므로, 평가가 일방적 판정이 아니라 상호 검증이 된다',
  ], 0.62, 3.95, 8.8, 11, 0.28);
}

// ═══════════ 8. 전체 흐름 ═══════════
{
  const s = contentSlide(2);
  tagline(s, '02. 무엇인가');
  sectionTitle(s, '전체 흐름 — 3단계');
  const steps = [
    ['STEP 1', '소크라테스 문답', ['12개 질문 · 5단계', '명료화 → 독창성 → 실용성', '→ 수용태도 → 자기평가', '약 15분 소요']],
    ['STEP 2', '이원 채점 + 선례 조사', ['체크리스트 30항목', '+ 종합 판단', '검증 통로 4개 조회', '실질 독창성 판정']],
    ['STEP 3', '5문장 결과', ['현재가치 · 잠재가치', '핵심위험 · 근거신뢰도', '다음 검증행동', '+ 2×2 위치 판정']],
  ];
  const w = 2.75, gx = 0.52;
  steps.forEach((st, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.6);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.36, fill: { color: C.PRIMARY } });
    txt(s, st[0], { x, y: 1.95, w, h: 0.36, fontSize: 11, bold: true, color: C.WHITE, align: 'center', valign: 'middle' });
    txt(s, st[1], { x: x + 0.15, y: 2.45, w: w - 0.3, h: 0.34, fontSize: 14, bold: true, align: 'center' });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.3, y: 2.86, w: w - 0.6, h: 0.012, fill: { color: C.CARD_BORDER } });
    bullets(s, st[2], x + 0.2, 2.98, w - 0.38, 10.2, 0.31);
    if (i < 2) {
      txt(s, '▶', { x: x + w + 0.06, y: 3.0, w: 0.4, h: 0.4, fontSize: 18, color: C.PRIMARY, align: 'center' });
    }
  });
  bottomBar(s, '문답이 끝나기 전에는 선례 조사를 시작하지 않습니다 — 대화가 조회의 입력이 됩니다');
}

// ═══════════ 9. 두 개의 축 ═══════════
{
  const s = contentSlide(2);
  tagline(s, '02. 무엇인가');
  sectionTitle(s, '두 개의 축 — 역할 분담');
  const axes = [
    ['축 A', '대화 채점', '제안이 얼마나 잘 방어되는가',
      ['12문답에서 드러난 진술을 평가', '체크리스트 30항목 + 종합판단',
       '독창성 35% · 실용성 35% · 수용태도 30%', '산출: 0~10 점수 + 불일치 폭'], C.PRIMARY],
    ['축 B', '선례 검증', '그 아이디어가 실제로 새로운가',
      ['국가 데이터 4개 통로를 조회', '조회 결과와 설계를 대조해 판정',
       '근거 등급 A급 / B급 구분', '산출: 4구간 밴드 + 확신도 + 근거'], '1E4E8C'],
  ];
  const w = 4.5, gx = 0.2;
  axes.forEach((a, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.75);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.42, fill: { color: a[4] } });
    txt(s, `${a[0]}  ·  ${a[1]}`, { x, y: 1.95, w, h: 0.42, fontSize: 13, bold: true,
      color: C.WHITE, align: 'center', valign: 'middle' });
    txt(s, `"${a[2]}"`, { x: x + 0.18, y: 2.52, w: w - 0.36, h: 0.3, fontSize: 12.5,
      italic: true, color: C.PRIMARY, align: 'center' });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.3, y: 2.9, w: w - 0.6, h: 0.012, fill: { color: C.CARD_BORDER } });
    bullets(s, a[3], x + 0.22, 3.05, w - 0.42, 10.8, 0.36);
  });
  card(s, 0.4, 4.88, 9.2, 0.52, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '두 축은 서로 다른 질문에 답합니다 —  "말을 잘했는가(A)"와 "실제로 새로운가(B)"는 별개입니다',
    { x: 0.5, y: 4.88, w: 9, h: 0.52, fontSize: 12, bold: true, color: C.PRIMARY,
      align: 'center', valign: 'middle' });
}

// ═══════════ 10. 12문답 5단계 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ① — 12문답 5단계 구조');
  const stages = [
    ['명료화', '2문', '한 문장 정의로 압축\n대상·문제·방법 확인'],
    ['독창성', '3문', '기존 해법과의 차이\n모방 어려운 차별점인가'],
    ['실용성', '3문', '필요 자원과 최대 장애물\n최소 실행 버전(MVP)'],
    ['수용태도', '3문', '누가 쓰고 왜 갈아타나\n반대할 이해관계자는'],
    ['자기평가', '1문', '스스로 꼽는 최대 약점\n그 보완 방안'],
  ];
  const w = 1.79, gx = 0.11;
  stages.forEach((st, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.5);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.34, fill: { color: C.PRIMARY } });
    txt(s, st[0], { x, y: 1.95, w, h: 0.34, fontSize: 11.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    txt(s, st[1], { x, y: 2.42, w, h: 0.45, fontSize: 20, bold: true, color: C.PRIMARY, align: 'center' });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.2, y: 2.94, w: w - 0.4, h: 0.012, fill: { color: C.CARD_BORDER } });
    txt(s, st[2], { x: x + 0.08, y: 3.06, w: w - 0.16, h: 1.2, fontSize: 9, color: C.TEXT_SUB,
      align: 'center', lineSpacingMultiple: 1.3 });
  });
  card(s, 0.4, 4.6, 9.2, 0.8, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '설계 의도', { x: 0.62, y: 4.7, w: 1.4, h: 0.28, fontSize: 11.5, bold: true, color: C.PRIMARY });
  txt(s, '채점 기준(독창성·실용성·수용태도)마다 3문씩 배정해, 점수의 근거가 될 진술을 반드시 확보합니다.\n' +
        '마지막 자기평가 1문은 제안자가 스스로 약점을 인정하는지를 보는 항목으로, 수용태도 채점에 직결됩니다.',
    { x: 2.05, y: 4.68, w: 7.4, h: 0.62, fontSize: 10.5, lineSpacingMultiple: 1.25 });
}

// ═══════════ 11. 질문 설계 원리 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ② — 질문은 무엇을 캐내는가');
  const rows = [
    ['명료화', '대상 · 문제 · 방법', '"누구의 어떤 문제를 어떻게"를 한 문장으로 합의', C.PRIMARY],
    ['독창성', '차별점 · 공백의 이유', '기존 해법 식별 → 차이 진술 → 왜 아직 없었나 → 모방 장벽', '1E4E8C'],
    ['실용성', '자원 · 장애물 · MVP', '필요 인력·예산, 최대 장애물과 대응, 단계적 실행 경로', '2563EB'],
    ['수용태도', '사용자 · 전환비용 · 반대', '왜 갈아타는가, 손해 보는 이해관계자는 누구인가', '1E4E8C'],
    ['자기평가', '약점 인정', '가장 큰 약점 하나와 보완 방안 — 정직성의 지표', '2563EB'],
  ];
  let y = 1.95;
  rows.forEach((r, i) => {
    card(s, 0.4, y, 9.2, 0.56, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE, shadow: false });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.045, h: 0.56, fill: { color: r[3] } });
    txt(s, r[0], { x: 0.6, y, w: 1.05, h: 0.56, fontSize: 12, bold: true, color: r[3], valign: 'middle' });
    txt(s, r[1], { x: 1.7, y, w: 2.15, h: 0.56, fontSize: 10.5, bold: true, valign: 'middle' });
    txt(s, r[2], { x: 3.95, y, w: 5.5, h: 0.56, fontSize: 10.5, color: C.TEXT_SUB, valign: 'middle' });
    y += 0.63;
  });
  card(s, 0.4, 5.0, 9.2, 0.45, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '질문자는 답을 평가하지 않습니다 — 캐묻기만 하고, 채점은 대화가 끝난 뒤 별도로 수행됩니다',
    { x: 0.5, y: 5.0, w: 9, h: 0.45, fontSize: 11.5, bold: true, color: C.PRIMARY,
      align: 'center', valign: 'middle' });
}

// ═══════════ 12. 이원 채점 개요 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ③ — 이원 채점: 두 번 재고 평균한다');
  const two = [
    ['① 체크리스트 채점', '기계적 · 재현 가능', ['기준마다 이진 항목 10개 (총 30개)',
      '"이 사건이 대화에 있었는가"로만 판정', '충족 개수 = 그대로 0~10점', '판정 기준이 문서로 고정되어 있음'], C.PRIMARY],
    ['② 종합 판단 채점', '맥락적 · 질을 봄', ['대화 전체를 읽고 기준별 0~10점',
      '항목 충족 여부로 잡히지 않는 깊이 반영', '판단 근거(rationale)를 함께 기록', '강점·보완점·격려 문구 생성'], '1E4E8C'],
  ];
  const w = 4.5, gx = 0.2;
  two.forEach((t, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.45);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.4, fill: { color: t[3] } });
    txt(s, t[0], { x, y: 1.95, w, h: 0.4, fontSize: 12.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    txt(s, t[1], { x: x + 0.15, y: 2.45, w: w - 0.3, h: 0.28, fontSize: 11, italic: true,
      color: C.PRIMARY, align: 'center' });
    bullets(s, t[2], x + 0.22, 2.82, w - 0.42, 10.5, 0.36);
  });
  card(s, 0.4, 4.55, 9.2, 0.85, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '기준별 최종점수  =  ( 체크리스트 점수  +  종합판단 점수 )  ÷  2',
    { x: 0.4, y: 4.63, w: 9.2, h: 0.36, fontSize: 14, bold: true, color: C.PRIMARY, align: 'center' });
  txt(s, '종합점수 = 독창성 35% + 실용성 35% + 수용태도 30% 가중 평균  (가중치 고정)',
    { x: 0.4, y: 5.0, w: 9.2, h: 0.3, fontSize: 11, color: C.TEXT_SUB, align: 'center' });
}

// ═══════════ 13. 체크리스트 30항목 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ④ — 체크리스트 30항목 (기준별 10개)');
  const cols = [
    ['독창성 O1~O10', ['O1 기존 해법 식별', 'O2 차별점 명시', 'O3 차별점의 검증 가능성',
      'O4 공백의 설명', 'O5 모방 장벽', 'O6 관점 전환', 'O7 새로움–가치 연결',
      'O8 반례 대응', 'O9 한계 인정', 'O10 무모순']],
    ['실용성 P1~P10', ['P1 자원 구체화', 'P2 MVP 정의', 'P3 핵심 장애물 식별',
      'P4 장애물 대응책', 'P5 구현 경로', 'P6 비용 대비 효과', 'P7 운영 주체 특정',
      'P8 단계적 경로', 'P9 실행 리스크 인정', 'P10 무모순']],
    ['수용태도 A1~A10', ['A1 수용 주체 특정', 'A2 상대적 이점', 'A3 전환 비용',
      'A4 적합성', 'A5 시험 가능성', 'A6 반대 세력 식별', 'A7 저항 대응',
      'A8 확산 경로', 'A9 수용 리스크 인정', 'A10 무모순']],
  ];
  const w = 2.93, gx = 0.2;
  cols.forEach((c, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.9, w, 2.92);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.9, w, h: 0.36, fill: { color: C.PRIMARY } });
    txt(s, c[0], { x, y: 1.9, w, h: 0.36, fontSize: 11.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    c[1].forEach((item, j) => {
      txt(s, item, { x: x + 0.16, y: 2.36 + j * 0.245, w: w - 0.3, h: 0.24, fontSize: 9.8, color: '333333' });
    });
  });
  card(s, 0.4, 4.95, 9.2, 0.5, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '각 항목은 "있었다/없었다"로만 판정 —  주관적 인상이 아니라 대화에서 확인 가능한 사건입니다',
    { x: 0.5, y: 4.95, w: 9, h: 0.5, fontSize: 11.5, bold: true, color: C.PRIMARY,
      align: 'center', valign: 'middle' });
}

// ═══════════ 14. 이론적 근거 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ⑤ — 체크리스트의 이론적 근거');
  txt(s, '항목을 임의로 만들지 않고, 각 기준마다 확립된 평가 프레임을 채택했습니다.',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 12, color: C.TEXT_SUB });
  const rows = [
    ['독창성', 'Runco & Jaeger — 창의성 표준 정의 (새로움 + 유용성)\nDean et al. (2006) — 아이디어 평가 구인'],
    ['실용성', 'TELOS 타당성 프레임워크\nReal-Win-Worth (Day, HBR 2007) · 린 스타트업 MVP'],
    ['수용태도', 'Rogers — 혁신 확산 이론 5속성\nDavis — 기술수용모형(TAM)'],
  ];
  let y = 2.35;
  rows.forEach((r, i) => {
    card(s, 0.4, y, 9.2, 0.78, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.05, h: 0.78, fill: { color: C.PRIMARY } });
    txt(s, r[0], { x: 0.68, y, w: 1.5, h: 0.78, fontSize: 13, bold: true, color: C.PRIMARY, valign: 'middle' });
    txt(s, r[1], { x: 2.25, y: y + 0.08, w: 7.2, h: 0.62, fontSize: 10.8, lineSpacingMultiple: 1.3 });
    y += 0.88;
  });
  card(s, 0.4, 5.0, 9.2, 0.45, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '항목별 근거는 별도 문서(checklist-rationale)에 정리되어 있어, 외부 검토·수정이 가능합니다',
    { x: 0.5, y: 5.0, w: 9, h: 0.45, fontSize: 11, color: C.TEXT_SUB, align: 'center', valign: 'middle' });
}

// ═══════════ 15. 불일치 = 신뢰구간 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ⑥ — 두 채점의 불일치를 숨기지 않는다');
  card(s, 0.4, 1.92, 9.2, 1.05, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '기계적 채점(체크리스트)과 맥락적 채점(종합판단)이 어긋난다는 것은,\n' +
        '그 평가 자체가 불확실하다는 신호입니다. 이 차이를 숨기지 않고 점수 범위로 표시합니다.',
    { x: 0.62, y: 2.05, w: 8.8, h: 0.8, fontSize: 12, lineSpacingMultiple: 1.3 });
  const ex = [
    ['두 채점이 일치', '체크리스트 7 · 종합 7', '7.0 (범위 좁음)', '판정 신뢰 높음', C.GREEN],
    ['두 채점이 어긋남', '체크리스트 8 · 종합 4', '6.0 (범위 넓음)', '추가 확인 필요', C.AMBER],
  ];
  let y = 3.15;
  ex.forEach((e) => {
    card(s, 0.4, y, 9.2, 0.75);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.05, h: 0.75, fill: { color: e[4] } });
    txt(s, e[0], { x: 0.66, y, w: 2.1, h: 0.75, fontSize: 12, bold: true, color: e[4], valign: 'middle' });
    txt(s, e[1], { x: 2.8, y, w: 2.6, h: 0.75, fontSize: 11, color: C.TEXT_SUB, valign: 'middle' });
    txt(s, e[2], { x: 5.45, y, w: 2.1, h: 0.75, fontSize: 12, bold: true, valign: 'middle' });
    txt(s, e[3], { x: 7.6, y, w: 1.9, h: 0.75, fontSize: 11, color: e[4], valign: 'middle' });
    y += 0.85;
  });
  bottomBar(s, '"6.0 (5.2–6.8)" 형태로 제시 — 통계적 신뢰구간이 아니라 두 채점의 편차 폭입니다');
}

// ═══════════ 16. 5문장 결과 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ⑦ — 산출물 ①: 5문장 결과');
  txt(s, '새 점수를 만들지 않고, 이미 산출된 채점 결과를 담당자가 읽을 서술로 묶습니다.',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 12, color: C.TEXT_SUB });
  const five = [
    ['현재 가치', '지금 근거로 방어 가능한 수준은 얼마이며, 가장 탄탄한 축은 무엇인가'],
    ['잠재 가치', '무엇이 보완되면 어디까지 갈 수 있는가'],
    ['핵심 위험', '이 제안을 무너뜨릴 가장 큰 요인은 무엇인가'],
    ['근거 신뢰도', '이 판단이 어느 정도 근거에 서 있는가 (범위 · 확신도)'],
    ['다음 검증행동', '누가 무엇을 확인하면 판정이 바뀌는가'],
  ];
  let y = 2.3;
  five.forEach((f, i) => {
    card(s, 0.4, y, 9.2, 0.5, { fill: i % 2 ? C.CARD_ALT_BG : C.WHITE, shadow: false });
    s.addShape(pres.shapes.OVAL, { x: 0.55, y: y + 0.1, w: 0.3, h: 0.3, fill: { color: C.PRIMARY } });
    txt(s, String(i + 1), { x: 0.55, y: y + 0.1, w: 0.3, h: 0.3, fontSize: 10, bold: true,
      color: C.WHITE, align: 'center', valign: 'middle' });
    txt(s, f[0], { x: 1.0, y, w: 1.75, h: 0.5, fontSize: 12, bold: true, color: C.PRIMARY, valign: 'middle' });
    txt(s, f[1], { x: 2.8, y, w: 6.65, h: 0.5, fontSize: 11, valign: 'middle' });
    y += 0.56;
  });
  card(s, 0.4, 5.1, 9.2, 0.38, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '제안자에게 그대로 회신할 수 있는 형태 — "검토 후 회신"을 대체합니다',
    { x: 0.5, y: 5.1, w: 9, h: 0.38, fontSize: 11, bold: true, color: C.PRIMARY, align: 'center', valign: 'middle' });
}

// ═══════════ 17. 2×2 위치 판정 ═══════════
{
  const s = contentSlide(3);
  tagline(s, '03. 대화와 채점');
  sectionTitle(s, '축 A ⑧ — 산출물 ②: 2×2 위치 판정');
  txt(s, '축 A(방어력)와 축 B(실질 독창성)를 교차해 담당자의 다음 행동을 지정합니다.',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 12, color: C.TEXT_SUB });
  // 축 라벨
  txt(s, '실질 독창성 (축 B)  높음  ▲', { x: 0.4, y: 2.28, w: 3.2, h: 0.25, fontSize: 10, color: C.TEXT_SUB });
  const cells = [
    ['보완 후 재문답', '독창적이나 근거 부족 —\n문답을 보완해 방어력 확보', 'FFF8E8', C.AMBER, 2.55],
    ['추진', '독창적이고 방어력도 충분 —\n다음 단계로 이관', 'F0F9F3', C.GREEN, 2.55],
    ['보류', '새롭지도 방어되지도 않음 —\n제안자에게 근거와 함께 회신', 'F5F5F5', '8A93A8', 3.72],
    ['기존 사업 개선으로 재포지셔닝', '방어는 되나 선례 존재 —\n기존 사업 개선안으로 전환', 'EFF4FB', C.PRIMARY, 3.72],
  ];
  cells.forEach((c, i) => {
    const x = i % 2 === 0 ? 0.4 : 5.1;
    card(s, x, c[4], 4.5, 1.1, { fill: c[2], border: c[3], lw: 1.2 });
    txt(s, c[0], { x: x + 0.18, y: c[4] + 0.12, w: 4.14, h: 0.32, fontSize: 13, bold: true, color: c[3] });
    txt(s, c[1], { x: x + 0.18, y: c[4] + 0.48, w: 4.14, h: 0.55, fontSize: 10, color: C.TEXT_SUB,
      lineSpacingMultiple: 1.2 });
  });
  txt(s, '방어력 낮음 (축 A)', { x: 0.4, y: 4.92, w: 4.5, h: 0.28, fontSize: 10.5,
    color: C.TEXT_SUB, align: 'center' });
  txt(s, '방어력 높음 (축 A)  ▶', { x: 5.1, y: 4.92, w: 4.5, h: 0.28, fontSize: 10.5,
    color: C.TEXT_SUB, align: 'center' });
  card(s, 0.4, 5.25, 9.2, 0.32, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '판정 보류(확신도 부족) 시에는 이 칸을 표시하지 않습니다', { x: 0.5, y: 5.25, w: 9, h: 0.32,
    fontSize: 10, bold: true, color: C.PRIMARY, align: 'center', valign: 'middle' });
}

// ═══════════ 18. 검증 통로 4개 ★ ═══════════
{
  const s = contentSlide(4);
  tagline(s, '04. 검증 통로');
  sectionTitle(s, '축 B — 검증 통로 4개');
  txt(s, '네 소스는 서로 다른 질문에 답합니다. 하나라도 빠지면 "없다"는 결론을 신뢰할 수 없습니다.',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 12, color: C.TEXT_SUB });
  const ch = [
    ['①', '재정', '예산이 붙어\n집행되었나', '세출예산\n최근 5개 연도', '국내'],
    ['②', 'KDI 연구', '연구로\n검토되었나', 'KDI 발간물 7,362건\n(정책연구 1,178)', '국내'],
    ['③', '국회 의안', '입법이\n시도되었나', '발의 · 의결현황\n본문 포함', '국내'],
    ['④', '해외사례', '다른 나라가\n실제 시행했나', 'OECD OPSI\n1,015건', '해외'],
  ];
  const w = 2.2, gx = 0.19;
  ch.forEach((c, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 2.3, w, 2.3);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.3, w, h: 0.42, fill: { color: i === 3 ? '1E4E8C' : C.PRIMARY } });
    txt(s, `${c[0]}  ${c[1]}`, { x, y: 2.3, w, h: 0.42, fontSize: 12.5, bold: true,
      color: C.WHITE, align: 'center', valign: 'middle' });
    txt(s, c[2], { x: x + 0.1, y: 2.84, w: w - 0.2, h: 0.55, fontSize: 11.5, bold: true,
      align: 'center', lineSpacingMultiple: 1.2 });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.25, y: 3.48, w: w - 0.5, h: 0.012, fill: { color: C.CARD_BORDER } });
    txt(s, c[3], { x: x + 0.1, y: 3.6, w: w - 0.2, h: 0.5, fontSize: 10, color: C.TEXT_SUB,
      align: 'center', lineSpacingMultiple: 1.25 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + w / 2 - 0.32, y: 4.18, w: 0.64, h: 0.26,
      fill: { color: c[4] === '해외' ? 'E8EEF8' : C.TAB_INACTIVE }, rectRadius: 0.06, line: { color: C.CARD_BORDER, width: 0.5 } });
    txt(s, c[4], { x: x + w / 2 - 0.32, y: 4.18, w: 0.64, h: 0.26, fontSize: 9,
      color: C.TEXT_SUB, align: 'center', valign: 'middle' });
  });
  bottomBar(s, '집행 · 검토 · 입법 · 해외 — 한 질문에 한 소스. 교차 확인이 판정의 근거가 됩니다');
}

// ═══════════ 19. 재정 + 국회 의안 ═══════════
{
  const s = contentSlide(4);
  tagline(s, '04. 검증 통로');
  sectionTitle(s, '통로 ① 재정 · ③ 국회 의안 — 집행과 입법');
  const two = [
    ['① 재정 (세출예산)', '예산이 붙어 집행되었나',
      ['사업명 + 예산 시계열을 조회', '최근 연도 예산이 0이면 종료된 사업',
       '예산 존재 = 집행의 직접 증거', '단, 제목만으로는 설계 동일성을 알 수 없음'], C.PRIMARY],
    ['③ 국회 의안', '입법이 시도되었나',
      ['의안명 + 발의자 + 의결현황 조회', '법률안은 제안이유·주요내용 본문까지 확보',
       '가결 = 제도화 완료 / 부결 = 강한 반증', '임기만료폐기는 기각이 아님 — 감점 근거로 쓰지 않음'], '1E4E8C'],
  ];
  const w = 4.5, gx = 0.2;
  two.forEach((t, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.5);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.4, fill: { color: t[3] } });
    txt(s, t[0], { x, y: 1.95, w, h: 0.4, fontSize: 12.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    txt(s, `"${t[1]}"`, { x: x + 0.15, y: 2.45, w: w - 0.3, h: 0.28, fontSize: 11.5, italic: true,
      color: C.PRIMARY, align: 'center' });
    bullets(s, t[2], x + 0.22, 2.85, w - 0.42, 10.2, 0.38);
  });
  card(s, 0.4, 4.6, 9.2, 0.82, { fill: 'FFF8E8', border: 'E8D5A8', shadow: false });
  txt(s, '주의', { x: 0.62, y: 4.7, w: 0.8, h: 0.28, fontSize: 11.5, bold: true, color: C.AMBER });
  txt(s, '국회 발의안 상당수는 심사가 끝나지 않은 채 "임기만료폐기"로 사라집니다.\n' +
        '이를 "국회에서 폐기된 아이디어"로 읽으면 오판이므로, 판정 규칙에서 명시적으로 배제했습니다.',
    { x: 1.5, y: 4.68, w: 7.95, h: 0.62, fontSize: 10.5, lineSpacingMultiple: 1.25 });
}

// ═══════════ 20. KDI 연구 (kdinov) ═══════════
{
  const s = contentSlide(4);
  tagline(s, '04. 검증 통로');
  sectionTitle(s, '통로 ② KDI 연구 — 2차원 판정');
  txt(s, '단순 키워드 일치가 아니라, 아이디어를 대상×수단×영역으로 분해해 문헌마다 두 축으로 판정합니다.',
    { x: 0.4, y: 1.86, w: 9.2, h: 0.3, fontSize: 11.5, color: C.TEXT_SUB });
  // 좌: 중첩도
  card(s, 0.4, 2.28, 4.5, 2.35);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 2.28, w: 4.5, h: 0.36, fill: { color: C.PRIMARY } });
  txt(s, '중첩도 — 얼마나 겹치는가', { x: 0.4, y: 2.28, w: 4.5, h: 0.36, fontSize: 11.5, bold: true,
    color: C.WHITE, align: 'center', valign: 'middle' });
  const codes = [['N0', '3축이 한 자리에서 일치 — 신규 아님'], ['N1', '축 하나가 다르거나 흩어져 있음'],
    ['N2', '축 하나만 강하게 겹침'], ['N3', '영역만 중첩'], ['N4', '무관']];
  codes.forEach((c, i) => {
    const y = 2.76 + i * 0.36;
    txt(s, c[0], { x: 0.6, y, w: 0.55, h: 0.3, fontSize: 11.5, bold: true, color: C.PRIMARY });
    txt(s, c[1], { x: 1.2, y, w: 3.55, h: 0.3, fontSize: 10, color: '333333' });
  });
  // 우: 역할
  card(s, 5.1, 2.28, 4.5, 2.35);
  s.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 2.28, w: 4.5, h: 0.36, fill: { color: '1E4E8C' } });
  txt(s, '역할 — 어떻게 쓸 것인가', { x: 5.1, y: 2.28, w: 4.5, h: 0.36, fontSize: 11.5, bold: true,
    color: C.WHITE, align: 'center', valign: 'middle' });
  const roles = [['실행', '이미 제도화·집행 — 강한 반증', C.RED],
    ['경합', '같은 수단을 이미 제안 — 차별화 필요', C.AMBER],
    ['근거', '효과분석만 — 인용해 정당화에 사용', C.GREEN],
    ['선례', '영역은 다르나 설계 참조 가능', C.PRIMARY],
    ['무관', '관련 없음', '8A93A8']];
  roles.forEach((r, i) => {
    const y = 2.76 + i * 0.36;
    txt(s, r[0], { x: 5.3, y, w: 0.6, h: 0.3, fontSize: 11.5, bold: true, color: r[2] });
    txt(s, r[1], { x: 5.95, y, w: 3.5, h: 0.3, fontSize: 10, color: '333333' });
  });
  card(s, 0.4, 4.78, 9.2, 0.62, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '"중첩도가 높다"와 "위협적이다"는 다릅니다 — 같은 주제라도 역할이 \'근거\'면 감점이 아니라 인용처입니다.',
    { x: 0.5, y: 4.78, w: 9, h: 0.62, fontSize: 11, bold: true, color: C.PRIMARY,
      align: 'center', valign: 'middle' });
}

// ═══════════ 21. 해외사례 ═══════════
{
  const s = contentSlide(4);
  tagline(s, '04. 검증 통로');
  sectionTitle(s, '통로 ④ 해외사례 — OECD OPSI');
  const stats = [['1,015', '수집 사례'], ['98', '국가'], ['1,015', '본문 확보'], ['4', '정부 수준']];
  const w = 2.2, gx = 0.19;
  stats.forEach((st, i) => {
    const x = 0.4 + i * (w + gx);
    const first = i === 0;
    card(s, x, 1.95, w, 1.0, { fill: first ? C.PRIMARY : C.WHITE, border: first ? C.PRIMARY : C.CARD_BORDER });
    txt(s, st[0], { x, y: 2.08, w, h: 0.5, fontSize: 24, bold: true,
      color: first ? C.WHITE : C.PRIMARY, align: 'center' });
    txt(s, st[1], { x, y: 2.6, w, h: 0.28, fontSize: 10, color: first ? 'E4EEFF' : C.TEXT_SUB, align: 'center' });
  });
  const cols = [
    ['무엇을 답하는가', ['다른 나라 정부가 실제로 시행했는가', '국내 미발견이어도 해외 선례 반영',
      '"국내 최초"와 "세계 최초"를 구분']],
    ['무엇이 들어 있나', ['문제·해법·혁신요소·성과', '실패요인·성공조건·복제 가능성',
      '제목만이 아니라 설계 본문까지 대조']],
    ['어떻게 확보했나', ['OECD 공개 사례를 정리해 로컬 코퍼스 구축',
      '자동 수집 차단 시 우회하지 않음', '기관이 설명할 수 있는 방식만 채택']],
  ];
  const cw = 2.93, cgx = 0.2;
  cols.forEach((c, i) => {
    const x = 0.4 + i * (cw + cgx);
    card(s, x, 3.12, cw, 1.75);
    txt(s, c[0], { x: x + 0.16, y: 3.25, w: cw - 0.32, h: 0.3, fontSize: 12, bold: true, color: C.PRIMARY });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.16, y: 3.58, w: cw - 0.32, h: 0.012, fill: { color: C.CARD_BORDER } });
    bullets(s, c[1], x + 0.16, 3.68, cw - 0.32, 9.8, 0.36);
  });
  bottomBar(s, 'A급(해외·자기신고) — 각국이 스스로 신고한 사례로, 성과는 독립 검증되지 않았습니다', 5.02);
}

// ═══════════ 22. 근거 등급 ═══════════
{
  const s = contentSlide(5);
  tagline(s, '05. 왜 믿을 수 있나');
  sectionTitle(s, '근거 등급 — A급과 B급을 섞지 않는다');
  const two = [
    ['A급 — 조회로 확인', C.GREEN, 'F0F9F3',
      ['국내 A급: 재정·KDI·의안 조회 결과', 'A급(해외): OPSI — 각국 자기신고, 성과 미검증',
       '사업명·연도·부처·예산·의안명 인용 가능',
       '단, 설계가 같음을 함께 논증해야 감점 근거']],
    ['B급 — 모델의 기억', C.AMBER, 'FFF8E8',
      ['조회로 검증되지 않은 AI의 배경지식', '고유명사(사업명·연도) 인용 금지',
       '"유사 취지의 바우처 계열이 존재" 수준의 유형 진술만']],
  ];
  const w = 4.5, gx = 0.2;
  two.forEach((t, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.15, { fill: t[2], border: t[1], lw: 1.2 });
    txt(s, t[0], { x: x + 0.18, y: 2.1, w: w - 0.36, h: 0.34, fontSize: 14, bold: true, color: t[1] });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.18, y: 2.5, w: w - 0.36, h: 0.012, fill: { color: t[1] } });
    bullets(s, t[3], x + 0.18, 2.6, w - 0.36, 10, 0.35);
  });
  card(s, 0.4, 4.25, 9.2, 1.15, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '왜 구분하는가', { x: 0.62, y: 4.36, w: 2, h: 0.28, fontSize: 12, bold: true, color: C.PRIMARY });
  bullets(s, [
    'AI가 그럴듯하게 지어낸 사업명이 공문서에 인용되는 것을 구조적으로 차단합니다',
    '담당자는 A급 근거만 그대로 인용하고, B급은 "확인이 필요한 단서"로 취급하면 됩니다',
  ], 0.62, 4.7, 8.8, 11, 0.3);
}

// ═══════════ 23. 미발견 + 오판 방지 ═══════════
{
  const s = contentSlide(5);
  tagline(s, '05. 왜 믿을 수 있나');
  sectionTitle(s, '미발견은 독창성을 확정하지 않는다');
  card(s, 0.4, 1.92, 9.2, 0.95, { fill: 'FDF2F2', border: 'F0C0C0', shadow: false });
  txt(s, '"찾지 못했다"가 될 수 있는 네 가지', { x: 0.62, y: 2.02, w: 4, h: 0.28,
    fontSize: 12, bold: true, color: C.RED });
  txt(s, '①  실제로 선례가 없다        ②  이름이 달라 검색이 놓쳤다\n' +
        '③  데이터가 못 덮는 영역(지자체·기금·행정지침)        ④  질의어가 부실했다',
    { x: 0.62, y: 2.34, w: 8.8, h: 0.48, fontSize: 10.3, lineSpacingMultiple: 1.25 });
  txt(s, '오판 방지 장치 3종', { x: 0.4, y: 3.0, w: 9.2, h: 0.3, fontSize: 13, bold: true, color: C.TEXT_DARK });
  const guards = [
    ['방향성 역전 감지', '"정부가 AI를 쓴다"와\n"기업이 AI를 배운다"는 반대 정책 —\n축이 겹쳐도 별도 규칙으로 판별'],
    ['이름만 겹침 배제', '제목이 같아도 대상·수단이 다르면\n오히려 독창성의 근거 —\n설계 대조를 의무화'],
    ['재현율 통제', '반드시 걸려야 할 문헌을\n회수하지 못하면 결론을 내지 않고\n판정 보류로 처리'],
  ];
  const w = 2.93, gx = 0.2;
  guards.forEach((g, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 3.4, w, 1.35);
    txt(s, String(i + 1), { x: x + 0.16, y: 3.5, w: 0.4, h: 0.3, fontSize: 15, bold: true, color: C.PRIMARY });
    txt(s, g[0], { x: x + 0.55, y: 3.52, w: w - 0.7, h: 0.28, fontSize: 11.5, bold: true });
    txt(s, g[1], { x: x + 0.16, y: 3.88, w: w - 0.32, h: 0.8, fontSize: 9, color: C.TEXT_SUB,
      lineSpacingMultiple: 1.22 });
  });
  bottomBar(s, '결론은 "선례 없음"이 아니라 "N개 질의에서 미발견" — 확신도는 최대 \'중\'으로 제한', 4.92);
}

// ═══════════ 24. 판정의 검증 (신설) ═══════════
{
  const s = contentSlide(5);
  tagline(s, '05. 왜 믿을 수 있나');
  sectionTitle(s, '판정의 검증 — 확인된 것과 확인되지 않은 것');
  // 확인된 것
  card(s, 0.4, 1.92, 4.5, 2.4, { fill: 'F0F9F3', border: C.GREEN, lw: 1.2 });
  txt(s, '확인된 것', { x: 0.58, y: 2.04, w: 4.1, h: 0.3, fontSize: 13.5, bold: true, color: C.GREEN });
  txt(s, '판별력 시험 (n = 10)', { x: 0.58, y: 2.38, w: 4.1, h: 0.26, fontSize: 10.5,
    bold: true, color: C.TEXT_DARK });
  const rows = [['진부 아이디어 5건', '평균 4.23'], ['창의 아이디어 5건', '평균 8.50'],
    ['두 그룹 분포 겹침', '없음']];
  rows.forEach((r, i) => {
    const y = 2.68 + i * 0.3;
    txt(s, r[0], { x: 0.62, y, w: 2.5, h: 0.28, fontSize: 10, color: '333333' });
    txt(s, r[1], { x: 3.2, y, w: 1.5, h: 0.28, fontSize: 10, bold: true, color: C.GREEN, align: 'right' });
  });
  txt(s, '두 채점 간 불일치 (30건 기준)', { x: 0.58, y: 3.62, w: 4.1, h: 0.26, fontSize: 10.5,
    bold: true, color: C.TEXT_DARK });
  txt(s, '평균 절대차 2.03점 · 3점 이상 괴리 7건', { x: 0.62, y: 3.9, w: 4.1, h: 0.26,
    fontSize: 10, color: '333333' });
  // 확인되지 않은 것
  card(s, 5.1, 1.92, 4.5, 2.4, { fill: 'FDF2F2', border: 'F0C0C0', lw: 1.2 });
  txt(s, '확인되지 않은 것', { x: 5.28, y: 2.04, w: 4.1, h: 0.3, fontSize: 13.5, bold: true, color: C.RED });
  bullets(s, [
    '전문가(연구자) 판정과의 일치도',
    '동일 대화 재채점 시 재현성',
    '경계 사례에서의 판별력',
    '표현력 편향의 크기',
    '실제 중복 제안 탐지율',
  ], 5.3, 2.42, 4.15, 10.3, 0.36, C.TEXT_DARK);
  card(s, 0.4, 4.45, 9.2, 0.95, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '현재 판정력이 입증된 범위', { x: 0.62, y: 4.55, w: 3, h: 0.28, fontSize: 11.5,
    bold: true, color: C.PRIMARY });
  txt(s, '표본 10건 · 극단 사례(명백히 진부 vs 명백히 창의)에 한정됩니다. 시험 문항은 사람이 아니라 모델이 생성했습니다.\n' +
        '실제 국민 제안은 중간대에 몰리므로, 경계 사례 판별력과 전문가 일치도는 도입 전 별도 검증이 필요합니다.',
    { x: 0.62, y: 4.85, w: 8.8, h: 0.5, fontSize: 10.3, lineSpacingMultiple: 1.25 });
}

// ═══════════ 25. 어떻게 만들었나 ═══════════
{
  const s = contentSlide(5);
  tagline(s, '06. 구축과 운영');
  sectionTitle(s, '어떻게 만들었나');
  const parts = [
    ['화면', '문답·결과 웹 화면\n음성 입력 · 문답 저장\nWord/PDF 불러와 재평가'],
    ['평가 엔진', '문답 생성 · 이원 채점\n명세 추출 · 선례 판정\n판정 규칙은 문서로 분리'],
    ['데이터', 'KDI 발간물 7,362건\nOPSI 1,015건 (로컬)\n재정 · 국회 의안 (조회)'],
    ['배포', '연구용 · 공개용 2종\n초대 코드 접근 통제\n키는 서버에 미보관'],
  ];
  const w = 2.2, gx = 0.19;
  parts.forEach((p, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 1.55);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w, h: 0.36, fill: { color: C.PRIMARY } });
    txt(s, p[0], { x, y: 1.95, w, h: 0.36, fontSize: 11.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    txt(s, p[1], { x: x + 0.12, y: 2.44, w: w - 0.24, h: 0.95, fontSize: 9.8, color: C.TEXT_SUB,
      align: 'center', lineSpacingMultiple: 1.3 });
  });
  card(s, 0.4, 3.65, 9.2, 1.72, { fill: C.CARD_ALT_BG, shadow: false });
  txt(s, '데이터 확보에서 지킨 원칙', { x: 0.62, y: 3.76, w: 4, h: 0.28, fontSize: 12.5, bold: true, color: C.PRIMARY });
  const rules = [
    ['불안정한 소스는 끈다', '외부 연구정보 API가 응답을 보장하지 못해 중단하고, 로컬 코퍼스로 대체'],
    ['우회하지 않는다', '해외 사이트의 자동 수집 차단을 기술적으로 우회하지 않고, 공개 자료를 정리해 구축'],
    ['외국 상용 서비스에 의존하지 않는다', '유료 해외 정책DB 대신 OECD 공개 사례로 코퍼스를 자체 확보'],
  ];
  let y = 4.13;
  rules.forEach((r) => {
    txt(s, '•', { x: 0.66, y, w: 0.15, h: 0.34, fontSize: 11, color: C.PRIMARY });
    txt(s, r[0], { x: 0.84, y, w: 2.9, h: 0.34, fontSize: 10.8, bold: true });
    txt(s, r[1], { x: 3.8, y, w: 5.65, h: 0.34, fontSize: 10.5, color: C.TEXT_SUB });
    y += 0.4;
  });
}

// ═══════════ 25. 운영 비용 ═══════════
{
  const s = contentSlide(5);
  tagline(s, '06. 구축과 운영');
  sectionTitle(s, '운영 비용 — 월 처리량별 추정');
  txt(s, '아이디어 1건당 약 2.8만~4.3만 토큰 · 캐싱 적용 시 추정(현재 미구현) · 환율 1,500원 기준',
    { x: 0.4, y: 1.88, w: 9.2, h: 0.3, fontSize: 11, color: C.TEXT_SUB });
  const head = ['월 처리량', '표준 모델 · 단문', '표준 모델 · 장문', '고급 모델 · 단문', '고급 모델 · 장문'];
  const data = [
    ['500건', '약 14만 원', '약 18만 원', '약 24만 원', '약 30만 원'],
    ['1,000건', '약 29만 원', '약 36만 원', '약 48만 원', '약 60만 원'],
    ['2,000건', '약 57만 원', '약 72만 원', '약 96만 원', '약 120만 원'],
    ['10,000건', '약 285만 원', '약 360만 원', '약 480만 원', '약 600만 원'],
  ];
  const colW = [1.7, 1.875, 1.875, 1.875, 1.875];
  let x = 0.4;
  head.forEach((h, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.3, w: colW[i], h: 0.44, fill: { color: C.PRIMARY },
      line: { color: C.WHITE, width: 0.5 } });
    txt(s, h, { x, y: 2.3, w: colW[i], h: 0.44, fontSize: 10.5, bold: true, color: C.WHITE,
      align: 'center', valign: 'middle' });
    x += colW[i];
  });
  let y = 2.74;
  data.forEach((row, ri) => {
    x = 0.4;
    row.forEach((cell, ci) => {
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: colW[ci], h: 0.46,
        fill: { color: ri % 2 ? C.CARD_ALT_BG : C.WHITE }, line: { color: C.CARD_BORDER, width: 0.5 } });
      txt(s, cell, { x, y, w: colW[ci], h: 0.46, fontSize: 11,
        bold: ci === 0, color: ci === 0 ? C.PRIMARY : C.TEXT_DARK, align: 'center', valign: 'middle' });
      x += colW[ci];
    });
    y += 0.46;
  });
  card(s, 0.4, 4.72, 9.2, 0.68, { fill: C.LIGHT_BLUE, shadow: false });
  txt(s, '월 1,000건을 표준 모델로 처리할 경우 약 29만~36만 원 (API 비용만)',
    { x: 0.5, y: 4.78, w: 9, h: 0.3, fontSize: 11.5, bold: true, color: C.PRIMARY, align: 'center' });
  txt(s, '※ 캐싱 미적용 시 입력 토큰이 전액 과금되어 실제 비용은 이보다 큼 · 인건비·서버·코퍼스 갱신 비용 제외',
    { x: 0.5, y: 5.08, w: 9, h: 0.26, fontSize: 9.5, color: C.TEXT_SUB, align: 'center' });
}

// ═══════════ 26. 한계와 다음 단계 ═══════════
{
  const s = contentSlide(5);
  tagline(s, '06. 구축과 운영');
  sectionTitle(s, '한계와 다음 단계');
  const two = [
    ['현재의 한계', C.AMBER, 'FFF8E8',
      ['표현력 편향 — 조리 있게 말하는 제안자가 유리', '법적·규제 타당성은 채점에 미포함',
       '지자체 자체사업·기금사업 포착이 불균등', '재정 자료는 최근 5개 시점(결측 있음)',
       '해외 코퍼스는 OECD 등재·자기신고 사례', '판정은 최종 결론이 아니라 검토 후보 목록']],
    ['다음 단계', C.PRIMARY, 'EFF4FB',
      ['전문가 판정과의 일치도 측정', '동일 대화 재채점 재현성 검증',
       '표현력 편향 보정 설계 · 법적 타당성 항목 추가', '지자체·기금 데이터 통로 추가',
       '부처 배정·이관 절차와 연계', '판정 이력을 국가 아이디어 코퍼스로 축적']],
  ];
  const w = 4.5, gx = 0.2;
  two.forEach((t, i) => {
    const x = 0.4 + i * (w + gx);
    card(s, x, 1.95, w, 2.75, { fill: t[2], border: t[1], lw: 1.2 });
    txt(s, t[0], { x: x + 0.18, y: 2.1, w: w - 0.36, h: 0.34, fontSize: 14, bold: true, color: t[1] });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 0.18, y: 2.5, w: w - 0.36, h: 0.012, fill: { color: t[1] } });
    bullets(s, t[3], x + 0.18, 2.62, w - 0.36, 10, 0.33);
  });
  bottomBar(s, '이 시스템은 담당자를 대체하지 않습니다 — 판단의 근거를 갖춘 상태로 만들어 줍니다', 4.9);
}

// ═══════════ 27. 마무리 ═══════════
{
  const s = pres.addSlide();
  pageNo += 1;
  s.background = { color: C.DARK_BG };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 5.625, fill: { color: C.PRIMARY } });
  txt(s, '온 국민 아이디어 등록제', { x: 0.6, y: 1.35, w: 8, h: 0.4, fontSize: 17, color: C.PRIMARY, bold: true });
  txt(s, '국민의 제안에', { x: 0.6, y: 1.95, w: 9, h: 0.7, fontSize: 36, bold: true, color: C.WHITE });
  txt(s, '근거 있는 답을 돌려줍니다', { x: 0.6, y: 2.6, w: 9, h: 0.7, fontSize: 36, bold: true, color: C.WHITE });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.62, y: 3.55, w: 2.6, h: 0.02, fill: { color: C.PRIMARY } });
  txt(s, '대화로 캐묻고, 국가 데이터로 확인하고, 확신도와 함께 말합니다',
    { x: 0.6, y: 3.75, w: 8.6, h: 0.35, fontSize: 14, color: 'C7D2E5' });
  txt(s, `${pageNo} / ${TOTAL}`, { x: 8.4, y: 4.95, w: 1.1, h: 0.3, fontSize: 10,
    color: '8A93A8', align: 'right' });
}

pres.writeFile({ fileName: process.argv[2] || 'idea_registry.pptx' })
  .then(f => console.log('생성 완료:', f));

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType,
} = require("docx");

const NAVY = "1F3864", RED = "A62B2B", GREEN = "2E6B3E", AMBER = "9A6A00",
      GREY = "5A5A5A", LINE = "C9C9C9", BG = "F2F4F7", BGR = "FBF0F0";
const F = "맑은 고딕";

const t = (text, o = {}) => new TextRun({ text, font: F, size: o.size || 20,
  bold: o.b, italics: o.i, color: o.c, break: o.br });
const p = (runs, o = {}) => new Paragraph({
  children: Array.isArray(runs) ? runs : [runs],
  spacing: { before: o.before ?? 60, after: o.after ?? 60, line: 278 },
  indent: o.indent, border: o.border,
});
const h1 = (text) => new Paragraph({
  children: [t(text, { size: 30, b: true, c: NAVY })],
  spacing: { before: 380, after: 140 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY, space: 6 } },
});
const h2 = (text, color) => new Paragraph({
  children: [t(text, { size: 23, b: true, c: color || NAVY })],
  spacing: { before: 260, after: 90 },
});
const body = (text, o = {}) => p(t(text, o));
const bullet = (text, o = {}) => new Paragraph({
  children: [t("· ", { c: GREY }), t(text, o)],
  spacing: { before: 40, after: 40, line: 272 },
  indent: { left: 240, hanging: 150 },
});
const quote = (text) => new Paragraph({
  children: [t(text, { i: true, c: GREY, size: 19 })],
  spacing: { before: 90, after: 110, line: 262 },
  indent: { left: 340 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: LINE, space: 10 } },
});
const fix = (text) => new Paragraph({
  children: [t("개선책  ", { b: true, c: GREEN, size: 19 }), t(text, { size: 19 })],
  spacing: { before: 110, after: 140, line: 272 },
  indent: { left: 240 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: GREEN, space: 10 } },
});
const cell = (content, o = {}) => new TableCell({
  width: { size: o.w || 0, type: WidthType.PERCENTAGE },
  shading: o.bg ? { type: ShadingType.CLEAR, fill: o.bg } : undefined,
  margins: { top: 70, bottom: 70, left: 110, right: 110 },
  children: (Array.isArray(content) ? content : [content]).map((c) =>
    new Paragraph({ children: [t(c, { size: 18, b: o.b, c: o.c })],
      spacing: { before: 0, after: 0, line: 252 } })),
});
const table = (header, rows, widths) => new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 6, color: LINE },
    bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE },
    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: LINE },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [
    new TableRow({ tableHeader: true,
      children: header.map((hh, i) => cell(hh, { b: true, c: NAVY, bg: BG, w: widths[i] })) }),
    ...rows.map((r) => new TableRow({
      children: r.map((c, i) => (c && typeof c === "object")
        ? cell(c.v, { w: widths[i], b: c.b, c: c.c, bg: c.bg })
        : cell(c, { w: widths[i] })),
    })),
  ],
});
const sp = () => new Paragraph({ children: [], spacing: { before: 0, after: 110 } });

const k = [];

// ── 표지
k.push(new Paragraph({ children: [t("KCI 중간보고서 동료심사", { size: 40, b: true, c: NAVY })], spacing: { after: 60 } }));
k.push(new Paragraph({ children: [t("L1·L2·L3 대비 구조 분석 · 장점 2 · 단점 8 · 개선책", { size: 23, c: GREY })], spacing: { after: 150 } }));
k.push(new Paragraph({
  children: [
    t("심사 대상: 「K-Culture Index(KCI) 개발 및 실증 연구」 중간보고서 요약본 (재정학회, 2026.9, 20쪽)", { size: 17, c: GREY }),
    t("대조 체계: KWCI 3레이어 모형 — 해설서(2026-06-28) 및 jason-j-kim/kwci-dashboard 저장소(55abda7, 산출 2026-09-02)", { size: 17, c: GREY, br: true }),
    t("심사 유의: 본 심사는 20쪽 요약본에 근거한다. 본보고서에서 이미 다뤄진 항목이 있다면 해당 지적은 철회한다.", { size: 17, c: RED, br: true }),
  ],
  spacing: { after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE, space: 8 } },
}));

// ── 0. 심사 요지
k.push(h1("0. 심사 요지"));
k.push(p([t("KCI는 지수 설계에서 "), t("기술(description)에서 추론(inference)으로 넘어가려는 올바른 시도", { b: true, c: NAVY }),
  t("다. 그 방향은 옳다. 그러나 그 전환을 뒷받침해야 할 추정 구조에 "),
  t("결과를 무효화할 수 있는 결함이 최소 두 건", { b: true, c: RED }),
  t(" 있다. 첫째는 비음수 제약 하에서 부호 일관성을 발견으로 보고한 점이고, 둘째는 가중을 준거에 적합시킨 뒤 같은 준거로 검정한 점이다.")]));
k.push(p([t("현 상태로는 "), t("β 판정 결과를 인용 가능한 실증 결과로 볼 수 없다.", { b: true, c: RED }),
  t(" 다만 이는 파일럿 단계의 통상적 미비이며, 아래 개선책은 대부분 추가 수집 없이 재분석만으로 처리된다.")]));

// ── 1. 구조 대조
k.push(h1("1. L1·L2·L3와 C·A·B는 무엇이 다른가"));
k.push(h2("1.1  분류의 축이 다르다"));
k.push(p([t("KWCI의 L1·L2·L3는 "), t("자료의 출처", { b: true }), t("로 나눈 층위다 — 경제통계인가, 플랫폼 지표인가, 수용자 신호인가. KCI의 C·A·B는 "),
  t("소비자 의사결정의 깊이", { b: true }), t("로 나눈 단계다 — 알고 있는가(인지), 호의적인가(태도), 하려는가(행동의도).")]));
k.push(sp());
k.push(table(["", "KWCI — L1·L2·L3", "KCI — C·A·B"],
  [
    ["분류 축", "자료의 출처 (무엇으로 재는가)", { v: "심리 단계 (무엇을 재는가)", b: true }],
    ["층의 관계", "병렬 — 서로 다른 것을 잰다", "위계 — 같은 것의 깊이 차등"],
    ["수출의 위치", { v: "L1, 지수 내부 (가중 0.5)", c: RED }, { v: "지수 외부 준거 (우변)", c: GREEN }],
    ["가중 결정", "외생 — 연구자 지정, 프로파일 토글", { v: "내생 — NNLS 추정", b: true }],
    ["합성의 의미", { v: "불분명", c: RED }, "잠재변수 '관심'의 세 측면"],
    ["가능한 질문", "“어디가 센가” (기술)", { v: "“관심이 수출을 선행하는가” (추론)", b: true }],
  ], [16, 42, 42]));

k.push(h2("1.2  왜 이 차이가 결정적인가 — 가중합의 해석 가능성"));
k.push(p([t("KWCI의 지수값은 "), t("0.5×수출 + 0.3×팬클럽수 + 0.2×검색량", { b: true }),
  t("이다. 단위도 개념도 다른 세 양의 가중합이 무엇을 뜻하는지 말할 수 없다. 가중치를 바꾸면 국가 순위가 바뀌는데, 어느 가중이 옳은지 판별할 외부 기준도 없다. 해설서가 이를 “가치판단과 직결”이라 표현한 것은 정확하나, 바꿔 말하면 "),
  t("측정이 아니라 선언", { b: true, c: RED }), t("이다.")]));
k.push(p([t("C·A·B는 셋 모두 “한류에 대한 관심”이라는 "), t("하나의 잠재변수", { b: true }),
  t("의 측면이다. 따라서 합성이 해석을 갖고, 가중을 데이터로 추정하는 것도 정당화된다. "),
  t("KCI의 가장 큰 이론적 진전은 β가 아니라 이 재편에 있다.", { b: true, c: NAVY })]));

k.push(h2("1.3  실측으로 확인한 L2의 실태 — 폐기가 옳았던 근거"));
k.push(body("본 심사자가 KWCI 저장소의 산출 데이터(2026-09-02)를 직접 검증한 결과는 다음과 같다."));
k.push(sp());
k.push(table(["검증 항목", "결과"],
  [
    ["L2 자료원", "KF 한류현황 kf_count 단일 (K-pop만 Apple Music Top50 점유율)"],
    ["도메인 구분력", { v: "없음 — 국가 단위로 min-max 후 전 장르에 동일 값 병합", c: RED }],
    ["설계상 가중", "0.30"],
    ["실효 가중", { v: "0.426 — 콘텐츠 4도메인의 L1 결측으로 재정규화되며 증폭", b: true, c: RED }],
    ["그중 단일값분", { v: "0.352 — 횡단지수의 35%가 국가당 숫자 하나", b: true, c: RED }],
    ["국가 KWCI와의 상관", { v: "r = 0.930 (n=15)", b: true, c: RED }],
  ], [30, 70]));
k.push(sp());
k.push(p([t("8도메인 × 3레이어 가중합의 결과가 "), t("팬클럽 수 하나와 상관 0.93", { b: true, c: RED }),
  t("이다. L2는 층이 아니라 국가 상수였다. KCI가 이 체계를 버린 것은 옳다. "),
  t("다만 그 근거가 KCI 보고서 어디에도 적혀 있지 않다", { b: true }), t(" — 후술 단점 8 참조.")]));

// ── 2. 장점
k.push(h1("2. 장점 (2)"));

k.push(h2("장점 1.  좌우변 분리 — 검정 가능한 명제를 만들었다", GREEN));
k.push(body("KWCI는 수출을 지수에 넣고 그 지수로 한류의 경제효과를 설명했다. 이는 동어반복이며, 어떤 데이터로도 반증되지 않는다. KCI는 수출을 지수 밖으로 옮겨 “관심이 수출을 선행하는가”라는 반증 가능한 명제를 세웠다."));
k.push(quote("MVP: E 단일 지수로 개념 실증(‘관심→수출 연관의 존재’로 순환 참조 문제점 확인) / Pilot 1차: C(소비·상거래) 요소는 지수 내부에서 분리해 ‘수출액’이라는 외부 준거로 전환"));
k.push(p([t("연구팀이 "), t("스스로 순환을 발견하고 설계를 바꿨다는 기록", { b: true }),
  t("이 남아 있다는 점은 방법론적 성숙의 증거다. 지수 연구에서 이 전환을 실제로 수행한 사례는 드물다.")]));

k.push(h2("장점 2.  층위를 심리 단계로 재편하고 가중을 내생화했다", GREEN));
k.push(body("§1.2에서 논한 대로, 자료 출처별 층위의 가중합은 해석이 불가능하다. C·A·B는 단일 잠재변수의 세 측면이므로 합성이 의미를 갖는다. 여기에 가중을 미 연준 FCI-G식 성과준거 가중으로 추정해, 발표 원칙이던 “고정 사전은 출발점, 최종 목적은 내생적 결정”을 실현했다."));
k.push(body("추정 설계 7요소(국가 고정효과 · 전년동기차 변환 · 시차 탐색 · NNLS · 등가중 축소 · 산업 풀링 · 이중 트랙)도 표준적이고 견고하다. 특히 국가 고정효과와 전년동기차의 병용은 수준 상관과 계절 허구 상관을 동시에 차단하는 정석이며, KWCI에는 이에 해당하는 장치가 전무하다."));

// ── 3. 단점
k.push(h1("3. 단점 (8) 과 개선책"));

k.push(h2("단점 1.  비음수 제약 하에서 “β 전부 양수”는 발견이 아니다", RED));
k.push(p([t("보고서의 대표 결론은 "), t("“8산업 β 전부 양수(방향 일관)”", { b: true }), t("다. 그런데 추정량은 "),
  t("NNLS(비음수 최소제곱)", { b: true, c: RED }), t("이다.")]));
k.push(quote("차원 가중 w와 총효과 β를 비음수 최소제곱으로 추정 / 추정 설계 7요소 — … 비음수 최소제곱(NNLS) …"));
k.push(p([t("NNLS는 계수를 음수로 산출할 수 없다. "),
  t("즉 β ≥ 0 은 추정량의 제약이지 데이터의 발견이 아니다.", { b: true, c: RED }),
  t(" 부호를 음수로 낼 수 없는 추정량으로 “부호 일관성”을 보고하는 것은 항진명제이며, Executive Summary의 첫 번째 결론이 여기에 걸린다.")]));
k.push(body("이 지적은 β를 별도로 OLS 추정했다면 해소된다. 그러나 요약본 문면으로는 w와 β가 같은 NNLS 적합에서 나온다. 어느 쪽인지가 결론의 지위를 좌우하므로 반드시 명시되어야 한다."));
k.push(fix("① β는 제약 없는 추정량(OLS/FE)으로 별도 산출하고 NNLS는 w 추정에만 한정한다. ② 그 결과 음수가 나오는 산업을 그대로 보고한다. ③ 두 추정치를 병기해 제약의 영향을 공시한다. ④ “방향 일관”이라는 표현은 제약 없는 추정에서 확인되기 전까지 사용하지 않는다."));

k.push(h2("단점 2.  적합 순환 — 준거에 맞춘 가중으로 그 준거를 설명한다", RED));
k.push(quote("가중의 근거는 ‘수출을 가장 잘 설명하는 비율’로 CAB가중치 설정"));
k.push(p([t("C·A·B 결합 가중 w를 수출에 적합시킨 뒤, 그 합성지수로 다시 수출을 설명하는 β와 r²를 보고한다. KWCI식 순환(수출을 지수에 포함)은 끊었으나 "),
  t("적합 순환(fitting circularity)", { b: true, c: RED }), t("이 새로 생겼다. r²는 정의상 부풀 방향으로 편향된다.")]));
k.push(p([t("이 모순은 보고서 자신의 "), t("두 정의가 불일치한다는 사실", { b: true }), t("로 드러난다.")]));
k.push(sp());
k.push(table(["출처", "정의", "함의"],
  [
    ["제2장", "국가×산업 단위 주간 관심 및 태도 종합지수", "독립적 측정"],
    ["Executive Summary", { v: "수출액의 변동 중 소비자 심리 성분을 재구성한 지표", b: true }, { v: "수출의 분해 — 독립적이지 않음", c: RED }],
  ], [22, 48, 30]));
k.push(sp());
k.push(p([t("실제 구현은 "), t("요약본의 정의", { b: true }), t("에 해당한다. 그렇다면 KCI는 “관심”이 아니라 “수출을 가장 잘 설명하도록 재조합된 검색·댓글 신호”이며, 그 지수의 β는 예측력의 증거가 아니라 적합도의 재확인이다.")]));
k.push(fix("① w 추정 표본과 β 검정 표본을 분리한다 — 시간 분할(2021–2024 적합 / 2025–2026 검정) 또는 국가 홀드아웃(leave-one-country-out). ② 등가중(w=1/3 고정) 판본의 β를 병기해 가중 최적화의 기여분을 분리한다. ③ 두 정의 중 하나를 채택하고 보고서 전체에서 통일한다."));

k.push(h2("단점 3.  위약검정이 없다", RED));
k.push(p([t("보고서의 PRD 대조 트랙은 “문화 관심(CUL) 대 구매 신호(PRD)”의 대조이지 "),
  t("위약이 아니다", { b: true }), t(". 위약검정은 ")
  , t("한류와 무관한 대상에 동일 파이프라인을 적용해 계수가 0으로 나오는지", { b: true }),
  t(" 확인하는 절차다. 이것이 없으면 “8산업 전부 양수”가 신호인지 공통 추세의 잔재인지 판별할 수 없다.")]));
k.push(body("r²가 .01~.08인 구간에서는 이 판별이 특히 중요하다. 그 정도 설명력은 서로 무관한 시계열 쌍에서도 흔히 관측된다."));
k.push(fix("추가 수집 없이 즉시 가능한 것부터 셋. ① 시점 셔플 위약(placebo-in-time) — 좌변 시계열을 국가 내에서 무작위 순환시켜 β 분포를 만들고 실제 β의 분위를 본다. ② 무관 품목 위약 — 반도체·석유·선박 월간 수출을 우변에 놓고 동일 모형 실행. ③ 교차 배정 위약 — A국 CAB로 B국 수출을 설명. 셋 모두에서 유의한 β가 나오면 통제가 불충분한 것이므로 본 결과를 채택하지 않는다."));

k.push(h2("단점 4.  우변 합성에 좌변과 같은 플랫폼 원천이 혼입되어 있다", RED));
k.push(body("보고서는 순환 금지를 명문화했다 — “준거에 사용된 데이터는 검증에 재사용 불가”. 그러나 준거 자체의 구성에서 이 원칙이 지켜지지 않는다."));
k.push(sp());
k.push(table(["산업", "우변(준거) 구성", "좌변(CAB) 원천", "충돌"],
  [
    ["게임·웹툰", { v: "콘진원 총액 × Google Play 앱 순위 변조", c: RED }, "Google Trends 검색 + YouTube 댓글", { v: "동일 생태계", b: true, c: RED }],
    ["영상", { v: "ECOS 총액 × Netflix Top10 소비 변조", c: RED }, "동상", { v: "검증 원천과도 중복", c: RED }],
  ], [12, 36, 30, 22]));
k.push(sp());
k.push(p([t("앱 순위는 다운로드·매출로 생성되고, 다운로드는 검색을 경유한다. "),
  t("즉 우변이 좌변의 함수를 포함한다.", { b: true, c: RED }),
  t(" 이 상태에서 게임 β=0.0006·웹툰 β=0.0017이 무엇을 재는지 확정할 수 없다. 영상은 더 나쁘다 — 준거가 Netflix Top10 변조인데 제5장의 "),
  t("검증 원천도 Netflix Top10", { b: true }), t("이다. 좌변·우변·검증이 한 원천으로 수렴한다.")]));
k.push(fix("① 합성 준거에서 플랫폼 유래 성분을 제거하고 계절형·연간 앵커만으로 재구성한 판본을 병기한다. ② 그것이 불가하면 해당 4개 산업의 β를 본문 표에서 제외하고 “준거 미확보, 판정 보류”로 표기한다. 현재처럼 실측 산업과 같은 표에 나란히 싣는 것은 등급 표기만으로 구분되지 않는다. ③ 영상의 검증 원천을 Netflix 계열이 아닌 것(예: 방송 수출 통관 실측)으로 교체한다."));

k.push(h2("단점 5.  C와 B가 같은 원천이어서 3차원 설계가 실질적으로 붕괴한다", RED));
k.push(p([t("원천은 둘(Google Trends, YouTube 댓글)인데 차원은 셋이다. "),
  t("C(인지)와 B(행동의도)는 모두 Google Trends 검색이며 쿼리 목록만 다르다.", { b: true }),
  t(" 같은 플랫폼·같은 상대 정규화·같은 기간이므로 두 계열은 높은 상관을 가질 수밖에 없다.")]));
k.push(p([t("비음수 제약과 다중공선성이 겹치면 NNLS 해는 "), t("코너 해(한쪽 가중 0)", { b: true, c: RED }),
  t("로 몰린다. 보고서가 한계에 적은 문장이 바로 그 증상이다.")]));
k.push(quote("검색(상대지수) vs 반응(발생률)의 가중치는 0 또는 1로 선택의 문제"));
k.push(body("이것은 한계가 아니라 진단이다. 3차원 설계가 데이터상 1~2차원으로 수축한다면, C·A·B라는 이론적 구조가 실제 산출에 반영되지 않는다는 뜻이다."));
k.push(fix("① C와 B의 상관계수, VIF 또는 설계행렬 조건수를 공시한다. ② 차원별 단독 회귀 β와 결합 회귀 β를 병기해 각 차원의 증분 설명력을 제시한다. ③ 증분이 없으면 2차원(검색·반응)으로 축소하고 이론 서술을 그에 맞춘다. ④ 척도 이질성은 결합 전 순위변환 또는 국가 내 표준화로 완화한다."));

k.push(h2("단점 6.  시차 k 탐색의 선택 편의가 보정되지 않았고 “시차차”가 미정의다", AMBER));
k.push(p([t("추정 설계에 “시차 k 탐색”이 포함되어 있다. 8개 산업에서 각각 최적 k를 고르면 그 k에서의 β·r²는 "),
  t("선택 편의", { b: true, c: RED }), t("를 갖는다. 보고된 k가 3~12주로 넓게 흩어져 있다는 사실 자체가 탐색의 흔적이며, 다중비교 보정은 언급되지 않는다.")]));
k.push(p([t("별개로 “시차차” 열의 정의가 확정되지 않는다. 용어 설명은 “관심의 구매 선행 주수”인데, β 열의 k와 값이 다르다(관광 k=6, 시차차 +3). 두 지표의 관계를 설명하는 산식이 없다. 그 결과 "),
  t("음수 4건(패션 −9 · 음악 −5 · 뷰티 −1 · 식품 −1)", { b: true, c: RED }),
  t("의 해석이 불가능하다. 문면대로 읽으면 관심이 구매를 후행한다는 뜻이며, 선행지표를 표방하는 지수에서 이는 해석 없이 지나갈 값이 아니다.")]));
k.push(fix("① k 후보 집합을 사전 등록하고, 탐색은 훈련 구간에서만 수행한 뒤 홀드아웃에서 재추정한다. ② 다중비교 보정(Bonferroni 또는 FDR) 후 유의성을 재판정한다. ③ 시차차의 산식을 표 각주에 명시한다. ④ 음수 산업은 “선행 근거 없음”으로 별도 분류하고 3부류 유형화에서 분리한다."));

k.push(h2("단점 7.  저신호 절단이 생존 편의를 만든다", AMBER));
k.push(p([t("40셀 중 5셀을 공시(censored) 처리한 것은 정직한 조치다. 그러나 "),
  t("탈락 기준이 좌변에 있고(비영 토픽 ≥3, 전 기간 커버 ≥1) 그 탈락이 β 추정 표본을 바꾼다.", { b: true, c: RED }),
  t(" 신호가 약한 셀이 빠지면 남은 표본은 신호–수출 관계가 강한 쪽으로 치우친다. 전형적인 생존 편의다.")]));
k.push(body("사우디는 바구니의 39%가 저신호 공시 셀이라고 보고서가 밝혔다. 국가 KCI가 8산업 셀의 수출 구성비 가중합인데 39%가 빠진 상태의 국가 지수를 다른 국가와 같은 축에 놓는 것은 성립하지 않는다."));
k.push(fix("① 절단 셀을 제외가 아니라 결측으로 두고 Tobit 또는 Heckman 계열로 보정한 판본을 병기한다. ② 최소한 절단 포함·제외 두 판본의 β를 나란히 보고한다. ③ 국가 KCI는 공시 셀 비중을 함께 표기하고, 일정 비율(예: 30%) 초과 시 국가 지수 자체를 공시로 처리한다."));

k.push(h2("단점 8.  유일하게 통과한 산업이 가장 검증 불가능한 산업이다", RED));
k.push(p([t("OOS 조건까지 충족한 산업은 관광 하나다(r²=.21). 그런데 관광의 B차원은 항공권·비자·숙박 검색이고 우변은 입국자 수다. "),
  t("둘은 같은 의사결정의 앞뒤이지 독립 사건이 아니다.", { b: true, c: RED }),
  t(" “항공권을 검색한 사람이 몇 주 뒤 입국한다”는 발견이라기보다 정의에 가깝다.")]));
k.push(p([t("제5장은 이를 인지하고 다음과 같이 처리했다.")]));
k.push(quote("조건부: 관광 = 입국자가 이미 우변 — 별도 수렴 검증 없이 β 자체를 타당성 증거로 정직 명시"));
k.push(p([t("명시한 태도는 정직하나, 논리적으로는 "), t("검증 불가능을 검증 통과로 치환", { b: true, c: RED }),
  t("한 것이다. 8개 중 유일하게 “신뢰” 등급을 받은 산업이 독립 검증 원천이 없는 산업이라는 사실은, 모형 전체의 타당성 근거가 사실상 비어 있음을 뜻한다.")]));
k.push(body("여기에 표본 구조가 겹친다. 국가 고정효과 패널을 표방하나 국가는 5개이며, 글로벌 KCI의 국가 가중은 일본 50% · 미국 33%로 두 나라가 83%다. 횡단 식별이 사실상 두 나라에서 나온다."));
k.push(fix("① 관광 B차원에서 예약 행위어(항공권·숙박·비자)를 제외한 C·A 전용 판본으로 β를 재추정한다. 값이 유지되면 진정한 선행성이고, 무너지면 동어반복이다. 이 한 번의 재분석이 모형 타당성의 핵심 증거가 된다. ② 15국 확장 전까지 “글로벌 KCI” 명칭을 보류하고 “5개국 KCI”로 표기한다. ③ 국가별 β를 개별 보고하고 풀링 결과와 대조해 풀링 가정(국가 간 동질성)의 성립 여부를 제시한다."));

// ── 4. 그 밖에
k.push(h1("4. 그 밖의 지적 (경미)"));
k.push(table(["항목", "내용"],
  [
    ["요약–본문 불일치", "Executive Summary가 영상·웹툰의 “PRD 부호 역전”을 누락하고, 8개 산업 중 가장 약한 식품(β 0.00006, r² .01)을 목록에서 빠뜨렸다"],
    ["KWCI와의 관계 부재", "보고서에 KWCI 언급이 전무하다. 두 지수가 병존하면 인용자가 혼란하며, L2 폐기의 근거(§1.3)가 문서화되지 않아 기존 사용자를 설득하지 못한다"],
    ["다변화 차원의 상실", "β는 “관심이 수출로 전환되는가”만 답한다. KWCI의 ENM(유효시장수)이 답하던 복원력 차원이 사라졌다"],
    ["표기 정합성", "표지 「20206.9」, 본문 “5개국 개상”·“k기 선행” 등 오탈자. 같은 범주를 “무관형”(요약)과 “무작위형”(제4·6장)으로 혼용"],
  ], [22, 78]));

// ── 5. 우선순위
k.push(h1("5. 개선 우선순위"));
k.push(table(["순위", "조치", "필요 자원", "효과"],
  [
    [{ v: "1", b: true, c: RED }, { v: "β를 제약 없는 추정량으로 재산출", b: true }, { v: "재분석만", c: GREEN }, "대표 결론의 지위를 결정한다"],
    [{ v: "2", b: true, c: RED }, { v: "위약검정 3종 실행", b: true }, { v: "재분석 + 무관 품목 수출", c: GREEN }, "결과 채택 여부의 근거"],
    [{ v: "3", b: true, c: RED }, { v: "w 적합 표본과 β 검정 표본 분리", b: true }, { v: "재분석만", c: GREEN }, "적합 순환 제거"],
    [{ v: "4", b: true, c: AMBER }, { v: "관광 C·A 전용 판본 β 재추정", b: true }, { v: "재분석만", c: GREEN }, "유일 통과 산업의 타당성 확인"],
    [{ v: "5", b: true, c: AMBER }, { v: "C–B 상관·VIF 공시, 차원별 증분 설명력", b: true }, { v: "재분석만", c: GREEN }, "3차원 설계의 정당화"],
    [{ v: "6", b: true, c: AMBER }, { v: "합성 준거 4개 산업 β 판정 보류 표기", b: true }, "표기 수정", "순환 준거 노출 차단"],
    [{ v: "7", b: true, c: GREY }, { v: "시차차 산식 명시, 다중비교 보정", b: true }, "재분석 + 표기", "해석 가능성 확보"],
    [{ v: "8", b: true, c: GREY }, { v: "Executive Summary 전면 수정", b: true }, "집필", "요약–본문 정합"],
  ], [8, 40, 26, 26]));
k.push(sp());
k.push(p([t("1~5번은 "), t("추가 데이터 구매 없이 기존 자료의 재분석만으로 수행 가능", { b: true, c: GREEN }),
  t("하다. 보고서가 차기 과제로 제시한 “보조 자료 구매”보다 우선한다 — 데이터를 더 사기 전에 지금 데이터로 무엇을 말할 수 있는지가 먼저 확정되어야 한다.")]));

// ── 6. 종합 판정
k.push(h1("6. 종합 판정"));
k.push(table(["영역", "판정", "사유"],
  [
    ["설계 방향", { v: "우수", b: true, c: GREEN }, "좌우변 분리와 심리 단계 재편은 지수 연구의 정석"],
    ["추정 구조", { v: "결함", b: true, c: RED }, "비음수 제약 하 부호 보고 · 적합 순환 · 위약 부재"],
    ["준거 품질", { v: "부분 미달", b: true, c: RED }, "8종 중 4종 합성, 그중 2종에 좌변 원천 혼입"],
    ["표본", { v: "미달", b: true, c: RED }, "5개국, 그중 2개국이 83% · 저신호 절단의 생존 편의"],
    ["보고 정직성", { v: "양호", b: true, c: GREEN }, "본문은 한계를 명시. 다만 요약이 본문보다 강하게 말한다"],
    ["인용 가능성", { v: "현 단계 불가", b: true, c: RED }, "1~3번 조치 후 재심사 필요"],
  ], [16, 18, 66]));
k.push(sp());
k.push(p([t("이 보고서의 가장 큰 위험은 방법론이 아니라 "), t("요약과 본문의 낙차", { b: true, c: RED }),
  t("에 있다. 본문은 “β는 참고치”, “측정 불능 공시”, “OOS 동시 충족은 관광뿐”이라고 적었으나, 요약은 “8산업 β 전부 양수”를 앞세운다. "),
  t("정책 결정자 대부분은 요약만 읽는다.", { b: true })]));
k.push(p([t("본 심사자의 권고는 다음과 같다. "),
  t("β 판정을 결과가 아닌 “진단 절차의 작동 확인”으로 재서술하고, 실증 결론은 위약검정과 표본 분리 이후로 미룰 것.", { b: true, c: NAVY }),
  t(" 파일럿의 성과는 β의 크기가 아니라 측정→준거→추정→검증 체계가 실데이터에서 끝까지 돌았다는 사실이며, 그것만으로도 충분한 중간 성과다.")]));

k.push(new Paragraph({
  children: [t("본 심사는 KCI 중간보고서 요약본(20쪽)과 KWCI 공개 저장소(jason-j-kim/kwci-dashboard, 커밋 55abda7, 산출 2026-09-02)의 코드·산출 데이터 직접 검증에 근거한다. §1.3의 수치는 심사자가 해당 저장소의 패널 CSV로 재계산한 값이다. 본보고서에서 이미 다뤄진 항목이 있다면 해당 지적은 철회한다.", { size: 16, c: GREY })],
  spacing: { before: 340 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: LINE, space: 8 } },
}));

const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 20 } } } },
  sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: k }],
});
Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(process.argv[2], b);
  console.log("= " + process.argv[2] + "  " + (b.length / 1024).toFixed(0) + " KB");
});

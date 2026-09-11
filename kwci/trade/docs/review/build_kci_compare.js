const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, HeadingLevel, ShadingType,
} = require("docx");

const NAVY = "1F3864", RED = "A62B2B", GREEN = "2E6B3E", AMBER = "9A6A00",
      GREY = "5A5A5A", LINE = "C9C9C9", BG = "F2F4F7";

const F = "맑은 고딕";

const t = (text, o = {}) => new TextRun({ text, font: F, size: o.size || 20,
  bold: o.b, italics: o.i, color: o.c, break: o.br });

const p = (runs, o = {}) => new Paragraph({
  children: Array.isArray(runs) ? runs : [runs],
  spacing: { before: o.before ?? 60, after: o.after ?? 60, line: 276 },
  alignment: o.align,
  indent: o.indent,
  border: o.border,
});

const h1 = (text) => new Paragraph({
  children: [t(text, { size: 30, b: true, c: NAVY })],
  spacing: { before: 360, after: 140 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY, space: 6 } },
});

const h2 = (text, color) => new Paragraph({
  children: [t(text, { size: 24, b: true, c: color || NAVY })],
  spacing: { before: 240, after: 90 },
});

const body = (text, o = {}) => p(t(text, o));

const bullet = (text, o = {}) => new Paragraph({
  children: [t("· ", { c: GREY }), t(text, o)],
  spacing: { before: 40, after: 40, line: 276 },
  indent: { left: 220, hanging: 140 },
});

const quote = (text) => new Paragraph({
  children: [t(text, { i: true, c: GREY, size: 19 })],
  spacing: { before: 90, after: 110, line: 264 },
  indent: { left: 340 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: LINE, space: 10 } },
});

const cell = (content, o = {}) => new TableCell({
  width: { size: o.w || 0, type: WidthType.PERCENTAGE },
  shading: o.bg ? { type: ShadingType.CLEAR, fill: o.bg } : undefined,
  margins: { top: 70, bottom: 70, left: 110, right: 110 },
  children: (Array.isArray(content) ? content : [content]).map((c) =>
    new Paragraph({
      children: typeof c === "string" ? [t(c, { size: 18, b: o.b, c: o.c })] : [c],
      alignment: o.align,
      spacing: { before: 0, after: 0, line: 252 },
    })),
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
    new TableRow({
      tableHeader: true,
      children: header.map((hh, i) =>
        cell(hh, { b: true, c: NAVY, bg: BG, w: widths[i] })),
    }),
    ...rows.map((r) => new TableRow({
      children: r.map((c, i) => {
        if (c && typeof c === "object" && !Array.isArray(c)) {
          return cell(c.v, { w: widths[i], b: c.b, c: c.c });
        }
        return cell(c, { w: widths[i] });
      }),
    })),
  ],
});

const spacer = () => new Paragraph({ children: [], spacing: { before: 0, after: 100 } });

// ══════════════════════════════════════════════════════════════════
const kids = [];

kids.push(new Paragraph({
  children: [t("KCI 중간보고서 검토", { size: 40, b: true, c: NAVY })],
  spacing: { after: 60 },
}));
kids.push(new Paragraph({
  children: [t("KWCI 대비 무엇이 개선되고 무엇이 악화되었는가", { size: 24, c: GREY })],
  spacing: { after: 140 },
}));
kids.push(new Paragraph({
  children: [t("대상: 「K-Culture Index(KCI) 개발 및 실증 연구」 중간보고서 요약본 (재정학회, 2026.9)", { size: 17, c: GREY }),
             t("대조: KWCI 대시보드 해설서(2026-06-28) 및 jason-j-kim/kwci-dashboard 저장소(55abda7, 산출 2026-09-02)", { size: 17, c: GREY, br: true })],
  spacing: { after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LINE, space: 8 } },
}));

// ── 총평
kids.push(h1("총평"));
kids.push(p([t("KCI는 KWCI의 개선판이 아니라 "), t("다른 종류의 지수다", { b: true, c: NAVY }),
  t(". KWCI는 “지금 한류가 어느 나라에서 얼마나 센가”를 기술하는 상태지수이고, KCI는 “관심이 수출을 선행하는가”를 검정하는 예측모형이다. 두 지수를 같은 축에 놓고 우열을 가리는 것은 성립하지 않는다.")]));
kids.push(p([t("그 전제 위에서 판정하면 — "), t("틀은 크게 개선됐고, 증거의 힘은 아직 약하며, 적용 범위는 후퇴했다.", { b: true })]));
kids.push(spacer());
kids.push(table(
  ["항목", "판정", "근거"],
  [
    [{ v: "방법론 설계", b: true }, { v: "크게 개선", b: true, c: GREEN }, "순환참조 제거 · 가중 내생화 · 검정 도입 · 측정불능 공시"],
    [{ v: "증거의 힘", b: true }, { v: "아직 약함", b: true, c: AMBER }, "r² .01~.08(8개 중 7개) · 시차 음수 4개 · 준거 절반 합성 · 위약검정 부재"],
    [{ v: "적용 범위", b: true }, { v: "후퇴", b: true, c: RED }, "15개국 → 5개국, 그중 2개국이 글로벌의 83%"],
    [{ v: "산출물", b: true }, { v: "후퇴", b: true, c: RED }, "다변화(ENM) · 대시보드 · 2018=100 장기 시계열 상실"],
    [{ v: "문서 품질", b: true }, { v: "보완 필요", b: true, c: AMBER }, "요약–본문 불일치 · 식품 누락 · 오탈자·용어 혼용"],
  ], [18, 18, 64]));

// ── 구조 대조
kids.push(h1("1. 구조 대조"));
kids.push(table(
  ["", "KWCI (대시보드)", "KCI (중간보고서)"],
  [
    ["지수 안에 든 것", "L1 경제(0.5) + L2 영향력(0.3) + L3 수용자(0.2)", { v: "관심만 — C(인지·검색)·A(태도·댓글)·B(행동의도)", b: true }],
    ["수출의 위치", { v: "지수 내부, 가중 0.5", b: true, c: RED }, { v: "지수 밖 외부 준거(우변)", b: true, c: GREEN }],
    ["가중치 결정", "사람이 지정, 4~5개 프로파일 토글", { v: "NNLS로 추정 (수출을 가장 잘 설명하는 비율)", b: true }],
    ["시간 해상도", "분기 (실제로는 연간 선형보간)", { v: "주간", b: true }],
    ["대상 국가", "15", { v: "5 (미·사우디·일·영·베트남)", c: RED }],
    ["검정 장치", { v: "없음", c: RED }, "β · r² · 시차 k · 전환감쇠비 → 4등급 판정"],
    ["부가 산출", "8도메인 종합 · ENM 다변화 · 라이브 대시보드", "35/40셀 (대시보드는 차기 과제)"],
  ], [20, 40, 40]));

// ══ 개선
kids.push(h1("2. 개선된 것"));

kids.push(h2("2.1  순환참조를 끊었다 — 가장 큰 변화", GREEN));
kids.push(body("KWCI는 수출을 지수 안에 0.5 가중으로 넣고 그 지수로 한류를 설명했다. “라면 수출이 늘었다 → 지수가 올랐다 → 한류 때문에 라면이 팔린다”는 동어반복이다."));
kids.push(body("KCI는 이 문제를 명시적으로 인지하고 고쳤다."));
kids.push(quote("MVP: EPMCR 5요소 설계 중 E 단일 지수로 개념 실증(‘관심→수출 연관의 존재’로 순환 참조 문제점 확인) / Pilot 1차: C(소비·상거래) 요소는 지수 내부에서 분리해 ‘수출액’이라는 외부 준거로 전환 / 좌변(관심 신호)과 우변(성과 준거)의 분리가 모형의 골격"));
kids.push(p([t("KWCI가 "), t("구조적으로 던질 수 없는 질문", { b: true }), t("을 KCI는 던질 수 있다.")]));

kids.push(h2("2.2  가중치가 내생화됐다", GREEN));
kids.push(body("KWCI의 0.5/0.3/0.2와 도메인 가중은 전부 사람이 정했고, 프로파일을 바꾸면 국가 순위가 재배열되는데 고를 근거는 “가치판단”이었다. KCI는 결과준거가중 + NNLS(미 연준 FCI-G 기법)로 데이터가 정한다. 발표자료의 원칙 — “고정 사전은 출발점이고 최종 목적은 내생적 결정” — 이 실현된 자리다."));

kids.push(h2("2.3  실패할 수 있는 장치가 생겼다", GREEN));
kids.push(body("KWCI에는 가설도 기각 가능성도 없다. KCI는 산업별로 신뢰 / 양호 / 경계 / 공시 등급을 매기고, 영상·웹툰은 스스로 “공시(부호 역전)”로 내려앉힌다."));

kids.push(h2("2.4  측정 불능을 감추지 않는다", GREEN));
kids.push(p([t("KWCI는 관광 L1이 API 실패로 샘플 폴백인데도 "), t("수치는 그대로 나간다", { b: true, c: RED }),
  t(" — 해설서가 “수치는 동일하고 출처 라벨만 바뀐다”고 적어놓았다. KCI는 40셀 중 5셀을 아예 산출하지 않고(게임 4개국, 패션 사우디), 품질 기준까지 명시했다 — 비영 토픽 ≥3, 전 기간 커버 토픽 ≥1.")]));

kids.push(h2("2.5  순환 금지를 제도화했다", GREEN));
kids.push(quote("준거에 사용된 데이터는 검증에 재사용 불가 / 게임·웹툰 = 매출 순위(Top Grossing)는 우변 전용, 무료 다운로드(Top Free)는 좌변 전용"));

kids.push(h2("2.6  재척도 문제를 이미 풀었다", GREEN));
kids.push(body("Google Trends는 요청당 최대 5개 질의를 0~100으로 상대 정규화하므로, 배치마다 척도가 달라 이어붙일 수 없다. KCI는 이를 겹침 체인·접합 배율·브리지로 처리하고, 사전·앵커·모수 동결과 세대(D1→D3) 버전 관리까지 갖췄다. 대규모 Trends 수집에서 가장 먼저 부딪히는 함정을 선제적으로 해결한 부분이다."));

// ══ 악화
kids.push(h1("3. 악화되거나 잃은 것"));

kids.push(h2("3.1  범위가 3분의 1로 줄었고, 2개국이 83%를 차지한다", RED));
kids.push(p([t("15개국 → 5개국. 그리고 글로벌 KCI의 국가 가중이 "), t("일본 50% · 미국 33% = 83%", { b: true, c: RED }), t("다. 보고서도 인정한다 — ")]));
kids.push(quote("두 나라 곡선이 곧 세계 곡선. 15국 확장 시 중국(13.5%)·대만(8.7%) 진입으로 구성 대폭 변동 예정"));
kids.push(body("이 상태로 “글로벌 KCI”라는 이름을 쓰는 것은 무리다. 명칭에 5개국임을 병기하는 편이 안전하다."));

kids.push(h2("3.2  준거의 절반이 합성인데, 그것이 회귀의 종속변수다", RED));
kids.push(spacer());
kids.push(table(
  ["실측 준거 (4종)", "합성 준거 (4종)"],
  [
    ["식품·뷰티·패션 — 관세청 HS 품목", "음악·영상 — ECOS 총액 × 배분율"],
    ["관광 — KTO 입국자 수", "게임·웹툰 — 콘진원 총액 × Google Play 순위 변조"],
  ], [50, 50]));
kids.push(spacer());
kids.push(p([t("KWCI도 콘텐츠 L1이 부실했지만 거기서는 "), t("설명변수", { b: true }), t("였다. KCI에서는 "),
  t("회귀의 종속변수", { b: true, c: RED }),
  t("다. 종속변수가 합성이면 β가 잡아낸 것이 실제 수출인지 합성 규칙 자체인지 구분되지 않는다. 보고서도 “게임·웹툰 β는 참고치”라고 적었다.")]));
kids.push(body("영상은 더 미묘하다. 준거가 「Netflix Top10 소비 변조」인데 제5장의 검증 원천도 「Netflix Top10 변형 지표」다. “원계열은 우변 사용 중”이라 변형을 쓴다지만, 스스로 세운 순환 금지 원칙의 경계선이다."));

kids.push(h2("3.3  r²가 8개 중 7개에서 .01~.08이다", RED));
kids.push(spacer());
kids.push(table(
  ["산업", "준거 등급", "β (k주)", "r²", "시차차", "판정"],
  [
    [{ v: "관광", b: true }, "KTO 실측", "0.0020 (6)", { v: ".21", b: true, c: GREEN }, "+3", { v: "신뢰", c: GREEN }],
    ["뷰티", "KCS 실측", "0.0008 (7)", ".04", { v: "−1", c: RED }, "양호"],
    ["게임", "KOCCA 합성", "0.0006 (10)", ".08", "0", "양호"],
    ["패션", "KCS 실측", "0.0027 (3)", ".04", { v: "−9", b: true, c: RED }, "경계"],
    ["음악", "ECOS 프록시", "0.0025 (6)", ".03", { v: "−5", c: RED }, "경계"],
    [{ v: "식품", b: true, c: RED }, "KCS 실측", { v: "0.00006 (3)", c: RED }, { v: ".01", c: RED }, { v: "−1", c: RED }, "경계"],
    ["영상", "ECOS 프록시", "0.0008 (3)", ".03", "—", { v: "공시(부호 역전)", c: RED }],
    ["웹툰", "KOCCA 합성", "0.0017 (12)", ".03", "—", { v: "공시(부호 역전)", c: RED }],
  ], [12, 18, 18, 10, 12, 30]));
kids.push(spacer());
kids.push(p([t("Executive Summary는 "), t("“8산업 β 전부 양수(방향 일관)”", { b: true }),
  t("를 앞세운다. 그러나 r²가 .01~.03인 계열의 부호는 거의 의미가 없다. 그 정도 설명력은 서로 무관한 시계열 쌍에서도 흔히 나온다.")]));

kids.push(h2("3.4  위약검정이 없다 — 지금 가장 시급한 결손", RED));
kids.push(body("PRD 대조 사전(1,062행)과 “이중 트랙 대조”는 있으나, 반도체·석유 같은 문화 무관 품목에 같은 모형을 돌려 β가 0인지 확인하는 절차는 보고서에 보이지 않는다."));
kids.push(p([t("r²가 이 수준이면 "), t("위약 없이는 “8개 전부 양수”가 신호인지 잡음인지 판별할 수 없다.", { b: true }),
  t(" 8개가 모두 양수일 확률은, 계열끼리 상관되어 있으면 결코 1/256이 아니다. 위약 품목에서도 β가 양수로 나온다면 통제가 불충분한 것이므로 결과를 채택해서는 안 된다.")]));

kids.push(h2("3.5  시차가 음수인 산업이 넷이다", RED));
kids.push(body("보고서는 시차차를 “관심의 구매 선행 주수”로 정의했다. 그 정의대로 읽으면 음수는 관심이 구매를 뒤따른다는 뜻이다. 선행지표를 표방하는 지수에서 패션 −9주는 “동행형”으로 뭉뚱그릴 수 있는 값이 아니다."));
kids.push(p([t("다만 PRD 트랙과의 차분값일 가능성도 있어 보인다. "), t("표에 산식이 없어 정의가 확정되지 않는다", { b: true }),
  t(" — 확인이 필요한 지점이다.")]));

kids.push(h2("3.6  요약과 본문이 어긋난다", AMBER));
kids.push(spacer());
kids.push(table(
  ["Executive Summary", "본문 β표"],
  [
    ["“8산업 β 전부 양수”", { v: "영상·웹툰 판정 = “공시(PRD 부호 역전)”", c: RED }],
    ["관광 / 뷰티·게임 / 패션·음악 / 영상·웹툰 — 7개 산업", { v: "8개 산업. 식품이 누락됐다", b: true, c: RED }],
  ], [50, 50]));
kids.push(spacer());
kids.push(p([t("빠진 식품이 하필 "), t("가장 약한 산업", { b: true }),
  t("이다 — β 0.00006(뷰티의 1/13), r² .01, 전환감쇠비 0.41(유일하게 1 미만). 요약에서 최약 산업이 빠진 것은 의도가 아니더라도 오해를 산다.")]));
kids.push(body("용어도 흔들린다. 같은 범주를 요약은 “무관형”, 제4·6장은 “무작위형”으로 부른다. 표지 날짜가 「20206.9」이고 본문에 “5개국 개상”, “k기 선행” 등 오탈자가 있다. 문체부 제출본이면 교정이 필요하다."));

kids.push(h2("3.7  KWCI가 갖고 있던 산출물이 사라졌다", AMBER));
kids.push(body("8도메인 종합 단일지수(정책 커뮤니케이션용), ENM 다변화 지표, 라이브 대시보드, 15개국 패널, 2018=100 장기 시계열. KCI에서 대시보드는 “차기 과제”다."));
kids.push(p([t("특히 "), t("다변화 지표의 상실이 아깝다", { b: true }),
  t(". KWCI에서 나온 “관광은 2024년 중국 재집중으로 93.8 — 2018년 아래” 같은 발견은 β로는 나오지 않는다. 볼륨과 분리된 복원력 차원은 정책 판단에 직접 쓰이는 정보다.")]));

// ── 권고
kids.push(h1("4. 권고"));
kids.push(table(
  ["우선순위", "항목", "사유"],
  [
    [{ v: "1", b: true, c: RED }, { v: "위약검정 추가", b: true }, "r² .01~.08에서 “방향 일관”을 주장하려면 필수. 문화 무관 품목에 동일 모형 적용"],
    [{ v: "2", b: true, c: RED }, { v: "Executive Summary 수정", b: true }, "본문과 불일치. 식품 누락 복원, 부호 역전 2건 명시, r² 병기"],
    [{ v: "3", b: true, c: AMBER }, { v: "시차차 정의 명시", b: true }, "산식 부재로 음수 4건의 해석이 확정되지 않음"],
    [{ v: "4", b: true, c: AMBER }, { v: "합성 준거 β의 지위 격하 표기", b: true }, "게임·웹툰·음악·영상 β는 본문 표에서도 “참고치”로 구분"],
    [{ v: "5", b: true, c: GREY }, { v: "“글로벌 KCI” 명칭에 5개국 병기", b: true }, "일·미가 83%. 현재 명칭은 범위를 오인시킨다"],
    [{ v: "6", b: true, c: GREY }, { v: "KWCI와의 관계 정리 1개 절 추가", b: true }, "보고서에 KWCI 언급이 없다. 병존 시 인용자가 혼란"],
    [{ v: "7", b: true, c: GREY }, { v: "다변화(ENM) 승계 검토", b: true }, "KWCI의 유효 산출물. β가 대체하지 못하는 차원"],
  ], [10, 32, 58]));

kids.push(h1("5. 맺음"));
kids.push(p([t("이 보고서는 "), t("틀을 고치느라 결과를 잃은 상태", { b: true, c: NAVY }),
  t("다. 파일럿 단계에서는 정상적인 거래이며, “β는 참고치”·“측정 불능 공시”라고 스스로 밝히는 태도는 KWCI보다 훨씬 정직하다.")]));
kids.push(p([t("다만 "), t("Executive Summary만 읽으면 그 정직함이 보이지 않는다.", { b: true, c: RED }),
  t(" 요약이 본문보다 강하게 말한다. 이 보고서의 가장 큰 위험은 방법론이 아니라 여기에 있다 — 읽는 사람 대부분은 요약만 읽는다.")]));

kids.push(new Paragraph({
  children: [t("본 검토는 KCI 중간보고서 요약본(20쪽)과 KWCI 대시보드 해설서·공개 저장소(jason-j-kim/kwci-dashboard, 커밋 55abda7, 산출 2026-09-02)의 실제 코드·산출 데이터 대조에 근거한다. KWCI 측 수치는 라이브 산출값 기준이며, 해설서(2026-06-28)의 수치와는 차이가 있다.", { size: 16, c: GREY })],
  spacing: { before: 340 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: LINE, space: 8 } },
}));

const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 20 } } } },
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } },
    children: kids,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = process.argv[2];
  fs.writeFileSync(out, buf);
  console.log("= " + out + "  " + (buf.length / 1024).toFixed(0) + " KB");
});

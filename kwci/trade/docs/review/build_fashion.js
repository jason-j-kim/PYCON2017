const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
} = require("docx");
const fs = require("fs");

const FONT = "맑은 고딕";
const MONO = "Consolas";
const INK = "1A1A1A", MUTED = "6B6B6B";
const NAVY = "1F3A5F", RED = "9E2A2B", GREEN = "2D5A3D", AMBER = "8A6510";
const RULE = "D8D8D8", TINT = "F3F4F6";
const W = 9360;

const p = (t, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 130, line: 276 },
  indent: o.indent ? { left: o.indent } : undefined,
  children: [new TextRun({ text: t, font: FONT, size: o.size ?? 20,
    color: o.color ?? INK, bold: o.bold, italics: o.italics })],
});

const lead = (b, r, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 130, line: 276 },
  children: [
    new TextRun({ text: b, font: FONT, size: 20, bold: true, color: o.lc ?? INK }),
    new TextRun({ text: r, font: FONT, size: 20, color: INK })],
});

const h1 = (t, c = NAVY) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 380, after: 110 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
  children: [new TextRun({ text: t, font: FONT, size: 26, bold: true, color: c })],
});

const h2 = (t) => new Paragraph({
  spacing: { before: 280, after: 110 }, keepNext: true,
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, color: INK })],
});

const quote = (t, who) => new Paragraph({
  spacing: { before: 60, after: 130, line: 264 },
  indent: { left: 340 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: "C9CDD2", space: 140 } },
  children: [
    new TextRun({ text: t, font: FONT, size: 18, color: "3D3D3D", italics: true }),
    ...(who ? [new TextRun({ text: `   — ${who}`, font: FONT, size: 16, color: MUTED })] : []),
  ],
});

const code = (ls) => ls.map((t, i) => new Paragraph({
  spacing: { before: i === 0 ? 60 : 0, after: i === ls.length - 1 ? 150 : 0 },
  indent: { left: 340 },
  children: [new TextRun({ text: t, font: MONO, size: 17, color: "2E4A52" })],
}));

const cell = (t, o = {}) => new TableCell({
  width: { size: o.w, type: WidthType.DXA },
  shading: o.head ? { type: ShadingType.CLEAR, fill: TINT } : undefined,
  margins: { top: 70, bottom: 70, left: 130, right: 130 },
  children: [new Paragraph({ alignment: o.align, spacing: { after: 0, line: 250 },
    children: [new TextRun({ text: t, font: FONT, size: 18,
      bold: o.head || o.b, color: o.c ?? INK })] })],
});

const table = (ws, hd, rows, al = []) => new Table({
  columnWidths: ws, width: { size: W, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [
    new TableRow({ tableHeader: true,
      children: hd.map((t, i) => cell(t, { w: ws[i], head: true, align: al[i] })) }),
    ...rows.map((r) => new TableRow({ children: r.map((c, i) => {
      const o = typeof c === "object" ? c : { t: c };
      return cell(o.t, { w: ws[i], align: al[i], b: o.b, c: o.c });
    }) })),
  ],
});

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20, color: INK } } } },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1150, left: 1080, right: 1080 } } },
    children: [
      new Paragraph({ spacing: { after: 40 }, children: [new TextRun({
        text: "K-Fashion 수출통계의 이중 왜곡", font: FONT, size: 32, bold: true, color: NAVY })] }),
      new Paragraph({ spacing: { after: 70 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: NAVY } },
        children: [new TextRun({ text: "", size: 2 })] }),
      p("KCI 조사보고서(김영범)와 KWCI L1 수집결과(김재준)의 대조  ·  2026-07-31",
        { color: MUTED, size: 18, after: 240 }),

      lead("두 조사가 K-Fashion에 대해 같은 결론에 다른 경로로 도달했다. ",
        "그리고 두 결과를 겹치면 각각으로는 나오지 않는 세 번째 결론이 나온다. " +
        "이 문서는 그 대조를 정리한다.", { after: 220 }),

      // ── 1 ────────────────────────────────────────────
      h1("1. 두 조사의 진단"),
      quote("“패션 수출액 상위국(베트남 19.6%·중국 13.1%·인니 6.3%)들이 K-패션 " +
        "소비국이 아니라 이를 가공하는 나라다. … 베트남 수출액은 베트남 소비자의 " +
        "K-패션 수요가 아니라 미국·유럽 의류 소비의 간접 함수다.”", "KCI 보고서 §3.7"),
      quote("“한국 브랜드 의류 수출의 상당분은 OEM·원부자재이고, 브랜드 완제품은 " +
        "역직구로 나가 일반 무역통계에서 과소계상된다.”", "KWCI 계획서 §4.2"),
      p("전자는 “통계에 잡히는 것이 소비 신호가 아니다”, 후자는 “소비 신호인 것이 " +
        "통계에 안 잡힌다”이다. 방향이 반대인 두 왜곡이다."),

      // ── 2 ────────────────────────────────────────────
      h1("2. 국가 순위가 실제로 다르다"),
      p("두 조사가 같은 해(2024) 같은 산업을 재고도 상위국이 다르다. " +
        "품목 정의가 다르기 때문이다.", { after: 180 }),
      table([1500, 1970, 1970, 1970, 1950],
        ["", "1위", "2위", "3위", "4·5위"],
        [
          [{ t: "KCI\n(MTI 4 섬유류)", b: true },
           { t: "베트남 19.6%", b: true, c: RED }, "중국 13.1%", "미국", "인니 6.3% · 일본"],
          [{ t: "KWCI\n(BEC 소비재)", b: true },
           { t: "중국 28%", b: true, c: GREEN }, "미국 23%", { t: "베트남 18%", c: MUTED }, "일본 14% · 대만 5%"],
        ]),
      lead("베트남이 1위에서 3위로 내려간다. ",
        "KWCI는 UN BEC rev.5의 최종소비재 판정을 통과한 품목만 남기므로 " +
        "원단(HS 50~60)·단추·지퍼가 애초에 대역에 없다. 김영범 박사가 " +
        "“향후 MTI 44로 한정해 다시 수집할 필요”라고 한 그 작업이, BEC 필터로 " +
        "이미 부분 수행된 셈이다.", { before: 160 }),

      h2("정량 대조 — 필터가 걷어낸 몫"),
      ...code([
        "KCI  패션 2024 (MTI 4 전체)        ≈ 10,650 백만$",
        "KWCI K-Fashion 2024 (BEC 소비재)   ≈  3,200 백만$",
        "                                    ────────────",
        "                              통과분  약 30%",
      ]),
      lead("주의 — 이 30%를 그대로 “B2B 비중”으로 읽으면 안 된다. ",
        "두 정의의 포괄 범위가 완전히 겹치지 않는다. KWCI 대역에는 신발(64)·" +
        "가방(4202)·장신구(7113/7117)·안경(9003/9004)이 들어 있고 이들은 MTI 4 " +
        "밖이다. 방향(대부분이 걸러진다)은 유효하나 배율은 정밀 대조가 필요하다."),

      // ── 3 ────────────────────────────────────────────
      h1("3. 겹쳤을 때 나오는 결론", RED),
      lead("B2B 왜곡을 걷어냈는데도 K-Fashion은 여전히 낮다. ",
        "이것이 두 조사를 합쳐야만 보이는 사실이다."),
      table([3200, 3080, 3080],
        ["지표", "K-Fashion", "다른 도메인"],
        [
          ["성장 (2018=100 → 2024)", { t: "104.4", b: true, c: RED },
           "K-Beauty 164.6 · K-Food 161.4"],
          ["RCA ≥ 1 통과율", { t: "3/30 = 10%", b: true, c: RED },
           "K-Beauty 40% · K-Food 47%"],
          ["다변화 ENM (2018→2024)", "5.20 → 5.22", "K-Beauty 2.49 → 4.58"],
        ],
        [undefined, AlignmentType.CENTER, undefined]),
      p("만약 낮은 수치의 원인이 B2B 부자재 혼입뿐이었다면, 소비재만 남긴 " +
        "KWCI 집계에서는 정상 수준이 나와야 한다. 그런데 6년간 4% 성장에 " +
        "특화도 통과율 10%다.", { before: 160 }),
      lead("→ B2B 왜곡을 제거해도 낮다는 것은, 남은 설명이 “실제로 정체했다” " +
        "아니면 “통계 밖에서 성장했다” 둘 중 하나라는 뜻이다. ",
        "김영범 보고서 단독으로는 첫 번째 가능성을 배제할 수 없고, KWCI 단독으로는 " +
        "낮은 수치가 부자재 탓인지 역직구 탓인지 구분할 수 없다. " +
        "두 결과를 겹쳐야 선택지가 둘로 좁혀진다."),

      h2("다변화 지표가 주는 보조 증거"),
      p("K-Fashion의 ENM은 5.20 → 5.22로 6년간 사실상 무변화다. 같은 기간 " +
        "K-Beauty는 2.49 → 4.58로 시장 구조가 크게 재편됐다. 시장이 실제로 " +
        "움직이는 산업은 집중도가 변한다. K-Fashion만 6년간 정지해 있다는 것은, " +
        "이 통계가 살아있는 시장의 변화를 담고 있지 않다는 신호로 읽힌다."),
      p("다만 이는 방증이지 증거가 아니다. B2B 가치사슬이 안정적이면 " +
        "집중도도 안정적일 수 있다.", { color: MUTED, size: 18 }),

      // ── 4 ────────────────────────────────────────────
      h1("4. 남은 오염원 — KWCI 쪽도 깨끗하지 않다", AMBER),
      p("공정하게 적자면, BEC 필터도 부자재를 전부 걸러내지 못했다. " +
        "KWCI의 K-Fashion 상위 품목에 다음이 남아 있다."),
      table([2100, 4200, 3060],
        ["HS", "품목", "문제"],
        [
          ["711319", "귀금속 장신구", { t: "단가 16,637$/kg — 금 시세 반영, 사실상 금괴성 거래", c: RED }],
          ["621790", "의류 부속품(garment parts)", "BEC는 소비재로 보나 실질은 부자재"],
          ["621710", "의류 액세서리", "동일"],
        ]),
      lead("711319는 특히 문제다. ",
        "단가가 2위 품목(20$/kg)의 800배다. 이것이 K-Fashion 1위에 올라 있는 " +
        "동안에는 도메인 총액과 성장률이 금 시세에 좌우된다. KWCI는 이를 미리 " +
        "제거하지 않고 S3(한류 반응성 회귀)의 위약검정으로 걸러내도록 설계했으나, " +
        "S3 실시 전까지는 오염원으로 남는다.", { before: 160 }),

      // ── 5 ────────────────────────────────────────────
      h1("5. 검증 설계 — 세 정의를 나란히"),
      p("두 조사의 대조가 시사하는 것은 “어느 정의가 옳은가”가 아니라 " +
        "“정의를 바꾸면 무엇이 달라지는가를 보여야 한다”는 것이다. " +
        "같은 연도에 대해 세 계열을 나란히 산출하면 왜곡의 크기가 정량화된다."),
      table([1300, 3400, 4660],
        ["", "정의", "읽는 법"],
        [
          [{ t: "①", b: true }, "MTI 4 섬유류 전체", "산업 규모 — 원부자재 포함, 소비 신호 아님"],
          [{ t: "②", b: true }, "BEC 최종소비재 (현 KWCI)", "①에서 명백한 중간재 제거"],
          [{ t: "③", b: true }, "②에서 6217·7113 추가 제외", { t: "순수 브랜드 완제품 — 소비 신호에 가장 근접", b: true }],
        ],
        [AlignmentType.CENTER, undefined, undefined]),
      p("①→②→③으로 가며 베트남 비중이 계속 낮아지고 미국·일본 비중이 오른다면, " +
        "그 이동폭 자체가 “수출통계가 소비 신호를 얼마나 왜곡하는가”의 측정값이 " +
        "된다. 세 계열의 성장률 차이는 그 왜곡이 시계열에 미치는 영향이다.",
        { before: 140 }),
      lead("그리고 ③마저 낮게 나온다면 역직구 가설만 남는다. ",
        "그때 관세청 전자상거래 수출 통계를 붙이면 판정이 끝난다."),

      // ── 6 ────────────────────────────────────────────
      h1("6. 제안"),
      table([1300, 3200, 4860],
        ["", "누가", "무엇을"],
        [
          [{ t: "1", b: true }, "KCI (김영범)", "패션을 MTI 44로 재수집 — 위 ②에 해당. 기존 MTI 4와 병기"],
          [{ t: "2", b: true }, "KWCI (김재준)", "③ 계열 산출 — 6217·7113 제외 버전을 현 계열과 병렬 제공"],
          [{ t: "3", b: true }, "공동", "관세청 전자상거래 수출 통계 확보 — 양쪽 판정의 공통 전제"],
        ],
        [AlignmentType.CENTER, undefined, undefined]),
      p("2번은 KWCI 코드에서 대역 상수 두 줄을 고치면 되고 캐시가 있어 " +
        "재수집이 필요 없다. 3번이 병목이며, 두 조사가 함께 요청하는 편이 " +
        "확보 가능성이 높다.", { before: 140 }),

      new Paragraph({ spacing: { before: 300 },
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
        children: [new TextRun({ text: "", size: 2 })] }),
      lead("요약: ", "K-Fashion 수출통계는 양쪽에서 왜곡된다. 잡히는 것 중 " +
        "상당수는 소비 신호가 아니고(B2B), 소비 신호인 것 상당수는 잡히지 " +
        "않는다(역직구). 두 조사가 각각 한쪽씩 밝혔고, 겹치면 " +
        "“B2B를 걷어내도 낮다”는 새로운 사실이 나온다. 이는 역직구 가설을 " +
        "강화하지만 확정하지는 않으며, 확정에는 전자상거래 통계가 필요하다.",
        { before: 100, after: 60 }),
      p("본 대조에 쓰인 KWCI 수치의 원자료·코드는 " +
        "kwci_kfood_kbeauty_kfashion_20260731.zip 에 포함되어 있다.",
        { color: MUTED, size: 17 }),
    ],
  }],
});

Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(process.argv[2], b);
  console.log("작성 완료:", process.argv[2]);
});

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
} = require("docx");
const fs = require("fs");

const FONT = "맑은 고딕";          // 사용자 Windows 에서 렌더링될 한글 폰트
const MONO = "Consolas";
const INK = "1A1A1A";
const MUTED = "6B6B6B";
const ACCENT = "1F4E5F";
const RULE = "D8D8D8";
const TINT = "F2F5F6";

const W = 9360;                    // A4 본문 폭 (DXA)

const p = (text, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 140, line: 276 },
  alignment: o.align,
  children: [new TextRun({
    text, font: FONT, size: o.size ?? 20,
    color: o.color ?? INK, bold: o.bold, italics: o.italics,
  })],
});

// 굵은 도입부 + 이어지는 본문을 한 단락으로
const lead = (bold, rest, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 140, line: 276 },
  children: [
    new TextRun({ text: bold, font: FONT, size: 20, bold: true, color: INK }),
    new TextRun({ text: rest, font: FONT, size: 20, color: INK }),
  ],
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 340, after: 160 },
  children: [new TextRun({ text, font: FONT, size: 26, bold: true, color: ACCENT })],
});

const bullet = (text) => new Paragraph({
  spacing: { after: 90, line: 276 },
  indent: { left: 340, hanging: 200 },
  children: [
    new TextRun({ text: "· ", font: FONT, size: 20, color: MUTED }),
    new TextRun({ text, font: FONT, size: 20, color: INK }),
  ],
});

const code = (lines) => lines.map((t, i) => new Paragraph({
  spacing: { before: i === 0 ? 60 : 0, after: i === lines.length - 1 ? 160 : 0 },
  indent: { left: 260 },
  children: [new TextRun({ text: t, font: MONO, size: 17, color: "2E4A52" })],
}));

const cell = (text, o = {}) => new TableCell({
  width: { size: o.w, type: WidthType.DXA },
  shading: o.head ? { type: ShadingType.CLEAR, fill: TINT } : undefined,
  margins: { top: 70, bottom: 70, left: 130, right: 130 },
  children: [new Paragraph({
    alignment: o.align,
    spacing: { after: 0, line: 250 },
    children: [new TextRun({
      text, font: FONT, size: 18,
      bold: o.head || o.bold, color: o.color ?? INK,
    })],
  })],
});

const table = (widths, header, rows, aligns = []) => new Table({
  columnWidths: widths,
  width: { size: W, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [
    new TableRow({
      tableHeader: true,
      children: header.map((t, i) =>
        cell(t, { w: widths[i], head: true, align: aligns[i] })),
    }),
    ...rows.map((r) => new TableRow({
      children: r.map((c, i) => {
        const bold = typeof c === "object";
        const txt = bold ? c.t : c;
        return cell(txt, { w: widths[i], align: aligns[i], bold,
                           color: bold ? ACCENT : undefined });
      }),
    })),
  ],
});

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20, color: INK } } } },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1200, left: 1080, right: 1080 } } },
    children: [
      // ── 표제 ────────────────────────────────────────────────
      new Paragraph({
        spacing: { after: 60 },
        children: [new TextRun({
          text: "K-소비재 수출 데이터셋 — 한 장 요약",
          font: FONT, size: 34, bold: true, color: ACCENT })],
      }),
      new Paragraph({
        spacing: { after: 60 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT } },
        children: [new TextRun({ text: "", size: 2 })],
      }),
      p("2026-07  ·  KWCI 경제 레이어 1차 산출", { color: MUTED, size: 18, after: 300 }),

      // ── 물음 ────────────────────────────────────────────────
      h1("물음"),
      lead("한류의 경제 성과를 국가별로 재려면 ",
        "먼저 “어떤 품목이 한류 소비재인가”를 정해야 한다. " +
        "“라면은 한류다”라고 선언하면 결론을 전제로 쓰는 것이 된다. " +
        "연구자의 직관이 아닌 기준으로 고를 수 있는가.", { after: 60 }),

      // ── 방식 ────────────────────────────────────────────────
      h1("답한 방식"),
      lead("사람이 고르지 않고 ", "공개 분류와 정량 기준으로 걸렀다."),
      ...code([
        "HS 5,611개",
        " ├ S0   UN BEC 최종소비재만                 →  1,481",
        " ├ S1   aT·대한화장품협회·KOTRA 공식 분류    →    928  ← 동결",
        " ├ A    관세청 전수 조회, 수출액 상위        →     75",
        " └ S2   현시비교우위 RCA ≥ 1                →     23",
      ]),
      lead("928개 시점에서 목록을 SHA-256으로 동결했다. ",
        "검정 결과를 보고 후보를 바꾸면 해시가 달라진다. " +
        "사후 선택이 없었음을 파일로 증명한다."),
      p("관세청은 “한국이 얼마 팔았나”(분자)만 준다. RCA·단가 프리미엄은 " +
        "“세계 평균 대비”가 필요하므로 Comtrade가 분모를 맡는다. " +
        "두 소스는 대체재가 아니다.", { after: 60 }),

      // ── 산출 ────────────────────────────────────────────────
      h1("산출"),
      lead("75품목 × 15개국 × 2018~2024 = 7,875칸. ",
        "관세청 호출 약 1만 회, 실패 0. 총액·총량에 더해 단가(USD/kg)를 냈다 — " +
        "같은 1kg을 더 비싸게 파는가가 문화 프리미엄의 가장 직접적인 형태다.",
        { after: 180 }),
      table([1900, 1200, 1200, 1300, 1560, 2200],
        ["", "2018", "2024", "지수", "RCA 통과", "ENM (다변화)"],
        [
          ["K-Beauty", "44억$", "72억$", "164.6", "6/15", { t: "2.49 → 4.58" }],
          ["K-Food", "33억$", "53억$", "161.4", "14/30", "5.62 → 5.74"],
          ["K-Fashion", "17억$", "18억$", { t: "104.4" }, { t: "3/30" }, "5.20 → 5.22"],
        ],
        [undefined, AlignmentType.RIGHT, AlignmentType.RIGHT,
         AlignmentType.RIGHT, AlignmentType.CENTER, AlignmentType.CENTER]),
      p("공표 통계와 대조 — K-Beauty 총액 1.01배, 라면 1.12배, " +
        "한국 총수출 1.00배, 세계 총수출 0.95배.",
        { color: MUTED, size: 18, before: 140, after: 60 }),

      // ── 발견 ────────────────────────────────────────────────
      h1("알게 된 것"),
      lead("하나. 사전 가설이 틀렸다. ",
        "착수 시 “K-Beauty의 중국 의존이 심화됐을 것”으로 보았으나 반대였다. " +
        "ENM 2.49 → 4.58, 사실상 중국 단일 시장에서 미국·일본으로 분산됐다. " +
        "같은 기간 방한 관광은 중국 재집중으로 후퇴했다. 쏠림의 방향은 도메인마다 " +
        "다르므로 “한류 전반의 쏠림 심화”로 묶으면 틀린 정책이 나온다."),
      lead("둘. K-Fashion은 “약한 시장”이 아니라 “안 보이는 시장”일 수 있다. ",
        "성장 4%, RCA 통과 10%로 세 지표가 동시에 낮다. 그러나 같은 기간 패션 " +
        "플랫폼 해외 매출은 크게 늘었다. 브랜드 완제품이 역직구로 나가면 일반 " +
        "무역통계에서 과소계상된다. 이 수치는 “해외 판매 실적”이 아니라 " +
        "“일반 무역통계에 잡힌 부분”이다. 전자상거래 통계와 대조하기 전까지 " +
        "판정은 미결이다."),
      lead("셋. 세 도메인의 상위 5개국이 거의 같다 ",
        "(중국·미국·일본·베트남). 소비재 수출이 도메인 특성보다 시장 규모·" +
        "근접성에 좌우될 가능성을 시사한다.", { after: 60 }),

      // ── 미답 ────────────────────────────────────────────────
      h1("아직 답하지 않은 것"),
      lead("이 데이터셋은 “한국이 무엇을 얼마나 파는가”를 쟀다. ",
        "“그것이 한류 때문인가”는 검정하지 않았다. RCA는 한국의 특화도를 잴 뿐이다."),
      p("셋째 발견이 그 필요성을 보여준다. 구조가 이렇게 닮았으면 단순 상관으로는 " +
        "“한류 때문”과 “시장이 크기 때문”을 구분할 수 없다. 판별에는 파트너 GDP·" +
        "환율을 통제한 패널 회귀와, 반도체·석유·선박 같은 문화 무관 품목에 대한 " +
        "위약검정이 필요하다. 위약 품목에서 계수가 유의하면 통제가 불충분한 " +
        "것이므로 결과를 채택하지 않는다."),
      lead("panel.csv 가 그 회귀의 종속변수다. ",
        "한류 신호 자료만 결합하면 바로 돌아간다.", { after: 60 }),

      // ── 잔여 ────────────────────────────────────────────────
      h1("남은 과제"),
      table([4400, 4960],
        ["과제", "필요한 것"],
        [
          ["S3 한류 반응성 검정", "L3 신호(Trends·YouTube) 국가 × 기간"],
          ["K-Fashion 판정", "관세청 전자상거래 수출 통계"],
          ["분기 시차 분석", "월별 재수집 (현재는 연 단위)"],
        ]),
      p("세 가지 모두 기존 코드로 처리되며, 재수집은 캐시 덕에 증분으로 끝난다.",
        { before: 140, after: 300 }),

      new Paragraph({
        spacing: { before: 120 },
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
        children: [new TextRun({ text: "", size: 2 })],
      }),
      p("상세는 README.md(배포 요약)와 방법론_상세.md(전체 방법론·API 제약)를 참조.",
        { color: MUTED, size: 17, before: 100 }),
    ],
  }],
});

Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(process.argv[2] || "00_한장요약.docx", b);
  console.log("작성 완료:", process.argv[2]);
});

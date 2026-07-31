const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
} = require("docx");
const fs = require("fs");

const FONT = "맑은 고딕";
const MONO = "Consolas";
const INK = "1A1A1A";
const MUTED = "6B6B6B";
const RED = "9E2A2B";        // 치명
const AMBER = "8A6510";      // 내적 모순
const NAVY = "1F3A5F";       // 일반
const GREEN = "2D5A3D";      // 잘된 점
const RULE = "D8D8D8";
const TINT = "F3F4F6";
const W = 9360;

const p = (text, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 130, line: 276 },
  indent: o.indent ? { left: o.indent } : undefined,
  children: [new TextRun({
    text, font: FONT, size: o.size ?? 20,
    color: o.color ?? INK, bold: o.bold, italics: o.italics })],
});

const lead = (bold, rest, o = {}) => new Paragraph({
  spacing: { before: o.before ?? 0, after: o.after ?? 130, line: 276 },
  indent: o.indent ? { left: o.indent } : undefined,
  children: [
    new TextRun({ text: bold, font: FONT, size: 20, bold: true,
                  color: o.leadColor ?? INK }),
    new TextRun({ text: rest, font: FONT, size: 20, color: INK }),
  ],
});

// 항목 제목: [A] 배지 + 제목
const item = (tag, title, color) => new Paragraph({
  spacing: { before: 300, after: 120 },
  keepNext: true,
  children: [
    new TextRun({ text: `${tag}  `, font: FONT, size: 22, bold: true, color }),
    new TextRun({ text: title, font: FONT, size: 22, bold: true, color: INK }),
  ],
});

const h1 = (text, color = NAVY) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 380, after: 100 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
  children: [new TextRun({ text, font: FONT, size: 26, bold: true, color })],
});

// 원문 인용
const quote = (text) => new Paragraph({
  spacing: { before: 60, after: 130, line: 264 },
  indent: { left: 340 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: "C9CDD2", space: 140 } },
  children: [new TextRun({ text, font: FONT, size: 18, color: "3D3D3D", italics: true })],
});

const code = (lines) => lines.map((t, i) => new Paragraph({
  spacing: { before: i === 0 ? 60 : 0, after: i === lines.length - 1 ? 140 : 0 },
  indent: { left: 340 },
  children: [new TextRun({ text: t, font: MONO, size: 17, color: "2E4A52" })],
}));

const cell = (text, o = {}) => new TableCell({
  width: { size: o.w, type: WidthType.DXA },
  shading: o.head ? { type: ShadingType.CLEAR, fill: TINT } : undefined,
  margins: { top: 70, bottom: 70, left: 130, right: 130 },
  children: [new Paragraph({
    alignment: o.align, spacing: { after: 0, line: 250 },
    children: [new TextRun({ text, font: FONT, size: 18,
      bold: o.head || o.bold, color: o.color ?? INK })],
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
    new TableRow({ tableHeader: true,
      children: header.map((t, i) => cell(t, { w: widths[i], head: true, align: aligns[i] })) }),
    ...rows.map((r) => new TableRow({
      children: r.map((c, i) => {
        const o = typeof c === "object" ? c : { t: c };
        return cell(o.t, { w: widths[i], align: aligns[i], bold: o.b, color: o.c });
      }),
    })),
  ],
});

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 20, color: INK } } } },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1150, left: 1080, right: 1080 } } },
    children: [
      // ── 표제 ──────────────────────────────────────────
      new Paragraph({
        spacing: { after: 40 },
        children: [new TextRun({ text: "KCI 수출 준거 데이터 조사보고서 — 검토 의견",
          font: FONT, size: 32, bold: true, color: NAVY })],
      }),
      new Paragraph({
        spacing: { after: 70 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: NAVY } },
        children: [new TextRun({ text: "", size: 2 })],
      }),
      p("대상: 20260730_KCI_수출준거데이터_v3.docx (김영범)  ·  검토 2026-07-31",
        { color: MUTED, size: 18, after: 240 }),

      lead("치명적 오류 2건, 내적 모순 4건, 논리적 결함 3건. ",
        "추정치 사용 자체는 문제가 아니다. 문제는 추정 논리가 문서 안에서 " +
        "일관되지 않다는 점이다. 아래 A~D가 정리되면 전문가 논의 자료로 충분하다.",
        { after: 220 }),

      table([900, 4300, 2200, 1960],
        ["", "항목", "성격", "우선순위"],
        [
          [{ t: "A", b: true, c: RED }, "각주 ⓘ 자릿수 10배 오류", "치명", { t: "즉시", b: true, c: RED }],
          [{ t: "B", b: true, c: RED }, "단가 체계 이중화 — 총액≠국가별 합", "치명", { t: "즉시", b: true, c: RED }],
          [{ t: "C", b: true, c: AMBER }, "관광 산식이 §6과 §3.1에서 다름", "내적 모순", "배포 전"],
          [{ t: "D", b: true, c: AMBER }, "§3.8.2 뷰티 문단이 패션 복붙", "내적 모순", { t: "즉시", b: true, c: RED }],
          [{ t: "E", b: true, c: NAVY }, "웹툰 ⓖ — 비중 상승을 총액 성장으로", "논리", "재검토"],
          [{ t: "F", b: true, c: AMBER }, "제목이 문서 자신의 금지 규칙 위반", "내적 모순", "배포 전"],
          [{ t: "G", b: true, c: NAVY }, "HS 8523 표기 — 메모리 포함 호", "재현성", "배포 전"],
          [{ t: "H", b: true, c: NAVY }, "중국 2021 관광액 검산 불일치", "검산", "재검토"],
          [{ t: "I", b: true, c: NAVY }, "영상 2023 추정 표시(*) 누락", "표기", "배포 전"],
        ],
        [AlignmentType.CENTER, undefined, AlignmentType.CENTER, AlignmentType.CENTER]),

      // ── A ──────────────────────────────────────────────
      h1("치명적 오류", RED),
      item("[A]", "각주 ⓘ 자릿수 오류", RED),
      table([3000, 6360], ["위치", "값"],
        [["§1 표 8행 (관광 2025)", { t: "≈24,600 백만$", b: true }],
         ["각주 ⓘ", { t: "≈2,460 (2,080~2,840M$)", b: true, c: RED }]]),
      p("10배 차이다. 검산하면 1,894만 명 × $1,300 = 24,622M이므로 표가 맞고 " +
        "각주 전체가 한 자리 누락이다. 범위값도 1,894만 × $1,100~1,500 = " +
        "20,834~28,410M이어야 한다.", { before: 140 }),
      lead("영향: ", "각주만 보고 인용하면 관광이 뷰티(11,431)의 1/5로 읽힌다. " +
        "관광은 8개 산업 중 최대 항목이므로 순위가 통째로 뒤집힌다."),

      item("[B]", "단가 체계가 두 개 — 총액과 국가별 합이 맞지 않음", RED),
      table([2340, 1755, 1755, 1755, 1755],
        ["", "사우디", "중국", "미국", "일본"],
        [["§3.1 본문", "2,330", "1,920", "1,690", "930"],
         ["단가 표 (§3.1 하단)", "2,000", "1,650", "1,450", "800"],
         [{ t: "배율", b: true }, { t: "1.165", b: true, c: RED },
          { t: "1.164", b: true, c: RED }, { t: "1.166", b: true, c: RED },
          { t: "1.163", b: true, c: RED }]],
        [undefined, AlignmentType.RIGHT, AlignmentType.RIGHT,
         AlignmentType.RIGHT, AlignmentType.RIGHT]),
      p("전 항목이 정확히 1.165배 차이다. §3.1이 “2023년 앵커 $1,513으로 " +
        "재기준화했다”고 한 그 조정인데, 단가 표가 갱신되지 않았다(표는 평균 " +
        "$1,300 체계).", { before: 140 }),
      lead("표기 불일치에 그치지 않는다. ",
        "두 체계가 서로 다른 절에서 실제로 계산에 쓰였다."),
      ...code([
        "§1 표    관광 2023 = 14,340  ←  1,103만 × $1,300   (구체계)",
        "§3.1     중국 2023 =  3,878  ←    202만 × $1,920   (신체계)",
      ]),
      lead("국가별을 모두 더해도 총액이 나오지 않는다. ",
        "신체계로 통일하면 2023년 총액은 16,700 수준이어야 한다. 두 절을 함께 " +
        "인용할 수 없는 상태다."),

      // ── C·D·F ──────────────────────────────────────────
      h1("내적 모순", AMBER),
      item("[C]", "관광 산식이 §6과 §3.1에서 다름", AMBER),
      ...code([
        "§6 ⓔ    관광액 = 방한객수 × $1,300 (전체 평균)",
        "§3.1    관광액 = 방한객수 × 국가별 기준단가 × 연도지수",
      ]),
      p("§7 유의사항도 “국적별 단가 미반영 상태”라며 ⓔ 편에 선다. 그러나 §3.1은 " +
        "국가별 단가를 이미 적용했다고 서술한다. v2→v3 개정에서 §6·§7이 " +
        "따라오지 않은 것으로 보인다. 읽는 사람이 “이 표는 어떻게 만들어졌나”에 " +
        "답할 수 없다."),

      item("[D]", "§3.8.2 뷰티 문단이 패션 문단 복붙 + 문장 절단", AMBER),
      quote("“수출 상위 5국은 2023년 1~8월 관세통계 데이터를 연간으로 환산한 " +
        "것이다. 베트남 > 중국 > 미국 > 인니 > 일본의 순이다. 15개국의 " +
        "커버리지는 67.8%로 잔”"),
      p("§3.7 패션 문단과 글자까지 동일하고 “잔”에서 잘렸다. 베트남·인도네시아 " +
        "상위는 봉제국 서열이지 뷰티가 아니다."),
      lead("더 큰 문제는 바로 위 문단과의 모순이다. ",
        "§3.8은 “뷰티는 식약처 국가별 실측이 매년 있어 유일하게 연도별 변동 " +
        "비중을 실측으로 넣었다”고 한다. 그런데 여기선 “2023년 1~8월 구조 " +
        "환산”이라고 한다. 커버리지도 §3.8 앞부분의 83%→62%와 67.8%가 어긋난다."),

      item("[F]", "제목이 문서 자신의 금지 규칙을 위반", AMBER),
      quote("§7 — “관광은 서비스 수입이므로 ‘8대 산업 수출 총계’ 같은 단일 합산 " +
        "표기는 금지 — 수출(7개)과 관광(수입)을 분리 집계”"),
      p("그런데 문서 제목이 「8대 산업 × 15개국 × 5개년」이고 §1 표 제목이 " +
        "「전세계 연도별 8대 산업 수출총액」이다. 본인이 금지한 표기를 표제로 " +
        "쓰고 있다. 「7대 산업 수출 + 관광수입」으로 바꾸는 것이 맞다."),

      // ── E ──────────────────────────────────────────────
      h1("논리적 결함", NAVY),
      item("[E]", "웹툰 각주 ⓖ — 비중 상승을 총액 성장의 근거로 사용", NAVY),
      quote("“일본 비중이 40.3%→49.5%로 +9.2%p 급증한 것은 해외 매출이 국내보다 " +
        "빠르게 컸다는 신호라, 수출은 산업 성장률보다 높게 잡는 것이 정합적이다”"),
      lead("비중 상승은 총액 증가를 함의하지 않는다. ",
        "수출이 정체해도 다른 나라가 줄면 일본 비중은 오른다. 분모의 변화와 " +
        "분자의 변화를 구분하지 않았다."),
      lead("더 큰 문제는 저자 본인의 경고를 위반한다는 점이다. ",
        "§3.5 본문은 이렇게 적고 있다."),
      quote("“2023→2024의 일본 +9.2%p에는 ‘실제 집중 심화’와 ‘방식 변화’가 " +
        "섞여 있으므로 추세로 보는 경우 주의가 필요하다”"),
      p("방식 변화가 섞였을 수 있다고 경고해 놓고, 그 수치를 근거로 성장률을 " +
        "1.15~1.20배 상향했다. 웹툰은 이미 “총액 자체가 절반 추정”인 산업이라 " +
        "이 상향이 3층 추정 구조에서 그대로 증폭된다."),

      item("[G]", "HS 8523 — 재현 시 반드시 틀리는 표기", NAVY),
      p("§3.4는 “실물음반(관세청 HS8523, 총액의 ~16%)”이라 적었다. HS 8523에는 " +
        "SSD·메모리카드(8523.51)가 포함되고, 한국의 8523 수출은 압도적으로 " +
        "반도체다. 이 코드로 조회하면 음반이 아니라 메모리가 나온다."),
      p("인용된 “2023년 상반기 일본 4,852만$”는 음반 규모로 타당하므로 실제로는 " +
        "세부 소호를 쓰셨을 것이다. 그러나 문서에 8523으로만 적혀 있으면 다음 " +
        "사람이 반드시 틀린다. 정확한 소호(8523.80 등)를 명기해야 한다."),

      item("[H]", "검산이 맞지 않는 셀", NAVY),
      quote("§3.1 — “중국 … 2021년은 지수 1.75가 곱해져 1,119백만$”"),
      ...code([
        "2021년 중국 방한객 ≈ 17만 명",
        "  17만 × $1,920 × 1.75 =   572M   (신체계)",
        "  17만 × $1,650 × 1.75 =   491M   (구체계)",
        "  문서 값                = 1,119M   ← 약 2배",
      ]),
      p("어느 체계로도 재현되지 않는다. 원표를 확인하지 못해 단정할 수는 없으나 " +
        "검산이 필요하다."),

      item("[I]", "추정 표시(*) 누락", NAVY),
      p("§1 표 영상 2023년 「931 (영화 62 + 방송 미확정-전년 수치 도입)」은 " +
        "2022년 방송 수치(869)를 그대로 복사한 값인데 별표(*)가 없다. 다른 " +
        "추정치에는 모두 붙어 있어 확정치로 오독된다.", { after: 60 }),

      // ── 잘된 점 ────────────────────────────────────────
      h1("잘 되어 있는 부분", GREEN),
      lead("식품 통합의 중복 제거 검증이 이 보고서에서 가장 단단하다. ",
        "9,160 + 2,997 = 12,157 vs 공표 12,011, 오차 1.2%를 제시하고 그 원인" +
        "(집계 시점·품목 경계)까지 밝힌 것은 방법론적으로 모범이다. " +
        "K-Food+ 13,030과의 혼용 금지를 명시한 것도 정확하다."),
      lead("패션 B2B 문제 인식이 정확하다. ",
        "“베트남 수출액은 베트남 소비자의 K-패션 수요가 아니라 미국·유럽 의류 " +
        "소비의 간접 함수”라는 진단과 MTI 44로 한정하자는 처방 모두 옳다."),
      lead("N/A와 “미수집(경로)”의 구분은 좋은 설계다. ",
        "“원천이 세상에 없음”과 “있는데 아직 못 받음”을 섞지 않는 규율이 " +
        "후속 작업의 우선순위를 자동으로 정해 준다."),
      lead("뷰티의 연도별 변동 비중은 유일하게 전 연도 실측이다. ",
        "식약처 공표와 0.1% 이내 정합이며, 중국 53.2%→17.6%, 미국 8.8%→19.1%도 " +
        "별도 확인한 값과 일치한다.", { after: 60 }),

      // ── 조치 ──────────────────────────────────────────
      h1("조치 우선순위"),
      table([2200, 7160], ["시점", "항목"],
        [[{ t: "즉시", b: true, c: RED }, "A 각주 ⓘ 자릿수 · D 뷰티 문단 재작성"],
         [{ t: "배포 전", b: true, c: AMBER }, "B·C 단가 체계와 산식을 하나로 통일 · F 제목 수정 · G HS 소호 명기 · I 별표"],
         [{ t: "재검토", b: true }, "E 웹툰 상향 근거 · H 중국 2021 검산"]]),
      lead("B·C가 가장 무겁다. ",
        "나머지는 오탈자 수준이지만 이 둘은 “이 표가 어떻게 계산됐는지 문서로 " +
        "알 수 없다”는 문제라, 전문가 검토에서 가장 먼저 걸린다. 관광 셀이 " +
        "§1과 §3.1에서 다른 값을 내는 상태로는 두 절을 함께 인용할 수 없다.",
        { before: 160 }),

      new Paragraph({
        spacing: { before: 280 },
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
        children: [new TextRun({ text: "", size: 2 })],
      }),
      p("추정치가 대부분인 것은 현 단계에서 불가피하다는 판단에 동의한다. " +
        "추정 자체가 문제가 아니라 추정 논리가 문서 안에서 일관되지 않은 것이 " +
        "문제이며, A·B·C·D만 정리되면 전문가 논의 자료로 충분히 견딘다.",
        { color: MUTED, size: 18, before: 100 }),
    ],
  }],
});

Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(process.argv[2], b);
  console.log("작성 완료:", process.argv[2]);
});

const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        WidthType, BorderStyle, ShadingType } = require("docx");

const NAVY="1F3864", RED="A62B2B", GREEN="2E6B3E", GREY="5A5A5A", LINE="C9C9C9", BG="F2F4F7";
const F="맑은 고딕";
const t=(x,o={})=>new TextRun({text:x,font:F,size:o.size||20,bold:o.b,italics:o.i,color:o.c,break:o.br});
const p=(r,o={})=>new Paragraph({children:Array.isArray(r)?r:[r],
  spacing:{before:o.before??70,after:o.after??70,line:284},indent:o.indent,border:o.border});
const h1=(x)=>new Paragraph({children:[t(x,{size:28,b:true,c:NAVY})],
  spacing:{before:400,after:150},
  border:{bottom:{style:BorderStyle.SINGLE,size:12,color:NAVY,space:6}}});
const body=(x,o={})=>p(t(x,o));
const quote=(x)=>new Paragraph({children:[t(x,{i:true,c:GREY,size:19})],
  spacing:{before:100,after:120,line:266},indent:{left:340},
  border:{left:{style:BorderStyle.SINGLE,size:14,color:LINE,space:10}}});
const cell=(c,o={})=>new TableCell({width:{size:o.w||0,type:WidthType.PERCENTAGE},
  shading:o.bg?{type:ShadingType.CLEAR,fill:o.bg}:undefined,
  margins:{top:70,bottom:70,left:110,right:110},
  children:[new Paragraph({children:[t(c,{size:18,b:o.b,c:o.c})],spacing:{before:0,after:0,line:252}})]});
const table=(hd,rs,w)=>new Table({width:{size:100,type:WidthType.PERCENTAGE},
  borders:{top:{style:BorderStyle.SINGLE,size:6,color:LINE},
    bottom:{style:BorderStyle.SINGLE,size:6,color:LINE},
    left:{style:BorderStyle.NONE},right:{style:BorderStyle.NONE},
    insideHorizontal:{style:BorderStyle.SINGLE,size:4,color:LINE},
    insideVertical:{style:BorderStyle.NONE}},
  rows:[new TableRow({tableHeader:true,children:hd.map((h,i)=>cell(h,{b:true,c:NAVY,bg:BG,w:w[i]}))}),
    ...rs.map(r=>new TableRow({children:r.map((c,i)=>(c&&typeof c==="object")
      ? cell(c.v,{w:w[i],b:c.b,c:c.c}) : cell(c,{w:w[i]}))}))]});
const sp=()=>new Paragraph({children:[],spacing:{before:0,after:110}});

const k=[];
k.push(new Paragraph({children:[t("사라진 층",{size:42,b:true,c:NAVY})],spacing:{after:60}}));
k.push(new Paragraph({children:[t("KCI에서 L2 영향력 레이어가 제거된 것의 문제",{size:23,c:GREY})],spacing:{after:150}}));
k.push(new Paragraph({
  children:[t("2026-09 · KWCI 3레이어 모형과 KCI C·A·B 모형의 구조 비교",{size:17,c:GREY}),
    t("실측 근거: kwci/trade/data/processed/panel.csv (75품목 × 15개국 × 2018–2024)",{size:17,c:GREY,br:true})],
  spacing:{after:220},
  border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

k.push(h1("1. 무엇이 사라졌는가"));
k.push(body("KWCI는 한류를 세 층으로 나누어 쟀다. L1 경제는 수출과 관광수입, L3 수용자는 검색과 SNS 반응, 그리고 그 사이에 L2 영향력이 있었다. L2가 담당하던 것은 차트·랭킹·수상·팬덤 인프라 — 한 마디로 한류가 현지 사회에서 차지한 자리였다."));
k.push(p([t("KCI는 이 체계를 버리고 관심을 C(인지)·A(태도)·B(행동의도) 세 차원으로 재편했다. 표면적으로는 L3가 세분화된 것처럼 보이지만, 실제로 일어난 일은 다르다. "),
  t("C·A·B는 셋 다 개인 소비자의 행동이다.",{b:true}),
  t(" 검색하고, 댓글을 달고, 사려 한다. 개인의 머릿속과 손끝에서 일어나는 일이다.")]));
k.push(p([t("L2가 재던 것은 그런 것이 아니었다. 빌보드 1위, 칸 황금종려상, 넷플릭스 글로벌 Top10 진입, 현지 방송사 편성, 대형 유통 입점, 한류 동호회의 규모 — 이것들은 "),
  t("개인이 검색하지 않아도 존재하며, 오히려 검색을 만들어내는 쪽",{b:true,c:NAVY}),
  t("에 있다. 발표자료가 네 통찰 중 하나로 세웠던 “위상 대 행동”의 구분에서, KCI에는 행동만 남았다.")]));
k.push(body("사라진 것은 하나의 데이터 소스가 아니라 하나의 인과적 지위다. 원인 쪽에 있던 변수가 모형에서 통째로 빠졌다."));

k.push(h1("2. 한류 수용은 도메인이 아니라 국가 단위로 움직인다"));
k.push(body("L2를 폐기할 때 가장 자주 지적되는 결함은 그것이 도메인을 구분하지 못한다는 점이다. KWCI의 구현에서 L2는 국가 단위로 정규화되어 모든 장르 행에 같은 값으로 병합되었다. 도메인별 차이가 없는 층을 도메인별 지수에 넣는 것은 분명 이상해 보인다."));
k.push(p([t("그러나 이 판단은 “도메인마다 다른 수용층이 있다”는 가정 위에 서 있다. 그 가정은 검정된 적이 없다. 그래서 L1 패널로 직접 확인했다 — 세 소비재 도메인의 "),
  t("국가별 수출 구성비가 서로 얼마나 닮았는가",{b:true}),t(".")]));
k.push(sp());
k.push(table(["연도","도메인 쌍","피어슨","스피어만"],
  [["2018","K-Food × K-Beauty","0.784","0.950"],
   ["2018","K-Food × K-Fashion","0.687","0.825"],
   ["2018","K-Beauty × K-Fashion","0.428","0.839"],
   [{v:"2024",b:true},{v:"K-Food × K-Beauty",b:true},{v:"0.987",b:true,c:RED},{v:"0.961",b:true,c:RED}],
   [{v:"2024",b:true},{v:"K-Food × K-Fashion",b:true},{v:"0.942",b:true,c:RED},{v:"0.925",b:true,c:RED}],
   [{v:"2024",b:true},{v:"K-Beauty × K-Fashion",b:true},{v:"0.940",b:true,c:RED},{v:"0.907",b:true,c:RED}]],
  [12,40,24,24]));
k.push(sp());
k.push(p([t("2024년 세 쌍 모두 피어슨 0.94 이상이다. 라면을 많이 사는 나라가 화장품도 많이 사고 옷도 많이 산다. 더 중요한 것은 "),
  t("이 상관이 6년 사이에 크게 올랐다는 사실",{b:true,c:NAVY}),
  t("이다 — 2018년 0.43~0.78에서 2024년 0.94~0.99로. 도메인 간 국가 구조가 시간이 갈수록 수렴하고 있다.")]));
k.push(sp());
k.push(table(["도메인","2024년 상위 5개국"],
  [["K-Food","CN 27%   US 25%   JP 15%   VN 8%   TH 6%"],
   ["K-Beauty","CN 34%   US 26%   JP 15%   VN 7%   TW 4%"],
   ["K-Fashion","CN 28%   US 23%   VN 18%   JP 14%   TW 5%"]],[18,82]));
k.push(sp());
k.push(p([t("상위 4개국이 사실상 동일하다. 이것이 뜻하는 바는 분명하다. "),
  t("K-pop 팬과 K-beauty 소비자와 한식당 손님은 대체로 같은 사람들이거나 같은 사회적 층이다.",{b:true}),
  t(" 도메인별로 분리된 수용층이 있는 것이 아니라, 하나의 한류 관심층이 여러 도메인을 가로질러 소비한다.")]));
k.push(p([t("그렇다면 "),t("국가 단위로 측정되는 층이 존재하는 것은 결함이 아니라 구조의 반영",{b:true,c:GREEN}),
  t("이다. L2가 도메인을 구분하지 않는다는 사실은, 구분할 것이 실제로 적다는 뜻일 수 있다. 이 층을 없애면 도메인 횡단적 수용이라는 한류의 핵심 성질을 잴 자리가 사라진다.")]));

k.push(h1("3. 검색은 유량이고 팬덤은 존량이다"));
k.push(body("KCI 보고서가 답하지 못한 문제가 하나 있다. 영상·음악·웹툰에서 관심과 수출의 부호가 역전된다."));
k.push(quote("무작위형(영상·음악·웹툰 — 성숙기 검색 하락 vs 가입 기반 매출 증가) / 곡선의 어긋남은 지수 실패인가? 소비 구조의 정직한 반영인가?"));
k.push(p([t("답의 후보 하나는 L2의 부재다. "),t("검색량은 신규 유입의 지표이지 존량의 지표가 아니다.",{b:true,c:NAVY}),
  t(" 이미 팬인 사람은 검색하지 않는다. 드라마를 처음 접한 사람은 제목을 검색하지만, 3년째 구독 중인 사람은 앱을 열 뿐이다. 시장이 성숙할수록 검색은 줄고 매출은 는다.")]));
k.push(p([t("L2가 재던 것 — 팬덤 규모, 차트 체류 주수, 구독자 수, 동호회 회원 — 은 "),
  t("존량",{b:true}),t("이다. 성숙 시장에서는 존량 지표가 유량 지표보다 정확하다.")]));
k.push(p([t("C·A·B는 셋 다 유량이다. 검색도 댓글도 그 주에 일어난 행동이다. "),
  t("KCI에는 존량을 재는 차원이 없다.",{b:true,c:RED}),
  t(" 8개 산업 중 3개에서 부호가 역전된 것이 우연이 아닐 수 있다. 그리고 그 3개가 하필 구독형 — 존량이 매출을 결정하는 산업 — 이라는 점이 이 해석을 지지한다.")]));

k.push(h1("4. 정책이 손댈 수 있는 지점이 사라졌다"));
k.push(body("이 연구는 문화체육관광부 발주다. 지수의 용도에는 진단만이 아니라 개입 설계가 포함된다."));
k.push(p([t("그런데 "),t("정책 수단은 거의 전부 L2 쪽에 있다.",{b:true,c:NAVY}),
  t(" 정부가 외국인 개인의 검색을 직접 늘릴 방법은 없다. 그러나 현지 쇼케이스를 열고, 방송 편성을 지원하고, 대형 유통 입점을 주선하고, 국제 시상식 출품을 돕고, 문화원을 운영하는 것은 할 수 있다. 이것들은 전부 위상을 만드는 일이며 L2의 내용물이다.")]));
k.push(p([t("KCI는 “관심이 오르면 수출이 오른다”까지는 말한다. 그러나 "),
  t("“관심을 어떻게 올리는가”는 모형 밖에 있다.",{b:true,c:RED}),
  t(" 관심은 좌변의 출발점으로 주어질 뿐, 무엇이 그것을 만드는지는 설명되지 않는다. 정책 담당자 입장에서 이 지수는 온도계이지 조절기가 아니다.")]));
k.push(body("L2가 층으로 남아 있었다면 “차트 성과가 오르면 관심이 오르고 관심이 오르면 수출이 오른다”는 2단 경로를 검정할 수 있었다. 그 경로의 앞단이 정책 개입 지점이다. 지금은 앞단이 없다."));

k.push(h1("5. 신호가 하나 죽으면 셀이 죽는다"));
k.push(p([t("KWCI의 결측 재정규화는 비판받을 설계다. 한 층이 비면 남은 층의 가중을 늘려 지수를 산출하므로, 실효 가중이 설계값과 달라진다. 그러나 그 설계에는 "),
  t("한 층이 죽어도 지수가 나온다",{b:true}),t("는 성질이 있었다.")]));
k.push(p([t("KCI의 좌변은 Google Trends와 YouTube 댓글 둘뿐이다. 이 둘이 막히면 "),
  t("셀이 통째로 죽는다.",{b:true,c:RED}),
  t(" 실제로 40셀 중 5셀이 산출되지 못했고, 사우디아라비아는 바구니의 39%가 저신호로 공시 처리되었다.")]));
k.push(p([t("가장 심각한 것은 중국이다. Google과 YouTube가 모두 차단된 시장이라 "),
  t("KCI로는 중국을 측정할 방법이 없다",{b:true,c:RED}),
  t("(Baidu·Bilibili 구축은 차기 과제로 남아 있다). 그런데 §2의 표가 보여주듯 중국은 K-Food 27%, K-Beauty 34%, K-Fashion 28%로 세 도메인 모두에서 최대 시장이다.")]));
k.push(p([t("L2 계열의 지표 — 현지 팬덤 규모, 플랫폼 랭킹, 유통 입점 수 — 는 "),
  t("중국에서도 관측 가능하다.",{b:true,c:GREEN}),
  t(" 웨이보 팬덤 규모, 아이치이 랭킹, 현지 화장품 유통 데이터는 존재한다. L2를 유지했다면 검색이 막힌 시장에서 대체 신호로 기능할 수 있었다. 지금 구조에서는 최대 시장이 구조적 결측이다.")]));

k.push(h1("6. 사라진 것이 아니라 우변으로 옮겨갔다"));
k.push(body("더 근본적인 문제가 있다. L2는 모형에서 제거된 것이 아니라 위치를 옮겼다."));
k.push(sp());
k.push(table(["산업","KCI 우변(수출 준거)의 구성","원래 무엇이었나"],
  [["영상",{v:"ECOS 총액 × Netflix Top10 소비 변조",c:RED},{v:"KWCI L2 — 플랫폼 랭킹",b:true}],
   ["게임·웹툰",{v:"콘진원 총액 × Google Play 앱 순위 변조",c:RED},{v:"KWCI L2 — 플랫폼 랭킹",b:true}]],
  [14,48,38]));
k.push(sp());
k.push(p([t("넷플릭스 Top10 체류 주수와 앱 순위는 KWCI에서 L2의 정의 그 자체였다. KCI는 이것을 층에서 빼놓고 "),
  t("수출 준거의 구성 요소로 집어넣었다.",{b:true,c:RED}),
  t(" 그 결과 “관심 → 수출”로 해석되는 β가 실제로는 “관심 → 플랫폼 랭킹”을 재고 있을 수 있다.")]));
k.push(p([t("이것은 보고서가 스스로 금지한 순환에 해당한다 — 좌변은 Google Trends 검색이고, 앱 순위는 다운로드로 만들어지며, 다운로드는 검색을 경유한다. "),
  t("우변이 좌변의 함수를 포함한다.",{b:true,c:RED})]));
k.push(p([t("L2를 명시적인 층으로 두었다면 이 혼입이 표에 드러났을 것이다. 층을 없애면서 "),
  t("혼입도 함께 보이지 않게 되었다.",{b:true}),
  t(" 제거가 아니라 은폐에 가깝다.")]));

k.push(h1("7. 대체물이 더 낫다는 증거가 아직 없다"));
k.push(p([t("L2 폐기를 정당화하는 논거는 대체로 이렇다. L1·L2·L3는 자료 출처로 나눈 층위여서 가중합의 의미가 불분명한 반면, C·A·B는 하나의 잠재변수를 깊이별로 나눈 것이므로 합성이 해석을 갖는다는 것이다. "),
  t("이 논거는 위계가 실재할 때만 성립한다.",{b:true,c:NAVY})]));
k.push(body("인지에서 태도로, 태도에서 행동의도로 이어지는 위계효과 모형은 마케팅에서 오래된 비판 대상이다. 저관여 상황에서는 행동이 태도보다 먼저 오고, 태도는 사후에 합리화된다. 한류 소비재의 상당 부분 — 편의점에서 집은 라면, 추천 알고리즘이 띄운 드라마 — 은 저관여 소비에 가깝다."));
k.push(p([t("게다가 C와 B는 같은 원천(Google Trends)에서 쿼리 목록만 달리한 계열이다. 두 차원이 독립적이라는 보장이 없고, 보고서 스스로 한계에 “검색 대 반응의 가중치는 0 또는 1로 선택의 문제”라고 적었다. "),
  t("위계가 데이터로 확인된 바 없다.",{b:true,c:RED})]));
k.push(body("위계가 성립하지 않는다면 C·A·B도 결국 세 개의 서로 다른 측정을 가중합한 것이며, 그 점에서 L1·L2·L3와 구조적으로 같아진다. 낡은 3층을 버리고 새 3층을 세웠는데, 새 3층이 더 낫다는 증거가 아직 제시되지 않았다."));

k.push(h1("8. 무엇을 해야 하는가"));
k.push(body("L2의 부활을 주장하려는 것이 아니다. KWCI의 L2 구현은 자료원이 하나뿐이었고 실효 가중이 설계값을 크게 넘었으며 도메인 해상도가 없었다. 그 구현을 그대로 되살릴 이유는 없다."));
k.push(p([t("문제는 "),t("구현의 부실을 이유로 개념까지 함께 버렸다는 점",{b:true,c:NAVY}),
  t("이다. 존량, 위상, 정책 개입 지점, 검색이 막힌 시장의 대체 신호 — 이 넷은 모두 C·A·B가 담당하지 못하는 자리이며, 지금 모형에 비어 있다.")]));
k.push(body("다음 세 검정이 이 문제를 논쟁이 아니라 측정으로 정리한다. 셋 모두 추가 데이터 구매 없이 기존 자료로 수행된다."));
k.push(sp());
k.push(table(["검정","설계","판정 기준"],
  [[{v:"1. 국가 단위성",b:true},"L1 패널에서 도메인 간 국가 구성비 상관을 산출(본문 §2에서 수행)",
    {v:"2024년 0.94~0.99 — 국가 단위 층의 정당성 확인됨",c:GREEN}],
   [{v:"2. 존량 효과",b:true},"영상·음악·웹툰에서 C·A·B에 존량 대리변수(팬덤 규모·구독자 수) 하나를 추가해 β 재추정",
    "부호 역전이 해소되면 L2 부재가 원인"],
   [{v:"3. 우변 혼입",b:true},"게임·웹툰·영상 준거에서 플랫폼 랭킹 변조를 제거한 판본으로 β 재산출",
    "β가 무너지면 현재 β는 “관심 → 플랫폼 랭킹”이었던 것"]],
  [16,50,34]));
k.push(sp());
k.push(p([t("검정 1은 이미 답이 나왔다. 한류 소비는 도메인이 아니라 국가 단위로 묶이며, 그 경향은 강해지고 있다. "),
  t("국가 단위 위상 층을 되살리되, 자료원을 복수로 두고 도메인 해상도를 확보하는 것이 합리적 방향",{b:true,c:NAVY}),
  t("이다. 빌보드·스포티파이·넷플릭스·스팀은 KWCI 해설서가 이미 L2의 확장 후보로 적어두었던 것들이다. 그것들을 좌변의 독립적인 층으로 복원하면, 지금 우변에 섞여 들어간 혼입도 함께 해소된다.")]));
k.push(p([t("한 가지만 덧붙인다. 관심이 수출을 얼마나 선행하는지 묻는 것은 좋은 질문이다. 그러나 "),
  t("관심을 무엇이 만드는지 묻지 않는 지수는 진단할 수는 있어도 처방할 수 없다.",{b:true,c:NAVY}),
  t(" 정책 연구의 산출물로서 이 결손은 통계적 결손보다 무겁다.")]));

k.push(new Paragraph({
  children:[t("본 분석의 §2 수치는 kwci/trade/data/processed/panel.csv(75품목 × 15개국 × 2018–2024, 관세청 실측)로 산출했다. 도메인별 국가 구성비를 연도별로 구해 도메인 쌍 간 피어슨·스피어만 상관을 계산한 값이다.",{size:16,c:GREY})],
  spacing:{before:340},
  border:{top:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

const doc=new Document({styles:{default:{document:{run:{font:F,size:20}}}},
  sections:[{properties:{page:{margin:{top:1000,bottom:1000,left:1000,right:1000}}},children:k}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(process.argv[2],b);
  console.log("= "+process.argv[2]+"  "+(b.length/1024).toFixed(0)+" KB");});

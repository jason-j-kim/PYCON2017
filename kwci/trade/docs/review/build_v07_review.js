const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        WidthType, BorderStyle, ShadingType } = require("docx");

const NAVY="1F3864", RED="A62B2B", GREEN="2E6B3E", AMBER="9A6A00",
      GREY="5A5A5A", LINE="C9C9C9", BG="F2F4F7";
const F="맑은 고딕";

const t=(x,o={})=>new TextRun({text:x,font:F,size:o.size||20,bold:o.b,italics:o.i,color:o.c,break:o.br});
const p=(r,o={})=>new Paragraph({children:Array.isArray(r)?r:[r],
  spacing:{before:o.before??70,after:o.after??70,line:280},indent:o.indent,border:o.border});
const h1=(x)=>new Paragraph({children:[t(x,{size:28,b:true,c:NAVY})],
  spacing:{before:400,after:150},
  border:{bottom:{style:BorderStyle.SINGLE,size:12,color:NAVY,space:6}}});
const h2=(x,c)=>new Paragraph({children:[t(x,{size:23,b:true,c:c||NAVY})],
  spacing:{before:280,after:100}});
const body=(x,o={})=>p(t(x,o));
const quote=(x)=>new Paragraph({children:[t(x,{i:true,c:GREY,size:19})],
  spacing:{before:100,after:120,line:266},indent:{left:340},
  border:{left:{style:BorderStyle.SINGLE,size:14,color:LINE,space:10}}});
const fix=(x)=>new Paragraph({children:[t("권고  ",{b:true,c:GREEN,size:19}),t(x,{size:19})],
  spacing:{before:110,after:150,line:272},indent:{left:240},
  border:{left:{style:BorderStyle.SINGLE,size:14,color:GREEN,space:10}}});
const mono=(x)=>new Paragraph({children:[t(x,{size:17,c:GREY,font:"D2Coding"})],
  spacing:{before:60,after:90,line:250},indent:{left:280}});
const cell=(c,o={})=>new TableCell({width:{size:o.w||0,type:WidthType.PERCENTAGE},
  shading:o.bg?{type:ShadingType.CLEAR,fill:o.bg}:undefined,
  margins:{top:70,bottom:70,left:110,right:110},
  children:[new Paragraph({children:[t(c,{size:18,b:o.b,c:o.c})],
    spacing:{before:0,after:0,line:252}})]});
const table=(hd,rs,w)=>new Table({width:{size:100,type:WidthType.PERCENTAGE},
  borders:{top:{style:BorderStyle.SINGLE,size:6,color:LINE},
    bottom:{style:BorderStyle.SINGLE,size:6,color:LINE},
    left:{style:BorderStyle.NONE},right:{style:BorderStyle.NONE},
    insideHorizontal:{style:BorderStyle.SINGLE,size:4,color:LINE},
    insideVertical:{style:BorderStyle.NONE}},
  rows:[new TableRow({tableHeader:true,
      children:hd.map((h,i)=>cell(h,{b:true,c:NAVY,bg:BG,w:w[i]}))}),
    ...rs.map(r=>new TableRow({children:r.map((c,i)=>(c&&typeof c==="object")
      ? cell(c.v,{w:w[i],b:c.b,c:c.c}) : cell(c,{w:w[i]}))}))]});
const sp=()=>new Paragraph({children:[],spacing:{before:0,after:110}});

const k=[];

// ── 표지
k.push(new Paragraph({children:[t("KCI 중간보고서 심사의견",{size:38,b:true,c:NAVY})],spacing:{after:60}}));
k.push(new Paragraph({children:[t("「K-Culture Index 개발 및 실증 연구」 v07 에 대한 동료심사",{size:22,c:GREY})],spacing:{after:150}}));
k.push(new Paragraph({
  children:[
    t("심사 대상: 중간보고서 v07 (2026.09) 본문·부록 A~E, 251,671자 · 표 34개",{size:17,c:GREY}),
    t("대조 자료: 함께 제출된 kci_dashboard.html (kci_p2_shared, 2026-09-12 생성) 내장 데이터 3벌 — EXP 8,039행 · SIG 9,905행 · SVE 8,039행",{size:17,c:GREY,br:true}),
    t("본 의견의 모든 실측 수치는 위 대시보드 내장 데이터를 심사자가 직접 재계산한 값이다.",{size:17,c:GREY,br:true}),
  ],
  spacing:{after:200},
  border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

// ── 총평
k.push(h1("총평"));
k.push(p([t("본 보고서는 제2장에서 자기 방법의 한계를 다섯 항목으로 자인하고 각각에 방어책을 붙였다. 방법론 문헌에 대한 이해와 자기 검토의 수준이 이 분야의 통상적 보고서를 상회한다. 그러나 "),
  t("제2장이 세운 기준이 제4장의 결과 보고와 부록의 실제 사전에 적용되지 않았다.",{b:true,c:RED}),
  t(" 본 심사가 지적하는 결함의 다수는 새로운 문제가 아니라, 보고서가 이미 인지하고 서술한 원칙을 스스로 지키지 않은 데서 발생한다.")]));
k.push(p([t("가장 무거운 것은 둘이다. 첫째, 대표 결론인 “8산업 β 전부 양수”는 비음수 최소제곱의 제약이지 데이터의 발견이 아니며, 이 사실은 제2장에 명시되어 있다. 둘째, 웹툰의 국가별 준거는 횡단 변동이 "),
  t("정확히 0",{b:true,c:RED}),
  t("인데 표 4.2는 이를 “국가층에서 정방향 성립”으로 판정한다. 두 항목은 결과의 지위를 직접 좌우하므로 수정 전에는 인용을 권하지 않는다.")]));
k.push(p([t("아래 지적은 다섯 묶음 열여섯 항목이다. 각 항목은 문제·근거·권고의 순으로 기술한다. "),
  t("실증에 관한 네 항목(C-1, C-2, C-3, D-1)은 추가 자료 구매 없이 기존 자료의 재분석만으로 해소된다.",{b:true})]));

// ══ A
k.push(h1("A. 설계 규칙과 실제 사전의 불일치"));

k.push(h2("A-1. C 차원 선정 기준이 D3 사전에서 지켜지지 않는다",RED));
k.push(body("제2장은 C 차원 토픽의 선정 기준을 세 가지로 규정한다. 그 셋째는 다음과 같다."));
k.push(quote("셋째, 값이 안정적이고 뜻이 하나여야 한다. … 신곡이나 새 시즌 주기로 출렁이는 인물·작품 토픽보다 개념 토픽을 우선한다."));
k.push(body("그러나 부록 B3 의 D3 등재 목록은 이 기준과 반대다."));
k.push(sp());
k.push(table(["산업","C 토픽 구성","개념 토픽 비율"],
  [[{v:"GAME",b:true},"PUBG · 검은사막 · Stellar Blade · First Descendant · Lost Ark · Dave the Diver · LCK · LoL Worlds · Faker · Gen.G 등",{v:"0 / 12",b:true,c:RED}],
   ["MUSIC","BTS · BLACKPINK · Korean idol","1 / 3"],
   ["VIDEO","K-drama · Parasite · Crash Landing on You · Squid Game","1 / 4"]],[12,60,28]));
k.push(sp());
k.push(p([t("게임 산업의 C 차원에는 개념 토픽이 "),t("하나도 없다",{b:true,c:RED}),
  t(". 규정과 실행이 정면으로 어긋난다.")]));
k.push(fix("규정을 개정하거나 사전을 개정하거나 하나를 택해야 한다. 후자를 권고한다. 게임에 Korean game·K-game 등 개념 토픽을 프로브하여 등재하고, IP 토픽은 민감도 분석용 보조층으로 강등한다. 전자를 택할 경우 제2장 셋째 기준을 “IP 우선”으로 개정하고 그 이론적 근거를 제시해야 한다."));

k.push(h2("A-2. 바스켓 크기 규정을 세 산업이 위반한다",RED));
k.push(body("제2장은 바스켓 규모를 규정한다 — “산업당 3~7개의 바스켓으로 묶고”. 실제 등재 수는 다음과 같다."));
k.push(mono("GAME 12종  ← 상한 초과\nFOOD 7 · TOURISM 4 · VIDEO 4 · FASHION 4 · MUSIC 3\nWEBTOON 2종  ← 하한 미달\nBEAUTY 1종  ← 하한 미달"));
k.push(p([t("뷰티의 C 차원이 단일 토픽 K-beauty 하나다. 뷰티는 표 4.1 에서 “양호” 판정을 받은 산업이다. "),
  t("단일 토픽은 바스켓이 아니며, 해당 토픽에 분류 오류가 있을 경우 산업 전체가 무효가 된다.",{b:true})]));
k.push(fix("뷰티 C 에 Korean skincare·glass skin·Korean makeup 을 프로브하여 최소 3종을 확보하고, 웹툰 C 에 K-webtoon·Korean comics 를 추가한다. 게임은 12종을 7종으로 축소하되 탈락 기준(프로브 nonzero 비율 등)을 명문화한다."));

k.push(h2("A-3. 우변 최대 품목에 대응하는 좌변 토픽이 부재한다",AMBER));
k.push(body("제2장의 둘째 기준은 정확하다."));
k.push(quote("라면(ramen)은 검색자 대부분이 일본 음식으로 인식하므로 부적격이며, 대신 ramyeon이나 buldak처럼 한국 귀속이 분명한 표현을 쓴다."));
k.push(p([t("그러나 D3 의 FOOD C 에 ramyeon 이 없고 브랜드 토픽 Buldak 만 있다. "),
  t("라면(HS 1902.30)은 K-Food 수출의 최대 품목이다.",{b:true}),
  t(" 우변의 1위 품목이 좌변에서 단일 브랜드로만 대표되면, 해당 브랜드의 점유율 변동이 품목 전체의 관심 변동으로 오인된다.")]));
k.push(fix("ramyeon 토픽 ID 를 프로브하여 존재 시 등재하고 부재 시 Korean instant noodles 를 키워드층에 둔다. 아울러 부록에 「우변 준거 상위 품목 × 좌변 토픽 대응표」를 신설한다. 현재 문서로는 좌우변이 무엇으로 연결되는지 확인할 수 없다."));

k.push(h2("A-4. FASHION C 의 Fila 는 문화 신호가 아니다",RED));
k.push(mono("FASHION  C  Fila /m/0_vw_y6  태그 kr-owned  채택 5국"));
k.push(p([t("kr-owned 는 "),t("소유 구조",{b:true}),
  t("를 표시할 뿐 문화 귀속을 보증하지 않는다. Fila 는 이탈리아 태생 브랜드이며 전 세계 검색의 대다수는 한국 문화와 무관한 스포츠웨어 수요다. 이는 제2장 둘째 기준 — “검색하는 사람이 그 대상을 한국과 연결해야 한다” — 에 저촉된다. "),
  t("ramen 을 배제한 논리를 Fila 에는 적용하지 않았다.",{b:true,c:RED})]));
k.push(fix("Fila 제외 판본의 패션 β 를 병기한다. 두 값이 유의하게 다르면 사전에서 제외하고, 같으면 kr-owned 태그 전체를 민감도 분석 항목으로 명시한다."));

k.push(h2("A-5. TOURISM C 가 맨 지명이며 가중 68%를 점한다",RED));
k.push(mono("TOURISM  C  Busan · Seoul · Jeju Island · Gyeongbokgung Palace"));
k.push(body("지명 단독 검색은 뉴스·정치·스포츠·재난 관련 검색을 포함한다. 부산은 영화제·엑스포 유치 보도로 여행 수요와 무관하게 급등한다."));
k.push(quote("왜 관광 지수에서 C가 68%인가 — 관광객 수를 가장 잘 설명하는 비율이기 때문"));
k.push(p([t("8산업 중 "),t("유일한 ‘신뢰’ 판정 산업의 가중 3분의 2가 맨 지명 검색에 실려 있다.",{b:true,c:RED}),
  t(" 더구나 지명 검색과 입국자 수는 모두 “해당국의 한국 관련 뉴스 노출”에 동시 반응할 수 있으므로, 높은 설명력이 인과가 아니라 공통 원인의 소산일 가능성을 배제하지 못한다.")]));
k.push(fix("Seoul travel·ソウル 旅行 등 의도어를 결합한 계열로 C 를 재구성하여 β 를 재추정한다. 값이 유지되면 지명 단독도 무방하나, 하락하면 현행 관광 β 는 뉴스 노출을 측정한 것이다. 관광이 유일한 통과 산업이므로 이 재추정은 보고서 전체의 실증 근거를 좌우한다."));

// ══ B
k.push(h1("B. 결과 보고의 내적 모순"));

k.push(h2("B-1. 동일 산업에 세 가지 판정이 병존한다",RED));
k.push(sp());
k.push(table(["위치","영상·웹툰","식품","패션·음악"],
  [["Executive Summary",{v:"재검토",b:true},{v:"(누락)",c:RED},"보류"],
   ["표 4.1",{v:"공시(부호 역전)",b:true},"경계(국가층 참조)",{v:"경계",b:true}],
   ["표 4.2",{v:"통과(국가층)",b:true,c:RED},{v:"통과(국가층)",c:RED},{v:"보류",b:true}]],[26,28,24,22]));
k.push(sp());
k.push(p([t("영상·웹툰이 재검토·공시·통과로 갈린다. 식품은 Executive Summary 의 판정 목록에서 누락되었는데, 해당 산업은 "),
  t("β 0.00006 · r² .01 로 8산업 중 최약",{b:true,c:RED}),t("이다.")]));
k.push(fix("판정 어휘를 4단계(통과·조건부통과·보류·공시)로 고정하고 세 위치를 통일한다. 표 4.1 과 표 4.2 를 단일 표로 통합하는 것이 가장 안전하다."));

k.push(h2("B-2. 표 4.1 의 열 제목과 내용이 다른 트랙에 속한다",AMBER));
k.push(body("표 4.1 의 계수 열은 β_CUL 이나, 판정 열에 “부호 역전”이 기재되어 있다. 제2장에 따르면 β_CUL 은 비음수 제약으로 음수가 될 수 없다."));
k.push(quote("부호 제약은 CUL 트랙의 가중 추정에만 걸고 대조 트랙(PRD)의 β 추정에는 부호를 열어 두어"));
k.push(body("즉 부호 역전은 β_PRD 의 성질인데 β_CUL 열에 표기되어 있다. 독자는 β_CUL 이 역전된 것으로 읽는다."));
k.push(fix("표 4.1 에 β_PRD·k_PRD 열을 추가하여 두 트랙을 병렬 제시하고, 부호 역전은 PRD 열에만 표기한다."));

k.push(h2("B-3. PRD 트랙의 지위가 제2장과 제4장에서 상반된다",RED));
k.push(quote("제2장: 파생 지표(전환 감쇠비 β_CUL/β_PRD와 시차차 k_CUL − k_PRD)의 세 기능은 데이터는 수집하되 분석여부는 추후 결정한다"));
k.push(quote("제4장: 관광은 … 전환 감쇠비 1.69로 관심 1단위가 구매 1단위의 약 1.7배로 방한객을 설명하여 /  표 4.2 판정 근거: 양 트랙 β 양수·유의"));
k.push(p([t("분석 여부가 미정인 트랙의 산출물이 "),t("이미 판정 근거로 사용되고 있다.",{b:true,c:RED})]));
k.push(fix("제2장의 “추후 결정” 문장을 삭제하고 PRD 를 정식 분석 대상으로 승격하거나, 제4장의 전환감쇠비·시차차를 잠정 표기로 강등한다. 양자택일이다."));

k.push(h2("B-4. 준거 등급 체계가 4등급과 5등급을 오간다",AMBER));
k.push(sp());
k.push(table(["위치","등급 체계"],
  [["제2장","KCS_HS / KTO / PROXY_MEASURED / PROXY_CONSUMPTION / SYNTH (5등급)"],
   ["제4장",{v:"KCS_HS / KTO / ECOS_PROXY / KOCCA_SYNTH (4등급)",c:RED}],
   ["부록 D","음악 proxy_measured / 영상 proxy consumption (5등급으로 복귀)"]],[16,84]));
k.push(sp());
k.push(body("제2장과 부록 D 는 음악과 영상을 다른 등급으로 구분하나 제4장은 양자를 ECOS_PROXY 로 통합한다. 등급 체계는 준거 신뢰도의 핵심 장치이므로 문서 내 동요는 허용되지 않는다."));
k.push(fix("5등급 체계로 고정하고 제4장 표기를 수정한다."));

// ══ C
k.push(h1("C. 추정 논리의 결함"));

k.push(h2("C-1. 대표 결론이 추정량의 제약이다",RED));
k.push(quote("제4장: 산업별 β_CUL은 모두 양수로 … 방향이 8산업에서 일관된다"));
k.push(quote("제2장: (4) 비음수 제약 … 사전 배제하며(Uhlig, 2005) / 셋째, 부호 제약이 진짜 음의 관계를 숨길 수 있다 … NNLS는 이를 0으로 눌러 “무관계”로 보고한다"));
k.push(p([t("β_CUL ≥ 0 은 비음수 최소제곱의 성질이지 데이터의 발견이 아니다. "),
  t("음수를 산출할 수 없는 추정량으로 부호 일관성을 보고하는 것은 항진명제다.",{b:true,c:RED}),
  t(" 보고서는 제2장에서 그 이유를 정확히 서술한 뒤 제4장에서 이를 결과로 제시한다.")]));
k.push(fix("“8산업 β 전부 양수”를 결론에서 삭제한다. 부호를 개방한 β_PRD 의 부호 분포를 대신 보고하면 방향성 주장이 성립한다. 제2장이 PRD 의 부호를 개방한 취지가 바로 이것이다."));

k.push(h2("C-2. 웹툰은 국가층이 부재한데 국가층을 근거로 통과 판정을 받았다",RED));
k.push(body("대시보드 내장 데이터로 전년동기 로그증가율의 국가 간 표준편차를 산출하였다."));
k.push(sp());
k.push(table(["산업","2022~2023 중앙값","2025~2026 중앙값"],
  [[{v:"webtoon",b:true},{v:"0.0000",b:true,c:RED},{v:"0.0164",c:RED}],
   ["game","0.1976","0.0971"],
   ["food","0.3408","0.3315"],
   ["fashion","0.6091","0.6591"]],[20,40,40]));
k.push(sp());
k.push(p([t("웹툰은 2022~2023 구간에서 "),t("15개국의 종속변수가 완전히 동일하다.",{b:true,c:RED}),
  t(" 국가 구성비를 추적한 결과 2021-01 ~ 2024-03 의 39개월 동안 단 하나의 구성비만 존재하며, 이후에도 분기 단위로만 변화한다(게임도 동일).")]));
k.push(quote("부록 D3: 국가별 월간 배분율은 … 구글플레이 국가별 매출 순위에서 … 자국 연평균 대비 상대 변동을 변조 계수로 삼아"));
k.push(p([t("문서가 기술한 월간 변조가 데이터에 존재하지 않는다. 한국 웹툰 앱이 다수 국가의 매출 순위권에 진입하지 못하여 변조 계수가 1 로 고정된 것으로 추정된다.")]));
k.push(p([t("함의는 중대하다. 웹툰의 국가별 계열은 전국 총액에 상수를 곱한 값이므로 "),
  t("횡단 정보가 0",{b:true,c:RED}),
  t("이다. 15개국 패널이라 하나 실질 표본은 시계열 하나이며, 명목 자유도가 15배 팽창한다. HAC 표준오차로는 교정되지 않고 국가 클러스터링을 적용하여도 유효 횡단 표본은 1 이다.")]));
k.push(p([t("그럼에도 표 4.2 는 웹툰을 “통과(국가층) — 영어권 국가층에서 정방향 성립”으로 판정한다. "),
  t("존재하지 않는 국가층을 근거로 통과 판정을 내린 것이다.",{b:true,c:RED})]));
k.push(fix("① 5국 파일럿 웹툰·게임의 국가 간 증가율 분산을 즉시 확인하고, 0 이면 해당 β 를 철회하여 “국가별 준거 부재로 산출 불가”로 표기한다. ② 변조 계수가 1 로 고정된 셀·월을 플래그로 노출한다. 현재는 합성 결과만 제시되고 변조 작동 여부가 확인되지 않는다. ③ 앱 순위가 부재한 국가는 결측으로 처리한다. 앵커만으로 값을 생성하면 자료가 존재한다는 착시를 유발한다."));

k.push(h2("C-3. 성과준거 가중이 등가중과 구별되는지 검정되지 않았다",RED));
k.push(body("제2장은 성과준거 가중을 본 연구의 방법론적 기여로 제시한다."));
k.push(quote("가중의 근거를 “왜 관광 지수에서 C가 68%인가 — 관광객 수를 가장 잘 설명하는 비율이기 때문”으로 한 줄에 답할 수 있다"));
k.push(body("그러나 동 장의 한계 다섯째는 다음과 같다."));
k.push(quote("추정 창(수년)의 유효 자유도 제약으로 가중치가 등가중과 통계적으로 구별되지 않을 수 있으며, 이 경우 축소 추정이 등가중을 채택하는 것은 결함이 아니라 정직한 판정이다"));
k.push(p([t("해당 검정의 결과가 문서 어디에도 제시되지 않았다. 68%가 33%와 구별되지 않으면 위 “한 줄 답변”은 성립하지 않으며 "),
  t("연구의 핵심 기여가 무력화된다.",{b:true,c:RED}),
  t(" 축소 강도 λ 의 실제 값도 보고되지 않았다.")]));
k.push(fix("산업별로 ① 추정 w, ② 축소 후 w, ③ λ 값, ④ 등가중 대비 표본외 개선 여부를 단일 표로 제시한다. λ 가 큰 산업은 “데이터가 가중을 결정하지 못하였다”고 명시한다. 이는 결함의 고백이 아니라 정직한 보고이며, 보고서 자신이 그렇게 규정하였다."));

// ══ D
k.push(h1("D. 측정 인프라의 미검증"));

k.push(h2("D-1. A 차원 백필이 44%이며 그 결과 측정 정의가 시간에 따라 변한다",RED));
k.push(quote("제4장: 백필은 1,698개 수집 단위로 계획되어 2026년 8월 26일 현재 약 44%(≈747단위)가 완료"));
k.push(body("대시보드 신호 데이터에서 연도별 차원 가용률을 산출하였다."));
k.push(sp());
k.push(table(["연도","C","A","B","S"],
  [["2021","100%",{v:"83%",c:RED},"68%","95%"],
   ["2023","100%",{v:"86%",c:RED},"68%","95%"],
   ["2024","100%",{v:"95%",b:true},"68%","95%"],
   ["2026","100%",{v:"95%",b:true},"68%","95%"]],[20,20,20,20,20]));
k.push(sp());
k.push(p([t("A 가용률이 2021년 83%에서 2024년 이후 95%로 상승한다. 제2장의 부분창 재정규화 규정에 따르면 A 결측 주는 C·B 만으로 재정규화되므로, "),
  t("시계열 전반부는 2차원 합성, 후반부는 3차원 합성이다.",{b:true,c:RED}),
  t(" 즉 측정 정의가 시간에 따라 변한다. 12개월 차분을 적용하면 차원 구성이 상이한 두 시점을 차감하게 된다.")]));
k.push(body("보고서 자신이 동일한 원칙을 표집오차 게이트에 대해 세웠다 — “장치의 탈착 자체가 측정 정의의 변경으로서 시계열 일관성을 해치는 것을 방지하려는 조치”. 게이트에 그만한 주의를 기울이면서 A 차원의 시간 의존적 유무는 훨씬 큰 동일 문제를 야기한다."));
k.push(fix("세 방안 중 하나를 택한다. ① 백필 완료까지 β 추정을 보류하고 완료 후 재산출한다(가장 엄정). ② A 를 제외한 C·B 2차원 판본으로 전 구간을 재추정하여 현행 결과와 병기한다(백필과 무관하게 즉시 가능). ③ 최소한 kci_dims 플래그를 연도별 가용률 표로 공표하고 차원 구성 전환 구간을 도표에 표시한다. ②를 권고한다. 두 판본의 β 가 일치하면 결과는 백필 진도와 무관하게 성립하고, 불일치하면 현행 β 는 백필 진도를 측정한 것이다."));

k.push(h2("D-2. B 차원이 24셀에서 전무한데 그 구조가 보고되지 않았다",AMBER));
k.push(mono("차원별 관측   C 9,905   A 8,907   B 6,710   S 9,443   (총 9,905행)"));
k.push(p([t("B 는 68%에서 고정되어 있다. 시간이 아니라 셀 구조의 문제다. 브라질·독일은 대부분 산업에서 B 가 존재하지 않는다. B 는 제2장이 “문화 경험을 실행하려는 의도”로 정의한 차원이며 CUL→PRD 전환 논증의 중간 고리다. "),
  t("그것이 3분의 1 결측인데 셀별 가용표가 제시되지 않았다.",{b:true})]));
k.push(fix("국가 × 산업 80셀의 차원 가용 행렬을 부록에 신설한다. B 결측 셀의 KCI 는 실질적으로 C·A 합성이므로 타 셀과 동일 축에 배치할 수 없다."));

k.push(h2("D-3. 수집 방식 전환의 무해성을 단일 셀로 주장한다",AMBER));
k.push(quote("전환 전후 모두 표본이 있는 US_TOURISM에서 긍정률 격차 −0.002, 의도율 −0.001로 표집 영향이 무시 가능함을 실측했다"));
k.push(p([t("40셀 중 1셀이며, 그것도 신호가 가장 두꺼운 셀이다. "),
  t("검색 방식 변경의 영향은 저신호 셀에서 더 크다",{b:true}),
  t(" — 영상 탐색 방식이 바뀌면 결과 상위가 달라지고, 표본이 얇을수록 그 영향이 잔존한다.")]));
k.push(fix("병행 표본이 존재하는 셀 전수에서 격차를 측정하고, 셀의 주간 관측 수 대비 격차를 산점도로 제시한다. 저신호 셀에서 격차가 확대되는 경향이 관측되면 해당 셀에 보정을 도입해야 한다."));

k.push(h2("D-4. 링크 계수의 타당성을 하류 회귀 성능으로 판정하였다",RED));
k.push(quote("적용 결과 예측력 지표는 유지되었고 … 관광의 설명력은 소폭 개선되어, 셀별 전환이 타당했음을 확인하였다"));
k.push(p([t("측정 도구의 타당성을 그 도구가 생성한 값이 회귀에서 적합한 정도로 판정하였다. 이 절차는 "),
  t("β 를 상승시키는 방향으로 ρ 를 선택하게 만든다.",{b:true,c:RED}),
  t(" 제2장이 세운 “선택과 평가의 분리” 원칙에 저촉된다.")]));
k.push(fix("ρ 의 타당성은 병행 표본 자체의 일치도, 즉 두 수집 방식이 동일 기간 동일 셀에서 산출한 값의 근접도로만 판정한다. 회귀 성능은 사후 관찰로만 기술하고 “타당했음을 확인하였다”는 표현을 삭제한다."));

// ══ E
k.push(h1("E. 대상 모집단의 미확정"));
k.push(body("문서 내 국가 명단이 최소 네 가지로 병존한다."));
k.push(sp());
k.push(table(["위치","명단"],
  [["제2장 표 2.9","미·영·호주·독·프·브라질·멕시코·인니·베트남·일·인도·이집트·사우디·UAE·중국"],
   ["부록 B 서두",{v:"“최종 112셀 — 중국 제외 14개국 × 8산업”",c:RED}],
   ["부록 B3 (D3 채택)",{v:"US·GB·JP·SA·VN (5국)",c:RED}],
   ["제출 대시보드",{v:"BR·CA·CN·DE·FR·GB·ID·IN·JP·MX·PH·SA·TW·US·VN (중국 포함 15국)",c:RED}]],[22,78]));
k.push(sp());
k.push(body("제2장 표의 호주·이집트·UAE 가 대시보드에 없고, 대시보드의 캐나다·대만·필리핀이 제2장 표에 없다. 부록 B 는 “중국 제외”를 명시하나 대시보드 수출 데이터에는 중국이 포함된다."));
k.push(body("여기서 두 가지 구체적 결함이 파생한다."));
k.push(p([t("첫째, 제2장은 “무슬림 시장(이집트·사우디·UAE·인니)의 할랄 결합 쿼리는 … 해당 4개국 A 사전에 "),
  t("필수 포함한다",{b:true}),
  t("”고 규정하나, 대시보드 신호 국가는 BR·DE·GB·IN·JP·PH·SA·TW·US·VN 이다. "),
  t("필수 규정 대상 4개국 중 3개가 수집 대상에 포함되지 않는다.",{b:true,c:RED})]));
k.push(p([t("둘째, 제2장은 A 차원의 주 신호를 “YouTube 댓글·"),t("Bilibili 탄막",{b:true}),
  t("의 긍정 판정 발생률”로 규정하나 부록 B 는 중국을 제외한다. "),
  t("작동하지 않는 원천이 주 신호로 규칙서에 기재되어 있다.",{b:true,c:RED})]));
k.push(fix("제1장에 「대상 모집단 확정표」를 신설한다. 열은 국가 / 수출 준거 유무 / 신호 수집 유무 / 사전 세대 / 파일럿·본구축 구분으로 구성한다. 제2장과 부록 B 의 명단을 해당 표에 맞추어 일괄 수정한다. 현행 문서로는 대상국이 확정되지 않는다."));

// ══ 우선순위
k.push(h1("F. 조치 우선순위"));
k.push(table(["순위","조치","자원","좌우되는 결과"],
  [[{v:"1",b:true,c:RED},{v:"웹툰·게임 5국판 국가 간 분산 확인 → 0 이면 β 철회",b:true},{v:"즉시",c:GREEN},"표 4.2 의 두 칸"],
   [{v:"2",b:true,c:RED},{v:"관광 C 를 의도어 결합 계열로 재추정",b:true},{v:"재분석",c:GREEN},"유일한 통과 산업"],
   [{v:"3",b:true,c:RED},{v:"A 제외(C·B 2차원) 판본 β 병기",b:true},{v:"재분석",c:GREEN},"백필 44%의 영향 분리"],
   [{v:"4",b:true,c:RED},{v:"등가중 대비 검정 결과 및 λ 공표",b:true},{v:"재분석",c:GREEN},"방법론적 기여의 성립"],
   [{v:"5",b:true,c:AMBER},"“8산업 β 전부 양수” 삭제, β_PRD 부호로 대체","집필","대표 결론"],
   [{v:"6",b:true,c:AMBER},"판정표 3종 통일, 준거 등급 5단계 고정","집필","인용 가능성"],
   [{v:"7",b:true,c:GREY},"대상 모집단 확정표 신설","집필","문서 정합성"],
   [{v:"8",b:true,c:GREY},"사전 규칙 위반 3건 시정 (게임 12 · 뷰티 1 · 웹툰 2)","재프로브","측정 타당성"]],
  [8,44,14,34]));
k.push(sp());
k.push(p([t("1~4 는 실증의 사활이 걸린 항목이며 "),
  t("추가 자료 구매 없이 기존 자료의 재분석만으로 수행된다.",{b:true,c:GREEN}),
  t(" 보고서가 차기 과제로 제시한 “8산업별 보정 데이터 구매”에 선행해야 한다. 자료를 추가 확보하기 전에 현행 자료로 무엇을 진술할 수 있는지가 먼저 확정되어야 한다.")]));

// ══ 결어
k.push(h1("G. 결어"));
k.push(p([t("본 보고서의 제2장은 이 분야에서 보기 드문 수준의 자기 검토를 담고 있다. NNLS 의 다섯 가지 단점을 스스로 열거하고 각각에 방어책을 배치하였으며, 데이터 스누핑·자기 채점·준거 품질 종속을 모두 명시적으로 다룬다. "),
  t("문제는 그 엄격함이 제4장의 결과 보고와 부록의 실제 사전에 적용되지 않았다는 데 있다.",{b:true,c:NAVY})]));
k.push(p([t("제2장이 “NNLS 는 음의 관계를 0 으로 눌러 무관계로 보고한다”고 서술한 뒤 제4장이 “8산업 모두 양수”를 발견으로 제시하는 구조가 그 단절을 압축한다. "),
  t("제2장의 기준을 제4장에 이전하는 것만으로 본 심사가 지적한 열여섯 항목 중 아홉이 해소된다.",{b:true})]));
k.push(p([t("실증에 관한 판단은 다음과 같다. 현 단계에서 "),
  t("β 판정 결과는 인용 가능한 실증 결과로 볼 수 없다.",{b:true,c:RED}),
  t(" 다만 이는 파일럿 단계의 통상적 미비이며, 결함의 성격은 설계의 오류가 아니라 검증의 미완이다. 우선순위 1~4 를 수행한 뒤 재심사를 권고한다.")]));
k.push(p([t("끝으로 파일럿의 성과를 β 의 크기에서 찾지 않기를 권한다. 측정 → 준거 → 추정 → 합성 → 검증의 전 구성요소가 실데이터에서 완주하였다는 사실 자체가 중간 성과로 충분하며, "),
  t("β 판정을 “결과”가 아니라 “진단 절차의 작동 확인”으로 재서술하는 것",{b:true,c:NAVY}),
  t("이 현 단계에 부합하는 기술이다.")]));

k.push(new Paragraph({
  children:[t("본 심사의견의 실측 수치는 제출된 kci_dashboard.html 내장 데이터(EXP 8,039행 · SIG 9,905행)를 심사자가 직접 추출·재계산한 값이다. 파일럿 β 는 5국 산출이고 대시보드는 15국 구축분이므로, C-2 의 웹툰 관련 지적은 5국판에서의 재확인을 요한다. 다만 부록 D3 이 기술한 배분 방법이 양자에 동일하므로 동일한 성질이 관측될 개연성이 높다.",{size:16,c:GREY})],
  spacing:{before:340},
  border:{top:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

const doc=new Document({styles:{default:{document:{run:{font:F,size:20}}}},
  sections:[{properties:{page:{margin:{top:1000,bottom:1000,left:1000,right:1000}}},children:k}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(process.argv[2],b);
  console.log("= "+process.argv[2]+"  "+(b.length/1024).toFixed(0)+" KB");});

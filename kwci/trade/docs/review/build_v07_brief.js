const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        WidthType, BorderStyle, ShadingType } = require("docx");

const NAVY="1F3864", RED="A62B2B", GREEN="2E6B3E", GREY="5A5A5A", LINE="C9C9C9", BG="F2F4F7";
const F="맑은 고딕";

const t=(x,o={})=>new TextRun({text:x,font:o.font||F,size:o.size||20,bold:o.b,italics:o.i,color:o.c,break:o.br});
const p=(r,o={})=>new Paragraph({children:Array.isArray(r)?r:[r],
  spacing:{before:o.before??70,after:o.after??70,line:280},indent:o.indent,border:o.border});
const h1=(x)=>new Paragraph({children:[t(x,{size:26,b:true,c:NAVY})],
  spacing:{before:340,after:130},
  border:{bottom:{style:BorderStyle.SINGLE,size:10,color:NAVY,space:6}}});
const num=(n,x)=>new Paragraph({
  children:[t(n+". ",{size:23,b:true,c:NAVY}),t(x,{size:23,b:true,c:NAVY})],
  spacing:{before:300,after:100}});
const body=(x,o={})=>p(t(x,o));
const quote=(x)=>new Paragraph({children:[t(x,{i:true,c:GREY,size:19})],
  spacing:{before:90,after:110,line:264},indent:{left:340},
  border:{left:{style:BorderStyle.SINGLE,size:14,color:LINE,space:10}}});
const rec=(x)=>new Paragraph({children:[t("권고  ",{b:true,c:GREEN,size:19}),t(x,{size:19})],
  spacing:{before:100,after:140,line:272},indent:{left:240},
  border:{left:{style:BorderStyle.SINGLE,size:14,color:GREEN,space:10}}});
const mono=(x)=>new Paragraph({children:[t(x,{size:17,c:GREY,font:"D2Coding"})],
  spacing:{before:70,after:100,line:250},indent:{left:280}});
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

k.push(new Paragraph({children:[t("KCI 중간보고서(v07) 검토 소견",{size:36,b:true,c:NAVY})],spacing:{after:60}}));
k.push(new Paragraph({children:[t("요약 — 여섯 항목",{size:22,c:GREY})],spacing:{after:150}}));
k.push(new Paragraph({
  children:[t("대상: 「K-Culture Index 개발 및 실증 연구」 중간보고서 v07 (2026.09)",{size:17,c:GREY}),
    t("실측 근거: 함께 제출된 kci_dashboard.html 내장 데이터(EXP 8,039행 · SIG 9,905행)를 재계산한 값",{size:17,c:GREY,br:true})],
  spacing:{after:200},
  border:{bottom:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

// ── 총평
k.push(h1("총평"));
k.push(body("제2장의 자기 검토 수준은 이 분야의 통상적 보고서를 상회한다. NNLS의 단점을 다섯 항목으로 스스로 열거하고 각각에 방어책을 배치하였으며, 데이터 스누핑·자기 채점·준거 품질 종속을 모두 명시적으로 다룬다."));
k.push(p([t("문제는 "),t("그 엄격함이 제4장의 결과 보고와 부록의 실제 사전에 적용되지 않았다는 데 있다.",{b:true,c:RED}),
  t(" 아래 지적의 다수는 새로운 문제가 아니라, 보고서가 이미 서술한 원칙을 스스로 지키지 않은 경우다. 여섯 항목으로 요약한다.")]));

// ── 1
k.push(num(1,"“8산업 β 전부 양수”는 발견이 아니라 추정량의 제약이다"));
k.push(body("제2장은 다음과 같이 서술한다."));
k.push(quote("부호 제약이 진짜 음의 관계를 숨길 수 있다 … NNLS는 이를 0으로 눌러 “무관계”로 보고한다"));
k.push(p([t("정확한 진술이다. 그러나 제4장과 Executive Summary는 그 비음수 결과를 “방향 일관성”의 근거로 제시한다. "),
  t("음수를 산출할 수 없는 추정량으로 부호 일관성을 보고하는 것은 항진명제다.",{b:true,c:RED})]));
k.push(rec("해당 문장을 결론에서 삭제하고, 부호를 개방한 β_PRD의 부호 분포로 대체한다. 제2장이 PRD의 부호를 연 취지가 이것이다."));

// ── 2
k.push(num(2,"웹툰은 국가별 변동이 0이다"));
k.push(body("제출된 대시보드 데이터로 전년동기 증가율의 국가 간 표준편차를 산출하였다."));
k.push(sp());
k.push(table(["산업","2022~2023","2025~2026"],
  [[{v:"webtoon",b:true},{v:"0.0000   ← 15개국이 완전히 동일",b:true,c:RED},{v:"0.0164",c:RED}],
   ["game","0.1976","0.0971"],
   ["food","0.3408","0.3315"],
   ["fashion","0.6091","0.6591"]],[22,46,32]));
k.push(sp());
k.push(p([t("국가 구성비는 "),t("2021-01 ~ 2024-03의 39개월 동안 단 하나",{b:true}),
  t("이며, 이후에도 분기 단위로만 변화한다(게임도 동일). 부록 D3이 기술한 월간 변조가 데이터에 존재하지 않는다. 웹툰 앱이 다수 국가의 Google Play 매출 순위권에 진입하지 못하여 변조 계수가 1로 고정된 것으로 추정된다.")]));
k.push(p([t("그럼에도 표 4.2는 웹툰을 “통과(국가층) — 영어권 국가층에서 정방향 성립”으로 판정한다. "),
  t("존재하지 않는 국가층을 근거로 통과 판정을 내린 것이다.",{b:true,c:RED})]));
k.push(rec("5국 파일럿에서 동일 계산을 1회 수행한다. 0이면 해당 β를 철회하고 “국가별 준거 부재로 산출 불가”로 표기한다."));

// ── 3
k.push(num(3,"A 차원 백필 44%로 측정 정의가 시간에 따라 변한다"));
k.push(body("대시보드 신호의 연도별 차원 가용률은 다음과 같다."));
k.push(mono("2021   C 100%   A 83%   B 68%   S 95%\n2024   C 100%   A 95%   B 68%   S 95%"));
k.push(p([t("부분창 재정규화 규정에 따르면 "),
  t("전반부는 C·B 2차원, 후반부는 C·A·B 3차원 합성",{b:true,c:RED}),
  t("이 된다. 12개월 차분을 적용하면 차원 구성이 상이한 두 시점을 차감하게 된다. 제2장이 서술한 문제와 동일하다.")]));
k.push(quote("장치의 탈착 자체가 측정 정의의 변경으로서 시계열 일관성을 해치는 것을 방지하려는 조치"));
k.push(rec("백필 완료를 기다릴 필요가 없다. A를 제외한 C·B 2차원 판본으로 전 구간 β를 재추정하여 현행 결과와 병기한다. 두 판본이 일치하면 결과는 백필 진도와 무관하게 성립하고, 불일치하면 현행 β는 백필 진도를 측정한 것이다."));

// ── 4
k.push(num(4,"관광 C가 맨 지명이며 가중 68%를 점한다"));
k.push(mono("TOURISM  C   Busan · Seoul · Jeju Island · Gyeongbokgung Palace"));
k.push(body("지명 단독 검색은 뉴스·정치·스포츠 관련 검색을 포함한다. 부산은 영화제·엑스포 유치 보도로 여행 수요와 무관하게 급등한다."));
k.push(p([t("관광은 8산업 중 "),t("유일하게 표본외 개선까지 충족한 산업",{b:true}),
  t("이다. 지명 검색과 입국자 수가 모두 “해당국의 한국 관련 뉴스 노출”에 동시 반응할 수 있으므로, 높은 설명력이 공통 원인의 소산일 가능성을 배제하지 못한다.")]));
k.push(rec("Seoul travel·ソウル 旅行 등 의도어를 결합한 계열로 C를 재구성하여 β를 재추정한다. B 차원(Korail·Naver Map)의 설계는 적절하다."));

// ── 5
k.push(num(5,"동일 산업에 판정이 셋 병존한다"));
k.push(sp());
k.push(table(["위치","영상·웹툰 판정"],
  [["Executive Summary",{v:"재검토",b:true}],
   ["표 4.1",{v:"공시(부호 역전)",b:true}],
   ["표 4.2",{v:"통과(국가층)",b:true,c:RED}]],[34,66]));
k.push(sp());
k.push(p([t("식품은 Executive Summary의 판정 목록에서 누락되었으나, 해당 산업은 "),
  t("β 0.00006 · r² .01로 8산업 중 최약",{b:true,c:RED}),
  t("이다. 준거 등급도 제2장은 5단계, 제4장은 4단계로 상이하다.")]));
k.push(rec("표 4.1과 표 4.2를 단일 표로 통합하고 판정 어휘를 4단계로 고정한다."));

// ── 6
k.push(num(6,"등가중 대비 검정 결과가 제시되지 않았다"));
k.push(body("제2장은 성과준거 가중을 방법론적 장점으로 제시한다."));
k.push(quote("왜 관광 지수에서 C가 68%인가 — 관광객 수를 가장 잘 설명하는 비율이기 때문"));
k.push(body("그러나 동 장의 한계 다섯째는 다음과 같다."));
k.push(quote("추정 창(수년)의 유효 자유도 제약으로 가중치가 등가중과 통계적으로 구별되지 않을 수 있으며, 이 경우 축소 추정이 등가중을 채택하는 것은 결함이 아니라 정직한 판정이다"));
k.push(p([t("해당 검정 결과와 축소 강도 λ가 "),t("문서에 없다.",{b:true,c:RED}),
  t(" 68%가 33%와 구별되지 않으면 위 “한 줄 답변”은 성립하지 않는다.")]));
k.push(rec("산업별로 추정 w / 축소 후 w / λ / 등가중 대비 표본외 개선의 4열 표를 제시한다. λ가 큰 산업은 “데이터가 가중을 결정하지 못하였다”고 명시한다. 이는 결함의 고백이 아니라 정직한 보고이며, 보고서 자신이 그렇게 규정하였다."));

// ── 우선순위
k.push(h1("조치 우선순위"));
k.push(table(["","조치","소요"],
  [[{v:"1",b:true,c:RED},{v:"웹툰·게임 5국판 국가 간 분산 확인",b:true},{v:"즉시",c:GREEN}],
   [{v:"2",b:true,c:RED},{v:"관광 C를 의도어 결합 계열로 재추정",b:true},{v:"재분석",c:GREEN}],
   [{v:"3",b:true,c:RED},{v:"A 제외(C·B 2차원) 판본 β 병기",b:true},{v:"재분석",c:GREEN}],
   [{v:"4",b:true,c:RED},{v:"등가중 대비 검정 결과 및 λ 공표",b:true},{v:"재분석",c:GREEN}]],
  [8,72,20]));
k.push(sp());
k.push(p([t("네 항목 모두 "),t("추가 자료 구매 없이 기존 자료의 재분석만으로 수행된다.",{b:true,c:GREEN}),
  t(" 차기 과제로 제시된 “8산업별 보정 데이터 구매”에 선행해야 한다. 자료를 추가 확보하기 전에 현행 자료로 무엇을 진술할 수 있는지가 먼저 확정되어야 한다.")]));
k.push(body("나머지 항목(판정표 통일, 준거 등급 정리, 대상 국가 명단 확정)은 집필 정합성에 해당하며 단기간에 처리 가능하다."));

// ── 부기
k.push(h1("부기"));
k.push(p([t("본 파일럿의 성과를 β의 크기에서 찾을 필요는 없다. 측정 → 준거 → 추정 → 합성 → 검증의 전 구성요소가 실데이터에서 완주하였다는 사실 자체로 중간 성과는 충분하다. "),
  t("β 판정을 “결과”가 아니라 “진단 절차의 작동 확인”으로 재서술하는 것",{b:true,c:NAVY}),
  t("이 현 단계에 부합하며, 위 지적의 다수도 그 재서술로 해소된다.")]));

k.push(new Paragraph({
  children:[t("상세 검토는 별도 의견서(5묶음 16항목)로 정리되어 있다. 파일럿 β는 5국 산출이고 대시보드는 15국 구축분이므로 항목 2의 지적은 5국판에서의 재확인을 요하나, 부록 D3이 기술한 배분 방법이 양자에 동일하므로 동일한 성질이 관측될 개연성이 높다.",{size:16,c:GREY})],
  spacing:{before:320},
  border:{top:{style:BorderStyle.SINGLE,size:6,color:LINE,space:8}}}));

const doc=new Document({styles:{default:{document:{run:{font:F,size:20}}}},
  sections:[{properties:{page:{margin:{top:1000,bottom:1000,left:1000,right:1000}}},children:k}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(process.argv[2],b);
  console.log("= "+process.argv[2]+"  "+(b.length/1024).toFixed(0)+" KB");});

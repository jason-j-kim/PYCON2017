#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KDI 연구계획 보고서를 만든다 — 공무원 보고형식(개조식).

앞서 만든 안내서들과 달리 이것은 결재선에 올라가는 문서다. 그래서 서식을
바꾼다. □ ○ - · 네 단계 기호, 계단식 들여쓰기, 명사형 종결.

내용은 docs/KDI연구초안.md 에서 가져온다. 지어낸 숫자를 넣지 않는다 —
예비 관찰은 예비 관찰로, n=1쌍은 n=1쌍으로 적는다. 결재자가 나중에
원자료를 보고 놀라는 일이 없어야 한다.
"""
import os
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm

KO = "맑은 고딕"
TITLE, HEAD, BODY, SMALL = Pt(16), Pt(12), Pt(11), Pt(10)
BLACK = RGBColor(0, 0, 0)

doc = Document()
sec = doc.sections[0]
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
sec.left_margin, sec.right_margin = Cm(2.5), Cm(2.5)

st = doc.styles["Normal"]
st.font.name = KO
st.font.size = BODY
st.font.color.rgb = BLACK
st.element.rPr.rFonts.set(qn("w:eastAsia"), KO)
st.paragraph_format.line_spacing = Pt(17)
st.paragraph_format.space_after = Pt(4)


def style_run(r, size=BODY, bold=False):
    r.font.name = KO
    r.font.size = size
    r.font.bold = bold
    r.font.color.rgb = BLACK
    rpr = r._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {}); rpr.insert(0, rf)
    for a in ("w:eastAsia", "w:ascii", "w:hAnsi"):
        rf.set(qn(a), KO)
    return r


def p(text="", size=BODY, bold=False, after=4, before=0, indent=0,
      hang=None, align=None, line=17, keep=False):
    par = doc.add_paragraph()
    f = par.paragraph_format
    f.space_after, f.space_before, f.line_spacing = Pt(after), Pt(before), Pt(line)
    if indent:
        f.left_indent = Cm(indent)
    if hang is not None:
        f.first_line_indent = Cm(-hang)
    if align is not None:
        par.alignment = align
    f.keep_together = True
    if keep:
        f.keep_with_next = True
    if text:
        style_run(par.add_run(text), size, bold)
    return par


def rich(chunks, after=4, before=0, indent=0, hang=None, size=BODY):
    par = p("", after=after, before=before, indent=indent, hang=hang)
    for t, b in chunks:
        style_run(par.add_run(t), size, b)
    return par


# ── 개조식 네 단계 ────────────────────────────────────────────────────
def jang(text):                      # Ⅰ. 장
    return p(text, HEAD, True, after=8, before=18, keep=True)


def ne(text, bold=True):             # □ 1단
    return p(f"□ {text}", BODY, bold, after=5, before=8,
             indent=0.0, hang=0.0, keep=True)


def o(text, after=4):                # ○ 2단
    return p(f"○ {text}", indent=0.65, hang=0.45, after=after)


def o_rich(chunks, after=4):
    return rich([("○ ", False)] + list(chunks), indent=0.65, hang=0.45, after=after)


def dash(text, after=3):             # - 3단
    return p(f"- {text}", SMALL, indent=1.25, hang=0.42, after=after)


def dot(text, after=3):              # · 4단
    return p(f"· {text}", SMALL, indent=1.85, hang=0.38, after=after)


def table(rows, widths, small=True):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for gc, w in zip(t._tbl.find(qn("w:tblGrid")), widths):
        gc.set(qn("w:w"), str(w))
    sz = SMALL if small else BODY
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            cell.width = Pt(widths[ci] / 20)
            for li, line in enumerate(str(val).split("\n")):
                par = cell.paragraphs[0] if li == 0 else cell.add_paragraph()
                par.paragraph_format.space_after = Pt(1)
                par.paragraph_format.space_before = Pt(1)
                par.paragraph_format.line_spacing = Pt(14)
                par.paragraph_format.keep_with_next = (ri < len(rows) - 1)
                if ri == 0 or (ci == 0 and len(rows[0]) > 2):
                    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                style_run(par.add_run(line), sz, ri == 0)
        t.rows[ri]._tr.get_or_add_trPr().append(
            t.rows[ri]._tr.makeelement(qn("w:cantSplit"), {}))
    tblPr = t._tbl.tblPr
    b = tblPr.makeelement(qn("w:tblBorders"), {})
    for edge, s in (("top", "6"), ("bottom", "6"), ("left", "4"), ("right", "4"),
                    ("insideH", "2"), ("insideV", "2")):
        e = b.makeelement(qn("w:" + edge), {})
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), s)
        e.set(qn("w:color"), "000000"); e.set(qn("w:space"), "0")
        b.append(e)
    tblPr.append(b)
    t.rows[0]._tr.get_or_add_trPr().append(
        t.rows[0]._tr.makeelement(qn("w:tblHeader"), {}))
    p("", after=8)
    return t


def rule_line(after=10):
    par = doc.add_paragraph()
    par.paragraph_format.space_before = Pt(2)
    par.paragraph_format.space_after = Pt(after)
    pPr = par._p.get_or_add_pPr()
    b = pPr.makeelement(qn("w:pBdr"), {})
    bot = b.makeelement(qn("w:bottom"), {})
    bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), "6")
    bot.set(qn("w:color"), "000000"); bot.set(qn("w:space"), "1")
    b.append(bot); pPr.append(b)


C = WD_ALIGN_PARAGRAPH.CENTER
R = WD_ALIGN_PARAGRAPH.RIGHT

# ══ 표제부 ═════════════════════════════════════════════════════════════
p("2026. 9.", SMALL, align=R, after=2)
p("국민대학교 김재준", SMALL, align=R, after=14)

p("생성형 AI 기반 정책 아이디어 평가체계 연구", TITLE, True, align=C, after=4)
p("추진계획(안)", TITLE, True, align=C, after=10)
rule_line(14)

ne("추진 목적")
o("생성형 AI 확산에 따라 서면 진술에 의존하는 공공 평가의 타당성이 흔들리고 "
  "있는바, 그 영향의 크기를 실증하고 대응 설계를 제시하고자 함")
o("이를 위해 실제 작동하는 정책 아이디어 평가 시스템을 활용, 2단계 연구를 "
  "순차 추진하고자 함", after=8)

# ══ Ⅰ. 추진 배경 ══════════════════════════════════════════════════════
jang("Ⅰ. 추진 배경")

ne("공공 평가의 상당수가 신청자의 서면 진술에 의존")
o("국민제안·공모사업·연구과제 선정 등에서 평가 대상은 제안 내용이나, "
  "실제 심사 근거는 신청자가 작성한 문서임")

ne("생성형 AI 확산으로 진술의 질과 내용의 질이 분리")
o("동일한 착상이라도 AI 보조 여부에 따라 진술의 완성도가 달라짐")
o_rich([("이 경우 평가는 제안의 질이 아니라 ", False), ("도구 접근성", True),
        ("을 측정하게 되어, 의도한 구인(構人)을 재지 못하는 문제가 발생", False)])

ne("탐지·금지 방식은 대응책이 되기 어려움")
o("AI 생성물 탐지의 정확도가 행정처분의 근거로 쓰일 수준에 이르지 못함")
o("평가 대상이 '사람의 능력'이 아니라 '제안이라는 산출물'인 영역에서는, "
  "금지보다 균등 제공이 정합적일 수 있음")
dash("다만 이 주장은 격차의 존재가 실증되어야 성립하는바, 본 연구의 검증 대상임")

# ══ Ⅱ. 그간의 경과 ════════════════════════════════════════════════════
jang("Ⅱ. 그간의 경과")

ne("평가 시스템 구축 완료(연구자 자체 개발)")
o("소크라테스식 12문답으로 제안을 구조화하고, 국가 데이터 4개 통로로 "
  "선례를 확인하여 이원 평가하는 웹 시스템")
dash("축 A(방어력) — 독창성·실용성·수용태도 3기준, 가중치 35:35:30")
dash("축 B(실질 독창성) — 4개 통로 조회 후 선례 계열 판정 및 확신도 부여")

ne("검증용 국가 데이터 탑재")
table([
    ["통로", "자료", "규모"],
    ["① 재정(집행)", "세출예산 사업", "14,122개 사업"],
    ["② 연구(검토)", "KDI 발간물", "7,362건"],
    ["③ 입법(시도)", "국회 의안(실시간 조회)", "열린국회정보 API"],
    ["④ 해외(시행)", "OECD OPSI 정책사례", "1,015건 · 98개국"],
], [1700, 3400, 2900])

o_rich([("조회 결과를 ", False), ("미실행 / 조회 실패 / N건", True),
        (" 셋으로 구분하여, 앞의 둘은 '선례 없음'이 아니라 '확인하지 못함'으로 "
         "처리하고 확신도 상향을 제한함", False)])

ne("KDI 서버 설치용 배포판 전달 완료")
o("윈도우 서버판(작업 스케줄러 + IIS) 및 설치·운영 안내서 전달")
o("설치 즉시 가동 가능한 상태로, 별도 개발 소요 없음", after=8)

# ══ Ⅲ. 예비 검토 결과 ═════════════════════════════════════════════════
jang("Ⅲ. 예비 검토 결과 및 문제 인식")

ne("예비 검토에서 두 가지가 관찰됨")

o_rich([("(관찰 1) ", True),
        ("평가도구 자체의 재현성에 문제 — 동일 대화 로그를 체크리스트로 "
         "4회 채점한 결과 합계가 ", False),
        ("13~17로 분포", True), ("(30점 척도, 평균 15.0)", False)])
dash("당초 체크리스트는 '해당 사건이 대화에 있었는가'만 판정하는 기계적 "
     "절차로 설계하였고 재현성이 그 설계의 근거였으나, 경험적으로 미성립")

o_rich([("(관찰 2) ", True),
        ("동일 아이디어에 대해 AI 보조 조건의 점수가 높았음", False),
        (" (5.2 → 8.0)", True)])
dash("다만 이는 n=1쌍의 통제되지 않은 비교로, 두 조건에 서로 다른 질문이 "
     "제시되었음. 방향의 시사에 한정되며 크기의 근거로 사용 불가")

ne("문제 인식 — 측정과 격차의 선후가 뒤바뀌어 있음")
o("도구의 측정오차를 모르는 상태에서 격차를 보고하면, 그 수치가 실재하는 "
  "차이인지 채점 잡음인지 판별할 수 없음")
o("따라서 '격차를 측정하는 연구'가 아니라 '측정도구를 먼저 검증하고, "
  "그 오차를 넘는 격차가 있는지 검정하는 연구'로 설계할 필요")

ne("이 문제 인식이 본 계획의 설계 근거")
o_rich([("예비 관찰을 연구 결과로 제시하지 아니함", True),
        (". 본 계획은 위 관찰을 ", False), ("가설의 지위", True),
        ("로 두고, 통제된 본실험으로 확정하는 것을 과제로 함", False)])

# ══ Ⅳ. 추진 방향 ══════════════════════════════════════════════════════
jang("Ⅳ. 추진 방향")

ne("(원칙 1) 측정이 먼저, 격차는 그다음")
o("측정오차를 선행 추정하고 판정 임계값을 사전 결정한 뒤 본실험 착수")

ne("(원칙 2) 근거의 지위를 문서에 명시")
o("예비 관찰·본실험 결과·모델 지식을 구분하여 표기하고, 확인하지 못한 것은 "
  "'없음'이 아니라 '미확인'으로 기재")

ne("(원칙 3) 제도 설계는 실증 이후")
o("격차가 확인되지 않으면 제도 개편을 권고하지 아니함. 2단계 연구의 도입 "
  "조건이 1단계 결과에 직접 의존하도록 설계", after=8)

# ══ Ⅴ. 세부 추진계획 ══════════════════════════════════════════════════
jang("Ⅴ. 세부 추진계획")

ne("2단계 순차 추진")

table([
    ["구분", "1단계 연구", "2단계 연구"],
    ["과제명", "생성형 AI가 공공 평가에\n미치는 영향 — 평가도구의\n재현성과 도구 격차",
     "국민 정책제안의 검증 병목과\n제도 재설계 — 대화형 구조화와\n다원 선례검증의 적용"],
    ["성격", "실증 분석", "제도 설계"],
    ["발간(안)", "정책연구시리즈", "연구보고서"],
    ["기간", "7개월", "12개월"],
    ["착수 요건", "없음 (즉시 착수 가능)", "1단계 결과"],
], [1100, 3450, 3450])

o_rich([("1단계를 선행하여야 함", True),
        (". 2단계의 도입 조건이 1단계 결과에 의존하는바, 선후를 바꾸면 "
         "'재현성이 확인되지 않은 도구를 제도화하자'는 제안이 되어 방어 곤란",
         False)])

o_rich([("자료 수집은 공유", True),
        (". 1단계 본실험 90세션에 전문가 심사를 병행하면 2단계의 선결 과제"
         "(준거 타당도)가 동시에 해결되어, 별도 수집 소요를 절감", False)],
       after=8)

ne("1단계 연구 일정 (7개월)")
table([
    ["월", "추진 내용"],
    ["1", "체계적 문헌 검토, 실험 프로토콜 확정, IRB 심의·동의 절차"],
    ["2", "선행 20세션 — 측정오차 추정 및 판정 임계값 사전 결정,\n"
          "최소탐지효과(MDE) 산출 및 표본 재조정"],
    ["3", "응답자 모집(30명), 예비 세션"],
    ["4~5", "본실험 90세션, 반복채점 270회, 명세 고정 재채점 병행"],
    ["6", "분석 — 신뢰도 추정, 격차 검정, 구성요소 분해, 완화장치 효과"],
    ["7", "보고서 작성"],
], [700, 7300])

ne("2단계 연구 일정 (12개월)")
table([
    ["분기", "추진 내용"],
    ["1", "접수·처리 통계 확보, 현행 제도 분석, IRB 심의, 면접 설계"],
    ["2", "담당자 면접(15~20인), 병목 가설 검증, 재현성·준거타당도 측정"],
    ["3", "국제 비교, 처리 절차 설계 확정, 총소유비용 추계"],
    ["4", "파일럿 설계, 법·제도 정비안 도출, 보고서 작성"],
], [700, 7300])

# ══ Ⅵ. 소요 및 행정사항 ═══════════════════════════════════════════════
jang("Ⅵ. 소요 및 행정사항")

ne("투입(안)")
table([
    ["구분", "1단계 (7개월)", "2단계 (12개월)"],
    ["연구 인력", "책임연구원 1, 연구원 1,\n연구조원 1",
     "책임연구원 1, 연구원 2,\n연구조원 1"],
    ["외부 자문", "측정·평가 1, 정책 실무자 1",
     "행정법 1, 측정·평가 1,\n제안제도 실무자 2"],
    ["조사·심사", "응답자 30명 사례비", "담당자 면접 사례비,\n전문가 심사 3인"],
    ["전산", "모델 호출 비용\n(270회 채점 + 세션 진행)", "모델 호출 비용,\n코퍼스 갱신"],
], [1200, 3400, 3400])

o("구체 금액은 기관 기준 단가 확정 후 산정 예정")
o_rich([("시스템 개발비는 불요", True),
        (" — 평가 시스템과 검증용 코퍼스가 이미 구축되어 있으며, "
         "서버 설치 자료도 전달 완료", False)])

ne("사전 조치 필요사항")
o("(연구윤리) 사람 대상 실험인바 IRB 심의 선행 필요")
o("(개인정보) 문답 이력에 개인정보가 포함될 수 있어, 수집·보관·파기 절차 "
  "사전 확정 필요")
o("(전산) 서버 설치 시 api.anthropic.com 외부 통신 허용 필요. 미허용 시 "
  "시스템 전체가 작동하지 않음")
o("(자료 협조) 2단계 착수를 위해서는 국민제안 접수·처리 통계 확보가 "
  "선결 조건임", after=8)

# ══ Ⅶ. 기대효과 ═══════════════════════════════════════════════════════
jang("Ⅶ. 기대효과 및 한계")

ne("기대효과")
o("(측정) 공공 평가도구의 재현성을 실측한 수치를 제시, 향후 평가체계 "
  "설계의 기준점 제공")
o("(정책) AI 시대 공공 평가의 대응 원칙 — 탐지·금지 대 균등 제공 — 에 "
  "대해 실증에 근거한 판단 근거 제시")
o("(제도) 국민제안 처리 병목에 대한 구체적 절차 설계안과 도입 로드맵 도출")
o("(자산) 평가 시스템과 국가 데이터 코퍼스가 연구 종료 후에도 기관 자산으로 "
  "잔존, 후속 연구에 재사용 가능")

ne("한계 및 유의사항")
o_rich([("예비 관찰은 확정된 결과가 아님", True),
        (". 관찰 2는 n=1쌍의 통제되지 않은 비교로, 본실험에서 재현되지 "
         "않을 가능성을 배제할 수 없음", False)])
o("본 계획의 정책 권고는 격차의 존재가 1단계에서 확인되는 것을 전제로 함. "
  "확인되지 않을 경우 권고 내용을 조정하여야 함")
o("문답 생성·채점·판정에 동일 계열 모델이 사용되는 구조적 순환이 있는바, "
  "전문가 심사를 준거로 병행하여 완화할 계획임")

rule_line(8)
p("붙임  1. 정책 아이디어 평가 시스템 설치·운영 안내서 1부.", SMALL, after=2)
p("      2. 연구 초안(연구 1·2) 1부.  끝.", SMALL)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "KDI_연구추진계획.docx")
doc.save(out)
print("저장 완료 —", out)

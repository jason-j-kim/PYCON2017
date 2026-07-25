"""PRISM 소스(정책연구 과제) 모의 검증 — 실제 API 없이 데이터 경로를 점검한다.

실행: DATA_GO_KR_KEY=TESTKEY python simulation/mock_prism.py
PRISM(getResearchList_v2)은 키워드 파라미터가 없어 날짜로 목록을 받아 과제명으로
로컬 매칭한다. 여기서 보는 것은 '응답 파싱 → 키워드 필터 → 구조화'와 키 정규화다.
"""
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("DATA_GO_KR_KEY", "TESTKEY")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _prism_json(rows):
    # data.go.kr 표준 중첩: response>body>items>research[...]
    return json.dumps({"response": {"header": {"resultCode": "00"},
                                    "body": {"items": {"research": rows}}}},
                      ensure_ascii=False)


def RESEARCH(name, organ="한국행정연구원", date="2023-05-01", biz=""):
    return {"research_name": name, "organ_name": organ,
            "research_date": date, "biz_name": biz}


def run(name, rows, query, capture=None):
    def fake(req, timeout=None):
        if capture is not None:
            capture["url"] = req.full_url
        return _Resp(_prism_json(rows).encode())
    urllib.request.urlopen = fake
    hits = app._prism_lookup(query)
    print(f"\n===== {name} =====")
    print(f"질의어: '{query}'  → PRISM {len(hits)}건")
    for h in hits:
        print(f"  · {h['title']}  ({h['org']}, {h['period']})")
    return hits


if __name__ == "__main__":
    pool = [
        RESEARCH("중소기업 데이터 분석 역량 강화 방안 연구"),
        RESEARCH("교양교육 필수화의 정책효과 분석", organ="한국교육개발원", date="2022-11-01"),
        RESEARCH("노후 경유차 조기폐차 보조금의 대기질 개선 효과", organ="한국환경연구원"),
        RESEARCH("탄소중립 이행을 위한 재정지원 체계 연구"),
    ]

    # 1) 정상 — 질의어가 과제명에 걸림. '분석'만 겹치는 교양교육 연구는 걸러져야 함
    h1 = run("정상 — 키워드 매칭(과매칭 차단)", pool, "중소기업 데이터 분석")
    assert all("교양교육" not in x["title"] for x in h1), "일반어 '분석' 과매칭 미차단"
    print("[검증] '분석'만 겹친 무관 연구 제외 OK")

    # 2) 다른 정책 — 다른 과제가 걸림
    run("다른 정책 — 경유차", pool, "노후 경유차 조기폐차")

    # 3) 미발견 — 아무 과제명에도 안 걸림
    run("미발견 — 무관한 질의", pool, "우주항공 스타트업 세제")

    # 4) 빈 응답
    run("빈 응답 — research 0건", [], "무엇이든")

    # 5) 키 정규화 — Encoding 키를 넣어도 URL에 이중 인코딩 없이 나가는지
    cap = {}
    app.DATA_GO_KR_KEY = "aB3d%2Bxy%2Fz%3D%3D"       # Encoding 형태
    run("키 정규화 — Encoding 입력", pool, "교양교육", capture=cap)
    sk = cap["url"].split("serviceKey=")[1].split("&")[0]
    print(f"[검증] 나간 serviceKey = {sk}")
    assert "%252" not in sk, "이중 인코딩 발생(%252...)"
    assert sk == "aB3d%2Bxy%2Fz%3D%3D", "정규화 후 재인코딩 불일치"
    print("[검증] 이중 인코딩 없음 · 올바른 단일 인코딩 OK")

    print("\n모든 PRISM 시나리오 통과.")

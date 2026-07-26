"""의안 소스(ALLBILLV2 + likms 본문) 모의 검증 — 실제 API 없이 데이터 경로를 점검한다.

실행: ASSEMBLY_KEY=TESTKEY python simulation/mock_bill.py
Claude 채점(extract/judge/grade)은 CLI가 필요해 여기서 제외한다. 여기서 보는 것은
'의안명 검색 → BILL_ID → 제안이유 본문 → 구조화된 히트'까지의 데이터 흐름이다.
"""
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("ASSEMBLY_KEY", "TESTKEY")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app  # noqa: E402


def _allbillv2(eraco, rows):
    return json.dumps({"ALLBILLV2": [
        {"head": [{"list_total_count": len(rows)}, {"RESULT": {"CODE": "INFO-000"}}]},
        {"row": rows},
    ]}, ensure_ascii=False)


def _summary_html(body):
    return ("<html><head><style>.x{}</style></head><body>"
            "<h2>제안이유 및 주요내용</h2><div class='t'>" + body + "</div></body></html>")


# ── 시나리오별 가짜 응답 라우터 ────────────────────────────────────────────
SCENARIOS = {}


def run(name, list_rows, summaries, query="중소기업 데이터 바우처"):
    """list_rows: 대수→row리스트, summaries: BILL_ID→본문(None이면 likms 404)."""
    def fake(req, timeout=None):
        u = req.full_url
        if "ALLBILLV2" in u:
            eraco = "제22대" if "22" in u else "제21대"
            return _Resp(_allbillv2(eraco, list_rows.get(eraco, [])).encode())
        if "summaryPopup" in u:
            bid = u.split("billId=")[-1].split("&")[0]
            body = summaries.get(bid)
            if body is None:
                raise urllib.error.HTTPError(u, 404, "Not Found", {}, None)
            return _Resp(_summary_html(body).encode())
        raise AssertionError("예상 못한 URL: " + u)

    urllib.request.urlopen = fake
    app._DEBUG_SEEN.clear()
    hits = app._bill_lookup(query)
    print(f"\n===== {name} =====")
    print(f"의안 {len(hits)}건")
    for h in hits:
        body = h["summary"]
        print(f"  · [{h['eraco']}] {h['name']} — {h['result']} "
              f"({h['proposer'] or '제안자?'}, {h['date'] or '?'})")
        print(f"      본문 {len(body)}자: {body[:70]}{'…' if len(body) > 70 else ''}")
    return hits


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def R(bill_id, nm, eraco="제22대", result="계류", proposer="홍길동의원 등 10인",
      dt="2024-08-01"):
    return {"ERACO": eraco, "BILL_ID": bill_id, "BILL_NM": nm, "PROPOSER": proposer,
            "PPSL_DT": dt, "JRCMIT_NM": "산자중기위", "RGS_CONF_RSLT": result,
            "LINK_URL": f"https://likms.assembly.go.kr/bill/billDetail.do?billId={bill_id}"}


if __name__ == "__main__":
    # 1) 정상: 본문 있는 의안 1건
    run("정상 — 본문 확보",
        {"제22대": [R("PRC_A", "중소기업 데이터바우처 지원법안", result="임기만료폐기")],
         "제21대": []},
        {"PRC_A": ("중소기업이 외부 데이터를 구매·가공·분석하는 비용을 국가가 바우처로 "
                   "보조하여 데이터 분석 역량 격차를 해소하려는 것임. 기존 대행 컨설팅과 "
                   "달리 기업이 직접 클라우드 분석 도구를 선택해 쓰도록 공급측 채널을 신설함.")})

    # 2) 대수 2개에서 같은 의안명 → 중복 제거
    run("중복 제거 — 두 대수 같은 이름",
        {"제22대": [R("PRC_A", "데이터바우처 지원법안")],
         "제21대": [R("PRC_A2", "데이터바우처 지원법안", eraco="제21대")]},
        {"PRC_A": "본문 A", "PRC_A2": "본문 A2"})

    # 3) likms 본문 실패(404) → 제목·결과만 남는다
    run("본문 실패 — likms 404",
        {"제22대": [R("PRC_B", "소상공인 디지털전환 촉진법안", result="부결")],
         "제21대": []},
        {"PRC_B": None}, query="소상공인 디지털전환")

    # 4) 의안 미발견(빈 결과)
    run("미발견 — 검색 결과 0",
        {"제22대": [], "제21대": []}, {})

    # 5) 500자 초과 본문 → 잘림 확인
    long_body = "제안이유 " + ("가나다라마바사아자차 " * 80)  # 약 800자
    hits = run("길이 제한 — 500자 컷",
               {"제22대": [R("PRC_C", "장문 제안이유 법안")], "제21대": []},
               {"PRC_C": long_body}, query="장문 제안이유")
    assert hits and len(hits[0]["summary"]) <= app.BILL_SUMMARY_MAXLEN, "500자 컷 실패"
    print(f"\n[검증] 최대 길이 {app.BILL_SUMMARY_MAXLEN}자 이하로 잘림 OK "
          f"(실제 {len(hits[0]['summary'])}자)")
    print("\n모든 시나리오 통과.")

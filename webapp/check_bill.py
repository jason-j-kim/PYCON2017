#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 국회 의안 통로가 실제로 살아 있는지 확인한다.

키가 '설정돼 있다'와 '응답이 온다'는 다른 문제다. 만료·오타·발급기관 착오
(공공데이터포털 키를 열린국회정보에 넣는 경우)면 키는 있는데 매번 0건이 나오고,
그러면 화면에 "실행 — 0건"으로 찍혀 '조회했는데 선례가 없다'로 잘못 읽힌다.
그래서 키 유무가 아니라 **실제 응답**을 본다.

사용:  python webapp\\check_bill.py
       python webapp\\check_bill.py 기본소득
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = sys.argv[:1] + sys.argv[1:]      # app 임포트 시 인자 영향 없음

import app as A                             # noqa: E402  (경로 삽입 뒤에 임포트)

QUERY = sys.argv[1] if len(sys.argv) > 1 else "기본소득"


def main():
    print()
    if not A.ASSEMBLY_KEY:
        print("  ✗ ASSEMBLY_KEY 가 이 창에 없습니다 — ③ 통로는 미실행 상태입니다.")
        print()
        # 안내를 이 기계에 맞춰 준다. 리눅스 서버에서 keys.local.bat 을
        # 만들라고 하면 그대로 막힌다.
        if os.name == "nt":
            print("    keys.local.bat 을 만들어 키를 넣거나, 이 창에서 직접:")
            print("      set ASSEMBLY_KEY=열린국회정보_인증키")
            print("    한 뒤 다시 실행하세요. (set 은 그 창에서만 유효합니다)")
        else:
            print("    /etc/policy-eval.env 의 ASSEMBLY_KEY 에 넣고 서비스를")
            print("    다시 켜거나, 이 창에서 직접:")
            print("      export ASSEMBLY_KEY=열린국회정보_인증키")
            print("    한 뒤 다시 실행하세요. (export 는 그 창에서만 유효합니다)")
        return 1

    k = A.ASSEMBLY_KEY
    print(f"  키 있음: {k[:4]}…{k[-4:]}  (길이 {len(k)})")
    print(f"  질의어 : {QUERY}")
    print("  열린국회정보(open.assembly.go.kr) 조회 중 …")
    print()

    # 1단계: 원 API를 한 번 직접 두드려 '연결·인증'과 '검색결과 없음'을 가른다.
    # _bill_lookup 은 통신 오류를 삼키고 빈 목록을 주므로 그것만 보면 둘이 섞인다.
    import urllib.parse
    params = {"KEY": k, "Type": "json", "pIndex": 1, "pSize": 3,
              "ERACO": A.ERACO_TERMS[0], "BILL_NM": QUERY}
    try:
        data = A._http_get_data(A.ALLBILL_BASE + "?" + urllib.parse.urlencode(params))
    except Exception as e:
        print(f"  ✗ 서버에 닿지 못했습니다: {e}")
        print()
        print("    인터넷 연결 또는 사내 방화벽·프록시를 확인하세요.")
        print("    이 경우 키와 무관하며, 서버는 이 통로를 '0건'으로 처리합니다.")
        return 1
    raw = A._as_rows(A._find_key(data, "row"))
    msg = str(data)
    for bad in ("INVALID", "인증", "등록되지", "서비스키", "DEADLINE", "LIMITED"):
        if bad in msg and not raw:
            print(f"  ✗ 키가 거부되었습니다. 응답: {msg[:300]}")
            print()
            print("    열린국회정보(open.assembly.go.kr)에서 발급한 키가 맞는지")
            print("    확인하세요. 공공데이터포털(data.go.kr) 키와는 다릅니다.")
            return 1
    print(f"  ✔ 연결·인증 정상 — 원 API 응답 {len(raw)}행")
    print()

    try:
        hits = A._bill_lookup(QUERY)
    except Exception as e:
        print(f"  ✗ 호출 중 예외: {e}")
        return 1

    if hits:
        print(f"  ✔ 통로 정상 — {len(hits)}건")
        for h in hits:
            print(f"     · {h['name']}  [{h['result']}] {h.get('date') or ''}")
        print()
        print("    이 키로 서버를 띄우면 네 통로가 모두 켜집니다.")
        return 0

    print("  △ 통로는 살아 있으나 이 질의어로는 0건입니다.")
    print()
    print("    연결과 인증은 위에서 확인됐으므로 키 문제가 아닙니다.")
    print("    질의어에 해당하는 의안이 없거나, 관련성 필터가 걸러낸 것입니다.")
    print("    다른 말로 확인해 보세요:  python webapp\\check_bill.py 국민건강보험법")
    return 2


def hold():
    """창이 곧바로 닫히지 않게 붙잡는다. 더블클릭으로 열면 결과가 순식간에
    사라져 아무 소용이 없다."""
    import os
    if os.name != "nt" or not sys.stdin.isatty():
        return
    try:
        input("\n  Enter 를 누르면 닫힙니다. ")
    except Exception:
        pass


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    except KeyboardInterrupt:
        print("\n  중단했습니다.")
    except Exception as e:
        import traceback
        print("\n  진단 도구 자체가 멈췄습니다 — " + repr(e))
        print(traceback.format_exc())
    finally:
        hold()
    sys.exit(rc)

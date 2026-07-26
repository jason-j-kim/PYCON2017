"""PRISM만 직접 호출해 원인을 진단한다(엔진·캐시 우회).

준비: call keys.local.bat 을 먼저 한 창에서.
사용: python simulation\\diag_prism.py 무용
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app  # noqa: E402

term = sys.argv[1] if len(sys.argv) > 1 else "무용"

print("=" * 55)
key = app.DATA_GO_KR_KEY
print(f"DATA_GO_KR_KEY 실림? : {'예' if key else '아니오 — 빈 값!'} (길이 {len(key)})")
if key:
    print(f"  키 앞 6글자: {key[:6]}…  (전체는 안 찍음)")
print(f"PRISM_BASE          : {app.PRISM_BASE}")
print(f"검색어 '{term}' → searchword 후보 : {app._prism_search_terms(term)}")
print("-" * 55)
print("PRISM 직접 호출 결과:")
try:
    hits = app._prism_lookup(term)
    print(f"  건수: {len(hits)}")
    for h in hits:
        print(f"   · {h.get('title')} | {h.get('org')} | {h.get('period')}")
    if not hits:
        print("  (0건 — 위에 [축B 디버그:prism-…] 줄이 떴다면 그 totalCount 확인)")
except Exception:
    print("  ▼▼ 예외 발생(이게 '호출 자체 없음'의 진짜 원인) ▼▼")
    traceback.print_exc()
print("=" * 55)

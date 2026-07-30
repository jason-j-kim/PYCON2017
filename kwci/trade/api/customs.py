#!/usr/bin/env python3
"""
KWCI L1 — 관세청 무역통계 커넥터 (총액·총량의 정본)

공공데이터포털(data.go.kr)의 관세청 수출입 무역통계 API를 쓴다.
품목(HS) x 국가 x 기간으로 수출금액·중량을 받아, KWCI L1의 분자를 만든다.

오퍼레이션명·파라미터·응답 필드는 문서와 실제 동작이 어긋나는 사례가 흔하다.
--probe 로 후보를 실제 호출해 확인하고 통과한 것만 probe_customs.json 에 기록한다.

키: keys.local.bat 의 DATA_GO_KR_KEY (Comtrade 커넥터와 같은 방식으로 찾는다)

사용법
------
  python customs.py --probe      # 오퍼레이션·파라미터·응답필드 실측
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests가 필요합니다:  pip install requests")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comtrade import _from_keyfile                      # noqa: E402

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
ROOT = TRADE.parent.parent
PROBE_OUT = HERE / "probe_customs.json"

KEY_NAMES = ("DATA_GO_KR_KEY", "DATA_GO_KR_SERVICE_KEY", "CUSTOMS_KEY")
TIMEOUT = 60

# 후보 엔드포인트. 공공데이터포털은 같은 통계를 여러 오퍼레이션으로 내보내고
# 경로가 개편된 이력이 있어, 하나로 단정하지 않고 순서대로 시험한다.
ENDPOINTS = [
    ("nitemtrade",
     "품목별 국가별 수출입실적",
     "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"),
    ("nitemtrade_http",
     "품목별 국가별 (http)",
     "http://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"),
    ("Nitemtrade",
     "품목별 국가별 (대문자 경로)",
     "https://apis.data.go.kr/1220000/Nitemtrade/getNitemtradeList"),
    ("itemtrade",
     "품목별 수출입실적 (국가 미지정)",
     "https://apis.data.go.kr/1220000/itemtrade/getitemtradeList"),
]

# 라면 · 베트남 · 2024년 1~3월로 시험한다.
SAMPLE = dict(hsSgn="190230", cntyCd="VN", strtYymm="202401", endYymm="202403")

# 응답에서 찾아야 할 값들. 이름이 다를 수 있어 후보를 둔다.
FIELD_HINTS = {
    "수출금액": ("expDlr", "expUsdAmt", "expAmt"),
    "수출중량": ("expWgt", "expWgtAmt"),
    "수입금액": ("impDlr", "impUsdAmt"),
    "국가":     ("cntyCd", "cntyNm", "statCd"),
    "품목":     ("hsCd", "hsSgn", "statKor"),
    "기간":     ("year", "yymm", "prdCd"),
}


def find_key() -> str:
    import os
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n].strip()
    for path in (ROOT / "keys.local.bat", ROOT / "keys.local",
                 TRADE / ".env", ROOT / ".env"):
        vals = _from_keyfile(path)
        for n in KEY_NAMES:
            if vals.get(n):
                print(f"  키 출처: {path.name}")
                return vals[n]
    sys.exit(
        "DATA_GO_KR_KEY 를 찾지 못했습니다.\n"
        f"  {ROOT / 'keys.local.bat'} 의  set DATA_GO_KR_KEY=<키>  를 확인하세요."
    )


def parse_xml(text: str):
    """관세청은 type=json 을 무시하고 XML을 돌려준다. 태그->값 사전으로 편다."""
    if not text.lstrip().startswith("<"):
        return None
    try:
        from defusedxml import ElementTree as ET
    except ImportError:
        import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(text)
    except Exception:
        return None

    def walk(el):
        kids = list(el)
        if not kids:
            return (el.text or "").strip()
        out: dict = {}
        for k in kids:
            v = walk(k)
            if k.tag in out:
                if not isinstance(out[k.tag], list):
                    out[k.tag] = [out[k.tag]]
                out[k.tag].append(v)
            else:
                out[k.tag] = v
        return out
    return {root.tag: walk(root)}


def flatten(obj, out: dict | None = None) -> dict:
    """응답 구조가 제각각이라 잎 노드를 평평하게 펴서 필드를 찾는다."""
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                flatten(v, out)
            else:
                out.setdefault(k, v)
    elif isinstance(obj, list):
        for v in obj[:3]:
            flatten(v, out)
    return out


def probe() -> int:
    key = find_key()
    print(f"  키 길이 {len(key)}자\n")
    result: dict = {"sample": SAMPLE, "tests": {}, "endpoint": None}

    for name, desc, url in ENDPOINTS:
        params = {"serviceKey": key, "type": "json", **SAMPLE}
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            st, body = r.status_code, r.text or ""
        except requests.RequestException as e:
            print(f"  x {name:<18} {type(e).__name__}")
            result["tests"][name] = {"error": type(e).__name__}
            continue

        payload, fmt = None, None
        try:
            payload, fmt = r.json(), "json"
        except ValueError:
            payload, fmt = parse_xml(body), "xml"   # 관세청은 XML로 응답한다

        flat = flatten(payload) if payload else {}
        # 공공데이터포털은 오류도 200으로 주고 본문에 코드를 넣는다.
        # 성공 판정은 resultCode 로만 한다 — resultMsg 는 "정상서비스."(한글)와
        # "NORMAL SERVICE."(영문)가 섞여 나와 문자열로 가리면 성공을 오류로 읽는다.
        code = str(flat.get("resultCode", "")).strip()
        if code and code not in ("00", "0"):
            err = f"resultCode={code} {flat.get('resultMsg', '')}"[:100]
        else:
            err = next((str(flat[k]) for k in ("returnAuthMsg", "errMsg")
                        if flat.get(k)), None)
        has_data = any(h in flat for hints in FIELD_HINTS.values() for h in hints)

        mark = "o" if (st == 200 and has_data and not err) else \
               ("~" if st == 200 else "x")
        print(f"  {mark} {name:<18} {desc}")
        print(f"      HTTP {st}" + (f"  오류: {err[:70]}" if err else "")
              + f"  [{fmt}]"
              + ("" if payload else f"  {body[:70]}"))

        result["tests"][name] = {
            "status": st, "format": fmt,
            "error": err, "keys": sorted(flat)[:40],
        }
        if payload and not has_data:
            print(f"      응답 태그: {sorted(flat)[:14]}")

        if mark == "o":
            print("      응답 필드 확인:")
            for label, cands in FIELD_HINTS.items():
                hit = next((c for c in cands if c in flat), None)
                shown = f"{hit} = {flat[hit]}" if hit else "못 찾음"
                print(f"        {label:<8} {shown}")
            result["tests"][name]["fields"] = {
                label: next((c for c in cands if c in flat), None)
                for label, cands in FIELD_HINTS.items()
            }
            result["tests"][name]["sample_row"] = {
                k: str(v) for k, v in list(flat.items())[:25]}
            if result["endpoint"] is None:
                result["endpoint"] = {"name": name, "url": url}
        time.sleep(0.6)

    # 한 호출이 얼마나 담는지 재서 수집 규모를 정한다.
    ep = result["endpoint"]
    if ep:
        print("\n[수집 범위] 한 호출이 담는 양")
        cover = [
            ("국가 무관", dict(hsSgn="190230", strtYymm="202401", endYymm="202412")),
            ("전기간 8년", dict(hsSgn="190230", strtYymm="201801", endYymm="202512")),
            ("HS 4자리", dict(hsSgn="1902", strtYymm="202401", endYymm="202412")),
        ]
        for label, extra in cover:
            try:
                rr = requests.get(ep["url"],
                                  params={"serviceKey": key, **extra},
                                  timeout=TIMEOUT)
                fl = flatten(parse_xml(rr.text) or {})
                n = fl.get("totalCount", "?")
                print(f"    {label:<12} totalCount={n}")
                result.setdefault("coverage", {})[label] = str(n)
            except requests.RequestException as e:
                print(f"    {label:<12} {type(e).__name__}")
            time.sleep(0.6)

    PROBE_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"\n= {PROBE_OUT.name} 기록")

    if result["endpoint"]:
        print(f"\n엔드포인트 '{result['endpoint']['name']}' 확인 — 수집 진행 가능합니다.")
        return 0
    print("\n! 작동하는 엔드포인트를 찾지 못했습니다.")
    print("  probe_customs.json 의 tests 를 보여주시면 경로를 다시 잡겠습니다.")
    print("  (data.go.kr 에서 '관세청 무역통계' 활용신청 승인 여부도 확인해 주세요)")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true",
                    help="엔드포인트·파라미터·응답필드 실측")
    args = ap.parse_args()
    if args.probe:
        return probe()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

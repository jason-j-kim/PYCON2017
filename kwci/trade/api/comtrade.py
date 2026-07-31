#!/usr/bin/env python3
"""
KWCI L1 — UN Comtrade 커넥터 (S2 RCA / S4 초과점유율·단가프리미엄의 분모)

Comtrade가 필요한 이유는 하나다. 관세청은 "한국이 얼마를 팔았나"(분자)만 준다.
RCA·초과점유율·단가프리미엄은 전부 "세계는 얼마를 팔았나"(분모)가 있어야
계산된다. 그 분모를 여기서 가져온다.

    RCA_j = (한국의 j 수출 / 한국 총수출) ÷ (세계의 j 수출 / 세계 총수출)

세계 총수출을 어떤 쿼리로 얻는지는 문서와 실제 동작이 어긋날 수 있어
추측하지 않는다. --probe 로 후보 전략을 실제 호출해 확인하고, 통과한
전략만 기록해서 그것으로 수집한다.

키
--
아래 순서로 찾는다.
  1) 환경변수 COMTRADE_KEY 또는 COMTRADE_SUBSCRIPTION_KEY
  2) 저장소 루트의 keys.local (Windows .bat 형식의 set NAME=VALUE)
  3) kwci/trade/.env  (NAME=VALUE)

사용법
------
  python comtrade.py --probe        # 키 확인 + 쿼리 전략 실측 -> probe.json
  python comtrade.py --probe-scale  # 수집 규모 실측 -> probe_scale.json
  python comtrade.py --quota        # 남은 호출 여유 확인
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests가 필요합니다:  pip install requests")

HERE = Path(__file__).resolve().parent          # kwci/trade/api
TRADE = HERE.parent                             # kwci/trade
ROOT = TRADE.parent.parent                      # 저장소 루트
CACHE = TRADE / "data" / "raw" / "comtrade"
PROBE_OUT = HERE / "probe.json"

BASE = "https://comtradeapi.un.org/data/v1/get"
KOREA = 410            # reporterCode
WORLD_PARTNER = 0      # partnerCode=0 => World
TIMEOUT = 90

KEY_NAMES = ("COMTRADE_KEY", "COMTRADE_SUBSCRIPTION_KEY", "COMTRADE_API_KEY")


# ------------------------------------------------------------------ 키

def _from_keyfile(path: Path) -> dict[str, str]:
    """keys.local(.bat 의 set NAME=VALUE) 및 .env 형식을 함께 읽는다."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip().lstrip("@")
        if not line or line.startswith(("#", "::", "rem ")):
            continue
        m = re.match(r"(?:set\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line,
                     re.IGNORECASE)
        if m:
            out[m.group(1).upper()] = m.group(2).strip().strip('"').strip("'")
    return out


def find_key() -> str:
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n].strip()
    # keys.local.bat 이 실제 파일명이다(탐색기는 .bat 를 숨긴다). 둘 다 본다.
    for path in (ROOT / "keys.local.bat", ROOT / "keys.local",
                 TRADE / ".env", ROOT / ".env"):
        vals = _from_keyfile(path)
        for n in KEY_NAMES:
            if vals.get(n):
                print(f"  키 출처: {path.name}")
                return vals[n]
    sys.exit(
        "Comtrade 키를 찾지 못했습니다. 다음 중 하나로 설정하세요:\n"
        "  set COMTRADE_KEY=<발급받은 키>            (현재 세션)\n"
        f"  {ROOT / 'keys.local'} 에  set COMTRADE_KEY=<키>  추가\n"
        f"  {TRADE / '.env'} 에  COMTRADE_KEY=<키>  추가"
    )


# ------------------------------------------------------------------ 호출

class Comtrade:
    def __init__(self, key: str) -> None:
        self.key = key
        self.s = requests.Session()
        self.s.headers.update({
            "Ocp-Apim-Subscription-Key": key,
            "User-Agent": "KWCI-L1/0.1",
        })
        self.calls = 0
        self.last_headers: dict[str, str] = {}

    def get(self, freq: str = "A", timeout: int | None = None,
            retry: int = 2, **params) -> tuple[int, dict | None, str]:
        """(status, payload, note). 예외를 던지지 않고 상태를 돌려준다.

        cmdCode=TOTAL 처럼 전 신고국을 받는 질의는 응답이 수 MB라 기본
        타임아웃으로는 끊긴다. 호출부가 timeout 을 올려 잡을 수 있게 한다.
        """
        url = f"{BASE}/C/{freq}/HS"
        r = None
        for attempt in range(retry + 1):
            try:
                r = self.s.get(url, params=params,
                               timeout=timeout or TIMEOUT)
                break
            except requests.RequestException as e:
                if attempt == retry:
                    return 0, None, f"{type(e).__name__} (재시도 {retry}회)"
                time.sleep(2.0 * (attempt + 1))
        self.calls += 1
        self.last_headers = {k.lower(): v for k, v in r.headers.items()}

        if r.status_code != 200:
            body = (r.text or "")[:160].replace("\n", " ")
            return r.status_code, None, body
        try:
            return 200, r.json(), ""
        except ValueError:
            return 200, None, "JSON 파싱 실패"

    @staticmethod
    def rows(payload: dict | None) -> list[dict]:
        if not payload:
            return []
        for k in ("data", "results", "dataset"):
            v = payload.get(k)
            if isinstance(v, list):
                return v
        return []

    def limit_note(self) -> str:
        h = self.last_headers
        keys = [k for k in h if "ratelimit" in k or "quota" in k or "remaining" in k]
        return "  ".join(f"{k}={h[k]}" for k in sorted(keys)) or "(한도 헤더 없음)"


# ------------------------------------------------------------------ 프로브

# RCA 분모(세계 총수출)를 얻는 후보 전략들. 어느 것이 실제로 되는지 모르므로
# 전부 시도하고 결과를 기록한다. 비용(호출 수)이 낮은 순으로 둔다.
WORLD_STRATEGIES = [
    ("reporter_world",
     "reporterCode=0 이 세계 집계를 돌려주는가 (가장 싸다)",
     dict(reporterCode=0, partnerCode=WORLD_PARTNER, flowCode="X")),
    ("all_reporters",
     "reporterCode 생략 시 전 신고국을 돌려주는가 (합산해서 씀)",
     dict(partnerCode=WORLD_PARTNER, flowCode="X")),
    ("world_imports",
     "세계 수입(미러)으로 대체 가능한가 (partner=0, flow=M)",
     dict(reporterCode=0, partnerCode=WORLD_PARTNER, flowCode="M")),
]

PERIOD = "2023"
SAMPLE_HS = "190230"                      # 라면
BATCH_HS = "190230,200599,330499,620342"  # 라면·김치·화장품·의류


def probe() -> int:
    key = find_key()
    api = Comtrade(key)
    print(f"  키 길이 {len(key)}자  ...{key[-4:]}\n")

    result: dict = {"period": PERIOD, "tests": {}, "world_strategy": None}

    def run(name: str, desc: str, **params) -> list[dict]:
        st, payload, note = api.get(**params)
        rows = api.rows(payload)
        ok = st == 200 and bool(rows)
        mark = "o" if ok else ("~" if st == 200 else "x")
        print(f"  {mark} {name:<18} {desc}")
        print(f"      HTTP {st}  행 {len(rows):,}"
              + (f"  {note[:80]}" if note else ""))
        result["tests"][name] = {"status": st, "rows": len(rows),
                                 "note": note[:200], "params": {k: str(v)
                                                                for k, v in params.items()}}
        if rows:
            r0 = rows[0]
            keep = {k: r0.get(k) for k in
                    ("reporterCode", "reporterDesc", "partnerCode", "cmdCode",
                     "flowCode", "period", "primaryValue", "netWgt", "qty")
                    if k in r0}
            print(f"      표본 {keep}")
            result["tests"][name]["sample"] = {k: str(v) for k, v in keep.items()}
        time.sleep(1.0)      # 무료 티어 배려
        return rows

    print("[1] 기본 호출 — 한국의 라면 수출")
    run("korea_single", "reporter=410, cmd=190230, partner=World",
        reporterCode=KOREA, period=PERIOD, partnerCode=WORLD_PARTNER,
        cmdCode=SAMPLE_HS, flowCode="X")

    print("\n[2] 한국 총수출 (RCA 분모 중 하나)")
    run("korea_total", "cmdCode=TOTAL",
        reporterCode=KOREA, period=PERIOD, partnerCode=WORLD_PARTNER,
        cmdCode="TOTAL", flowCode="X")

    print("\n[3] 배치 — cmdCode 를 콤마로 묶을 수 있는가")
    rows = run("batch_cmd", f"cmdCode={BATCH_HS}",
               reporterCode=KOREA, period=PERIOD, partnerCode=WORLD_PARTNER,
               cmdCode=BATCH_HS, flowCode="X")
    got = {str(r.get("cmdCode")) for r in rows}
    result["tests"]["batch_cmd"]["distinct_cmd"] = sorted(got)
    print(f"      회수된 품목 {len(got)}종 / 요청 4종")

    print("\n[4] 다기간 — period 를 콤마로 묶을 수 있는가")
    rows = run("batch_period", "period=2022,2023",
               reporterCode=KOREA, period="2022,2023",
               partnerCode=WORLD_PARTNER, cmdCode=SAMPLE_HS, flowCode="X")
    result["tests"]["batch_period"]["distinct_period"] = sorted(
        {str(r.get("period")) for r in rows})

    print("\n[5] RCA 분모 — 세계 총수출을 얻는 전략")
    for name, desc, extra in WORLD_STRATEGIES:
        rows = run(name, desc, period=PERIOD, cmdCode=SAMPLE_HS, **extra)
        if rows and result["world_strategy"] is None:
            result["world_strategy"] = name
            result["tests"][name]["reporters"] = len(
                {str(r.get("reporterCode")) for r in rows})

    print(f"\n[한도] {api.limit_note()}")
    print(f"[호출] 이번 프로브에서 {api.calls}회")

    result["limit_headers"] = api.last_headers
    result["calls"] = api.calls
    PROBE_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"\n= {PROBE_OUT.name} 기록")

    ws = result["world_strategy"]
    if ws:
        print(f"\n세계 총수출 전략: '{ws}' 채택 가능 — S2(RCA) 진행 가능합니다.")
    else:
        print("\n! 세계 총수출을 얻는 전략을 찾지 못했습니다.")
        print("  probe.json 의 tests 를 보여주시면 다른 경로를 설계하겠습니다.")
    return 0 if ws else 1


def probe_scale() -> int:
    """수집 규모를 재는 2단계 프로브.

    all_reporters 전략은 품목·연도당 2,300여 신고국 행을 돌려준다.
    928품목 x 8년이면 1,700만 행이라 그대로는 무료 티어로 불가능하다.
    설계를 정하려면 세 가지를 실측해야 한다.
      A) 서버가 신고국을 합산해 주는가 (aggregateBy) — 되면 비용이 수천분의 1
      B) 한 호출에 품목을 몇 개까지 묶을 수 있고 몇 행/몇 바이트가 오는가
      C) 응답이 잘리는가 (묶음 결과가 개별 결과의 합과 맞는가)
    """
    api = Comtrade(find_key())
    out: dict = {"tests": {}}

    def call(label: str, **params) -> tuple[list[dict], int]:
        t0 = time.time()
        st, payload, note = api.get(**params)
        rows = api.rows(payload)
        size = len(json.dumps(payload)) if payload else 0
        dt = time.time() - t0
        print(f"    HTTP {st}  행 {len(rows):>7,}  {size/1e6:>6.2f}MB  {dt:>5.1f}s"
              + (f"  {note[:60]}" if note else ""))
        out["tests"][label] = {"status": st, "rows": len(rows),
                               "bytes": size, "seconds": round(dt, 1),
                               "note": note[:200]}
        time.sleep(1.5)
        return rows, size

    print("[A] 서버측 집계 — 신고국을 합쳐서 주는가")
    agg_ok = False
    for mode in ("cmdCode", "cmdCode,period"):
        print(f"  aggregateBy={mode}")
        rows, _ = call(f"aggregate_{mode.replace(',', '_')}",
                       period=PERIOD, cmdCode=SAMPLE_HS,
                       partnerCode=WORLD_PARTNER, flowCode="X",
                       aggregateBy=mode, breakdownMode="aggregate")
        if rows and len(rows) <= 5:
            agg_ok = True
            print(f"      -> 집계 성공. 표본 primaryValue="
                  f"{rows[0].get('primaryValue')}")
            break

    print("\n[B] 품목 묶음 규모 — 한 호출에 몇 개까지")
    import csv as _csv
    master = TRADE / "master" / "item_master.csv"
    if master.exists():
        with master.open(encoding="utf-8") as f:
            codes = [r["hs2022"] for r in _csv.DictReader(f)]
    else:
        codes = [SAMPLE_HS, "200599", "330499", "620342"] * 10
    print(f"  후보 {len(codes):,}개 중 앞에서 잘라 시험")

    per_item = None
    for n in (1, 10, 40):
        if n > len(codes):
            break
        print(f"  품목 {n}개")
        rows, size = call(f"chunk_{n}", period=PERIOD,
                          cmdCode=",".join(codes[:n]),
                          partnerCode=WORLD_PARTNER, flowCode="X")
        got = len({str(r.get("cmdCode")) for r in rows})
        print(f"      회수 품목 {got}/{n}")
        out["tests"][f"chunk_{n}"]["distinct_cmd"] = got
        if n == 1 and rows:
            per_item = len(rows)
        if per_item and rows and len(rows) < per_item * n * 0.5:
            print(f"      ! 응답이 잘린 것으로 보입니다 "
                  f"(예상 ~{per_item*n:,}행)")
            out["tests"][f"chunk_{n}"]["truncated"] = True

    print("\n[C] 세계 총수출 (RCA 분모의 분모)")
    rows, _ = call("world_total", period=PERIOD, cmdCode="TOTAL",
                   partnerCode=WORLD_PARTNER, flowCode="X")
    total = sum(float(r.get("primaryValue") or 0) for r in rows)
    print(f"      신고국 {len(rows):,}개 합계 ${total/1e12:.2f}조")
    out["tests"]["world_total"]["sum_usd"] = total

    print(f"\n[한도] {api.limit_note()}")
    print(f"[호출] {api.calls}회")

    # 수집 계획 추정
    print("\n[수집 계획 추정]")
    if agg_ok:
        print("  aggregateBy 사용 가능 -> 품목당 1행. 928품목 x 3년을"
              "\n  묶음 호출 수십 회로 끝낼 수 있습니다.")
        out["plan"] = "aggregate"
    elif per_item:
        best = max((n for n in (1, 10, 40)
                    if out["tests"].get(f"chunk_{n}", {}).get("rows")
                    and not out["tests"][f"chunk_{n}"].get("truncated")),
                   default=1)
        bytes_1y = out["tests"][f"chunk_{best}"]["bytes"] / best * len(codes)
        print(f"  서버 집계 불가 -> 신고국 행을 받아 직접 합산합니다.")
        print(f"  묶음 {best}개 기준: 1년치 약 {len(codes)//best + 1:,}회 호출, "
              f"{bytes_1y/1e9:.1f}GB")
        print(f"  RCA는 3개년(2022~2024) 평균으로 산출하면 "
              f"약 {(len(codes)//best + 1) * 3:,}회.")
        out["plan"] = f"sum_reporters(chunk={best})"
    else:
        print("  ! 규모를 재지 못했습니다. probe_scale.json 을 보여주세요.")
        out["plan"] = None

    p = HERE / "probe_scale.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    print(f"\n= {p.name} 기록")
    return 0


def quota() -> int:
    api = Comtrade(find_key())
    st, _, note = api.get(reporterCode=KOREA, period=PERIOD,
                          partnerCode=WORLD_PARTNER, cmdCode=SAMPLE_HS,
                          flowCode="X")
    print(f"  HTTP {st}  {note[:120]}")
    print(f"  {api.limit_note()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true",
                    help="키 확인 + 쿼리 전략 실측 (호출 ~8회)")
    ap.add_argument("--probe-scale", action="store_true", dest="probe_scale",
                    help="수집 규모 실측 — 서버측 집계·묶음 한계·응답 크기")
    ap.add_argument("--quota", action="store_true", help="한도 헤더만 확인")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    if args.quota:
        return quota()
    if args.probe_scale:
        return probe_scale()
    if args.probe:
        return probe()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

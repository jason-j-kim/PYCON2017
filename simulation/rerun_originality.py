"""기존 문답(transcript)을 그대로 불러와 축 B(선례 조사)만 다시 채점한다.

새 문답을 다시 칠 필요 없이, 저장된 정책 세션에 대해 재정·PRISM·의안 조회와
독창성 판정을 새 코드로 재실행하고 결과를 DB에 저장(웹에서도 갱신됨)한다.

준비: 키가 필요하므로 keys.local.bat을 먼저 불러온 창에서 실행한다.
  Windows:
      call keys.local.bat
      python simulation\\rerun_originality.py            (가장 최근 정책 세션)
      python simulation\\rerun_originality.py 52e3b565ed89 (세션 ID 지정)

Claude 채점 단계는 `claude -p` CLI를 쓰므로 Pro 로그인된 PC에서 돌아간다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import app, db  # noqa: E402


def _latest_policy_sid():
    with db._conn() as conn:
        row = conn.execute(
            "SELECT id, idea FROM sessions WHERE profile='정책' "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
    return row


def main():
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    if not sid:
        row = _latest_policy_sid()
        if not row:
            print("정책 세션이 없습니다. 먼저 /policy에서 문답을 하나 진행하세요.")
            return
        sid, idea = row[0], row[1]
        print(f"가장 최근 정책 세션 사용: {sid}")
        print(f"아이디어: {idea[:80]}...")
    session = db.get_session(sid)
    if not session:
        print(f"세션을 찾을 수 없습니다: {sid}")
        return

    transcript = "\n\n".join(app._transcript_log(sid))
    if not transcript.strip():
        print("이 세션에는 문답 기록이 없습니다.")
        return

    fiscal_fn = app._fiscal_local_search if app._fiscal_available() else None
    prism_fn = app._prism_lookup if app.DATA_GO_KR_KEY else None
    bill_fn = app._bill_lookup if app.ASSEMBLY_KEY else None
    print("\n소스 가용:",
          f"재정={'O' if fiscal_fn else 'X'}",
          f"PRISM={'O' if prism_fn else 'X(키없음)'}",
          f"의안={'O' if bill_fn else 'X(키없음)'}")

    # 재현성: 세션별로 명세(검색어)를 캐시해 재사용한다. "--fresh"면 새로 추출.
    cache_dir = Path(__file__).resolve().parent / "spec_cache"
    cache_dir.mkdir(exist_ok=True)
    cache_fp = cache_dir / f"{sid}.json"
    spec = judge = None
    if "--fresh" not in sys.argv and cache_fp.exists():
        cached = json.loads(cache_fp.read_text(encoding="utf-8"))
        spec, judge = cached.get("spec"), cached.get("judge")
        print(f"저장된 명세 재사용(재현성): {cache_fp.name}")
        print(f"의안 질의어: {spec.get('queries', {}).get('bill')}")
    else:
        print("명세를 새로 추출합니다(첫 실행 또는 --fresh).")
    print("재채점 중… (조회 + Claude 판정, 30초~2분)\n")

    result = app.engine.originality_axis(
        transcript, fiscal_fn, prism_fn, bill_fn, spec=spec, judge=judge)
    db.save_originality(sid, result)          # 웹에서도 갱신되도록 저장
    if spec is None:                          # 첫 추출이면 명세를 캐시에 저장
        cache_fp.write_text(json.dumps(
            {"spec": result["spec"], "judge": result["judge"]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"명세 저장됨(다음부터 재사용): {cache_fp.name}")

    o, lk = result["originality"], result.get("lookup")
    print("=" * 60)
    print(f"실질 독창성 : {o['band']}   (확신도 {o.get('confidence','?')})")
    print(f"판정 근거   : {o.get('reasoning','')}")
    if o.get("retraction_condition"):
        print(f"철회 조건   : {o['retraction_condition']}")
    print("-" * 60)
    if lk is None:
        print("커버리지    : 외부 조회 미실행")
    else:
        f, p, b = lk.get("fiscal", []), lk.get("prism", []), lk.get("bill", [])
        prof = lk.get("profile", {})
        print(f"커버리지    : 재정 {len(f)}건 · PRISM {len(p)}건 · 국회 의안 {len(b)}건")
        print(f"집행/검토/입법 = {prof.get('exec')}/{prof.get('review')}/{prof.get('law')}")
        for h in b:
            body = (h.get("summary") or "").strip()
            print(f"  · [의안] {h.get('name')} — {h.get('result')} "
                  f"({h.get('proposer') or '제안자?'})")
            print(f"      본문: {body[:90] + '…' if body else '(없음)'}")
        for h in f[:3]:
            print(f"  · [재정] {h.get('name')}")
        for h in p[:3]:
            print(f"  · [연구] {h.get('title')}")
    print("-" * 60)
    for ev in o.get("evidence", []):
        print(f"  [{ev.get('grade')}·{ev.get('source')}] {ev.get('text')}")
    print("=" * 60)
    print(f"\n저장 완료. 웹에서 이 세션({sid})을 열면 갱신된 결과가 보입니다.")


if __name__ == "__main__":
    main()

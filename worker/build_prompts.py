#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""축 B 시스템 프롬프트를 web/api/evaluate.py에서 추출해 worker/src/prompts.js 생성.

프롬프트를 손으로 옮겨 적으면 원본과 어긋난다. Vercel판이 실제로 쓰는 문자열을
그대로 뽑아 Worker가 같은 프롬프트를 쓰도록 한다.

사용:  python worker/build_prompts.py
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "api" / "evaluate.py"
OUT = Path(__file__).resolve().parent / "src" / "prompts.js"

WANT = ["SPEC_EXTRACTOR_SYSTEM", "PRECEDENT_JUDGE_SYSTEM",
        "ORIGINALITY_GRADER_SYSTEM", "_SPEC_SCHEMA"]


def main():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in WANT:
                found[t.id] = ast.literal_eval(node.value)

    missing = [w for w in WANT if w not in found]
    if missing:
        raise SystemExit(f"추출 실패: {missing}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "// 자동 생성 — 직접 수정하지 말 것.",
        "// 원본: web/api/evaluate.py   재생성: python worker/build_prompts.py",
        "",
    ]
    for name in ["SPEC_EXTRACTOR_SYSTEM", "PRECEDENT_JUDGE_SYSTEM", "ORIGINALITY_GRADER_SYSTEM"]:
        lines.append(f"export const {name} = {json.dumps(found[name], ensure_ascii=False)};")
        lines.append("")
    lines.append(f"export const SPEC_SCHEMA = {json.dumps(found['_SPEC_SCHEMA'], ensure_ascii=False, indent=2)};")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"생성: {OUT}  ({OUT.stat().st_size/1024:.1f}KB)")
    for name in WANT:
        v = found[name]
        n = len(v) if isinstance(v, str) else len(json.dumps(v))
        print(f"  {name}: {n:,}자")


if __name__ == "__main__":
    main()

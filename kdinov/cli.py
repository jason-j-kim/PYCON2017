"""CLI.

  1) ??? ??? (1?, ??? ??)
     python -m kdinov mirror --keys-env kdi_keys.env --full --db kdi.sqlite

  2) ? ??/?? ?? ?? (JSONL/JSON/TXT/CSV)
     python -m kdinov ingest --db kdi.sqlite --file external.csv --source manual

  3) DB ?? (???? ???, ?? ?? ??)
     python -m kdinov search --db kdi.sqlite --idea idea.json

  4) ?? (???? ???, ?? ?? ??)
     python -m kdinov judge --db kdi.sqlite --idea idea.json -o report.md

  5) ? ???
     python -m kdinov web --db kdi.sqlite

  6) ?? ??? ??
     python -m kdinov probe --keys-env kdi_keys.env --cd A
"""
from __future__ import annotations
import argparse, json, os, sys
from .model import Idea
from .sources import (Store, mirror, mirror_by_terms, load_file, load_env_file,
                      key_for_cd, key_status, normalize_cds, API, CORPORA)
from .search import format_hits, search_docs, terms_from_idea, terms_from_query
from .verdict import assess, check_recall, summarize
from .report import to_markdown, to_console
from .web import main as web_main


def _idea(path: str) -> Idea:
    with open(path, encoding="utf-8") as fh:
        return Idea.from_dict(json.load(fh))


def cmd_mirror(a):
    load_env_file(a.keys_env)
    cd = "ABCDEF" if a.full else normalize_cds(a.cd)
    missing = [c for c, ok, _names in key_status(cd, a.key) if not ok]
    if missing:
        print("? ???? ??? ??:", "".join(missing))
    st = Store(a.db)
    if a.terms:
        idea = _idea(a.idea)
        terms = [t for ax in idea.axes for t, _k, _w in ax.terms()]
        docs = mirror_by_terms(a.key, terms, cd)
        print("??: ???? ?? ? ???? ????? ???? ??")
    else:
        docs = mirror(a.key, cd, debug=a.debug)
    if not docs:
        sys.exit("??? ??? ????. ?? cd ??? ??????.")
    print(f"{st.put(docs)}? ?? ? {a.db} (?? {st.count()}?)")


def cmd_ingest(a):
    path = a.file or a.jsonl or a.csv or a.txt
    if not path:
        sys.exit("??? ??? ????. --file, --jsonl, --csv, --txt ? ??? ??????.")
    st = Store(a.db)
    docs = load_file(path, a.source)
    if not docs:
        sys.exit(f"{path} ?? ?? ??? ??? ?? ?????.")
    print(f"{st.put(docs)}? ?? ? {a.db} (?? {st.count()}?)")


def cmd_search(a):
    st = Store(a.db)
    corpus = st.all(a.source)
    if not corpus:
        sys.exit(f"{a.db} ? ?? ????. ?? mirror ?? ingest ????.")
    if a.idea:
        terms = terms_from_idea(_idea(a.idea))
    else:
        terms = terms_from_query(a.query)
    if not terms:
        sys.exit("???? ????. --idea ?? --query ? ??????.")
    hits = search_docs(corpus, terms, a.limit)
    print(format_hits(hits, len(corpus)))


def cmd_web(a):
    argv = ["--db", a.db, "--host", a.host, "--port", str(a.port)]
    if a.demo:
        argv.append("--demo")
    if getattr(a, "test_mode", False):
        argv.append("--test-mode")
    if getattr(a, "test_password", None):
        argv += ["--test-password", a.test_password]
    argv += ["--test-result-limit", str(getattr(a, "test_result_limit", 8))]
    argv += ["--test-snippet-chars", str(getattr(a, "test_snippet_chars", 220))]
    argv += ["--test-max-analyze-per-hour", str(getattr(a, "test_max_analyze_per_hour", 20))]
    if getattr(a, "test_show_links", False):
        argv.append("--test-show-links")
    return web_main(argv)


def cmd_judge(a):
    st = Store(a.db)
    corpus = st.all()
    if not corpus:
        sys.exit(f"{a.db} ? ?? ????. ?? mirror ?? ingest ????.")
    idea = _idea(a.idea)
    assessments = [assess(d, idea) for d in corpus]
    recall = check_recall(corpus, idea, assessments)
    summary = summarize(assessments, recall, len(corpus), idea=idea)
    print(to_console(assessments, summary))
    if a.out:
        md = to_markdown(idea.text, assessments, recall, summary)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"\n??? ? {a.out}")
    return 0 if summary["overall"] != "VOID" else 2


def cmd_probe(a):
    import requests
    load_env_file(a.keys_env)
    cd = normalize_cds(a.cd)[:1] or a.cd.upper()
    key = key_for_cd(cd, a.key)
    if not key:
        sys.exit(f"{cd} ??? ??? ???? ????. --key, KDI_API_KEY ?? KDI_API_KEY_{cd}? ??????.")
    r = requests.get(API, params={"type": "json", "apiKey": key, "cd": cd},
                     timeout=60)
    print("HTTP", r.status_code, "| bytes", len(r.content))
    txt = r.text
    try:
        obj = r.json()
        print("TOTAL_COUNT =", obj.get("TOTAL_COUNT"))
        print("top-level keys =", list(obj)[:10])
        arc = obj.get("ARCHIVE")
        print("ARCHIVE type =", type(arc).__name__,
              "len =", len(arc) if hasattr(arc, "__len__") else "-")
        first = arc[0] if isinstance(arc, list) and arc else arc
        if isinstance(first, dict):
            print("record keys =", list(first))
    except Exception as e:
        print("JSON ?? ??:", e)
        print(txt[:800])


def cmd_status(a):
    st = Store(a.db)
    print(f"{a.db}: ? {st.count()}?")
    for source, kind, n in st.summary():
        label = f"{source} / {kind or '???'}"
        print(f"  {label}: {n}?")


def main(argv=None):
    p = argparse.ArgumentParser("kdinov")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mirror", help="??? ???")
    m.add_argument("--key", default=os.environ.get("KDI_API_KEY"), required=False,
                   help="?? ?. cd? KDI_API_KEY_A ?? ??? ? ?? ?? ??")
    m.add_argument("--keys-env", default=os.environ.get("KDI_KEYS_ENV"),
                   help="KDI_API_KEY_A=... ??? ??? ? ??")
    m.add_argument("--db", default="kdi.sqlite")
    m.add_argument("--cd", default="AB", help=f"??? ?? {CORPORA}")
    m.add_argument("--full", action="store_true", help="KDI Open API ?? ?? ABCDEF ?? ???")
    m.add_argument("--terms", action="store_true", help="???? ?? ??")
    m.add_argument("--idea", help="--terms ?? ? ? ??")
    m.add_argument("--debug", action="store_true")
    m.set_defaults(fn=cmd_mirror)

    g = sub.add_parser("ingest", help="?? ?? ?? (JSONL/JSON/TXT/CSV)")
    g.add_argument("--db", default="kdi.sqlite")
    g.add_argument("--file", help="?? ?? ?? ??")
    g.add_argument("--jsonl", help="?? ??? JSONL ?? ??")
    g.add_argument("--csv", help="CSV/TSV ?? ??")
    g.add_argument("--txt", help="??? ?? ??")
    g.add_argument("--source", default="manual")
    g.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("search", help="?? DB?? ?? ???? ?? ??")
    s.add_argument("--db", default="kdi.sqlite")
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--idea", help="? ?? JSON ??")
    src.add_argument("--query", help="?? ??? ???")
    s.add_argument("--source", help="?? source? ??")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_search)

    w = sub.add_parser("web", help="? ??? ??")
    w.add_argument("--db", default="kdi.sqlite")
    w.add_argument("--demo", action="store_true", help="??? ???? ??")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8787)
    w.add_argument("--test-mode", action="store_true", help="researcher test mode")
    w.add_argument("--test-password", default=os.environ.get("KDINOV_TEST_PASSWORD"))
    w.add_argument("--test-result-limit", type=int, default=8)
    w.add_argument("--test-snippet-chars", type=int, default=220)
    w.add_argument("--test-show-links", action="store_true")
    w.add_argument("--test-max-analyze-per-hour", type=int, default=20)
    w.set_defaults(fn=cmd_web)

    j = sub.add_parser("judge", help="??")
    j.add_argument("--db", default="kdi.sqlite")
    j.add_argument("--idea", required=True)
    j.add_argument("-o", "--out")
    j.set_defaults(fn=cmd_judge)

    b = sub.add_parser("probe", help="?? ??? ??")
    b.add_argument("--key", default=os.environ.get("KDI_API_KEY"))
    b.add_argument("--keys-env", default=os.environ.get("KDI_KEYS_ENV"))
    b.add_argument("--cd", default="A")
    b.set_defaults(fn=cmd_probe)

    q = sub.add_parser("status", help="SQLite ??? ??")
    q.add_argument("--db", default="kdi.sqlite")
    q.set_defaults(fn=cmd_status)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())

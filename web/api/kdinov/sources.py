"""??? ?? ??.

??: KDI ????? ??? ???? ???. ???? ??? ???
???? ? ??? ?? ????. ??? ???.
  - ???? ????? ???? (??? ?????? ???? ??)
  - ?? ??? ??? ???? ?? ?? (?? ?? ??)
  - ??? ?? ???? (?? ?? ??? ???? ??)
"""
from __future__ import annotations
import csv, json, os, re, sqlite3, time
from pathlib import Path
from typing import Iterable, Any
from .model import Doc

API = "https://www.kdi.re.kr/KDIOpenAPI"
# cd ?? -> ???? (KDI Open API ?? ??)
CORPORA = {"A": "???????", "B": "????", "C": "????",
           "D": "????", "E": "???", "F": "?????"}

# ???? ?? ?? ???? ??? ?? ????. ?? KDI_API_KEY? fallback.
KEY_ENV_BY_CD = {
    "A": ("KDI_API_KEY_A", "KDI_API_KEY_BASIC_REPORT"),
    "B": ("KDI_API_KEY_B", "KDI_API_KEY_ISSUE"),
    "C": ("KDI_API_KEY_C", "KDI_API_KEY_FORECAST"),
    "D": ("KDI_API_KEY_D", "KDI_API_KEY_TRENDS"),
    "E": ("KDI_API_KEY_E", "KDI_API_KEY_SCHOLAR"),
    "F": ("KDI_API_KEY_F", "KDI_API_KEY_VIDEO"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  doc_id TEXT PRIMARY KEY, source TEXT, title TEXT, url TEXT, date TEXT,
  keywords TEXT, toc TEXT, summary TEXT, kind TEXT, raw TEXT, fetched_at REAL);
CREATE INDEX IF NOT EXISTS ix_docs_source ON docs(source);
CREATE INDEX IF NOT EXISTS ix_docs_kind ON docs(kind);
"""


class Store:
    """?? ?? ???. ???? ???? ??."""

    def __init__(self, path: str = "kdi_corpus.sqlite"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def put(self, docs: Iterable[Doc]) -> int:
        rows = [(d.doc_id, d.source, d.title, d.url, d.date, d.keywords,
                 d.toc, d.summary, d.kind, json.dumps(d.raw, ensure_ascii=False),
                 time.time()) for d in docs]
        self.db.executemany(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.db.commit()
        return len(rows)

    def all(self, source: str | None = None) -> list[Doc]:
        q = "SELECT doc_id,source,title,url,date,keywords,toc,summary,kind,raw FROM docs"
        args: tuple = ()
        if source:
            q, args = q + " WHERE source=?", (source,)
        return [Doc(*r[:9], raw=json.loads(r[9] or "{}"))
                for r in self.db.execute(q, args)]

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]

    def summary(self) -> list[tuple[str, str, int]]:
        return list(self.db.execute(
            "SELECT source, COALESCE(kind,''), COUNT(*) FROM docs "
            "GROUP BY source, kind ORDER BY source, kind"))


# --------------------------------------------------------------------------
# ? ??
# --------------------------------------------------------------------------
def load_env_file(path: str | None) -> list[str]:
    """KEY=VALUE ??? ?? ?? ???? ????? ???.

    ?? ??? ????? ???? ???. ? ?? ?? ???? ???.
    """
    if not path:
        return []
    loaded: list[str] = []
    with open(path, encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if not name or not value:
                continue
            os.environ.setdefault(name, value)
            loaded.append(name)
    return loaded


def key_for_cd(cd: str, common_key: str | None = None) -> str | None:
    """cd? ?? ??, ??? ?? ?? ????."""
    cd = (cd or "").upper()
    for name in KEY_ENV_BY_CD.get(cd, ()):
        value = os.environ.get(name)
        if value:
            return value
    return common_key or os.environ.get("KDI_API_KEY")


def key_status(cds: str, common_key: str | None = None) -> list[tuple[str, bool, str]]:
    out = []
    for cd in normalize_cds(cds):
        env_names = ",".join(KEY_ENV_BY_CD.get(cd, ())) or "KDI_API_KEY"
        out.append((cd, bool(key_for_cd(cd, common_key)), env_names))
    return out


def normalize_cds(cds: str) -> str:
    seen = []
    for ch in (cds or "").upper():
        if ch in CORPORA and ch not in seen:
            seen.append(ch)
    return "".join(seen)


# --------------------------------------------------------------------------
# KDI Open API ???
# --------------------------------------------------------------------------
def _pick(d: dict, *keys: str) -> str:
    """?? ???? ??? ?? ? ???? ??? ???? ????."""
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _archive_items(payload: dict[str, Any]) -> list[dict]:
    items = payload.get("ARCHIVE") or payload.get("ARCHIVES") or []
    if isinstance(items, dict):
        items = items.get("ARCHIVE", items)
    if isinstance(items, dict):
        items = [items]
    return [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []


def parse_archive(payload: dict, cd: str) -> list[Doc]:
    """Open API ??? Doc?? ?????."""
    out = []
    for idx, it in enumerate(_archive_items(payload), 1):
        doc = doc_from_mapping(it, source="kdi_api", fallback_id=f"{cd}:{idx}")
        if doc:
            if not doc.kind:
                doc.kind = _pick(it, "PUB_CD_NM") or CORPORA.get(cd, cd)
            if not doc.doc_id:
                doc.doc_id = doc.url or f"{cd}:{doc.title}"
            out.append(doc)
    return out


def mirror(api_key: str | None, cds: str = "AB", sleep: float = 0.5,
           debug: bool = False) -> list[Doc]:
    """srhValue? ?? ??? ??? ????."""
    import requests
    docs: list[Doc] = []
    for cd in normalize_cds(cds):
        key = key_for_cd(cd, api_key)
        if not key:
            print(f"  [{cd}] {CORPORA.get(cd, cd)}: ? ?? - ???")
            continue
        r = requests.get(API, params={"type": "json", "apiKey": key,
                                      "cd": cd}, timeout=60)
        r.raise_for_status()
        payload = r.json()
        if debug:
            print(json.dumps(payload, ensure_ascii=False)[:2000])
        got = parse_archive(payload, cd)
        print(f"  [{cd}] {CORPORA.get(cd, cd)}: {len(got)}? "
              f"(TOTAL_COUNT={payload.get('TOTAL_COUNT')})")
        docs += got
        time.sleep(sleep)
    return docs


def mirror_by_terms(api_key: str | None, terms: list[str], cds: str = "AB",
                    sleep: float = 0.5) -> list[Doc]:
    """?? ?? ??? ??? ?? ?? ??."""
    import requests
    seen: dict[str, Doc] = {}
    for cd in normalize_cds(cds):
        key = key_for_cd(cd, api_key)
        if not key:
            print(f"  [{cd}] {CORPORA.get(cd, cd)}: ? ?? - ???")
            continue
        for t in terms:
            r = requests.get(API, params={
                "type": "json", "apiKey": key, "cd": cd,
                "srhKey": "ALL", "srhValue": t}, timeout=60)
            r.raise_for_status()
            for d in parse_archive(r.json(), cd):
                seen.setdefault(d.doc_id, d)
            time.sleep(sleep)
    return list(seen.values())


# --------------------------------------------------------------------------
# ??/?? ?? ??
# --------------------------------------------------------------------------
def doc_from_mapping(row: dict, source: str = "manual",
                     fallback_id: str | int = "") -> Doc | None:
    """CSV/JSON/KDI ?? ??? Doc?? ?????."""
    d = {str(k).strip(): ("" if v is None else str(v).strip())
         for k, v in row.items() if k is not None}
    title = _pick(d, "title", "Title", "TITLE", "??", "????", "??",
                  "PUB_NM_KORN", "PUB_NM_ENG", "MOV_NM")
    if not title:
        return None
    url = _pick(d, "url", "URL", "link", "??", "?????", "DETAIL_PAGE", "LINK_URL")
    keywords = " ".join(filter(None, [
        _pick(d, "keywords", "keyword", "???", "PUB_KEYWORD"),
        _pick(d, "topic", "topics", "????", "TOPIC_ARR"),
    ]))
    doc_id = _pick(d, "doc_id", "id", "ID", "PUB_NO", "NUMROW") or url or f"{source}:{fallback_id}:{title}"
    kind = _pick(d, "kind", "type", "????", "?????", "PUB_CD_NM", "CD_NM_KORN", "SERIES_NM_KORN", "SERIES_NM_ENG", "PUB_CD")
    kind = {"E2": "KDI \uacbd\uc81c\uc804\ub9dd", "E3": "KDI \uacbd\uc81c\ub3d9\ud5a5"}.get(kind, kind)
    return Doc(
        doc_id=doc_id,
        source=_pick(d, "source", "??") or source,
        title=title,
        url=url,
        date=_pick(d, "date", "year", "??", "???", "ISSU_DT", "PUB_DT"),
        keywords=keywords,
        toc=_pick(d, "toc", "??", "PUB_CN"),
        summary=_pick(d, "summary", "??", "??", "??", "SUMM_KORN", "SUMM_ENG", "MOV_CN"),
        kind=kind,
        raw=row,
    )


def docs_from_json(obj: Any, source: str = "manual", cd: str = "?") -> list[Doc]:
    if isinstance(obj, dict) and ("ARCHIVE" in obj or "ARCHIVES" in obj):
        return parse_archive(obj, cd)
    if isinstance(obj, dict):
        doc = doc_from_mapping(obj, source, 1)
        return [doc] if doc else []
    if isinstance(obj, list):
        out = []
        for i, row in enumerate(obj, 1):
            if isinstance(row, dict):
                doc = doc_from_mapping(row, source, i)
                if doc:
                    out.append(doc)
        return out
    return []


COPIED_ARCHIVE_KEYS = set("""
DETAIL_PAGE ISSU_DT ISSU_OFFICE_ENG ISSU_OFFICE_KORN MAIN_AUT_NM SUB_AUT_NM
CO_AUT_NM NUMROW PUB_CD PUB_CD_NM CD_NM_KORN PER_CD PUB_CN PUB_KEYWORD PUB_LANG PUB_NM_ENG
PUB_NM_KORN PUB_NO PUB_TYPE SERIES_NM_ENG SERIES_NM_KORN SERIES_NO_ENG
SERIES_NO_KORN SUMM_ENG SUMM_KORN TOPIC_ARR TOTAL_COUNT ARCHIVE
""".split())


def _clean_copied_value(lines: list[str]) -> str:
    value = "\n".join(lines).strip()
    if value.startswith('"'):
        value = value[1:]
    value = re.sub(r'"\s*,?\s*$', "", value.strip())
    return value.strip()


def _parse_copied_archive_chunk(chunk: str) -> dict[str, str]:
    row: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in chunk.splitlines():
        m = re.match(r"^\s*([A-Z_]+)\s*:\s*(.*)$", line)
        if m and m.group(1) in COPIED_ARCHIVE_KEYS:
            if current:
                row[current] = _clean_copied_value(buf)
            current = m.group(1)
            buf = [m.group(2)]
        elif current:
            buf.append(line)
    if current:
        row[current] = _clean_copied_value(buf)
    return row


def parse_copied_archive_text(text: str, source: str = "kdi_api_file") -> list[Doc]:
    """Parse a browser-copied KDI API response.

    Some copied KDI responses look like JavaScript object literals, not strict
    JSON: keys are unquoted and long string values contain literal newlines.
    This parser keeps those multiline fields intact and normalizes rows to Doc.
    """
    if "ARCHIVE" not in text or "DETAIL_PAGE" not in text:
        return []
    starts = [m.start() for m in re.finditer(r"(?m)^\s*DETAIL_PAGE\s*:", text)]
    docs: list[Doc] = []
    for i, start in enumerate(starts, 1):
        end = starts[i] if i < len(starts) else len(text)
        row = _parse_copied_archive_chunk(text[start:end])
        doc = doc_from_mapping(row, source=source, fallback_id=i)
        if doc:
            docs.append(doc)
    return docs


def load_jsonl(path: str, source: str = "manual") -> list[Doc]:
    """??? ?? ???? ? ?? ??? JSONL? ????."""
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            d = json.loads(line)
            if isinstance(d, dict) and ("ARCHIVE" in d or "ARCHIVES" in d):
                out.extend(parse_archive(d, "?"))
                continue
            doc = doc_from_mapping(d, source, i) if isinstance(d, dict) else None
            if doc:
                out.append(doc)
    return out


def load_delimited(path: str, source: str = "manual") -> list[Doc]:
    p = Path(path)
    delimiter = "\t" if p.suffix.lower() == ".tsv" else ","
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
        except csv.Error:
            pass
        for i, row in enumerate(csv.DictReader(fh, delimiter=delimiter), 1):
            doc = doc_from_mapping(row, source, i)
            if doc:
                out.append(doc)
    return out


def load_text(path: str, source: str = "manual") -> list[Doc]:
    text = Path(path).read_text(encoding="utf-8-sig")
    stripped = text.strip()
    if not stripped:
        return []
    copied = parse_copied_archive_text(text, source)
    if copied:
        return copied
    try:
        return docs_from_json(json.loads(stripped), source)
    except json.JSONDecodeError:
        pass

    docs = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines, 1):
        if "|" in line or "\t" in line:
            parts = [p.strip() for p in re.split(r"\s*\|\s*|\t+", line)]
            docs.append(Doc(
                doc_id=f"{source}:{i}:{parts[0]}", source=source,
                title=parts[0], date=parts[1] if len(parts) > 1 else "",
                kind=parts[2] if len(parts) > 2 else "",
                summary=" ".join(parts[3:]) if len(parts) > 3 else line,
                raw={"line": line}))
    if docs:
        return docs

    for i, block in enumerate(re.split(r"\n\s*\n", stripped), 1):
        block_lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not block_lines:
            continue
        docs.append(Doc(
            doc_id=f"{source}:{i}:{block_lines[0]}", source=source,
            title=block_lines[0][:180], summary=" ".join(block_lines[1:])[:5000],
            raw={"text": block}))
    return docs


def load_file(path: str, source: str = "manual") -> list[Doc]:
    suffix = Path(path).suffix.lower()
    if suffix == ".jsonl":
        return load_jsonl(path, source)
    if suffix == ".json":
        return docs_from_json(json.loads(Path(path).read_text(encoding="utf-8-sig")), source)
    if suffix in (".csv", ".tsv"):
        return load_delimited(path, source)
    return load_text(path, source)

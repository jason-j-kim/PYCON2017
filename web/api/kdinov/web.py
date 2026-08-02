"""Browser-facing policy originality checker backed by a local SQLite corpus."""
from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .decompose import decompose_policy_idea
from .model import Idea
from .search import CorpusIndex, terms_from_idea
from .sources import Store, load_jsonl
from .verdict import (Assessment, assess, atomic_relations, check_recall,
                      evidence_grade, policy_package_key, summarize)

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
EXAMPLES_ROOT = ROOT / "ideas"

AXIS_TARGET = "\ub300\uc0c1"
AXIS_INSTRUMENT = "\uc218\ub2e8"
AXIS_DOMAIN = "\uc601\uc5ed"
ROLE_EXECUTION = "\uc2e4\ud589"
ROLE_COMPETING = "\uacbd\ud569"
ROLE_EVIDENCE = "\uadfc\uac70"
ROLE_PRECEDENT = "\uc120\ub840"
ROLE_IRRELEVANT = "\ubb34\uad00"


def clamp_int(value, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))


def short_text(value: str, max_chars: int) -> str:
    value = value or ""
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."


def limited_matched(matched: dict) -> dict:
    return {field: terms[:3] for field, terms in (matched or {}).items()}


def apply_test_limits(result: dict, config: dict) -> dict:
    doc_limit = config.get("result_limit", 8)
    snippet_chars = config.get("snippet_chars", 220)
    show_links = config.get("show_links", False)

    result["documents"] = result.get("documents", [])[:doc_limit]
    result["searchHits"] = result.get("searchHits", [])[:doc_limit]
    result["packages"] = result.get("packages", [])[:doc_limit]
    for doc in result["documents"]:
        doc["evidence"] = short_text(doc.get("evidence", ""), snippet_chars)
        doc["notes"] = (doc.get("notes") or [])[:2]
        if not show_links:
            doc["url"] = ""
    for hit in result["searchHits"]:
        hit["snippet"] = short_text(hit.get("snippet", ""), snippet_chars)
        hit["matched"] = limited_matched(hit.get("matched", {}))
        if not show_links:
            hit["url"] = ""
    result["testMode"] = {
        "enabled": True,
        "resultLimit": doc_limit,
        "snippetChars": snippet_chars,
        "linksVisible": show_links,
    }
    return result


def load_corpus(db_path: str | None = None, demo: bool = False):
    if demo:
        docs = load_jsonl(str(ROOT / "tests" / "corpus.jsonl"))
        docs += load_jsonl(str(ROOT / "external_artist.jsonl"))
        return docs
    if not db_path:
        return []
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"DB 파일이 없습니다: {db_path}")
    docs = Store(db_path).all()
    if not docs:
        raise SystemExit(f"DB가 비어 있습니다: {db_path}")
    return docs


def corpus_period(corpus) -> dict:
    years = []
    for doc in corpus:
        y = doc.year()
        if not y:
            match = re.search(r"(19|20)\d{2}", doc.title or "")
            y = match.group(0) if match else ""
        if y:
            years.append(int(y))
    return {
        "minYear": min(years) if years else None,
        "maxYear": max(years) if years else None,
        "unknownYear": len(corpus) - len(years),
    }


def analyze_payload(payload: dict, corpus, corpus_index: CorpusIndex | None = None,
                    progress=None) -> dict:
    idea = idea_from_payload(payload)
    index = corpus_index or CorpusIndex(corpus)
    if progress:
        progress("indexing", "빠른 색인에서 후보를 추리는 중")
    selection = index.candidates(idea)
    if progress:
        progress("assessing", f"후보 {len(selection.docs):,}건을 정밀 판정하는 중")
    assessments = [assess(doc, idea) for doc in selection.docs]
    recall = check_recall(corpus, idea, assessments)
    summary = summarize(
        assessments, recall, len(corpus), idea=idea,
        candidate_count=selection.candidate_count,
        precise_count=len(selection.docs), truncated=selection.truncated,
    )
    limit = clamp_int(payload.get("limit"), 30, 1, 30)
    packages = summary.pop("packages", [])
    summary["package_count"] = len(packages)
    search_hits = index.search(terms_from_idea(idea), limit=limit)
    kept = [a for a in assessments if a.flagged]
    direct = [a for a in kept if a.code in ("N0", "N1")]
    evidence = [a for a in kept if a.role in (ROLE_EVIDENCE, ROLE_PRECEDENT)]
    if progress:
        progress("formatting", "근거 문헌과 판정 결과를 정리하는 중")

    return {
        "idea": idea.text,
        "summary": summary,
        "metrics": {
            "policyPackageCount": len(packages),
            "mentionCount": selection.candidate_count,
            "directMentionCount": len(direct),
            "preciseCount": len(selection.docs),
            "evidenceCount": len(evidence),
            "mentionDensity": round(100 * selection.candidate_count / len(corpus), 1) if corpus else 0,
            "searchHitCount": len(search_hits),
        },
        "recall": {
            "rate": recall.rate,
            "ok": recall.ok,
            "expected": recall.expected,
            "found": recall.found,
            "missed": recall.missed,
        },
        "documents": [
            assessment_to_dict(a, idea)
            for a in sorted(kept, key=lambda x: (x.code, role_order(x.role), -x.score))[:limit]
        ],
        "searchHits": [
            {
                "title": h.doc.title,
                "score": h.score,
                "kind": h.doc.kind or h.doc.source,
                "year": h.doc.year(),
                "url": h.doc.url,
                "matched": h.matched,
                "snippet": h.snippet,
            }
            for h in search_hits
        ],        "packages": packages[:limit],

    }
def idea_from_payload(payload: dict) -> Idea:
    axes = {}
    for name in (AXIS_TARGET, AXIS_INSTRUMENT, AXIS_DOMAIN):
        spec = payload.get("axes", {}).get(name, {})
        axes[name] = {
            "exact": split_terms(spec.get("exact", "")),
            "syn": split_terms(spec.get("syn", "")),
            "broad": split_terms(spec.get("broad", "")),
        }
    return Idea.from_dict({
        "idea": payload.get("idea", "").strip(),
        "axes": axes,
        "financing": split_terms(payload.get("financing", "")),
        "delivery": split_terms(payload.get("delivery", "")),
        "known_positives": split_terms(payload.get("known_positives", "")),
        "claims": {
            name: split_terms(value)
            for name, value in (payload.get("claims") or {}).items()
        },
    })


def split_terms(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").replace("\n", ",").split(",") if part.strip()]


def role_order(role: str) -> int:
    return {
        ROLE_EXECUTION: 0,
        ROLE_COMPETING: 1,
        ROLE_EVIDENCE: 2,
        ROLE_PRECEDENT: 3,
        ROLE_IRRELEVANT: 4,
    }.get(role, 9)


def assessment_to_dict(a: Assessment, idea: Idea) -> dict:
    return {
        "title": a.doc.title,
        "url": a.doc.url,
        "kind": a.doc.kind or a.doc.source,
        "year": a.doc.year(),
        "code": a.code,
        "role": a.role,
        "score": a.score,
        "axes": a.axes_at,
        "direction": None if not a.direction else {
            "verdict": a.direction.verdict,
            "rule": a.direction.rule,
            "reason": a.direction.reason,
        },
        "evidence": a.window.text if a.window else "",
        "design": a.design,
        "atomicRelations": atomic_relations(a, idea),
        "evidenceQuality": evidence_grade(a.doc),
        "packageId": policy_package_key(a.doc)[:80],
        "notes": a.notes,
    }


def read_examples() -> list[dict]:
    out = []
    for path in sorted(EXAMPLES_ROOT.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append({"id": path.stem, "label": data.get("idea", path.stem), "data": data})
    return out

class AnalysisJobs:
    """긴 판정을 요청 스레드와 분리하고 상태/결과를 보관한다."""

    def __init__(self, analyzer, max_workers: int = 2):
        self.analyzer = analyzer
        self.executor = ThreadPoolExecutor(max_workers=max_workers,
                                           thread_name_prefix="kdinov-analysis")
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}

    def submit(self, payload: dict) -> str:
        job_id = uuid.uuid4().hex
        with self.lock:
            self.jobs[job_id] = {
                "jobId": job_id, "status": "queued", "stage": "queued",
                "message": "분석 대기열에 등록됨", "createdAt": time.time(),
            }
        self.executor.submit(self._run, job_id, payload)
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id: str, **values):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(values)

    def _run(self, job_id: str, payload: dict):
        self._update(job_id, status="running", stage="indexing",
                     message="빠른 색인에서 후보를 추리는 중")
        try:
            def progress(stage, message):
                self._update(job_id, stage=stage, message=message)
            result = self.analyzer(payload, progress)
            self._update(job_id, status="completed", stage="completed",
                         message="판정 완료", result=result, completedAt=time.time())
        except Exception as exc:  # pragma: no cover - HTTP integration path
            self._update(job_id, status="failed", stage="failed",
                         message="판정 실패", error=str(exc), completedAt=time.time())


class Handler(BaseHTTPRequestHandler):
    corpus = []
    status = {}
    test_config = {"enabled": False}
    rate_log = {}
    corpus_index = None
    analysis_jobs = None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            return self.json_response({
                "ok": True,
                **self.status,
                "testMode": bool(self.test_config.get("enabled")),
                "locked": bool(self.test_config.get("enabled") and self.test_config.get("password")),
                "limits": {
                    "resultLimit": self.test_config.get("result_limit", 30),
                    "snippetChars": self.test_config.get("snippet_chars", 0),
                    "linksVisible": bool(self.test_config.get("show_links")),
                    "maxAnalyzePerHour": self.test_config.get("max_analyze_per_hour", 0),
                },
            })
        if path == "/api/examples":
            if not self.require_auth():
                return
            return self.json_response({"examples": read_examples()})
        if path.startswith("/api/jobs/"):
            if not self.require_auth():
                return
            job_id = path.rsplit("/", 1)[-1]
            job = self.analysis_jobs.get(job_id) if self.analysis_jobs else None
            if not job:
                return self.json_response({"ok": False, "error": "JOB_NOT_FOUND"}, status=404)
            return self.json_response({"ok": True, **job})
        if path == "/":
            path = "/index.html"
        return self.serve_file(path.lstrip("/"))

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if not self.require_auth():
                return
            if path in ("/api/analyze", "/api/analyze-async") and not self.check_rate_limit():
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if path == "/api/decompose":
                draft = decompose_policy_idea(payload.get("idea", ""))
                return self.json_response({"ok": True, "draft": draft})
            if path in ("/api/analyze", "/api/analyze-async"):
                if not self.corpus:
                    raise ValueError("Corpus is empty.")
                if self.test_config.get("enabled"):
                    payload["limit"] = min(
                        clamp_int(payload.get("limit"), 30, 1, 30),
                        self.test_config.get("result_limit", 8),
                    )
                if path == "/api/analyze-async":
                    job_id = self.analysis_jobs.submit(payload)
                    return self.json_response({"ok": True, "jobId": job_id,
                                               "status": "queued"}, status=202)
                result = analyze_payload(payload, self.corpus, self.corpus_index)
                if self.test_config.get("enabled"):
                    result = apply_test_limits(result, self.test_config)
                return self.json_response({"ok": True, **result})
            return self.send_error(404)
        except Exception as exc:
            return self.json_response({"ok": False, "error": str(exc)}, status=400)

    def require_auth(self) -> bool:
        if not self.test_config.get("enabled"):
            return True
        password = self.test_config.get("password") or ""
        if not password:
            return True
        provided = self.headers.get("X-KDINOV-Test-Key", "")
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth.split(" ", 1)[1].strip()
        if hmac.compare_digest(provided, password):
            return True
        self.json_response({
            "ok": False,
            "error": "UNAUTHORIZED",
            "message": "Test password is required.",
        }, status=401)
        return False

    def check_rate_limit(self) -> bool:
        if not self.test_config.get("enabled"):
            return True
        limit = int(self.test_config.get("max_analyze_per_hour") or 0)
        if limit <= 0:
            return True
        now = time.time()
        key = self.client_address[0]
        history = [t for t in self.rate_log.get(key, []) if now - t < 3600]
        if len(history) >= limit:
            self.rate_log[key] = history
            self.json_response({
                "ok": False,
                "error": "RATE_LIMITED",
                "message": "Analyze request limit reached. Try again later.",
            }, status=429)
            return False
        history.append(now)
        self.rate_log[key] = history
        return True

    def serve_file(self, relative: str):
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            return self.send_error(403)
        if not target.exists() or not target.is_file():
            return self.send_error(404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        if ctype.startswith("text/") or ctype in ("application/javascript", "text/javascript"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, payload: dict, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # pragma: no cover
        return


def main(argv=None):
    parser = argparse.ArgumentParser("kdinov web")
    parser.add_argument("--db", default="kdi.sqlite")
    parser.add_argument("--demo", action="store_true", help="run with demo corpus")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--test-mode", action="store_true", help="enable researcher test mode")
    parser.add_argument("--test-password", default=os.environ.get("KDINOV_TEST_PASSWORD", ""))
    parser.add_argument("--test-result-limit", type=int, default=8)
    parser.add_argument("--test-snippet-chars", type=int, default=220)
    parser.add_argument("--test-show-links", action="store_true")
    parser.add_argument("--test-max-analyze-per-hour", type=int, default=20)
    args = parser.parse_args(argv)

    corpus = load_corpus(args.db, args.demo)
    Handler.corpus = corpus
    Handler.corpus_index = CorpusIndex(corpus)
    Handler.test_config = {
        "enabled": bool(args.test_mode),
        "password": args.test_password,
        "result_limit": clamp_int(args.test_result_limit, 8, 1, 30),
        "snippet_chars": clamp_int(args.test_snippet_chars, 220, 0, 2000),
        "show_links": bool(args.test_show_links),
        "max_analyze_per_hour": clamp_int(args.test_max_analyze_per_hour, 20, 0, 500),
    }
    Handler.rate_log = {}
    def run_analysis(payload, progress):
        result = analyze_payload(payload, corpus, Handler.corpus_index, progress)
        if Handler.test_config.get("enabled"):
            result = apply_test_limits(result, Handler.test_config)
        return result

    Handler.analysis_jobs = AnalysisJobs(run_analysis)
    Handler.status = {
        "db": "demo corpus" if args.demo else args.db,
        "corpusCount": len(corpus),
        "period": corpus_period(corpus),
        "demo": args.demo,
        "mode": "test" if args.test_mode else ("demo" if args.demo else "real-db"),
    }
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    suffix = " test-mode" if args.test_mode else ""
    print(f"kdinov web: {url} ({len(corpus)} docs){suffix}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
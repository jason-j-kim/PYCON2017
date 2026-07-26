# -*- coding: utf-8 -*-
"""Vercel 서버리스 프록시 — 브라우저의 Claude 문답/채점 호출을 Anthropic으로 넘긴다.

브라우저가 api.anthropic.com을 직접 부르면 CORS로 막히므로, 이 얇은 프록시가
방문자의 Claude 키(헤더 X-Claude-API-Key)를 붙여 Anthropic Messages API로 전달한다.
키는 저장하지 않고 그 요청에만 쓴다. 문답·채점(12문항·이원 채점)이 이 경로를 쓴다.

요청 본문(JSON): {"system": "...", "user": "...", "max_tokens": 1200}
응답(JSON):       {"text": "모델 응답 텍스트"}
"""
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        api_key = (self.headers.get("X-Claude-API-Key") or "").strip()
        if not api_key:
            self._send(401, {"error": "Claude API 키가 필요합니다."})
            return
        try:
            length = int(self.headers.get("content-length", 0) or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}") if length else {}
        except Exception:
            self._send(400, {"error": "요청 본문(JSON)을 읽지 못했습니다."})
            return

        system = payload.get("system") or ""
        user = payload.get("user") or ""
        max_tokens = int(payload.get("max_tokens") or 1200)
        if not user:
            self._send(400, {"error": "user 프롬프트가 비어 있습니다."})
            return

        body = json.dumps({
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode("utf-8")
        req = urllib.request.Request(ANTHROPIC_URL, data=body, headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            code = 401 if e.code == 401 else (429 if e.code == 429 else 502)
            msg = f"Claude API 오류 HTTP {e.code}"
            if e.code == 401:
                msg = "Claude 인증 실패 — API 키를 확인해 주세요."
            elif e.code == 429:
                msg = "요청이 한도를 초과했습니다. 잠시 후 다시 시도하세요."
            self._send(code, {"error": msg, "detail": detail[:300]})
            return
        except urllib.error.URLError as e:
            self._send(502, {"error": f"Claude API 연결 실패: {e.reason}"})
            return

        stop_reason = data.get("stop_reason")
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        if not text:
            # 빈 응답의 실제 사유를 알려준다(대개 max_tokens로 잘렸거나 thinking만 반환).
            self._send(502, {"error": f"모델이 빈 응답을 반환했습니다 (stop_reason={stop_reason}). "
                                      "max_tokens를 늘리거나 더 빠른 모델로 바꿔 보세요."})
            return
        self._send(200, {"text": text, "stop_reason": stop_reason})

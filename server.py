#!/usr/bin/env python3
"""
อับดุล — ถามไรตอบได้ (Ctrl+V Hackathon prototype)

Tiny stdlib-only server:
  - serves the static chat UI from ./public
  - POST /api/chat -> forwards to the SYDEAR Router Gateway
    (model alias: sydear-photon) with the server-side system prompt.
    The gateway API key NEVER leaves this box: it is read from a
    0600 file on the server (default: the gateway's own .keys/abdul.key).

Run:  ABDUL_PORT=28100 python3 server.py
"""
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"

GW_URL = os.environ.get("ABDUL_GW_URL", "http://127.0.0.1:28080")
GW_MODEL = os.environ.get("ABDUL_GW_MODEL", "sydear-photon")
KEY_FILE = os.environ.get(
    "ABDUL_GW_KEY_FILE", "/opt/sydear-router-gateway/.keys/abdul.key")
PORT = int(os.environ.get("ABDUL_PORT", "28100"))
MAX_DOC_CHARS = 12000
MAX_Q_CHARS = 4000

SYSTEM_PROMPT = (
    "เธอคือ \"อับดุล\" ผู้ช่วยตอบคำถามเป็นภาษาไทยบ้านๆ ให้คนทั่วไปเข้าใจได้\n"
    "โดยไม่ต้องไปค้น Google เอง\n\n"
    "กฎสำคัญ:\n"
    "1. ตอบเป็นภาษาไทยธรรมดาๆ ที่ใช้คุยกันทุกวัน ห้ามใช้ศัพท์ยากโดยไม่อธิบาย "
    "ถ้าจำเป็นต้องใช้ศัพท์เฉพาะ ให้แปลเป็นภาษาบ้านๆ ต่อท้ายทันที\n"
    "2. ตอบสั้นๆ ตรงประเด็นก่อน แล้วค่อยขยายความถ้าจำเป็น อย่าตอบยืดยาวเกินไป\n"
    "3. ถ้าไม่แน่ใจ ให้บอกตรงๆ ว่า \"อันนี้อับดุลไม่แน่ใจ\" แล้วบอกว่าที่แน่ใจมีแค่ไหน "
    "แยกให้ชัดว่าอะไรคือเรื่องที่มีคนบอก/มีหลักฐาน กับอะไรคือการเดา\n"
    "4. ห้ามแต่งเรื่อง ห้ามอ้างตัวเลข วันที่ หรือชื่อที่จำไม่ได้ ถ้าจำไม่ได้ให้บอกว่าจำไม่ได้\n"
    "5. ถ้าผู้ใช้แปะเอกสารมา ให้ตอบจากเอกสารนั้นเท่านั้น ถ้าในเอกสารไม่มีคำตอบ "
    "ให้บอกว่าในเอกสารไม่ได้บอกไว้ อย่าเอาความรู้ข้างนอกมาเติมโดยไม่บอก\n"
    "6. ถ้าคำถามกำกวม ให้ถามกลับสั้นๆ 1 คำถามก่อนตอบ หรือตอบตามความเข้าใจพร้อมบอกว่าเข้าใจแบบนี้\n"
    "7. ใช้น้ำเสียงเป็นกันเอง เหมือนเพื่อนอธิบายให้เพื่อนฟัง ไม่เป็นทางการ"
)

# --- tiny per-IP rate limit: 20 requests / 60s (prototype guard) ---
_hits = defaultdict(deque)
RATE_LIMIT = 20
RATE_WINDOW = 60


def _allowed(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and q[0] < now - RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return False
    q.append(now)
    return True


def _read_key() -> str:
    return Path(KEY_FILE).read_text().strip()


def _ask_gateway(messages):
    body = json.dumps({
        "model": GW_MODEL,
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        GW_URL + "/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + _read_key(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep logs quiet; errors still surface via exceptions

    # -- helpers ------------------------------------------------------
    def _json(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path):
        target = (PUBLIC / path.lstrip("/")).resolve()
        if not str(target).startswith(str(PUBLIC)):
            return self._json(403, {"error": "forbidden"})
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            return self._json(404, {"error": "not found"})
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- routes -------------------------------------------------------
    # NOTE: /api/chat always answers HTTP 200 with {"answer": ...} or
    # {"error": ...} in the body. Application errors must NOT use 5xx
    # statuses: Cloudflare replaces a 5xx origin response with its own
    # error page, so the browser would never see our JSON.
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path in ("/", "/index.html"):
            return self._static("index.html")
        if self.path == "/api/health":
            return self._json(200, {"ok": True, "model": GW_MODEL})
        return self._static(self.path)

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json(404, {"error": "not found"})
        ip = self.client_address[0]
        if not _allowed(ip):
            return self._json(200, {"error": "ถามบ่อยไปหน่อย พักแป๊บแล้วถามใหม่นะ"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 200_000:
                return self._json(200, {"error": "ข้อความยาวเกินไป"})
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(200, {"error": "ส่งข้อมูลมาไม่ถูก ลองใหม่อีกทีนะ"})
        question = str(payload.get("question") or "").strip()[:MAX_Q_CHARS]
        document = str(payload.get("document") or "").strip()[:MAX_DOC_CHARS]
        history = payload.get("history") or []
        if not question:
            return self._json(200, {"error": "พิมพ์คำถามก่อนนะ"})
        if document:
            user_text = (
                "ผู้ใช้แปะเอกสารมา แล้วถามว่า: " + question + "\n\n"
                "--- เอกสารที่แปะมา ---\n" + document +
                "\n--- จบเอกสาร ---\n\n"
                "ตอบคำถามจากเอกสารข้างบนเท่านั้น")
        else:
            user_text = question
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in history[-8:]:
            role = m.get("role")
            content = str(m.get("content") or "")[:2000]
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        try:
            answer = _ask_gateway(messages)
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("error", {})
                msg = detail.get("message", "")
            except Exception:
                msg = ""
            print(f"[abdul] gateway HTTP {e.code}: {msg[:200]}")
            return self._json(200, {
                "error": "ตอนนี้สมองของอับดุลตอบไม่ได้ ลองใหม่อีกทีนะ"
                         + (f" ({msg[:80]})" if msg else "")})
        except Exception as e:
            print(f"[abdul] gateway error: {e}")
            return self._json(200, {
                "error": "ตอนนี้อับดุลติดขัดนิดหน่อย ลองใหม่อีกทีนะ"})
        return self._json(200, {"answer": answer})


if __name__ == "__main__":
    print(f"abdul on :{PORT} -> {GW_URL} model={GW_MODEL}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

"""Loopback-only HTTP transport. No external dependencies or analytics."""

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .bank import CollectError, digest
from .exporter import export_bundle

STATIC = Path(__file__).resolve().parents[1] / "static"


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, port=8765):
        self.store = store
        self.collector_key = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Tokens, consent and responses never enter request logs.

    def reply(
        self,
        status,
        content,
        content_type="application/json; charset=utf-8",
        download=None,
    ):
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if download:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download}"'
            )
        self.end_headers()
        self.wfile.write(content)

    def check_host(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            raise CollectError("仅允许本机 127.0.0.1 访问")

    def check_collector(self):
        key = self.headers.get("X-Collector-Key", "")
        if not secrets.compare_digest(key, self.server.collector_key):
            raise CollectError("采集员访问码无效")

    def do_GET(self):
        try:
            self.check_host()
            static = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/collector": ("collector.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/collector.js": ("collector.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if self.path in static:
                filename, mime = static[self.path]
                self.reply(200, (STATIC / filename).read_bytes(), mime)
            elif self.path == "/api/info":
                bank = self.server.store.bank
                self.reply(
                    200,
                    {
                        "mode": "synthetic_only",
                        "formal_collection_enabled": False,
                        "bank_version": bank.document["bank_version"],
                        "bank_sha256": bank.sha256,
                        "consent": bank.document["consent"],
                        "consent_hash": digest(bank.document["consent"]),
                        "csrf": self.server.csrf,
                    },
                )
            elif self.path == "/api/collector":
                self.check_collector()
                self.reply(200, self.server.store.summary())
            elif self.path == "/api/export":
                self.check_collector()
                data, _ = export_bundle(self.server.store)
                self.reply(200, data, "application/zip", "bite-collect-synthetic.zip")
            else:
                self.reply(404, {"error": "未找到页面"})
        except CollectError as e:
            self.reply(403, {"error": str(e)})

    def do_POST(self):
        try:
            self.check_host()
            if self.headers.get(
                "Origin"
            ) != self.server.origin or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", ""), self.server.csrf
            ):
                raise CollectError("请求来源或 CSRF 校验失败")
            if self.headers.get("Content-Type") != "application/json":
                raise CollectError("要求 application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise CollectError("请求大小无效")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise CollectError("请求格式无效")
            store = self.server.store
            token = self.headers.get("X-Session-Token", "")
            if self.path == "/api/session":
                result = store.create(body)
            elif self.path == "/api/state":
                result = store.state(token, resume=body.get("resume") is True)
            elif self.path == "/api/answer":
                result = store.save(token, body.get("question_id"), body.get("answer"))
            elif self.path == "/api/pause":
                result = store.pause(token)
            elif self.path == "/api/withdraw":
                if body.get("confirm") is not True:
                    raise CollectError("请明确确认删除此会话")
                result = store.withdraw(token)
            else:
                self.reply(404, {"error": "未找到接口"})
                return
            self.reply(200, result)
        except (CollectError, ValueError, TypeError, KeyError) as e:
            self.reply(400, {"error": str(e)})
        except Exception:
            self.reply(500, {"error": "本地保存失败，回答尚未确认，请保留页面并重试"})

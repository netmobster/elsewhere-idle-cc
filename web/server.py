"""Elsewhere web prototype.

    python web/server.py

Opens a 30-minute playable world in the browser. Python still rolls.
Three optional Bedrock layers (interpret / narrate / chronicle) speak.
Without AWS credentials the same loop runs on local templates.
"""

from __future__ import annotations

import json
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web import game

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
HOST, PORT = "127.0.0.1", 8765


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[web] " + (fmt % args) + "\n")

    def _json(self, code, payload):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/play", "/play.html"):
            self.path = "/play.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        if parsed.path == "/api/health":
            return self._json(200, {
                "ok": True,
                "ai": game.ai.bedrock_ready(),
                "models": game.ai.DEFAULTS,
                "session_minutes": game.SESSION_MINUTES,
            })
        parts = parsed.path.strip("/").split("/")
        if parts[:2] == ["api", "session"] and len(parts) == 3:
            try:
                sess = game.load_session(parts[2])
            except KeyError:
                return self._json(404, {"error": "no such session"})
            # Opening the world is what makes time pass: whatever happened while
            # the player was away resolves now, against the real clock.
            game.catch_up(sess)
            game.touch(sess)
            game.save_session(sess)
            return self._json(200, game.public(sess))
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        try:
            return self._post(parts)
        except KeyError:
            return self._json(404, {"error": "no such session"})
        except Exception as exc:
            return self._json(400, {"error": str(exc)})

    def _post(self, parts):
        if parts == ["api", "session"]:
            sess = game.new_session(owner_token=self.headers.get("X-Elsewhere-Owner", ""))
            return self._json(200, game.public(sess))
        if parts[:2] != ["api", "session"] or len(parts) < 4:
            return self._json(404, {"error": "unknown"})
        sid, action = parts[2], parts[3]
        sess = game.load_session(sid)
        game.catch_up(sess)
        game.touch(sess)
        if action == "ping":
            # Heartbeat from a visible tab, so time spent reading the board counts.
            game.save_session(sess)
            return self._json(200, game.public(sess))
        if game.expired(sess):
            # Free play time is spent. The world does not stop — it keeps running
            # in real time and stays visible. It just stops taking orders.
            game.save_session(sess)
            return self._json(403, {"error": "free play time used — your world is still running",
                                    **game.public(sess)})
        body = self._read()
        result = None
        if action == "watch":
            game.apply_watch(sess, body.get("target") or body.get("watch") or "")
        elif action == "order":
            result = game.enqueue(sess, body, replace=bool(body.get("replace")))
            if isinstance(result, dict) and result.get("error"):
                game.save_session(sess)
                return self._json(400, {**result, **game.public(sess)})
        elif action == "cancel":
            result = game.cancel(sess, int(body.get("index", -1)))
        elif action == "say":
            result = game.freeform(sess, body.get("text") or "")
            if result.get("error"):
                game.save_session(sess)
                return self._json(400, {**result, **game.public(sess)})
        elif action == "advance":
            result = game.advance(sess, float(body.get("hours") or 8))
        else:
            return self._json(404, {"error": "unknown action"})
        game.save_session(sess)
        # `result` lets the client show its working: how a sentence was read and
        # priced, and what a skip resolved. Everything in it is already fog-safe or
        # is the player's own order.
        return self._json(200, {**game.public(sess), "result": _safe_result(action, result)})


def _safe_result(action, result):
    if not isinstance(result, dict):
        return None
    if action == "advance":
        # new_ledger is raw — it can carry unwatched clock rows. The client gets
        # the fogged ledger through `view` instead; only the count travels here.
        return {"ticks": result.get("ticks", 0)}
    return result


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Elsewhere web prototype  http://{HOST}:{PORT}/")
    print(f"AI: {'Bedrock' if game.ai.bedrock_ready() else 'local fallback (no AWS creds)'}")
    print(f"{game.SESSION_MINUTES} minute sessions · ${game.BUDGET_USD:.2f} cap")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

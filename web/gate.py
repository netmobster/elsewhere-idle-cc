"""A shared-password gate for the web prototype.

Set ELSEWHERE_PASSWORD and every page and every API call needs the word first.
Leave it unset and the server is exactly as it was: open, local, no gate.

This is a door, not a security system: one password, shared, no accounts. It exists
because the API spends real money on Bedrock per call, so a gate that only lives in
the browser's JavaScript would not actually protect anything — anyone can skip the
page and POST to /api/session directly. So the check runs here, on the server, and
the pass is a signed cookie rather than the password itself.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from http.cookies import SimpleCookie

COOKIE = "elsewhere_pass"
MAX_AGE = 60 * 60 * 24 * 14  # a fortnight, then type it again
# New secret per boot unless one is pinned: restarting the server signs everyone out.
SECRET = os.environ.get("ELSEWHERE_COOKIE_SECRET") or secrets.token_hex(16)


def password() -> str:
    return os.environ.get("ELSEWHERE_PASSWORD", "").strip()


def enabled() -> bool:
    return bool(password())


def _sign(expires: int) -> str:
    msg = f"{expires}.{password()}".encode("utf-8")
    return hmac.new(SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def mint() -> str:
    expires = int(time.time()) + MAX_AGE
    return f"{expires}.{_sign(expires)}"


def valid(token: str) -> bool:
    try:
        raw, sig = token.split(".", 1)
        expires = int(raw)
    except (ValueError, AttributeError):
        return False
    if expires < time.time():
        return False
    return hmac.compare_digest(sig, _sign(expires))


def cookie_ok(header: str) -> bool:
    if not header:
        return False
    jar = SimpleCookie()
    try:
        jar.load(header)
    except Exception:
        return False
    morsel = jar.get(COOKIE)
    return bool(morsel and valid(morsel.value))


def check(candidate: str) -> bool:
    """Compare in constant time, so the answer doesn't leak through the clock."""
    return bool(candidate) and hmac.compare_digest(candidate.strip(), password())


def set_cookie_header() -> tuple[str, str]:
    return ("Set-Cookie", f"{COOKIE}={mint()}; Path=/; Max-Age={MAX_AGE}; SameSite=Lax; HttpOnly")


PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Elsewhere</title>
<meta name="theme-color" content="#0d0c0b">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Spectral:ital,wght@0,300;0,400;1,300&display=swap" rel="stylesheet">
<style>
  :root{color-scheme:dark}
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0d0c0b;color:#e8e2d4;
       font-family:Spectral,Georgia,serif;padding:24px}
  .door{width:min(420px,100%);text-align:center}
  h1{font-family:Cinzel,Georgia,serif;font-weight:600;font-size:30px;letter-spacing:.14em;margin:0 0 6px}
  p{margin:0 0 22px;font-style:italic;color:#9a9182;line-height:1.5}
  form{display:flex;gap:8px}
  input{flex:1;background:#151311;border:1px solid #3b352c;border-radius:2px;color:#e8e2d4;
        font:inherit;font-size:16px;padding:12px 13px;outline:none}
  input:focus{border-color:#c2a46a}
  button{font-family:Cinzel,Georgia,serif;letter-spacing:.1em;font-size:14px;padding:12px 18px;
         background:#c2a46a;color:#17140f;border:none;border-radius:2px;cursor:pointer}
  button:hover{background:#e8e2d4}
  .no{margin-top:14px;min-height:20px;color:#b4573f;font-style:italic}
</style></head>
<body>
  <div class="door">
    <h1>ELSEWHERE</h1>
    <p>The world is running without you. It is not open to everyone yet.</p>
    <form id="f" autocomplete="off">
      <input id="p" type="password" placeholder="password" aria-label="Password" autofocus>
      <button type="submit">ENTER</button>
    </form>
    <div class="no" id="no" role="status"></div>
  </div>
<script>
document.getElementById('f').onsubmit = async e => {
  e.preventDefault();
  const r = await fetch('/api/gate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ password: document.getElementById('p').value })
  });
  if (r.ok) { location.href = '/'; return; }
  document.getElementById('no').textContent = 'Not that one.';
  document.getElementById('p').value = '';
  document.getElementById('p').focus();
};
</script>
</body></html>
"""

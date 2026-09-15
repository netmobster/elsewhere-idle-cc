"""Session worlds. Engine owns truth; this file never rolls."""

from __future__ import annotations

import json
import os
import secrets
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path

import engine
from web import ai, fog, pricing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SESS = HERE / "sessions"
SESS.mkdir(exist_ok=True)

SESSION_MINUTES = int(os.environ.get("ELSEWHERE_SESSION_MINUTES", "30"))
# A gap between two requests longer than this is the player being away, not
# playing, and does not count against their free time. The client pings while
# the tab is visible, so reading the board counts; closing the laptop does not.
IDLE_GAP_SECONDS = int(os.environ.get("ELSEWHERE_IDLE_GAP_SECONDS", "90"))
OWNER_TOKEN = os.environ.get("ELSEWHERE_OWNER_TOKEN", "")
BUDGET_USD = float(os.environ.get("ELSEWHERE_SESSION_BUDGET_USD", "0.20"))
MAX_CALLS = {"interpret": 16, "narrate": 14, "chronicle": 1}


def _now():
    return datetime.now(timezone.utc)


def _path(sid: str) -> Path:
    return SESS / f"{sid}.json"


def load_session(sid: str) -> dict:
    p = _path(sid)
    if not p.exists():
        raise KeyError("no such session")
    return json.loads(p.read_text(encoding="utf-8"))


def save_session(sess: dict) -> None:
    _path(sess["id"]).write_text(json.dumps(sess, indent=2, default=str),
                                 encoding="utf-8")


def remaining(sess: dict) -> float:
    """Free *play* time left, not time since the world was made.

    It used to be wall-clock from creation, which meant every free world died
    half an hour after it started and no free player could ever come back the
    next day — the one thing this game is about. The world now persists and runs
    in real time for as long as it lives; the free tier is thirty minutes of
    actually playing it, spent across as many visits as you like.
    """
    if sess.get("unlimited"):
        return float("inf")
    return max(0.0, SESSION_MINUTES * 60 - float(sess.get("play_seconds", 0.0)))


def expired(sess: dict) -> bool:
    return remaining(sess) <= 0 and sess["state"].get("status") != "settled"


def touch(sess: dict) -> None:
    """Accrue active play time from the gap since the last request."""
    now = _now()
    last = sess.get("last_seen")
    if last:
        gap = (now - datetime.fromisoformat(last)).total_seconds()
        if 0 < gap <= IDLE_GAP_SECONDS:
            sess["play_seconds"] = float(sess.get("play_seconds", 0.0)) + gap
    sess["last_seen"] = now.isoformat()


def catch_up(sess: dict) -> dict:
    """Advance the world to the real clock. This is "while you were gone".

    Runs on every load. If the player skipped ahead, last_tick is in the future
    and the engine returns zero ticks until real time catches up — no rewind,
    no double counting.
    """
    s = sess["state"]
    if s.get("status") == "settled":
        return {"ticks": 0}
    return _resolve(sess, _now(), skipped_hours=None)


def spend_ok(sess: dict, layer: str) -> bool:
    if sess["spend_usd"] >= BUDGET_USD:
        return False
    return sess["calls"].get(layer, 0) < MAX_CALLS[layer]


def charge(sess: dict, meta: dict) -> None:
    layer = meta.get("layer")
    if layer:
        sess["calls"][layer] = sess["calls"].get(layer, 0) + 1
    sess["spend_usd"] = round(sess["spend_usd"] + float(meta.get("usd") or 0), 6)
    sess["ai_log"].append({
        "at": _now().isoformat(),
        "layer": layer,
        "source": meta.get("source"),
        "model": meta.get("model"),
        "usd": meta.get("usd", 0),
    })


def new_session(seed=None, owner_token: str = "") -> dict:
    state = engine.new_world(seed)
    sid = secrets.token_urlsafe(10)
    sess = {
        "id": sid,
        "started": _now().isoformat(),
        "last_seen": _now().isoformat(),
        "play_seconds": 0.0,
        "unlimited": False,
        "spend_usd": 0.0,
        "calls": {"interpret": 0, "narrate": 0, "chronicle": 0},
        "ai_log": [],
        "ai_mode": "bedrock" if ai.bedrock_ready() else "fallback",
        "messages": [],
        "state": state,
    }
    if OWNER_TOKEN and owner_token and secrets.compare_digest(owner_token, OWNER_TOKEN):
        sess["unlimited"] = True
    view = fog.view(state)
    briefing = ai.narrate(view, None, first=True)
    charge(sess, briefing["meta"])
    sess["messages"].append({"role": "narrator", "text": briefing["text"], **_stamp(sess["state"]),
                             "meta": briefing["meta"]})
    save_session(sess)
    return sess


def _stamp(s: dict) -> dict:
    """Which day and watch a message belongs to, so old briefings can collapse to a row."""
    w = fog.world_mode(s)
    return {"day": s.get("day", 1), "watch": w["watch_name"], "at": s.get("last_tick")}


def public(sess: dict) -> dict:
    left = remaining(sess)
    unlimited = left == float("inf")
    return {
        "id": sess["id"],
        "unlimited": unlimited,
        "minutes_left": None if unlimited else round(left / 60, 2),
        "seconds_left": None if unlimited else int(left),
        "play_minutes": round(float(sess.get("play_seconds", 0.0)) / 60, 1),
        "expired": expired(sess),
        "spend_usd": sess["spend_usd"],
        "budget_usd": BUDGET_USD,
        "ai_mode": sess["ai_mode"],
        "calls": sess["calls"],
        "models": ai.DEFAULTS,
        "messages": sess["messages"],
        "view": fog.view(sess["state"]),
    }


def _match_front(state, want):
    if not want:
        return next(f for f in state["factions"] if f["id"] == state["watching"])
    want = str(want)
    f = next((x for x in state["factions"] if x["id"] == want), None)
    if f:
        return f
    return next(x for x in state["factions"] if want.lower() in x["name"].lower())


def apply_watch(sess: dict, want: str) -> None:
    s = sess["state"]
    if want.lower() in ("general", "all", "hill", "broad"):
        s["watch_mode"] = "general"
        s["watch_until"] = s.get("tick", 0) + engine.WATCH_TICKS
        return
    f = _match_front(s, want)
    s["watch_mode"] = "focused"
    s["watching"] = f["id"]
    s["watch_until"] = s.get("tick", 0) + engine.WATCH_TICKS


def enqueue(sess: dict, spec: dict, replace=False) -> dict:
    s = sess["state"]
    if s.get("status") == "settled":
        return {"error": "world already settled"}
    s["watch_until"] = s.get("tick", 0) + engine.WATCH_TICKS
    if replace:
        # Keep a queued mega. Its stake is the whole purse at queue time, so
        # clearing and rebuilding re-prices it from whatever is left — the bug
        # fixed in the engine in v1.1.0, reintroduced here.
        s["queue"] = [q for q in s["queue"] if q.get("kind") == "mega"]
    if len(s["queue"]) >= engine.QUEUE_SLOTS:
        return {"error": "queue full"}
    kind = spec.get("kind") or "disrupt"
    if kind not in engine.ACTIONS:
        kind = "improvise"
    f = _match_front(s, spec.get("target") or s["watching"])
    if kind == "improvise":
        # Intent in, price out. coin / hands / gain / grants in the request are
        # never read — see web/pricing.py for why.
        committed = sum(int(q.get("coin") or q.get("cost") or 0)
                        for q in s["queue"] if q.get("kind") != "mega")
        available = {"coin": max(0, s["holding"]["coin"] - committed),
                     "hands": s["holding"]["hands"]}
        priced = pricing.price(spec, available)
        order = {
            "what": (spec.get("what") or spec.get("said") or "an improvised scheme")[:240],
            "target": f["id"],
            "clock_at_queue": f["clock"],
            "said": (spec.get("said") or spec.get("what") or "")[:600],
            **priced,
        }
    elif kind == "mega":
        order = {
            "what": spec.get("what") or f"MEGA PROJECT: {f['name']}",
            "kind": "mega",
            "cost": s["holding"]["coin"],
            "target": f["id"],
            "clock_at_queue": f["clock"],
            "said": spec.get("said", ""),
        }
    else:
        committed = sum(int(q.get("coin") or q.get("cost") or 0)
                        for q in s["queue"] if q.get("kind") != "mega")
        if engine.ACTIONS[kind]["cost"] > s["holding"]["coin"] - committed:
            return {"error": f"not enough coin for {kind} once queued orders are paid"}
        order = {
            "what": spec.get("what") or engine.ACTIONS[kind]["label"].format(front=f["name"]),
            "kind": kind,
            "cost": engine.ACTIONS[kind]["cost"],
            "target": f["id"],
            "clock_at_queue": f["clock"],
            "said": spec.get("said", ""),
        }
    s["queue"].append(order)
    return {"queued": order["what"], "kind": kind, "target": f["name"]}


def cancel(sess: dict, index: int) -> dict:
    """Withdraw a queued order before it fires. Nothing has been spent yet."""
    q = sess["state"]["queue"]
    if not 0 <= index < len(q):
        return {"error": "no such order"}
    gone = q.pop(index)
    return {"cancelled": gone.get("what")}


def advance(sess: dict, hours: float) -> dict:
    """The skip button. Moves the world ahead of the real clock."""
    s = sess["state"]
    if s.get("status") == "settled":
        return {"ticks": 0, "settled": True}
    hours = max(0.0, min(float(hours), 72.0))
    base = max(datetime.fromisoformat(s["last_tick"]), _now())
    return _resolve(sess, base + timedelta(hours=hours), skipped_hours=hours)


def _resolve(sess: dict, now, skipped_hours):
    """Tick the engine to `now`, then narrate or chronicle what happened."""
    s = sess["state"]
    before = len(s["ledger"])
    out = engine.tick(s, now)
    if not out.get("ticks"):
        return out
    out["new_ledger"] = s["ledger"][before:]
    if s.get("status") == "settled":
        score = score_world(s)
        s["score"] = score
        if spend_ok(sess, "chronicle"):
            ch = ai.chronicle(s, score)
            charge(sess, ch["meta"])
            s["chronicle"] = ch["text"]
            sess["messages"].append({"role": "chronicle", "text": ch["text"],
                                     "meta": ch["meta"]})
        else:
            ch = ai._template_chronicle(s, score)
            s["chronicle"] = ch
            sess["messages"].append({
                "role": "chronicle", "text": ch,
                "meta": {"source": "budget-cap", "layer": "chronicle", "usd": 0},
            })
    elif spend_ok(sess, "narrate") and not expired(sess):
        view = fog.view(s)
        briefing = ai.narrate(view, int(skipped_hours) if skipped_hours else None, first=False)
        charge(sess, briefing["meta"])
        sess["messages"].append({"role": "narrator", "text": briefing["text"], **_stamp(sess["state"]),
                                 "meta": briefing["meta"]})
    return out


def freeform(sess: dict, text: str) -> dict:
    if expired(sess):
        return {"error": "session expired"}
    if sess["state"].get("status") == "settled":
        return {"error": "world already settled"}
    sess["messages"].append({"role": "player", "text": text})
    view = fog.view(sess["state"])
    if spend_ok(sess, "interpret"):
        mapped = ai.interpret(text, view)
        charge(sess, mapped.get("_meta") or {})
    else:
        mapped = ai._heuristic_interpret(text, view)
        mapped["_meta"] = {"source": "budget-cap", "layer": "interpret", "usd": 0}
    watch = mapped.get("watch")
    if watch:
        try:
            apply_watch(sess, watch)
        except Exception:
            pass
    results = []
    for order in (mapped.get("orders") or [])[:engine.QUEUE_SLOTS]:
        try:
            results.append(enqueue(sess, order))
        except ValueError as exc:
            results.append({"error": str(exc)})
    priced = [q for q in sess["state"]["queue"][-len(results):]] if results else []
    return {
        "read_as": {"watch": mapped.get("watch"),
                    "orders": [{k: o.get(k) for k in ("kind", "what", "target", "scale", "aims", "perilous", "beholden")}
                               for o in (mapped.get("orders") or [])]},
        "priced": [{k: o.get(k) for k in ("kind", "what", "target", "scale", "coin", "cost", "hands",
                                          "gain", "grants", "perilous")} for o in priced],
        "results": results,
        "via": (mapped.get("_meta") or {}).get("source"),
    }


def score_world(s: dict) -> dict:
    L = s["ledger"]
    acts = [e for e in L if e["t"] == "action"]
    raids = [e for e in L if e["t"] == "raid"]
    clocks = [e for e in L if e["t"] == "clock"]
    c = {o: len([a for a in acts if a["outcome"] == o])
         for o in ("ok", "partial", "refund", "misfire")}
    born = datetime.fromisoformat(s["created"])
    died = datetime.fromisoformat(s.get("settled_at", s["last_tick"]))
    lifespan = (died - born).total_seconds() / 86400
    taken = sum(r.get("taken", 0) for r in raids)
    stolen = sum(a.get("gain", 0) for a in acts)
    watched_rolls = sum(1 for x in clocks if x.get("watched"))
    vigilance = round(100 * watched_rolls / max(1, len(clocks)))
    lost = sum(1 for f in s["factions"] if f["done"])
    held = len(s["factions"]) - lost
    endurance = round(lifespan * 20)
    stewardship = s["holding"]["coin"]
    execution = c["ok"] * 30 + c["partial"] * 12 - c["misfire"] * 20 - c.get("refund", 0) * 5
    defiance = held * 120
    total = endurance + stewardship + execution + defiance + stolen - taken + vigilance
    if total >= 900:
        rank, line = "REMEMBERED", "They still use your name for the road."
    elif total >= 550:
        rank, line = "RECORDED", "A clerk wrote you down. That is not nothing."
    elif total >= 300:
        rank, line = "TOLERATED", "The reach outlived you and did not comment."
    elif total >= 120:
        rank, line = "MISLAID", "Two generations, and the ledger is the only proof."
    else:
        rank, line = "UNMOURNED", "Nobody agrees how long you were even there."
    return {
        "total": total, "rank": rank, "line": line,
        "lifespan": round(lifespan, 1), "held": held, "lost": lost,
        "endurance": endurance, "stewardship": stewardship,
        "execution": execution, "defiance": defiance,
        "plunder": stolen, "losses": -taken, "vigilance": vigilance,
    }


def snapshot(sess: dict) -> dict:
    return deepcopy(sess)

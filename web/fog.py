"""Player-facing view of a world. Never emits a `true` fact."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import engine

try:
    from zoneinfo import ZoneInfo
    WORLD_TZ = ZoneInfo("America/Toronto")
except Exception:
    WORLD_TZ = timezone.utc


def _watching(s, f):
    posted = s["tick"] <= s.get("watch_until", 0)
    general = posted and s.get("watch_mode") == "general"
    return posted and not general and s["watching"] == f["id"]


def _posted(s):
    return s["tick"] <= s.get("watch_until", 0)


def fog_front(s, f):
    posted = _posted(s)
    general = posted and s.get("watch_mode") == "general"
    seen = _watching(s, f)
    out = {
        "id": f["id"],
        "name": f["name"],
        "style": f["style"],
        "wants": f["wants"],
        "doing": f["doing"],
        "aggression": f["aggression"],
        "expansive": f["expansive"],
        "openness": f["openness"],
        "done": f["done"] if s.get("status") == "settled" else False,
        "watched": seen,
        "sight": "exact" if seen else ("band" if general else "fog"),
    }
    if s.get("status") == "settled":
        out["clock"] = f["clock"]
        out["sight"] = "exact"
        out["label"] = f'{f["clock"]}/10'
        return out
    if seen:
        out["clock"] = f["clock"]
        out["label"] = f'{f["clock"]}/10'
    elif general:
        b = engine.band(f["clock"])
        out["band"] = b
        out["label"] = b["word"]
    else:
        out["clock"] = None
        out["label"] = "unknown"
    return out


def fog_ledger(s):
    settled = s.get("status") == "settled"
    rows = []
    for e in s.get("ledger", [])[-80:]:
        t = e.get("t")
        if t == "clock" and not settled:
            if not e.get("gained") or not e.get("watched"):
                continue
        if t == "clock":
            rows.append({
                "t": "clock", "at": e["at"], "front": e["front"],
                "roll": e["roll"], "mods": e["mods"], "total": e["total"],
                "threshold": e["threshold"], "gained": e["gained"],
                "seg": e.get("seg"),
            })
        elif t in ("action", "mega", "raid", "interest"):
            rows.append({k: e[k] for k in e if k != "id"})
    return list(reversed(rows))


def fog_facts(s):
    out = []
    for fact in s.get("facts", []):
        if fact.get("visibility") == "true" and s.get("status") != "settled":
            continue
        out.append({
            "at": fact.get("at"),
            "fact": fact["fact"],
            "note": fact.get("note", ""),
            # known / suspected / false render identically during play
            "visibility": fact["visibility"] if s.get("status") == "settled"
            else "held",
        })
    return out[-12:]


def horizon_safe(s):
    rows = []
    for r in engine.horizon(s):
        if r.get("rumour") and r.get("hours") is None:
            rows.append({
                "front": r["front"], "id": r["id"], "rumour": True,
                "line": f'Nothing reliable has come back from {r["front"]}.',
            })
        else:
            days = r.get("days")
            rows.append({
                "front": r["front"], "id": r["id"], "rumour": bool(r.get("rumour")),
                "hours": r.get("hours"), "days": days,
                "line": (f'{r["front"]} looks about {days} day(s) from finishing.'
                         if days is not None else f'{r["front"]} is moving.'),
            })
    return rows


def world_mode(s):
    last = datetime.fromisoformat(s["last_tick"]).astimezone(WORLD_TZ)
    wh = last.hour
    if 5 <= wh < 10:
        mode, watch = "morning", "the dawn watch"
    elif 10 <= wh < 17:
        mode, watch = "day", "the day watch"
    elif 17 <= wh < 21:
        mode, watch = "sunset", "the dusk watch"
    else:
        mode, watch = "night", "the night watch"
    return {
        "mode": mode,
        "watch_name": watch,
        "clock": last.strftime("%H:%M"),
        "when": last.isoformat(),
    }


def options(s):
    coin, hands = s["holding"]["coin"], s["holding"]["hands"]
    out = []
    for k, spec in engine.ACTIONS.items():
        if k == "improvise":
            continue
        if k == "mega":
            if coin >= engine.MEGA_MIN_COIN:
                out.append({"kind": k, "cost": coin, "hands": 0,
                            "affordable": True,
                            "label": "MEGA — spend everything"})
            continue
        out.append({
            "kind": k, "cost": spec["cost"], "hands": spec["hands"],
            "affordable": spec["cost"] <= coin and spec["hands"] <= hands,
            "label": spec["label"],
        })
    return {
        "coin": coin,
        "hands": round(hands, 1),
        "slots_left": engine.QUEUE_SLOTS - len(s["queue"]),
        "options": out,
    }


def view(s):
    posted = _posted(s)
    general = posted and s.get("watch_mode") == "general"
    watching = None
    if posted and not general:
        watching = next((f["name"] for f in s["factions"] if s["watching"] == f["id"]),
                        None)
    effects = []
    for e in s.get("effects", []):
        left = e["until"] - s.get("tick", 0)
        if left <= 0:
            continue
        who = None
        if e.get("front"):
            fr = next((x for x in s["factions"] if x["id"] == e["front"]), None)
            who = fr["name"] if fr else e["front"]
        effects.append({
            "kind": e["kind"], "front": who, "value": e["value"],
            "hours_left": left * engine.TICK_HOURS,
        })
    last = datetime.fromisoformat(s["last_tick"])
    queue = []
    for i, q in enumerate(s["queue"]):
        fires = last + timedelta(hours=engine.TICK_HOURS * (i + 1))
        queue.append({
            "what": q.get("what"), "kind": q.get("kind"),
            "cost": "ALL" if q.get("kind") == "mega" else q.get("cost", 0),
            "target": q.get("target"),
            "fires": fires.isoformat(),
            "said": q.get("said", ""),
        })
    return {
        "seed": s["seed"],
        "status": s.get("status", "live"),
        "day": s.get("day", 1),
        "tick": s.get("tick", 0),
        "holding": {
            "name": s["holding"]["name"],
            "coin": s["holding"]["coin"],
            "hands": round(s["holding"]["hands"], 1),
            "standing": s["holding"].get("standing", "intact"),
        },
        "watch": {
            "mode": "general" if general else ("focused" if posted else "none"),
            "name": watching,
            "posted": posted,
        },
        "fronts": [fog_front(s, f) for f in s["factions"]],
        "queue": queue,
        "effects": effects,
        "ledger": fog_ledger(s),
        "facts": fog_facts(s),
        "horizon": horizon_safe(s) if s.get("status") != "settled" else [],
        "world": world_mode(s),
        "options": options(s),
        "epilogue": s.get("epilogue"),
        "score": s.get("score"),
        "chronicle": s.get("chronicle"),
        "settled": s.get("status") == "settled",
    }

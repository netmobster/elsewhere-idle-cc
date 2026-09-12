"""Elsewhere — fast-forward simulator.

Drives the engine with a scripted player so a week can be played in a second.
Records what the player decided each day and what the dice did about it.

    python sim.py                 # run all three strategies, 7 days each
    python sim.py attentive 14    # one strategy, N days

Strategies are deliberately different so the sims test the design instead of
repeating it:
    attentive  — turns up every day, watches the fastest threat, queues full
    absentee   — one turn on day 1, then vanishes for the rest of the week
    erratic    — plays most days, changes its mind about what to watch constantly
"""

import json, sys, random, zlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import engine

HERE = Path(__file__).parent
OUT = HERE / "sims"
OUT.mkdir(exist_ok=True)

import engine as E

GOALS = [
    "Keep the coast open. Everything else is negotiable.",
    "I want the barrow left alone and I will spend to make that true.",
    "Trade my way out of this. Fighting is for people with coin.",
    "Hold the reach. Slow whoever is fastest.",
    "Stop bleeding money. Nothing ambitious this week.",
]


def want(kind, front, s):
    """Turn an intent into a queue entry, if the holding can pay for it."""
    spec = E.ACTIONS[kind]
    if kind == "mega":
        if s["holding"]["coin"] < E.MEGA_MIN_COIN:
            return None
        return {"what": f'MEGA PROJECT against {front["name"]}', "kind": "mega",
                "cost": s["holding"]["coin"], "target": front["id"],
                "clock_at_queue": front["clock"]}
    if spec["cost"] > s["holding"]["coin"]:
        return None
    label = spec["label"].format(front=front["name"] if front else "the reach")
    s["holding"]["coin"] -= 0   # charged at execution, not at queue time
    return {"what": label, "kind": kind, "cost": spec["cost"],
            "target": front["id"], "clock_at_queue": front["clock"]}


def plan_attentive(s, rng, live, day, recently_raided):
    """Spend on what the world is actually doing. Priority order matters."""
    plan, budget = [], s["holding"]["coin"]
    lead = max(live, key=lambda f: f["clock"])
    rich = max(live, key=lambda f: f["openness"])

    def take(kind, front):
        nonlocal budget
        c = E.ACTIONS[kind]["cost"]
        if c <= budget and len(plan) < 5:
            budget -= c
            plan.append((kind, front))

    if budget < 90:                        # income first, always
        take("trade", rich)
    if lead["clock"] >= 5:                 # slow whoever is winning
        take("disrupt", lead)
    if recently_raided:
        take("fortify", lead)
    if day <= 2:
        take("invest", lead)
    take("disrupt", lead)
    take("trade", rich)
    for f in live:                         # buy information on the unseen
        if f["id"] != s["watching"]:
            take("scout", f)
    return plan


def plan_hoarder(s, rng, live, day):
    """Spend nothing; compound; then bet the whole purse on one great work.

    The hypothesis under test: faction advance + raids should mean a hoarder
    never catches up, because the world does not wait for the purse to fill.
    """
    coin = s["holding"]["coin"]
    if coin >= HOARD_TRIGGER:
        lead = max(live, key=lambda f: f["clock"])
        return [("mega", lead)]
    # keep one cheap order running so the holding still earns and compounds
    rich = max(live, key=lambda f: f["openness"])
    return [("trade", rich)]


HOARD_TRIGGER = 800   # go for the MYTHIC tier: nothing else is worth the silence


def play_day(s, rng, strategy, day, recently_raided):
    """Return the turn the player took, or None if they did not turn up."""
    live = [f for f in s["factions"] if not f["done"]]
    if not live:
        return None
    if strategy == "absentee" and day > 1:
        return None
    if strategy == "erratic" and rng.random() < 0.3:
        return None

    if strategy in ("attentive", "hoarder"):
        watch = max(live, key=lambda f: f["clock"] * 2 + f["expansive"] + f["aggression"])
    elif strategy == "erratic":
        watch = rng.choice(live)
    else:
        watch = max(live, key=lambda f: f["expansive"] + f["aggression"])
    s["watching"] = watch["id"]
    s["watch_until"] = s.get("tick", 0) + E.WATCH_TICKS

    room = 5 - len(s["queue"])
    if room <= 0:
        return {"watch": watch["name"], "queued": [], "spend": 0,
                "goal": rng.choice(GOALS)}

    if strategy == "attentive":
        plan = plan_attentive(s, rng, live, day, recently_raided)[:room]
    elif strategy == "hoarder":
        plan = plan_hoarder(s, rng, live, day)[:room]
    else:
        budget, plan = s["holding"]["coin"], []
        for _ in range(room):
            k = rng.choice(list(E.ACTIONS))
            c = E.ACTIONS[k]["cost"]
            if c <= budget:
                budget -= c
                plan.append((k, rng.choice(live)))

    queued = []
    for kind, front in plan:
        e = want(kind, front, s)
        if e:
            s["queue"].append(e)
            queued.append(e["what"])
    return {"watch": watch["name"], "queued": queued,
            "spend": sum(s["holding"]["coin"] if k == "mega" else E.ACTIONS[k]["cost"]
                         for k, _ in plan),
            "goal": rng.choice(GOALS)}


def run(strategy, days=7, seed=None):
    # stable across processes — hash() is salted per interpreter run
    rng = random.Random(zlib.crc32(strategy.encode()) ^ (seed or 0))
    s = engine.new_world(seed)
    start = datetime.now(timezone.utc)
    s["created"] = s["last_tick"] = start.isoformat()

    log, recent_raid = [], False
    for day in range(1, days + 1):
        decision = play_day(s, rng, strategy, day, recent_raid)
        before = len(s["ledger"])
        out = engine.tick(s, start + timedelta(days=day))
        rows = s["ledger"][before:]

        acts = [e for e in rows if e["t"] == "action"]
        raids = [e for e in rows if e["t"] == "raid"]
        log.append({
            "day": day,
            "turned_up": decision is not None,
            "decision": decision,
            "outcomes": [{"what": a["what"], "outcome": a["outcome"],
                          "roll": a["roll"], "drift": a["drift"],
                          "total": a["total"]} for a in acts],
            "raids": [{"front": r["front"], "taken": r["taken"]} for r in raids],
            "clocks": {f["name"]: f["clock"] for f in s["factions"]},
            "watching": next((f["name"] for f in s["factions"]
                              if f["id"] == s["watching"]), None),
            "coin": s["holding"]["coin"],
            "settled": s.get("status") == "settled",
        })
        recent_raid = bool(raids)
        if s.get("status") == "settled":
            break

    payload = {"strategy": strategy, "days_played": len(log),
               "log": log, "final": s}
    (OUT / f"{strategy}.json").write_text(json.dumps(payload, indent=2),
                                          encoding="utf-8")
    return payload


if __name__ == "__main__":
    if len(sys.argv) > 1:
        p = run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 7)
        print(f'{p["strategy"]}: {p["days_played"]} days')
    else:
        for strat in ("attentive", "absentee", "erratic"):
            p = run(strat, 7, seed=8812)
            f = p["final"]
            print(f'{strat:<10} {p["days_played"]}d  coin {f["holding"]["coin"]:>4}  '
                  f'settled={f.get("status")=="settled"}  '
                  + " ".join(f'{x["clock"]}/10' for x in f["factions"]))

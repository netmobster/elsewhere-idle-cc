"""Elsewhere — V0.1 engine.

The one principle, borrowed from SEREN:
    The model narrates a result it did not choose.

Everything that decides an outcome happens in here, is seeded, and is written to
the ledger with its arithmetic showing. The narrator reads the ledger. It does
not get a vote.

Usage:
    python engine.py new [--seed N]      generate a world, write state.json
    python engine.py queue "a" "b" ...   set the action queue (max QUEUE_SLOTS)
    python engine.py tick [--now ISO]    advance the world to now, resolve queue
    python engine.py status              print current state as JSON
"""

import json, random, sys, argparse, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent
STATE = HERE / "state.json"

# ---------------------------------------------------------------- tunables

TICK_HOURS       = 8      # one world tick = 8 real hours
SEGMENTS         = 10     # clock segments to completion
CLOCK_DIE        = 6      # d6 per advance roll
CLOCK_THRESHOLD  = 6      # roll+mods >= this advances a segment
DOUBLE_AT        = 10     # ... and >= this advances two
# 5/8 was calibrated when the world only settled once ALL THREE agendas
# finished. Settling on the FIRST one cut every world from ~17 days to ~6 and
# inverted the balance: the hoarder beat careful play in 8 of 12 seeds, because
# compounding interest does not care how short the game is but spending does.
# Slowing the clocks restores the long world the rest of the design assumes.
MISFIRE_IN       = 4      # 1 in N queued actions degrades (chaos dial)
DRIFT_CAP        = 2      # a stale plan is damaged, never auto-void
RAID_COOLDOWN    = 6      # ticks a front must wait between raids
WATCH_TICKS      = 9
# Two ways to spend your one lookout:
#   focused  — one neighbour: exact bar, −1 to their rolls, they will not raid you
#   general  — all three from the hill: a rough band only, no brake, no protection
WATCH_MODES      = ("focused", "general")      # eyes stay posted 3 days past your last order, then go home
QUEUE_SLOTS      = 5      # 3 fire per day, so ~2 turns of proxy if you vanish
HANDS_CAP        = 10
HANDS_PER_TICK   = 0.5
COIN_PER_TICK    = 10
HOARD_RATES      = [0.10, 0.15, 0.25, 0.40]   # compounding, per consecutive unspent day      # the holding earns; without this a broke player is stuck broke
START_COIN       = 200
MAX_NARRATED     = 12     # beats above this collapse into an era summary

VISIBILITY = ("true", "known", "suspected", "false")

# Action catalogue. `kind` decides what a landed action DOES to the world.
#   disrupt  negative mod on a front's clock rolls
#   fortify  raises the bar a raid must clear against the holding
#   trade    converts a front's openness into coin
#   scout    reveals a front's true clock (a `known` fact, no watch spent)
#   invest   raises hands production
ACTIONS = {
    "disrupt": {"cost": 60, "hands": 2, "value": 3, "ticks": 12,
                "label": "Disrupt {front}"},
    "fortify": {"cost": 50, "hands": 2, "value": 3, "ticks": 12,
                "label": "Fortify the reach"},
    "trade":   {"cost": 20, "hands": 1, "value": 0, "ticks": 0,
                "label": "Open trade with {front}"},
    "scout":   {"cost": 30, "hands": 1, "value": 0, "ticks": 0,
                "label": "Scout {front}"},
    "invest":  {"cost": 40, "hands": 1, "value": 1, "ticks": 15,
                "label": "Invest in the holding"},
    # IMPROVISE — the fourth surface. Costs and effects are supplied per-attempt;
    # the roll, the ladder and the outcome are the engine's, exactly as for any
    # other order. See resolve_improvised().
    "improvise": {"cost": 0, "hands": 0, "value": 0, "ticks": 12,
                  "label": "{front}"},
    # MEGA — costs everything you have. Lands enormous, or MUTATES.
    "mega":    {"cost": 0, "hands": 0, "value": 6, "ticks": 24,
                "label": "MEGA PROJECT: {front}"},
}

MEGA_MIN_COIN = 150   # below this the project is not credible enough to attempt

# ---------------------------------------------------------------- factions

STYLES = ["builders", "raiders", "merchants", "zealots", "diggers"]
WANTS = {
    "builders":  "to raise a second wall across the reach",
    "raiders":   "to make the coast road impassable to anyone but them",
    "merchants": "to hold every lease between the docks and the pass",
    "zealots":   "to wake the thing under the barrow",
    "diggers":   "to reach whatever the old company stopped digging for",
}
DOING = {
    "builders":  "quarrying above the treeline",
    "raiders":   "burning waystations, one a week",
    "merchants": "buying up salvage rights along the coast",
    "zealots":   "singing at the barrow mouth, in shifts",
    "diggers":   "sinking a shaft nobody was asked about",
}
NAMES_A = ["Sundered", "Salt", "Ninth", "Quiet", "Iron", "Pale", "Long", "Broken"]
NAMES_B = ["Choir", "Company", "Kindred", "Charter", "Hand", "Assembly", "Watch"]

# The holding is named per world. "Varn's Reach" was a placeholder that got
# hardcoded; it survives here as one roll among many.
HOLD_A = ["Varn", "Aldec", "Morrow", "Keld", "Thyre", "Ossen", "Brack", "Nieve",
          "Harrow", "Culm", "Dray", "Fen"]
HOLD_B = ["Reach", "Landing", "Hold", "Crossing", "Rest", "Bastion", "Wend",
          "Stair", "Gate", "Mire"]


def gen_faction(rng, taken, used_styles):
    words = {w for t in taken for w in t.split()[1:]}
    while True:
        name = f"The {rng.choice(NAMES_A)} {rng.choice(NAMES_B)}"
        if not (set(name.split()[1:]) & words):
            break
    style = rng.choice([x for x in STYLES if x not in used_styles])
    return {
        "id": name.lower().replace("the ", "").replace(" ", "-"),
        "name": name,
        "style": style,
        "wants": WANTS[style],
        "doing": DOING[style],
        # personality vector — these bias existing rolls, they add no new systems
        "aggression":   rng.randint(1, 6),   # will it take from an undefended holding
        "expansive":    rng.randint(1, 6),   # clock speed
        "openness":     rng.randint(1, 6),   # will it trade with you
        "clock": 0,
        "done": False,
    }


def new_world(seed=None):
    seed = seed if seed is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    taken, factions = set(), []
    for _ in range(3):
        f = gen_faction(rng, taken, {x["style"] for x in factions})
        taken.add(f["name"])
        factions.append(f)
    now = datetime.now(timezone.utc)
    return {
        "seed": seed,
        "created": now.isoformat(),
        "last_tick": now.isoformat(),
        "day": 1,
        "holding": {"name": f"{rng.choice(HOLD_A)}'s {rng.choice(HOLD_B)}",
                    "coin": START_COIN, "hands": 4.0, "standing": "intact"},
        "watching": factions[0]["id"],
        "watch_mode": "focused",
        "watch_until": WATCH_TICKS,
        "factions": factions,
        "status": "live",
        "hoard": 0,
        "tick": 0,
        "effects": [],
        "queue": [],
        "ledger": [],
        "facts": [],
    }

# ---------------------------------------------------------------- mutations

def _m_wrong_front(s, rng, f, spent):
    others = [x for x in s["factions"] if x["id"] != f["id"] and not x["done"]]
    if not others:
        return _m_windfall(s, rng, f, spent)
    o = rng.choice(others)
    o["clock"] = max(0, o["clock"] - 5)
    return ("WRONG FRONT",
            f'Everything you built landed on {o["name"]} instead. '
            f'They are five segments further from what they wanted, and they '
            f'have no idea why. {f["name"]} did not notice at all.')


def _m_schism(s, rng, f, spent):
    taken = {x["name"] for x in s["factions"]}
    used = {x["style"] for x in s["factions"]}
    n = gen_faction(rng, taken, used if len(used) < len(STYLES) else set())
    n["clock"] = max(0, f["clock"] - 2)
    f["clock"] = max(0, f["clock"] - 2)
    s["factions"].append(n)
    return ("SCHISM",
            f'{f["name"]} broke in half under the pressure. {n["name"]} walked out '
            f'with a {n["style"]} agenda of its own. You now have one more problem '
            f'than you started with, and both halves are slower than the whole was.')


def _m_inversion(s, rng, f, spent):
    c, hnd = s["holding"]["coin"], s["holding"]["hands"]
    s["holding"]["coin"] = int(hnd * 30)
    s["holding"]["hands"] = min(HANDS_CAP, c / 30.0)
    return ("INVERSION",
            f'The project did something to the money. Coin and labour traded places '
            f'at thirty to one — you now hold {s["holding"]["coin"]} coin and '
            f'{s["holding"]["hands"]:.0f} hands. Nobody can explain the exchange rate.')


def _m_isolation(s, rng, f, spent):
    s["effects"].append({"kind": "fortify", "front": None, "value": 9,
                         "until": s["tick"] + 60})
    s["holding"]["isolated"] = True
    return ("THE WALL WORKED",
            'It worked. It worked far past where you wanted it to stop. Nothing can '
            'reach the reach any more — not raiders, not merchants, not news. '
            'Raids cannot touch you. Neither can trade.')


def _m_awakening(s, rng, f, spent):
    for x in s["factions"]:
        x["aggression"] = min(6, x["aggression"] + 2)
        x["openness"] = max(1, x["openness"] - 2)
    return ("SOMETHING WOKE",
            'Whatever the project disturbed, every faction felt it. All of them are '
            'more aggressive and less willing to talk than they were this morning. '
            'Nobody will say what they saw.')


def _m_audience(s, rng, f, spent):
    s["holding"]["watch_inverted"] = True
    return ("THEY PERFORM",
            'A core rule of the world quietly changed. Being watched no longer slows '
            'a faction down — it speeds them up. They are playing to an audience now, '
            'and you are it.')


def _m_benefactor(s, rng, f, spent):
    gift = spent * 3
    s["holding"]["coin"] += gift
    taken = {x["name"] for x in s["factions"]}
    n = gen_faction(rng, taken, {x["style"] for x in s["factions"]})
    n["aggression"] = 6
    n["wants"] = "to collect on a debt the reach does not remember taking"
    n["doing"] = "counting, patiently, from somewhere upriver"
    s["factions"].append(n)
    return ("A BENEFACTOR",
            f'{gift} coin arrived with no note. Within the week {n["name"]} appeared '
            f'upriver, and what they want is to be paid back.')


def _m_timeslip(s, rng, f, spent):
    for x in s["factions"]:
        if not x["done"]:
            x["clock"] = min(SEGMENTS, x["clock"] + 3)
    return ("TIME SLIPPED",
            'Three days happened at once. Every clock in the reach jumped three '
            'segments while the work was still being unpacked.')


def _m_windfall(s, rng, f, spent):
    f["clock"] = max(0, f["clock"] - 6)
    return ("IT SIMPLY WORKED",
            f'No twist. {f["name"]} is six segments further from what it wanted, and '
            f'the reach is talking about it. Sometimes the wish is just granted.')


def _m_hollow(s, rng, f, spent):
    s["holding"]["hands"] = 0.0
    f["clock"] = max(0, f["clock"] - 4)
    return ("IT ATE THE LABOUR",
            f'It worked — {f["name"]} lost four segments — and it consumed every pair '
            f'of hands in the reach doing it. There is nobody left to start anything '
            f'for a while.')


MUTATIONS = [
    (_m_windfall,    "good"),
    (_m_hollow,      "mixed"),
    (_m_wrong_front, "mixed"),
    (_m_schism,      "world"),
    (_m_benefactor,  "mixed"),
    (_m_isolation,   "world"),
    (_m_awakening,   "bad"),
    (_m_inversion,   "world"),
    (_m_audience,    "world"),
    (_m_timeslip,    "bad"),
]

# ---------------------------------------------------------------- helpers

def load():
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(s):
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def eid(s, p="e"):
    n = sum(1 for r in s["ledger"] if r["id"].startswith(p)) + 1
    return f"{p}{n:03d}"


def tick_rng(s, tick_no):
    """Deterministic per-tick RNG: same seed + same tick = same world, always."""
    h = hashlib.sha256(f'{s["seed"]}:{tick_no}'.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def add_fact(s, statement, visibility, note=""):
    s["facts"].append({
        "id": f"f{len(s['facts'])+1:03d}",
        "at": s["last_tick"],
        "fact": statement,
        "visibility": visibility,   # true | known | suspected | false
        "note": note,
    })

def effect(s, kind, front=None):
    """Total live value of an effect kind, optionally scoped to one front."""
    return sum(e["value"] for e in s["effects"]
               if e["kind"] == kind and e["until"] > s["tick"]
               and (front is None or e.get("front") == front))


def expire(s):
    s["effects"] = [e for e in s["effects"] if e["until"] > s["tick"]]


# ---------------------------------------------------------------- the tick

def advance_world(s, rng, at, tick_no):
    """One tick. Every faction rolls to advance its clock."""
    events = []
    for f in s["factions"]:
        if f["done"]:
            continue
        posted = s["tick"] <= s.get("watch_until", 0)
        general = s.get("watch_mode") == "general"
        watched = posted and not general and s["watching"] == f["id"]
        roll = rng.randint(1, CLOCK_DIE)
        mods = [["expansive", f["expansive"] // 3]]
        if not watched:
            mods.append(["unwatched", 1])
        elif s["holding"].get("watch_inverted"):
            mods.append(["performing", 2])
        else:
            mods.append(["watched", -1])
        dis = effect(s, "disrupt", f["id"])
        if dis:
            mods.append(["disrupted", -dis])
        total = roll + sum(m[1] for m in mods)

        gained = 2 if total >= DOUBLE_AT else (1 if total >= CLOCK_THRESHOLD else 0)
        if gained:
            f["clock"] = min(SEGMENTS, f["clock"] + gained)

        s["ledger"].append({
            "id": eid(s), "at": at.isoformat(), "t": "clock", "front": f["id"],
            "roll": roll, "mods": mods, "total": total,
            "threshold": CLOCK_THRESHOLD, "gained": gained,
            "seg": f'{f["clock"]}/{SEGMENTS}', "watched": watched,
        })

        if gained and watched:
            events.append(("clock", f, gained))

        if f["clock"] >= SEGMENTS and not f["done"]:
            f["done"] = True
            events.append(("complete", f, None))
            # A finished agenda is never hideable. A wall goes up, a barrow opens,
            # a road closes — the whole reach finds out whether it was watching or
            # not. This is the one thing fog does not cover.
            add_fact(s, f'{f["name"]} got what it wanted: {f["wants"]}.', "known",
                     "everyone knows. This kind of thing cannot be kept quiet.")

        # aggression: take from an undefended holding while you are gone
        if (not watched and f["aggression"] >= 5
                and tick_no - f.get("last_raid", -99) >= RAID_COOLDOWN):
            r2 = rng.randint(1, CLOCK_DIE)
            fort = effect(s, "fortify")
            if r2 + f["aggression"] // 2 >= DOUBLE_AT + fort:
                purse = s["holding"]["coin"]
                taken = min(purse, int(10 * f["aggression"] + purse * 0.12 * f["aggression"] / 6))
                if taken <= 0:
                    continue
                f["last_raid"] = tick_no
                s["holding"]["coin"] -= taken
                s["ledger"].append({
                    "id": eid(s), "at": at.isoformat(), "t": "raid",
                    "front": f["id"], "roll": r2,
                    "mods": [["aggression", f["aggression"] // 2]],
                    "total": r2 + f["aggression"] // 2,
                    "threshold": DOUBLE_AT + effect(s, "fortify"),
                    "taken": taken,
                })
                events.append(("raid", f, taken))
                add_fact(s, f'{f["name"]} took {taken} coin from the reach.',
                         "suspected", "you were not here; the count is a guess")
    return events


def resolve_action(s, rng, action, at):
    """An action checks its preconditions when it EXECUTES, not when queued.

    ok / partial / refund / misfire. A landed action APPLIES ITS EFFECT to the
    world — that is the whole difference between v0.1 and this.
    """
    kind = action.get("kind", "disrupt")
    spec = ACTIONS[kind]
    cost = action.get("cost", spec["cost"])

    if kind == "mega":
        return resolve_mega(s, rng, action, at)
    if kind == "improvise":
        return resolve_improvised(s, rng, action, at)
    tgt = action.get("target")
    f = next((x for x in s["factions"] if x["id"] == tgt), None)

    drift = min((f["clock"] - action.get("clock_at_queue", f["clock"])) if f else 0,
                DRIFT_CAP)
    roll = rng.randint(1, CLOCK_DIE)
    mods = [["drift", -drift]]
    total = roll - drift

    if rng.randint(1, MISFIRE_IN) == 1 and drift > 0:
        outcome, refund, power = "misfire", 0, 0.0
    elif total >= 4:
        outcome, refund, power = "ok", 0, 1.0
    elif total >= 2:
        outcome, refund, power = "partial", cost // 2, 0.5
    else:
        outcome, refund, power = "refund", cost, 0.0

    s["holding"]["coin"] -= (cost - refund)
    s["holding"]["hands"] = max(0, s["holding"]["hands"] - spec["hands"] * (1 if power else 0))

    gain = 0
    if power:
        if kind in ("disrupt", "fortify", "invest"):
            s["effects"].append({
                "kind": kind, "front": tgt if kind == "disrupt" else None,
                "value": max(1, round(spec["value"] * power)),
                "until": s["tick"] + spec["ticks"]})
        elif kind == "trade" and f:
            gain = round(f["openness"] * 12 * power)
            s["holding"]["coin"] += gain
        elif kind == "scout" and f:
            add_fact(s, f'{f["name"]} stands at {f["clock"]}/{SEGMENTS}.', "known",
                     "scouted, so this number is real")

    s["ledger"].append({
        "id": eid(s), "at": at.isoformat(), "t": "action", "kind": kind,
        "what": action["what"], "target": tgt, "roll": roll, "mods": mods,
        "total": total, "drift": drift, "outcome": outcome,
        "cost": cost, "refund": refund, "gain": gain,
    })
    return outcome


def resolve_improvised(s, rng, action, at):
    """A bespoke order the player invented. The engine still rules on it.

    action carries: what, target, coin, hands, and `grants` — a list of
    (kind, value, ticks) the attempt applies if it lands. Openness of the target
    modifies the roll, because a receptive neighbour is an easier sell.
    """
    tgt = action.get("target")
    f = next((x for x in s["factions"] if x["id"] == tgt), None)
    coin = int(action.get("coin", 0))
    hands = float(action.get("hands", 0))

    receptive = (f["openness"] // 2) if f else 0
    strain = 1 if hands >= 6 else 0          # committing every hand is a stretch
    roll = rng.randint(1, CLOCK_DIE)
    mods = [["receptive", receptive], ["overreach", -strain]]
    total = roll + receptive - strain

    s["holding"]["coin"] = max(0, s["holding"]["coin"] - coin)
    s["holding"]["hands"] = max(0.0, s["holding"]["hands"] - hands)

    if total >= 8:
        outcome, power = "ok", 1.0
    elif total >= 5:
        outcome, power = "partial", 0.5
    else:
        outcome, power = "refund", 0.0

    # Plunder, if the attempt was after something portable.
    gain = 0
    want = int(action.get("gain", 0))
    if want and power:
        gain = round(want * power * (1 + (f["openness"] if f else 0) / 12))
        s["holding"]["coin"] += gain

    # Coming home. Anything less than a half-landing and they do not.
    lost = 0.0
    if action.get("perilous"):
        if power:
            s["holding"]["hands"] = min(HANDS_CAP, s["holding"]["hands"] + hands)
        else:
            lost = hands

    granted = []
    if power:
        for kind, value, ticks in action.get("grants", []):
            v = max(1, round(value * power))
            # Only disrupt/fortify/invest are ever READ back out of s["effects"].
            # Granting a "trade" or a "scout" used to append an effect nobody
            # consumes, so the order landed, reported success, and did nothing.
            # These resolve immediately, exactly as the menu versions do.
            if kind == "trade":
                paid = round((f["openness"] if f else 3) * 4 * v * power)
                s["holding"]["coin"] += paid
                gain += paid
                granted.append(f"trade {paid} coin")
            elif kind == "scout" and f:
                add_fact(s, f'{f["name"]} stands at {f["clock"]}/{SEGMENTS}.', "known",
                         "scouted, so this number is real")
                granted.append("scout")
            elif kind == "hands":
                # There was no way to improvise a net gain of people. A feast
                # thrown to make babies is the most obvious improvised order in
                # the game and it had no mechanism behind it.
                before = s["holding"]["hands"]
                s["holding"]["hands"] = min(HANDS_CAP, before + v)
                got = s["holding"]["hands"] - before
                granted.append(f"hands +{got:g}")
            else:
                s["effects"].append({"kind": kind,
                                     "front": tgt if kind == "disrupt" else None,
                                     "value": v, "until": s["tick"] + ticks})
                granted.append(f"{kind} {v}")
        if f and action.get("beholden"):
            f["openness"] = min(6, f["openness"] + (2 if power == 1.0 else 1))
            f["aggression"] = max(1, f["aggression"] - (2 if power == 1.0 else 1))
            granted.append("beholden")

    s["ledger"].append({
        "id": eid(s), "at": at.isoformat(), "t": "action", "kind": "improvise",
        "what": action["what"], "target": tgt, "roll": roll, "mods": mods,
        "total": total, "drift": 0, "outcome": outcome,
        "cost": coin, "refund": 0, "gain": gain,
        "granted": granted, "hands_spent": hands, "hands_lost": lost,
        # The player's own phrasing, kept verbatim. The chronicle is written in
        # the register the player used — "hopefully not dying too much" is a
        # voice, and the story should sound like the world talking back to THAT
        # person. Never paraphrased, never cleaned up.
        "said": action.get("said", ""),
    })
    if power and f:
        add_fact(s, action.get("fact")
                 or f'Something changed in how {f["name"]} deals with the reach.',
                 "known")
    return outcome


def resolve_mega(s, rng, action, at):
    """Everything you have, on one thing. It lands, or the wish is granted sideways."""
    tgt = action.get("target")
    f = next((x for x in s["factions"] if x["id"] == tgt), None)
    spent = action.get("cost", s["holding"]["coin"])
    s["holding"]["coin"] = max(0, s["holding"]["coin"] - spent)
    s["holding"]["hands"] = 0.0

    drift = min((f["clock"] - action.get("clock_at_queue", f["clock"])) if f else 0,
                DRIFT_CAP)
    roll = rng.randint(1, CLOCK_DIE) + rng.randint(1, CLOCK_DIE)   # 2d6
    scale = min(6, spent // 150)        # the stake buys odds. dare bigger, land easier.
    total = roll + scale - drift * 2

    row = {"id": eid(s), "at": at.isoformat(), "t": "mega", "what": action["what"],
           "target": tgt, "roll": roll, "dice": "2d6",
           "mods": [["scale", scale], ["drift", -drift * 2]],
           "total": total, "threshold": 9, "spent": spent}

    if total >= 9:
        wipe = 4 + scale                      # a big enough bet erases a whole clock
        f["clock"] = max(0, f["clock"] - wipe)
        s["effects"].append({"kind": "disrupt", "front": tgt, "value": 4 + scale // 2,
                             "until": s["tick"] + 24})
        # MYTHIC: an enormous stake rolled well does not just win, it resets the board
        mythic = spent >= 800 and total >= 14
        if mythic:
            for x in s["factions"]:
                if x["id"] != tgt and not x["done"]:
                    x["clock"] = max(0, x["clock"] - 3)
            s["holding"]["coin"] += spent // 2
        row.update({"outcome": "mythic" if mythic else "landed",
                    "wipe": wipe, "mutation": None})
        s["ledger"].append(row)
        add_fact(s,
                 (f'The great work against {f["name"]} did not merely succeed. Every '
                  f'front in the reach lost ground and half the treasury came back.')
                 if mythic else
                 f'The great work against {f["name"]} succeeded outright.', "known")
        return "mega_mythic" if mythic else "mega_landed"

    # A larger stake does not avoid the twist — it buys a better class of twist.
    WEIGHT = {"good": 1 + scale, "world": 1 + scale // 2, "mixed": 3, "bad": max(1, 5 - scale)}
    pool = [i for i, (_, fl) in enumerate(MUTATIONS) for _ in range(WEIGHT[fl])]
    idx = pool[rng.randrange(len(pool))]
    fn, flavour = MUTATIONS[idx]
    name, tale = fn(s, rng, f, spent)
    row.update({"outcome": "mutated", "mutation": name, "flavour": flavour,
                "tale": tale})
    s["ledger"].append(row)
    add_fact(s, tale, "known", "you were there when it happened")
    s.setdefault("mutations", []).append({"at": at.isoformat(), "name": name,
                                          "flavour": flavour, "tale": tale})
    return "mega_mutated"


def spec_value():
    return 6


def tick(s, now=None):
    now = now or datetime.now(timezone.utc)
    last = datetime.fromisoformat(s["last_tick"])
    elapsed = (now - last).total_seconds()
    ticks = int(elapsed // (TICK_HOURS * 3600))
    if ticks < 1:
        return {"ticks": 0, "events": [], "actions": []}

    start_len = len(s["ledger"])
    events, actions = [], []
    spent_today = False

    for i in range(ticks):
        at = last + timedelta(hours=TICK_HOURS * (i + 1))
        s["tick"] = s.get("tick", 0) + 1
        expire(s)
        rng = tick_rng(s, s["tick"])   # absolute tick, NOT wall clock
        events += advance_world(s, rng, at, i)
        before_coin = s["holding"]["coin"]
        if s["queue"]:
            a = s["queue"].pop(0)
            actions.append((a, resolve_action(s, rng, a, at)))
        if s["holding"]["coin"] < before_coin:
            spent_today = True

        # day boundary: hoard compounds, spending resets it
        if s["tick"] % (24 // TICK_HOURS) == 0:
            if spent_today:
                s["hoard"] = 0
            elif not s["queue"]:
                # nobody is running the holding — a purse nobody manages earns nothing
                s["hoard"] = 0
            else:
                s["hoard"] = s.get("hoard", 0) + 1
                rate = HOARD_RATES[min(s["hoard"] - 1, len(HOARD_RATES) - 1)]
                gained = int(s["holding"]["coin"] * rate)
                if gained:
                    s["holding"]["coin"] += gained
                    s["ledger"].append({
                        "id": eid(s), "at": at.isoformat(), "t": "interest",
                        "streak": s["hoard"], "rate": rate, "gained": gained,
                        "total": s["holding"]["coin"]})
                    events.append(("interest", None, gained))
            spent_today = False
        s["holding"]["hands"] = min(HANDS_CAP, s["holding"]["hands"]
                                    + HANDS_PER_TICK + effect(s, "invest") * 0.5)
        # no orders, no revenue — an unrun holding does not earn
        if s["queue"]:
            s["holding"]["coin"] += COIN_PER_TICK + effect(s, "invest") * 2

    # the world dies of neglect: when every front lands, it settles
    # The world ends the moment ANY neighbour completes its agenda. The operator's
    # rule: "if they won, I lost." Waiting for all three meant a finished world kept
    # running and the epilogue never fired.
    if any(f["done"] for f in s["factions"]) and s.get("status") != "settled":
        s["status"] = "settled"
        s["settled_at"] = now.isoformat()
        s["epilogue"] = [
            (f'{f["name"]} got what it wanted: {f["wants"]}.' if f["done"] else
             f'{f["name"]} never finished. {f["clock"]}/10 when it ended.')
            for f in s["factions"]]
        archive = HERE / "worlds"
        archive.mkdir(exist_ok=True)
        (archive / f'{s["seed"]}.json').write_text(
            json.dumps(s, indent=2), encoding="utf-8")

    s["day"] += int(ticks * TICK_HOURS / 24)
    s["last_tick"] = now.isoformat()
    if s["holding"]["coin"] < 0:
        s["holding"]["coin"] = 0
        s["holding"]["standing"] = "diminished"   # soft loss: never wiped

    return {"ticks": ticks, "elapsed_days": round(elapsed / 86400, 1),
            "events": events, "actions": actions,
            "new_ledger": s["ledger"][start_len:]}

BANDS = [(0, 0, "nothing yet"), (3, 1, "barely started"), (6, 4, "about half way"),
         (8, 7, "close"), (10, 9, "almost there")]


def band(clock):
    """What you can tell from a hill: a range and a word, never a number."""
    for top, lo, word in BANDS:
        if clock <= top:
            return {"lo": lo, "hi": top, "word": word}
    return {"lo": 9, "hi": 10, "word": "almost there"}


def horizon(s):
    """The cliffhanger: the nearest thing about to happen, and roughly when.

    Uses only what the player could know. A watched front gets a real estimate;
    an unwatched one gets a rumour, because you do not have the number.
    """
    out = []
    for f in s["factions"]:
        if f["done"]:
            continue
        posted = s["tick"] <= s.get("watch_until", 0)
        general = s.get("watch_mode") == "general"
        watched = posted and not general and s["watching"] == f["id"]
        mod = f["expansive"] // 3 + (-1 if watched else 2 if s["holding"].get(
            "watch_inverted") else 1) - effect(s, "disrupt", f["id"])
        # expected segments per tick on a d6 against CLOCK_THRESHOLD / DOUBLE_AT
        p1 = sum(1 for d in range(1, CLOCK_DIE + 1)
                 if CLOCK_THRESHOLD <= d + mod < DOUBLE_AT) / CLOCK_DIE
        p2 = sum(1 for d in range(1, CLOCK_DIE + 1)
                 if d + mod >= DOUBLE_AT) / CLOCK_DIE
        rate = p1 + 2 * p2
        if rate <= 0:
            continue
        # FOG: an estimate needs a clock, and you only have a clock for what you
        # can see. Unwatched fronts yield a rumour with no number attached.
        if watched:
            known_clock = f["clock"]
        elif (s.get("watch_mode") == "general"
              and s["tick"] <= s.get("watch_until", 0)):
            b = band(f["clock"])
            known_clock = (b["lo"] + b["hi"]) / 2      # a guess from the middle
        else:
            known_clock = last_known(s, f)
        if known_clock is None:
            out.append({"front": f["name"], "id": f["id"], "watched": False,
                        "ticks": None, "hours": None, "days": None,
                        "clock": None, "rumour": True, "rate": round(rate, 2),
                        "wants": f["wants"]})
            continue
        ticks = (SEGMENTS - known_clock) / rate
        out.append({"front": f["name"], "id": f["id"], "watched": watched,
                    "ticks": round(ticks, 1),
                    "hours": round(ticks * TICK_HOURS),
                    "days": round(ticks * TICK_HOURS / 24, 1),
                    "clock": known_clock, "rumour": not watched,
                    "wants": f["wants"]})
    out.sort(key=lambda x: (x["ticks"] is None, x["ticks"] or 0))
    return out


def last_known(s, f):
    """The most recent clock the player actually learned for this front, if any.

    Set by a successful `scout`. Returns None when they have never had a number.
    """
    import re
    for fact in reversed(s["facts"]):
        if fact["visibility"] == "known" and fact["fact"].startswith(f["name"]):
            m = re.search(r"(\d+)/" + str(SEGMENTS), fact["fact"])
            if m:
                return int(m.group(1))
    return None


# ---------------------------------------------------------------- cli

def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["new", "tick", "ff", "queue", "watch",
                                   "options", "horizon", "improvise", "status", "add"])
    p.add_argument("args", nargs="*")
    p.add_argument("--seed", type=int)
    p.add_argument("--now")
    a = p.parse_args()

    if a.cmd == "new":
        s = new_world(a.seed)
        save(s)
        print(json.dumps({"seed": s["seed"],
                          "factions": [{k: f[k] for k in
                                        ("name", "style", "wants", "aggression",
                                         "expansive", "openness")}
                                       for f in s["factions"]]}, indent=2))
        return

    s = load()

    if a.cmd in ("queue", "add"):
        # `queue` replaces the standing orders. `add` appends to them.
        #
        # Replace used to be the only path, and it silently destroyed a queued
        # mega: the stake is the whole purse AT QUEUE TIME, so rebuilding the
        # list re-prices it from whatever coin is left now. Adding one 20-coin
        # trade alongside a 152-coin mega quietly turned the mega into a 20-coin
        # mega. There was no way to append without paying that.
        s["watch_until"] = s.get("tick", 0) + WATCH_TICKS
        if a.cmd == "queue":
            s["queue"] = []
        room = QUEUE_SLOTS - len(s["queue"])
        for spec in a.args[:max(0, room)]:
            parts = spec.split("|")
            what = parts[0]
            tgt = parts[1] if len(parts) > 1 and parts[1] else s["watching"]
            kind = parts[2] if len(parts) > 2 and parts[2] in ACTIONS else "disrupt"
            cost = s["holding"]["coin"] if kind == "mega" else ACTIONS[kind]["cost"]
            match = next((f for f in s["factions"] if f["id"] == tgt), None)
            if match is None:
                match = next(f for f in s["factions"] if tgt.lower() in f["name"].lower())
            s["queue"].append({
                "what": what, "kind": kind, "cost": cost,
                "target": match["id"], "clock_at_queue": match["clock"],
            })
        save(s)
        print(json.dumps(s["queue"], indent=2))
        return

    if a.cmd == "watch":
        want = a.args[0]
        if want.lower() in ("general", "all", "hill", "broad"):
            s["watch_mode"] = "general"
            s["watch_until"] = s.get("tick", 0) + WATCH_TICKS
            save(s)
            print(json.dumps({"watching": "all three, from the hill",
                              "mode": "general"}))
            return
        s["watch_mode"] = "focused"
        f = next((x for x in s["factions"] if x["id"] == want), None) or             next(x for x in s["factions"] if want.lower() in x["name"].lower())
        s["watching"] = f["id"]
        s["watch_until"] = s.get("tick", 0) + WATCH_TICKS
        save(s)
        print(json.dumps({"watching": f["name"]}))
        return

    if a.cmd == "options":
        coin, hands = s["holding"]["coin"], s["holding"]["hands"]
        out = []
        for k, spec in ACTIONS.items():
            if k == "mega":
                if coin >= MEGA_MIN_COIN:
                    out.append({"kind": k, "cost": coin, "affordable": True,
                                "label": "MEGA PROJECT — spend everything"})
                continue
            out.append({"kind": k, "cost": spec["cost"],
                        "affordable": spec["cost"] <= coin and spec["hands"] <= hands,
                        "label": spec["label"]})
        print(json.dumps({"coin": coin, "hands": round(hands, 1),
                          "slots_left": QUEUE_SLOTS - len(s["queue"]),
                          "options": out}, indent=2))
        return

    if a.cmd == "improvise":
        spec = json.loads(a.args[0])
        f = next((x for x in s["factions"] if x["id"] == spec["target"]), None)
        if f is None:
            f = next(x for x in s["factions"]
                     if spec["target"].lower() in x["name"].lower())
        spec["target"] = f["id"]
        spec["kind"] = "improvise"
        spec["clock_at_queue"] = f["clock"]
        # Improvised orders used to always insert at position 0, which is not
        # written down anywhere and silently reorders everything the player just
        # queued. Append like every other order; pass "next": true to jump.
        if spec.pop("next", False):
            s["queue"].insert(0, spec)
        else:
            s["queue"].append(spec)
        s["watch_until"] = s.get("tick", 0) + WATCH_TICKS
        save(s)
        print(json.dumps({"queued": spec["what"], "target": f["name"],
                          "coin": spec.get("coin", 0),
                          "hands": spec.get("hands", 0)}, indent=2))
        return

    if a.cmd == "horizon":
        print(json.dumps(horizon(s), indent=2))
        return

    if a.cmd == "ff":
        raw = a.args[0] if a.args else "1"
        days = (float(raw[:-1]) / 24.0) if raw.lower().endswith("h") else float(raw)
        now = datetime.fromisoformat(s["last_tick"]) + timedelta(days=days)
        out = tick(s, now)
        save(s)
        print(json.dumps({k: v for k, v in out.items() if k != "events"},
                         indent=2, default=str))
        return

    if a.cmd == "tick":
        now = datetime.fromisoformat(a.now) if a.now else None
        out = tick(s, now)
        save(s)
        print(json.dumps({k: v for k, v in out.items() if k != "events"},
                         indent=2, default=str))
        return

    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()

"""Changing what you cannot see must not change what you are shown.

    python web/test_fog.py

The browser draws the spine's smears, "days dark", "as of last week" and every
neighbour bar from the view the server sends — nothing else. So the whole fog
contract reduces to one property: rewrite the true clock of a front the player
is not watching, rebuild the view, and nothing about that front may differ.

If it ever does, something in the view is carrying truth the player does not
have, and the smear (or anything else drawn from it) could be read like a bar.
"""

import copy
import json
import os
import random
import sys
from pathlib import Path

os.environ["ELSEWHERE_AI"] = "off"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web import fog, game  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  ({detail})" if not cond and detail else ""))
    if not cond:
        FAILS.append(name)


def front_view(state, fid):
    v = fog.view(state)
    f = next(x for x in v["fronts"] if x["id"] == fid)
    hz = [h for h in v["horizon"] if h["id"] == fid]
    rows = [r for r in v["ledger"] if r.get("front") == fid]
    # The horizon ORDER decides which front becomes the headline — the loudest
    # object on the page. Ranking by hidden truth would leak without a number.
    order = [h["id"] for h in v["horizon"]]
    return json.dumps({"front": f, "horizon": hz, "rows": rows, "order": order}, sort_keys=True, default=str)


rng = random.Random(3)
made, checked, leaks = [], 0, 0
for seed in range(30):
    sess = game.new_session(seed=9000 + seed)
    made.append(sess["id"])
    s = sess["state"]
    for _ in range(rng.randint(1, 5)):
        # move the eyes around so there is real memory, then go dark
        pick = rng.choice([f["id"] for f in s["factions"]] + ["general"])
        game.apply_watch(sess, pick)
        game.advance(sess, rng.choice([8, 16, 24]))
        if s.get("status") == "settled":
            break
    if s.get("status") == "settled":
        continue
    view = fog.view(s)
    for f in s["factions"]:
        vf = next(x for x in view["fronts"] if x["id"] == f["id"])
        if vf["sight"] == "exact":
            continue
        before = front_view(s, f["id"])
        for fake in (0, 3, 9):
            s2 = copy.deepcopy(s)
            tgt = next(x for x in s2["factions"] if x["id"] == f["id"])
            if vf["sight"] == "band":
                # a hill read legitimately reports a band; only move truth inside it
                lo, hi = vf["band"]["lo"], vf["band"]["hi"]
                if not lo <= fake <= hi:
                    continue
            tgt["clock"] = fake
            checked += 1
            if front_view(s2, f["id"]) != before:
                leaks += 1
                print(f"  LEAK  seed {9000+seed} {f['id']} sight={vf['sight']} true clock {f['clock']} -> {fake} changed the view")

for sid in made:
    try:
        (game.SESS / f"{sid}.json").unlink()
    except FileNotFoundError:
        pass

check("hidden clocks were actually varied", checked > 40, checked)
check("no fogged front's view changed when its true clock did", leaks == 0, leaks)

# memory is stale-by-construction: it only reads ticks you were watching
sess = game.new_session(seed=4321)
s = sess["state"]
fid = s["watching"]
game.advance(sess, 16)                           # watched for two ticks
seen_seg = fog.view(s)["fronts"][[f["id"] for f in s["factions"]].index(fid)]["memory"]["last_eyes_seg"]
other = next(f["id"] for f in s["factions"] if f["id"] != fid)
game.apply_watch(sess, other)                    # look away
game.advance(sess, 48)
vf = next(x for x in fog.view(s)["fronts"] if x["id"] == fid)
check("a front you looked away from is fogged", vf["sight"] == "fog", vf["sight"])
check("its memory is the reading from when you watched", vf["memory"]["last_eyes_seg"] == seen_seg,
      (vf["memory"]["last_eyes_seg"], seen_seg))
check("it has been dark for about two days", 40 <= vf["memory"]["dark_hours"] <= 56, vf["memory"]["dark_hours"])
check("a fogged front still carries no clock", vf.get("clock") is None, vf.get("clock"))
(game.SESS / f"{sess['id']}.json").unlink()

print()
if FAILS:
    print(f"  ===> FAIL  ({len(FAILS)} failing)")
    sys.exit(1)
print("  ===> PASS")

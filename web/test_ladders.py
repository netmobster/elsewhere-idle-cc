"""The ladder the client prints must agree with the outcome the engine chose.

    python web/test_ladders.py

The client once printed the improvise ladder ("8 lands · 5 partial") beside every
roll. Catalogue orders resolve on 4 / 2, so a correct part-landed trade on a 3 sat
next to a ladder saying 3 was a failure. Nothing was wrong with the engine and
nothing crashed; the ledger just looked like it was lying. This plays many worlds
and checks every resolved row against the table play.html uses.
"""

import os
import random
import sys
from pathlib import Path

os.environ["ELSEWHERE_AI"] = "off"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web import game  # noqa: E402

# Mirror of ladder() in web/static/play.html. If one changes, change both.
LADDER = {
    "catalogue": {"ok": 4, "partial": 2},
    "improvise": {"ok": 8, "partial": 5},
    "mega": {"ok": 9},
}


def expected(row):
    t = row["total"]
    if row["t"] == "mega":
        return "landed" if t >= row.get("threshold", LADDER["mega"]["ok"]) else "not landed"
    # The row must carry its own ladder now, and that ladder must be the one that
    # actually decided the outcome.
    assert "ladder" in row, f"action row has no ladder recorded: {row.get('kind')}"
    table = row["ladder"]
    fixed = LADDER["improvise"] if row.get("kind") == "improvise" else LADDER["catalogue"]
    assert table == fixed, f"{row.get('kind')} recorded {table}, engine rules are {fixed}"
    if t >= table["ok"]:
        return "ok"
    if t >= table["partial"]:
        return "partial"
    return "refund"


rng = random.Random(11)
checked = mismatches = misfires = 0
kinds_seen = set()
made = []
for seed in range(40):
    sess = game.new_session(seed=5000 + seed)
    made.append(sess["id"])
    s = sess["state"]
    for day in range(12):
        if s.get("status") == "settled":
            break
        target = rng.choice(s["factions"])["id"]
        pick = rng.random()
        try:
            if pick < 0.45:
                game.enqueue(sess, {"kind": rng.choice(["trade", "scout", "invest", "fortify", "disrupt"]), "target": target})
            elif pick < 0.9:
                game.enqueue(sess, {"kind": "improvise", "target": target, "what": "a scheme",
                                    "scale": rng.choice(["small", "normal", "big"]),
                                    "aims": rng.sample(["disrupt", "trade", "plunder", "hands"], 2),
                                    "perilous": rng.random() < 0.4})
            elif s["holding"]["coin"] >= 150:
                game.enqueue(sess, {"kind": "mega", "target": target})
        except ValueError:
            pass
        game.advance(sess, 24)
    for row in s["ledger"]:
        if row["t"] not in ("action", "mega") or "total" not in row:
            continue
        kinds_seen.add(row.get("kind") if row["t"] == "action" else "mega")
        out = row.get("outcome")
        if out == "misfire":            # a drift roll, not a ladder result
            misfires += 1
            continue
        want = expected(row)
        got = out if row["t"] == "action" else ("landed" if out in ("landed", "ok", "mythic") or (row["total"] >= 9) else "not landed")
        checked += 1
        if want != got:
            mismatches += 1
            print(f"  MISMATCH  {row.get('kind', row['t']):<9} total {row['total']}  engine={out}  ladder says {want}")

for sid in made:
    try:
        (game.SESS / f"{sid}.json").unlink()
    except FileNotFoundError:
        pass

print(f"  rows checked : {checked}   (misfires skipped: {misfires})")
print(f"  kinds seen   : {', '.join(sorted(k for k in kinds_seen if k))}")
ok = checked > 100 and mismatches == 0 and {"improvise", "trade"} <= kinds_seen
print(f"\n  ===> {'PASS' if ok else 'FAIL'}  ({mismatches} mismatches)")
sys.exit(0 if ok else 1)

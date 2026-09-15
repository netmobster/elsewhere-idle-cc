"""The client describes intent. The server sets every number.

    python web/test_pricing.py

Exits non-zero on failure. No server, no network, no AWS.
"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web import pricing  # noqa: E402

HOLDING = {"coin": 200, "hands": 4.0}
FAILS = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def has_effect(order):
    return bool(order["grants"]) or order["gain"] > 0


print("forged numbers are ignored")
forged = pricing.price({"coin": 0, "hands": 0, "gain": 99999,
                        "grants": [["hands", 50, 0], ["invest", 999, 9999]]}, HOLDING)
check("gain from the request is not paid", forged["gain"] == 0, forged["gain"])
check("coin from the request is not used", forged["coin"] == 40, forged["coin"])
check("grant values from the request are not used",
      all(v <= pricing.CEILING["grant"] for _, v, _ in forged["grants"]), forged["grants"])
check("a scheme cannot be free", forged["coin"] > 0 or forged["hands"] > 0)

print("plunder needs risk")
safe = pricing.price({"scale": "big", "aims": ["plunder"]}, HOLDING)
risky = pricing.price({"scale": "big", "aims": ["plunder"], "perilous": True}, HOLDING)
check("plunder without perilous pays nothing", safe["gain"] == 0, safe["gain"])
check("plunder with perilous pays the table", risky["gain"] == pricing.TABLE["big"]["gain"])

print("nothing lands and does nothing")
check("risk-free plunder still has an effect", has_effect(safe), safe)
check("no aims still has an effect", has_effect(pricing.price({}, HOLDING)))

print("scale and the purse")
allin = pricing.price({"scale": "all_in"}, HOLDING)
check("all_in spends the whole purse", allin["coin"] == 200, allin["coin"])
check("all_in hands capped at 8 and at what exists", allin["hands"] == 4.0, allin["hands"])
broke = pricing.price({"scale": "normal", "aims": ["trade"]}, {"coin": 0, "hands": 3.0})
check("a broke holding can still send people", broke["coin"] == 0 and broke["hands"] == 2.0, broke)
try:
    pricing.price({"scale": "normal"}, {"coin": 0, "hands": 0})
    check("an empty holding is refused", False)
except ValueError:
    check("an empty holding is refused", True)
check("unknown scale falls back to normal", pricing.price({"scale": "LEGENDARY"}, HOLDING)["scale"] == "normal")
check("hands grant is capped", all(v <= pricing.HANDS_GRANT_CAP for k, v, _ in
      pricing.price({"scale": "all_in", "aims": ["hands"]}, HOLDING)["grants"] if k == "hands"))
check("at most two grants", len(pricing.price(
      {"aims": ["disrupt", "fortify", "invest", "trade", "scout"]}, HOLDING)["grants"]) <= pricing.MAX_GRANTS)

print("fuzz: 20,000 hostile intents")
rng = random.Random(7)
junk = [None, "", "all_in", "big", 999, -5, "💀", ["plunder"] * 50, {"a": 1}, True]
worst_gain = worst_grant = worst_ticks = 0
no_effect = 0
for _ in range(20_000):
    intent = {k: rng.choice(junk) for k in ("scale", "aims", "perilous", "beholden", "coin", "gain", "grants")}
    # half the time a junk type, half the time a plausible list, so both paths are hit
    if rng.random() < 0.5:
        intent["aims"] = rng.sample(["disrupt", "fortify", "invest", "trade", "scout", "hands", "plunder", "x"],
                                    rng.randint(0, 8))
    hold = {"coin": rng.randint(0, 5000), "hands": rng.uniform(0.5, 10)}
    o = pricing.price(intent, hold)
    worst_gain = max(worst_gain, o["gain"])
    worst_grant = max([worst_grant] + [v for _, v, _ in o["grants"]])
    worst_ticks = max([worst_ticks] + [t for _, _, t in o["grants"]])
    no_effect += not has_effect(o)
    assert o["coin"] <= hold["coin"] and o["hands"] <= hold["hands"] + 1e-9
check("gain never exceeds the ceiling", worst_gain <= pricing.CEILING["gain"], worst_gain)
check("grant value never exceeds the ceiling", worst_grant <= pricing.CEILING["grant"], worst_grant)
check("duration never exceeds the ceiling", worst_ticks <= pricing.CEILING["ticks"], worst_ticks)
check("no order is priced with zero effect", no_effect == 0, no_effect)

print()
if FAILS:
    print(f"  ===> FAIL  ({len(FAILS)} failing)")
    sys.exit(1)
print("  ===> PASS")

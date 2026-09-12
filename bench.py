"""Elsewhere — fitness bench.

Runs every strategy across several world seeds and reports whether the build
passes the five criteria in NOTES.md. Objective, repeatable, and it does not
care how good the prose is.

    python bench.py            # full bench, 6 seeds
    python bench.py 12         # 12 seeds
"""

import json, sys, statistics
from datetime import datetime
from pathlib import Path

import sim

HERE = Path(__file__).parent
SEEDS = [8812, 4177, 991, 20260908, 555, 77, 31337, 1024, 6060, 42, 2718, 1618]
STRATS = ("attentive", "hoarder", "erratic", "absentee")


def reckon(S):
    L = S["ledger"]
    acts = [e for e in L if e["t"] == "action"]
    raids = [e for e in L if e["t"] == "raid"]
    clocks = [e for e in L if e["t"] == "clock"]
    c = {o: len([a for a in acts if a["outcome"] == o])
         for o in ("ok", "partial", "refund", "misfire")}
    born = datetime.fromisoformat(S["created"])
    died = datetime.fromisoformat(S.get("settled_at", S["last_tick"]))
    life = (died - born).total_seconds() / 86400
    taken = sum(r["taken"] for r in raids)
    vig = round(100 * sum(1 for x in clocks if x["watched"]) / max(1, len(clocks)))
    total = (round(life * 20) + S["holding"]["coin"]
             + c["ok"] * 30 + c["partial"] * 12 - c["misfire"] * 20 - c["refund"] * 5
             - taken + vig)
    return {"score": total, "life": life, "coin": S["holding"]["coin"],
            "counts": c, "acts": len(acts),
            "done": sum(1 for f in S["factions"] if f["done"]),
            "fronts": len(S["factions"]),
            "megas": len([e for e in L if e["t"] == "mega"]),
            "mutations": [e.get("mutation") for e in L
                          if e["t"] == "mega" and e["outcome"] == "mutated"]}


def run(nseeds):
    seeds = SEEDS[:nseeds]
    agg = {s: [] for s in STRATS}
    zero_streaks = []
    for sd in seeds:
        for st in STRATS:
            P = sim.run(st, days=21, seed=sd)
            r = reckon(P["final"])
            r["days_played"] = P["days_played"]
            agg[st].append(r)
            if st == "attentive":
                streak = best = 0
                for d in P["log"]:
                    streak = streak + 1 if d["coin"] == 0 else 0
                    best = max(best, streak)
                zero_streaks.append(best)

    def m(st, k):
        return statistics.mean(x[k] for x in agg[st])

    lost_a_front = sum(1 for x in agg["attentive"] if x["done"] >= 1)
    lose_rate = lost_a_front / max(1, len(seeds))

    wins = sum(1 for i in range(len(seeds))
               if agg["hoarder"][i]["score"] > agg["attentive"][i]["score"])
    hoard_winrate = wins / max(1, len(seeds))

    print(f"{'strategy':<11}{'score':>8}{'life':>8}{'coin':>7}{'acts':>6}"
          f"{'ok%':>6}{'mis%':>6}{'fronts done':>13}")
    for st in STRATS:
        A = agg[st]
        tot = sum(x["acts"] for x in A) or 1
        okp = 100 * sum(x["counts"]["ok"] for x in A) / tot
        mip = 100 * sum(x["counts"]["misfire"] for x in A) / tot
        print(f"{st:<11}{m(st,'score'):>8.0f}{m(st,'life'):>8.1f}{m(st,'coin'):>7.0f}"
              f"{m(st,'acts'):>6.1f}{okp:>6.0f}{mip:>6.0f}"
              f"{m(st,'done'):>7.1f}/{agg[st][0]['fronts']}")

    # ---------------------------------------------------------------- criteria
    att = m("attentive", "score"); err = m("erratic", "score")
    abs_ = m("absentee", "score"); hrd = m("hoarder", "score")
    allacts = [x for st in STRATS for x in agg[st]]
    tot = sum(x["acts"] for x in allacts) or 1
    shares = {o: sum(x["counts"][o] for x in allacts) / tot
              for o in ("ok", "partial", "refund", "misfire")}
    top_share = max(shares.values())

    checks = [
        ("1 differentiation  attentive beats every other strategy by >= 150",
         att >= max(err, abs_, hrd) + 150),
        ("2 attention pays   attentive life >= 1.6x absentee",
         m("attentive", "life") >= 1.6 * m("absentee", "life")),
        ("3 outcome spread   no outcome above 55%",
         top_share <= 0.55),
        ("4 living economy   attentive coin > 0, zero-streak <= 2 days",
         m("attentive", "coin") > 0 and (max(zero_streaks) if zero_streaks else 0) <= 2),
        # Under the any() settle rule a settled world has exactly ONE finished
        # agenda, so the mean is pinned at a ceiling of 1.0 and "mean >= 1"
        # silently demands that the attentive player NEVER holds the world open.
        # That is the opposite of the intent. What this criterion protects is
        # "you usually lose" — so measure that, and leave room for the rare
        # outright win, which is now a real and wanted outcome.
        ("5 still loseable   attentive loses a front in >= 70% of seeds",
         lose_rate >= 0.70),
        ("6 the dare is real  hoarder loses on average, wins 15-45% of seeds",
         m("attentive", "score") > m("hoarder", "score")
         and 0.15 <= hoard_winrate <= 0.45),
    ]
    print()
    for label, passed in checks:
        print(("  PASS  " if passed else "  FAIL  ") + label)
    print(f"\n  outcome shares: " +
          "  ".join(f"{k} {v*100:.0f}%" for k, v in shares.items()))
    print(f"  attentive lost a front in {lost_a_front}/{len(seeds)} seeds "
          f"({lose_rate*100:.0f}%) and held the world open in the rest")
    print(f"  hoarder beat the attentive player in {wins}/{len(seeds)} seeds "
          f"({hoard_winrate*100:.0f}%)")
    print(f"  scores: attentive {att:.0f}  hoarder {hrd:.0f}  erratic {err:.0f}"
          f"  absentee {abs_:.0f}   (lead {att - max(err, abs_, hrd):.0f})")
    ok = all(p for _, p in checks)
    print(f"\n  ===> {'PASS' if ok else 'FAIL'}  ({sum(p for _,p in checks)}/6)")
    return ok


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    sys.exit(0 if run(n) else 1)

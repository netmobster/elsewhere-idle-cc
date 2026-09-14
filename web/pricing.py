"""Price an improvised order on the server. The client never sets a number.

In Claude Code the only thing that ever wrote an improvise spec was the model,
running locally for one player. On the web the spec arrives over HTTP, which
means anyone with devtools can write it. The engine resolves whatever it is
given — send `coin: 0, gain: 99999` and it pays out, which it did: 200 coin
became 141,825 in a single tick.

So the boundary moves. A request may describe *intent*:

    what      what they are attempting, for the ledger
    said      their exact words, verbatim, for the narrator
    target    a faction id
    scale     small | normal | big | all_in
    aims      any of: disrupt fortify invest trade scout hands plunder
    perilous  are people being put at risk
    beholden  is it generous or flattering toward the target

and this module turns intent into an engine order by lookup. Every coin, hand,
payout, grant value and duration comes from the table below. Anything else in
the request is ignored — not validated, ignored — including whatever numbers
the interpret model decided to add.
"""

from __future__ import annotations

SCALES = ("small", "normal", "big", "all_in")

# Anchored to the catalogue: trade 20, scout 30, invest 40, fortify 50,
# disrupt 60. A normal scheme costs about what a normal order does.
TABLE = {
    "small":  {"coin": 20, "hands": 1.0, "grant": 1, "ticks": 6,  "gain": 20},
    "normal": {"coin": 40, "hands": 2.0, "grant": 2, "ticks": 12, "gain": 40},
    "big":    {"coin": 80, "hands": 4.0, "grant": 3, "ticks": 18, "gain": 80},
    # all_in spends the purse and most of the people, not a fixed amount.
    "all_in": {"coin": None, "hands": None, "grant": 4, "ticks": 24, "gain": 120},
}

GRANT_KINDS = ("disrupt", "fortify", "invest", "trade", "scout", "hands")
MAX_GRANTS = 2          # a scheme is about something, not everything
HANDS_GRANT_CAP = 2     # people are the scarcest thing in the game
ALL_IN_HANDS = 8.0      # everyone who can walk, which triggers overreach at 6+

# Absolute ceilings. The table can never produce these; they exist so a future
# edit to the table cannot quietly reopen the hole.
CEILING = {"gain": 150, "grant": 4, "ticks": 24, "coin": 10_000, "hands": 10.0}


def normalise_scale(value) -> str:
    v = str(value or "normal").strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in SCALES else "normal"


def normalise_aims(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple, set, dict)):
        # 999, True, 3.5 — whatever arrived, it is not a list of aims.
        value = []
    seen, out = set(), []
    for a in value or []:
        a = str(a).strip().lower()
        if a in (*GRANT_KINDS, "plunder") and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def price(intent: dict, holding: dict) -> dict:
    """Build the engine's improvise fields from intent. Returns a fresh dict."""
    scale = normalise_scale(intent.get("scale"))
    aims = normalise_aims(intent.get("aims"))
    row = TABLE[scale]
    have_coin = int(holding.get("coin", 0))
    have_hands = float(holding.get("hands", 0))

    # Cost. A broke holding can still send people — the quilts were priced at
    # nothing but hands — so coin scales down to what exists, and hands do not
    # disappear. Every scheme costs somebody.
    coin = have_coin if row["coin"] is None else min(row["coin"], have_coin)
    want_hands = min(ALL_IN_HANDS, have_hands) if row["hands"] is None else row["hands"]
    hands = min(want_hands, have_hands)
    if hands <= 0 and coin <= 0:
        raise ValueError("nothing left to spend on it")

    grants = []
    for kind in [a for a in aims if a in GRANT_KINDS][:MAX_GRANTS]:
        value = row["grant"]
        if kind == "hands":
            value = min(value, HANDS_GRANT_CAP)
        grants.append((kind, min(value, CEILING["grant"]), min(row["ticks"], CEILING["ticks"])))

    perilous = bool(intent.get("perilous"))
    # You cannot take something portable without putting somebody at risk.
    # Without this rule, plunder is a free money button.
    gain = min(row["gain"], CEILING["gain"]) if ("plunder" in aims and perilous) else 0

    # An order that lands must change something. Plunder attempted without risk
    # pays nothing, and if it was the only aim the order used to cost 80 coin and
    # four hands, land, report success, and do nothing at all — silent success,
    # the worst failure mode this game has. So anything with no effect left gets
    # the default one.
    if not grants and gain == 0:
        grants.append(("disrupt", min(row["grant"], CEILING["grant"]), row["ticks"]))

    return {
        "kind": "improvise",
        "scale": scale,
        "aims": aims,
        "coin": int(min(coin, CEILING["coin"])),
        "hands": float(min(hands, CEILING["hands"])),
        "gain": int(gain),
        "grants": grants,
        "perilous": perilous,
        "beholden": bool(intent.get("beholden")),
    }

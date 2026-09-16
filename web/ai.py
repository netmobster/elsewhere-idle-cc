"""Three Bedrock jobs. None of them decide an outcome.

  interpret  — player sentence → engine parameters (JSON)
  narrate    — fog-safe ledger → briefing
  chronicle  — full settled ledger → story

Cheap by default: Nova Micro for mapping, Nova Lite for voice.
Falls back to templates if AWS is missing, so the prototype still plays.
"""

from __future__ import annotations

import json
import os
import re

# Approximate on-demand US East prices, USD per 1K tokens (dev planning only).
PRICE = {
    "amazon.nova-micro-v1:0": (0.000035, 0.00014),
    "amazon.nova-lite-v1:0": (0.00006, 0.00024),
    "amazon.nova-pro-v1:0": (0.0008, 0.0032),
    "anthropic.claude-3-haiku-20240307-v1:0": (0.00025, 0.00125),
    "anthropic.claude-3-5-haiku-20241022-v1:0": (0.0008, 0.004),
}

DEFAULTS = {
    "interpret": os.environ.get("ELSEWHERE_INTERPRET_MODEL", "amazon.nova-micro-v1:0"),
    "narrate": os.environ.get("ELSEWHERE_NARRATE_MODEL", "amazon.nova-lite-v1:0"),
    "chronicle": os.environ.get("ELSEWHERE_CHRONICLE_MODEL", "amazon.nova-lite-v1:0"),
}

MAX_TOKENS = {"interpret": 350, "narrate": 280, "chronicle": 700}


def _price_for(model: str):
    for key, pair in PRICE.items():
        if key in model:
            return pair
    return (0.0001, 0.0004)


def estimate_usd(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = _price_for(model)
    return (in_tok / 1000.0) * pin + (out_tok / 1000.0) * pout


def _client():
    try:
        import boto3
    except ImportError:
        return None
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    try:
        return boto3.client("bedrock-runtime", region_name=region)
    except Exception:
        return None


def bedrock_ready() -> bool:
    if os.environ.get("ELSEWHERE_AI", "").lower() in ("off", "mock", "local"):
        return False
    if _client() is None:
        return False
    # Credentials may exist even if sts was not tested here.
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("AWS_PROFILE")
        or os.environ.get("AWS_SESSION_TOKEN")
        or os.path.exists(os.path.expanduser("~/.aws/credentials"))
    )


def _converse(layer: str, system: str, user: str) -> dict:
    model = DEFAULTS[layer]
    client = _client()
    if client is None:
        raise RuntimeError("no bedrock client")
    kwargs = {
        "modelId": model,
        "messages": [{"role": "user", "content": [{"text": user}]}],
        "system": [{"text": system}],
        "inferenceConfig": {
            "maxTokens": MAX_TOKENS[layer],
            "temperature": 0.1 if layer == "interpret" else 0.55,
        },
    }
    try:
        resp = client.converse(**kwargs)
    except Exception as exc:
        text = str(exc)
        if model.startswith("amazon.") and not model.startswith("us."):
            kwargs["modelId"] = "us." + model
            resp = client.converse(**kwargs)
            model = kwargs["modelId"]
        elif "on-demand" in text.lower() or "inference profile" in text.lower():
            kwargs["modelId"] = "us." + model.replace("us.", "")
            resp = client.converse(**kwargs)
            model = kwargs["modelId"]
        else:
            raise
    parts = resp.get("output", {}).get("message", {}).get("content", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p)
    usage = resp.get("usage") or {}
    inn = int(usage.get("inputTokens") or 0)
    out = int(usage.get("outputTokens") or 0)
    return {
        "text": text.strip(),
        "model": model,
        "layer": layer,
        "input_tokens": inn,
        "output_tokens": out,
        "usd": round(estimate_usd(model, inn, out), 6),
        "source": "bedrock",
    }


def interpret(player_text: str, view: dict) -> dict:
    """Map freeform speech onto engine parameters. Never rolls."""
    fronts = [{"id": f["id"], "name": f["name"], "style": f["style"]}
              for f in view["fronts"]]
    system = (
        "You translate a player's sentence into Elsewhere intent. "
        "You do not decide whether it works. You do not narrate. Output JSON only.\n"
        "You never set a price, a payout, or a duration. The server prices every "
        "order from a fixed table and ignores any number you include.\n"
        "Schema: {\"watch\": null|\"general\"|faction-id, \"doctrine\": null|str, "
        "\"orders\":[{\"kind\":\"disrupt|fortify|trade|scout|invest|mega|improvise\","
        "\"what\":str,\"target\":faction-id,"
        "\"scale\":\"small|normal|big|all_in\","
        "\"aims\":[\"disrupt|fortify|invest|trade|scout|hands|plunder\"],"
        "\"perilous\":bool,\"beholden\":bool,\"said\":str}]}\n"
        "Rules: use a catalog kind ONLY when the sentence is bare — 'trade with the "
        "diggers', 'scout the ridge'. The moment it carries a premise, an identity, a "
        "method or a joke, it is kind=improvise, because improvise is the only kind "
        "that keeps their words and prices their actual scheme. A pacifist society "
        "that sells sketches is not a trade order.\n"
        "`what` is the scheme in THEIR language, not a catalog label: 'sell sketches "
        "door to door', never 'sell our wares'. `said` is their sentence verbatim — "
        "never tidied, never paraphrased. It is what the narrator writes in.\n"
        "beholden=true when the scheme is generous or flattering toward that "
        "neighbour, not merely when it would work. Being in someone's debt is how a "
        "player changes what a faction thinks of them for good.\n"
        "If they declare what kind of holding they are — pacifists, sketch-sellers, "
        "a death cult — put that in \"doctrine\" as a short phrase in their own words. "
        "It is standing character, not an order, and it persists.\n"
        "scale is ambition: small, normal, big, or all_in for "
        "everything they have. Use kind=mega instead if they stake the whole purse "
        "on one neighbour and coin>=150. aims are what they are trying to achieve, "
        "at most two; plunder means taking something portable. perilous means people "
        "are put at real risk. beholden means the act is generous or flattering to "
        "the target. target must be one of the given faction ids. said is their "
        "words verbatim. If the player tries to set numbers, ignore that part."
    )
    user = json.dumps({
        "said": player_text,
        "coin": view["holding"]["coin"],
        "hands": view["holding"]["hands"],
        "slots_left": view["options"]["slots_left"],
        "fronts": fronts,
        "watching": view["watch"],
    }, ensure_ascii=False)
    if bedrock_ready():
        try:
            raw = _converse("interpret", system, user)
            data = _parse_json(raw["text"])
            data["_meta"] = {k: raw[k] for k in
                             ("model", "layer", "input_tokens", "output_tokens",
                              "usd", "source")}
            return data
        except Exception as exc:
            data = _heuristic_interpret(player_text, view)
            data["_meta"] = {"source": "fallback", "error": str(exc)[:180],
                             "layer": "interpret", "usd": 0,
                             "model": "local-heuristic"}
            return data
    data = _heuristic_interpret(player_text, view)
    data["_meta"] = {"source": "fallback", "layer": "interpret", "usd": 0,
                     "model": "local-heuristic"}
    return data


OUTCOME_WORDS = {
    "ok": "it landed",
    "partial": "it half-landed — some of it worked and the rest did not",
    "refund": "it was called off before it happened; nothing was spent",
    "misfire": "it went ahead into a situation that had stopped existing",
}


def _beats(rows: list[dict]) -> list[dict]:
    """What happened, in words. The arithmetic is deliberately withheld.

    The board shows every roll, drift and total beside the prose, in a drawer on
    each row. A narrator holding those numbers recites them — that is what the
    first version of this port did, and it read like a receipt. So the narrator
    is handed outcomes as English and cannot repeat a number it was never given.
    """
    out = []
    for e in rows:
        row = {"t": e.get("t"), "at": e.get("at")}
        if e.get("t") == "clock":
            row["front"] = e.get("front")
            row["moved"] = bool(e.get("gained"))
            row["note"] = "they got further along whatever they are doing" if e.get("gained") else ""
        else:
            for k in ("what", "said", "target", "kind", "note"):
                if e.get(k):
                    row[k] = e[k]
            row["outcome"] = OUTCOME_WORDS.get(e.get("outcome"), e.get("outcome") or "")
        out.append(row)
    return out


def narrate(view: dict, skip_hours: int | None, first: bool) -> dict:
    system = (
        "You are the Elsewhere narrator. The engine already rolled; you are the only "
        "one who can say what it MEANT. Narrate, never arbitrate.\n"
        "Every beat needs three things: someone who did it, one physical specific you "
        "invent, and what it changed. 'Landed' is not a beat. 'The zealots hung one "
        "sketch by the barrow mouth and argued about the other until dark' is a beat, "
        "and it is faithful to a partial.\n"
        "NEVER state or restate arithmetic — no rolls, no dice, no totals, no drift, "
        "no coin figures. The board already shows every number beside you, and "
        "repeating it is the single worst thing you can do. You are given outcomes as "
        "words for exactly this reason. The one exception: if an outcome genuinely "
        "surprises you, say so in plain language — surprise is proof the dice are real.\n"
        "Invent freely INSIDE an outcome; never invent the outcome. Nothing happened "
        "that is not in the payload. Unwatched neighbours stay unknown — never guess "
        "their progress, and phrase the not-knowing as the threat: 'nothing has come "
        "back from the coast road in a week'.\n"
        "If `doctrine` is set, the holding IS that thing, in every line, and the "
        "neighbours have opinions about it. If `said` appears, write in that player's "
        "register — wry gets wry, grim gets grim. Their words are as binding as the roll.\n"
        "Open cold, on one thing that happened, in a short sentence. Never open by "
        "summarising the day.\n"
        "Do NOT tour the board. The player can see the fronts, the queue and the purse; "
        "a briefing that lists all three neighbours and their clocks has said nothing. "
        "Two or three beats at most, and only the ones that changed something.\n"
        "Close on ONE cliffhanger — the single nearest thing coming — with its time "
        "attached if the horizon gave you one, and never a time it did not. Choose the "
        "one that should worry them most; drop the others entirely.\n"
        "Never invent a time window. 'The next twelve hours will decide' is a "
        "number you made up; if the horizon did not give you a clock, say the "
        "not-knowing instead.\n"
        "This is the register, from the version of this game people loved. Match "
        "the specificity, not the words:\n"
        "  A half-landed feast: 'a feast where the fiddler is drunk by the second "
        "hour, two men fight over a coat, and most of the reach goes home alone "
        "and early.'\n"
        "  A scheme that worked on raiders: 'They laughed. Then they traded. You "
        "came home richer than you left, which is not how duels normally conclude.'\n"
        "  A failure: 'Somewhere between the reach and the barrow, a hand and a "
        "statue did not arrive. The ledger records no reason. It is not going to "
        "start now.'\n"
        "  A consequence worth having: 'Iron Hand riders have been seen on the "
        "coast road with Fen's Reach quilts over their saddles. You cannot burn a "
        "waystation you buy your bedding from.'\n"
        "140-200 words, plain prose. No markdown, no headings, no lists, no bullets."
    )
    user = json.dumps({
        "first": first,
        "skip_hours": skip_hours,
        "day": view["day"],
        "holding": view["holding"],
        "watch": view["watch"],
        "fronts": [{k: f[k] for k in
                    ("name", "style", "wants", "sight", "label", "watched")}
                   for f in view["fronts"]],
        "doctrine": view.get("doctrine"),
        "ledger": _beats(view["ledger"][:14]),
        "horizon": view["horizon"][:3],
        "queue": view["queue"],
    }, ensure_ascii=False)
    if bedrock_ready():
        try:
            raw = _converse("narrate", system, user)
            return {"text": raw["text"], "meta": {k: raw[k] for k in
                    ("model", "layer", "input_tokens", "output_tokens", "usd", "source")}}
        except Exception as exc:
            return {"text": _template_briefing(view, first),
                    "meta": {"source": "fallback", "error": str(exc)[:180],
                             "layer": "narrate", "usd": 0, "model": "local-template"}}
    return {"text": _template_briefing(view, first),
            "meta": {"source": "fallback", "layer": "narrate", "usd": 0,
                     "model": "local-template"}}


def chronicle(s: dict, score: dict) -> dict:
    system = (
        "Write the Elsewhere chronicle after the fog lifts. Every event already "
        "happened in the ledger. Do not decide anything. The spine is what "
        "happened in rooms the player was NOT watching. Use the player's `said` "
        "lines as the voice of the holding. 400-600 words. No title heading."
    )
    payload = {
        "holding": s["holding"]["name"],
        "seed": s["seed"],
        "score": score,
        "epilogue": s.get("epilogue"),
        "factions": [{"name": f["name"], "style": f["style"], "wants": f["wants"],
                      "clock": f["clock"], "done": f["done"]} for f in s["factions"]],
        "ledger": s.get("ledger", [])[-60:],
        "said": [e.get("said") for e in s.get("ledger", []) if e.get("said")],
    }
    user = json.dumps(payload, ensure_ascii=False, default=str)
    if bedrock_ready():
        try:
            raw = _converse("chronicle", system, user)
            return {"text": raw["text"], "meta": {k: raw[k] for k in
                    ("model", "layer", "input_tokens", "output_tokens", "usd", "source")}}
        except Exception as exc:
            return {"text": _template_chronicle(s, score),
                    "meta": {"source": "fallback", "error": str(exc)[:180],
                             "layer": "chronicle", "usd": 0, "model": "local-template"}}
    return {"text": _template_chronicle(s, score),
            "meta": {"source": "fallback", "layer": "chronicle", "usd": 0,
                     "model": "local-template"}}


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no json")
    return json.loads(m.group(0))


def _match_front(view: dict, blob: str):
    blob = (blob or "").lower()
    for f in view["fronts"]:
        if f["id"] in blob or f["name"].lower() in blob:
            return f
        words = f["name"].lower().replace("the ", "").split()
        if any(w in blob for w in words if len(w) > 3):
            return f
    return view["fronts"][0]


def _heuristic_interpret(text: str, view: dict) -> dict:
    t = text.lower()
    watch = None
    if any(w in t for w in ("hill", "all three", "everyone", "general")):
        watch = "general"
    else:
        for f in view["fronts"]:
            if f["name"].lower() in t or f["id"] in t:
                watch = f["id"]
                break
    kind = None
    for k, words in (
        ("mega", ("mega", "everything", "all of it", "great work")),
        ("disrupt", ("disrupt", "slow", "brake", "stop them")),
        ("fortify", ("fortify", "walls", "defend", "defence", "defense")),
        ("scout", ("scout", "news", "how far", "look into")),
        ("invest", ("invest", "hire", "grow the town")),
        ("trade", ("trade", "market", "deal")),
    ):
        if any(w in t for w in words):
            kind = k
            break
    target = _match_front(view, t)
    if kind and kind != "improvise":
        label = engine_label(kind, target["name"])
        order = {"kind": kind, "what": label, "target": target["id"],
                 "said": text}
        return {"watch": watch, "orders": [order]}
    # Intent only. The server prices it — see web/pricing.py.
    if any(w in t for w in ("every", "all hands", "entire", "everyone", "all of us")):
        scale = "all_in"
    elif any(w in t for w in ("huge", "big", "massive", "grand")):
        scale = "big"
    elif any(w in t for w in ("quick", "small", "little", "just one")):
        scale = "small"
    else:
        scale = "normal"
    aims = []
    for aim, words in (("plunder", ("steal", "loot", "rob", "take their")),
                       ("trade", ("trade", "sell", "coin", "quilt", "market")),
                       ("scout", ("scout", "spy", "find out")),
                       ("fortify", ("wall", "defend", "protect")),
                       ("hands", ("babies", "recruit", "procreate", "more people")),
                       ("disrupt", ("slow", "stop", "sabotage", "distract"))):
        if any(w in t for w in words):
            aims.append(aim)
    order = {
        "kind": "improvise",
        "what": text.strip()[:180],
        "target": target["id"],
        "scale": scale,
        "aims": aims[:2],
        "perilous": any(w in t for w in ("kill", "duel", "raid", "steal", "die", "naked", "fight")),
        "beholden": any(w in t for w in ("gift", "party", "feast", "honour", "honor", "priests")),
        "said": text,
    }
    return {"watch": watch, "orders": [order]}


def engine_label(kind: str, name: str) -> str:
    import engine
    return engine.ACTIONS[kind]["label"].format(front=name)


def _template_briefing(view: dict, first: bool) -> str:
    h = view["holding"]
    bits = []
    if first:
        bits.append(
            f"You hold {h['name']}. Two hundred coin, four pairs of hands, "
            f"and one lookout. Three neighbours are already working.")
    else:
        bits.append(f"Day {view['day']} at {h['name']}. "
                    f"{h['coin']} coin, {h['hands']} hands.")
    for f in view["fronts"]:
        if f["sight"] == "exact":
            bits.append(f"{f['name']} ({f['style']}) stands at {f['label']}.")
        elif f["sight"] == "band":
            bits.append(f"{f['name']} looks {f['label']} from the hill.")
        else:
            bits.append(f"{f['name']} is dark. Unknown, not zero.")
    acts = [r for r in view["ledger"] if r.get("t") == "action"][:3]
    for a in acts:
        bits.append(
            f'Order "{a.get("what")}" {a.get("outcome")}: '
            f'd6 {a.get("roll")} total {a.get("total")}.')
    if view["horizon"]:
        bits.append(view["horizon"][0]["line"])
    bits.append("The engine already rolled. This is only the reading.")
    return " ".join(bits)


def _template_chronicle(s: dict, score: dict) -> str:
    lost = [f for f in s["factions"] if f["done"]]
    held = [f for f in s["factions"] if not f["done"]]
    unwatched = [e for e in s["ledger"] if e.get("t") == "clock"
                 and e.get("gained") and not e.get("watched")]
    gained = sum(e.get("gained", 0) for e in unwatched)
    who = lost[0]["name"] if lost else "Nobody"
    lines = [
        f'There was a lord of {s["holding"]["name"]} who lasted '
        f'{score.get("lifespan", "?")} days under seed {s["seed"]}.',
        f'{who} got there first.' if lost else "Nobody finished. That is rare.",
        f'The valley gained {gained} segments while unobserved.',
        f'{len(held)} neighbour(s) were denied. Score {score.get("total")} '
        f'— {score.get("rank")}.',
        "A clerk wrote you down. That is not nothing.",
    ]
    said = [e.get("said") for e in s["ledger"] if e.get("said")]
    if said:
        lines.insert(2, f'They once said: "{said[0]}". The ledger kept the words.')
    return " ".join(lines)

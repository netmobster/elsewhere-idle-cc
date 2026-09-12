"""Elsewhere — sidebar renderer. "Iron & Ember".

Design by the operator, built in Claude Design. This file only ever writes
CONTENT into it — never colour, never layout. Every visual value is a token in
the stylesheet below; if something needs to look different, change the token.

THE ONE DISCIPLINE: this renders the player's FILE ON THE WORLD, not the world.

  - `true` facts are NEVER emitted.
  - `known`, `suspected` and `false` render IDENTICALLY. The board must never
    mark which of the player's beliefs is the wrong one.
  - Ledger clock rows appear only for fronts the player had EYES ON.
  - An unknown clock renders as fog, never as zero.

If any of those leak, fog is decoration.

    python render.py
"""

import json, html
from pathlib import Path
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    WORLD_TZ = ZoneInfo("America/Toronto")   # the world keeps one clock, and it is ET
except Exception:
    WORLD_TZ = timezone.utc

HERE = Path(__file__).parent
S = json.loads((HERE / "state.json").read_text(encoding="utf-8"))

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
SEGMENTS = 10

KIND_ROW = {"ok": ("LANDED", "ok"), "partial": ("PARTIAL", "partial"),
            "refund": ("CALLED OFF", "refund"), "misfire": ("MISFIRE", "misfire"),
            "landed": ("GREAT WORK", "ok"), "mythic": ("LEGENDARY", "ok"),
            "mutated": ("IT TWISTED", "misfire")}


def esc(x):
    return html.escape(str(x))


def roman(n):
    return ROMAN[n] if n < len(ROMAN) else str(n + 1)


now = datetime.now(timezone.utc)
last = datetime.fromisoformat(S["last_tick"])
h = S["holding"]
settled = S.get("status") == "settled"
gone = (now - last).total_seconds() / 86400
fresh = len(S["ledger"]) == 0

gone_word = ("you were just here" if gone < 0.5 else
             "a day gone" if gone < 1.5 else f"{gone:.0f} days gone")

# ---- the world's own hour, derived from the tick, not from the reader's window.
# Fast-forward eight hours and the sky moves with it. The picker overrides this
# for looking; it does not change what time it is.
world_now = last.astimezone(WORLD_TZ)
wh = world_now.hour
if 5 <= wh < 10:
    world_mode, watch_name = "morning", "the dawn watch"
elif 10 <= wh < 17:
    world_mode, watch_name = "day", "the day watch"
elif 17 <= wh < 21:
    world_mode, watch_name = "sunset", "the dusk watch"
else:
    world_mode, watch_name = "night", "the night watch"
world_clock = world_now.strftime("%H:%M")


# ---- what changed since the player last looked -----------------------------
# "Last view" is defined by this render, so the snapshot is written back at the
# end of the file. State shows where you are; the delta shows what it cost.
prev = S.get("seen") or {}
d_coin = h["coin"] - prev.get("coin", h["coin"])
d_hands = h["hands"] - prev.get("hands", h["hands"])
d_queue = len(S["queue"]) - prev.get("queue", len(S["queue"]))
d_ticks = S.get("tick", 0) - prev.get("tick", S.get("tick", 0))
first_look = not prev


def chip(v, fmt="{:+.0f}"):
    """A delta chip, or nothing at all when nothing moved."""
    if first_look or not v:
        return ""
    cls = "up" if v > 0 else "down"
    return f'<span class="d {cls}">{fmt.format(v)}</span>'


since = ""
if not first_look and d_ticks:
    hrs = d_ticks * 8
    since = (f'since you last looked, {hrs} hours ago'
             if hrs < 48 else f'since you last looked, {hrs // 24} days ago')


posted = S["tick"] <= S.get("watch_until", 0)
general = posted and S.get("watch_mode") == "general"


def watching(f):
    """Focused watch only. General watch sees everyone roughly and nobody exactly."""
    return posted and not general and S["watching"] == f["id"]


# ---------------------------------------------------------------- horizon
def horizon_lines():
    """The cliffhanger — only ever from what the player could actually know."""
    try:
        import engine
        rows = engine.horizon(S)
    except Exception:
        return None, None
    if not rows:
        return None, None
    sighted = [r for r in rows if r.get("hours") is not None]
    blind = [r for r in rows if r.get("hours") is None]

    if sighted:
        top = sighted[0]
        d = top["days"]
        when = ("less than a day" if d < 1 else "about a day" if d < 1.6
                else f"about {d:.0f} days")
        # `wants` is always an infinitive ("to raise a second wall"), so it can
        # only ever follow a verb that takes one. Never a preposition.
        line = f'{top["front"]} is {when} away. They want {top["wants"]}.'
        more = (f'At the pace you have watched, the last '
                f'{SEGMENTS - top["clock"]} segments fall in about {d:.1f} days.')
    else:
        line = "Nothing has reached you from anywhere."
        more = ("You have no eyes and no numbers. Whatever is happening out "
                "there is happening without a witness.")

    bits = [f'{r["front"]} is rumour only.' for r in blind]
    bits += [f'{r["front"]} was {r["clock"]}/10 when you last had a number.'
             for r in sighted[1:]]
    if bits:
        more += " " + " ".join(bits)
    return line, more


hz_line, hz_more = horizon_lines()
HORIZON = ""
if hz_line:
    HORIZON = f"""
  <section class="horizon">
    <span class="label hot">WHAT IS COMING</span>
    <p class="line">{esc(hz_line)}</p>
    <p class="more">{esc(hz_more)}</p>
  </section>"""

# ---------------------------------------- neighbours (internal data key: front)
fronts = []
for f in S["factions"]:
    seen = watching(f)
    if seen:
        segs = "".join(
            f'<i class="on{" last" if i == f["clock"] - 1 else ""}"></i>'
            if i < f["clock"] else "<i></i>" for i in range(SEGMENTS))
        segwrap, segn = f'<div class="segs">{segs}</div>', f'{f["clock"]}/10'
    elif general:
        # From the hill: a band, not a number. Segments inside the band glow dim.
        import engine as _E
        b = _E.band(f["clock"])
        segs = "".join(
            f'<i class="band"></i>' if b["lo"] <= i + 1 <= b["hi"] else "<i></i>"
            for i in range(SEGMENTS))
        segwrap = f'<div class="segs rough">{segs}</div>'
        segn = b["word"]
    else:
        segwrap = '<div class="segs unknown">' + "<i></i>" * SEGMENTS + "</div>"
        segn = "?/10"

    fronts.append(f"""
      <details class="front {'seen' if seen else ('rough' if general else 'unseen')}">
        <summary>
          <div class="frow"><span class="fname">{esc(f['name']).upper()}</span><span class="fstyle">{esc(f['style'])}</span><span class="eyes">{'EYES ON' if seen else ('FROM THE HILL' if general else 'NO EYES')}</span></div>
          <div class="clock">{segwrap}<span class="segn num{" word" if general and not seen else ""}">{segn}</span></div>
        </summary>
        <div class="fbody">
          <p><em>WANTS</em>{esc(f['wants'])}</p>
          <p><em>LAST SEEN</em>{esc(f['doing'])}</p>
          <div class="fstats"><span><b>{f['aggression']}</b>aggression</span><span><b>{f['expansive']}</b>expansive</span><span><b>{f['openness']}</b>openness</span></div>
          {'<p class="warn">This one is finished. What it wanted is now true.</p>' if f['done'] else ''}
        </div>
      </details>""")

# ---------------------------------------------------------------- beliefs
beliefs = [b for b in S["facts"] if b["visibility"] in ("known", "suspected", "false")]
belief_rows = "".join(
    f'<li><span class="v{" suspected" if b["visibility"] == "suspected" else ""}"></span>'
    f'<span>{esc(b["fact"])}</span>'
    + (f'<span class="note">{esc(b["note"])}</span>' if b.get("note") else "")
    + "</li>" for b in beliefs)
if not belief_rows:
    belief_rows = ('<li><span class="v suspected"></span>'
                   '<span>Nothing has reached you yet.</span></li>')

# ---------------------------------------------------------------- in force
# Effects outlive the order that bought them. A brake bought yesterday is still
# holding today, and the board has to say so or the spend feels wasted.
def pack(title, rows):
    """Modal payload: a title plus term/definition pairs."""
    return title + "~~" + "~~".join(f"{k}||{v}" for k, v in rows)


def nowrow(title, right, rows, cold=False):
    """A NOW row. `rows` is a list of (term, definition) shown in its modal."""
    body = "~~".join(f"{k}||{v}" for k, v in rows)
    cls = "cold live" if cold else "live"
    return (f'<li class="{cls}" tabindex="0" role="button" '
            f'data-n="{esc(title)}~~{body}">'
            f'<span class="ef">{title}</span>'
            f'<span class="efleft num">{right}</span></li>')



EFFECT_NAME = {"disrupt": "Slowing", "fortify": "Defences up", "invest": "Investment"}
tick_now = S.get("tick", 0)
inforce = []
for e in sorted(S.get("effects", []), key=lambda x: x["until"]):
    left = e["until"] - tick_now
    if left <= 0:
        continue
    ends = (last + timedelta(hours=8 * left)).astimezone(WORLD_TZ)
    who = ""
    if e.get("front"):
        fr = next((x for x in S["factions"] if x["id"] == e["front"]), None)
        who = fr["name"] if fr else e["front"]
    days = left * 8 / 24
    left_word = (f"{left * 8} hours left" if days < 1.5
                 else f"{days:.1f} days left")
    title = EFFECT_NAME.get(e["kind"], e["kind"].title()) + (f" \u00b7 {esc(who)}" if who else "")
    inforce.append(nowrow(title, left_word, [
        ("Strength", str(e["value"])),
        ("Runs out", f'{ends.strftime("%H:%M on %d %b")}, the world\'s time'),
        ("Already paid for", "You bought this earlier and it is still working. "
                             "Nothing more to spend on it."),
    ]))

watched_name = next((f["name"] for f in S["factions"] if watching(f)), None)
nxt = S["queue"][0] if S["queue"] else None
nxt_at = (last + timedelta(hours=8)).astimezone(WORLD_TZ).strftime("%H:%M")

now_rows = []
if general:
    now_rows.append(nowrow(
        "Watching from the hill", "all three, roughly", [
            ("What it buys", "A rough band on every neighbour — barely started, "
                             "about half way, close, almost there. Never a number."),
            ("What it costs", "No brake on anyone, and no protection. Every "
                              "neighbour can rob you and none of them work slower."),
            ("How long", "Three days past your last order, same as any watch."),
            ("To change it", "Say “watch <name>” to focus on one again."),
        ]))
elif watched_name:
    now_rows.append(nowrow(
        f"Eyes on {esc(watched_name)}", "lookout posted", [
            ("What it buys", "You see their real bar, they work one slower, and "
                             "they will not rob you."),
            ("What it costs", "The other two go dark. Their bars are unknown, "
                              "not zero."),
            ("How long", "Three days past your last order. Then the lookout goes "
                         "home and everybody goes dark."),
            ("To move it", "Say \u201cwatch someone else\u201d in the terminal."),
        ]))
else:
    now_rows.append(nowrow(
        "No eyes anywhere", "the lookout went home", [
            ("What happened", "You went three days without an order, so nobody is "
                              "watching anybody."),
            ("What it costs", "Every neighbour is unknown, every one of them works "
                              "faster, and any of them can rob you."),
            ("To fix it", "Give any order. It re-posts the watch."),
        ], cold=True))

if nxt:
    now_rows.append(nowrow(
        f'Next order \u2014 {esc(nxt["what"])}', f"fires {nxt_at}", [
            ("When", f"{nxt_at}, the next time the world moves."),
            ("Not guaranteed", "It resolves against the world as it is then, not "
                               "as it is now. If things moved, it can land "
                               "part-done, be called off, or go wrong entirely."),
        ]))
else:
    now_rows.append(nowrow(
        "Nothing queued", "the town has no instructions", [
            ("What this costs", "A town with no orders earns nothing, and unspent "
                                "coin stops compounding."),
            ("And", "Your lookout is on a three-day clock from your last order. "
                    "Silence ends with everyone dark."),
        ], cold=True))
INFORCE = f"""
  <section>
    <div class="qhead"><span class="label hot">NOW</span><span class="hint">what is true at this hour</span></div>
    <ul class="inforce">{''.join(now_rows)}{''.join(inforce)}</ul>
  </section>"""

# ---------------------------------------------------------------- queue
qrows = []
for i in range(5):
    # Orders fire one per tick, eight hours apart, starting from the next tick.
    fires = (last + timedelta(hours=8 * (i + 1))).astimezone(WORLD_TZ)
    when_label = fires.strftime("%H:%M")
    day_off = (fires.date() - world_now.date()).days
    if day_off == 1:
        when_label += " tomorrow"
    elif day_off > 1:
        when_label += f" in {day_off} days"
    if i < len(S["queue"]):
        q = S["queue"][i]
        cost = "ALL" if q.get("kind") == "mega" else str(q.get("cost", ""))
        try:
            import engine as _E
            ticks = _E.ACTIONS.get(q.get("kind", ""), {}).get("ticks", 0)
        except Exception:
            ticks = 0
        holds = (f' &middot; holds {ticks * 8 // 24} days' if ticks >= 3 else "")
        kind = q.get("kind", "")
        detail = (f'{esc(q["what"])}|{kind}|{cost}|{when_label}|'
                  f'{ticks * 8 // 24 if ticks else 0}')
        qrows.append(f'<li class="live" tabindex="0" role="button" data-q="{detail}">'
                     f'<span class="slot">{roman(i)}</span>'
                     f'<span class="what">{esc(q["what"])}{holds}</span>'
                     f'<span class="fires num">{when_label}</span>'
                     f'<span class="cost num">{cost}</span></li>')
    else:
        qrows.append(f'<li class="empty"><span class="slot">{roman(i)}</span>'
                     f'<span class="what">empty. The world moves anyway.</span>'
                     f'<span class="fires num">{when_label}</span>'
                     f'<span class="cost"></span></li>')

# ---------------------------------------------------------------- ledger
rows = []
for e in reversed(S["ledger"][-80:]):
    when = e["at"][5:16].replace("T", " ")
    t = e["t"]
    if t == "clock":
        # FOG: a clock row belongs to the player only if they had eyes on it.
        if not e["gained"] or not e["watched"]:
            continue
        mods = " ".join(f'{k} {v}' if v > 0 else f'{k} −{abs(v)}'
                        for k, v in e["mods"])
        det = pack(esc(e["front"].replace("-", " ").title()) + " made progress", [
            ("What they were doing", "Working toward what they want. Every neighbour "
                                     "rolls once every eight hours."),
            ("What it needed", f'{e["threshold"]} or better, after their modifiers.'),
            ("What they rolled", f'd6 {e["roll"]}, '
                                 + ", ".join(f"{k} {v:+d}" for k, v in e["mods"])
                                 + f' = {e["total"]}'),
            ("What happened", f'{e["gained"]} segment(s) gained. Now at {e["seg"]}.'),
        ])
        rows.append(
            f'<div class="row clock live" tabindex="0" role="button" data-n="{det}">'
            f'<div class="l1"><span class="kind">CLOCK</span>'
            f'<span class="what">{esc(e["front"].replace("-", " ").title())}</span>'
            f'<span class="when">{when}</span></div><div class="l2">'
            f'<span>d6 {e["roll"]} + {mods} = {e["total"]} vs {e["threshold"]}</span>'
            f'<span class="delta">+{e["gained"]} → {e["seg"]}</span></div></div>')
    elif t == "raid":
        det = pack(esc(e["front"].replace("-", " ").title()) + " robbed you", [
            ("Why it happened", "You had no eyes on them. An unwatched neighbour with "
                                "a temper helps itself, and a fatter purse means a "
                                "bigger theft."),
            ("What it needed", f'{e["threshold"]} or better.'),
            ("What they rolled", f'd6 {e["roll"]}, aggression +{e["mods"][0][1]} '
                                 f'= {e["total"]}'),
            ("What it cost you", f'{e["taken"]} coin, gone.'),
        ])
        rows.append(
            f'<div class="row raid live" tabindex="0" role="button" data-n="{det}">'
            f'<div class="l1"><span class="kind">RAID</span>'
            f'<span class="what">{esc(e["front"].replace("-", " ").title())}</span>'
            f'<span class="when">{when}</span></div><div class="l2">'
            f'<span>d6 {e["roll"]} + aggression {e["mods"][0][1]} = {e["total"]} vs {e["threshold"]}</span>'
            f'<span class="delta">−{e["taken"]}</span></div></div>')
    elif t == "interest":
        det = pack("Your strongbox grew", [
            ("Why", f'Day {e["streak"]} in a row without spending. Untouched coin '
                    "compounds: 10%, then 15%, then 25%, then 40% a day."),
            ("This day", f'{int(e["rate"] * 100)}% &mdash; {e["gained"]} coin.'),
            ("The catch", "Spending anything resets the streak to zero, and a fat "
                          "purse attracts bigger raids."),
        ])
        rows.append(
            f'<div class="row ok live" tabindex="0" role="button" data-n="{det}">'
            f'<div class="l1"><span class="kind">UNSPENT</span>'
            f'<span class="what">Day {e["streak"]} of touching nothing</span>'
            f'<span class="when">{when}</span></div><div class="l2">'
            f'<span>{int(e["rate"] * 100)}% on the strongbox</span>'
            f'<span class="delta">+{e["gained"]}</span></div></div>')
    elif t == "mega":
        label, cls = KIND_ROW.get(e["outcome"], ("GREAT WORK", "ok"))
        tale = e.get("mutation") or "it landed"
        rows.append(
            f'<div class="row {cls}"><div class="l1"><span class="kind">{label}</span>'
            f'<span class="what">{esc(e["what"])} — {esc(tale)}</span>'
            f'<span class="when">{when}</span></div><div class="l2">'
            f'<span>2d6 {e["roll"]} + stake {e["mods"][0][1]} = {e["total"]} vs {e["threshold"]}</span>'
            f'<span class="delta">−{e["spent"]}</span></div></div>')
    elif t == "action":
        label, cls = KIND_ROW.get(e["outcome"], (e["outcome"].upper(), ""))
        moved = f'+{e["refund"]} back' if e["refund"] else f'−{e["cost"]}'
        gain = f' · +{e["gain"]} earned' if e.get("gain") else ""
        MEANT = {
            "ok": "It landed in full. The effect applies at full strength.",
            "partial": "The world had shifted, so it only half worked &mdash; half the "
                       "effect, half your money back.",
            "refund": "Conditions had changed too much for it to be worth doing. "
                      "Called off, money returned.",
            "misfire": "It went ahead into a situation that no longer existed. The "
                       "money is gone and nothing was achieved.",
        }
        det = pack(esc(e["what"]), [
            ("What you ordered", esc(e["what"]) + f' &mdash; {e["cost"]} coin.'),
            ("What had changed", (f'The target moved {e["drift"]} segment(s) between '
                                  "you queueing this and it coming up.")
                                 if e["drift"] else
                                 "Nothing. The world was as you left it."),
            ("What it rolled", f'd6 {e["roll"]}, drift &minus;{e["drift"]} = {e["total"]}. '
                               "4 or more lands, 2 to 3 part-lands, below that is "
                               "called off."),
            ("What happened", MEANT.get(e["outcome"], "")),
            ("Net", (f'{e["refund"]} coin returned.' if e["refund"]
                     else f'{e["cost"]} coin spent.')
                    + (f' Earned {e["gain"]}.' if e.get("gain") else "")),
        ])
        rows.append(
            f'<div class="row {cls} live" tabindex="0" role="button" data-n="{det}">'
            f'<div class="l1"><span class="kind">{label}</span>'
            f'<span class="what">{esc(e["what"])}</span>'
            f'<span class="when">{when}</span></div><div class="l2">'
            f'<span>d6 {e["roll"]} · drift −{e["drift"]} = {e["total"]}{gain}</span>'
            f'<span class="delta">{moved}</span></div></div>')

ledger = "".join(rows) or ('<div class="row"><div class="l1"><span class="kind">'
                           '—</span><span class="what">Nothing has happened '
                           'yet.</span></div></div>')

# ---------------------------------------------------------------- guide
GUIDE = f"""
  <details class="guide" {'open' if fresh else ''}>
    <summary><span class="label hot">READ ME FIRST</span><span class="ghint">{'start here' if fresh else 'reference'}</span></summary>
    <div class="gbody">
      <div class="gtabs">
        <button class="gtab on" data-g="g-how">What is this</button>
        <button class="gtab" data-g="g-money">Money &amp; people</button>
        <button class="gtab" data-g="g-orders">Your orders</button>
        <button class="gtab" data-g="g-mega">The big gamble</button>
        <button class="gtab" data-g="g-chaos">Ask for anything</button>
        <button class="gtab" data-g="g-first">First turn</button>
      </div>
      <div class="gview on" id="g-how">
        <p class="glead">You run one small town. Three neighbours each want something, and each is slowly getting it. <b>They keep working whether you are here or not &mdash; in real time, while you sleep.</b></p>
        <p>Each has a bar of ten segments. When one fills, they get what they wanted and the world changes for good. You cannot stop all three. A good run loses two.</p>
        <p><b>You have one set of eyes.</b> Watch a neighbour and you see exactly how far along they are, they work slower, and they will not rob you. The other two go dark &mdash; and a fogged bar means <b>you do not know</b>, not zero.</p>
        <p><b>Your eyes go home if you stop giving orders.</b> Three days after your last instruction the lookout quits and everyone goes dark.</p>
        <p class="gnote">A turn takes two minutes, once a day. Give orders, leave, come back and find out what happened without you.</p>
      </div>
      <div class="gview" id="g-money">
        <dl class="gterms">
          <dt>Coin &mdash; what you spend</dt><dd>Start with 200. The town earns about 10 every eight hours, <b>but only while orders are waiting</b>. A town nobody is running earns nothing. Neighbours with a temper steal it, and the fatter the purse the more they take.</dd>
          <dt>Coin you do not spend grows</dt><dd>Untouched a whole day it grows 10%. Two days 15%, three 25%, four or more 40% a day, compounding. Spend anything and the streak resets. <b>Saving is a real strategy, and it makes you a target.</b></dd>
          <dt>Hands &mdash; the people</dt><dd>Your workers. Returns slowly, stops at ten. Some orders need hands as well as coin, so you can be rich and unable to act.</dd>
          <dt>Time</dt><dd>The world moves every eight hours, three times a day. Each time, neighbours make progress and <b>one</b> of your orders happens.</dd>
        </dl>
      </div>
      <div class="gview" id="g-orders">
        <p class="glead">Five standing orders. Three happen per day, in the order you wrote them.</p>
        <dl class="gterms">
          <dt>Slow them down &mdash; 60</dt><dd>Sets a neighbour back hard for four days. Your only real brake.</dd>
          <dt>Trade &mdash; 20</dt><dd>Returns roughly 50 from a friendly neighbour. Pays for itself and keeps the town earning.</dd>
          <dt>Dig for news &mdash; 30</dt><dd>Tells you exactly how far along a dark neighbour is, <b>and how long you have</b>, without spending your watch.</dd>
          <dt>Build defences &mdash; 50</dt><dd>Much harder to rob, for four days.</dd>
          <dt>Invest &mdash; 40</dt><dd>More coin and more people every eight hours, for five days.</dd>
        </dl>
        <p class="gwarn"><b>The catch, and it is the whole game:</b> an order happens <b>when it comes up</b>, not when you wrote it. If the world moved in between it can come back part-done, be called off with your money back, or go wrong entirely &mdash; done to a situation that stopped existing.</p>
      </div>
      <div class="gview" id="g-mega">
        <p class="glead">Once you have real money you can bet all of it on one enormous undertaking.</p>
        <p>It costs <b>your entire purse and every worker</b>, needs at least 150 coin, and then two dice decide.</p>
        <p><b>The more you stake the better it goes.</b> A small bet needs a great roll and barely dents anyone. A huge one is nearly certain, erases a neighbour's whole bar, and can go <b>legendary</b> &mdash; everyone set back, half your money returned.</p>
        <p class="gwarn"><b>And when it does not land it does not simply fail. It happens sideways.</b> Your wall works so well nothing can reach you, including trade. The money inverts. A neighbour splits in two and now there are four. Something wakes up. A stranger pays you three times what you spent, then asks for it back.</p>
        <p>Staking more does not avoid the twist. It buys <b>a better class of twist</b>.</p>
        <p class="gnote">It wins about two games in five. It is supposed to be a gamble. Take it when you are losing anyway.</p>
      </div>
      <div class="gview" id="g-chaos">
        <p class="glead">The five orders are a shortcut, not the rules. <b>You can ask
        for anything you can describe, and it becomes a real order with real costs and
        a real roll.</b></p>
        <p>Type it in plain words. Whatever you ask for gets turned into a price in
        coin and hands, a modifier drawn from the world as it actually is, and a roll
        against the same ladder every other order faces. <b>Nobody decides whether it
        worked &mdash; not you, and not the narrator.</b> The dice do, and the result
        goes in the ledger with its arithmetic showing.</p>
        <p class="gwarn"><b>It can fail. It usually costs something even when it
        fails.</b> That is what makes it worth doing.</p>

        <p class="glead" style="font-size:15px;margin-top:18px">Things people have
        actually tried</p>
        <dl class="gterms">
          <dt>Send every worker to convert a neighbour to your religion</dt>
          <dd>Pitch a god of community and common interest to a people obsessed with
          walls. <em>Real attempt: their openness of 6 gave +3, committing every hand
          gave &minus;1 for overreach, the die came up 2. Four against five. The
          mission turned back and half the labour was gone.</em></dd>
          <dt>Marry into one of them</dt>
          <dd>Cheap, permanent, and it makes you family to people who were going to
          rob you.</dd>
          <dt>Start a rumour that the barrow is cursed</dt>
          <dd>Costs almost nothing. Works better on the superstitious than the
          mercenary, and the world knows which is which.</dd>
          <dt>Pay the raiders to rob somebody else</dt>
          <dd>Turn your worst neighbour into a weapon aimed at your worst problem.</dd>
          <dt>Throw a festival and invite all three</dt>
          <dd>Expensive, and everyone arrives armed. But nobody digs during a feast.</dd>
          <dt>Fake your own collapse</dt>
          <dd>Let them think the reach is finished. They stop watching you. So does
          everyone else.</dd>
          <dt>Sell the walls for coin</dt>
          <dd>You will need that money. You will also need those walls.</dd>
          <dt>Send one child with one message</dt>
          <dd>Small, strange, and cheap. Small strange things are often the ones the
          world has no defence against.</dd>
        </dl>
        <p class="gnote">This is the part a menu cannot do. The board tells you what is
        true, the numbers stay honest, and then you get to try something nobody wrote
        down. That is the whole reason this game lives in a terminal instead of a
        browser tab.</p>
      </div>

      <div class="gview" id="g-first">
        <p class="glead">First world? Do this and stop thinking about it.</p>
        <ol class="gsteps">
          <li><b>Watch whoever has the highest expansive</b> &mdash; that is how fast they work.</li>
          <li><b>Trade</b> with whoever has the highest openness. Costs 20, returns about 50.</li>
          <li><b>Slow down</b> the one you are watching.</li>
          <li><b>Dig for news</b> on a dark one, so you are not blind on two.</li>
          <li><b>Leave.</b> Come back tomorrow.</li>
        </ol>
        <p class="gnote">The three numbers on each neighbour: <b>aggression</b> how likely to rob you &middot; <b>expansive</b> how fast they work &middot; <b>openness</b> how much they will trade. All out of six.</p>
      </div>
    </div>
  </details>"""

# ---- the reckoning: derived, never invented ---------------------------------
_L = S["ledger"]
_acts = [e for e in _L if e["t"] == "action"]
_raids = [e for e in _L if e["t"] == "raid"]
_clocks = [e for e in _L if e["t"] == "clock"]
_megas = [e for e in _L if e["t"] == "mega"]
_imps = [e for e in _acts if e.get("kind") == "improvise"]
_c = {o: len([a for a in _acts if a["outcome"] == o])
      for o in ("ok", "partial", "refund", "misfire")}
_life = (datetime.fromisoformat(S.get("settled_at", S["last_tick"]))
         - datetime.fromisoformat(S["created"])).total_seconds() / 86400
_taken = sum(r["taken"] for r in _raids)
_stolen = sum(a.get("gain", 0) for a in _acts)
_vig = round(100 * sum(1 for x in _clocks if x["watched"]) / max(1, len(_clocks)))
_fell = sum(1 for f in S["factions"] if f["done"])
_held = len(S["factions"]) - _fell

_endurance = round(_life * 20)
_defiance = _held * 120
_execution = _c["ok"] * 30 + _c["partial"] * 12 - _c["misfire"] * 20 - _c["refund"] * 5
TOTAL = (_endurance + _defiance + _execution + _stolen
         + S["holding"]["coin"] - _taken + _vig)

if TOTAL >= 900:
    GLYPH_K, RANK, RANKLINE = "sun", "REMEMBERED", "They still use your name for the road."
elif TOTAL >= 550:
    GLYPH_K, RANK, RANKLINE = "sun", "RECORDED", "A clerk wrote you down. That is not nothing."
elif TOTAL >= 300:
    GLYPH_K, RANK, RANKLINE = "moon", "TOLERATED", "The reach outlived you and did not comment."
elif TOTAL >= 120:
    GLYPH_K, RANK, RANKLINE = "moon", "MISLAID", "Two generations, and the ledger is the only proof."
else:
    GLYPH_K, RANK, RANKLINE = "tomb", "UNMOURNED", "Nobody agrees how long you were even there."

GLYPHS = {
    "sun": '<circle cx="110" cy="110" r="60" class="gdisc"/>' + "".join(
        f'<rect x="107" y="10" width="6" height="20" rx="3" class="gray" '
        f'transform="rotate({a} 110 110)"/>' for a in range(0, 360, 30)),
    "moon": '<path class="gdisc" d="M110 44a66 66 0 1 0 50 110A74 74 0 0 1 110 44Z"/>',
    "tomb": '<path class="gdisc" d="M64 186V98a46 46 0 0 1 92 0v88Z"/>'
            '<rect x="50" y="182" width="120" height="13" rx="4" class="gdisc"/>',
}

_ROWS = [
    ("Endurance", _endurance, f"{_life:.1f} days before it ended"),
    ("Defiance", _defiance, f"{_held} of {len(S['factions'])} never got what they wanted"),
    ("Execution", _execution,
     f'{_c["ok"]} landed &middot; {_c["partial"]} partial &middot; {_c["refund"]} called off &middot; {_c["misfire"]} misfired'),
    ("Plunder", _stolen, f"{_stolen} coin out of other people's markets"),
    ("Stewardship", S["holding"]["coin"], "left in the strongbox"),
    ("Vigilance", _vig, f"{_vig}% of rolls made under your eye"),
    ("Losses", -_taken, f"{_taken} coin lost in {len(_raids)} raid(s)"),
]

_A = []


def _earn(cond, name, why):
    if cond:
        _A.append((name, why))


_earn(_held == len(S["factions"]), "Nobody Got Anything",
      "Not one neighbour finished. That is not supposed to be possible.")
_earn(_fell == len(S["factions"]), "Everyone Got What They Wanted",
      "Every agenda completed. The reach was scenery.")
_earn(_held >= 1 and _fell >= 1, "You Held The Line Somewhere",
      f"{_held} of {len(S['factions'])} denied. The rest took what they came for.")
_earn(len(_imps) >= 1, "Not On The Menu",
      f"{len(_imps)} order(s) nobody designed. You asked for something that did not exist.")
_earn(_stolen >= 100, "The Dying Traveller",
      f"{_stolen} coin taken by people who were not, in fact, dying.")
_earn(_c["misfire"] >= 1, "Fired Into The Void",
      f'{_c["misfire"]} order(s) executed into a situation that had stopped existing.')
_earn(_c["misfire"] == 0 and _acts, "Clean Sheet",
      "Not one order fired into a world that had moved. Suspicious.")
_earn(len(_raids) >= 2, "Soft Target",
      f"Robbed {len(_raids)} times. Being elsewhere is a policy with consequences.")
_earn(len(_megas) >= 1, "The Great Work", "You staked the entire purse on one undertaking.")
_earn(any(m["outcome"] == "mutated" for m in _megas), "Granted Sideways",
      "The wish was granted. Not as asked.")
_earn(any(f["visibility"] == "false" for f in S["facts"]), "Confidently Wrong",
      "You ended holding beliefs that were never true. Nobody corrected you.")
_earn(S["holding"]["coin"] == 0, "Bled Dry", "The strongbox reached zero.")
_earn(not _acts, "Absentee Landlord", "You never gave a single order.")

_M = []
_big = max(_raids, key=lambda r: r["taken"], default=None)
if _big:
    _M.append((_big["at"], f'{_big["front"].replace("-", " ").title()} took {_big["taken"]} coin',
               f'd6 {_big["roll"]} + aggression {_big["mods"][0][1]} = {_big["total"]}'))
_fin = next((x for x in S["facts"] if "got what it wanted" in x["fact"]), None)
if _fin:
    _M.append((_fin["at"], esc(_fin["fact"]), "and everybody found out"))
_best = max((a for a in _acts if a["outcome"] == "ok"),
            key=lambda a: a.get("gain", 0), default=None)
if _best:
    _M.append((_best["at"], esc(_best["what"]) + " landed", f'd6 {_best["roll"]}'))
_worst = min(_acts, key=lambda a: a["total"], default=None)
if _worst:
    _M.append((_worst["at"], esc(_worst["what"]) + " &mdash; " + _worst["outcome"],
               f'd6 {_worst["roll"]}, drift &minus;{_worst["drift"]} = {_worst["total"]}'))
_M.sort()

DATA_PANE = (
    "<table>" + "".join(
        f'<tr><td>{n}</td><td class="d">{d}</td>'
        f'<td class="v{" neg" if v < 0 else ""}">{v:+d}</td></tr>'
        for n, v, d in _ROWS) + "</table>"
    + '<h4>What they wanted</h4><ul class="fates">' + "".join(
        f'<li class="{"lost" if f["done"] else "held"}"><b>{esc(f["name"])}</b>'
        f'<p>{esc(f["wants"]).capitalize()}. '
        + ("<b>They got there.</b>" if f["done"]
           else f'Never finished &mdash; {f["clock"]}/10 at the end.')
        + "</p></li>" for f in S["factions"]) + "</ul>"
    + '<h4>What you earned</h4>' + ("".join(
        f'<div class="ach"><b>{esc(n)}</b><p>{w}</p></div>' for n, w in _A)
        or '<p class="muted">No achievements. That is itself remarkable.</p>')
    + '<h4>Moments</h4><ol class="moments">' + "".join(
        f'<li><span class="when">{m[0][5:16].replace("T", " ")}</span>'
        f'<span class="what">{m[1]}</span><code>{m[2]}</code></li>' for m in _M)
    + "</ol>")

BADGE = (
    f'<div class="badge" data-score="{TOTAL}" data-max="1000" '
    f'data-days="{_life:.0f}" data-held="{_held}" data-fronts="{len(S["factions"])}">'
    '<div class="halo" aria-hidden="true"></div>'
    '<div class="ring"><svg viewBox="0 0 300 300" aria-hidden="true">'
    '<defs><filter id="bblur" x="-80%" y="-80%" width="260%" height="260%">'
    '<feGaussianBlur stdDeviation="14"/></filter></defs>'
    '<g id="b-sparks"></g>'
    '<circle class="bticks" cx="150" cy="150" r="146"/>'
    '<circle class="bticks2" cx="150" cy="150" r="138"/>'
    '<circle class="btrack" cx="150" cy="150" r="118" pathLength="1000"/>'
    '<circle class="bfill" id="b-fill" cx="150" cy="150" r="118" pathLength="1000" '
    'transform="rotate(-90 150 150)"/>'
    '<circle class="bgaps" cx="150" cy="150" r="118" pathLength="1000" '
    'transform="rotate(-90.55 150 150)"/>'
    '<circle class="bdisc" cx="150" cy="150" r="98"/>'
    '<circle class="bsunglow" id="b-sunglow" r="26" filter="url(#bblur)"/>'
    '<circle class="bsun" id="b-sun" r="9"/>'
    '<circle class="btip" id="b-tip" r="4"/>'
    '</svg><div class="bscore"><b id="b-num">0</b><span>OF 1000</span></div></div>'
    f'<div class="kicker reveal">{RANK}</div>'
    '<div class="bmeta reveal d2">'
    f'<span>{esc(h["name"]).upper()}</span><span>&middot;</span>'
    f'<span>{_life:.0f} DAYS</span><span>&middot;</span>'
    f'<span class="held" id="b-held" aria-label="{_held} of {len(S["factions"])} held"></span>'
    '</div>'
    f'<p class="bline reveal d3">{RANKLINE}</p></div>')

# ---- the chronicle: written by the narrator, from the ledger ---------------
story_md = ""
story_path = HERE / "story.md"
if story_path.exists():
    story_md = story_path.read_text(encoding="utf-8")


def md_to_html(md):
    """Just enough markdown for a chronicle. No dependencies."""
    out, para = [], []

    def inline(t):
        """Bold and italic, applied to a WHOLE paragraph.

        Doing this per-line breaks any span that wraps across two source lines:
        the opener finds no partner and emits an unclosed tag. Join first,
        format second.
        """
        while t.count("**") >= 2:
            t = t.replace("**", "<b>", 1).replace("**", "</b>", 1)
        t = t.replace("**", "")
        while t.count("*") >= 2:
            t = t.replace("*", "<em>", 1).replace("*", "</em>", 1)
        return t.replace("*", "")

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def cells(line):
        """Split a table row, dropping the empty edges left by the outer pipes."""
        return [c.strip() for c in line.strip().strip("|").split("|")]

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # A table. Every row is an ordinary non-empty line, so without this they
        # all land in `para` and get joined with spaces into one long smear of
        # pipes. Consume the whole block here instead.
        if line.lstrip().startswith("|") and line.count("|") >= 2:
            flush()
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i].rstrip()); i += 1
            body = [r for r in block
                    if not set(r.replace("|", "").strip()) <= set("-: ")]
            head, rest = (body[0], body[1:]) if len(body) > 1 else (None, body)
            h = ['<table class="chtab">']
            if head:
                h.append("<thead><tr>" + "".join(
                    "<th>" + inline(esc(c)) + "</th>" for c in cells(head)) + "</tr></thead>")
            h.append("<tbody>" + "".join(
                "<tr>" + "".join("<td>" + inline(esc(c)) + "</td>" for c in cells(r)) + "</tr>"
                for r in rest) + "</tbody></table>")
            out.append("".join(h))
            continue

        # A blockquote. The chronicle quotes the player's own orders back at them,
        # which is the best thing in the file, so this is not a rare case.
        if line.lstrip().startswith(">"):
            flush()
            block = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                block.append(lines[i].lstrip()[1:].strip()); i += 1
            out.append("<blockquote>" + inline(esc(" ".join(block).strip())) + "</blockquote>")
            continue

        if line.lstrip().startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append(lines[i].lstrip()[2:].strip()); i += 1
            out.append("<ul>" + "".join("<li>" + inline(esc(x)) + "</li>" for x in items) + "</ul>")
            continue

        i += 1
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            out.append("<h3>" + esc(line[3:]) + "</h3>")
        elif line.startswith("# "):
            flush()
            out.append('<h2 class="chtitle">' + esc(line[2:]) + "</h2>")
        elif line.strip() == "---":
            flush()
            out.append('<div class="rule"></div>')
        else:
            para.append(esc(line))
    flush()
    return "\n".join(out)


STORY = md_to_html(story_md) if story_md else ""

_done = sum(1 for f in S["factions"] if f["done"])
_held = len(S["factions"]) - _done
SHARE = ("Elsewhere \u2014 " + h["name"] + ", seed " + str(S["seed"]) + ". "
         + str(S["day"]) + " days. " + str(_held) + "/" + str(len(S["factions"]))
         + " neighbours denied. Score " + str(TOTAL) + " \u2014 " + RANK + ".")

EPI_MODAL = ""
if story_md:
    EPI_MODAL = (
        '<dialog id="epi"><div class="epibody">'
        '<div class="epihead"><span class="label hot">' + esc(h["name"]).upper()
        + '</span><button class="gtab" id="epi-x">Close</button></div>'
        + BADGE
        + '<div class="etabs">'
          '<button class="gtab on" data-e="e-story">The chronicle</button>'
          '<button class="gtab" data-e="e-data">The score line</button></div>'
        + '<div class="eview on" id="e-story"><div class="chron" id="chron">'
        + STORY + '</div></div>'
        + '<div class="eview" id="e-data"><div class="chron">' + DATA_PANE + '</div></div>'
        + '<div class="epifoot">'
          '<button class="gtab" id="copy-story">Copy the chronicle</button>'
          '<button class="gtab" id="copy-share">Copy the score line</button>'
          '<span class="copied" id="copied" hidden>copied</span>'
          '</div></div></dialog>')

CHRON_CALL = ""
if story_md:
    CHRON_CALL = (
        '<section class="epicall"><div class="qhead">'
        '<span class="label hot">THE CHRONICLE</span>'
        '<span class="hint">what was happening where you could not see</span></div>'
        '<button class="chronbtn" id="open-epi">Read the story of '
        + esc(h["name"]) + '</button></section>')

EPILOGUE = ""
if settled:
    EPILOGUE = ('<section class="settled"><span class="label hot">THE WORLD SETTLED</span>'
                + "".join(f"<p>{esc(l)}</p>" for l in S.get("epilogue", []))
                + f'<p class="gnote">Archived as <span class="num">worlds/{S["seed"]}.json</span>. Roll a new one when you want.</p></section>')

DOC = f"""<title>Elsewhere - Idle World in CC</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Spectral:ital,wght@0,300;0,400;0,600;1,300&display=swap">
<style>
:root{{
  --bg:#0d0c0b; --panel:#171513; --ink:#e9e1d3; --mid:#a9a297; --soft:#6f6a62; --edge:#2a2622;
  --ember:#ff4d00; --ember2:#ff6a1a; --glow:rgba(255,77,0,.42); --good:#e9e1d3;
  --serif:Spectral,Georgia,serif; --caps:Cinzel,serif;
}}
[data-mode="morning"]{{--bg:#1e2226;--panel:#262b30;--ink:#dfe3e6;--mid:#b4bcc4;--soft:#8a949c;--edge:#343a40;--ember:#9fb4c4;--ember2:#b9cad6;--glow:rgba(159,180,196,.28);--good:#dfe3e6}}
[data-mode="day"]{{--bg:#181716;--panel:#211f1d;--ink:#e9e1d3;--mid:#b8b0a2;--soft:#8a847a;--edge:#2e2b27;--ember:#c9b99a;--ember2:#dccfb4;--glow:rgba(201,185,154,.22);--good:#e9e1d3}}
[data-mode="sunset"]{{--bg:#1a0e07;--panel:#24140a;--ink:#f0e2d0;--mid:#c8a888;--soft:#b08060;--edge:#3a2212;--ember:#ff8a30;--ember2:#ffa75a;--glow:rgba(255,138,48,.42);--good:#f0e2d0}}
*{{box-sizing:border-box}}
/* Scrollbars: thin and in-palette. The default chrome is a grey slab that
   breaks the whole lacquer-and-ember look. */
*{{scrollbar-width:thin;scrollbar-color:var(--edge) transparent}}
*::-webkit-scrollbar{{width:9px;height:9px}}
*::-webkit-scrollbar-track{{background:transparent}}
*::-webkit-scrollbar-thumb{{background:var(--edge);border-radius:99px;
  border:2px solid transparent;background-clip:content-box}}
*::-webkit-scrollbar-thumb:hover{{background:var(--ember);
  border:2px solid transparent;background-clip:content-box}}
*::-webkit-scrollbar-corner{{background:transparent}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);font-size:14px;line-height:1.5;transition:background .8s ease,color .8s ease}}
.num{{font-variant-numeric:tabular-nums}}
.backdrop{{position:fixed;inset:0;pointer-events:none;z-index:0}}
.backdrop .ground{{position:absolute;inset:0;background:radial-gradient(ellipse 85% 42% at 50% 108%,var(--glow),transparent 70%);animation:breathe 9s ease-in-out infinite;transition:background .8s}}
[data-mode="morning"] .backdrop .ground{{background:radial-gradient(ellipse 85% 42% at 50% -8%,var(--glow),transparent 70%)}}
.backdrop svg{{position:absolute;inset:0;width:100%;height:100%;opacity:.32}}
.sun,.sunglow{{transform-box:fill-box;transform-origin:center;transition:cx .8s,cy .8s,r .8s}}
.sun{{fill:var(--ember2)}} .sunglow{{fill:var(--ember);opacity:.7}}
[data-mode="morning"] .sun{{cx:140px;cy:300px;r:66px;animation:sunpulse 6s ease-in-out infinite}}
[data-mode="morning"] .sunglow{{cx:140px;cy:300px;r:150px;animation:sunpulse 6s ease-in-out infinite}}
[data-mode="day"] .sun{{cx:400px;cy:110px;r:58px;animation:breathe 12s ease-in-out infinite}}
[data-mode="day"] .sunglow{{cx:400px;cy:110px;r:300px;opacity:.55;animation:breathe 12s ease-in-out infinite}}
[data-mode="sunset"] .sun{{cx:660px;cy:560px;r:96px;animation:sunpulse 5s ease-in-out infinite}}
[data-mode="sunset"] .sunglow{{cx:660px;cy:560px;r:230px;animation:sunpulse 5s ease-in-out infinite}}
[data-mode="night"] .sun{{cx:620px;cy:150px;r:48px;fill:var(--ink);animation:breathe 14s ease-in-out infinite}}
[data-mode="night"] .sunglow{{cx:620px;cy:150px;r:110px;animation:breathe 14s ease-in-out infinite}}
.spark{{fill:var(--ember2);animation:rise var(--dur) linear var(--delay) infinite}}
[data-mode="morning"] .spark{{animation-direction:reverse}}
.wall{{fill:var(--bg);opacity:.9}} .wall-edge{{fill:none;stroke:var(--ember);stroke-width:1.2;opacity:.6}}
@keyframes breathe{{0%,100%{{opacity:.7}}50%{{opacity:1}}}}
@keyframes sunpulse{{0%,100%{{opacity:.75;transform:scale(1)}}50%{{opacity:1;transform:scale(1.07)}}}}
@keyframes rise{{0%{{transform:translate(0,0);opacity:0}}15%{{opacity:1}}100%{{transform:translate(18px,-260px);opacity:0}}}}
@keyframes ember{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
@keyframes fogseg{{0%,100%{{opacity:.3}}50%{{opacity:.8}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}}}
.wrap{{position:relative;z-index:1;max-width:820px;margin:0 auto;padding:24px 22px 72px;display:flex;flex-direction:column;gap:30px}}
section{{display:flex;flex-direction:column;gap:12px}}
.label{{font-family:var(--caps);font-size:9px;letter-spacing:.38em;color:var(--soft)}}
.label.hot{{color:var(--ember)}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}
.logo{{display:inline-flex;align-items:center;gap:10px;font-size:16px}}
.logo svg{{width:34px;height:34px}}
.logo .ring-dim{{fill:none;stroke:var(--edge);stroke-width:5;stroke-dasharray:14.8 2.8}}
.logo .ring-lit{{fill:none;stroke:var(--ember);stroke-width:5;stroke-dasharray:105 71;animation:ember 3s ease-in-out infinite}}
.logo .disc{{fill:var(--ink)}} .logo .bite{{fill:var(--bg)}}
.logo .word{{font-family:var(--caps);font-weight:600;letter-spacing:.18em;font-size:17px;line-height:1;display:block}}
.logo .sub{{font-family:var(--caps);font-size:8px;letter-spacing:.42em;color:var(--ember);display:block;margin-top:3px}}
.hours{{display:flex;align-items:center;gap:10px}}
/* Text size. The board is read in a narrow pane at 14px, which is fine for the
   author and not for everybody. One point per click, and it remembers. */
.type{{display:flex;align-items:center;gap:2px;padding:3px;border-radius:999px;
  border:1px solid var(--edge);margin-right:10px}}
.type button{{font-family:var(--caps);font-size:11px;line-height:1;color:var(--soft);
  background:transparent;border:0;cursor:pointer;padding:5px 7px;border-radius:999px;
  transition:color .15s,background .15s}}
.type button:hover{{color:var(--ink);background:var(--edge)}}
#fs-now{{min-width:26px;font-variant-numeric:tabular-nums;letter-spacing:.06em}}
.hours .now{{font-family:var(--caps);font-size:9px;letter-spacing:.3em;color:var(--soft)}}
.hours .picker{{display:flex;gap:8px;padding:6px 8px;border-radius:999px;border:1px solid var(--edge)}}
.hours button{{width:16px;height:16px;border:0;padding:0;cursor:pointer;border-radius:999px;background:transparent;box-shadow:inset 0 0 0 1.5px var(--soft)}}
.hours button[aria-pressed="true"]{{background:var(--ember);box-shadow:inset 0 0 0 1.5px var(--ember)}}
.hours button:focus-visible{{outline:2px solid var(--ember);outline-offset:3px}}
.mast{{display:flex;flex-direction:column;gap:10px}}
h1{{font-family:var(--caps);font-weight:400;font-size:clamp(30px,8.5vw,52px);letter-spacing:.06em;line-height:1;margin:0;text-wrap:balance}}
.meta{{display:flex;gap:6px 14px;flex-wrap:wrap;font-style:italic;font-weight:300;color:var(--soft)}}
.meta .lit{{color:var(--ember)}}
.intown{{margin:0;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}
.watchname{{font-family:var(--caps);font-size:11px;letter-spacing:.2em;color:var(--ember)}}
.wclock{{font-family:var(--caps);font-size:11px;letter-spacing:.14em;color:var(--soft)}}
.override{{font-size:11.5px;font-style:italic;font-weight:300;color:var(--soft)}}
.horizon{{border-left:2px solid var(--ember);padding:6px 0 6px 18px;gap:8px}}
.horizon .line{{margin:0;font-size:clamp(18px,4.6vw,22px);line-height:1.3;font-weight:300;text-wrap:pretty}}
.horizon .more{{margin:0;font-size:13.5px;font-weight:300;color:var(--mid);text-wrap:pretty}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:1px;background:var(--edge);border:1px solid var(--edge)}}
.stats div{{background:var(--panel);padding:14px 14px 12px;display:flex;flex-direction:column;gap:6px}}
.stats b{{font-family:var(--caps);font-weight:400;font-size:24px;line-height:1;letter-spacing:.04em}}
.stats span{{font-family:var(--caps);font-size:8px;letter-spacing:.3em;color:var(--soft)}}
.stats .d{{font-family:var(--caps);font-size:11px;letter-spacing:.06em;margin-left:8px;vertical-align:2px}}
.stats .d.up{{color:var(--ember)}}
.stats .d.down{{color:var(--soft)}}
.neighbours{{display:flex;flex-direction:column;gap:8px}}
details.front{{background:var(--panel);border:1px solid var(--edge)}}
details.front summary{{cursor:pointer;padding:14px 16px;display:flex;flex-direction:column;gap:12px;list-style:none}}
details.front summary::-webkit-details-marker{{display:none}}
.frow{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.fname{{font-family:var(--caps);font-size:14px;letter-spacing:.06em}}
.front.unseen .fname{{color:var(--mid)}}
.fstyle{{font-style:italic;font-weight:300;font-size:13px;color:var(--soft)}}
.eyes{{margin-left:auto;font-family:var(--caps);font-size:8px;letter-spacing:.3em;color:var(--soft)}}
.front.seen .eyes{{color:var(--ember)}}
.clock{{display:flex;align-items:center;gap:10px}}
.segs{{display:flex;gap:5px;flex:1 1 auto;min-width:0}}
.segs i{{flex:1 1 0;height:11px;background:var(--edge)}}
.segs i.on{{background:var(--ember);box-shadow:0 0 10px var(--glow)}}
.segs i.on.last{{animation:ember 1.8s ease-in-out infinite}}
.segs.unknown i{{background:transparent;border:1px solid var(--edge);animation:fogseg 3.4s ease-in-out infinite}}
.segs.rough i{{background:transparent;border:1px solid var(--edge)}}
.segs.rough i.band{{background:var(--ember);opacity:.32;border-color:transparent;animation:fogseg 4s ease-in-out infinite}}
.front.rough .fname{{color:var(--ink)}}
.front.rough .eyes,.front.rough .segn{{color:var(--mid)}}
.segn.word{{min-width:96px;font-size:10px;letter-spacing:.14em}}
.segs.unknown i:nth-child(2n){{animation-duration:3.8s;animation-delay:.6s}}
.segs.unknown i:nth-child(3n){{animation-duration:4.2s;animation-delay:1.2s}}
.segs.unknown i:nth-child(5n){{animation-delay:2s}}
.segn{{flex:0 0 auto;font-family:var(--caps);font-size:12px;color:var(--soft);min-width:40px;text-align:right}}
.front.seen .segn{{color:var(--ember)}}
.fbody{{padding:2px 16px 16px;color:var(--mid);font-size:13.5px;font-weight:300;display:flex;flex-direction:column;gap:6px}}
.fbody p{{margin:0;text-wrap:pretty}}
.fbody em{{font-style:normal;font-family:var(--caps);font-size:8px;letter-spacing:.3em;color:var(--soft);margin-right:10px}}
.fbody .warn{{color:var(--ember)}}
.fstats{{display:flex;gap:20px;margin-top:6px;font-size:12px;color:var(--soft);flex-wrap:wrap}}
.fstats b{{font-family:var(--caps);font-weight:400;font-size:16px;color:var(--ink);margin-right:6px}}
ul.beliefs{{list-style:none;margin:0;padding:0;border:1px solid var(--edge);background:var(--panel);display:flex;flex-direction:column}}
ul.beliefs li{{padding:12px 16px;display:grid;grid-template-columns:10px 1fr;gap:3px 12px;align-items:baseline;font-size:13.5px;border-top:1px solid var(--edge)}}
ul.beliefs li:first-child{{border-top:0}}
ul.beliefs .v{{width:7px;height:7px;transform:rotate(45deg);align-self:center;background:var(--ember)}}
ul.beliefs .v.suspected{{background:transparent;border:1px solid var(--soft)}}
ul.beliefs .note{{grid-column:2;font-size:12px;font-style:italic;font-weight:300;color:var(--soft)}}
.qhead{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.qhead .hint{{font-size:12px;font-style:italic;font-weight:300;color:var(--soft)}}
ol.queue{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}}
ol.queue li{{display:flex;align-items:center;gap:12px;padding:10px 14px;font-size:13.5px;border:1px solid var(--edge);background:var(--panel)}}
ol.queue li.empty{{background:transparent;border-style:dashed;color:var(--soft);font-style:italic;font-weight:300}}
ol.queue .slot{{flex:0 0 auto;width:26px;height:26px;display:inline-flex;align-items:center;justify-content:center;font-family:var(--caps);font-size:11px;background:var(--ember);color:var(--bg)}}
ol.queue li.empty .slot{{background:transparent;box-shadow:inset 0 0 0 1px var(--edge);color:var(--soft)}}
ol.queue .what{{flex:1 1 auto;min-width:0;text-wrap:pretty}}
ol.queue .fires{{flex:0 0 auto;font-family:var(--caps);font-size:10px;letter-spacing:.1em;color:var(--ember);opacity:.85}}
ol.queue li.empty .fires{{color:var(--soft);opacity:.5}}
ul.inforce{{list-style:none;margin:0;padding:0;border:1px solid var(--edge);background:var(--panel);display:flex;flex-direction:column}}
ul.inforce li{{padding:11px 16px;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;border-top:1px solid var(--edge);font-size:13.5px}}
ul.inforce li:first-child{{border-top:0}}
ul.inforce li.live{{cursor:pointer}}
ul.inforce li.live:hover .ef{{color:var(--ember)}}
ul.inforce li.live:focus-visible{{outline:2px solid var(--ember);outline-offset:-2px}}
ul.inforce li.cold .ef{{color:var(--soft);font-style:italic;font-weight:300}}
ul.inforce li.cold .ef{{color:var(--soft);font-style:italic;font-weight:300}}
ul.inforce li.cold .efleft{{color:var(--soft)}}
ol.queue li.live{{cursor:pointer}}
ol.queue li.live:hover{{border-color:var(--ember)}}
ol.queue li.live:focus-visible{{outline:2px solid var(--ember);outline-offset:2px}}
dialog{{background:var(--panel);color:var(--ink);border:1px solid var(--ember);max-width:460px;padding:20px;font-family:var(--serif)}}
dialog::backdrop{{background:rgba(0,0,0,.72)}}
dialog h3{{font-family:var(--caps);font-size:13px;letter-spacing:.14em;margin:0 0 14px;color:var(--ember)}}
dialog#epi{{max-width:680px;width:94vw;padding:0;max-height:92vh;border-radius:2px}}
.epibody{{display:flex;flex-direction:column;max-height:92vh}}
.epihead{{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 20px;border-bottom:1px solid var(--edge)}}
.epifoot{{flex:0 0 auto;display:flex;align-items:center;gap:10px;padding:12px 20px;box-shadow:0 -14px 18px -14px rgba(0,0,0,.9);border-top:1px solid var(--edge);flex-wrap:wrap}}
.copied{{font-size:11.5px;font-style:italic;color:var(--ember)}}
.chron{{flex:1 1 auto;min-height:0;overflow-y:auto;padding:20px 24px 26px;font-size:15px;line-height:1.75;color:var(--mid);overscroll-behavior:contain}}
.chron .chtitle{{font-family:var(--caps);font-weight:400;font-size:22px;letter-spacing:.05em;color:var(--ink);margin:0 0 6px}}
.chron h3{{font-family:var(--caps);font-size:11px;letter-spacing:.26em;color:var(--ember);margin:26px 0 10px}}
.chron p{{margin:0 0 13px;text-wrap:pretty}}
/* The chronicle quotes the player's own orders back at them. That is the best
   thing in the file, so it gets treated as a pull quote and not as a nested note. */
.chron blockquote{{margin:0 0 15px;padding:10px 0 10px 18px;border-left:2px solid var(--ember);
  color:var(--ink);font-style:italic;font-size:15px;line-height:1.5}}
.chron ul{{margin:0 0 13px;padding-left:20px}}
.chron li{{margin:0 0 5px}}
/* A chronicle table is written by the narrator, so its width is unknown. Let it
   scroll inside itself rather than pushing the modal sideways. */
.chron .chtab{{display:block;overflow-x:auto;width:100%;border-collapse:collapse;
  font-family:var(--caps);font-size:11.5px;letter-spacing:.04em;margin:0 0 15px;white-space:nowrap}}
.chron .chtab th{{text-align:left;color:var(--soft);font-weight:400;letter-spacing:.2em;
  text-transform:uppercase;font-size:9px;padding:0 16px 7px 0;border-bottom:1px solid var(--edge)}}
.chron .chtab td{{padding:7px 16px 7px 0;color:var(--mid);border-bottom:1px solid var(--edge)}}
.chron .chtab tr td:first-child{{color:var(--ink)}}
.chron b{{color:var(--ink)}}
.chron em{{color:var(--soft)}}
.chron .rule{{height:1px;background:linear-gradient(to right,transparent,var(--edge),transparent);margin:22px 0}}
.etabs{{flex:0 0 auto;display:flex;gap:6px;padding:0 20px 12px;border-bottom:1px solid var(--edge)}}
.eview{{display:none}}
.eview.on{{display:flex;flex-direction:column;flex:1 1 auto;min-height:0}}
.badge{{flex:0 0 auto;position:relative;width:100%;display:flex;flex-direction:column;
  align-items:center;gap:14px;text-align:center;isolation:isolate;padding:16px 20px 10px}}
.badge .halo{{position:absolute;left:50%;top:140px;width:440px;height:440px;
  transform:translate(-50%,-50%);border-radius:50%;
  background:radial-gradient(circle,var(--glow),transparent 62%);opacity:.7;
  animation:breathe 7s ease-in-out infinite;pointer-events:none;z-index:-1}}
[data-mode="day"] .badge .halo{{width:560px;height:560px;opacity:.55;animation-duration:12s}}
[data-mode="morning"] .badge .halo,[data-mode="sunset"] .badge .halo{{animation:sunpulse 5s ease-in-out infinite}}
.badge .ring{{width:min(264px,62vw);aspect-ratio:1;position:relative}}
.badge .ring svg{{width:100%;height:100%;overflow:visible}}
.bticks{{fill:none;stroke:var(--edge);stroke-width:1;stroke-dasharray:1.2 8.8;
  transform-box:fill-box;transform-origin:center;animation:turn 140s linear infinite}}
.bticks2{{fill:none;stroke:var(--soft);stroke-width:1;stroke-dasharray:6 194;opacity:.6;
  transform-box:fill-box;transform-origin:center;animation:turn 90s linear infinite reverse}}
.btrack{{fill:none;stroke:var(--edge);stroke-width:12}}
.bfill{{fill:none;stroke:var(--ember);stroke-width:12;stroke-dasharray:0 1000;
  transition:stroke-dasharray 2.4s cubic-bezier(.2,.7,.2,1);filter:drop-shadow(0 0 8px var(--glow))}}
.bgaps{{fill:none;stroke:var(--panel);stroke-width:16;stroke-dasharray:3 97}}
.btip{{fill:var(--ember2);animation:ember 1.6s ease-in-out infinite;filter:drop-shadow(0 0 6px var(--ember))}}
.bdisc{{fill:var(--panel);stroke:var(--edge);stroke-width:1}}
.bsun{{fill:var(--ember2);transform-box:fill-box;transform-origin:center;transition:cx 1.2s,cy 1.2s}}
.bsunglow{{fill:var(--ember);opacity:.8;transition:cx 1.2s,cy 1.2s}}
[data-mode="night"] .bsun{{fill:var(--ink)}}
[data-mode="morning"] .bsun,[data-mode="sunset"] .bsun{{animation:sunpulse 4s ease-in-out infinite}}
.bspark{{fill:var(--ember2);animation:rise var(--dur) linear var(--delay) infinite}}
[data-mode="morning"] .bspark{{animation-direction:reverse}}
.bscore{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px}}
.bscore b{{font-family:var(--caps);font-weight:400;font-size:clamp(56px,15vw,76px);line-height:1;
  letter-spacing:.02em;font-variant-numeric:tabular-nums;color:var(--ink);text-shadow:0 0 30px var(--glow)}}
.bscore span{{font-family:var(--caps);font-size:8.5px;letter-spacing:.4em;color:var(--ember)}}
.kicker{{font-family:var(--caps);font-size:11px;letter-spacing:.42em;color:var(--ember)}}
.bmeta{{display:flex;gap:6px 12px;justify-content:center;flex-wrap:wrap;font-family:var(--caps);
  font-size:8.5px;letter-spacing:.28em;color:var(--soft)}}
.held{{display:flex;gap:4px;align-items:center}}
.held i{{width:9px;height:9px;transform:rotate(45deg);border:1px solid var(--soft)}}
.held i.on{{background:var(--ember);border-color:var(--ember)}}
.bline{{margin:0;font-style:italic;font-size:18px;line-height:1.35;color:var(--ink);
  text-wrap:pretty;max-width:34ch}}
.reveal{{opacity:0;transform:translateY(8px);animation:reveal 1s ease .4s forwards}}
.reveal.d2{{animation-delay:1.2s}} .reveal.d3{{animation-delay:1.9s}}
@keyframes turn{{to{{transform:rotate(360deg)}}}}
@keyframes reveal{{to{{opacity:1;transform:none}}}}
.chron h4{{font-family:var(--caps);font-size:10px;letter-spacing:.28em;color:var(--ember);margin:26px 0 10px;font-weight:400}}
.chron table{{width:100%;border-collapse:collapse;font-size:12.5px}}
.chron td{{padding:10px 0;border-bottom:1px solid var(--edge);vertical-align:top}}
.chron td.d{{color:var(--soft);font-size:11.5px;padding-left:12px;font-style:italic}}
.chron td.v{{text-align:right;font-family:var(--caps);color:var(--ember);white-space:nowrap;font-variant-numeric:tabular-nums}}
.chron td.v.neg{{color:var(--mid)}}
ul.fates{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:14px}}
ul.fates li{{border-left:2px solid var(--edge);padding-left:14px}}
ul.fates li.lost{{border-left-color:var(--ember)}}
ul.fates b{{font-family:var(--caps);font-size:13px;letter-spacing:.05em;color:var(--ink)}}
ul.fates p{{margin:4px 0 0}}
.ach{{padding:11px 0;border-bottom:1px solid var(--edge)}}
.ach b{{font-family:var(--caps);font-size:10.5px;letter-spacing:.12em;color:var(--ink)}}
.ach p{{margin:4px 0 0;font-size:12.5px}}
ol.moments{{list-style:none;margin:0;padding:0}}
ol.moments li{{padding:12px 0;border-bottom:1px solid var(--edge);display:flex;flex-direction:column;gap:3px}}
.when{{font-size:10px;letter-spacing:.14em;color:var(--soft);text-transform:uppercase}}
ol.moments .what{{font-size:16px}}
ol.moments code{{font-size:11px;color:var(--soft)}}
.epicall{{gap:10px}}
.chronbtn{{background:none;border:1px solid var(--ember);color:var(--ember);padding:14px 18px;cursor:pointer;font-family:var(--caps);font-size:11px;letter-spacing:.22em;text-align:left;width:100%}}
.chronbtn:hover{{background:var(--ember);color:var(--bg)}}
.chronbtn:focus-visible{{outline:2px solid var(--ember);outline-offset:3px}}
.ef{{flex:1 1 auto;min-width:0}}
.efval{{font-family:var(--caps);font-size:11px;color:var(--ember)}}
.efval::before{{content:"strength ";font-family:var(--serif);font-style:italic;font-weight:300;color:var(--soft);letter-spacing:0}}
.efleft{{font-family:var(--caps);font-size:10px;letter-spacing:.1em;color:var(--ember)}}
.efends{{font-size:11.5px;font-style:italic;font-weight:300;color:var(--soft)}}
ol.queue .cost{{flex:0 0 auto;font-family:var(--caps);font-size:11px;color:var(--soft);min-width:34px;text-align:right}}
.ledger{{border:1px solid var(--edge);background:var(--panel);display:flex;flex-direction:column;max-height:440px;overflow-y:auto}}
.ledger .row{{padding:11px 16px;display:flex;flex-direction:column;gap:3px;border-top:1px solid var(--edge)}}
.ledger .row:first-child{{border-top:0}}
.ledger .l1{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}
.ledger .kind{{font-family:var(--caps);font-size:8px;letter-spacing:.3em;min-width:76px;color:var(--soft)}}
.ledger .what{{flex:1 1 auto;min-width:0;font-size:13.5px}}
.ledger .when{{font-size:11.5px;font-weight:300;color:var(--soft)}}
.ledger .l2{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;font-weight:300;color:var(--mid)}}
.ledger .delta{{margin-left:auto;font-family:var(--caps);font-size:11px;color:var(--mid)}}
.ledger .row.misfire .kind,.ledger .row.raid .kind,.ledger .row.misfire .delta,.ledger .row.raid .delta{{color:var(--ember)}}
.ledger .row.ok .kind{{color:var(--good)}}
.ledger .row.live{{cursor:pointer}}
.ledger .row.live:hover{{background:var(--bg)}}
.ledger .row.live:focus-visible{{outline:2px solid var(--ember);outline-offset:-2px}}
.guide{{border:1px solid var(--ember);background:var(--panel)}}
.guide summary{{cursor:pointer;padding:13px 16px;display:flex;align-items:center;gap:12px;list-style:none}}
.guide summary::-webkit-details-marker{{display:none}}
.ghint{{margin-left:auto;font-family:var(--caps);font-size:8px;letter-spacing:.3em;color:var(--soft)}}
.gbody{{border-top:1px solid var(--edge);padding:16px}}
.gtabs{{display:flex;gap:6px;margin-bottom:15px;flex-wrap:wrap}}
.gtab{{background:none;border:1px solid var(--edge);color:var(--soft);padding:5px 11px;cursor:pointer;font-family:var(--caps);font-size:9px;letter-spacing:.18em}}
.gtab.on{{background:var(--ember);color:var(--bg);border-color:var(--ember)}}
.gtab:focus-visible{{outline:2px solid var(--ember);outline-offset:2px}}
.gview{{display:none}} .gview.on{{display:block}}
.glead{{font-size:18px;line-height:1.5;color:var(--ink);margin:0 0 11px;font-weight:300;text-wrap:pretty}}
.gview p{{margin:0 0 10px;color:var(--mid);font-size:13.5px;font-weight:300;line-height:1.7;text-wrap:pretty}}
.gnote{{border-left:2px solid var(--ember);padding-left:12px;color:var(--soft)!important;font-style:italic}}
.gwarn{{border-left:2px solid var(--ember);padding-left:12px}}
ol.gsteps{{margin:0 0 10px;padding-left:18px;color:var(--mid);font-size:13.5px;font-weight:300;line-height:1.85}}
dl.gterms{{margin:0;font-size:13.5px;font-weight:300}}
dl.gterms dt{{font-family:var(--caps);font-size:10px;letter-spacing:.16em;color:var(--ink);margin-top:13px}}
dl.gterms dd{{margin:4px 0 0;color:var(--mid);line-height:1.65}}
.settled{{border:1px solid var(--ember);background:var(--panel);padding:16px}}
.settled p{{margin:0 0 6px;font-size:16px;font-weight:300}}
.foot{{margin:0;font-size:12px;font-weight:300;font-style:italic;line-height:1.65;color:var(--soft);text-wrap:pretty;max-width:560px}}
</style>

<div class="backdrop" aria-hidden="true">
  <div class="ground"></div>
  <svg viewBox="0 0 800 1000" preserveAspectRatio="xMidYMax slice">
    <defs><filter id="sunblur" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="40"/></filter></defs>
    <circle class="sunglow" filter="url(#sunblur)"/>
    <circle class="sun"/>
    <g id="sparks"></g>
    <path class="wall" d="M0 1000 L0 900 L40 900 L40 880 L70 880 L70 900 L120 900 L120 870 L150 870 L150 900 L230 900 L230 885 L260 885 L260 900 L340 900 L340 860 L370 860 L370 900 L470 900 L470 880 L500 880 L500 900 L580 900 L580 870 L610 870 L610 900 L700 900 L700 885 L730 885 L730 900 L800 900 L800 1000 Z"/>
    <path class="wall-edge" d="M0 1000 L0 900 L40 900 L40 880 L70 880 L70 900 L120 900 L120 870 L150 870 L150 900 L230 900 L230 885 L260 885 L260 900 L340 900 L340 860 L370 860 L370 900 L470 900 L470 880 L500 880 L500 900 L580 900 L580 870 L610 870 L610 900 L700 900 L700 885 L730 885 L730 900 L800 900"/>
  </svg>
</div>

<div class="wrap">
  <header style="display:flex;flex-direction:column;gap:22px">
    <div class="top">
      <span class="logo">
        <svg viewBox="0 0 64 64" aria-hidden="true">
          <circle class="ring-dim" cx="32" cy="32" r="28" transform="rotate(-90 32 32)"/>
          <circle class="ring-lit" cx="32" cy="32" r="28" transform="rotate(-90 32 32)"/>
          <circle class="disc" cx="32" cy="32" r="16"/>
          <circle class="bite" cx="41" cy="26" r="16"/>
        </svg>
        <span><span class="word">ELSEWHERE</span><span class="sub">IDLE CC</span></span>
      </span>
      <div class="type" role="group" aria-label="Text size">
        <button id="fs-down" title="Smaller text" aria-label="Smaller text">&minus;</button>
        <button id="fs-now" title="Reset text size" aria-label="Reset text size">14</button>
        <button id="fs-up" title="Larger text" aria-label="Larger text">+</button>
      </div>
      <div class="hours">
        <span class="now" id="hour-word">{world_mode.upper()}</span>
        <div class="picker" role="group" aria-label="Hour of the world">
          <button data-mode="morning" title="morning" aria-label="morning"></button>
          <button data-mode="day" title="day" aria-label="day"></button>
          <button data-mode="sunset" title="sunset" aria-label="sunset"></button>
          <button data-mode="night" title="night" aria-label="night"></button>
        </div>
      </div>
    </div>
    <div class="mast">
      <span class="label hot">DAY {S['day']} &middot; {gone_word.upper()}</span>
      <h1>{esc(h['name']).upper()}</h1>
      <p class="intown"><span class="watchname">It is {watch_name} in {esc(h['name'])}</span><span class="wclock num">{world_clock}</span><span class="override" id="override" hidden>you are looking at another hour</span></p>
      <div class="meta num"><span>Seed {S['seed']}</span><span class="lit">{'the world has settled' if settled else 'the holding ' + esc(h['standing'])}</span><span>last word {last.strftime('%d %b, %H:%MZ')}</span></div>
    </div>
  </header>
{EPILOGUE}
{EPI_MODAL}
{GUIDE}
{HORIZON}
  <section>
    {CHRON_CALL}
  </section>

  <section>
    <div class="qhead"><span class="label">THE HOLDING</span><span class="hint">{since}</span></div>
    <div class="stats num">
      <div><b>{h['coin']}{chip(d_coin)}</b><span>COIN</span></div>
      <div><b>{h['hands']:.0f}{chip(d_hands)}</b><span>HANDS</span></div>
      <div><b>{len(S['queue'])}/5{chip(d_queue)}</b><span>QUEUE</span></div>
      <div><b>{esc(h['standing']).upper()}</b><span>STANDING</span></div>
    </div>
  </section>

  <section>
    <span class="label">NEIGHBOURS</span>
    <div class="neighbours">{''.join(fronts)}</div>
  </section>

  <section>
    <span class="label">WHAT YOU KNOW</span>
    <ul class="beliefs">{belief_rows}</ul>
  </section>

{INFORCE}
  <section>
    <div class="qhead"><span class="label">QUEUE</span><span class="hint">one fires every eight hours &middot; times are the world's</span></div>
    <ol class="queue">{''.join(qrows)}</ol>
  </section>

  <dialog id="qd">
    <h3 id="qd-t"></h3>
    <dl class="gterms" id="qd-b"></dl>
    <p class="gnote">The board cannot change an order &mdash; only the world can, and
      only when the order comes up. To alter it, say so in the terminal:
      <em id="qd-say"></em></p>
    <button class="gtab" onclick="document.getElementById('qd').close()">Close</button>
  </dialog>

  <section>
    <span class="label">LEDGER</span>
    <div class="ledger num">{ledger}</div>
  </section>

  <p class="foot">This is your file on the world, not the world. It shows what you know and what you suspect, and it does not mark which of those is wrong. Clocks you had no eyes on are not zero. They are unknown.<br>Every row above was rolled by the engine under seed {S['seed']}. Re-runnable, and not up for negotiation.</p>
</div>

<script>
(function(){{
  var html = document.documentElement;
  // The world's hour comes from the engine, not from the reader's clock.
  var WORLD = '{world_mode}';
  function setMode(m){{
    html.setAttribute('data-mode', m);
    // The badge shares the board's palette through the tokens, but its sun is a
    // position, not a colour. Move it so an overridden hour stays coherent.
    var bs = document.getElementById('b-sun'), bg2 = document.getElementById('b-sunglow');
    if (bs) {{
      var r2 = {{morning:180, day:270, sunset:0, night:60}}[m] * Math.PI/180;
      var bx = 150 + 146*Math.cos(r2), by = 150 + 146*Math.sin(r2);
      [bs, bg2].forEach(function (e) {{ e.setAttribute('cx', bx); e.setAttribute('cy', by); }});
    }}
    var w = document.getElementById('hour-word'); if (w) w.textContent = m.toUpperCase();
    var o = document.getElementById('override'); if (o) o.hidden = (m === WORLD);
    document.querySelectorAll('.hours button').forEach(function(b){{ b.setAttribute('aria-pressed', String(b.dataset.mode===m)); }});
  }}
  document.querySelectorAll('.hours button').forEach(function(b){{ b.addEventListener('click', function(){{ setMode(b.dataset.mode); }}); }});
  setMode(WORLD);

  /* ---- text size ----------------------------------------------------------
     Every size on this board is a hardcoded px value, so raising body
     font-size cascades to nothing. Scaling the root does cascade, and takes
     the rules, gaps and bars with it, which is what "bigger" actually means
     here. One point per click against a 14px base. Unbounded upward; floored
     at 8 only because a zoom factor near zero cannot be clicked back. */
  (function () {{
    var BASE = 14, KEY = 'elsewhere-fs', size = BASE;
    try {{ var v = parseInt(localStorage.getItem(KEY), 10); if (v >= 8) size = v; }} catch (e) {{}}
    var out = document.getElementById('fs-now');
    function apply() {{
      document.documentElement.style.zoom = (size / BASE).toFixed(4);
      if (out) out.textContent = String(size);
      try {{ localStorage.setItem(KEY, String(size)); }} catch (e) {{}}
    }}
    function step(n) {{ size = Math.max(8, size + n); apply(); }}
    var up = document.getElementById('fs-up'), dn = document.getElementById('fs-down');
    if (up) up.addEventListener('click', function () {{ step(1); }});
    if (dn) dn.addEventListener('click', function () {{ step(-1); }});
    if (out) out.addEventListener('click', function () {{ size = BASE; apply(); }});
    document.addEventListener('keydown', function (ev) {{
      if (ev.target && /^(INPUT|TEXTAREA)$/.test(ev.target.tagName)) return;
      if (ev.key === '+' || ev.key === '=') {{ step(1); }}
      else if (ev.key === '-' || ev.key === '_') {{ step(-1); }}
      else return;
      ev.preventDefault();
    }});
    apply();
  }})();

  var g = document.getElementById('sparks'), NS = 'http://www.w3.org/2000/svg';
  function rnd(i,m){{ return ((i*9301+49297)%233280)/233280*m; }}
  for (var i=0;i<26;i++){{
    var c = document.createElementNS(NS,'circle');
    c.setAttribute('class','spark');
    c.setAttribute('cx', rnd(i+11,800)); c.setAttribute('cy', 980+rnd(i,40)); c.setAttribute('r', 0.9+rnd(i+5,1.6));
    c.style.setProperty('--dur', (9+rnd(i,10))+'s'); c.style.setProperty('--delay', (-rnd(i+3,18))+'s');
    g.appendChild(c);
  }}

  var SAY = {{disrupt:'slow them down', fortify:'build defences', trade:'trade',
             scout:'dig for news', invest:'invest', mega:'the big gamble'}};
  var dlg = document.getElementById('qd');
  function openQ(el){{
    var p = el.dataset.q.split('|');
    document.getElementById('qd-t').textContent = p[0];
    document.getElementById('qd-b').innerHTML =
      '<dt>Costs</dt><dd>' + p[2] + ' coin</dd>' +
      '<dt>Fires</dt><dd>' + p[3] + ", the world's time</dd>" +
      (p[4] !== '0' ? '<dt>Then holds for</dt><dd>' + p[4] + ' days</dd>' : '') +
      '<dt>If the world moves first</dt><dd>It can land part-done, be called off with ' +
      'your money back, or go wrong entirely. That is decided when it fires, not now.</dd>';
    document.getElementById('qd-say').textContent =
      '"drop ' + (SAY[p[1]] || p[1]) + '" or "replace it with ..."';
    dlg.showModal();
  }}
  function openN(el){{
    var parts = el.dataset.n.split('~~');
    document.getElementById('qd-t').textContent = parts[0];
    document.getElementById('qd-b').innerHTML = parts.slice(1).map(function (r) {{
      var kv = r.split('||');
      return '<dt>' + kv[0] + '</dt><dd>' + kv[1] + '</dd>';
    }}).join('');
    document.getElementById('qd-say').textContent = 'just say what you want changed';
    dlg.showModal();
  }}
  function bind(sel, fn){{
    document.querySelectorAll(sel).forEach(function (el) {{
      el.addEventListener('click', function () {{ fn(el); }});
      el.addEventListener('keydown', function (ev) {{
        if (ev.key === 'Enter' || ev.key === ' ') {{ ev.preventDefault(); fn(el); }}
      }});
    }});
  }}
  bind('ol.queue li.live', openQ);
  bind('ul.inforce li.live', openN);
  bind('.ledger .row.live', openN);

  // Clicking the backdrop closes it. A <dialog> reports clicks on its backdrop
  // as clicks on the dialog element itself, so compare against its own box.
  dlg.addEventListener('click', function (ev) {{
    var r = dlg.getBoundingClientRect();
    var inside = ev.clientX >= r.left && ev.clientX <= r.right &&
                 ev.clientY >= r.top && ev.clientY <= r.bottom;
    if (!inside) dlg.close();
  }});

  var epi = document.getElementById('epi');
  if (epi) {{
    // Autofire runs BEFORE anything else in this block. Everything below it is a
    // nice-to-have; the epilogue opening is not. Guarded so a failure in one
    // browser cannot take the rest of the page with it, and retried once on
    // load in case the dialog is not upgraded yet.
    var SETTLED = {'true' if settled else 'false'};
    var openEpi = function () {{
      if (epi.open) return;
      try {{ epi.showModal(); }}
      catch (err) {{ try {{ epi.show(); }} catch (e2) {{ epi.setAttribute('open',''); }} }}
      if (typeof runBadge === 'function') runBadge();
    }};
    if (SETTLED) {{
      openEpi();
      if (!epi.open) setTimeout(openEpi, 60);
      window.addEventListener('load', openEpi);
    }}

    var openBtn = document.getElementById('open-epi');
    if (openBtn) openBtn.addEventListener('click', function () {{ epi.showModal(); }});
    document.getElementById('epi-x').addEventListener('click', function () {{ epi.close(); }});
    epi.addEventListener('click', function (ev) {{
      var r = epi.getBoundingClientRect();
      var inside = ev.clientX >= r.left && ev.clientX <= r.right &&
                   ev.clientY >= r.top && ev.clientY <= r.bottom;
      if (!inside) epi.close();
    }});
    // ---- the badge: ring fills to the score, sun rides the rim by the WORLD's hour
    var runBadge = null;
    var bdg = epi.querySelector('.badge');
    if (bdg) {{
      var sc = +bdg.dataset.score, mx = +bdg.dataset.max;
      var frac = Math.min(1, sc / mx);
      var rad = {{morning:180, day:270, sunset:0, night:60}}['{world_mode}'] * Math.PI/180;
      var sx = 150 + 146*Math.cos(rad), sy = 150 + 146*Math.sin(rad);
      ['b-sun','b-sunglow'].forEach(function (id) {{
        var e = document.getElementById(id);
        e.setAttribute('cx', sx); e.setAttribute('cy', sy);
      }});
      var bheld = document.getElementById('b-held');
      for (var i = 0; i < +bdg.dataset.fronts; i++) {{
        var d = document.createElement('i');
        if (i < +bdg.dataset.held) d.className = 'on';
        bheld.appendChild(d);
      }}
      var bg = document.getElementById('b-sparks'), BNS = 'http://www.w3.org/2000/svg';
      for (var k = 0; k < 18; k++) {{
        var c = document.createElementNS(BNS, 'circle');
        c.setAttribute('class', 'bspark');
        c.setAttribute('cx', 40 + rnd(k+11, 220));
        c.setAttribute('cy', 300 + rnd(k, 30));
        c.setAttribute('r', .8 + rnd(k+5, 1.4));
        c.style.setProperty('--dur', (7 + rnd(k, 8)) + 's');
        c.style.setProperty('--delay', (-rnd(k+3, 14)) + 's');
        bg.appendChild(c);
      }}
      // Runs when the modal opens, not on page load, so the count-up is seen.
      var ran = false;
      runBadge = function () {{
        if (ran) return; ran = true;
        var bfill = document.getElementById('b-fill'), btip = document.getElementById('b-tip');
        requestAnimationFrame(function () {{ requestAnimationFrame(function () {{
          bfill.style.strokeDasharray = (frac*1000) + ' 1000';
        }}); }});
        var t0 = performance.now(), dur = 2400;
        var stepB = function (now) {{
          var pr = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - pr, 3);
          document.getElementById('b-num').textContent = Math.round(sc * e);
          var a = (-90 + 360*frac*e) * Math.PI/180;
          btip.setAttribute('cx', 150 + 118*Math.cos(a));
          btip.setAttribute('cy', 150 + 118*Math.sin(a));
          if (pr < 1) requestAnimationFrame(stepB);
        }};
        requestAnimationFrame(stepB);
      }};
      if (openBtn) openBtn.addEventListener('click', runBadge);
      // The autofire runs before this assignment, so if the modal is already
      // open the count-up has not started. Start it now.
      if (epi.open) runBadge();
    }}

    var flash = function () {{
      var c = document.getElementById('copied');
      c.hidden = false; setTimeout(function () {{ c.hidden = true; }}, 1600);
    }};
    var put = function (text) {{
      if (navigator.clipboard) {{ navigator.clipboard.writeText(text).then(flash, flash); return; }}
      var ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try {{ document.execCommand('copy'); }} catch (e) {{}}
      document.body.removeChild(ta); flash();
    }};
    document.getElementById('copy-story').addEventListener('click', function () {{
      put(document.getElementById('chron').innerText);
    }});
    document.getElementById('copy-share').addEventListener('click', function () {{
      put("{SHARE}");
    }});
    document.querySelectorAll('.etabs .gtab').forEach(function (b) {{
      b.addEventListener('click', function () {{
        document.querySelectorAll('.etabs .gtab').forEach(function (x) {{ x.classList.remove('on'); }});
        document.querySelectorAll('.eview').forEach(function (x) {{ x.classList.remove('on'); }});
        b.classList.add('on');
        document.getElementById(b.dataset.e).classList.add('on');
      }});
    }});
    // The world has ended. Open on arrival; closing leaves the board underneath.
    if (SETTLED) openEpi();   // idempotent: no-op if it already opened
  }}

  document.querySelectorAll('.gtab').forEach(function (b) {{
    b.addEventListener('click', function () {{
      document.querySelectorAll('.gtab').forEach(function (x) {{ x.classList.remove('on'); }});
      document.querySelectorAll('.gview').forEach(function (x) {{ x.classList.remove('on'); }});
      b.classList.add('on');
      document.getElementById(b.dataset.g).classList.add('on');
    }});
  }});
}})();
</script>"""

(HERE / "elsewhere-board.html").write_text(DOC, encoding="utf-8")

# Record this view, so the next one can show what moved in between.
S["seen"] = {"coin": h["coin"], "hands": h["hands"],
             "queue": len(S["queue"]), "tick": S.get("tick", 0),
             "at": now.isoformat()}
(HERE / "state.json").write_text(json.dumps(S, indent=2), encoding="utf-8")
print(f"wrote elsewhere-board.html  ({len(DOC)} bytes) — "
      f"fronts {len(S['factions'])}, beliefs {len(beliefs)}, "
      f"ledger rows {len(rows)}, settled={settled}")

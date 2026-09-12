"""Elsewhere — the epilogue.

A world that ends earns a monument. Reads a state (live or archived) and writes
epilogue.html: a shareable badge with the score inside it, the reckoning, what
each neighbour got, the achievements, and the moments the ledger says mattered.

Everything is DERIVED from the ledger. Nothing is invented, nothing is scored on
vibes. If it says you misfired three times, there are three rows.

    python epilogue.py            # the live world
    python epilogue.py 8812       # an archived one
    python epilogue.py --settle   # end the live world now and write its epilogue
"""

import json, sys, html
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).parent

args = [a for a in sys.argv[1:]]
settle_now = "--settle" in args
seed = next((a for a in args if not a.startswith("--")), None)

src = (HERE / "worlds" / f"{seed}.json") if seed else (HERE / "state.json")
S = json.loads(src.read_text(encoding="utf-8"))

if settle_now and S.get("status") != "settled":
    S["status"] = "settled"
    S["settled_at"] = datetime.now(timezone.utc).isoformat()
    S["epilogue"] = [f'{f["name"]} got what it wanted: {f["wants"]}.'
                     if f["done"] else
                     f'{f["name"]} never finished. They were {f["clock"]}/10 when it ended.'
                     for f in S["factions"]]
    (HERE / "worlds").mkdir(exist_ok=True)
    (HERE / "worlds" / f'{S["seed"]}.json').write_text(json.dumps(S, indent=2),
                                                       encoding="utf-8")
    (HERE / "state.json").write_text(json.dumps(S, indent=2), encoding="utf-8")

L = S["ledger"]
acts = [e for e in L if e["t"] == "action"]
raids = [e for e in L if e["t"] == "raid"]
clocks = [e for e in L if e["t"] == "clock"]
megas = [e for e in L if e["t"] == "mega"]
imps = [e for e in acts if e.get("kind") == "improvise"]

c = {o: len([a for a in acts if a["outcome"] == o])
     for o in ("ok", "partial", "refund", "misfire")}

born = datetime.fromisoformat(S["created"])
died = datetime.fromisoformat(S.get("settled_at", S["last_tick"]))
lifespan = (died - born).total_seconds() / 86400
taken = sum(r["taken"] for r in raids)
stolen = sum(a.get("gain", 0) for a in acts)
watched_rolls = sum(1 for x in clocks if x["watched"])
vigilance = round(100 * watched_rolls / max(1, len(clocks)))
lost = sum(1 for f in S["factions"] if f["done"])
held = len(S["factions"]) - lost

# ---------------------------------------------------------------- score
endurance = round(lifespan * 20)
stewardship = S["holding"]["coin"]
execution = c["ok"] * 30 + c["partial"] * 12 - c["misfire"] * 20 - c["refund"] * 5
defiance = held * 120                      # every neighbour you denied
plunder = stolen
losses = -taken
total = endurance + stewardship + execution + defiance + plunder + losses + vigilance

# badge: what shape the world takes when it is remembered
if total >= 900:
    glyph, rank, line = "sun", "REMEMBERED", "They still use your name for the road."
elif total >= 550:
    glyph, rank, line = "sun", "RECORDED", "A clerk wrote you down. That is not nothing."
elif total >= 300:
    glyph, rank, line = "moon", "TOLERATED", "The reach outlived you and did not comment."
elif total >= 120:
    glyph, rank, line = "moon", "MISLAID", "Two generations, and the ledger is the only proof."
else:
    glyph, rank, line = "tomb", "UNMOURNED", "Nobody agrees how long you were even there."

ROWS = [
    ("Endurance", endurance, f"{lifespan:.1f} days before it ended"),
    ("Defiance", defiance, f"{held} of {len(S['factions'])} neighbours never got what they wanted"),
    ("Execution", execution, f'{c["ok"]} landed &middot; {c["partial"]} partial &middot; {c["refund"]} called off &middot; {c["misfire"]} misfired'),
    ("Plunder", plunder, f"{stolen} coin taken from other people's markets"),
    ("Stewardship", stewardship, "left in the strongbox"),
    ("Vigilance", vigilance, f"{vigilance}% of rolls made under your eye"),
    ("Losses", losses, f"{taken} coin lost in {len(raids)} raid(s)"),
]

# ---------------------------------------------------------------- achievements
false_beliefs = [f for f in S["facts"] if f["visibility"] == "false"]
A = []


def earn(cond, name, line):
    if cond:
        A.append((name, line))


earn(held == len(S["factions"]), "Nobody Got Anything",
     "Not one neighbour finished. That is not supposed to be possible.")
earn(held >= 1 and lost >= 1, "You Held The Line Somewhere",
     f"{held} of {len(S['factions'])} were denied. The rest took what they came for.")
earn(lost == len(S["factions"]), "Everyone Got What They Wanted",
     "Every agenda completed. The reach was scenery.")
earn(len(imps) >= 1, "Not On The Menu",
     f"{len(imps)} order(s) nobody designed. You asked for something that did not exist.")
earn(stolen >= 100, "The Dying Traveller",
     f"{stolen} coin taken out of other people's markets by people who were not dying.")
earn(c["misfire"] >= 1, "Fired Into The Void",
     f'{c["misfire"]} order(s) executed into a situation that had stopped existing.')
earn(c["misfire"] == 0 and acts, "Clean Sheet",
     "Not one order fired into a world that had moved. Suspicious.")
earn(len(raids) >= 2, "Soft Target",
     f"Robbed {len(raids)} times. Being elsewhere is a policy with consequences.")
earn(len(megas) >= 1, "The Great Work",
     "You staked the entire purse on one undertaking.")
earn(any(m["outcome"] == "mutated" for m in megas), "Granted Sideways",
     "The wish was granted. Not as asked.")
earn(len(false_beliefs) >= 1, "Confidently Wrong",
     "You ended holding beliefs that were never true. Nobody corrected you.")
earn(S["holding"]["coin"] == 0, "Bled Dry", "The strongbox reached zero.")
earn(lifespan < 7, "Fast Collapse", f"The whole world resolved in {lifespan:.1f} days.")
earn(not acts, "Absentee Landlord", "You never gave a single order.")

# ---------------------------------------------------------------- moments
M = []
big = max(raids, key=lambda r: r["taken"], default=None)
if big:
    M.append((big["at"], f'{big["front"].replace("-", " ").title()} took {big["taken"]} coin',
              f'd6 {big["roll"]} + aggression {big["mods"][0][1]} = {big["total"]} vs {big["threshold"]}'))
first_done = next((f for f in S["facts"] if "got what it wanted" in f["fact"]), None)
if first_done:
    M.append((first_done["at"], first_done["fact"], "and everybody found out"))
best = max((a for a in acts if a["outcome"] == "ok"),
           key=lambda a: a.get("gain", 0), default=None)
if best:
    M.append((best["at"], f'"{best["what"]}" landed',
              f'd6 {best["roll"]}' + (f' &middot; +{best["gain"]} coin' if best.get("gain") else "")))
worst = min(acts, key=lambda a: a["total"], default=None)
if worst:
    M.append((worst["at"], f'"{worst["what"]}" &mdash; {worst["outcome"]}',
              f'd6 {worst["roll"]}, drift &minus;{worst["drift"]} = {worst["total"]}'))
for m in megas:
    M.append((m["at"], m.get("mutation") or "The great work landed",
              m.get("tale", "")[:120]))
M.sort()


def esc(x):
    return html.escape(str(x))


GLYPH = {
    "sun": '<circle cx="110" cy="110" r="62" class="disc"/>'
           + "".join(f'<rect x="107" y="8" width="6" height="22" rx="3" class="ray" '
                     f'transform="rotate({a} 110 110)"/>' for a in range(0, 360, 30)),
    "moon": '<path class="disc" d="M110 40a70 70 0 1 0 52 117A78 78 0 0 1 110 40Z"/>',
    "tomb": '<path class="disc" d="M62 190V96a48 48 0 0 1 96 0v94Z"/>'
            '<rect x="46" y="186" width="128" height="14" rx="4" class="disc"/>',
}

fates = "".join(
    f'<li class="{"lost" if f["done"] else "held"}"><b>{esc(f["name"])}</b>'
    f'<span class="st">{esc(f["style"])}</span>'
    f'<p>{esc(f["wants"]).capitalize()}. '
    + ("<b>They got there.</b>" if f["done"]
       else f'They never finished &mdash; {f["clock"]}/10 when it ended.')
    + "</p></li>" for f in S["factions"])

ach = "".join(f'<div class="ach"><b>{esc(n)}</b><p>{l}</p></div>' for n, l in A) \
      or '<p class="muted">No achievements. That is itself remarkable.</p>'

moments = "".join(
    f'<li><span class="when">{m[0][5:16].replace("T", " ")}</span>'
    f'<span class="what">{m[1]}</span><code>{m[2]}</code></li>' for m in M)

score_rows = "".join(
    f'<tr><td>{n}</td><td class="d">{d}</td>'
    f'<td class="v{" neg" if v < 0 else ""}">{v:+d}</td></tr>' for n, v, d in ROWS)

DOC = f"""<title>Elsewhere - An Epilogue</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Spectral:ital,wght@0,300;0,400;0,600;1,300&display=swap">
<style>
:root{{--bg:#0d0c0b;--panel:#171513;--ink:#e9e1d3;--mid:#a9a297;--soft:#6f6a62;--edge:#2a2622;
--ember:#ff4d00;--ember2:#ff6a1a;--glow:rgba(255,77,0,.42);
--serif:Spectral,Georgia,serif;--caps:Cinzel,serif}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);font-size:14px;line-height:1.6}}
.page{{max-width:720px;margin:0 auto;padding:46px 20px 90px;display:flex;flex-direction:column;gap:34px}}
.label{{font-family:var(--caps);font-size:9px;letter-spacing:.38em;color:var(--soft);text-align:center}}
.rule{{height:1px;background:linear-gradient(to right,transparent,var(--edge),transparent)}}
header{{text-align:center;display:flex;flex-direction:column;gap:12px}}
h1{{font-family:var(--caps);font-weight:400;font-size:clamp(30px,8vw,54px);letter-spacing:.05em;line-height:1;margin:0}}
h1 em{{font-style:italic;color:var(--ember)}}
.dates{{font-size:11px;letter-spacing:.16em;color:var(--soft);text-transform:uppercase}}

/* the shareable badge */
.badge{{display:flex;flex-direction:column;align-items:center;gap:4px}}
.badge svg{{width:min(300px,72vw);height:auto;overflow:visible}}
.badge .disc{{fill:none;stroke:var(--ember);stroke-width:3}}
.badge .ray{{fill:var(--ember);opacity:.85}}
.badge .ring{{fill:none;stroke:var(--edge);stroke-width:1.5}}
.badge .score{{font-family:var(--caps);font-weight:600;font-size:62px;fill:var(--ink);text-anchor:middle;dominant-baseline:central;letter-spacing:.02em}}
.badge .rankt{{font-family:var(--caps);font-size:11px;letter-spacing:.36em;fill:var(--ember);text-anchor:middle}}
.badge .who{{font-family:var(--caps);font-size:8.5px;letter-spacing:.3em;fill:var(--soft);text-anchor:middle}}
.badge .l{{font-family:var(--serif);font-style:italic;font-size:19px;color:var(--mid);margin-top:6px;text-align:center;text-wrap:pretty}}

table{{width:100%;border-collapse:collapse;font-size:12.5px}}
td{{padding:11px 0;border-bottom:1px solid var(--edge);vertical-align:top}}
tr:last-child td{{border-bottom:0}}
td.d{{color:var(--soft);font-size:11.5px;padding-left:14px;font-style:italic}}
td.v{{text-align:right;font-family:var(--caps);color:var(--ember);white-space:nowrap;font-variant-numeric:tabular-nums}}
td.v.neg{{color:var(--mid)}}
h2{{font-family:var(--caps);font-size:10px;letter-spacing:.32em;color:var(--ember);margin:0 0 14px;text-align:center;font-weight:400}}
ul.fates{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:16px}}
ul.fates li{{border-left:2px solid var(--edge);padding-left:15px}}
ul.fates li.lost{{border-left-color:var(--ember)}}
ul.fates b{{font-family:var(--caps);font-size:15px;letter-spacing:.05em}}
.st{{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--soft);margin-left:10px}}
ul.fates p{{margin:4px 0 0;color:var(--mid);font-weight:300;text-wrap:pretty}}
.ach{{padding:12px 0;border-bottom:1px solid var(--edge)}}
.ach:last-child{{border-bottom:0}}
.ach b{{font-family:var(--caps);font-size:11px;letter-spacing:.12em}}
.ach p{{margin:4px 0 0;color:var(--mid);font-size:12.5px;font-weight:300}}
ol.moments{{list-style:none;margin:0;padding:0}}
ol.moments li{{padding:13px 0;border-bottom:1px solid var(--edge);display:flex;flex-direction:column;gap:4px}}
ol.moments li:last-child{{border-bottom:0}}
.when{{font-size:10px;letter-spacing:.14em;color:var(--soft);text-transform:uppercase}}
.what{{font-size:17px;font-weight:300;text-wrap:pretty}}
ol.moments code{{font-size:11px;color:var(--soft)}}
.muted{{color:var(--soft);text-align:center}}
footer{{text-align:center;color:var(--soft);font-size:10.5px;line-height:1.9;letter-spacing:.04em}}
footer code{{color:var(--ember);opacity:.7}}
</style>

<div class="page">
  <header>
    <div class="label">AN EPILOGUE &middot; ELSEWHERE</div>
    <h1>{esc(S['holding']['name']).upper()}<br><em>has ended</em></h1>
    <div class="dates">{born.strftime('%d %b')} &mdash; {died.strftime('%d %b %Y')} &middot; {lifespan:.1f} days &middot; seed {S['seed']}</div>
  </header>

  <div class="badge">
    <svg viewBox="0 0 220 260" role="img" aria-label="Score {total}, rank {rank}">
      <circle class="ring" cx="110" cy="110" r="98"/>
      {GLYPH[glyph]}
      <text class="score" x="110" y="112">{total}</text>
      <text class="rankt" x="110" y="232">{rank}</text>
      <text class="who" x="110" y="252">{esc(S['holding']['name']).upper()} &#183; {lifespan:.0f} DAYS &#183; {held}/{len(S['factions'])} HELD</text>
    </svg>
    <p class="l">{line}</p>
  </div>

  <div class="rule"></div>
  <section><h2>The reckoning</h2><table>{score_rows}</table></section>
  <div class="rule"></div>
  <section><h2>What they wanted</h2><ul class="fates">{fates}</ul></section>
  <div class="rule"></div>
  <section><h2>What you earned</h2>{ach}</section>
  <div class="rule"></div>
  <section><h2>Moments</h2><ol class="moments">{moments}</ol></section>

  <footer>
    Every number here was rolled by <code>engine.py</code> under seed {S['seed']},<br>
    written to a ledger of {len(L)} entries, and re-derived for this page.<br>
    Nothing was decided after the fact.
  </footer>
</div>"""

(HERE / "epilogue.html").write_text(DOC, encoding="utf-8")
print(f"wrote epilogue.html — {total} ({rank}), badge '{glyph}', "
      f"{len(A)} achievements, {len(M)} moments, {held}/{len(S['factions'])} held")

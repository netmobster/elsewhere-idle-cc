# Elsewhere — build log

Running record of every iteration. Written after each bench run so nothing is
lost if the session dies.

## The fitness test

A build "passes" when all five hold. Measured by `bench.py`, not by opinion.

| # | Criterion | Target |
|---|---|---|
| 1 | **Differentiation** | attentive score > erratic > absentee, attentive beating absentee by ≥150 |
| 2 | **Attention pays** | attentive keeps the world alive ≥12 days; absentee ≤8 |
| 3 | **Outcome spread** | no single queue outcome exceeds 55% of all actions |
| 4 | **Living economy** | attentive ends with coin > 0 and is never at 0 for more than 2 straight days |
| 5 | **Still loseable** | attentive does not prevent every front from completing — at least one lands |

Criterion 5 matters: a game the attentive player always wins is as broken as one
they always lose.

---

## v0.1 — baseline (2026-09-08)

Engine as shipped. Actions resolve to ok/partial/refund/misfire but **have no
effect on the world**.

| strategy | days | coin | settled |
|---|---|---|---|
| attentive | 4 | 0 | yes |
| absentee | 6 | 0 | yes |
| erratic | 5 | 0 | yes |

**FAIL on 1, 2, 4.** Playing attentively did *worse* than not playing. Nothing a
player buys slows a clock or stops a raid, so both attention and spending are
decorative. Coin drains to zero on day one and stays there.

Diagnosis: the queue is a random-outcome generator attached to nothing. The world
model and the player model never touch.

Fix planned for v0.2 — action *types* with real effects:
- `fortify` — raises the bar a raid has to clear against you
- `disrupt` — adds a negative mod to a target front's clock rolls
- `trade` — converts openness into coin
- `scout` — reveals a front's true clock without spending your one watch
- `invest` — raises hands production

Plus the sim player has to become type-aware, or "attentive" will keep buying the
most expensive thing rather than the right thing.

---

## v0.2 — actions get effects (2026-09-09)

Added an action catalogue. A landed action now changes the world:

| kind | effect | cost |
|---|---|---|
| `disrupt` | −3 to a front's clock rolls for 12 ticks | 60 |
| `fortify` | +3 to the bar a raid must clear | 50 |
| `trade` | coin = openness × 12 | 20 |
| `scout` | reveals a front's true clock as a `known` fact | 30 |
| `invest` | +hands and +coin production | 40 |

`partial` applies the effect at half power. `refund` and `misfire` apply nothing.
Sim player rewritten to be type-aware — priority order, not most-expensive-first.

**2/5 → 4/5.** attentive 1007 vs absentee 473.

## v0.3 — the clock-speed dead end

Tried `unwatched +1 → +2` to make absence bite.

**4/5 → 2/5.** Reverted.

⭐ **Drift is derived from clock speed.** Faster clocks means every queued action
goes stale before it fires — misfires tripled to 20% and differentiation
collapsed. Clock speed and queue viability are the same dial. Do not tune absence
through it.

## v0.4 — criterion 2 was mis-specified

`absentee <= 8 days` forces fast clocks, which v0.3 proved breaks the queue. The
design goal was never an absolute number, it was that attention visibly extends a
world's life. Rewrote as a **ratio: attentive ≥ 1.6× absentee.** Harder to game
than the absolute, and it does not dictate the tuning that satisfies it.

## v0.5 — the economy, and a reward for absence

Added passive income. Immediately backfired: the absentee accumulated **232 coin
doing nothing** and their score inflated on stewardship alone.

Fix: **no orders, no revenue.** Income only accrues while the queue is non-empty.
A holding nobody is running does not earn.

## v0.6 — ⛔ the bench was not reproducible

`sim.py` seeded the player with `hash(strategy)`. Python salts string hashing per
process, so **the same code produced different verdicts on consecutive runs** —
which invalidated the whole v0.5 tuning sweep. Replaced with
`crc32(strategy) ^ seed`. Verified: two consecutive runs now agree exactly.

Every number before this point should be treated as indicative, not measured.

## v0.7 — the watch lapses ✅ PASS

Last failure was criterion 2: an absentee's world still lived ~15 days.

The fix that worked is not a speed change, it is a **decay**: eyes stay posted
`WATCH_TICKS` (3 days) past your last order, then go home. Nobody keeps a lookout
for a lord who never sends word. Absence now compounds — you lose your watch,
every front goes unwatched, and the world accelerates for you specifically.

### Result — 12 seeds, 21 days, deterministic

| strategy | score | life | coin | actions | ok% | misfire% | fronts lost |
|---|---|---|---|---|---|---|---|
| attentive | **1200** | 17.5d | 110 | 46.2 | 45% | 5% | 1.8 / 3 |
| erratic | 549 | 14.2d | 54 | 18.1 | 30% | 6% | 2.6 / 3 |
| absentee | 311 | 10.2d | 104 | 4.5 | 30% | 13% | 2.9 / 3 |

```
PASS  1 differentiation  gap 888
PASS  2 attention pays   17.5d vs 10.2d — 1.7x
PASS  3 outcome spread   ok 40 / partial 31 / refund 23 / misfire 5
PASS  4 living economy   attentive ends solvent, never broke >2 days
PASS  5 still loseable   attentive still loses 1.8 of 3 fronts
```

**===> PASS (5/5)** on both 8 and 12 seeds.

### What the passing build says about the design

- Skilled play is worth ~4× an absentee's score, and nearly **2× the world's life**
- It is still lost: the best player surrenders 1.8 of 3 fronts on average
- Absence is punished three ways that compound — the queue drains, the revenue
  stops, and the watch goes home
- The queue is the decision, and it is now genuinely tense: 23% refunds and 5%
  misfires means roughly a quarter of what you plan does not survive contact

### Next, if it continues

`fortify` is the least-picked action — the planner only buys it after a raid,
which is reactive. Chained actions (slot 4 needs slot 2 to have landed) were
designed but never built. The genie is still unwritten.

## v0.8 — ⛔⛔ the world RNG was never deterministic

**The v0.6 fix was incomplete and the v0.7 PASS was not a measurement.**

v0.6 fixed the *player* RNG. The *world* RNG was seeded like this:

```python
base = int(datetime.fromisoformat(s["created"]).timestamp())
rng  = tick_rng(s, base + i)
```

`s["created"]` is wall-clock time. **Every run drew a different world stream.**
Two benches three seconds apart returned attentive 833 and attentive 660.

The v0.6 reproducibility check passed because both runs happened to land inside
the same second. One confirming observation, treated as proof. The v0.7 "PASS
5/5" was therefore a single sample of a stochastic process, not a result.

Fix: seed on the absolute tick counter, never the clock.

```python
rng = tick_rng(s, s["tick"])   # (seed, tick) — nothing else
```

Verified properly this time: three benches, spaced two seconds apart, byte-identical.

### Honest re-measurement — 12 seeds, deterministic

| strategy | score | life | coin | actions | ok% | misfire% | fronts lost |
|---|---|---|---|---|---|---|---|
| attentive | **917** | 17.0d | 104 | 38.5 | 39% | 9% | 2.4 / 3 |
| erratic | 386 | 13.8d | 25 | 12.8 | 26% | 14% | 2.9 / 3 |
| absentee | 222 | 8.0d | 85 | 4.5 | 20% | 19% | 3.0 / 3 |

**===> PASS (5/5)**, reproducibly.

The design conclusions survive — attention is worth ~4× and 2.1× the world's
life — but every number in v0.2 through v0.7 was noise, and the tuning decisions
made from them were made on noise. They happened to land somewhere that passes.
That is luck, not method.

**Lesson: "I verified it twice" is not verification when the failure mode is
time-dependent.** Space the runs, or vary the thing you think is fixed.

## v0.9 — mega projects, mutations, interest, and the hoarder ✅ 6/6

Built together and benched as a system, per the operator's call. Three additions:

**Compounding interest.** 10 / 15 / 25 / 40% per consecutive unspent day. Any
spend resets the streak.

**MEGA PROJECT.** Costs the entire purse and all labour. `2d6 + scale − 2×drift`
against 9. On success the target loses 6 segments and eats a heavy disrupt. On
anything else it **mutates** — the wish granted sideways, from a table of ten.

**Purse-scaled raids.** `taken` was flat (`10 × aggression`). Now it scales with
what there is to take. A fat purse is a bigger target.

### The operator's hypothesis, tested

> *"the faction system and raids will solve for most of hoarding… forever hoarding
> won't ever truly catch you up (an economic inversion likely WOULD though)"*

**First half: confirmed.** A dedicated `hoarder` strategy scores 321 against the
attentive player's 741. Fronts advance while the purse fills; the world does not
wait.

**Second half: exactly backwards, and better for it.** `INVERSION` trades coin for
labour at 30:1 against a hands cap of 10 — so a purse of 1200 becomes 30 coin. It
is the most punishing result a hoarder can draw, and it *rewards* the cash-poor,
labour-rich profile of an active player. The mutation expected to rescue hoarding
is the one that erases it.

### Two bugs the bench found that neither of us predicted

⛔ **Mega was unreachable.** The hoarder fired **zero** mega projects across 12
seeds — average purse 111 against a 400 trigger. The revenue gate meant an empty
queue earned nothing while raids stripped it faster than interest compounded. The
strategy built to reach the mechanic could not reach it. Fixed by having the
hoarder keep one cheap order running, which is now a real skill expression:
hoarding correctly means *staying active while saving*, not going dark.

⛔ **Interest was never gated.** Revenue required a non-empty queue; interest did
not. So an absentee compounded untouched and reached **548 coin and a score of
708**, nearly matching the attentive player. Exactly the Fallen London conflict —
a cap forces return, uncapped interest rewards leaving. Fixed: a purse nobody is
managing earns nothing.

### Result — 12 seeds, 4 strategies, deterministic

| strategy | score | life | coin | actions | fronts lost |
|---|---|---|---|---|---|
| attentive | **741** | 15.8d | 79 | 33.3 | 2.6 / 3 |
| erratic | 366 | 15.4d | 17 | 7.2 | 2.8 / 3 |
| hoarder | 321 | 9.8d | 88 | 6.9 | 2.9 / 3 |
| absentee | 286 | 7.8d | 135 | 3.7 | 3.2 / 4 |

```
PASS  1 differentiation  lead 375 over the next best
PASS  2 attention pays   15.8d vs 7.8d — 2.0x
PASS  3 outcome spread   ok 34 / partial 29 / refund 24 / misfire 12
PASS  4 living economy   solvent, never broke >2 days
PASS  5 still loseable   still surrenders 2.6 of 3 fronts
PASS  6 hoarding loses   741 vs 321
===> PASS (6/6), verified across spaced runs
```

**Mega census:** 25 fired · 6 landed clean (24%) · 19 mutated (76%).
Flavours — world 8, mixed 4, good 4, bad 3. Eight of ten mutation types have
fired in the wild.

Absentee shows `3.2 / 4` fronts because a mutation spawned a fourth faction:
their day-one random queue rolled a mega, and `SCHISM` or `A BENEFACTOR` landed.
The world can now grow factions it was not seeded with.

### Note on Neptune's Pride, Fallen London, PBEM and Tides

Prior art reviewed this session. The load-bearing lessons:

- **Neptune's Pride** — real-time-over-days produces compulsion, not calm. The
  once-a-day cap is a safety rail, not a limitation. Expect tick-timing play.
- **Fallen London** — a *cap* forces return. Uncapped interest does the reverse.
  This directly caught the v0.9 interest bug.
- **Play-by-post 4X** — the motivator is other humans waiting. Elsewhere has
  nothing in that slot, and that gap is unaddressed.
- **Tides of Tomorrow** — async ghost influence. `worlds/` already archives every
  settled world; seeding new factions from other players' collapses is close to
  free and is the cheapest answer to the missing-social-obligation problem.

**Still unbuilt:** the cliffhanger line. Every one of those four gives a reason to
return *tomorrow specifically*. Elsewhere punishes absence but never invites
presence, and that is probably why the first playable turn got closed rather than
played.

## v1.0 — the dare, the cliffhanger, and a fog leak I reintroduced

**"Mega hoarding CAN be worth it… if you daaare."** The problem was one line:
`scale = min(3, spent // 100)`. Spending 1200 bought exactly the same bonus as
spending 300, so daring bigger bought nothing. A strictly dominated strategy is
dead content, not a temptation.

The stake now buys three things:

| stake | needs on 2d6 | clock wipe | bad-twist weight |
|---|---|---|---|
| 150 | 8+ | 5 | 4 |
| 300 | 7+ | 6 | 3 |
| 600 | 5+ | 8 | 1 |
| 900+ | 3+ | 10 | 1 |

Plus a **MYTHIC** tier at 800+ coin and a total of 14+: every other front loses
three segments and half the treasury comes back. And the twist table is now
weighted by stake — fortune favours the bold does not mean avoiding the twist, it
means buying a better class of twist.

**Result: the dare is real.** The hoarder beats the careful player in **5 of 12
seeds (42%)** while losing on average, 476 to 741. Criterion 6 rewritten from
"hoarding loses" to a win-rate band of 15–45%, which is the actual design goal.

### ⛔ I reintroduced the C2 fog leak

`horizon()` computed time-to-completion from `SEGMENTS - f["clock"]` — the **true**
clock — so it handed the player an accurate countdown for fronts they had no eyes
on. Same bug class as the ledger leak fixed one day earlier, in new code, written
by the same author who had just documented it.

Fixed: an estimate requires a clock, and you only have a clock for what you can
see. Unwatched fronts return `rumour: true` with no number.

**This produced an interaction worth keeping:** `scout` writes a `known` fact
carrying a real number, so scouting a front *buys you a countdown for it*. The
information action now has a second, better use than it was designed for.

### Also shipped

- `engine.py ff 8h` — hour-granular fast-forward for playtesting (`h` suffix =
  hours, bare number = days). Offered in chat after each turn as 4/8/12/24h.
- `engine.py horizon` — the cliffhanger feed.
- `/elsewhere` updated: cliffhanger is a required briefing step, skip offered after
  the turn, mega documented in the catalogue.

**Bench: 6/6, unchanged by any of it.**

## v1.0.1 — two interface bugs, both mine

**The artifact was still called "Varn's Reach."** Artifact titles are sticky across
redeploys by design, so renaming `<title>` never renamed the artifact. The board
had been living under a dead placeholder for days. Fixed by renaming the render
target to `elsewhere-board.html`, which forces a fresh artifact identity.

**The modal never rendered.** Three dismissed pickers, and I guessed at the cause
twice — "wrong moment", then "it steals the input box". Both invented from the
outside without looking.

The operator sent a screenshot. `AskUserQuestion` was rendering in this client as
the **raw `questions: [{...}]` JSON payload**, as a text blob, with nothing
clickable. There was never a picker to dismiss.

**That diagnosis was also wrong.** The JSON blob in the screenshot was the expanded
transcript record of the question, not a failed render. The picker worked. The
operator said so directly: *"the modal was totally great! I just couldn't send you
FEEDBACK while it was up!"*

> **Rule: keep the modal. Give it an escape hatch.** Every turn modal ends with
> **"Hold — I want to type"**, which closes it and waits.

⭐ **The wider lesson is about diagnosis, not pickers.** THREE confident
explanations in a row — "wrong moment", "it steals the input", "it does not
render" — and the second one was correct before it got discarded on a misread
screenshot. Ask the user what is wrong instead of inferring it; they answer in one
line and it is the right line.

## v1.0.2 — ⛔ a gameplay fix silently invalidated the balance (2026-09-11)

Caught on the last check before the first push, by running `bench.py` from a clean
copy of exactly the files that were about to ship. It failed 3 of 6.

**What happened.** In v1.0.1 the epilogue modal wasn't firing. One of the two causes
was the settle rule: the world only ended when **all three** neighbours completed
their agendas, so a world where the operator had already lost kept running and the
epilogue never came. The operator's framing was unambiguous — *"if they won, I
lost"* — so the rule became `any()`.

That is the right rule. It is also a balance change, and I did not treat it as one.

```
                        all()        any()
world length            17.5 d       6.2 d
attentive score          1200          223
hoarder score             476          312
hoarder beats careful    42%           67%
```

Settling on the first completed agenda cut every world to a third of its length. The
hoarder took the game, because **compounding interest does not care how short the
game is and spending does** — five days is not enough to convert coin into position,
but it is plenty to accrue 40% on a fat strongbox.

Four documents were publishing the old numbers, and `PRD-TRD.md` still described the
`all()` rule in prose. The README's entire *"Is it balanced?"* section — the section
that makes the case for the design — was false.

**The fix.** Slow the clocks to put the long world back: `CLOCK_THRESHOLD` 5 → 6 and
`DOUBLE_AT` 8 → 10. Nothing else. Worlds return to ~14.5 days and the order of merit
inverts back.

```
attentive    941   14.5 d      lost a front in 10 of 12
hoarder      644    8.3 d      beat careful play in 3 of 12
erratic      283    6.6 d
absentee     274    6.2 d
PASS 6/6
```

**Criterion 5 had to be restated, and that deserves scrutiny.** It read *"attentive
still loses ≥ 1 front"* as a mean across seeds. Under `any()` a settled world has
**exactly one** finished agenda, so the mean is pinned at a ceiling of 1.0 — and
demanding a mean of ≥1 therefore demands that the attentive player *never* holds the
world open past the bench horizon. That is the opposite of what the criterion was
protecting, which is "you usually lose". It is now a rate: **a front is lost in ≥70%
of seeds**, currently 83%. The rare world where careful play holds all three at bay
for three weeks is a real outcome and should be reachable.

Moving a goalpost to make a test pass is how you get a green suite and a broken game.
The distinction here: the metric was measuring a quantity whose range the rule change
had collapsed. The intent did not move.

**The lesson, which is the same one as v0.6 and v0.8.** A one-word change inside an
`if` was a balance change wearing a bugfix's clothes. The determinism bugs were caught
because the bench disagreed with itself; this one was caught because the bench was run
at all, on the shipping files, after the fix. **Run the harness after gameplay
changes, not only after balance changes — you do not get to decide which is which.**

---

## For the README (netmobster/elsewhere-idle-cc)

**The README is the site.** There is no separate landing page — GitHub's repo
front page IS the marketing, the manual and the demo. Write it as a page someone
lands on cold, not as developer docs. That means: a hook in the first three lines,
a screenshot of the board near the top, the pitch before the install steps, and
the four surfaces explained before any code. Anchored sections so the nav works.
Everything else links out from it.

Files: `README.md` (the site), `aboutjay.md`, `installer.md`, `LICENSE`,
`llms.txt`, `resources.md` with every relevant file linked and documented.

**Licence: recommend MIT** unless the operator's pick says otherwise — maximum
adoption, and the awesome-lists favour it. Ask before overriding.

**Install story:** clone the repo, let Claude Code build whatever local files are
needed. The README is instructions *for the agent*, not a setup script. Ship
`.claude/commands/elsewhere.md` inside the repo so it installs by cloning.

**Artifacts are Team/Enterprise gated** — say plainly that the board is a plain
HTML file on disk and artifact publishing is the upgrade, not the requirement.

### What the README has to carry

- Features and functionality
- The thinking, not just the rules
- The engine, and the **deterministic-rolls vs AI-interpretation** position:
  the engine rules, the model narrates, and the model being *surprised* by a roll
  is the proof the dice are real
- **The SEREN DNA, credited by link: https://seren-dm.lovable.app/**
  The genesis of the engine, the ledger and the roll system. Name it, do not
  paraphrase it. What came across:

  | from SEREN | what it does here |
  |---|---|
  | *"the model narrates a result it did not choose"* | the single load-bearing rule |
  | fronts and clocks | *"advances when the party is elsewhere"* became *"advances while you sleep"* |
  | an append-only ledger with its arithmetic showing | every row clickable, every number checkable |
  | `facts.jsonl` and the four visibility values | SEREN specced them and never wired a consumer. This is the consumer |

  Worth saying plainly: the fog layer was **designed for SEREN, shipped unused, and
  found its purpose in a different game.** Better than "inspired by", and true.

### The operator's own read, which is the positioning

> *"the chaos goblin option is AMAZING and is almost MORE fun than SEREN. SEREN is
> more IMMERSIVE, this is pick up and PLAY."*

Two games off one engine, and they are not competing:

| | SEREN | Elsewhere |
|---|---|---|
| shape | immersive, sit-down | pick up and play |
| session | an evening | two minutes a day |
| the model | dungeon master | narrator and translator |
| the draw | being inside a story | finding out what happened without you |

**Do not sell Elsewhere as SEREN-lite.** It is the same engineering honesty at a
different cadence, and the freeform layer is arguably a better showcase for the
engine's discipline precisely because the asks are absurd and the dice still rule.

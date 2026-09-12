# Elsewhere — PRD / TRD

**Status:** V0.2, passing fitness (5/5 across 12 seeds)
**Surface:** Claude Code — terminal as controller, artifact sidebar as screen
**Complexity target:** 4–6 on the operator's own scale (SEREN = 12, Yahtzee = 2). Currently ~6.

---

# Part 1 — Product

## 1.1 The one-line

**An idle real-time RPG that lives in Claude Code.** A turn-per-day strategy game where **your absence is the mechanic**: the world advances in real time whether you show up or not, and the orders you left behind execute into a world that has since moved.

## 1.2 The problem it solves

Idle games reward absence with accumulated progress. Live games punish it with nothing happening. Neither treats time away as *interesting*. Elsewhere makes the gap between sessions the source of both the tension and the comedy — you return holding stale information, and a plan written for a world that no longer exists.

## 1.3 The four surfaces

The operator's framing, and the clearest statement of the design:

> **The sidebar is deterministic. The chat is intelligence. The modal is options.
> Freeform lets the player ask for anything and the AI responds on the fly.**

The fourth is the product. Send missionaries to convert a neighbour, marry into
one, pay the raiders to rob somebody else, fake your own collapse. The ask is
translated into a price and a modifier drawn from the world as it actually is,
then rolled on the same ladder as every other order. **The model maps; the engine
rules.** That is what makes it an RPG rather than a dashboard, and it is why the
guide ships an **Ask for anything** tab — without it, players assume five buttons
is the whole game.

| surface | job | never does |
|---|---|---|
| **Sidebar** | State. Exactly what is true, rolled by the engine, arithmetic showing. | Interpret. Advise. Invent. |
| **Chat** | Intelligence. Reads the ledger and says what it means. | Decide outcomes. Contradict a roll. |
| **Modal** | Options. The turn as a small number of clicks with real costs attached. | Carry the whole game. It is a fast path, not the only path. |
| **Freeform** | Anything not in the menu. The player asks, the model answers in the fiction. | Break the engine. Anything with a mechanical effect goes through the engine. |

**The narrator narrates; it never arbitrates.** Every outcome exists in the ledger
before a word is written about it. When a roll surprises the narrator, that surprise
is genuine and it is the strongest evidence the player has that the dice are real.
A narrator that decided outcomes could not be surprised, and the player would know.

**And the player's own words set the register.** Improvised orders keep `said`
verbatim, so the chronicle is written back in the voice the player brought to it.
The same world, played wry, produces a wry history.

This is why the game needs an agent and not a UI. A menu can do the first three. Only
a model can do the fourth, and the fourth is what makes the first three feel alive.

## 1.4 Why this surface

Three things Claude Code has that a chat window does not:

| Capability | What it buys |
|---|---|
| **A save file on disk** | The world survives sessions, and knows exactly how long you were gone |
| **Executable code as referee** | Dice are rolled by a seeded RNG and written down. The narrator cannot fudge them |
| **A live artifact sidebar** | A persistent, drill-down board that redraws each turn |

## 1.4 The core loop

```
   ┌── you queue up to 5 actions and pick what to watch
   │
   │   ...real time passes. 3 ticks per day. The world rolls.
   │      Your queue executes one action per tick against
   │      whatever the world looks like WHEN IT FIRES.
   │
   └── you return to a briefing: what happened, what it cost,
       and which of your orders survived contact
```

**Session length: 2–5 minutes. One turn per calendar day.**

## 1.5 The two-part turn

1. **The spend** — a sequential modal of what you can currently afford. Each pick recomputes the bank, so the second question only offers what the first left you. Thumbs, not typing.
2. **The intent** — freeform text stating what you are actually trying to achieve. This does not bind the engine; it gives the briefing something to measure the outcome against.

## 1.6 Design pillars

- **The model narrates a result it did not choose.** Borrowed from SEREN. Every outcome is rolled in code and written to a ledger with its arithmetic showing. Prose may not contradict it.
- **The sidebar is your file on the world, not the world.** It renders what you know and suspect. It never renders truth, and never flags which of your beliefs is wrong.
- **Absence must compound.** One punishment is a cost; three that stack is a mechanic.
- **It must stay loseable.** The best player loses a neighbour in ~5 worlds out of 6.

## 1.7 What a world is

Three procedurally generated factions ("fronts"), each with an agenda and a 10-segment clock. Clocks fill in real time. When **any** front lands, the world **settles** — you get an epilogue and it is archived. Worlds die of neglect; run length is a function of attention, not a fixed season.

Each faction rolls a personality vector that biases existing rolls rather than adding systems:

| Stat | 1–6 | Drives |
|---|---|---|
| `aggression` | | whether it raids an undefended holding |
| `expansive` | | clock speed |
| `openness` | | trade yield |

## 1.8 Out of scope for V0.2

Chained actions · disasters that change the production math · the genie wish · a map · multiplayer · faction diplomacy · anything resembling a tech tree.

---

# Part 2 — Technical

## 2.1 Architecture

```
engine.py     truth.  (seed, state, elapsed) → new state + ledger. Deterministic.
sim.py        fast-forward. Scripted players for testing.
bench.py      the judge. Fitness criteria across N seeds.
render.py     sidebar.html — the player's file on the world
epilogue.py   epilogue.html — the monument for a settled world
report.py     report.html — playtest report + post-mortem
state.json    the save
worlds/       archived settled worlds
```

**Genesis:** the engine, the ledger and the roll system descend from **SEREN**
(https://seren-dm.lovable.app/) — a single-player AI dungeon master whose own
description is *"files and the shell keep the numbers honest."* This is that
principle at a different cadence.

**The discipline:** Python owns truth, the narrator owns voice. Any outcome the narrator states must exist as a ledger row.

## 2.2 Determinism

Per-tick RNG is `sha256(f"{seed}:{tick}")`. Same seed and same elapsed time reproduces a world exactly, forever, on any machine.

> ⚠️ **Known trap, hit twice.**
> 1. `sim.py` seeded its player with `hash(strategy)`. Python salts string hashing per process. Use `zlib.crc32`, never `hash()`.
> 2. **Worse:** `engine.tick` seeded the world stream from `s["created"]` — wall-clock time. Two benches seconds apart returned different results, and the v0.7 "PASS" was one sample of a stochastic process. Per-tick RNG must derive from `(seed, absolute tick)` and **nothing else**. No clock, no list ordering, no dict iteration.
>
> Verification rule: run the check **spaced in time**, not twice in a row. Both bugs survived a same-second double-check.

## 2.3 Tick model

`TICK_HOURS = 8` — three ticks per day. Each tick: the world rolls, then one queued action fires.

One tick a day was tried and reverted: it produces a briefing with a single roll in it. Three gives nine clock rolls, up to three action resolutions, and room for a raid.

## 2.4 Clock advance

```
d6 + expansive//3 + (watched ? -1 : +1) - disrupt_effect
  >= CLOCK_THRESHOLD (6)   → +1 segment
  >= DOUBLE_AT      (10)   → +2 segments
```

## 2.5 Action resolution — the core mechanic

An action checks its preconditions **when it executes, not when it was queued.**

```
drift = min(target.clock_now - target.clock_when_queued, DRIFT_CAP=2)
total = d6 - drift

1 in 4 when drift > 0  →  misfire   effect: none, coin: spent
total >= 4             →  ok        effect: full, coin: spent
total >= 2             →  partial   effect: half, coin: half refunded
otherwise              →  refund    effect: none, coin: returned
```

> ⚠️ **Drift and clock speed are the same dial.** Faster clocks mean more drift means every queued action goes stale. Tuning absence through clock speed necessarily breaks the queue. Learned the hard way in v0.3.

`DRIFT_CAP` exists because an uncapped penalty made success arithmetically impossible on a d6 — the queue scored 0 for 5 and could never have scored anything else.

## 2.6 Action catalogue

| kind | cost | hands | effect | duration |
|---|---|---|---|---|
| `disrupt` | 60 | 2 | −3 to a front's clock rolls | 12 ticks |
| `fortify` | 50 | 2 | +3 to the bar a raid must clear | 12 ticks |
| `trade` | 20 | 1 | coin += openness × 12 | instant |
| `scout` | 30 | 1 | reveals a front's true clock as a `known` fact | instant |
| `invest` | 40 | 1 | +hands and +coin production | 15 ticks |

## 2.7 The three absence penalties

They must all be present. Individually none is sufficient.

1. **The queue drains.** 5 slots, 3 fire per day — about two days of proxy.
2. **Revenue stops.** `COIN_PER_TICK` accrues only while the queue is non-empty. A holding nobody is running does not earn. *(Without this gate, passive income handed the absentee 232 coin for doing nothing.)*
3. **The watch lapses.** `WATCH_TICKS = 9` — eyes stay posted three days past your last order, then go home. This was the single change that took the build from 4/5 to 5/5.

## 2.8 Fog of war

Four visibility values, lifted from SEREN's `facts.jsonl` spec:

| value | the world | the player |
|---|---|---|
| `true` | it is so | has not learned it |
| `known` | it is so | knows it |
| `suspected` | it is so | suspects, unconfirmed |
| `false` | it is **not** so | believes it anyway |

**`false` is the one the design exists to keep.** A player confidently wrong is the most playable state available, and it is unrecoverable if nobody writes it down.

`render.py` emits `known`, `suspected` and `false` **undifferentiated**, and never emits `true`. If truth leaks into the sidebar, fog is decoration.

> Not inherited from SEREN: the typed roll vocabulary (8+ declared shapes, `ref` chains, 313 entries of regression data) and session numbering. We have one roll type, so there is nothing to extend; and every row carries a real UTC timestamp, which closes the `s`-field gap SEREN's own spec flags as unresolved.

## 2.9 Fitness criteria

A build ships only when `bench.py` returns 5/5 across ≥8 seeds.

| # | Criterion | Target |
|---|---|---|
| 1 | Differentiation | attentive > erratic > absentee, gap ≥ 150 |
| 2 | Attention pays | attentive life ≥ 1.6× absentee |
| 3 | Outcome spread | no single outcome > 55% |
| 4 | Living economy | attentive solvent, never broke > 2 days |
| 5 | Still loseable | attentive loses a front in ≥ 70% of seeds |

> Criterion 2 was originally an absolute (`absentee ≤ 8 days`). It was rewritten as a ratio because the absolute could only be satisfied by clock speeds that break the queue. **A test satisfiable only by breaking the design is a bad test.**

Current: **attentive 917 / erratic 386 / absentee 222**, lives 17.0 / 13.8 / 8.0 days. Reproducible.

## 2.10 Interfaces

- `/elsewhere [orders]` — the play command. Ticks, narrates, republishes, takes orders.
- `python engine.py new|watch|queue|tick|status`
- `python sim.py [strategy] [days]` · `python bench.py [seeds]` · `python report.py`

## 2.11 Next

1. **Chained actions** — slot 4 declares it needs slot 2 to have landed. Makes sequencing a puzzle and gives drift a second-order cost.
2. **Scheduled task** — ticks the world and messages the operator when the queue empties. No server; Claude Code's own scheduler.
3. **`fortify` is under-picked** — the planner only buys it reactively after a raid. Either the AI needs foresight or the action needs a second use.
4. **Disasters** that change production math rather than resetting numbers.
5. **The genie** — grants the literal request, rolls on an interpretation table.

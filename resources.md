# Resources

Everything in this project, what it does, and why it exists.

---

## Play

| file | what it is |
|---|---|
| [`.claude/commands/elsewhere.md`](.claude/commands/elsewhere.md) | The `/elsewhere` slash command. Ticks the world, narrates the briefing, takes orders, renders and publishes the board. Ships inside the repo so cloning installs it. |
| [`state.json`](state.json) | Your live world. Created on first run. Holds the seed, the factions, the ledger, your beliefs, the queue and every active effect. |
| [`elsewhere-board.html`](elsewhere-board.html) | The board. Rendered fresh each turn. Double-clickable, or published as a live Artifact pane. |
| [`story.md`](story.md) | The chronicle, written by the narrator when a world ends. Read into the board as a modal. |
| `worlds/` | Archived worlds, one JSON per finished game. Nothing is ever lost. |

---

## The engine

### [`engine.py`](engine.py) — truth

Every outcome in the game is decided here. Nothing else is allowed to decide anything.

| what | how |
|---|---|
| **Per-tick RNG** | `sha256(f"{seed}:{tick}")`. Seed and absolute tick, nothing else. No clock, no ordering, no `hash()`. |
| **Clock advance** | `d6 + expansive//3 + (watched ? −1 : +1) − disrupt` against 6, doubling at 10. |
| **Order resolution** | `d6 − drift`, capped. 4+ lands, 2–3 part-lands, below is called off, and 1-in-4 misfires when the world has moved. |
| **Raids** | Gated on aggression, scaled to the size of your purse. A fat strongbox is a bigger target. |
| **Interest** | 10 / 15 / 25 / 40% compounding per consecutive unspent day. Requires a non-empty queue — a holding nobody runs earns nothing. |
| **Mega projects** | `2d6 + stake − 2×drift` against 9. Stake buys odds, effect size, and a better class of failure. Ten-entry mutation table. |
| **Improvise** | The freeform path. Takes a cost, a target and a list of effects; modifies the roll by the target's own openness; resolves on the same ladder as everything else. |
| **Settling** | The first neighbour to complete their agenda ends the world. |

CLI: `new` · `watch` · `queue` · `improvise` · `tick` · `ff` · `horizon` · `options` · `status`

### [`render.py`](render.py) — the board

Writes `elsewhere-board.html`. **Content only, never colour** — every visual value is
a CSS token, so the design can be replaced without touching this file.

Enforces the fog contract:

- never emits a `true` fact
- renders `known`, `suspected` and `false` **identically**
- withholds ledger clock rows for neighbours you weren't watching
- an unwatched clock renders as fog, never as zero
- `horizon()` estimates require a clock you actually have

Also holds the text-size control (one point per click, unbounded, remembered
per browser), the hour-of-the-world logic (the sky follows the *world's* time in ET,
not the reader's), the guide drawer, the NOW panel, and the epilogue modal.

### [`epilogue.py`](epilogue.py) — the ending

Runs once, when the world settles. Lifts the fog on everything the player never saw,
scores the run, and writes `epilogue.html` — the badge and the chronicle, side by side.
It reads the ledger; it does not decide anything.

---

## Testing

| file | what it does |
|---|---|
| [`sim.py`](sim.py) | Scripted players — **attentive**, **hoarder**, **erratic**, **absentee** — so a fortnight of play runs in a second. Deterministic: player RNG is `crc32(strategy) ^ seed`. |
| [`bench.py`](bench.py) | Six fitness criteria across N seeds. Exits non-zero on failure, so it works in CI. |

The six criteria:

1. **Differentiation** — attentive beats every other strategy by ≥150
2. **Attention pays** — attentive lives ≥1.6× longer than absentee
3. **Outcome spread** — no single order outcome exceeds 55%
4. **Living economy** — attentive ends solvent, never broke more than two days
5. **Still loseable** — attentive loses a neighbour in at least 70% of seeds
6. **The dare is real** — hoarding loses on average but wins 15–45% of seeds

```bash
python bench.py 12
```

---

## Documents

| file | what it is |
|---|---|
| [`index.html`](index.html) | The landing page, served at [https://netmobster.github.io/elsewhere-idle-cc/](https://netmobster.github.io/elsewhere-idle-cc/). Self-contained, no build step. |
| [`README.md`](README.md) | The repo front page. Pitch, mechanics, the four surfaces, install, balance, lineage. |
| [`PRD-TRD.md`](PRD-TRD.md) | Product and technical spec. The formulas, the contracts, the criteria, and the traps. |
| [`NOTES.md`](NOTES.md) | The build log. Every iteration, including the ones that made things worse. |
| [`installer.md`](installer.md) | Setup, full CLI reference, troubleshooting. |
| [`llms.txt`](llms.txt) | Machine-readable summary for agents. |
| [`aboutjay.md`](aboutjay.md) | Who made this, and why. |
| [`LICENSE`](LICENSE) | Apache 2.0. |

---

## Worth reading in NOTES.md

The build log is deliberately honest. The entries that matter:

- **v0.1** — the baseline where *doing nothing was the best strategy*, because orders
  had no effect on the world.
- **v0.3** — tuning absence via clock speed broke the queue. Drift is derived from
  clock speed; they are the same dial.
- **v0.6 and v0.8** — two determinism bugs. The second invalidated six iterations of
  balance tuning, because the bench returned different verdicts for identical code.
- **v1.0** — a fog leak reintroduced in new code one day after the same bug class was
  fixed and documented.

---

## Lineage

**[SEREN](https://seren-dm.lovable.app/)** — the engine, the ledger and the roll
system descend from it. Its own line is *"files and the shell keep the numbers
honest."*

| from SEREN | what it became |
|---|---|
| *"the model narrates a result it did not choose"* | the single load-bearing rule |
| fronts and clocks | *"advances when the party is elsewhere"* → *"advances while you sleep"* |
| append-only ledger, arithmetic showing | every row clickable, every number checkable |
| `facts.jsonl` and four visibility values | SEREN specced them and never wired a consumer. This is the consumer. |

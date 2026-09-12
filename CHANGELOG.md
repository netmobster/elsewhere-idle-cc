# Changelog

What changed, when, and what broke. The full engineering account of the pre-release
iterations — including the ones that made the game worse — lives in
[`NOTES.md`](NOTES.md). This file is the shipping record.

Dates are the author's local time.

---

## v1.0.3 — first install test — 2026-09-11

The first time the game was installed by someone who wasn't the person who wrote it.
Everything worked. Two things were still wrong.

### Added

- **Text size control on the board.** A `−` `14` `+` group beside the hour picker.
  One point per click, unbounded upward, floored at 8. `+` and `-` work as keys,
  clicking the number resets, and the choice is remembered per browser.

  Every size on the board is a hardcoded px value, so raising `body` font-size
  cascades to nothing. It scales the root instead, which takes the rules, gaps and
  segment bars with it — on a board made mostly of alignment, that is what "bigger"
  has to mean.

- **A first-run branch in the slash command.** With no `state.json` there is no world
  to tick and no ledger to narrate. Nothing previously said to run `engine.py new`,
  so a fresh install would tick an empty world.

### Fixed

- **The slash command hardcoded the author's absolute path.** `.claude/commands/elsewhere.md`
  opened with `Game lives at C:/Users/Lenovo/OneDrive/Desktop/PROJECTS/Elsewhere/`.
  That directory exists on exactly one machine, so the first thing every clone did was
  point Claude Code at a path that wasn't there. It now locates the repo root by
  finding `engine.py`, and falls back to `python3`.

  Caught by reading the command as a stranger would, minutes before the first install
  test. It was the one file vendored into the repo without being re-read in its new
  context.

- **Shadowed commands are now documented.** A global `~/.claude/commands/elsewhere.md`
  left over from an earlier copy takes precedence over the one in the repo, so playing
  a fresh clone silently ticks the old world instead. `installer.md` now says what to
  do if you have both.

### Changed

- The landing page links to the source. It previously had two outbound links — the
  repo root and the licence — so a reader who wanted to see `engine.py` had nowhere to
  go. Adds a **The source** section covering every file, turns the install file list
  into real links, and adds a nav entry.
- `README.md`, `llms.txt`, `resources.md` and `installer.md` link back to the site,
  which none of them did.
- Two numbers left stale by the v1.0.2 rebalance: the landing page still claimed the
  hoarder *"beats careful play two times in five"* (it is one in four), and
  `epilogue.py` was missing from the install file list entirely.

---

## v1.0.2 — first public release — 2026-09-11

The repo goes public. The last check before pushing was `bench.py` run from a clean
copy of exactly the files about to ship, and it failed 3 of 6.

### Fixed

- **A gameplay fix had silently invalidated the balance.** The world used to settle
  only when *all three* neighbours completed their agendas, which meant a world the
  player had already lost kept running and the epilogue never fired. The rule became
  `any()` — if they won, you lost.

  That is the right rule. It is also a balance change, and it was not treated as one:

  | | `all()` | `any()` |
  |---|---|---|
  | world length | 17.5 d | 6.2 d |
  | attentive score | 1200 | 223 |
  | hoarder beats careful play | 42% | 67% |

  Settling on the first completed agenda cut every world to a third of its length and
  handed the game to the hoarder, because compounding interest does not care how short
  the game is but spending does.

  Fixed by slowing the clocks and nothing else: `CLOCK_THRESHOLD` 5 → 6,
  `DOUBLE_AT` 8 → 10.

  ```
  attentive    941   14.5 days   lost a front in 10 of 12
  hoarder      644    8.3 days   beat careful play in 3 of 12
  erratic      283    6.6 days
  absentee     274    6.2 days
  PASS 6/6
  ```

- **The epilogue modal now fires on its own** when a world settles, and the score ring
  animates to the final number instead of sitting at zero.

### Changed

- **Fitness criterion 5 was restated, and it deserves scrutiny.** It read *"attentive
  still loses ≥ 1 front"* as a mean across seeds. Under the `any()` settle rule a
  settled world has exactly **one** finished agenda, so the mean is pinned at a ceiling
  of 1.0 — and requiring a mean of ≥ 1 therefore requires that the attentive player
  *never* hold the world open. That is the opposite of what the criterion protected.

  It is now a rate: **a front is lost in ≥ 70% of seeds** (currently 83%). The rare
  world where careful play holds all three at bay is a real outcome and should be
  reachable.

  Moving a goalpost to make a test pass is how you get a green suite and a broken game.
  The distinction: the metric measured a quantity whose range the rule change had
  collapsed. The intent did not move.

- Four documents were publishing the old balance numbers, and `PRD-TRD.md` still
  described the `all()` rule in prose. All corrected.

### Added

- `index.html` — the landing page, served at
  [netmobster.github.io/elsewhere-idle-cc](https://netmobster.github.io/elsewhere-idle-cc/).
- `README.md`, `installer.md`, `resources.md`, `llms.txt`, `aboutjay.md`.
- Licence: **Apache 2.0**.

---

## v1.0.1 and earlier — pre-release

Not published. Kept here only as a pointer, because the failures are the useful part
and they are written up properly in [`NOTES.md`](NOTES.md):

| | |
|---|---|
| **v0.1** | The baseline where *doing nothing was the best strategy*, because orders had no effect on the world. |
| **v0.3** | Tuning absence via clock speed broke the queue. Drift is derived from clock speed; they are the same dial. |
| **v0.6** | ⛔ `sim.py` seeded player RNG from `hash()`. Python salts string hashing per process, so the bench was not reproducible. |
| **v0.8** | ⛔⛔ The world RNG was seeded from wall-clock time. Two runs three seconds apart gave different verdicts for identical code. **This invalidated six iterations of balance tuning.** |
| **v0.9** | Mega projects, the ten-entry mutation table, compounding interest, and the hoarder as a real temptation rather than a trap. |
| **v1.0** | A fog leak reintroduced in new code one day after the same bug class was fixed and documented. The fix produced an unplanned feature: scouting now buys a countdown. |
| **v1.0.1** | Two interface bugs, both self-inflicted. A modal that could not be dismissed to type, and an epilogue that never fired. |

---

*Two determinism bugs, two fog leaks, one balance regression, and one hardcoded path.
All of them are in here on purpose.*

# Changelog

What changed, when, and what broke. The full engineering account of the pre-release
iterations — including the ones that made the game worse — lives in
[`NOTES.md`](NOTES.md). This file is the shipping record.

Dates are the author's local time.

---

## v1.1.1 — one argument, everywhere — 2026-09-12

No code. The project had been describing itself by its *schedule* on every surface —
"an idle RPG that runs in real time whether you are there or not" — which says when it
happens and nothing about what it is.

The actual thesis, arrived at while writing about it rather than while building it:

> **Unbounded input, entering a bounded deterministic reality engine — and an AI
> beside you that has to narrate the result and live with it exactly like you do.**

That is the part nobody else is doing. The schedule is the hook; this is the design.
It now leads the README, the landing page, `llms.txt`, the demo's social card and the
repo description, at three lengths so each surface gets one that fits.

The consequence worth stating, and the reason "beside you" is not decoration: the
model is bound by everything the player is. It does not know the roll before it
writes. It has to make sense of an outcome it would not have chosen. It cannot revise,
because the ledger only appends. **And it is bound by its own translation** — it
priced the scheme, so it then has to narrate whatever that price produced, generous or
cruel.

### Changed

- **The four surfaces: "the modal is options" → "the modal is orientation."** Options
  are not a menu, they are a map — four priced choices show what the world takes
  seriously and roughly what it costs, and *then* a sentence can be aimed at it. The
  freeform layer does not escape the modal; the modal is what makes freeform usable.
  Options first, intent second. Corrected in the README and on the site.

---

## v1.1.0 — the chaos goblin release — 2026-09-12

The second playtest was played entirely sideways — a coronation feast thrown to
make babies, a pantsless dawn duel against raiders, and a seventy-two hour
municipal mandate on erections and quilts. It scored **1019 of 1000**, and it broke
four things that playing straight would never have touched.

### Fixed — engine

- **`queue` destroyed a queued mega's stake.** The stake for a mega is the entire
  purse *at queue time*. `queue` cleared the list and rebuilt it, re-pricing the mega
  from whatever coin remained — so adding one 20-coin trade alongside a 152-coin mega
  quietly turned it into a 20-coin mega. There was no way to append without paying
  that. **New command: `add`**, which appends. `queue` still replaces.

- **`improvise` always jumped the queue.** Every improvised order inserted at position
  0, which is written down nowhere and silently reorders everything the player just
  queued. It now appends like every other order. Pass `"next": true` to jump.

- **Improvised `trade` and `scout` grants did nothing.** Only `disrupt`, `fortify` and
  `invest` are ever read back out of `s["effects"]`. Granting a `trade` or a `scout`
  appended an effect nothing consumes, so the order rolled, landed, reported success
  and had no result. Both now resolve immediately, exactly as the menu versions do —
  which also means *"send somebody to go and look"* is improvisable at all for the
  first time.

- **Nothing could improvise a net gain of people.** There was no `hands` grant. A
  feast thrown to make babies is the most obvious improvised order in the game and it
  had no mechanism behind it; it had to be proxied with `invest`. `hands` is now a
  grant kind, capped at 10.

### Fixed — the chronicle

- **The chronicle renderer understood only headings, rules, bold and italic.** Table
  rows and blockquote lines are ordinary non-empty lines, so they were swept into the
  current paragraph and joined with spaces — a markdown table came out as one long
  smear of pipes, and a blockquote came out as a literal `&gt;`.

  This was not cosmetic. The chronicle quotes the player's own orders back at them,
  which is the best thing in the file, and every one of those quotes was rendering
  broken. `md_to_html` now handles tables, blockquotes and lists, and they are styled
  to match the board rather than to browser defaults. Wide tables scroll inside
  themselves instead of pushing the modal sideways.

### Changed

- **The modal is now every response, not every turn.** A briefing that ends in prose
  and waits for typed orders means the player has to type the word "modal" to get the
  interface they asked for. It is now the rule at the top of the command file, with
  the cases enumerated, and the "Hold — I want to type" escape hatch has to bounce
  straight back into a picker rather than answering and waiting.

- **A one-time welcome on first run** — read the guide, then three protips: be a chaos
  gremlin and ignore the menu, you will lose and that is the point, and the clock is a
  dial so real-time and one-sitting are both the real game.

- **First run no longer ticks a world with zero ticks.** It printed `{"ticks": 0}` as
  the first thing a new player ever saw, which reads like a failure.

- **The improvise contract is documented** in the command file — every field, every
  grant kind, and which ones resolve immediately.

- **The sample playthrough on the README and the site is now Fen's Reach** — the
  pantsless dawn duel and the quilt mandate, replacing the missionaries. It is a
  better demonstration of the same claim: the engine does not know what you are
  doing and rolls anyway.

- **`demo.html` — a complete played game, scene by scene.** Eight in-world days of
  Fen's Reach with the chat pane, the board and the picker in frame together, every
  player line verbatim and every roll taken from the ledger. It is the fastest way to
  understand what the game actually is, and it does the job no amount of prose was
  doing. Shipped as its own page rather than inlined: it redefines `--bg`, `--panel`,
  `--ink` and `--ember` on `:root`, which are the landing page's own tokens.

- **A real mobile nav.** The bar kept every section link, GitHub and the four-dot
  hour picker in one `nowrap` row, which on a phone collapsed into an unreadable
  scrum — and the section links were hidden outright below 760px, so the played game
  was unreachable from a phone. There is now a hamburger and a drawer: all seven
  links, the one worth tapping in ember at the top, and the hour picker inside it.
  Closes on link tap, Escape, tapping outside, and on resize past the breakpoint.
  The bar also goes solid on mobile — the blurred translucent version read as a
  floating box over the hero glow, with a hard vertical seam where the glow ended.

- **Social cards and a favicon.** The page had a description and nothing else, so a
  shared link rendered as bare text everywhere except Substack. Adds Open Graph and
  Twitter tags, a 1200×630 card, and the Elsewhere mark as an SVG favicon with PNG
  fallbacks.

### Known, not fixed

Balance observations from the same run, recorded rather than patched, because one
absurd playthrough is not a measurement:

- **Openness dominates the improvise roll.** +3 from an open front against −1 for
  committing your entire population. A perilous order rolled a 2 and came home
  profitable with no casualties. *Perilous stopped meaning perilous.*
- **Trade is roughly 3.6× with no downside** — the dominant line once you have one
  open neighbour.
- **Watch is a free 2-point swing**, and stacked with a disrupt it drives a front's
  rate to literal zero. A front rolled a 6 and still failed to advance.
- **An empty queue earns no interest, and nothing says so.** After spending everything
  on a mega you can enter a soft-lock with no warning.

### Verified

`python bench.py 12` → **PASS 6/6**, unchanged. `sim.py` does not improvise, so the
engine fixes do not touch the balance harness — which is itself worth noting as a
gap: the four bugs above were all in code the bench never exercises.

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

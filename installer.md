# Installing Elsewhere

[Site](https://netmobster.github.io/elsewhere-idle-cc/) · [Repo](https://github.com/netmobster/elsewhere-idle-cc)

**Short version:** clone it, open Claude Code, type `/elsewhere`. That's it.

There is no installer because there is nothing to install. The game is six Python
files with no dependencies, and Claude Code builds everything else on first run.

---

## Requirements

| | |
|---|---|
| **Python** | 3.9 or newer. `zoneinfo` is used for the world clock; on 3.8 it falls back to UTC. |
| **Claude Code** | Any recent version. The game is a slash command plus a Python engine. |
| **Packages** | None. Standard library only — `json`, `random`, `hashlib`, `datetime`, `pathlib`, `html`. |
| **A server** | No. |
| **An account** | No. Worlds live in a file on your disk. |

---

## Install

```bash
git clone https://github.com/netmobster/elsewhere-idle-cc
cd elsewhere-idle-cc
```

Open Claude Code in that directory and type:

```
/elsewhere
```

The `/elsewhere` command ships in `.claude/commands/` inside the repo, so cloning
installs it. First run rolls a world, renders the board and takes your orders.

**If `/elsewhere` doesn't appear**, Claude Code loads its command list at startup —
restart the session and it will be there.

---

## Where things live

```
elsewhere-idle-cc/
├── .claude/commands/elsewhere.md   the play command
├── engine.py                       truth
├── render.py                       the board
├── epilogue.py                     the ending
├── sim.py                          fast-forward, for testing
├── bench.py                        the balance harness
├── state.json                      your live world  (created on first run)
├── story.md                        the chronicle     (written when a world ends)
├── elsewhere-board.html            the board         (rendered each turn)
├── epilogue.html                   the ending        (written when a world ends)
└── worlds/                         archived worlds   (one JSON per finished game)
```

`state.json`, `story.md`, `elsewhere-board.html` and `worlds/` are all created for
you. Nothing else is generated.

---

## Seeing the board

**Every plan:** `elsewhere-board.html` is a normal HTML file. Double-click it, or
open it from the browser. It refreshes each time the game renders — reload to see
the new state.

**With Claude Code Artifacts:** the board publishes to a live pane beside the chat
that updates as you play, which is considerably nicer. Artifacts are currently a
Team/Enterprise feature. **The game does not require them.**

---

## Playing without the slash command

Everything is a plain CLI if you'd rather drive it yourself:

```bash
python engine.py new                  # roll a world
python engine.py watch "Long Hand"    # focus one neighbour
python engine.py watch general        # or watch all three from the hill
python engine.py queue "Slow them|long-hand|disrupt" "Trade|long-hand|trade"
python engine.py ff 8h                # fast-forward (h = hours, bare = days)
python engine.py tick                 # advance to now, honestly
python engine.py horizon              # what is coming, and when
python engine.py status               # the whole state as JSON
python render.py                      # rebuild the board
```

Order kinds: `disrupt` 60 · `fortify` 50 · `trade` 20 · `scout` 30 · `invest` 40 ·
`mega` (costs everything, minimum 150).

The chat layer is what makes it a game rather than a spreadsheet, but the engine
runs perfectly well without it.

---

## Testing and balance

```bash
python bench.py 12       # four strategies, twelve seeds, six criteria
python sim.py            # run all strategies once, quickly
python sim.py attentive 21
```

`bench.py` exits non-zero on a failing build, so it works in CI.

---

## Starting over

```bash
rm state.json story.md
python engine.py new
```

Finished worlds are already archived in `worlds/`, so nothing is lost.

---

## Troubleshooting

**"The board looks stale."** Run `python render.py`. The board is rendered, not live —
it only changes when the game does.

**"Nothing happened when I ticked."** Time is real. `engine.py tick` advances to *now*,
so if less than eight hours have passed there is nothing to advance. Use
`ff 8h` while testing.

**"My order was called off."** That is the game. An order resolves against the world
as it is when it fires, not when you wrote it. Click the ledger row for the arithmetic.

**"Everything is `?/10`."** You are watching from the hill, or your lookout went home.
Eyes lapse three days after your last order.

# 🕯️ Elsewhere

**An idle RPG that runs in Claude Code, in real time, whether you are there or not.**

### 🌐 [https://netmobster.github.io/elsewhere-idle-cc/](https://netmobster.github.io/elsewhere-idle-cc/)

**[▶ Watch a complete game, scene by scene](https://netmobster.github.io/elsewhere-idle-cc/demo.html)** — eight
in-world days, the chat and the board side by side. Every line the player typed is
verbatim; every roll comes from the engine's ledger.

Two minutes a day. Three neighbours who each want something. One set of eyes, and
three directions to point it.

You will lose. The interesting part is finding out *how* — because the story of
what happened while you were looking the other way is written for you at the end.

```
🕯️  OSSEN'S REACH — the dawn watch          124 coin · 10 hands · queue 0/5

    THE SUNDERED CHARTER   builders   ████████░░  8/10   EYES ON
    THE LONG HAND          diggers    ░░░░░░░░░░    ?     no eyes
    THE NINTH WATCH        raiders    ░░░░░░░░░░    ?     no eyes

    WHAT IS COMING
    The Sundered Charter is about a day away.
    They want to raise a second wall across the reach.
```

Those `░░░` are not zero. **They are unknown.** That distinction is the whole game.

---

## The one-minute version

You run a small holding. Three neighbours are each working toward something that
will change the world permanently when they finish. Each has a bar of ten segments.

**The bars fill in real time.** Not while the app is open — *in real time.* Close the
laptop, come back tomorrow, and two days of world have happened without you.

You have **one lookout**. Point it at a neighbour and you see their real number, they
work slower, and they will not rob you. The other two go dark. Point it at all three
from the hill instead and you get a vague band on everyone and no protection at all.

Then you leave **standing orders** — up to five, one fires every eight hours — and
you go away.

The catch, and it is the entire design:

> **An order happens when it comes up, not when you wrote it.**

You paid for a shipment from a dock you never finished buying. The dock changed hands
on Tuesday. Your grain went to the village at whatever they'd pay. They were delighted.

---

## But the real reason to play

The five orders are a **shortcut, not the rules**.

You can type anything you can describe, and it becomes a real order with a real
price, a real roll, and real consequences. Here is an actual playthrough — *Fen's
Reach*, eight days, seed `691420631`.

Day two. The lord surveyed his hungover population and issued this:

> *"the hands that can move proceed to walk towards the Iron Hand, pantsless and
> erect, ready to duel and duo with their, erm, mighty swords"*

They rolled a **2**. On a perilous order. That is the number where men do not come
home.

Every one of them came home. They came home **nineteen coin richer**.

The Iron Hand were raiders working toward a coast road that would belong to nobody
but them — and they happened to roll maximum openness in that world. Openness turns
out to mean that when a column of naked hungover men walks uphill at you at dawn with
their swords out, you do not kill them. You laugh. Then you do business. Then you
stop sending crews out on the dawn shift, because you cannot stop laughing.

That was **disrupt 2 on the coast road, bought with nothing but dignity.**

Later, the same lord committed the entire population to a single industry for
seventy-two hours:

> *"the entire reach is shocked by the advancement in erect quilt technology and the
> village puts their hands to both having erections and making quilts"*

```
d6 6   + receptive 3   − overreach 1   =  8      needed 8
```

Eight hands of ten. The engine docked a point for overreach, because committing your
whole population to one trade is a stretch even when the trade is that one. It landed
**on the nose**: 135 coin, the single most profitable act in the reach's history.

Nobody designed that move. Nobody wrote a rule for quilts. **It was in the numbers.**

### And then the part you did not see

The Iron Hand advanced **nine of their ten segments while nobody was watching them.**
The ledger is brutally consistent about it — the road stood still on exactly the three
ticks somebody had eyes on it, and moved on every other one.

The disrupt expired. The lord was offered a fresh one for 60 coin and spent it on the
shaft instead, where it misfired and bought nothing. It is the only order in eight days
that returned literally nothing, and it is the one that cost him the world.

Final score **1019**. Two of three neighbours denied, an altar to the Erect Champions
tended by priests nobody asked, and quilts on the saddle of every raider on the coast
road — a road he no longer owns, closed to everybody on earth except the people who
sold them the blankets.

> *It is just that somewhere out past the waystations, a faction of raiders finished
> a job while the entire population of Fen's Reach was extremely busy, for seventy-two
> consecutive hours, with erections and quilts.*

That paragraph is from the chronicle the game wrote itself, from the ledger, at the end.

---

## Four surfaces, four jobs

| | does | never does |
|---|---|---|
| **The board** | State. Exactly what is true, rolled by the engine, arithmetic showing. | Interpret. Advise. Invent. |
| **The chat** | Intelligence. Reads the ledger and tells you what it means. | Decide outcomes. Contradict a roll. |
| **The modal** | Options. The turn in three clicks with real costs attached. | Be the only way to play. |
| **Freeform** | Anything not on the menu. You ask; the world answers. | Break the engine. |

The first three are a UI. **The fourth is why this needs an agent.**

---

## How it actually works

**Python rules. The model narrates. They are not the same job and they never swap.**

Every outcome in the game — every clock tick, every raid, every order, every absurd
improvised scheme — is decided by `engine.py` with a seeded RNG and written to an
append-only ledger with its arithmetic showing. Click any row on the board and you
get *what you ordered · what had changed · what it rolled · what that means · net cost.*

The model's job is to read that ledger and tell you what it means, in the register
*you* brought to it. It translates your chaos into costs and modifiers. It does not
get a vote on whether your chaos worked.

> **When a roll surprises the narrator, that surprise is genuine — and it is the
> strongest evidence you have that the dice are real.**
>
> A narrator that decided outcomes could not be surprised, and you would be able
> to tell.

Determinism is enforced, not hoped for: per-tick RNG derives from `(seed, tick)` and
nothing else. No clock, no dict ordering, no wall time. Same seed plus same elapsed
time reproduces a world exactly, on any machine, forever.

*(It took two separate bugs to get that right. Both are documented in `NOTES.md`,
including the one where the bench returned different verdicts for identical code and
invalidated six iterations of tuning. The build log is honest about what broke.)*

---

## Fog is not decoration

Four visibility values, borrowed wholesale from [SEREN](https://seren-dm.lovable.app/):

| | the world | you |
|---|---|---|
| `true` | it is so | **have not learned it** |
| `known` | it is so | know it |
| `suspected` | it is so | suspect, unconfirmed |
| `false` | it is **not** so | believe it anyway |

`false` is the one the design exists to keep. **A player who is confidently wrong is
the most playable state in the game**, and the board will never tell you which of
your beliefs is the wrong one.

The renderer never emits a `true` fact. Ledger rows for neighbours you weren't
watching are withheld. An unwatched bar shows fog, never a number. If any of that
leaks, the fog is just a graphic.

---

## And then you find out

When a neighbour completes their agenda, the world settles and **the fog lifts.**

The epilogue fires automatically: a badge with your score, and a **chronicle** —
a real narrative history of your holding, written from the ledger, including every
single thing you never saw.

> *It is not a defeat, exactly. Nobody died. Not one hand was lost in eight days,
> and two of those days involved naked men walking at raiders on purpose.*

That paragraph is true, and the ledger can prove every clause of it. The chronicle
is written from the rows, not from memory — including the nine segments the Iron
Hand gained on the exact ticks nobody was looking.

This is the payoff, and it is why losing feels good.

---

## Install

There is no installer. **Clone it and ask Claude Code to play.**

```bash
git clone https://github.com/netmobster/elsewhere-idle-cc
cd elsewhere-idle-cc
```

Then, in Claude Code:

```
/elsewhere
```

It rolls you a world, renders the board, and takes your first orders. The `/elsewhere`
command ships inside the repo, so cloning installs it.

**Requirements:** Python 3.9+. No packages, no build step, no server, no account.

**The board is a plain HTML file on disk** — `elsewhere-board.html`, double-clickable.
If your plan supports Claude Code Artifacts it'll publish to a live pane that updates
each turn, which is nicer. That's an upgrade, not a requirement.

---

## What's in here

| file | what it is |
|---|---|
| [`engine.py`](engine.py) | Truth. Every outcome in the game is decided here. |
| [`render.py`](render.py) | The board. Renders your file on the world, never the world. |
| [`epilogue.py`](epilogue.py) | The ending. Lifts the fog, scores the world, writes the badge. |
| [`sim.py`](sim.py) | Fast-forward. Scripted players so a fortnight runs in a second. |
| [`bench.py`](bench.py) | The judge. Six fitness criteria across twelve seeds. |
| [`PRD-TRD.md`](PRD-TRD.md) | Design and technical spec. |
| [`NOTES.md`](NOTES.md) | The build log, including everything that broke. |
| [`CHANGELOG.md`](CHANGELOG.md) | The shipping record, release by release. |
| [`demo.html`](demo.html) | A complete played game, scene by scene. |
| [`resources.md`](resources.md) | Everything, linked and explained. |
| [`installer.md`](installer.md) | The long-form setup, if the two lines above aren't enough. |
| [`aboutjay.md`](aboutjay.md) | Who made this and why. |

---

## Is it balanced?

`python bench.py 12` runs four strategies across twelve worlds and reports against
six criteria. Current:

```
attentive    941   14.5 days   lost a front in 10 of 12 worlds
hoarder      644    8.3 days   beat careful play in 3 of 12
erratic      283    6.6 days
absentee     274    6.2 days

PASS 6/6
```

**Attention is worth about three and a half times an absentee's score, and more than
twice their lifespan.** But it does not make you safe: the attentive player still
loses a neighbour in five worlds out of six. A game the attentive player always won
would be as broken as one they always lost.

The hoarder is the interesting one. It loses on average and **beats careful play one
time in four.** That's the gamble, and it's deliberate — sitting on a fat strongbox
makes you a bigger target, and sometimes you get away with it anyway.

*Those numbers moved recently, and it is worth saying why.* The world used to end
only when **all three** neighbours finished. It now ends when **the first one does** —
because if they won, you lost, and a finished world that keeps running is not a
finished world. That single change cut every world from ~17 days to ~6 and handed the
game to the hoarder, since compounding interest does not care how short the game is
but spending does. The clocks were slowed to put the long world back. `NOTES.md` has
the full account.

---

## Genesis

The engine, the ledger and the roll system descend from
**[SEREN](https://seren-dm.lovable.app/)** — a single-player AI dungeon master whose
own description is *"files and the shell keep the numbers honest."*

What came across:

| from SEREN | what it became here |
|---|---|
| *"the model narrates a result it did not choose"* | the single load-bearing rule |
| fronts and clocks | *"advances when the party is elsewhere"* → *"advances while you sleep"* |
| an append-only ledger, arithmetic showing | every row clickable, every number checkable |
| four visibility values | SEREN specced them and never wired a consumer. **This is the consumer.** |

SEREN is the immersive one — an evening, a campaign, a world you live in.
Elsewhere is pick up and play. Same engineering honesty, different cadence.

---

## Licence

[Apache 2.0](LICENSE). Take it, fork it, build a different world with it.

---

**More:** [echofiles.substack.com](https://echofiles.substack.com) — where the
playthroughs get written up, including the one where a municipal quilt mandate
outperformed every sensible decision in the game.

*Built in Claude Code, over about a week, mostly at night.
The worst decisions are all documented.*

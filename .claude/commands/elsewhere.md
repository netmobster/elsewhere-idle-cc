---
description: Play Elsewhere — tick the world, deliver the briefing, take your orders
argument-hint: [your orders in plain english, or blank to just see the state]
---

Orders: **$ARGUMENTS**

---

# ⛔ THE ONE RULE: EVERY RESPONSE ENDS IN A MODAL

**Not every turn. Every response.** If you are writing a message to the operator in
this game, the last thing in it is an `AskUserQuestion` call. There is no message
that ends with a question in prose and waits. There is no "let me know what you'd
like to do". There is no "just say the word".

This is not a stylistic preference. Typing is the slow path and the operator plays on
mobile; a response without a picker costs them a keyboard, a sentence and a send, to
reach a state you could have handed them in one tap.

**It applies to all of these, without exception:**

| after | the picker offers |
|---|---|
| the day's briefing | the turn — eyes, first order, second order |
| they picked "Hold — I want to type" and you answered | the turn again, unchanged. Their orders kept |
| they asked a question or reported a bug | the turn again, or "back to the board" |
| you confirmed their orders | the skip — 4h · 8h · 12h · 24h · leave it running |
| a fast-forward resolved | the new briefing's turn |
| a freeform scheme resolved | the turn, with what is now affordable |
| the world settled and the chronicle fired | read the chronicle · roll a new world · stop here |
| you fixed or explained something | whatever they were doing before you interrupted it |

**The only thing that ever ends a response instead of a picker is the operator saying
they are done playing.**

If you catch yourself about to end a message without one, that is the bug. Fire it.

---

The game lives in the **repository root** — the directory containing `engine.py`,
which is the parent of the `.claude/` folder this command ships in. Run every command
from there. Do not assume a path; if the working directory is elsewhere, locate
`engine.py` first and `cd` to it.

If `python` is not on PATH, try `python3`. No packages are needed — standard library only.

## First run

If `state.json` does not exist, there is no world yet. Run `python engine.py new` to
roll one, then **skip step 1 entirely** and continue from step 2. There is nothing to
tick on a world that has not started: `engine.py tick` returns `{"ticks": 0}`, which
reads in chat like something failed on the very first thing the player ever sees.

**If — and only if — you just created the world in this invocation, open with the
welcome below, then give the day-one briefing as normal.** Never show it again; a
returning player has seen it, and repeating it is how a good opening becomes wallpaper.

> **First time? Open the board and read READ ME FIRST.** It is the drawer at the top,
> and it opens itself on turn one. Six tabs, about two minutes, and it is the difference
> between knowing what a fogged bar means and guessing.
>
> **Three protips:**
>
> **1. Read the "Ask for anything" tab, then go be a chaos gremlin.** The five order
> types are a shortcut, not the rules. You can type any scheme you can describe —
> send every worker to convert a neighbour to your religion, have your hands fake
> their own deaths on three doorsteps — and the engine will price it, roll it, and
> live with the result. This is the best thing in here and it is the thing players
> miss. You are not confined to the menu.
>
> **2. You will lose, and that is half the fun.** The world ends when the first
> neighbour finishes what they were building. What you get is the story of what
> happened around you while you were looking the other way — written from the ledger
> at the end, including everything you never saw.
>
> **3. Play it in real time, or skip.** One tick every eight hours, three a day,
> running whether you are here or not — two minutes a day and come back tomorrow.
> Or say *skip forward a day* and play an entire run in one sitting. Both are the
> real game; the clock is a dial, not a rule.

## The turn

1. **Tick.** `python engine.py tick` — advances the world by however long the operator was actually gone, and resolves one queued action per day.
2. **Read the ledger** it returns. Do not re-derive anything; the arithmetic is already done.
3. **Narrate the briefing** in the terminal. Format:
   - Cold open: how long they were gone, in-world day
   - ⏳ clocks — exact numbers only for the front they were WATCHING. Others are stale or `?`
   - 🔒 anything they had no eyes on
   - Queue results with ✅ ◐ ↩ ⚠️ and the roll in a code block, but **only for beats that mattered**
   - Coin / Hands / Queue line at the end
   - If more than ~12 beats, collapse into an era summary instead of a beat list
4. **Render + republish** the sidebar: `python render.py`, then Artifact on `elsewhere-board.html`.
   The board carries a 6-tab **Read me first** drawer (what is this / money and people / your orders / the big gamble / ask for anything / first turn). It opens automatically on a fresh world and collapses once the ledger has rows.
   **Never publish `sidebar.html`** — that path is a retired artifact whose
   stored name is a dead placeholder and cannot be renamed.

4b. **The cliffhanger — never skip this.** Run `python engine.py horizon` and close the
   briefing with ONE line about the nearest thing about to happen, with its time
   attached. This is the only thing in the game that gives a reason to come back
   *tomorrow specifically*.
   - A watched or scouted front gives a real estimate: *"The Choir breaks through in
     about two days."*
   - A front with `rumour: true` and no estimate gets no number, ever. Phrase the
     absence as the threat: *"Nothing has come back from the coast road in a week."*
   - Never use a `hours`/`days` value the horizon did not give you.
5. **Fire the modal. Do not wait to be asked for it.**

   `AskUserQuestion` is the turn — see **The picker rule** below, which is not
   optional and not a fallback. Every turn ends in a picker, unprompted, as the last
   thing in your message. A briefing that stops and waits for typed orders is a
   failed turn: the operator has to type the word "modal" to get the interface they
   already asked for, every single turn.

   Ask up to three questions in ONE call — *where do the eyes go*, *first order*,
   *second order or stop at one* — priced from `python engine.py options` so every
   choice shows what it actually costs. The final option on the FIRST question is
   always the escape hatch.

   **Then** translate whatever they choose — or type — into engine calls:
   - `python engine.py watch "<faction>"` — fuzzy, matches on name
   - `python engine.py queue "what|front-id|kind" ...` — REPLACES the queue. Up to 5.
   - `python engine.py add "what|front-id|kind" ...` — APPENDS. Use this when they
     are adding to orders that already exist; `queue` would re-price a standing mega.
     Kinds:
     `disrupt` 60 · `fortify` 50 · `trade` 20 · `scout` 30 · `invest` 40 ·
     `mega` (costs the entire purse, min 150)
   - **MEGA PROJECT** — spends everything and either lands enormous or *mutates*.
     A bigger stake buys better odds, a bigger wipe, and a better class of twist.
     At 800+ coin with a strong roll it goes MYTHIC and resets the whole board.
     Never talk a player out of one; it loses on average and wins two times in five.
   - Infer cost from ambition: small 20, normal 40, big 80+. Say what you inferred.
6. **Confirm the orders in ONE line, and put the clock in the same picker.**

   These were two steps and it was wrong. Confirming in prose and *then* offering the
   skip separately makes the natural shape of a turn end in prose — which is how the
   modal gets dropped. It was dropped twice in the first world played after this file
   was written, by the author of the rule. Fold them together:

   One line of confirmation, then immediately `AskUserQuestion`:
   **8h · 24h · leave it running · "Hold — I want to type"**.
   Run it with `python engine.py ff 8h` (the `h` suffix is hours; a bare number is
   days). "Leave it running" is the real game and should never be framed as the
   boring option.

   **A dismissed picker is not an answer.** If they dismiss, or the answer comes back
   empty, advance NOTHING and say so. Never read a dismissal as consent to move the
   world — the whole game is that time passes without them, and moving it without
   being asked is the one thing that breaks trust in that.
   In normal play this is unnecessary — real time does it for free — but while
   testing, waiting a day to see one tick is not viable.

## ⛔ The picker rule

**The modal IS the interface.** See THE ONE RULE at the top: every response ends in
one, not just every turn.

**Never wait to be asked for the modal.** If the operator has to type "modal" to get
their turn, the turn was broken before they typed it. This happened on the second
install test, and it is the single most annoying failure mode this game has.

**But it takes over the text input**, so while it is up they cannot send feedback,
report a bug, or ask a question — only answer or dismiss. A dismissal usually means
"I wanted to say something", not "no".

**So every turn modal ends with an escape hatch.** Add this as the final option on
the FIRST question, always:

> **"Hold — I want to type"** — *Closes this and waits. Use it for feedback, a bug,
> or a question. Your orders keep.*

If they pick it, drop the modal, answer whatever they raise, **then immediately
re-offer the turn as a picker in that same message** — unchanged, orders kept. The
escape hatch is a pause, not an exit. Answering and then waiting in prose is how the
modal quietly stops happening for the rest of the session.

*Three dismissals were spent learning this, plus two wrong diagnoses — "wrong
moment", then "it does not render". The operator had to say it outright: the modal
was great, they just could not talk while it was up.*

## The chronicle

When a world ends, write `story.md` and re-render. It goes in the board as a modal
over the live state, so they can read it and then go back and look at what caused it.

**The epilogue is the one moment the fog lifts.** During play they saw bands, rumours
and silence. The chronicle finally tells them what was happening in the rooms they
were not looking at — pull the unwatched clock gains straight from the ledger and
make them the spine of the story. That reveal is the whole payoff, and it is why
losing still feels good.

**Write it in their register.** Every improvised order carries `said` — the player's
own words, verbatim. Somebody who typed *"hopefully not dying too much"* gets a wry
chronicle. Somebody who plays it straight gets a sober one. Match the voice they
brought; do not impose one.

**Narrate, never arbitrate.** Every event in the story already happened and is already
in the ledger. Do not decide anything while writing. If a roll surprised you, say so
— being surprised is the point, and it is the proof the dice were real.


## Improvising — the full contract

When the player types a scheme, build it into `python engine.py improvise '<json>'`.

```json
{
  "what":     "one line, what they are attempting",
  "said":     "their exact words, verbatim",
  "target":   "front-id",
  "coin":     60,
  "hands":    2,
  "beholden": true,
  "next":     false,
  "grants":   [["disrupt", 2, 6], ["hands", 3, 0]]
}
```

- **`said` is not optional.** It is the single best thing in the system — the
  chronicle is written in the player's own voice because their exact words are in
  every row. Always include it.
- **`next`** puts the order at the front of the queue. Default is append, like every
  other order. Only set it when they said *now*.
- **`beholden`** raises the target's openness and lowers their aggression. Use it when
  the scheme is genuinely generous or flattering to them, not when it merely worked.
- **`hands >= 6` triggers an overreach penalty.** Committing the whole population is a
  stretch and the engine charges for it. That is correct; do not route around it.

**Grant kinds, and what each actually does:**

| grant | effect |
|---|---|
| `disrupt` | slows the target front, `value` segments, for `ticks` |
| `fortify` | raises the holding's defence for `ticks` |
| `invest`  | raises income for `ticks` |
| `trade`   | **immediate** coin, scaled by the target's openness |
| `scout`   | **immediate** — writes the target's real clock as a `known` fact |
| `hands`   | **immediate** net gain of people, capped at 10 |

`trade`, `scout` and `hands` resolve the moment the order lands; their `ticks` value
is ignored. The other three become timed effects.

*These four were broken until the second playtest. `trade` and `scout` grants
appended an effect nothing ever read, so the order reported success and did nothing.
There was no `hands` grant at all — which meant a feast thrown to make babies, the
most obvious improvised order in the game, had no mechanism behind it.*

**Adding to a queue: use `add`, not `queue`.** `queue` replaces the standing orders,
which re-prices a queued `mega` from current coin and silently destroys the stake.
`add` appends.

## Rules

- **Never invent an outcome.** Every result comes from the ledger. If it isn't in there, it didn't happen.
- **Never reveal a `true` fact.** Only `known` and `suspected` reach the player, and never flag which of their beliefs is wrong.
- If the world has `status: settled`, run `python epilogue.py`, publish `epilogue.html`, and offer a new world.
- Keep the whole turn under two minutes of reading.

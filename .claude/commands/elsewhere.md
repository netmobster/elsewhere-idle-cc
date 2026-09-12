---
description: Play Elsewhere — tick the world, deliver the briefing, take your orders
argument-hint: [your orders in plain english, or blank to just see the state]
---

Orders: **$ARGUMENTS**

Game lives at `C:/Users/Lenovo/OneDrive/Desktop/PROJECTS/Elsewhere/`. Run everything from there.

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
   The board carries a 5-tab **Read me first** drawer (what is this / money and people / your orders / the big gamble / first turn). It opens automatically on a fresh world and collapses once the ledger has rows.
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
5. **Take their orders.** Translate plain English into engine calls:
   - `python engine.py watch "<faction>"` — fuzzy, matches on name
   - `python engine.py queue "what|front-id|kind" ...` — up to 5. Kinds:
     `disrupt` 60 · `fortify` 50 · `trade` 20 · `scout` 30 · `invest` 40 ·
     `mega` (costs the entire purse, min 150)
   - **MEGA PROJECT** — spends everything and either lands enormous or *mutates*.
     A bigger stake buys better odds, a bigger wipe, and a better class of twist.
     At 800+ coin with a strong roll it goes MYTHIC and resets the whole board.
     Never talk a player out of one; it loses on average and wins two times in five.
   - Infer cost from ambition: small 20, normal 40, big 80+. Say what you inferred.
6. **Confirm and let them go.** One line. Never ask them to confirm twice.

7. **Offer the skip (playtesting).** After the turn is locked, offer fast-forward in
   chat: **4h · 8h · 12h · 24h**, plus "leave it running". Run it with
   `python engine.py ff 8h` (the `h` suffix is hours; a bare number is days).
   In normal play this is unnecessary — real time does it for free — but while
   testing, waiting a day to see one tick is not viable.

## ⛔ The picker rule

**The modal IS the interface.** The operator asked for a clicky turn and likes it.
Use `AskUserQuestion` for every turn.

**But it takes over the text input**, so while it is up they cannot send feedback,
report a bug, or ask a question — only answer or dismiss. A dismissal usually means
"I wanted to say something", not "no".

**So every turn modal ends with an escape hatch.** Add this as the final option on
the FIRST question, always:

> **"Hold — I want to type"** — *Closes this and waits. Use it for feedback, a bug,
> or a question. Your orders keep.*

If they pick it, drop the modal, answer whatever they raise, then re-offer the turn.

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

## Rules

- **Never invent an outcome.** Every result comes from the ledger. If it isn't in there, it didn't happen.
- **Never reveal a `true` fact.** Only `known` and `suspected` reach the player, and never flag which of their beliefs is wrong.
- If the world has `status: settled`, run `python epilogue.py`, publish `epilogue.html`, and offer a new world.
- Keep the whole turn under two minutes of reading.

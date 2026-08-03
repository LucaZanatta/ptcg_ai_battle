# AGENT_CHANGE_LEDGER

Every behavioural change tried on the champion, the failure class it named, and what happened.
Kills are recorded with the same weight as keeps — a rule that was tried and lost is evidence
about the base agent, and deleting it would leave the next campaign to rediscover it.

The base is `official_dragapult` (`champion.json`). All changes are made in `main.py`, this
contract's own wrapper, which consults the base agent on **every** decision and replaces only the
returned indices in a named decision class. With no rules enabled, the wrapper is action-identical
to the base: **0 mismatches over 941 decisions in 12 games** (`raw_evaluations/identity/`).

## The noise floor this ledger is read against

Two *identical* policies measured on the same dev panel in two separate runs:

| run | policy | games | dev field score |
|---|---|---:|---:|
| `deck_screen1` | `chal_dp_base` (wrapper, no rules) | 400 | 0.4850 |
| `rule_screen1` | `chal_dp_base2` (wrapper, no rules) | 600 | 0.5166 |

**3.2 points apart with nothing changed between them.** Any single-arm difference smaller than
that is not evidence, and this ledger reports deltas against the *same-run* control rather than
against a control measured in a different run.

---

## F1 — turn order (`go_first`)

**The failure class.** The official Dragapult sample scores YES = −1 in `SelectContext.IS_FIRST`,
so it always elects to go **second**. Nothing in the sample justifies it, and a public Mega
Lucario agent whose kernel is titled with a 1084.5 leaderboard score makes the opposite choice.
One bit, whole-game consequence, never measured.

**Change.** In `IS_FIRST`, return the YES option.

**Result — `rule_screen1`, 600 games each on the dev panel:**

| candidate | dev field | vs Grimmsnarl | vs Alakazam | vs mirror |
|---|---:|---:|---:|---:|
| control `chal_dp_base2` | **0.5166** | **0.308** | 0.583 | 0.433 |
| `go_first` | 0.4883 | **0.217** | 0.592 | 0.408 |

**KILLED.** −2.8 points overall and −9.1 against the single most important opponent. Going first
means no attack on the opening turn and no extra card; against a spread-damage deck that starts
scoring immediately, that is a turn given away. **The sample's choice is correct and now has
evidence behind it.**

---

## F2a — bench Dreepy when moving first (`bench_dreepy_always`)

**The failure class.** The sample benches *nothing* at setup when it is the first player
(`if my_index == state.firstPlayer or card.id != Dreepy: score = -1`) and only Dreepy when second.
A deck whose entire plan is Dreepy → Drakloak → Dragapult ex needs Dreepy on the board early, and
an empty bench also means one knockout ends the game.

**Change.** Select Dreepy at `SETUP_BENCH_POKEMON` regardless of turn order.

**Result:** 0.5033 against the 0.5166 control — **−1.3 points, inside the 3.2-point noise floor.
KILLED as unsupported.** Not "shown to be harmful": shown to be indistinguishable, which at this
cost is the same decision.

---

## F2b — fill the opening bench (`bench_wide_setup`)

**Change.** Fill the bench up to `maxCount`, preferring Dreepy, then Budew, then the ex support
Pokémon last.

**Result:** 0.4667 against 0.5166 — **−5.0 points, outside the noise floor. KILLED.**

Against Grimmsnarl it is 0.242 vs 0.308. That is the mechanism, and it is legible: Marnie's
Grimmsnarl ex attacks with Shadow Bullet, *180 damage plus 30 to a benched Pokémon*, and Froslass
puts a damage counter on every Pokémon with an Ability during checkup. A wide bench against that
deck is not development, it is surface area. **The sample's narrow bench is a correct read of the
current meta, arrived at before the current meta existed.**

---

## F3 — greedy option scoring (`turn_planner`)

**The failure class.** Every official sample scores each option in isolation against a
hand-written constant. That policy cannot see that playing card A first makes card B reachable,
or that this turn's attack costs next turn's attacker.

**Change.** `planner.py` (this contract's code) uses the engine's forward-search API: at a
decision it determinizes the hidden state, steps each candidate option from the root, lets **the
base agent itself** finish the turn from there, and scores the board each line leaves behind. The
expert remains the fallback — the planner overrides only when its own evaluation of the expert's
action is beaten by a stated margin.

**Feasibility, measured before building it:** `search_begin` 0.46 ms median, `search_step`
**0.245 ms**, 26/26 begins successful from a naive determinization, and our own deck/prize
determinization is *exact* (9/9 probes: the card count of unseen own cards matches deck + prize
exactly). Planning cost in play: **mean 14.3 ms, max 118.7 ms per decision** — against a mean of
0.65 ms for the base and 44 ms for the Alakazam agents that lead this panel.

**Override rate at defaults: 2.3%.** Low, and expected: with the base playing out the turn
regardless, the order of the first action usually converges to the same end-of-turn board. The
variants screened below widen where and how hard the planner looks.

**Result:** see `plan_screen1` — recorded in `EXECUTIVE_DECISION.md`.

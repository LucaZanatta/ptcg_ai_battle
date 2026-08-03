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
regardless, the order of the first action usually converges to the same end-of-turn board.

### F3, first result: the more it overrode, the worse it did

`plan_screen1`, 1,000 games each on the dev panel:

| arm | what it changed | dev field | vs Grimmsnarl |
|---|---|---:|---:|
| control `chal_dp_base2` | — | **0.5060** | 0.300 |
| `plan1` | MAIN decisions only | 0.4985 | 0.268 |
| `plan3` | MAIN, wider and deeper | 0.4910 | 0.295 |
| `plan4` | every decision, wider, punitive evaluator | 0.4850 | 0.260 |
| `plan2` | **every** single-select decision | **0.4790** | 0.295 |

**KILLED.** All four at or below the control, and **monotone in override rate**: the arm that
overrode most often was the worst, the most conservative was the best of the four. A contention
artefact would have depressed all four together rather than ordering them this way.

The mechanism: a hand-written board score is arguing with constants that encode deck knowledge it
does not have, and it loses that argument more often than it wins.

*(This run used a 120 ms wall-clock work budget and is retained as a screen, not as a strength
measurement — see `superseded/README.md` and `PIVOT_LEDGER P4`.)*

### F3, second result: gate the override on facts instead of taste

If the evaluator is the problem, remove it from the decision. `prize_only` mode overrides only on
a lexicographic improvement in **(terminal result, prizes taken, prizes conceded)** — quantities
that are facts about the simulated line. `use_ko_risk` adds a fourth term: the prizes the opponent
can immediately take back, computed from their *visible* active, its attached energy and its
public attacks.

| arm | mode | dev field (1,200 games) |
|---|---|---:|
| `prizeall` | exact gain, every decision | 0.5167 |
| `koall` | exact gain + knockout exposure, every decision | 0.5142 |
| control `chal_dp_base3` | — | **0.5125** |
| `koexact` | exact gain + knockout exposure, MAIN only | 0.5050 |
| `prizeonly` (screen 2) | exact gain, MAIN only | 0.5125 vs a 0.5042 control |

**Null.** Every arm sits within ±0.4 points of a control whose own run-to-run spread is ~1 point.

And the firing probe explains why, quantitatively: **these rules fire on 0.07%–0.4% of
decisions** — one to six times per sixteen games. There is nothing there to move a field score.

### The finding underneath both results

**The expert's turn is very close to order-invariant.** Whichever legal action it takes first, it
plays the rest of the turn to the same board, so a search over the *first* action almost never
changes the prize outcome — which is exactly what a 0.07–0.4% exact-gain firing rate measures. A
first-action search is the wrong instrument for this agent; the decisions that are *not*
recoverable later in the turn (which Supporter, which attack, which target) are a small minority,
and the expert already has hand-tuned constants for each of them.

### F3, third attempt: search only inside the expert's own shortlist

`shortlist_planner` asks the expert for its top-k — by re-asking it with each previous choice
vetoed — and searches only those. Every candidate is then expert-approved and the search is
breaking a tie rather than overruling knowledge. Fire rates: 0.13% (k=3, exact gate) and 0.32%
(k=4, board evaluator with a 200-point margin).

`rule_screen4`, 1,200 games each:

| arm | dev field | vs Grimmsnarl |
|---|---:|---:|
| control `chal_dp_base3` | **0.5279** | 0.352 |
| `short4` (k=4, board evaluator, 200-pt margin) | 0.5033 | 0.317 |
| `short3` (k=3, exact gate) | 0.4879 | 0.296 |

**KILLED.** Both below the control. Restricting the search to expert-approved options did not
rescue it.

### F3 verdict

Three designs, eleven arms, ~26,000 games. Every one at or below its same-run control. The
mechanism is measured rather than inferred:

1. with a board evaluator, the arms order **monotonically in override rate** — the more it
   overruled the expert, the worse it did;
2. with an exact gate, the override rate collapses to **0.07–0.4% of decisions**, because the
   expert's turn is close to order-invariant and the first action almost never changes the prize
   outcome;
3. restricting to the expert's own shortlist changes neither.

**A first-action search is the wrong instrument for this agent.** The engine's forward-search API
works, is fast (0.245 ms per step), and the determinization of our own hidden cards is exact —
none of that was the problem. The problem is that there is very little for it to decide.

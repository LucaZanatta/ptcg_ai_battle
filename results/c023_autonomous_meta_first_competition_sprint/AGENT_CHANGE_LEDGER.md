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

## F6 — the sample's own score constants (`tune`, then `ab_*`)

**The failure class.** Every official sample decides by adding hand-chosen round numbers —
`score = 40000`, `score += 250`, `return 20000`. None of them was ever measured against its
alternatives. This is the largest untested surface in the agent, and unlike F1–F4 it does not
require guessing *which* decision is wrong.

**Change.** `tools/c023_paramize.py` rewrites 110 of those constants, by AST transform, into
lookups whose defaults are the original values — restricted to constants that are genuinely
weights (assigned to a scoring variable, or returned from a `*_score` function). Card IDs, deck
sizes, energy costs and list indices are untouched. Verified rather than asserted: the
parameterised agent is **action-identical to the sample over 1,263 decisions in 14 games**.

### The search, and what it actually measured

A (1+5) search over those 110 parameters, registered in full before it ran
(`tuning/REGISTERED_PROTOCOL.md`): 1,000 games per arm, the incumbent re-measured every round in
the same run as its challengers, acceptance requiring twice the standard error of the difference
(4.47 points), and the output declared a *hypothesis* that must still clear confirmation and
validation on fresh runs.

Thirty-two rounds. Three acceptances. And the **pooled incumbent series** — the search's own
re-measurements, which are the most precise strength instrument in this campaign — says:

| incumbent | rounds | n | mean dev field |
|---|---|---:|---:|
| the untouched defaults | r0–r4 | 5 | **0.5062** |
| + 1 accepted parameter | r5–r21 | 17 | 0.5067 |
| + 4 accepted parameters | r22–r28 | 7 | **0.4984** |
| + 9 accepted parameters | r29–r32 | 4 | **0.4987** |

**The search walked downhill.** Its first accepted change was worth **+4.80 points when selected
and +0.05 over the next seventeen re-measurements**; the next two left the incumbent about 0.8
points *below* the defaults.

**Why, exactly (D7).** All three acceptances fired on **low incumbent draws**, not on exceptional
children — incumbent ranks 10, 2 and **1** out of 30, with the last two children scoring at or
*below* the mean best child. The acceptance rule compares a maximum over five children against a
**single** incumbent measurement, so a low incumbent is worth exactly as much as a good child.
The rule should have compared against the incumbent's running mean. It was not changed mid-run,
because choosing a threshold after seeing which rounds it accepts is what registration exists to
prevent; the search was stopped instead, and replaced.

### The clean test that replaced it

`tuning/REGISTERED_AB.md`, registered before the search was stopped. Four arms, **no selection
step**, 5,000 games each, decision threshold 2.0 points fixed in advance, and the validation panel
for anything that clears it. The three parameters tested all say the same thing — *reach harder
for a way to attack when the main line has not arrived* — which is **F5**, the one failure class
the loss mining supports.

**Result — `ab_dev`, 5,000 games per arm, zero errors:**

| arm | what it changes | dev field | vs control |
|---|---|---:|---:|
| `ab_f5` | 39 + 56 + 75 together | 0.5116 | **+0.17** |
| **`ab_ctrl`** | nothing | **0.5099** | — |
| `ab_p56` | Crispin fetch | 0.5091 | −0.08 |
| `ab_p39` | Latias ex fetch | 0.4968 | **−1.31** |

**And on the validation panel, which no search or tuning ever saw — `ab_val`, 2,400 games each:**

| arm | validation field |
|---|---:|
| `ab_f5` | 0.4971 |
| `ab_ctrl` | 0.4960 |
| difference | **+0.11** |

**KILLED, and the registered prediction was exact.** `REGISTERED_AB.md` predicted "all three arms
land within ±2 points of the control"; the largest deviation is −1.31, and the standard error of a
difference at 5,000 games per arm is ~1.0 point.

The single most useful number in the table: **parameter 39, which the search selected first and
valued at +4.80 points, measures −1.31 in a clean unselected test.** Not smaller than claimed — the
wrong sign.

### F6 verdict

Three independent lines of evidence, each capable of killing this on its own:

1. **The search's own incumbent series**: 42,000 games, and every accepted change after the first
   left the incumbent *below* the untouched sample.
2. **A powered, unselected A/B**: 20,000 games across four arms, everything inside ±1.4 points, and
   the search's flagship parameter negative.
3. **A held-out validation panel**: 4,800 games, +0.11 points.

**The official Dragapult sample's hand-written score constants are not improvable by search at
this scale.** That is a stronger statement than "we did not find an improvement", because the
instrument was calibrated: this campaign can resolve a 2-point difference at 5,000 games per arm,
and there is no 2-point difference here to find.

## F4 — bench exposure against a damage-spread deck (`bench_discipline_vs_spread`)

**The failure class.** Marnie's Grimmsnarl's Shadow Bullet hits a *benched* Pokémon for 30 on top
of 180 to the active, Froslass puts a counter on every Pokémon with an Ability each checkup, and
Munkidori moves three counters a turn onto our side. Every small basic we bench is a prize on a
timer. The sample scores playing a Dreepy at 51000 — the second-highest number in its table —
regardless of what is across the board.

**Change.** When the opponent shows the Grimmsnarl / Froslass / Munkidori package and our bench
already holds ≥ *cap*, veto playing a Pokémon with ≤100 HP and take **the expert's own next
preference** instead (the veto primitive: the observation is copied with that option removed and
the simulation instance of the base agent chooses from what remains).

**This rule was measured twice, and the first measurement was of nothing.** In its original form
the `View` resolved a PLAY option's card through its `area` field — and PLAY options carry no
area, so the precondition never held. **0 fires in 1,329 decisions.** The 1,200-game evaluation
that produced 0.5142 against a 0.5042 control was a measurement of the control policy under a
different name. See `failures/DEFECTS.md` D2 and `superseded/README.md`.

**The prediction, registered before the fixed rule ran** (`PREDICTIONS.md` P-A): *it will score at
or below the control, and the loss will be concentrated in the Grimmsnarl matchup it was written
for.* The reasoning was that the loss mining shows winning games with a **larger** mean bench
(3.31 vs 2.63), and that with a 100 HP threshold the only cards the rule can veto in this deck are
Dreepy and Budew — so every firing is the agent being stopped from developing its own evolution
line. `chal_dp_benchline`, the same rule with the Dreepy/Drakloak line protected, measured
**INERT**, which confirmed the rule's whole effect *is* blocking Dreepy.

**Result — `bench_screen`, 2,000 games each, the highest-powered run in the campaign:**

| arm | fire rate | dev field | vs control | vs Grimmsnarl |
|---|---:|---:|---:|---:|
| `bench_prizef` (cap 2 + exact-gain planner) | 17.6% | 0.5285 | +0.55 | 0.320 |
| control `chal_dp_base3` | — | **0.5230** | — | **0.343** |
| `bench2f` (cap 2) | 8.4% | 0.5145 | −0.85 | 0.340 |
| `bench3f` (cap 3) | 7.2% | 0.4995 | **−2.35** | **0.268** |
| `koexact` (planner, exact gate) | 0.4% | 0.4990 | −2.40 | 0.278 |

**KILLED, and the prediction holds.** No arm exceeds the control by more than the noise floor, the
two arms that actually change play both land below it, and `bench3f`'s loss is exactly where P-A
said it would be — **−7.5 points against Grimmsnarl**, the matchup the rule was written for.

The lesson is the one the mining already stated: against this deck, our losses are the games where
the line comes online *late*, not the games where the bench is *wide*. A rule that suppresses
development to reduce exposure is treating the symptom that correlates with winning.

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

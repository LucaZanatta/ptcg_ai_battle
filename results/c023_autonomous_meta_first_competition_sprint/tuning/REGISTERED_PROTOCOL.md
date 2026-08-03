# Registered protocol — the score-constant search

Written and committed **before the search ran**. Every threshold below is fixed here so it cannot
be chosen after seeing the answer.

## What is being searched

The 110 heuristic score constants of `official_dragapult`, extracted by AST transform
(`tools/c023_paramize.py`) into parameters whose defaults reproduce the sample exactly. Verified,
not asserted: **0 mismatches over 1,263 decisions in 14 games** against the untransformed sample.

The transform touches only constants that are weights — assigned to a scoring variable, or
returned from a function whose name ends in `_score`. Card IDs, deck sizes, energy costs, HP
thresholds and list indices are untouched. `_param_official_dragapult_slots.json` records every
parameter's original value, its function and its line in the sample.

Distribution across the agent: 44 in `agent`, 40 in `hand_score`, 16 in `attach_score`, 6 in
`main_option_proc`, 4 in `pokemon_score`.

## Why this is not the blind sweep the contract warns against

Each parameter is a named weight at a named line — "the score the agent gives to playing a Rare
Candy when it can evolve Dreepy and holds Dragapult ex" is parameter 63, not an anonymous
coordinate. Any accepted change is reported that way in `AGENT_CHANGE_LEDGER.md`.

The contract's actual condition is that the sweep "can be validated before the deadline". It can:
the search finishes by 07:00 on 2026-08-04, leaving 37 hours for confirmation, validation on a
disjoint opponent panel, packaging and reporting.

## The search

| | |
|---|---|
| algorithm | (1+λ) with λ=5, multiplicative sign-preserving perturbation |
| perturbation | k ~ U{1..5} parameters, each × exp(N(0, 0.35)), rounded, sign never flipped |
| objective | off-mirror field score on the **dev panel only** (`PANEL_SPLIT.json`) |
| games per arm | 200 per opponent × 5 opponents = **1,000** |
| arms per round | 6 (incumbent + 5 children) = 6,000 games |
| rounds | up to 70, hard-stopped at **2026-08-04T05:00:00Z** |
| seed | 20260803 |

## The three defences against hill-climbing on noise

Registered because a (1+λ) search that takes the best of five each round *will* drift upward on
noise alone, and saying so afterwards is worth nothing.

1. **The incumbent is re-measured every round, in the same run as its challengers.** A round's
   comparison is between numbers produced under identical machine conditions, not against a
   remembered score from an earlier run.
2. **Acceptance requires a margin of twice the standard error of the difference** at the round's
   game count — at 1,000 games per arm that is **±4.47 points**. A child that merely leads is
   rejected.
3. **The output is a hypothesis, not a candidate.** `tune_best` must then clear, on *fresh* runs:
   - **confirm** — ≥1,200 games on the dev panel, against a same-run control;
   - **validate** — ≥800 games on the **validation panel**, which contains no agent the search
     ever saw.

## What is predicted, before the run

**The search will report a dev-panel gain, and most of it will not survive confirmation.** That is
the expected behaviour of a selection procedure over a noisy objective, and the size of the
shrinkage is itself a result worth recording.

**A tuned agent will be promoted only if** it clears the promotion rule already registered in
`PANEL_SPLIT.json`: a material broad-field improvement surviving on the validation panel, with no
opponent below 0.15 and no regression in errors, timeouts or illegal actions. The ~+4 point target
in that file was written before any result existed and is not being relaxed here.

## What is recorded regardless of outcome

- every round's incumbent score, best child, gain and accept/reject decision (`tune_history.json`)
- every arm's raw games (`raw_evaluations/tune_r*/games.jsonl`)
- the final parameter set, **read back as named weights with their original values**
- the confirmation and validation deltas, including the shrinkage from the search estimate

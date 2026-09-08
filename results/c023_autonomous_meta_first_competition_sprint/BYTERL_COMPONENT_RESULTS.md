# BYTERL_COMPONENT_RESULTS

**Status: `NOT_ADMITTED`. No ByteRL component was integrated into any c023 candidate.**

This is a decision with evidence behind it, not an omission, and the evidence is mostly c022's —
which is the point, because c022 ran the isolated admission tests this contract would otherwise
have had to repeat.

## What the contract requires before a component may be used

> Evaluate on new holdout data using grouped game-level statistics… State-outcome correlation
> alone is insufficient. …Do not combine neural components until one isolated component passes.

## The value head: measured, and it fails admission

c022 registered the admission condition **before** any transfer arm ran: the value head must beat
a **constant predictor at the observed base rate** on held-out games.

| checkpoint | value skill vs a constant predictor at the base rate |
|---|---:|
| `floor_fixed_deck` | **−0.06** |
| `floor_end_to_end` | **−0.10** |

Both negative. A head that cannot beat "always predict the base rate" has learned nothing about
which positions are good, whatever its mean-squared error looks like in absolute terms. c022's
`transfer/value_only/NOT_RUN.md` records the gate holding and the arm not being run.

## The policy prior and rollout policy: measured, and inconclusive

c022 ran both as isolated transfer arms into corrected MCGS, 200 games each, 12 simulations per
decision, 0 abandoned, with a noise floor measured **before** the arms ran:

| arm | field score | Δ vs the measured floor | verdict |
|---|---:|---:|---|
| T1 policy prior | 0.130 | +1.5 pp | INCONCLUSIVE — inside a 5.0 pp floor |
| T2 rollout policy | 0.120 | +0.5 pp | INCONCLUSIVE — inside a 5.0 pp floor |

And the deployment finding, which is what matters here: T2 made **6,172,385** network calls,
885 per searched decision, and spent **78% of its wall clock inside the network** for no
measurable strength. Under a deployment clock that is strongly negative.

## Why nothing changed that in c023

Three reasons, in order of weight:

1. **The strongest checkpoint is not a strong player.** `br3_fixed_deck_long` reached 73% of its
   matched budget and separates from a random floor — but scores ~0.15 against a frozen bar of
   0.58. c023's champion scores 0.4653 against a panel where the leaders reach 0.64. Grafting a
   0.15-strength policy onto a 0.47-strength expert is not a promising direction, and the
   contract is explicit that internal training progress is not a continuation criterion.
2. **The architecture mismatch is unresolved.** c022 recorded it plainly: the c022 model's
   defining feature is its LSTM recurrence, and any query from inside a search node is made from
   a **zeroed** recurrent state, because a search node carries no episode history. A null result
   from such a query is evidence about a stateless query of a recurrent policy, not about the
   policy.
3. **Opportunity cost against a hard deadline.** The contract forbids a component that "blocks
   higher-value expert-agent work". The measured competitive lever in this campaign is the
   Grimmsnarl matchup at 0.250 against an opponent representing ~60% of the top two ladder bands.
   Every hour spent on a component that has already failed its own admission gate is an hour not
   spent there.

## The one measurement that would reopen this

c022 named it: **`br3_fixed_deck_long`'s value head has never been evaluated for admission.** Its
*policy* separates from the random floor; its value head was never scored against the constant
predictor. That is a cheap offline measurement — held-out games already exist under
`c022/results/byterl/external_evaluations/` — and it is the correct next step if a future
campaign wants a learned component here.

It was not run in c023 because a positive result would only unlock a value-reranking arm that
would then need its own screen, confirmation and validation inside a window that the Grimmsnarl
work already fills. Recording the gate as **unmet-and-unmeasured** is the honest state; calling
it `NOT_RUN` for lack of time and calling it failed are different claims and this file makes the
first one.

## Reusable assets that were taken from that lineage

Not the network. What carried over is engineering, and it is worth naming because the contract
asks whether ByteRL provided measurable value:

- the **identity-carrying job/result contract** (c009) that this campaign's harness enforces
- the **evidence-validation discipline** — recompute every aggregate from raw rows with a
  different code path — which caught nothing here only because the harness was built to its shape
- the measured knowledge that **a latency-budgeted search must not share a machine**, which
  changed the planner's work budget from a clock to a count (`PIVOT_LEDGER P4`)

**Answer to executive question 9: no. ByteRL provided no measurable competitive value in c023,
and no component was admitted.**

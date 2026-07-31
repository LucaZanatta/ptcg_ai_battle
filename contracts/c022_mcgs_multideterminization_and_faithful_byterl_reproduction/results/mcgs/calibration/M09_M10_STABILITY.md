# M09 / M10 — the ensemble stabilises the value, not the choice

`TRAINING_AND_EVALUATION §5` requires "action disagreement and stability on at least 500 frozen
decisions". **500 of 500 captured, 499 evaluated**, each replayed 3 times per K under independent
world draws with everything else held constant.

Game arms cannot supply this: every arm plays its own games, so two arms never face the same
decision and "stability" would be confounded with "different position". This replays the *same*
decisions.

| | K=1 | K=8 | delta |
|---|---:|---:|---:|
| mean action stability | 0.6106 | 0.6119 | **+0.0013** |
| fraction perfectly stable | 0.1563 | 0.1583 | +0.0020 |
| mean predicted-probability SD across repeats | 0.0610 | **0.0454** | **−0.0156** |
| within-decision world agreement | 1.000 | 0.5633 | — |
| distinct best actions within a decision | 1.000 | 3.2251 | — |

## The result

**Action stability does not move.** 0.6106 → 0.6119 is +0.13 of a percentage point across 499
frozen decisions. Given the same decision and independent world draws, a K=8 ensemble picks the
same action almost exactly as often as a single world does.

**The value estimate does stabilise.** Predicted-probability SD across repeats falls from 0.0610
to 0.0454 — a 26% reduction. Averaging over eight worlds does what averaging does: it reduces the
variance of the estimate.

**The worlds genuinely disagree.** Within-decision agreement is 0.5633 and the eight worlds
nominate 3.23 distinct best actions on average. The mechanism is not inert on this decision set —
there is real disagreement for it to aggregate. It simply does not convert into a more stable
choice.

## Why this matters beyond M09/M10

The stability probe's own registered reading, written before it ran, said:

> Stability RISING with K is the ensemble working: the chosen action stops depending on which
> hidden world happened to be sampled. Predicted-probability SD FALLING with K is the same effect
> in the value estimate.

We got the second without the first, and that is a sharper statement than either measurement
alone. The ensemble reduces variance in the *value* while leaving the *argmax* almost untouched —
so the aggregation is working arithmetically and failing to change the decision.

This corroborates `FINDING_the_calibration_gain_is_compute.md` from an independent direction and
on different data. That finding measured a 1.2% ensemble contribution to calibration on 200 paired
games; this measures near-zero ensemble contribution to action stability on 499 frozen decisions.
Two different probes, two different quantities, the same conclusion: **root-level ensembling
smooths the number the search reports without changing what the search does.**

It also explains the field-score results rather than merely agreeing with them. A method that does
not change the chosen action cannot change the game's outcome, whatever it does to the reported
probability — which is why `paired_k8` sits inside the K=1 replication spread, and why the
`k8_s384` depth arm showed world disagreement *undiminished* at 4x the search.

## What this does not say

- **Not that K is useless in general.** It is a measurement of *root-level* aggregation at 96
  simulations per decision, which is the only mechanism the PTCG API permits (`M01b`: eleven source
  sites need interior hidden-state mutation the engine refuses). The source re-determinizes before
  every rollout, deep in the tree. That is a different operation and it is unavailable here.
- **Not that the value stabilisation is worthless.** A better-calibrated probability is useful for
  anything that consumes it — a transfer prior, a resignation rule, a search that spends budget on
  uncertainty. It is simply not what a field score measures.

# M08 ceiling remeasurement — the obligation discharged, and the answer is a problem

`PREREGISTERED_AGGREGATION.json` recorded, after `D13`:

> `tools/c022_probe_rollout_bias.py` is re-run after the sweep, and the ceiling it measures is
> compared against the recorded 0.201 root-only / 0.200 mean-over-actions / 0.088 selection gap.
> **If the ceiling moved, M08's target moves with it and BOTH readings are reported here — the
> target is not silently updated to whatever the second measurement says.**

It moved. Both readings, as promised:

| quantity | pre-D13, registered | post-D13, remeasured |
|---|---:|---:|
| rollout from the ROOT, before any action | 0.201 | **0.6003** |
| the same rollouts scored for the OPPOSING seat | 0.601 | **0.3281** |
| mean over root actions | 0.200 | 0.5873 |
| max over root actions | 0.289 | 0.6927 |
| selection gap (max − mean) | 0.088 | 0.1054 |
| turn-capped fraction | 0.197 | 0.0778 |

## The two readings do not differ by a correction — they differ by a swap

`0.201 / 0.601` became `0.6003 / 0.3281`. The root seat and the opposing seat have essentially
exchanged values. A payload fix — which is what `D13` was, multi-select decisions emitting one
option where `minCount > 1` required a set — changes *which actions get played*. It is not obvious
how it inverts *which seat a rollout is scored for*, and the sum also moved (0.802 → 0.928, the
remainder being turn-capped rollouts, whose fraction fell from 0.197 to 0.0778).

Two readings are consistent with that pattern and they have opposite consequences:

1. **The fix is real and the old number was wrong.** D13's payload defect made multi-select
   decisions play a different action set; if those decisions systematically ended turns, the
   rollouts were being scored from the wrong side of the turn boundary, and the old 0.201 was the
   opponent's win rate wearing the root player's name. Under this reading the *new* number is the
   ceiling.
2. **The probe's sampled roots differ between runs.** The probe captures frozen roots from live
   games, and the environment redraws its games on every run
   (`NOISE_FLOOR_ACCIDENTAL_REPLICATION.md`). Twelve roots is a small sample, and a different draw
   could move these numbers without any defect at all — though a near-exact swap is a strange
   coincidence for sampling to produce.

**I cannot distinguish them from the artifacts in hand, and I am not going to pick the one that
suits the report.**

## What this puts in doubt

`FINDING_the_calibration_gain_is_compute.md` states that the residual ~21 pp overconfidence in
both 96-simulation arms "is the floor `PREREGISTERED_AGGREGATION.json` measured before any sweep
ran". That sentence rests on the **pre-D13** ceiling of ~9 pp root optimism plus a depth term.

Against the post-D13 ceiling, root-only optimism is ~48 pp (0.6003 predicted against a field score
near 0.12), which is *larger* than the 20–22 pp the arms actually exhibit — so the arms would be
**better** calibrated than their own rollouts, which needs a different explanation than the one
that report gives.

**The finding's primary result is untouched.** The decomposition — 98.8% of the Brier improvement
from simulations, 1.2% from the ensemble — is a comparison between three measured arms and does
not reference the ceiling at all. What is in doubt is the *explanation* offered for the residual,
not the measurement of the effect.

## Status

- The obligation is **discharged**: the probe was re-run and both readings are recorded.
- `M08`'s pass condition is **not moved**. It asked for a reduction in Brier and log-loss relative
  to the K=1 arm, which is a comparison between arms and does not depend on the ceiling's value.
- The residual explanation in `FINDING_the_calibration_gain_is_compute.md` is marked as resting on
  a superseded ceiling, pending the seat-attribution question above.

The next step is small and specific: score the probe's rollouts for both seats on the *same*
frozen roots under the pre- and post-D13 payload paths. That isolates a payload effect from a
sampling effect, and it is the only thing that decides which of the two readings is the ceiling.
It was not run for want of time, not for want of a method.

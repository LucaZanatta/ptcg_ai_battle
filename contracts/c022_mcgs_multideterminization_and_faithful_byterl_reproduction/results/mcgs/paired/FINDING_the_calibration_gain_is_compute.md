# The overconfidence fix is simulations, not worlds

## The three arms

200 paired games each, same seed, same world-seed stream, same opponent panel, same seats, same
decision budget, `fixed` protocols crossing at 96 simulations per decision.

| arm | K | sims/decision | field score | Wilson 95% | overconfidence | Brier | log-loss | ECE |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| `paired_k1` | 1 | 12 | 0.1156 | [0.078, 0.168] | 32.3 pp | 0.29397 | 3.613 | 0.345 |
| `paired_k8` | 8 | 96 | 0.1650 | [0.120, 0.223] | 20.5 pp | 0.17224 | 0.833 | 0.205 |
| `paired_k1_c96` | **1** | **96** | 0.1231 | [0.084, 0.177] | **22.2 pp** | **0.17370** | **0.599** | 0.222 |

## The decomposition

The `fixed_per_world` comparison that produced c022's headline calibration result confounds two
things: `paired_k8` has eight worlds **and** eight times the simulations. `paired_k1_c96` holds
the simulations and removes the worlds.

| step | what changes | ΔBrier | Δlog-loss | Δoverconfidence |
|---|---|---:|---:|---:|
| `paired_k1` → `paired_k1_c96` | **simulations only**, 12 → 96 | **−0.1203** | **−3.014** | **−10.1 pp** |
| `paired_k1_c96` → `paired_k8` | **worlds only**, 1 → 8 at 96 sims | −0.0015 | **+0.234** | −1.7 pp |
| `paired_k1` → `paired_k8` | both, the original comparison | −0.1217 | −2.780 | −11.8 pp |

**98.8% of the Brier improvement is compute.** The ensemble contributes 1.2%, which is far inside
run-to-run variation, and on log-loss the ensemble is *worse* at matched compute — 0.599 becomes
0.833.

Field score tells the same story with less resolution: `paired_k8` is 4.2 pp above `paired_k1_c96`,
their Wilson intervals overlap, and the measured four-arm K=1 replication spread is 5.0 pp.

## What this does and does not overturn

**It does not overturn the c021 finding.** c021's single-determinization search really did predict
root wins near 96% against poor outcomes, and this contract reproduced overconfidence of 32.3 pp
at a comparable budget. That defect is real.

**It overturns the proposed mechanism for fixing it.** `CONTRACT §0` asked for the "closest legal
PTCG equivalent" of the source's re-determinization, on the premise that sampling one hidden world
and searching it deeply is what produces the overconfidence. At 200 paired games the evidence says
otherwise: searching *the same single world* eight times harder recovers essentially all of the
calibration, and adding seven more worlds at equal total cost adds nothing measurable.

**Why more simulations in one world helps.** At 12 simulations a root action's value rests on a
handful of rollouts, so the estimate is extreme by variance alone — the arm predicts 0.478 against
a 0.155 base rate. At 96 the within-world estimate regresses toward that world's truth, and the
predicted probability falls to 0.367. The ensemble attacks a *different* error — disagreement
between worlds — and that error turns out to be small next to the sampling noise it was competing
with.

**The residual, and a caveat added 2026-07-31 after the M08 remeasurement.** Both 96-simulation
arms remain ~21 pp overconfident with negative Brier skill. The explanation below cites the
PRE-D13 ceiling, and the post-D13 remeasurement moved it substantially — root-only optimism
0.201 → 0.6003, with the root and opposing seats effectively swapping. See
`../calibration/M08_CEILING_REMEASUREMENT.md`: the explanation of the residual is therefore
**pending**, while the decomposition above — which compares three measured arms and does not
reference the ceiling at all — is unaffected. The original text follows.

`PREREGISTERED_AGGREGATION.json`'s `calibration_target_M08` measured that floor before any sweep
ran: ~9 pp of irreducible rollout
optimism at the root plus a within-world selection term that compounds with depth, of which
"cross-world root aggregation attacks it only at the root". That prediction stands. What did not
survive is the expectation that the reducible part was large.

## Consequences for the recorded statuses

- `MCGS_HIDDEN_INFO`'s requirement *"the calibration gain is attributable to K rather than to
  compute"* is **NOT met**. The status is `PARTIAL`, and the requirement it fails is named in
  `STATUS.md` rather than absorbed into prose.
- The requirement *"K>1 does not regress external field performance beyond noise"* still holds:
  `paired_k8` sits above every K=1 replication.
- `M08`'s registered pass condition — *"K>1 must reduce the gap ... relative to the K=1 arm on
  the SAME decisions and seeds"* — was written against `paired_k1` at 12 simulations, and is met
  on those terms. It is reported as met **and** as uninformative, because the control shows the
  reduction is not attributable to K. The threshold is not moved after the fact; the reading is
  qualified by a measurement the threshold did not anticipate.

## Why this arm existed at all

It was not registered in the original sweep plan. It was added at 19:30 on 2026-07-30, after the
paired arms landed and **before** any attribution claim was written, because the `fixed_per_world`
protocol makes K and compute vary together and no result from it can separate them. It could only
ever make the contract's headline weaker, which is the reason it was worth running.

It also converts the paired arms into the compute-controlled `fixed_total` comparison at 200
games — the protocol the 32-game sweep could not resolve — because `fixed_per_world` at 12/world
and `fixed_total` at 96 are the same configuration when K=8.

## The measurement this leaves open

Every number here is at 96 simulations per decision. `M11_SOURCE_TIMING.md` measured the source's
own schedule at a **median of ~600**, and the two regimes need not behave alike: between-world
disagreement is what the ensemble corrects, and how that scales with depth is unmeasured. A
K=1 vs K=8 pair at the source's schedule costs the same wall clock at either K, because the clock
is the budget and K divides it. That is the single measurement most likely to change this
conclusion, and it has not been made.

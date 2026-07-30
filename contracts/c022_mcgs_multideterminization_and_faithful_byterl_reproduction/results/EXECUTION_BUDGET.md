# Execution budget and the cut order

Written **before** the budget is under pressure, because a cut order decided later — with a
half-finished sweep and a clock — is a judgment call that will bend toward whatever is nearly
done. This file makes executing it mechanical.

`CONTRACT.md §5`: "Do not invent an open-ended overnight run." Every item below is a bounded
block with a named parameter set.

## Measured throughput

From the arms actually run, not estimated:

| quantity | value | source |
|---|---|---|
| MCGS simulation cost, unloaded | 52 ms/sim/worker | `hardware/contention_tests.json` |
| MCGS simulation cost, under ByteRL load | 71 ms/sim/worker | same |
| one 40-game arm at 192 sims/decision, nproc 14, loaded | ~44 min | `ft_k1`, 13:57→14:41 |
| ByteRL throughput | ~68 decisions/s at 2 actors | `smoke_br3d` |

## The chain, in the contract's mandated order

`CONTRACT.md §5` fixes the order; the only freedom is scale.

| # | item | scale | est. | runs alone? |
|---|---|---|---|---|
| 1 | M04 identity | done | — | — |
| 2 | fixed-total K sweep | 4 arms × 40 games | ~3 h | no |
| 3 | fixed-per-world K sweep | 4 arms × 40 games | ~3 h | no |
| 4 | frozen-decision stability (M09/M10) | 500 decisions × 4 K × 5 repeats | ~1 h | no |
| 5 | paired arms for the shortlisted K | 2 arms × 200 games | ~2.5 h | no |
| 6 | unrestricted source-timing arm (M11) | 20 games at 15 s/10 s | ~1 h | **yes** |
| 7 | Kaggle deploy arm (M12) | 40 games | ~45 min | **yes** |
| 8 | ByteRL conformance BR0→BR3 | 5 × 40k decisions | ~2 h | pre-b2 rungs **yes** (D18) |
| 9 | ByteRL controlled rungs | 5 × 120k decisions | ~5 h | pre-b2 rungs **yes** (D18) |
| 10 | BR3 fixed-deck decisive | 3,607,599 decisions | ~4 h | no (concurrent) |
| 11 | BR3 end-to-end decisive | 3,607,599 decisions | ~5 h | no (concurrent) |

### Amendment 19:25 — D18: the pre-b2 rungs are latency-sensitive

The "no (concurrent)" on items 8 and 9 was written before D18 and is measurably wrong for the
**BR0, BR1 and BR1.5** rungs. Their subject matter is an unbounded queue's throughput imbalance,
and that imbalance is the ratio of two throughputs — so competing load changes the number being
reported. `ctrl_BR0` ran under `paired_k8` and its learner ramped from 1.24 to 4.60 updates/s as
that arm drained, against a flat 11.4 for the clean `ctrl_BR1`.

The line is drawn at the **bounded blocking FIFO**, not at the ByteRL/MCGS boundary:

| rungs | queue | contention-tolerant? | why |
|---|---|---|---|
| BR0, BR1, BR1.5 | unbounded | **no — must run alone** | ratio, queue age and policy lag are load measurements |
| BR2, BR3 | bounded, blocking | yes | actors block when full; ratio pinned at ~1.02 under every load tested |

Concretely: MCGS work may overlay BR2/BR3 and the decisive arms, and may not overlay BR0/BR1/BR1.5.
Latency-bounded MCGS arms (items 6, 7, 13) still require a quiet machine in both directions.
`ctrl_BR0` is re-queued as a clean re-run.
| 12 | transfer noise floor + T1/T2 | 3 + 2 arms × 200 games | ~3 h | no |
| 13 | final panel | registered candidates | ~2 h | **yes** |
| 14 | package, source capture, reports | — | ~1 h | — |

Items 8–11 run concurrently with 2–5 and 12, which is what the concurrency decision bought.
The MCGS chain is therefore the critical path.

## Cut order, fixed now

Cut from the **bottom of this list up**. Each row states exactly what changes, so no judgment is
required at the time.

| order | cut | parameter change | what is lost | why it is cuttable |
|---|---|---|---|---|
| 1 | **BR3 end-to-end scale** | `MATCHED_DECISIONS` for `decisive_e2e` → whatever the block affords | the E2E arm falls short of the matched budget | `DECISION_RULES §3` names `BYTERL_SCALE=COMPUTE_LIMITED` an EXPECTED outcome. `BYTERL_E2E=PARTIAL` for "merely generating legal diverse decks" is an explicitly permitted status. Fidelity is unaffected — it is a probe property, not a scale property. |
| 2 | **BR3 fixed-deck scale** | same for `decisive_fixed` | the fixed-deck arm falls short | same. `TRAINING_AND_EVALUATION §2` orders fixed-deck FIRST, so it is cut second. |
| 3 | **robust-LCB secondary arm** | drop `MCGS_MULTI_DET_ROBUST_LCB` from the panel | the one `ALGORITHMIC_ADAPTATION` goes unevaluated as a *selector* | it is already computed for every decision from the same raw per-world statistics, so its ablation survives as an offline comparison; only the played-arm evaluation is lost. `A3` calls it "an explicitly adapted secondary arm". |
| 4 | **unrestricted source-timing arm** | record the blocker instead | M11 has no executed arm | `PROBE_MATRIX M11` says "executes **or exact blocker recorded**". The blocker would be recorded honestly: a 15 s/10 s schedule over ~46 decisions per game is ~10 min of search per game per side, and 20 games is ~7 h alone. |
| 5 | **ByteRL controlled rungs** | drop step 9 | adjacent-rung attribution rests on conformance runs only | weakest evidence loss, but it is evidence `TRAINING_AND_EVALUATION §2` explicitly asks for, so it is cut before nothing else remains. |

## Never cut

| item | why |
|---|---|
| the **200-game paired arms** | `TRAINING_AND_EVALUATION §5` names ≥200 paired games as the minimum causal evidence for a shortlisted K, and `MCGS_HIDDEN_INFO=PASS` requires K>1 not to regress external performance beyond noise. Without them the primary branch cannot reach PASS. At 40 games a Wilson interval spans ~15 points and resolves nothing. |
| **either fidelity gate** | `MANDATORY_IMPLEMENTATION C` forbids transfer before both. Both are probe properties and cost minutes, not hours. |
| the **transfer noise floor** | `DECISION_RULES §4` defines a pass as an improvement beyond measured noise. Without the denominator there is no claim to make, only a number. |
| **game accounting and the validity gates** | these are what make every other number mean what it says. |
| the **final panel running alone** | it is wall-clock sensitive and the contention measurement showed load alone moves a field score by 10 points. |

## What a cut is NOT permitted to do

- reduce game counts below the registered minimum and report the comparison anyway;
- drop an arm after seeing its result;
- relax a preregistered threshold;
- convert a compute shortfall into a method failure. `FIDELITY_RULES §5` is explicit: "Do not
  convert undertraining into method failure."

## User ruling on when to cut — 2026-07-30 ~16:45

Asked whether to apply the compressions (transfer at 96 simulations, skipping the unrestricted
timing arm under M11's "or exact blocker recorded", cutting end-to-end scale), the user ruled:

> "no, make sense to compress only if we reach midnight, otherwise it's fine as it is"

So:

```text
until 00:00   run at full registered scale. Cut nothing.
at   00:00    assess against this table. If the remaining chain does not project to finish in
              a reasonable window, apply the cut order from the top down, recording each cut
              and its reason in this file at the time it is taken.
```

### How a scale cut is recorded — written 19:55, before any cut is taken

Cuts 1 and 2 stop a decisive arm at "whatever the block affords". That phrasing is only honest
if the achieved figure is the right one, so the procedure is fixed here rather than decided while
looking at a half-trained arm:

1. The arm is stopped, not killed mid-write: `--checkpoint-every 400` means the latest checkpoint
   is at most 400 updates old, and that checkpoint is the one evaluated.
2. The achieved exposure reported is **`produced_decisions`**, not `consumed_decisions`. The
   matched budget is defined in `byterl/budget/c021_matched_budget.json` as "total environment
   decisions", which is the actor-side quantity. `--target-decisions` gates on the learner-side
   counter, and at BR3's measured production/consumption ratio of 1.023 the two are within 2.3%
   — so a completed arm satisfies the budget either way, but a STOPPED arm must report the
   counter the budget is defined in.
3. The report states `produced_decisions / 3,607,599` as a fraction, in the same sentence as any
   claim about that arm's strength. `FIDELITY_RULES §5`: "Do not convert undertraining into
   method failure."
4. The stop time and the reason (`schedule`, never a result) go in this file at the moment of the
   cut.

This is a **schedule** trigger, not a results trigger. Nothing about what has been measured by
midnight may influence which items get cut — the cut order was fixed before any of it existed,
and a cut taken because an arm looked disappointing would be exactly the gate-shopping the order
exists to prevent.

## Status

Recorded 2026-07-30 at 14:50, revised 16:45, 20:55.

| item | state at 20:55 |
|---|---|
| 2, 3 (K sweeps, 32 games) | **complete** — a shortlist; established nothing on field score |
| 4 (frozen-decision stability) | queued for the concurrent block |
| 5 (**200-game paired arms**) | **complete and analysed.** Brier 0.294 → 0.172, log-loss 3.61 → 0.83, overconfidence 32.3 → 20.5 pp. Field 0.1156 → 0.1650 with OVERLAPPING Wilson intervals against a 5.0 pp four-arm replication spread: no field claim |
| 5b (`paired_k1_c96`, compute-matched) | queued — added because `fixed_per_world` confounds K with 8x simulations |
| 6 (M11 unrestricted) | **EXECUTED** at 8 games / 279 decisions. The 1 h vs 7 h contradiction in this file is resolved: parallel efficiency on the median is 0.97, so a 20-game arm is ~41 min, and the 7 h figure was a serial extrapolation. The 20-game arm was **not run** — a scope decision at 21:15 with reasons, recorded in `M11_SOURCE_TIMING.md`, not the cut order firing. Its only additional output is a field score that at 20 games spans ~35 points against a measured 5.0 pp floor, and none is claimed |
| 7 (M12 deploy) | queued behind the probe, at c021's measured 90 s / 0.9 s / 0.7 s clock |
| 8 (conformance) | **superseded** — its BR1.5 predates D17 and its BR2/BR3 predate D19. The controlled ladder at 120k decisions subsumes it; not re-run, and 30 minutes of exclusive machine saved |
| 9 (controlled rungs) | **BR0, BR1, BR1.5 complete** on one commit. BR2/BR3 deferred to the concurrent block (D18: bounded queue, load-invariant) |
| 10, 11 (decisive arms) | launch after the exclusive block |
| 12 (transfer) | noise floor complete (3 arms, 5.0 pp spread); T1/T2 gated on both fidelity gates |
| 13 (final panel) | tool written; **count-budgeted**, so it shares the machine rather than needing it |
| 14 (package, reports) | statuses computed from artifacts; validator at 19 checks |

**Nothing has been cut.** The 00:00 trigger has not fired.

### Projection recorded at 23:01, before the trigger

Measured rates under the four-way concurrent block, not estimates:

| arm | decisions at 23:01 | rate | projected at the 23:50 stop |
|---|---:|---:|---|
| `br3_fixed_deck` | 98,155 | 29.6/s | 184,369 = **5.1%** of 3,607,599 |
| `br3_end_to_end` | 115,211 | 34.5/s | 215,437 = **6.0%** of 3,607,599 |

Both arms will therefore be `COMPUTE_LIMITED`, which `DECISION_RULES §3` names as the EXPECTED
outcome when fidelity passes and paper scale is not approached. The 23:50 stop is the recorded
cut procedure executing — stop on a checkpoint, report `produced_decisions` as a fraction, log
`schedule` as the reason — and is taken ten minutes before midnight for the mechanical reason
that the arms need that time to write manifests and run their evaluations. It is cuts 1 and 2
of the fixed order, in the fixed order, for the reason the order anticipated.

**What was NOT traded away to buy those percentages.** Reallocating the compute held by
`paired_k1_c96`, the upper ladder rungs, the fidelity runs and the panel would have moved the
decisive arms from ~5% to perhaps ~8% of the matched budget, which converts no status. Those
four items each convert a `PARTIAL` or `NOT_RUN` status to a decided one. The allocation follows
from that, not from the clock.

Also worth recording, because it is the b2 property under exactly the conditions that would
break an unbounded queue: throughout the four-way contention both decisive arms held
`queue_occupancy` at the 48-unroll cap, `policy_lag` under 8, and a production/consumption ratio
of **1.02** — at roughly 20% of their clean throughput. D18 showed the pre-b2 ratio moving from
41.9 to 12.1 with load; the b2 ratio does not move.

### Schedule costs absorbed, and where they came from

Every one is a defect the pre-committed bounds caught, not a planning miss:

| cost | cause |
|---|---|
| ~2.5 h | three sweep arms discarded for D14 (per-K compute overhead) and the guard-sets-arm-duration correction |
| ~40 min | D17 — the B1.5 rung was a declared flag no implementation read, so the ladder was relaunched |
| ~35 min | D19 — the B06 check compared the learner against μ, which D17 correctly made uniform; ladder relaunched again |
| ~22 min | D20 — B06 ran once in 556 policy versions; the ladder was restarted so all five rungs come from one commit |

That is roughly four hours spent on four checks that were reporting success while verifying
nothing. None of it was avoidable by planning; all of it was found by looking at a number that
did not fit.

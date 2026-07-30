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
| 8 | ByteRL conformance BR0→BR3 | 5 × 40k decisions | ~2 h | no (concurrent) |
| 9 | ByteRL controlled rungs | 5 × 120k decisions | ~5 h | no (concurrent) |
| 10 | BR3 fixed-deck decisive | 3,607,599 decisions | ~4 h | no (concurrent) |
| 11 | BR3 end-to-end decisive | 3,607,599 decisions | ~5 h | no (concurrent) |
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

## Status

Recorded 2026-07-30 at 14:50, with items 2 and 8 in progress and nothing yet cut.

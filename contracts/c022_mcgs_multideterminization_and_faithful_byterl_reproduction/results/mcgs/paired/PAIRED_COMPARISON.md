# The 200-game paired comparison

`TRAINING_AND_EVALUATION §5` requires at least 200 paired games before a six-point effect may be claimed. These are those games. The 32-game K sweep was a shortlist and established nothing on field score -- `NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` showed every one of its K effects sitting inside a single replication difference.

**Validity gates: PASS**  (exclusion spread 0.5 pp, bound 8 pp)

## Arms

| arm | K | protocol | sims/decision | games | completed | abandoned | field score | Wilson 95% |
|---|---:|---|---:|---:|---:|---:|---:|---|
| `paired_k1` | 1 | fixed_per_world | 12.0 | 200 | 199 | 1 | 0.1156 | [0.0783, 0.1675] |
| `paired_k8` | 8 | fixed_per_world | 96.0 | 200 | 200 | 0 | 0.165 | [0.12, 0.2227] |

## The reference: what two identical runs differ by

4 arms, K=1, fixed_per_world, 12 simulations/world, 200 games, decision budget 50. The seed is the only difference, and the environment redraws its games regardless.

| arm | seed | field score | role |
|---|---:|---:|---|
| `noise_k1_s90210` | 90210 | 0.125 | registered noise-floor arm |
| `noise_k1_s40031` | 40031 | 0.135 | registered noise-floor arm |
| `noise_k1_s71877` | 71877 | 0.085 | registered noise-floor arm |
| `paired_k1` | 90210 | 0.1156 | paired control; repeats seed 90210, so also a replication |

mean **0.1152**, range 0.085–0.135 (**5.0 pp**), sample sd **0.0216**.

This is the denominator for every field-score statement below. It is measured, not assumed, and it is the reason a 5-point difference between two arms is not a result.

## Field score

| arm | field score | Wilson 95% | Δ vs floor mean | exceeds all replications? | position |
|---|---:|---|---:|---|---:|
| `paired_k1` | 0.1156 | [0.0783, 0.1675] | 0.04 pp | no (1/4) | t = 0.017 |
| `paired_k8` | 0.165 | [0.12, 0.2227] | 4.98 pp | yes (4/4) | t = 2.062 |

`paired_k8` scores 0.165 against `paired_k1`'s 0.1156, a difference of 4.94 pp. The two Wilson intervals [0.0783, 0.1675] and [0.12, 0.2227] OVERLAP, and the K=1 replication set spans 5.0 pp on its own. **No improvement in field score is claimed.** What the arms do establish is the condition `MCGS_HIDDEN_INFO` actually needs: K>1 does not regress external performance -- the K=8 point estimate is above every one of the 4 K=1 replications, not below them.

The compute-matched control `paired_k1_c96` has not run. Until it does, this pair confounds K with an 8x simulation budget and no part of it is attributable to the ensemble.

## Calibration (M08)

Per DECISION, not per game: n is in the thousands rather than 200, which is why the calibration comparison can resolve what the field score cannot.

| arm | n | mean predicted | base rate | overconfidence | Brier | Brier (constant baseline) | skill | log-loss | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `paired_k1` | 6478 | 0.4783 | 0.1553 | 32.3 pp | 0.29397 | 0.13118 | -1.241 | 3.61279 | 0.3449 |
| `paired_k8` | 7680 | 0.3824 | 0.1779 | 20.5 pp | 0.17224 | 0.14623 | -0.1779 | 0.83287 | 0.2045 |

K=8 reduces Brier from 0.29397 to 0.17224 (Δ -0.12173), log-loss from 3.61279 to 0.83287 (Δ -2.7799), expected calibration error from 0.3449 to 0.2045, and overconfidence from 32.3 pp to 20.5 pp.

**M08's registered condition is met.** It asked for a reduction in the gap between predicted win probability and realised outcome, measured as Brier and log-loss relative to K=1. The Brier improvement is 3.2x the 0.0377 ΔBrier between the two accidentally-replicated 32-game arms, and the log-loss improvement is 11x the 0.244 seen there. It also replicates the shortlisted effect out of sample: the 32-game `fixed_per_world` K=8 arm showed ΔBrier −0.105 and Δlog-loss −2.45, and these 200-game arms show -0.122 and -2.78.

**And both arms remain worse than a constant predictor at the base rate.** Brier skill is -1.241 at K=1 and -0.1779 at K=8: negative in both cases. The ensemble makes the search's stated belief far less badly calibrated without making it informative. Saying only that Brier improved would be true and misleading, so both are reported here rather than in a footnote. M08's threshold is NOT retightened to require positive skill -- moving a preregistered target after seeing the number is the error `PREREGISTERED_AGGREGATION.json` forbids, and it forbids it in both directions.

## World disagreement (M09)

| arm | K | modal agreement | unanimous | distinct best actions | sd of selected value |
|---|---:|---:|---:|---:|---:|
| `paired_k1` | 1 | 1.0 | 1.0 | 1.0 | None |
| `paired_k8` | 8 | 0.6078 | 0.1292 | 2.9079 | 0.2274 |

At K=1 these are 1.0 by construction -- one world always agrees with itself -- and the row is kept only so the table cannot be misread as a measurement.

## Starvation control

| arm | world records | sims/world | expanded actions/world | worlds expanding ≤1 action |
|---|---:|---:|---:|---:|
| `paired_k1` | 397 | 12.0 | 4.07 | 0.0 |
| `paired_k8` | 3200 | 12.0 | 4.0 | 0.0 |

Under `fixed_per_world` every world gets the same 12 simulations at every K, so starvation is not a competing explanation for anything in these arms. The column is reported because it *is* a competing explanation under `fixed_total`, and a reader comparing the two protocols needs to see that it was checked rather than assumed.

## Threats to this comparison

### These are not literally the same decisions

M08's wording is "relative to the K=1 arm on the SAME decisions and seeds". The arms share seed 90210, the same world-seed stream, the same opponent panel, the same seats, the same game count and the same decision budget. They do **not** share games: the `cabt` environment exposes no seed, and the shuffle, prize assignment and coin flips are drawn inside the native engine on every run (`NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` demonstrates this with two scripted deterministic agents producing different winners under identical Python seeds). The visible consequence is that the calibration sets differ in size — 6,478 decisions against 7,680. There is no fix available in this environment: the frozen-decision set used for M09/M10 replays identical decisions but has no realised outcome, so it cannot supply a Brier score. What was matched is stated above; what could not be matched is stated here rather than left for a reader to discover from the row counts.

### K is confounded with compute under fixed_per_world

At 12 simulations per world, K=8 spends 96 simulations per decision and K=1 spends 12. An improvement could be the ensemble or could be 8x the search. The `paired_k1_c96` arm — K=1 at 96 simulations per decision — is the control that separates them, and because `fixed_per_world` 12/world at K=8 is arithmetically identical to `fixed_total` 96 at K=8, adding it makes these arms the compute-controlled `fixed_total` comparison at 200 games, which is the protocol the 32-game sweep could not resolve. **It has not run yet, and until it does the attribution is open.**

### The ensemble is not the source's own ensemble executing

`FIDELITY_RULES §3` fixes the K-session ensemble as `LEGAL_INFORMATION_ADAPTER`. The official archive contains `AggregateDeterminizations`, `PickDeterminization` and `GenerateDeterminizationsAtOnce`, but `NodeConfig.PIMC = false` and the `determinizations` field is never assigned, so that path is unreachable in the shipped configuration. The aggregation rule executed here is a port of the source's own aggregation; the K sessions that feed it are not the source running. Nothing in this report should be read as the 2019 system's measured behaviour.


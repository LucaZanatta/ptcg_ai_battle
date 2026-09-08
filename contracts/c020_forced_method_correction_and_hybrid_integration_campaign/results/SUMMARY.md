# c020 — Forced Method Correction and Hybrid Integration Campaign

**Status: PARTIAL** — the code and evidence campaign is substantially executed, but a floor, semantic requirement, competitive gate or submission is missed (CONTRACT §14)

Parent `a1d322e291e5`, branch `contract/c020_forced_method_correction_and_hybrid_integration_campaign`, head `653bd52784eb`.
Controls frozen at `a1d322e291e5` before any c020 code ran.

## 1. Statuses, kept separate (§14)

| dimension | verdict |
|---|---|
| execution | {"mcts_floors_met": true, "byterl_floors_met": true, "hybrid_floors_met": true} |
| method fidelity | {"mcts": "PASS", "byterl": "PASS", "hybrid": "PASS"} |
| semantic | {"mcts": "PASS", "byterl": "PASS", "hybrid": "PASS", "common": "PASS"} |
| packages | 3 built |
| submissions | none |

## 2. Corrected MCTS floors

| floor | actual | required | |
|---|---|---|---|
| live searched decisions | 19,758 | 5,000 | met |
| real search_step expansions | 11,365,961 | 500,000 | met |
| decisions with 4 legal determinizations | 19,758 | 1,000 | met |
| complete sampled tree traces | 402 | 100 | met |
| recorded override opportunities | 19,758 | 500 | met |
| common-panel baseline vs corrected-MCTS games | 800 | 800 | met |
| conservative-override ablation games | 2,480 | 200 | met |

## 3. Corrected ByteRL floors

| floor | actual | required | |
|---|---|---|---|
| actual simulator training games | 104,000 | 100,000 | met |
| optimizer steps | 97,649 | 30,000 | met |
| complete corrected OSFP learning periods | 8 | 6 | met |
| immutable historical additions | 5 | 2 | met |
| games involving historical checkpoints | 36,151 | 2,000 | met |
| evaluation games across milestones/panels | 1,319 | 1,000 | met |

Mid-game unrolls carrying stored recurrent state: **1.0**
(c019 reset these to zero — audit #10).

## 4. Hybrid floors

| floor | actual | required | |
|---|---|---|---|
| H0-H4 all execute at smoke scale | 5 | 5 | met |
| final-panel games per promotable mode | 200 | 200 | met |

Prior admission: **False**. Value admission: **False**.

## 5. Competitive results (frozen panel)

| candidate | field | delta vs baseline (pts) |
|---|---|---|
| C019_PIMC_PUCT_CONTROL | 0.45 | -13.4 |
| C019_BYTERL_CONTROL | 0.06 | -52.4 |
| C020_CORRECTED_MCTS | 0.4275 | -15.6 |
| C020_CORRECTED_BYTERL | 0.275 | -30.9 |
| C020_H0 | 0.42 | -16.4 |
| C020_H1 | 0.4875 | -9.6 |
| C020_H2 | 0.445 | -13.9 |
| C020_H3 | 0.42 | -16.4 |
| C020_H4 | 0.465 | -11.9 |

## 6. Validator

41/42 checks, 0 critical
failures, 0 submission blockers,
**35 checks carrying a negative control**, and
0 broken checks.

Audit findings #16/#17 are the reason for that middle number: the c019 validator passed while
every semantic defect was live, because it checked that methods existed. Here each semantic check
injects the c019 behaviour as a fixture and must reject it; a check whose injection does not trip
it is reported BROKEN rather than passing.

## 7. Decision board

| role | id | basis |
|---|---|---|
| CHAMPION | dragapult | externally confirmed control; no c020 candidate has beaten it on external evidence |
| CHALLENGER | BASELINE_OFFICIAL_MEGA_LUCARIO | accepted submission 55011215; strongest measured candidate on the c020 frozen panel unless a c020 candidate cl |
| DIAGNOSTIC | C020_CORRECTED_MCTS | semantically corrected; -15.6 field points vs the frozen baseline |
| DIAGNOSTIC | C020_CORRECTED_BYTERL | semantically corrected; -30.9 field points vs the frozen baseline |
| DIAGNOSTIC | C020_H0 | semantically corrected; -16.4 field points vs the frozen baseline |
| DIAGNOSTIC | C020_H1 | semantically corrected; -9.6 field points vs the frozen baseline |
| DIAGNOSTIC | C020_H2 | semantically corrected; -13.9 field points vs the frozen baseline |
| DIAGNOSTIC | C020_H3 | semantically corrected; -16.4 field points vs the frozen baseline |
| DIAGNOSTIC | C020_H4 | semantically corrected; -11.9 field points vs the frozen baseline |
| ARCHIVE | C019_PIMC_PUCT_CONTROL | separate-tree PIMC with a four-feature objective; retained as the named control c020 is measured against |
| ARCHIVE | C019_BYTERL_CONTROL | pooled board, fragment multi-select, reset mid-game recurrent state, cross-period OSFP accounting; retained as |

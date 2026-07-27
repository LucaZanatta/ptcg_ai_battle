# c020 — Forced Method Correction and Hybrid Integration Campaign

**Status: PARTIAL** — the code and evidence campaign is substantially executed, but a floor, semantic requirement, competitive gate or submission is missed (CONTRACT §14)

Parent `a1d322e291e5`, branch `contract/c020_forced_method_correction_and_hybrid_integration_campaign`, head `1f16f58f47ef`.
Controls frozen at `a1d322e291e5` before any c020 code ran.

## 1. Statuses, kept separate (§14)

| dimension | verdict |
|---|---|
| execution | {"mcts_floors_met": false, "byterl_floors_met": false, "hybrid_floors_met": false} |
| method fidelity | {"mcts": "PASS", "byterl": "PASS", "hybrid": "PASS"} |
| semantic | {"mcts": "PASS", "byterl": "PASS", "hybrid": "PASS", "common": "PASS"} |
| packages | 1 built |
| submissions | none |

## 2. Corrected MCTS floors

| floor | actual | required | |
|---|---|---|---|
| live searched decisions | 544 | 5,000 | **MISSED** |
| real search_step expansions | 232,960 | 500,000 | **MISSED** |
| decisions with 4 legal determinizations | 544 | 1,000 | **MISSED** |
| complete sampled tree traces | 48 | 100 | **MISSED** |
| recorded override opportunities | 544 | 500 | met |
| common-panel baseline vs corrected-MCTS games | 0 | 800 | **MISSED** |
| conservative-override ablation games | 0 | 200 | **MISSED** |

## 3. Corrected ByteRL floors

| floor | actual | required | |
|---|---|---|---|
| actual simulator training games | 4,320 | 100,000 | **MISSED** |
| optimizer steps | 5,144 | 30,000 | **MISSED** |
| complete corrected OSFP learning periods | 0 | 6 | **MISSED** |
| immutable historical additions | 0 | 2 | **MISSED** |
| games involving historical checkpoints | 0 | 2,000 | **MISSED** |
| evaluation games across milestones/panels | 0 | 1,000 | **MISSED** |

Mid-game unrolls carrying stored recurrent state: **None**
(c019 reset these to zero — audit #10).

## 4. Hybrid floors

| floor | actual | required | |
|---|---|---|---|
| H0-H4 all execute at smoke scale | 5 | 5 | met |
| final-panel games per promotable mode | 0 | 200 | **MISSED** |

Prior admission: **False**. Value admission: **False**.

## 5. Competitive results (frozen panel)

| candidate | field | delta vs baseline (pts) |
|---|---|---|
| C019_PIMC_PUCT_CONTROL | None | None |
| C019_BYTERL_CONTROL | None | None |
| C020_CORRECTED_MCTS | None | None |
| C020_CORRECTED_BYTERL | None | None |
| C020_H0 | None | None |
| C020_H1 | None | None |
| C020_H2 | None | None |
| C020_H3 | None | None |
| C020_H4 | None | None |

## 6. Validator

34/41 checks, 0 critical
failures, 0 submission blockers,
**33 checks carrying a negative control**, and
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
| DIAGNOSTIC | C020_CORRECTED_MCTS | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_CORRECTED_BYTERL | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_H0 | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_H1 | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_H2 | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_H3 | not yet evaluated on the frozen panel |
| DIAGNOSTIC | C020_H4 | not yet evaluated on the frozen panel |
| ARCHIVE | C019_PIMC_PUCT_CONTROL | separate-tree PIMC with a four-feature objective; retained as the named control c020 is measured against |
| ARCHIVE | C019_BYTERL_CONTROL | pooled board, fragment multi-select, reset mid-game recurrent state, cross-period OSFP accounting; retained as |

# c022 statuses

Each status is computed from artifacts by `tools/c022_status.py`, and each requirement names the file it was decided from. `DECISION_RULES §6`: "Do not compress these into a misleading single PASS."

**A requirement with no artifact is `NOT_RUN`, never met.** One unmet requirement makes the status `PARTIAL` and the report names it.

| status | value |
|---|---|
| `SOURCE_FIDELITY` | **PASS** |
| `MCGS_HIDDEN_INFO` | **PARTIAL** |
| `MCGS_COMPETITIVE` | **PARTIAL** |
| `BYTERL_REFERENCE_FIDELITY` | **PASS** |
| `BYTERL_FIXED_DECK` | **PARTIAL** |
| `BYTERL_E2E` | **PARTIAL** |
| `BYTERL_SCALE` | **COMPUTE_LIMITED** |
| `TRANSFER` | **NOT_RUN** |
| `PACKAGE` | **NOT_RUN** |
| `SUBMISSION` | **NOT_RUN** |
| `OVERALL` | **PARTIAL** |

2 of 10 statuses PASS; 3 have not run. The honest outcomes `DECISION_RULES §6` lists are combinations, not a single verdict, and this table is meant to be read as one.

## `SOURCE_FIDELITY` = PASS

*FIDELITY_RULES §1-§3*

| requirement | verdict | evidence |
|---|---|---|
| the official source is audited at anchored sites | **met** | `results/fidelity/mcgs_hidden_information_trace.jsonl` |
| frozen controls still hash to what was frozen | **met** | `results/validation_report.json V13` |
| every deviation is declared with its adaptation class | **met** | `results/fidelity/ADAPTATION_LEDGER.md` |

- **the official source is audited at anchored sites** — 33 anchored source sites and 6 structural absence claims against archive f00a54f310a8f868...
- **frozen controls still hash to what was frozen** — 37 frozen files re-hashed
- **every deviation is declared with its adaptation class** — 91 ledger rows; every deviation carries a class and a reason

## `MCGS_HIDDEN_INFO` = PARTIAL

*DECISION_RULES §2 MCGS_HIDDEN_INFO*

| requirement | verdict | evidence |
|---|---|---|
| repeated legal hidden worlds are demonstrated | **met** | `results/probes/world_probes.json` |
| aggregation / re-determinization implemented and traced | **met** | `results/mcgs/PREREGISTERED_AGGREGATION.json, paired/*_traces.jsonl` |
| c021 overconfidence is materially reduced | **met** | `results/mcgs/paired/PAIRED_COMPARISON.md` |
| K>1 does not regress external field performance beyond noise | **met** | `results/mcgs/paired/, results/transfer/noise_floor/` |
| the calibration gain is attributable to K rather than to compute | **NOT met** | `results/mcgs/paired/paired_k1_c96_summary.json` |

- **repeated legal hidden worlds are demonstrated** — 6/6 world probes pass: M01b API hidden-information constraint, M02 repeated world generation, M02b world stream determinism, M02c world seed stream independence, M03 no leakage, M03b public root identity across worlds
- **aggregation / re-determinization implemented and traced** — rule `source_sum` ported from AggregateDeterminizations; 7680 decisions traced with per-world statistics, modal agreement 0.6078
- **c021 overconfidence is materially reduced** — overconfidence 32.3 -> 20.5 pp, Brier 0.29397 -> 0.17224; c021 predicted ~96% at the root, this arm predicts 0.3824
- **K>1 does not regress external field performance beyond noise** — K=8 field 0.165 vs a K=1 replication mean of 0.1152 (spread 5.0 pp over 4 arms); Wilson [0.12, 0.2227] vs [0.0783, 0.1675]
- **the calibration gain is attributable to K rather than to compute** — Brier decomposes as: simulations only (12 -> 96 in ONE world) -0.12027, worlds only (1 -> 8 at 96 simulations) -0.00146, total -0.12173. The ensemble contributes 1.2% of the improvement, against a measured replication difference of 0.0377. Log-loss moves the WRONG way for the ensemble at matched compute (0.2338). See FINDING_the_calibration_gain_is_compute.md.

## `MCGS_COMPETITIVE` = PARTIAL

*DECISION_RULES §2 MCGS_COMPETITIVE*

| requirement | verdict | evidence |
|---|---|---|
| credibly beats the strongest frozen champion on the broad panel | **NOT met** | `results/mcgs/final_panel/panel.json` |
| the improvement exceeds measured run-to-run noise | **NOT met** | `results/mcgs/paired/, NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` |

- **credibly beats the strongest frozen champion on the broad panel** — {"bar": "BASELINE_OFFICIAL_MEGA_LUCARIO, re-run here on this panel", "bar_field_score": 0.5833, "bar_wilson95": [0.4573, 0.6994], "best_candidate": "mcgs_k1", "candidate_field_score": 0.1333, "candidate_wilson95": [0.0691, 0.2417], "delta_pp": -45.0, "intervals_separate_in_candidate_favour": false, 
- **the improvement exceeds measured run-to-run noise** — delta 4.94 pp against a measured 5.0 pp replication spread; Wilson intervals OVERLAP. DECISION_RULES §2: 'A small noisy improvement over c021 MCGS is not a competitive pass.'

## `BYTERL_REFERENCE_FIDELITY` = PASS

*DECISION_RULES §3 BYTERL_REFERENCE_FIDELITY*

| requirement | verdict | evidence |
|---|---|---|
| LSTM-256 recurrence | **met** | `results/probes/byterl_probes.json B01` |
| exact complete-action autoregression | **met** | `results/probes/byterl_probes.json B03-B05` |
| actor versions and stored recurrent starts | **met** | `results/probes/byterl_probes.json B06-B07` |
| bounded blocking FIFO and measured production/consumption | **met** | `results/probes/byterl_probes.json B08-B10` |
| exact numerical V-trace / UPGO / b3 fixtures | **met** | `results/byterl/numerical_fixtures/fixtures.json` |
| published stage-delta tests | **met** | `tests/test_c022_stage_ladder.py, results/byterl/component_analysis/` |
| recurrent replay verified at high coverage | **met** | `results/byterl/stages/fid_*_manifest.json` |
| immutable OSFP history and correct period accounting | **met** | `results/byterl/osfp/osfp_accounting.json` |
| end-to-end construction path implemented | **met** | `results/byterl/end_to_end/` |
| every reported number survives an injection-tested validator | **met** | `results/validation_report.json` |

- **LSTM-256 recurrence** — B01: None
- **exact complete-action autoregression** — B04: None
- **actor versions and stored recurrent starts** — B07: None
- **bounded blocking FIFO and measured production/consumption** — B09: None
- **exact numerical V-trace / UPGO / b3 fixtures** — 34/34 comparisons agree at 1e-05 against references transcribed independently of the implementation and of the test suite's own copies
- **published stage-delta tests** — 5 rungs, one codebase; tests/test_c022_stage_ladder.py rejects extra changes
- **recurrent replay verified at high coverage** — fid_BR0: 112 checks, coverage 1.0, failures 0; fid_BR1: 111 checks, coverage 1.0, failures 0; fid_BR1_5: 111 checks, coverage 1.0, failures 0; fid_BR2: 111 checks, coverage 1.0, failures 0; fid_BR3: 111 checks, coverage 1.0, failures 0
- **immutable OSFP history and correct period accounting** — history 4/4 after 6 periods, bounded=True, immutable=True; self-play 0.6, promotion threshold 0.55
- **end-to-end construction path implemented** — B18: None
- **every reported number survives an injection-tested validator** — 19/19 checks that ran pass, no_data=[], inert=[], undetected injections=[]

## `BYTERL_FIXED_DECK` = PARTIAL

*DECISION_RULES §3 BYTERL_FIXED_DECK*

| requirement | verdict | evidence |
|---|---|---|
| statistically credible improvement over the random floor | **NOT met** | `results/byterl/external_evaluations/` |
| a reproducible upward external trajectory | **NOT_RUN** | `results/byterl/stages/br3_fixed_deck_curve.json` |

- **statistically credible improvement over the random floor** — br3_fixed_deck 0.0703 [0.0374, 0.1282] vs floor 0.0234 [0.008, 0.0666] over 128 games; intervals OVERLAP
- **a reproducible upward external trajectory** — could not be evaluated: AttributeError: 'list' object has no attribute 'get'

## `BYTERL_E2E` = PARTIAL

*DECISION_RULES §3 BYTERL_E2E*

| requirement | verdict | evidence |
|---|---|---|
| legal, diverse deck construction | **met** | `results/byterl/end_to_end/` |
| external improvement above random / fixed weak baselines | **NOT met** | `results/byterl/external_evaluations/` |

- **legal, diverse deck construction** — None
- **external improvement above random / fixed weak baselines** — br3_end_to_end 0.0547 [0.0267, 0.1086] vs floor 0.0625 [0.032, 0.1185] over 128 games; intervals OVERLAP

## `BYTERL_SCALE` = COMPUTE_LIMITED

*DECISION_RULES §3 BYTERL_SCALE*

| requirement | verdict | evidence |
|---|---|---|
| br3_fixed_deck reaches the matched budget | **NOT met** | `results/byterl/stages/br3_fixed_deck_manifest.json` |
| br3_end_to_end reaches the matched budget | **NOT met** | `results/byterl/stages/br3_end_to_end_manifest.json` |

- **br3_fixed_deck reaches the matched budget** — produced_decisions 328,601 of 3,607,599 (9.1%); the budget is defined in ENVIRONMENT decisions, so the actor-side counter is the one reported
- **br3_end_to_end reaches the matched budget** — produced_decisions 391,305 of 3,607,599 (10.8%); the budget is defined in ENVIRONMENT decisions, so the actor-side counter is the one reported

## `TRANSFER` = NOT_RUN

*DECISION_RULES §4 TRANSFER*

| requirement | verdict | evidence |
|---|---|---|
| a measured paired run-to-run noise floor exists | **met** | `results/transfer/noise_floor/` |
| one isolated ByteRL component improves corrected MCGS beyond that noise | **NOT_RUN** | `results/transfer/arms/` |

- **a measured paired run-to-run noise floor exists** — 3 arms, spread 5.0 pp: [0.135, 0.085, 0.125]
- **one isolated ByteRL component improves corrected MCGS beyond that noise** — no transfer arm has run

## `PACKAGE` = NOT_RUN

*DECISION_RULES §5*

| requirement | verdict | evidence |
|---|---|---|
| package validation passes | **NOT_RUN** | `results/mcgs/packages/package_validation.json` |

- **package validation passes** — no package has been built or validated

## `SUBMISSION` = NOT_RUN

*DECISION_RULES §5*

| requirement | verdict | evidence |
|---|---|---|
| exact candidate identity is frozen | **NOT_RUN** | `results/mcgs/submissions/` |
| a registered credible gate passes | **NOT met** | `results/mcgs/final_panel/` |

- **exact candidate identity is frozen** — no submission decision has been recorded
- **a registered credible gate passes** — MCGS_COMPETITIVE is PARTIAL; DECISION_RULES §5 requires a credible gate to pass before submitting, and §2 says a small noisy improvement is not one


# c022 statuses

Each status is computed from artifacts by `tools/c022_status.py`, and each requirement names the file it was decided from. `DECISION_RULES §6`: "Do not compress these into a misleading single PASS."

**A requirement with no artifact is `NOT_RUN`, never met.** One unmet requirement makes the status `PARTIAL` and the report names it.

| status | value |
|---|---|
| `SOURCE_FIDELITY` | **PASS** |
| `MCGS_HIDDEN_INFO` | **PARTIAL** |
| `MCGS_COMPETITIVE` | **PARTIAL** |
| `BYTERL_REFERENCE_FIDELITY` | **PARTIAL** |
| `BYTERL_FIXED_DECK` | **NOT_RUN** |
| `BYTERL_E2E` | **PARTIAL** |
| `BYTERL_SCALE` | **NOT_RUN** |
| `TRANSFER` | **NOT_RUN** |
| `PACKAGE` | **NOT_RUN** |
| `SUBMISSION` | **NOT_RUN** |
| `OVERALL` | **PARTIAL** |

1 of 10 statuses PASS; 5 have not run. The honest outcomes `DECISION_RULES §6` lists are combinations, not a single verdict, and this table is meant to be read as one.

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
| the calibration gain is attributable to K rather than to compute | **NOT_RUN** | `results/mcgs/paired/paired_k1_c96_summary.json` |

- **repeated legal hidden worlds are demonstrated** — 6/6 world probes pass: M01b API hidden-information constraint, M02 repeated world generation, M02b world stream determinism, M02c world seed stream independence, M03 no leakage, M03b public root identity across worlds
- **aggregation / re-determinization implemented and traced** — rule `source_sum` ported from AggregateDeterminizations; 7680 decisions traced with per-world statistics, modal agreement 0.6078
- **c021 overconfidence is materially reduced** — overconfidence 32.3 -> 20.5 pp, Brier 0.29397 -> 0.17224; c021 predicted ~96% at the root, this arm predicts 0.3824
- **K>1 does not regress external field performance beyond noise** — K=8 field 0.165 vs a K=1 replication mean of 0.1152 (spread 5.0 pp over 4 arms); Wilson [0.12, 0.2227] vs [0.0783, 0.1675]
- **the calibration gain is attributable to K rather than to compute** — paired_k1_c96 has not run; under fixed_per_world K=8 also spends 8x the simulations, so no part of the improvement is yet attributable to the ensemble rather than to compute

## `MCGS_COMPETITIVE` = PARTIAL

*DECISION_RULES §2 MCGS_COMPETITIVE*

| requirement | verdict | evidence |
|---|---|---|
| credibly beats the strongest frozen champion on the broad panel | **NOT_RUN** | `results/mcgs/final_panel/panel.json` |
| the improvement exceeds measured run-to-run noise | **NOT met** | `results/mcgs/paired/, NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` |

- **credibly beats the strongest frozen champion on the broad panel** — results/mcgs/final_panel/panel.json absent -- the panel has not run
- **the improvement exceeds measured run-to-run noise** — delta 4.94 pp against a measured 5.0 pp replication spread; Wilson intervals OVERLAP. DECISION_RULES §2: 'A small noisy improvement over c021 MCGS is not a competitive pass.'

## `BYTERL_REFERENCE_FIDELITY` = PARTIAL

*DECISION_RULES §3 BYTERL_REFERENCE_FIDELITY*

| requirement | verdict | evidence |
|---|---|---|
| LSTM-256 recurrence | **met** | `results/probes/byterl_probes.json B01` |
| exact complete-action autoregression | **met** | `results/probes/byterl_probes.json B03-B05` |
| actor versions and stored recurrent starts | **NOT_RUN** | `results/probes/byterl_probes.json B06-B07` |
| bounded blocking FIFO and measured production/consumption | **NOT_RUN** | `results/probes/byterl_probes.json B08-B10` |
| exact numerical V-trace / UPGO / b3 fixtures | **met** | `results/byterl/numerical_fixtures/fixtures.json` |
| published stage-delta tests | **met** | `tests/test_c022_stage_ladder.py, results/byterl/component_analysis/` |
| recurrent replay verified at high coverage | **NOT_RUN** | `results/byterl/stages/fid_*_manifest.json` |
| immutable OSFP history and correct period accounting | **met** | `results/byterl/osfp/osfp_accounting.json` |
| end-to-end construction path implemented | **met** | `results/byterl/end_to_end/` |
| every reported number survives an injection-tested validator | **met** | `results/validation_report.json` |

- **LSTM-256 recurrence** — B01: None
- **exact complete-action autoregression** — B04: None
- **actor versions and stored recurrent starts** — probe B07 has not run
- **bounded blocking FIFO and measured production/consumption** — probe B09 has not run
- **exact numerical V-trace / UPGO / b3 fixtures** — 34/34 comparisons agree at 1e-05 against references transcribed independently of the implementation and of the test suite's own copies
- **published stage-delta tests** — 1 rungs, one codebase; tests/test_c022_stage_ladder.py rejects extra changes
- **recurrent replay verified at high coverage** — the dedicated high-coverage B06 runs have not run (D20)
- **immutable OSFP history and correct period accounting** — history 4/4 after 6 periods, bounded=True, immutable=True; self-play 0.6, promotion threshold 0.55
- **end-to-end construction path implemented** — B18: None
- **every reported number survives an injection-tested validator** — 17/17 checks that ran pass, no_data=['V14', 'V17'], inert=[], undetected injections=[]

## `BYTERL_FIXED_DECK` = NOT_RUN

*DECISION_RULES §3 BYTERL_FIXED_DECK*

| requirement | verdict | evidence |
|---|---|---|
| statistically credible improvement over the random floor | **NOT_RUN** | `results/byterl/external_evaluations/` |
| a reproducible upward external trajectory | **NOT_RUN** | `results/byterl/stages/br3_fixed_deck_curve.json` |

- **statistically credible improvement over the random floor** — br3_fixed_deck has not been evaluated
- **a reproducible upward external trajectory** — no training curve recorded for the decisive fixed-deck arm

## `BYTERL_E2E` = PARTIAL

*DECISION_RULES §3 BYTERL_E2E*

| requirement | verdict | evidence |
|---|---|---|
| legal, diverse deck construction | **met** | `results/byterl/end_to_end/` |
| external improvement above random / fixed weak baselines | **NOT_RUN** | `results/byterl/external_evaluations/` |

- **legal, diverse deck construction** — None
- **external improvement above random / fixed weak baselines** — br3_end_to_end has not been evaluated

## `BYTERL_SCALE` = NOT_RUN

*DECISION_RULES §3 BYTERL_SCALE*

| requirement | verdict | evidence |
|---|---|---|
| br3_fixed_deck reaches the matched budget | **NOT_RUN** | `results/byterl/stages/br3_fixed_deck_manifest.json` |
| br3_end_to_end reaches the matched budget | **NOT_RUN** | `results/byterl/stages/br3_end_to_end_manifest.json` |

- **br3_fixed_deck reaches the matched budget** — br3_fixed_deck has not run
- **br3_end_to_end reaches the matched budget** — br3_end_to_end has not run

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


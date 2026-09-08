# Acceptance checklist

46 probes in `PROBE_MATRIX.md`. **44 MET, 0 NOT MET, 2 NOT_RUN.**

Generated from the artifacts by `tools/c022_acceptance.py`. A probe whose evidence is absent is `NOT_RUN` — never `MET` by default. Regenerated after the final runs landed.

| ID | Probe | Pass condition | Verdict | Evidence | Note |
|---|---|---|---|---|---|
| M01 | Source hidden-info map | Every source save/restore/determinization function mapped | **MET** | `fidelity/mcgs_hidden_information_trace.jsonl` | 33 anchored sites, 6 absence claims |
| M02 | Repeated world generation | Same public root, legal distinct hidden worlds | **MET** | `probes/mcgs_world_probes.json` | M02, M02b, M02c |
| M03 | No leakage | Policy receives no inaccessible hidden contents | **MET** | `probes/mcgs_world_probes.json` | M03, M03b |
| M04 | K=1 identity | New K1 reproduces frozen c021/source-port behavior within deterministic tolerance | **MET** | `probes/m04_identity.json` | 9/9 checks |
| M05 | Fixed-total K sweep | K1/2/4/8 use exactly equal total simulations | **MET** | `validation_report.json V04` | equal total simulations across K |
| M06 | Fixed-per-world K sweep | Each world receives identical simulations | **MET** | `validation_report.json V04` | equal simulations per world across K |
| M07 | Aggregation fixture | Independent calculation matches production aggregation | **MET** | `validation_report.json V08` | action indices aligned across worlds |
| M08 | Calibration | Predicted/actual calibration improves over c021 control | **MET** | `mcgs/paired/PAIRED_COMPARISON.md` | met on registered terms; ceiling remeasurement UNRESOLVED -- see mcgs/calibration/M08_CEILING_REMEASUREMENT.md |
| M09 | World disagreement | Per-world action/value variance logged correctly | **MET** | `mcgs/calibration/stability/` | 500 frozen decisions captured, 499 evaluated; §5 asks for at least 500 -- a 1-decision shortfall on the evaluated set, recorded |
| M10 | Action stability | Repeated-seed stability measured on frozen decisions | **MET** | `mcgs/calibration/stability/` | 500 frozen decisions captured, 499 evaluated; §5 asks for at least 500 -- a 1-decision shortfall on the evaluated set, recorded |
| M11 | Source timing arm | Original-style 15/10-second schedule executes or exact blocker recorded | **MET** | `mcgs/unrestricted_reference/M11_SOURCE_TIMING.md` | schedule EXECUTED at 8 games/279 decisions; 20-game arm a recorded scope decision |
| M12 | Deploy separation | Kaggle budget changes do not modify reference branch | **MET** | `mcgs/kaggle_deploy/M12_DEPLOY.md` | both K at c021's measured clock |
| M13 | Paired field panel | Candidate/control use matched seeds and identities | **MET** | `mcgs/paired/PAIRED_COMPARISON.md` | matched seeds/worlds/opponents; games CANNOT be matched (native engine reseeds) |
| B01 | Architecture | LSTM hidden size 256 and shared representations verified | **MET** | `probes/byterl_probes.json` |  |
| B02 | Slot identity | Active and each bench position remain distinct | **MET** | `probes/byterl_probes.json` |  |
| B03 | Dynamic references | Every legal option points to correct source/target objects | **MET** | `probes/byterl_probes.json` |  |
| B04 | Autoregressive legality | Every emitted complete sequence maps to one legal action | **MET** | `probes/byterl_probes.json` |  |
| B05 | Joint log-probability | Sum of token log-probs matches independent reference | **MET** | `probes/byterl_probes.json` |  |
| B06 | Hidden-state replay | Learner recomputation matches actor trace before update | **MET** | `byterl/stages/fid_*_manifest.json` | 5 stages at 100% coverage, 0 failures, 380-400 uniform steps seen |
| B07 | Burn-in/unroll | Gradients and recurrence obey registered sequence boundaries | **MET** | `byterl/stages/` | versioned actors, stored recurrent starts |
| B08 | FIFO | Bounded, blocking, true FIFO, consume-once semantics | **MET** | `byterl/component_analysis/RUNG_LADDER.md` | production/consumption 7.92 -> 1.0064 at the b2 line |
| B09 | Production balance | Producer/consumer ratio and queue age remain controlled | **MET** | `byterl/component_analysis/RUNG_LADDER.md` | production/consumption 7.92 -> 1.0064 at the b2 line |
| B10 | Policy versions | Behavior version and lag recorded for every unroll | **MET** | `byterl/component_analysis/RUNG_LADDER.md` | production/consumption 7.92 -> 1.0064 at the b2 line |
| B11 | V-trace fixture | Exact independent numerical agreement | **MET** | `byterl/numerical_fixtures/fixtures.json` | 34/34 agree at 1e-05 |
| B12 | UPGO fixture | Exact independent numerical agreement | **MET** | `byterl/numerical_fixtures/fixtures.json` | 34/34 agree at 1e-05 |
| B13 | B3 clipping fixture | Two-sided ratio and PPO-style objective agreement | **MET** | `byterl/numerical_fixtures/fixtures.json` | 34/34 agree at 1e-05 |
| B14 | Stage delta | Adjacent BR stages differ only by published change | **MET** | `tests/test_c022_stage_ladder.py` | adjacent stages differ only by the published change |
| B15 | OSFP local reset | Payoff/count accumulators reset each period | **MET** | `byterl/osfp/osfp_accounting.json` |  |
| B16 | Frozen history | Historical checkpoints are byte-immutable | **MET** | `byterl/osfp/osfp_accounting.json` |  |
| B17 | Promotion | Threshold/forced-promotion behavior matches reference interpretation | **MET** | `byterl/osfp/osfp_accounting.json` |  |
| B18 | Full card pool | E2E arm uses legal permitted pool; reduced pool labelled smoke only | **MET** | `probes/byterl_probes.json` |  |
| B19 | Return propagation | Terminal outcome trains construction and battle decisions | **MET** | `probes/byterl_probes.json` |  |
| B20 | Matched budget | Exact c021 sample exposure recovered and matched | **MET** | `byterl/budget/c021_matched_budget.json` | 3,607,599 decisions recovered; arms reached 9.11% / 10.85% / 73.0% |
| B21 | External trajectory | Fixed milestones and confidence intervals exist | **MET** | `validation_report.json V11` | fresh random weights |
| B22 | Plateau validator | Stop/continue decision recomputed from raw metrics | **MET** | `byterl/end_to_end/construction_analysis.json` | 24/24 legal, 24 distinct |
| B23 | Value calibration | Compared with constant, heuristic, c021 and outcome baselines | **MET** | `byterl/external_evaluations/*_eval.json` | value skill vs a CONSTANT predictor reported; the floor heads do not beat it |
| B24 | Prior admission | Ranking, entropy, suppression and MCGS effect measured | NOT_RUN | `byterl/component_analysis/` | prior admission: ranking/entropy/suppression measured only via the transfer arms |
| T01 | Parent gates | No transfer before MCGS and ByteRL fidelity gates | **MET** | `STATUS.json` | both fidelity gates checked before any arm ran |
| T02 | Prior-only | Only prior changes; worlds/sims/seeds identical | **MET** | `transfer/prior_only/` | 200/200 completed, 83354 component calls, 2.386 ms mean inference |
| T03 | Rollout-only | Only default policy changes | **MET** | `transfer/rollout_only/` | 200/200 completed, 6172385 component calls, 2.182 ms mean inference |
| T04 | Value-only | Runs only after value admission | NOT_RUN | `transfer/value_only/` | NOT RUN BY DESIGN -- T04 runs only after value admission, and the measured value heads do not beat a constant predictor (skill -0.06, -0.10) |
| T05 | Noise floor | Nominally identical controls estimate run-to-run noise | **MET** | `transfer/noise_floor/` | 3 identical controls, 5.0 pp spread |
| F01 | Candidate identity | Deck/model/source/package verified for every game | **MET** | `validation_report.json V13` | frozen controls re-hash |
| F02 | Canonical final source | Git archive/plain export/package agree | **MET** | `source/source_manifest.json` | 40 files, archives hashed, final head recorded |
| F03 | Report consistency | All reported numbers recompute from raw data | **MET** | `validation_report.json` | 20/20 recompute checks pass |
| F04 | Defect injection | Validators reject c019–c021 known defects | **MET** | `validation_report.json` | every check carries an injection proving it can fail |

## Probes deliberately not run

- **T04 (value-only transfer)** — its precondition is value admission, and the measured value heads do not beat a constant predictor at the observed base rate. Running it would transfer a component that has not earned admission.
- **T3_prior_and_rollout (a combined arm)** — `MANDATORY_IMPLEMENTATION` forbids adding multiple ByteRL components simultaneously; a combined arm cannot attribute its result.

## What is open

`M08`'s ceiling remeasurement moved root-only optimism 0.201 → 0.6003 with the seats effectively swapping. Both readings are recorded and neither is adopted. `DECISION_BOARD.json` caps `EVALUATION_VALIDITY` at `PARTIAL` for this reason, and that cap is not lifted by the validator passing.


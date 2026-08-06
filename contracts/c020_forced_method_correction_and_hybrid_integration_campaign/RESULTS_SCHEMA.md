# Mandatory c020 Results and Source Schema

The results must allow line-by-line debugging. Summaries without full code and raw evidence are unacceptable.

```text
results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── EXECUTION_BUDGET.json
├── DECISION_BOARD.json
├── implementation/
│   ├── forced_change_map.md
│   ├── c019_to_c020_file_map.json
│   ├── repair_pass.md
│   └── registered_final_protocol.json
├── controls/
│   ├── control_manifest.json
│   ├── c019_control_results.json
│   └── baseline_package/
├── mcts/
│   ├── configs/
│   ├── infoset_tables/
│   ├── determinizations/
│   ├── tree_traces/
│   ├── leaf_features/
│   ├── override_logs/
│   ├── ablations/
│   ├── raw_games/
│   ├── evaluations/
│   ├── latency/
│   ├── packages/
│   └── submissions/
├── byterl/
│   ├── configs/
│   ├── schema/
│   ├── model_architecture/
│   ├── actor_unrolls/
│   ├── recurrent_states/
│   ├── multiselect_records/
│   ├── learner_logs/
│   ├── vtrace_upgo_fixtures/
│   ├── checkpoints/
│   ├── osfp/
│   │   ├── period_local_GC/
│   │   ├── payoff_tables/
│   │   ├── frozen_evaluations/
│   │   ├── opponent_mixtures/
│   │   ├── promotion_history.jsonl
│   │   └── historical_checkpoints/
│   ├── raw_games/
│   ├── evaluations/
│   ├── packages/
│   └── submissions/
├── hybrid/
│   ├── configs/H0.json ... H4.json
│   ├── recurrent_state_traces/
│   ├── prior_calibration/
│   ├── value_calibration/
│   ├── ablations/
│   ├── raw_games/
│   ├── evaluations/
│   ├── packages/
│   └── submissions/
├── final_panel/
│   ├── registered_protocol.json
│   ├── raw_games.jsonl
│   ├── aggregates.json
│   ├── confidence_intervals.json
│   └── interpretation.md
├── probes/
│   ├── P00_.../
│   ├── M01_.../
│   ├── B01_.../
│   ├── H01_.../
│   └── F01_.../
├── failures/
│   ├── exceptions/
│   ├── timeouts/
│   ├── invalid_determinizations/
│   ├── recurrent_mismatches/
│   ├── multiselect_mismatches/
│   ├── package_failures/
│   └── taint_graph.json
├── packages/
│   ├── corrected_mcts/
│   ├── corrected_byterl/
│   └── eligible_hybrids/
├── submissions/
│   ├── references.json
│   ├── responses/
│   └── score_snapshots.jsonl
├── source/
│   ├── complete_repository_source.zip
│   ├── c020_competition_source_bundle.zip
│   ├── plain_inspection/
│   │   ├── cg/
│   │   ├── starter_kit/
│   │   ├── tools/
│   │   ├── tests/
│   │   └── package_entrypoints/
│   ├── milestones/
│   │   ├── M00_parent/
│   │   ├── M01_all_corrections_implemented/
│   │   ├── M02_complete_smoke/
│   │   ├── M03_repair_pass/
│   │   ├── M04_scaled_mcts/
│   │   ├── M05_scaled_byterl/
│   │   ├── M06_hybrid_H0_H4/
│   │   └── M07_submitted_packages/
│   ├── git_diff.patch
│   ├── source_manifest.json
│   └── hashes.sha256
└── git/
    ├── parent_resolution.md
    ├── initial_head.txt
    ├── final_head.txt
    ├── branch.txt
    ├── status.txt
    └── log.txt
```

## Full code requirement

`complete_repository_source.zip` contains the final repository tree excluding only `.git`, credentials, virtual environments, caches, and unrelated large historical datasets.

`c020_competition_source_bundle.zip` contains every source file required to reproduce:

- corrected information-set search;
- branch-local baseline memory;
- tactical evaluator and override gate;
- determinization prior/validation;
- corrected slot-aware encoder and option scorer;
- autoregressive multi-select;
- actor/unroll/queue/learner;
- V-trace and UPGO;
- OSFP scheduler/payoff/promotions;
- H0–H4 adapters;
- evaluations, packages, submissions;
- tests/probes/configs;
- exact deck and dependencies.

Plain inspection copies must include all c019 controls and all changed c020 files.

## Raw evidence minimums

### MCTS

- complete traces for at least 100 pivotal decisions;
- compact summaries for all searched decisions;
- all actual override logs;
- at least 10 full trees per major matchup;
- all invalid/rejected determinizations;
- shared information-set action statistics with determinization IDs;
- leaf feature decomposition.

### ByteRL

- all learning-period summaries;
- all frozen promotion evaluations/payoff tables;
- all checkpoint hashes;
- complete optimizer/loss series;
- representative unrolls from every opponent/checkpoint type;
- all recurrent mismatch failures;
- all observed final-evaluation multi-select records;
- full final and promoted checkpoints.

### Hybrid

- mode manifests H0–H4;
- branch-local recurrent traces;
- prior/value admission datasets;
- identical-budget ablation games;
- package traces for every promotable mode.

## Archive splitting

When the results exceed normal ZIP limits, create a standard split archive and include:

- every volume;
- a volume manifest;
- SHA-256 per volume;
- central-directory verification;
- an unsplit focused source/evidence ZIP under a manageable size.

Missing volumes or missing checkpoint entries must be reported explicitly.

# Mandatory c019 results and source schema

The user must be able to upload the c019 results and allow a line-by-line implementation audit. Summaries without code are unacceptable.

```text
results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── EXECUTION_BUDGET.json
├── DECISION_BOARD.json
├── method_fidelity/
│   ├── mcts_fidelity.json
│   ├── byterl_fidelity.json
│   ├── hybrid_fidelity.json
│   └── validator_output.json
├── common/
│   ├── deck_freeze.json
│   ├── canonical_action_schema.json
│   ├── environment.json
│   ├── dependencies.txt
│   └── machine_profile.json
├── mcts/
│   ├── configs/
│   ├── determinizations/
│   ├── trees/
│   ├── sampled_full_traces/
│   ├── aggregate_stats/
│   ├── parity/
│   ├── latency/
│   ├── raw_games/
│   ├── evaluations/
│   ├── packages/
│   └── submissions/
├── byterl/
│   ├── configs/
│   ├── model_architecture/
│   ├── actor_unrolls/
│   ├── queue_stats/
│   ├── learner_logs/
│   ├── vtrace_upgo_fixtures/
│   ├── osfp/
│   │   ├── learning_periods.jsonl
│   │   ├── opponent_samples.jsonl
│   │   ├── payoff_tables/
│   │   ├── promotion_history.jsonl
│   │   └── historical_checkpoints/
│   ├── checkpoints/
│   ├── raw_games/
│   ├── evaluations/
│   ├── packages/
│   └── submissions/
├── hybrid/
│   ├── adapters/
│   ├── smoke_traces/
│   ├── comparisons/
│   └── packages/
├── final_panel/
│   ├── registered_protocol.json
│   ├── raw_games.jsonl
│   ├── aggregates.json
│   └── interpretation.md
├── probes/
│   ├── P00_.../
│   ├── M01_.../
│   ├── B01_.../
│   └── ...
├── failures/
│   ├── exceptions/
│   ├── timeouts/
│   ├── invalid_determinizations/
│   ├── failed_unrolls/
│   └── taint_graph.json
├── packages/
│   ├── baseline/
│   ├── ptcg_ismcts_v0/
│   ├── ptcg_byterl_v0/
│   └── optional_hybrid/
├── submissions/
│   ├── references.json
│   ├── responses/
│   └── score_snapshots.jsonl
├── source/
│   ├── complete_repository_source.zip
│   ├── c019_competition_source_bundle.zip
│   ├── plain_inspection/
│   │   ├── cg/
│   │   ├── tools/
│   │   ├── tests/
│   │   └── packages_entrypoints/
│   ├── milestones/
│   │   ├── M00_parent/
│   │   ├── M01_shared_interface/
│   │   ├── M02_mcts_faithful/
│   │   ├── M03_byterl_actor_learner/
│   │   ├── M04_byterl_osfp/
│   │   ├── M05_hybrid_adapters/
│   │   └── M06_submitted_packages/
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

## Source bundle requirements

`complete_repository_source.zip` contains the final repository tree excluding only `.git`, credentials, virtual environments, caches, and unrelated large historical data.

`c019_competition_source_bundle.zip` must include:

- official API adapter;
- canonical observation/action representation;
- branch-local baseline wrapper;
- determinization sampler;
- MCTS node/tree/PUCT/rollout/backprop/aggregation/time controller;
- ByteRL token encoder, recurrent policy/value model, actor, queue, learner, V-trace, UPGO, OSFP scheduler/payoff code;
- hybrid adapters;
- evaluators;
- package builders and submission entrypoints;
- all tests/probes/configs;
- exact deck;
- dependencies and machine profile;
- source reference and license records.

Preserve full promoted ByteRL checkpoints and every submitted checkpoint. For large actor data, include complete manifests/hashes, all final-evaluation unrolls, all failure examples, and representative training shards; include full data when archive size permits.

## Runtime evidence minimums

### MCTS

- complete traces for at least 100 pivotal decisions;
- compact node summaries for all evaluated decisions;
- at least 10 full trees per major matchup;
- all determinization failures;
- PUCT statistics and root visits.

### ByteRL

- complete first/last 10 learning-period logs;
- every historical promotion record;
- all payoff tables;
- complete optimizer/loss time series;
- representative raw unrolls from each opponent type and checkpoint version;
- checkpoint hashes before/after every LP.

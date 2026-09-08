# Results Schema

```text
results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── DECISION_BOARD.json
├── controls/
│   ├── control_manifest.json
│   └── frozen_results.json
├── references/
│   └── c021_audit_reconciliation.md
├── fidelity/
│   ├── mcgs_hidden_information_source_map.md
│   ├── mcgs_hidden_information_trace.jsonl
│   ├── mcgs_hidden_information_gap_analysis.md
│   ├── byterl_source_search.md
│   ├── byterl_equation_map.md
│   ├── BYTERL_STAGE_LEDGER.md
│   ├── ADAPTATION_LEDGER.md
│   └── UNRESOLVED_REFERENCE_CHOICES.md
├── hardware/
│   ├── mcgs_throughput.json
│   ├── byterl_actor_scaling.json
│   ├── queue_gpu_metrics.jsonl
│   └── contention_tests.json
├── mcgs/
│   ├── k1_control/
│   ├── multi_det_k2/
│   ├── multi_det_k4/
│   ├── multi_det_k8/
│   ├── fixed_total_simulations/
│   ├── fixed_simulations_per_world/
│   ├── calibration/
│   ├── unrestricted_reference/
│   ├── kaggle_deploy/
│   ├── final_panel/
│   ├── packages/
│   └── submissions/
├── byterl/
│   ├── budget/c021_matched_budget.json
│   ├── architecture/
│   ├── action_traces/
│   ├── recurrent_traces/
│   ├── numerical_fixtures/
│   ├── queue_logs/
│   ├── stages/BR0/
│   ├── stages/BR1/
│   ├── stages/BR1_5/
│   ├── stages/BR2/
│   ├── stages/BR3/
│   ├── fixed_deck/
│   ├── end_to_end/
│   ├── checkpoints/
│   ├── external_evaluations/
│   ├── plateau_decisions/
│   ├── osfp/
│   └── component_analysis/
├── transfer/
│   ├── registered_protocol.json
│   ├── noise_floor/
│   ├── prior_only/
│   ├── rollout_only/
│   ├── value_only/
│   └── decisions.json
├── final_panel/
│   ├── registered_protocol.json
│   ├── raw_games.jsonl
│   ├── aggregates.json
│   ├── confidence_intervals.json
│   └── interpretation.md
├── probes/
├── failures/
│   ├── exceptions/
│   ├── fidelity/
│   ├── hidden_worlds/
│   ├── recurrence/
│   ├── queue/
│   ├── invalid_actions_decks/
│   └── taint_graph.json
├── source/
│   ├── final_git_archive.tar.gz
│   ├── c022_focused_source.zip
│   ├── plain_inspection/
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

## Evidence requirements

- Raw game records, not only aggregates.
- Exact sample/game/update counts for every ByteRL stage and long run.
- Queue occupancy, policy lag, actor blocks, learner throughput, and GPU utilization.
- Full MCGS per-world and aggregate root statistics for pivotal decisions.
- Frozen checkpoint/package/source hashes.
- Final reports generated only after all final evaluations.
- Consistency validator must recompute every score, count, status, candidate identity, and hash.

# Mandatory Results and Source Schema

```text
results/
├── SUMMARY.md
├── STATUS.json
├── ACCEPTANCE_CHECKLIST.md
├── EXECUTION_BUDGET.json
├── DECISION_BOARD.json
├── controls/
│   ├── control_manifest.json
│   └── frozen_control_results.json
├── fidelity/
│   ├── mcgs_official_source_inventory.json
│   ├── mcgs_source_to_ptcg_map.md
│   ├── mcgs_paper_equation_map.md
│   ├── mcgs_license_assessment.md
│   ├── byterl_source_search.md
│   ├── byterl_paper_equation_map.md
│   ├── BYTERL_STAGE_LEDGER.md
│   ├── ADAPTATION_LEDGER.md
│   └── UNRESOLVED_REFERENCE_CHOICES.md
├── hardware/
│   ├── environment_throughput.json
│   ├── mcgs_worker_scaling.json
│   ├── byterl_actor_scaling.json
│   ├── gpu_metrics.jsonl
│   └── storage_memory_metrics.jsonl
├── mcgs/
│   ├── reference_source_port/
│   │   ├── configs/
│   │   ├── abstraction_keys/
│   │   ├── dag_snapshots/
│   │   ├── edge_statistics/
│   │   ├── chance_nodes/
│   │   ├── sparse_sampling/
│   │   ├── damped_sampling/
│   │   ├── filters_obliged_actions/
│   │   ├── rollouts/
│   │   ├── timing/
│   │   ├── raw_games/
│   │   ├── evaluations/
│   │   └── packages/
│   ├── legal_corrected/
│   │   ├── change_manifest.json
│   │   ├── raw_games/
│   │   ├── evaluations/
│   │   ├── latency/
│   │   ├── packages/
│   │   └── submissions/
│   └── comparisons/
├── byterl/
│   ├── meta_environment/
│   ├── architecture/
│   ├── action_records/
│   ├── recurrent_unrolls/
│   ├── queue_logs/
│   ├── numerical_fixtures/
│   ├── stages/
│   │   ├── BR0/
│   │   ├── BR1/
│   │   ├── BR1_5/
│   │   ├── BR2/
│   │   └── BR3/
│   ├── osfp/
│   │   ├── period_local_payoffs/
│   │   ├── mixtures/
│   │   ├── frozen_evaluations/
│   │   ├── promotion_history.jsonl
│   │   └── historical_checkpoints/
│   ├── checkpoints/
│   ├── external_evaluations/
│   ├── component_analysis/
│   │   ├── priors/
│   │   ├── representation/
│   │   ├── autoregressive_decoder/
│   │   ├── recurrence/
│   │   ├── osfp_diversity/
│   │   ├── deck_construction/
│   │   └── value/
│   └── packages/
├── transfer/
│   ├── registered_hypotheses.json
│   ├── prior_only/
│   ├── value_only/
│   ├── other_single_component/
│   └── admission_decisions.json
├── final_panel/
│   ├── registered_protocol.json
│   ├── raw_games.jsonl
│   ├── aggregates.json
│   ├── confidence_intervals.json
│   └── interpretation.md
├── probes/
├── failures/
│   ├── exceptions/
│   ├── timeouts/
│   ├── source_mismatches/
│   ├── formula_mismatches/
│   ├── recurrent_mismatches/
│   ├── invalid_decks_actions/
│   ├── package_failures/
│   └── taint_graph.json
├── packages/
├── submissions/
│   ├── references.json
│   ├── responses/
│   └── score_snapshots.jsonl
├── source/
│   ├── final_git_archive.tar.gz
│   ├── c021_focused_source.zip
│   ├── plain_inspection/
│   ├── external_reference_manifest.json
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

## Canonical-source requirements

1. Create `final_git_archive.tar.gz` from the exact final commit using `git archive`, not from the mutable working tree.
2. Create plain inspection copies by checking out/exporting the same final commit.
3. Hash every file and verify selected source files are byte-identical between archive and plain copies.
4. `c021_focused_source.zip` must contain all code/config/tests/entrypoints required to reproduce both methods and all packages.
5. External MCGS source/papers must be represented by URL/hash/license manifests; do not include them in submission packages unless explicitly permitted.
6. A corrupt archive, stale copy or mixed-commit source set forces `SOURCE_FIDELITY=FAIL`.

## Reporting consistency

Generate `SUMMARY.md`, `STATUS.json`, `ACCEPTANCE_CHECKLIST.md` and `DECISION_BOARD.json` only after final raw aggregates and package/submission artifacts exist.

Run a validator that recomputes every reported game count, score, candidate identity, status gate and submitted package hash. Any mismatch forces final reporting failure.

## Minimum raw evidence

MCGS:

- at least 100 complete pivotal decision traces;
- at least 20 complete DAG/chance snapshots across major matchups;
- all category-filter/obliged-action activations in final panels;
- worker/search-budget scaling curves;
- every invalid hidden-state/chance sample;
- every final selected root action and supporting edge statistics.

ByteRL:

- all stage configurations and exact deltas;
- complete optimizer/loss/entropy/value series;
- queue occupancy/age/version-lag series;
- all OSFP period summaries and frozen promotions;
- representative full recurrent unrolls from every stage;
- complete final checkpoints and hashes;
- external evaluation games for every selected milestone;
- deck-construction outputs and legality results.

Transfer:

- preregistered hypothesis/config;
- identical-budget paired candidate/control games where possible;
- component admission decision with raw evidence.

# c018 Results and Source Requirements

The result archive must be sufficient for an independent code and evidence audit.

## Mandatory code deliverables

1. `results/source/complete_repository_source.zip`
2. `results/source/c018_competition_source_bundle.zip`
3. `results/source/inspection/` with uncompressed key c018 source files
4. `results/source/milestones/M00...M05/`
5. `results/source/git_diff.patch`
6. `results/source/source_manifest.json`
7. `results/source/hashes.sha256`
8. `results/source/environment.txt`
9. `results/source/dependency_lock.txt`

## Key files required in `inspection/`

At minimum copy the final versions of:

- official search API adapter/context manager;
- hidden-state determinization and archetype classifier;
- candidate generator/action representation;
- beam/best-first planner;
- heuristic leaf evaluator;
- trajectory schema/writer/reader;
- policy/value model;
- supervised trainer;
- PPO rollout/trainer;
- curriculum scheduler;
- identity-safe evaluator;
- guided-search integration;
- package builder and submission entrypoint;
- evidence validator;
- all c018-specific tests/probes.

## Milestone content

Each milestone must contain a manifest with:

- Git commit/tree hash;
- source hashes;
- config hashes;
- deck hash;
- checkpoint hashes;
- trajectory manifest hashes;
- package hashes;
- result artifact hashes;
- command used.

Milestones:

- `M00_parent`: resolved c017 parent and immutable baseline
- `M01_real_search`: first trusted official-API multi-step planner
- `M02_distilled`: best trusted search-distilled model
- `M03_curriculum`: best actual PPO curriculum checkpoint
- `M04_guided_search`: best trusted guided-search candidate
- `M05_submitted`: exact source/config/checkpoint/package uploaded

## Raw evidence rules

Summaries cannot replace raw data. Preserve:

- real search roots and sampled node traces;
- `search_begin/search_step/release/end` counters;
- raw game-level outcomes;
- action-level search decisions;
- determinization/profile metadata;
- full or compressed trusted trajectories;
- optimizer/training logs;
- raw curriculum rollouts and opponent identities;
- checkpoint hashes and promotion calculations;
- final-panel raw games;
- package validation logs;
- Kaggle CLI/API responses and polling snapshots;
- failures, exceptions, timeouts, and memory/lifecycle errors.

When a dataset is too large for the result ZIP, include a complete manifest, hashes, exact local path, schema, representative samples, and all final-evaluation records. Include the compressed full dataset whenever practical.

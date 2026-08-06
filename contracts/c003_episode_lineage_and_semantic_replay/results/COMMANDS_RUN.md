# Commands Run — c003

From repo root `/home/luca/kaggle/ptcg_ai_battle`, interpreter `.venv/bin/python`.
No secrets, no network.

## Contract-folder normalization
Delivered folder was doubly-nested (`contracts/c003_.../contracts/c003_.../`);
inner contents moved up one level (no file contents changed). `CLAUDE_COMMAND.txt`
confirms the single-level path.

## Git initial inspection (§11)
```bash
git status --short
git branch --show-current                 # contract/c002_reproducible_episode_capture
git rev-parse HEAD                         # ff6e94b...
git switch -c contract/c003_episode_lineage_and_semantic_replay
```

## AC-04 pre-flight de-risk
```bash
# Confirmed 500/500 c002 safe decisions reconstruct (to_observation_class) and
# reproduce (agent(serialized_obs)) — semantic replay is achievable.
```

## Tests (83 total)
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v   # 83 OK
# Per-AC logs:
.venv/bin/python -m unittest tests.test_schema_v2_lineage -v       > results/test_logs/schema_v2_lineage_tests.txt
.venv/bin/python -m unittest tests.test_deck_registry -v           > results/test_logs/deck_registry_tests.txt
.venv/bin/python -m unittest tests.test_provenance -v              > results/test_logs/provenance_tests.txt
.venv/bin/python -m unittest tests.test_observation_snapshot -v    > results/test_logs/observation_snapshot_tests.txt
.venv/bin/python -m unittest tests.test_terminal_classification -v > results/test_logs/terminal_classification_tests.txt
.venv/bin/python -m unittest tests.test_compression -v             > results/test_logs/compression_tests.txt
.venv/bin/python -m unittest tests.test_schema_v1_compatibility -v > results/test_logs/schema_v1_compatibility_tests.txt
```

## Environment report + v1 compatibility report
```bash
.venv/bin/python tools/environment_report.py --json results/artifacts/environment_report.json
# summarize_file(c002 v1 episodes) -> detected schema 1; schema_version:99 -> UnsupportedSchemaVersion
```

## Commit source BEFORE the acceptance capture (clean tree)
```bash
git add starter_kit/{episode_schema,agents,episode_compat}.py tools/environment_report.py tests/test_{schema_v2_lineage,deck_registry,schema_v1_compatibility}.py
git commit -m "c003: add schema v2 lineage, deck registry, and compat reader"   # d2e8502
git add starter_kit/episode_capture_v2.py tools/{capture_episodes_v2,validate_episodes_v2}.py tests/{_v2_helpers,test_semantic_replay,test_observation_snapshot,test_terminal_classification,test_provenance,test_compression}.py
git commit -m "c003: add v2 capture, semantic replay, terminal validation, gzip" # 26363cc
# Review fix: serialize the random-baseline agent lineage (§7.3) + harden validator
git add tools/capture_episodes_v2.py tools/validate_episodes_v2.py tests/_v2_helpers.py tests/test_schema_v2_lineage.py
git commit -m "c003: serialize random-baseline agent lineage in run metadata"    # afe52db (final HEAD)
git status --porcelain --untracked-files=no   # empty -> tracked tree clean
```

## Acceptance capture + validation (from clean branch)
```bash
.venv/bin/python tools/capture_episodes_v2.py --games-per-cohort 10 --base-seed 4242 --require-clean \
  --output-dir contracts/c003_episode_lineage_and_semantic_replay/results/artifacts/validation_run
# -> 30/30 games, run_metadata.git.dirty=false

.venv/bin/python tools/validate_episodes_v2.py <validation_run>/episodes_v2.jsonl \
  --validation-report ... --semantic-report ... --context-report ... --latency-report ...
.venv/bin/python tools/validate_episodes_v2.py <validation_run>/episodes_v2.jsonl.gz
# both: 30 games, 1382 decisions, 0 errors, 966/966 semantic replay, normal_win x30

# Cross-checks on the dataset:
sha256(jsonl) == sha256(gunzip -c gz)        # gzip content identical
grep -c '"game_seed"' episodes_v2.jsonl      # 0
```

## Git evidence
```bash
git diff ff6e94b..26363cc -- starter_kit tools tests > results/artifacts/c003.patch
git diff --check ff6e94b..26363cc            # no whitespace errors
git status --short > results/test_logs/final_git_status.txt
```

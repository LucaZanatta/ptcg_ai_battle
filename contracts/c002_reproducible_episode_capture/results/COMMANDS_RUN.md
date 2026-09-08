# Commands Run — c002

All from repo root `/home/luca/kaggle/ptcg_ai_battle`, interpreter `.venv/bin/python`.
No secrets, no network.

## Contract-folder normalization
The delivered folder was doubly-nested (`contracts/c002_.../contracts/c002_.../`),
an extraction artifact; inner contents moved up one level to the intended path
(no file contents changed). `CLAUDE_COMMAND.txt` confirms the single-level path.

## Git initial inspection (§13)
```bash
git status --short
git branch --show-current            # contract/c001_deterministic_safe_agent_core
git rev-parse HEAD                    # 283f31c...
git switch -c contract/c002_reproducible_episode_capture
```

## Engine-seeding investigation (pivotal for AC-04)
```bash
nm -D starter_kit/libcg.so | grep -iE "seed|rand"      # std::random_device + std::mt19937; no Seed export
# cross-process probe: identical deterministic agents + configuration.seed -> divergent results
```

## Build + unit verification
```bash
.venv/bin/python tools/verify_runtime_assets.py            # 13/13 PASS, exit 0
.venv/bin/python tools/verify_runtime_assets.py --json
.venv/bin/python tools/verify_runtime_assets.py --manifest <negative_manifest>   # exit 1
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v   # 46 tests, OK (run twice for AC-03)
```

## Episode capture / validation / coverage / replay
```bash
.venv/bin/python tools/capture_episodes.py --mode capture --games-per-cohort 20 --base-seed 777 \
  --output  contracts/c002_reproducible_episode_capture/results/artifacts/episodes/episodes.jsonl \
  --summary contracts/c002_reproducible_episode_capture/results/artifacts/episode_run_summary.json
#  -> 60/60 completed, 0 failed, 0 invalid, 60 unique seeds, 2553 records

.venv/bin/python tools/validate_episode_jsonl.py <episodes.jsonl> --json <episode_validation.json>
#  -> 60 games, 2433 decisions, 0 errors, exit 0

.venv/bin/python tools/context_coverage_report.py <episodes.jsonl> \
  --json <context_coverage.json> --csv <context_coverage.csv> --md <CONTEXT_COVERAGE.md>
#  -> 49 enum contexts, 11 observed

.venv/bin/python tools/capture_episodes.py --mode replay-check --games-per-cohort 20 --base-seed 777
#  -> seeds/seats + record-level policy reproduce; engine counts/winners do not
```

## Git (branch + two commits; no results committed)
```bash
git add runtime_assets.json tools/verify_runtime_assets.py REPRODUCIBILITY.md tests/test_runtime_assets.py .gitignore
git diff --cached --name-only                 # verified: only c002 source
git commit -m "c002: add reproducible runtime asset verification"     # f4b741d
git add starter_kit/episode_capture.py tools/capture_episodes.py tools/validate_episode_jsonl.py \
        tools/context_coverage_report.py tests/test_episode_capture.py tests/test_safe_policy.py tests/test_agent_integration.py
git commit -m "c002: add versioned episode capture and validation"    # ff6e94b (final HEAD)
git diff 283f31c..ff6e94b -- runtime_assets.json REPRODUCIBILITY.md .gitignore starter_kit tools tests > results/artifacts/c002.patch
git diff --check 283f31c..ff6e94b             # no whitespace errors
```

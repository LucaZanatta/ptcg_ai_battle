# Commands Run — c001

All from repo root `/home/luca/kaggle/ptcg_ai_battle`. No secrets. No network.

## Contract-folder normalization
The delivered folder was doubly-nested
(`contracts/c001_.../contracts/c001_.../`), an extraction artifact. The inner
contents (`CONTRACT.md`, `CLAUDE_COMMAND.txt`, `inputs/`, `references/`, `results/`)
were moved up one level to the intended path
`contracts/c001_deterministic_safe_agent_core/` (no file contents changed), then
the empty nested dirs removed. `CLAUDE_COMMAND.txt` confirms the intended
single-level path.

## Git initial inspection
```bash
git status --short
git branch --show-current        # contract/c000_repository_audit_and_baseline
git rev-parse HEAD               # 18c73c079a24280cdb1d686c082c0cb5541631c9
git log -5 --oneline
```

## Repo/API inspection (read-only)
```bash
sed/grep over starter_kit/api.py   # SelectData, Option, SelectContext (49), to_observation_class
head .venv/.../envs/cabt/cabt.py   # first_agent == list(range(maxCount)); INVALID handling
python - (read cabt.json)          # episodeSteps=10000, actTimeout=0
python - (3x first-vs-first)       # deterministic games terminate DONE/DONE
```

## Tests
```bash
.venv/bin/python -m unittest tests.test_safe_policy -v          > results/test_logs/unit_safe_policy.txt
.venv/bin/python -m unittest tests.test_agent_integration -v    > results/test_logs/unit_agent_integration.txt
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v > results/test_logs/unittest_all.txt   # Ran 30, OK
```

## Randomness audit (AST-based)
```bash
.venv/bin/python <ast scan of main.py + safe_policy.py>          > results/test_logs/randomness_audit.txt
```

## Benchmark (300 games)
```bash
.venv/bin/python tools/benchmark_safe_agent.py \
  --games-per-cohort 100 \
  --output contracts/c001_deterministic_safe_agent_core/results/artifacts/safe_agent_benchmark.json \
  > results/test_logs/benchmark_safe_agent.txt 2>&1
# 300/300 completed, 0 failed, 0 invalid, P99=0.207ms
```

## Git (branch + commits — see GIT_REPORT.md)
```bash
git switch -c contract/c001_deterministic_safe_agent_core
git add starter_kit/main.py starter_kit/safe_policy.py tests tools
git diff --cached --name-only            # verified: only c001 source paths
git commit -m "c001: add deterministic safe agent core"
git diff <initial>..<impl> -- starter_kit/main.py starter_kit/safe_policy.py tests tools \
  > results/artifacts/committed_diff.patch
git add contracts/c001_deterministic_safe_agent_core
git commit -m "c001: add safe agent validation evidence"
git commit -m "c001: record commit hashes in status/git report"   # finalization
```

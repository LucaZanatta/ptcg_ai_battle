# Acceptance Checklist — c000

## AC-01 — PASS
Requirement: `results/artifacts/repo_map.md` lists every top-level entry with its role.
Verification command: inspect `artifacts/repo_map.md`.
Evidence: `results/artifacts/repo_map.md` (table of all top-level entries + `starter_kit/` breakdown).
Notes: `.git`/`.venv` internals excluded by design; sizes from `du -sh`.

## AC-02 — PASS
Requirement: environment report records Python version + `kaggle-environments` version and confirms `cabt` is registered.
Verification command: `.venv/bin/python --version`; `.venv/bin/pip freeze`; `listdir(kaggle_environments/envs)`.
Evidence: `results/artifacts/environment.md`, `results/test_logs/pip_freeze.txt`.
Notes: Python 3.13.13; kaggle-environments 1.30.1; `cabt` present as built-in env dir.

## AC-03 — PASS
Requirement: `entry_points.md` names the agent fn, deck file(s), engine lib, and run/test harness with exact paths.
Verification command: inspect `artifacts/entry_points.md`.
Evidence: `results/artifacts/entry_points.md`.
Notes: agent = `starter_kit/main.py:agent`; deck = `starter_kit/deck.csv`; engine = `starter_kit/libcg.so` via `sim.py`; harness = `test_engine.py` / `cabt`.

## AC-04 — PASS
Requirement: a documented minimal command runs one `cabt` game to completion (both players terminal status, no exception).
Verification command: `.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/run_one_game.py`
Evidence: `results/artifacts/RUN_ONE_GAME.md`, `results/test_logs/run_one_game.txt`.
Notes: exit 0; 139 steps; player0 DONE (+1), player1 DONE (-1); printed `ONE_GAME_COMPLETED`.

## AC-05 — PASS
Requirement: >=10 `cabt` games complete without exception; metrics file reports per-game time+steps and aggregate min/mean/max.
Verification command: `.venv/bin/python contracts/c000_repository_audit_and_baseline/results/artifacts/baseline_measure.py`
Evidence: `results/artifacts/baseline_metrics.json`, `results/test_logs/baseline_run.txt`.
Notes: 10/10 completed; seconds min 0.045 / mean 0.093 / max 0.199; steps min 23 / mean 45.2 / max 94.

## AC-06 — PASS
Requirement: `risks.md` lists >=5 technical risks ranked by severity.
Verification command: inspect `artifacts/risks.md`.
Evidence: `results/artifacts/risks.md`.
Notes: 7 risks ranked (2 HIGH, 3 MEDIUM, 2 LOW).

## AC-07 — PASS
Requirement: `STATUS.json` present and valid, with a definitive outcome and matching criteria counts.
Verification command: `python -c "import json; json.load(open('.../STATUS.json'))"`.
Evidence: `results/STATUS.json`.
Notes: status `PASS`, 7/7 criteria passed.

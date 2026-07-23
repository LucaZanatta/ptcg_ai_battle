# c000 — Summary

## Objective
Audit the `ptcg_ai_battle` repository and reproduce the random-agent baseline
through the official `kaggle_environments` `cabt` environment, producing concrete
evidence (repo map, environment report, entry points, verified one-game command,
multi-game runtime measurements, ranked risks) and a definitive outcome.

## What was implemented
- Full repository map (`artifacts/repo_map.md`) of every top-level entry.
- Environment & dependency report (`artifacts/environment.md`,
  `test_logs/pip_freeze.txt`); confirmed `cabt` is a built-in env in
  `kaggle-environments==1.30.1`, Python 3.13.13.
- Entry-point / deck / engine / harness catalogue (`artifacts/entry_points.md`).
- Verified minimal one-game command (`artifacts/RUN_ONE_GAME.md`,
  `run_one_game.py`, `test_logs/run_one_game.txt`): one game completed, 139 steps,
  both players `DONE`.
- 10-game baseline measurement (`baseline_measure.py`,
  `artifacts/baseline_metrics.json`, `test_logs/baseline_run.txt`): **10/10 games
  completed**, mean **0.09s/game** (min 0.04, max 0.20), mean 45.2 steps.
- Ranked technical-risk list (`artifacts/risks.md`), 7 risks.

## Important design decisions
- **Baseline harness = built-in `cabt` env** via `make("cabt", ...)`, not the
  direct `libcg.so` battle loop — this matches the competition runner and the
  existing `test_engine.py`. (Smallest reversible choice per protocol §10.)
- Measurement scripts live under `results/artifacts/` (throwaway helpers), keeping
  project source untouched.
- Used a self-contained random agent (deck loaded by absolute repo path) so the
  reproduction does not depend on the current working directory.

## What was not implemented
- No agent/strategy changes, no engine or deck edits (out of scope, protocol §E).
- No episode/replay persistence and no `search_*` latency benchmark (flagged as
  risks #3 and #5 for future contracts).

## Known limitations
- Baseline metrics reflect **random play only**; a real agent's per-step latency
  is unmeasured.
- Engine is a black-box `.so`; rules are inferred from the observation model, not
  read from source.
- Only 10 games measured (as scoped); percentile latencies (P95/P99) not computed.

## Recommended next step
**c001 — deterministic legal-action fallback**: implement and fixture-test a
selector that returns a valid action for every `SelectContext`, removing the
game-forfeit risk (risk #2) before any strategic work.

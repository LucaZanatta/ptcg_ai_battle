# c001 — Summary

## Objective
Implement a deterministic, production-safe baseline agent core: return the
validated 60-card deck during deck selection; return a legal, deterministic
`list[int]` of option indices for every valid cabt `Select`; remove randomness
from the competition entrypoint; and prove it with unit tests, a 300-game cabt
integration benchmark, and latency measurement.

## What was implemented
- **`starter_kit/safe_policy.py`** — pure, engine-agnostic module:
  `MalformedSelection`/`MalformedDeck` exceptions; `validate_bounds`,
  `select_indices` (returns `list(range(maxCount))`), `select_for` (duck-typed on
  a `Select`), `validate_selection`, and `parse_deck`/`load_deck`/`default_deck_path`
  (module-relative, with the Kaggle-runner fallback). No RNG, clock, or hidden state.
- **`starter_kit/main.py`** — `agent(obs_dict)` converts via `to_observation_class`,
  returns the cached validated deck when `select is None`, else delegates to
  `select_for`. `random` is neither imported nor used; import has no side effects.
- **`tests/test_safe_policy.py`** (25 tests) and **`tests/test_agent_integration.py`**
  (5 tests) — stdlib `unittest` only.
- **`tools/benchmark_safe_agent.py`** — 3-cohort, 300-game cabt benchmark with
  per-call latency instrumentation, selection validation, and context coverage.

## Design decisions
- **Deterministic rule = first `maxCount` options** (`list(range(maxCount))`). This
  is engine-sanctioned: the cabt env ships `first_agent` using exactly this
  (`kaggle_environments/envs/cabt/cabt.py:82`). `maxCount` is always in
  `[minCount, maxCount]` and `<= len(option)`, so it is always legal.
- **`cg.*` imports everywhere** (main, tests, benchmark). `cg` is a symlink to
  `starter_kit`; mixing `cg.*` and `starter_kit.*` in one process would load
  `libcg.so` twice. Documented in `main.py`.
- **Malformed observations are surfaced, not faked.** Impossible bounds raise
  `MalformedSelection`; the public path stays safe for valid observations only
  (per §D). No fabricated actions.
- Selector is pure and decoupled from `api.py` (duck-typed), so unit tests need
  no engine except the enum import for `SelectContext` coverage.

## Results (evidence under `results/`)
- **Unit tests:** 30/30 pass (`test_logs/unittest_all.txt`).
- **Benchmark:** **300/300 games completed, 0 failed, 0 invalid safe selections**
  across all three cohorts (100 each). 9,984 safe-agent calls (400 deck calls).
- **Enum-level context coverage:** 49/49 `SelectContext` members are
  selector-compatible (`artifacts/enum_context_coverage.json`).
- **Runtime context coverage:** 9/49 contexts observed in the 300 games
  (MAIN, SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON, TO_ACTIVE, TO_HAND,
  ATTACH_FROM, ATTACH_TO, DRAW_COUNT, IS_FIRST) — the rest simply did not arise
  in sampled games (`artifacts/runtime_context_coverage.json`).

## Safe-agent call latency (AC-06)
Measured around the agent call only (not engine time), over 9,984 calls:

| min | mean | P50 | P95 | **P99** | max |
|-----|------|-----|-----|---------|-----|
| 0.0021 ms | 0.096 ms | 0.072 ms | 0.152 ms | **0.207 ms** | 87.47 ms |

**P99 = 0.207 ms < 10 ms → AC-06 PASS.** The single 87.47 ms `max` is a one-time
first-call warm-up (lazy deck load + first `to_observation_class` construction +
interpreter/GC warm-up); steady-state P99 is ~0.2 ms. The contract's bound is on
P99, not max; the outlier is reported for transparency.

## What was not implemented (per Non-goals)
No strategy/scoring, no heuristics, no deck changes, no `search_*`/MCTS, no ML,
no submission tarball, no API/engine refactor, no new dependencies.

## Known limitations
- The policy is intentionally non-strategic (always the first legal options); it
  wins vs random here (71%/84%/n-a) only incidentally.
- Runtime coverage reflects only sampled games; 40 enum contexts were not reached.
- The safe production path assumes valid cabt observations; impossible bounds are
  raised/logged, not repaired.

## Recommended next step
**c002** — capture and persist game episodes (observations, chosen actions,
outcomes) from the safe agent, establishing the dataset needed before any
strategy or learning contract (c000 risk #3).

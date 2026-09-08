# Acceptance Checklist — c002

Overall: **PARTIAL** — 7/8 criteria pass; AC-04 is partially met (engine
non-determinism, external limitation).

## AC-01 — PASS — Runtime assets are reproducibly declared
- Manifest: `artifacts/runtime_assets.json` (13 assets; sha256 for untracked externals).
- Verifier human table: `test_logs/runtime_assets_human.txt` — 13/13 PASS, exit 0.
- Verifier JSON: `artifacts/runtime_assets_verification.json`.
- Negative test (missing required asset): `test_logs/runtime_assets_negative_test.txt` — exit 1.
- Output distinguishes tracked / external / symlink / python_env assets.

## AC-02 — PASS — Clean reproducibility procedure exists
- `artifacts/REPRODUCIBILITY.md` (also tracked at repo root): asset categories,
  exact verify/test/one-game/capture commands, and the non-committable assets +
  how to provide them.
- `test_logs/clean_reproduction_commands.txt`: verify (exit 0), test suite (OK),
  one-game capture (3/3) all succeed from the repo root.

## AC-03 — PASS — Tests are side-effect free
- `test_logs/tests_run_1.txt`, `tests_run_2.txt` — 46 tests OK on both runs.
- `test_logs/test_side_effect_check.txt` — no tracked source or c000/c001 result
  file changed (byte-identical dir hashes before/after; git status clean).
- c001 tests refactored: they no longer write `enum_context_coverage.json` /
  `deck_validation.json` into contract results.

## AC-04 — PARTIAL — Episode JSONL capture works on real games
- **PASS parts:** 60/60 games complete (`artifacts/episode_run_summary.json`,
  `test_logs/episode_capture_run.txt`); every game has a terminal record; zero
  invalid safe selections; 60 unique recorded seeds; balanced cohorts
  (20 safe-vs-safe, 20 safe-p0-vs-random, 20 random-p0-vs-safe).
- **FAIL part (condition 3):** re-running the 5-game subset reproduces seeds and
  seat assignments and byte-identical record-level safe decisions (157/157), but
  NOT decision counts or winners — the engine RNG is `std::random_device`-seeded
  and unseedable. Evidence: `test_logs/deterministic_replay_check.txt`;
  root cause: `failures/AC04_engine_nondeterminism.md`.

## AC-05 — PASS — Episode round-trip validation passes
- `test_logs/episode_validation.txt` / `artifacts/episode_validation.json` —
  60 games, 2433 decisions, **0 errors**, exit 0. Streaming validator checks
  schema, ordering, index bounds, terminal-vs-decision counts, and record-level
  policy determinism. Backing scan: 0/2433 decisions with omitted observation
  fields; `legal_option_count == len(legal_option_metadata)` in 2433/2433.

## AC-06 — PASS — Context and latency report is generated
- `artifacts/context_coverage.json` / `.csv` / `CONTEXT_COVERAGE.md`.
- All 49 enum contexts appear (38 zero-count included); 11 observed at runtime;
  per-seat counts, fallback counts, invalid counts, and P50/P95/P99/max latency
  per context. Explicitly distinguishes enum vs runtime coverage and lists the
  38 not-observed contexts.

## AC-07 — PASS — Automated test suite passes
- `test_logs/pytest_full.txt` — 46 tests, OK, no skips.
- `artifacts/test_inventory.json` — all 13 §8 categories represented
  (`all_13_categories_represented: true`); c001 deterministic-selector tests
  still pass.

## AC-08 — PASS — Git state is reviewable and reproducible
- `GIT_REPORT.md`, `artifacts/c002.patch` (12 files, 1638 insertions / 51
  deletions, no whitespace errors), `artifacts/source_snapshot/`.
- Two `c002:` commits; no results folder committed (no self-referential commit);
  externals declared in the manifest. Final status explained line-by-line.

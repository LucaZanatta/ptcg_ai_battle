# Acceptance Checklist — c001

## AC-01 — PASS — Deterministic safe selector exists and is isolated
Requirement: pure deterministic selector + explicit validation in
`starter_kit/safe_policy.py`; no randomness in the safe-agent path.
Verification: `.venv/bin/python -m unittest tests.test_safe_policy -v` (25 tests OK);
AST-based randomness scan of `main.py` + `safe_policy.py`.
Evidence: `test_logs/unit_safe_policy.txt`, `test_logs/randomness_audit.txt`
(RESULT: PASS — zero randomness), `artifacts/source_snapshot/`.

## AC-02 — PASS — All SelectContext enum members are selector-compatible
Requirement: a stdlib test iterates every real `SelectContext` member and proves
context identity does not alter/break legal deterministic selection.
Verification: `.venv/bin/python -m unittest tests.test_safe_policy -v`
(`TestSelectContextCoverage.test_all_contexts_compatible` OK).
Evidence: `test_logs/unit_safe_policy.txt`, `artifacts/enum_context_coverage.json`
(enum_contexts_total = 49, all listed).

## AC-03 — PASS — Deck selection is validated and deterministic
Requirement: entrypoint returns the same 60 integer card IDs on repeated calls;
invalid length and malformed IDs rejected.
Verification: `.venv/bin/python -m unittest tests.test_agent_integration -v` (5 OK).
Evidence: `test_logs/unit_agent_integration.txt`, `artifacts/deck_validation.json`
(deck_size 60, deterministic true, rejects_wrong_length true, rejects_malformed_card_id true).

## AC-04 — PASS — Full unit-test suite passes
Requirement: all c001 tests pass, zero failures/errors.
Verification: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`.
Evidence: `test_logs/unittest_all.txt` — **Ran 30 tests ... OK**.

## AC-05 — PASS — 300-game cabt benchmark completes
Requirement: all 300 games complete, both players terminal, zero exceptions,
zero invalid safe selections.
Verification: `.venv/bin/python tools/benchmark_safe_agent.py --games-per-cohort 100
--output contracts/c001_deterministic_safe_agent_core/results/artifacts/safe_agent_benchmark.json`.
Evidence: `test_logs/benchmark_safe_agent.txt`, `artifacts/safe_agent_benchmark.json`
(games_completed 300/300, games_failed 0, invalid_safe_selections 0),
`artifacts/runtime_context_coverage.json` (9 observed / 49 enum; not-observed listed).

## AC-06 — PASS — Runtime overhead is measured and bounded
Requirement: report safe-agent call latency; P99 < 10 ms (engine time excluded).
Verification: benchmark command from AC-05.
Evidence: `latency_ms` in `safe_agent_benchmark.json`
(P50 0.072, P95 0.152, **P99 0.207**, max 87.47 ms) and latency summary in
`SUMMARY.md`. P99 0.207 ms < 10 ms. Max is a one-time warm-up outlier (documented).

## AC-07 — PASS — Competition entrypoint remains compatible
Requirement: `starter_kit/main.py:agent` runs through the cabt harness as both
player 0 and player 1, no import errors / interface change.
Verification: `TestHarnessSmoke.test_agent_runs_as_both_players` (both seats DONE/DONE)
plus the 300-game benchmark (safe agent used as p0, p1, and both).
Evidence: `test_logs/unit_agent_integration.txt`, `test_logs/benchmark_safe_agent.txt`.

## AC-08 — PASS — Git changes are complete and isolated
Requirement: all c001 source/test changes committed on the c001 branch; no
pre-existing/binary/PDF/venv/scratch/unrelated files staged.
Verification: `git diff --cached --name-only` before each commit; diff stats.
Evidence: `GIT_REPORT.md`, `FILES_CHANGED.md`, `artifacts/committed_diff.patch`
(only `starter_kit/main.py`, `starter_kit/safe_policy.py`, `tests/`, `tools/`).

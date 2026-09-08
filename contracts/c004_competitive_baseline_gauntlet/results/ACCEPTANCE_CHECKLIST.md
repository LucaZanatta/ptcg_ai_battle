# Acceptance Checklist — c004

Overall: **PASS** — 10/10.

## AC-01 — c003 competitive amendments — PASS
Requirement: three Phase-0 defects fixed with regression tests; existing c003 tests still pass.
Verification: `.venv/bin/python -m unittest tests.test_c003_amendments -v`; re-validate the c003 dataset.
Result: 10 amendment tests OK. (1) `final_state_terminal` extracts errors from the final step (proven: a stale step-0 error does NOT leak into a clean DONE/DONE terminal); (2) validator checks `legal_option_metadata == observation.select.option`; (3) `replay_registry` verifies agent id/version/source-hash before invoking (OK/hash_mismatch/unregistered/stochastic). The frozen c003 dataset re-validates with 0 errors and **966/966** replay (hash-verified). 113-test suite green.
Evidence: `test_logs/c003_amendment_tests.txt`, `artifacts/c003_amendment_report.json`.

## AC-02 — Candidate manifest and freeze — PASS
Requirement: ≥3 complete runnable pairs admitted and frozen; before==after; no strategic change.
Result: **4** admitted, each with full source/deck/agent/version/hash lineage. Freeze **before == after** (verified). Compatibility adaptations (own-deck return, per-game seed) documented; no strategic change.
Evidence: `artifacts/candidate_manifest.json`, `candidate_admission.md`, `candidate_freeze_hashes_before.json`, `candidate_freeze_hashes_after.json`.

## AC-03 — Candidate smoke gate — PASS
Requirement: every candidate passes 10 seat-balanced smoke games, 0 invalid/exception/timeout.
Result: all four **10/10 completed, 0 defects**.
Evidence: `test_logs/candidate_smoke_tests.txt`, `artifacts/candidate_smoke_report.json`.

## AC-04 — Complete balanced round robin — PASS
Requirement: every pair, both seat orders, sequential balanced protocol, schema-v2 lineage.
Result: all **6** unordered pairs played, ≥40 games each (4 stopped at 40 by CI, 2 close pairs; the det/det pair ran to the 200 cap). Both seat orders balanced; stratified-bootstrap CI stopping; stopping reasons recorded; nothing omitted. 400 gauntlet games captured with run/game lineage (gzip).
Evidence: `artifacts/gauntlet_plan.json`, `artifacts/gauntlet_games.jsonl.gz`, `artifacts/pair_stopping_report.json`, `test_logs/gauntlet_execution.txt`.

## AC-05 — Matchup and seat analysis — PASS
Requirement: complete pairwise + seat-adjusted results with documented uncertainty.
Result: unordered + ordered matchup matrices; per-candidate seat0/seat1/balanced win rates; overall seat-0 rate 0.54; pairwise stratified-bootstrap CIs (+ per-seat Wilson). Draws scored 0.5; reliability defects handled.
Evidence: `artifacts/matchup_matrix.csv`, `ordered_matchup_matrix.csv`, `seat_effects.csv`, `pairwise_intervals.json`.

## AC-06 — Global ranking and robustness — PASS
Requirement: bootstrap-supported ranking + worst-matchup analysis; ≥2000 resamples; reproducible.
Result: regularized Bradley-Terry (finite strengths under lopsided matchups; symmetric pseudo-count) + **2000-resample** bootstrap (strength CIs + rank frequencies) + worst-matchup conservative bounds. Analysis reproducible from the fixed capture (seeded bootstrap; re-run yields identical ranking — tested).
Evidence: `artifacts/bradley_terry_ranking.json`, `bootstrap_ranking.json`, `worst_matchups.json`, `test_logs/statistical_analysis_tests.txt`.

## AC-07 — Reliability and latency — PASS
Requirement: reliability + latency per candidate (invalid, agent/env errors, timeouts, fallback, calls, P50/95/99/max).
Result: reports for all four candidates; **0** reliability defects across 400 games; P99 ≈ 0.003 ms (det) / ≈ 0.01 ms (random); fallback = 100% for deterministic (fallback policy), 0% for random.
Evidence: `artifacts/reliability_report.json`, `latency_report.json`, `fallback_report.json`.

## AC-08 — Explicit competitive decision — PASS
Requirement: primary + backup by predefined rule; explicit rejections; full decision content.
Result: **primary=det_starter, backup=det_cabt** via the code-defined rule (BT strength → overlapping-interval tiebreak on worst-matchup lower bound → P99 → determinism). Rankings, evidence, weak matchups, reliability status, uncertainty, rejection codes, and frozen ids all present. No "more testing needed".
Evidence: `artifacts/selected_baselines.md`, `competitive_decision.json`.

## AC-09 — Actionable c005 hypothesis — PASS
Requirement: one specific hypothesis for the primary, ≥5 captured examples, one decision problem, unchanged baseline + intervention + opponents + keep/reject criterion; no implementation.
Result: hypothesis targets "when to attack in MAIN" for the unchanged `det_starter`. **3,122** captured MAIN decisions (of 5,774) declined a legal ATTACK (≫5); 200 concrete examples recorded. Intervention, frozen opponents, and a 0.55-CI keep/reject criterion specified. Not implemented.
Evidence: `artifacts/c005_policy_hypothesis.md`, `artifacts/tactical_failure_examples.jsonl`.

## AC-10 — Git and source integrity — PASS
Requirement: c004 source committed cleanly; frozen candidate strategy/decks unchanged; earlier results untouched; HEADs recorded; no unrelated changes.
Result: 3 `c004:` commits; final HEAD `9cc8426`; `c004.patch` (16 files, 1623 insertions / 46 deletions, no whitespace errors); candidate freeze before==after; only untracked contract-results packages remain; no c00x results modified.
Evidence: `GIT_REPORT.md`, `artifacts/c004.patch`, `artifacts/source_snapshot/`, `artifacts/CLEAN_CHECKOUT.md`, `test_logs/final_git_status.txt`.

# Acceptance Checklist — c005

Overall: **PASS** — 13/13.

## AC-01 — Current research and source audit — PASS
Mandatory sources attempted: 4 official kiyotah kernels acquired (kernel output +
notebook source, anonymous), wmh/ptcg-abc cloned @ `1b31d39a`. Competition rules
precisely referenced (URL + category); full text not machine-retrievable
(JS-rendered) — recorded honestly. Verified facts separated from author-reported
claims; license/reuse status recorded; no ineligible candidate selected for
Submission A.
Evidence: `artifacts/teacher_research.md`, `source_evidence.json` (in teacher_sources),
`rules_and_reuse_audit.md`, `test_logs/source_acquisition.txt`.

## AC-02 — At least three real strategic candidates — PASS
**4** distinct strategic policies on **4** distinct archetypes admitted
(dragapult/spread_setup, mega_lucario/switch_midrange, mega_abomasnow/linear_aggro,
iono/disruption_control). Random/fallback controls excluded. Dragapult + Lucario
attempted and admitted. Freeze hashes **before == after**.
Evidence: `strategic_candidate_manifest.json` (= strategic_run_metadata.json teachers),
`candidate_admission.md`, `candidate_freeze_before.json`, `candidate_freeze_after.json`.

## AC-03 — Reliability smoke gate — PASS
Each teacher: 10 seat-0 + 10 seat-1 games vs ≥2 strategic opponents; all
completed with **0** invalid actions, attributable exceptions, or timeouts.
Evidence: `test_logs/strategic_smoke_tests.txt` (= gauntlet execution log),
`artifacts/strategic_smoke_report.json`.

## AC-04 — Complete strategic gauntlet — PASS
All 6 unordered pairs, both seat orders, sequential stratified-bootstrap protocol
(2000 resamples), 720 games; no pair omitted.
Evidence: `strategic_gauntlet_games.jsonl.gz`, `strategic_matchup_matrix.csv`,
`strategic_pairwise_intervals.json`, `strategic_ranking.json`, `strategic_bootstrap.json`,
`strategic_worst_matchups.json`, `test_logs/strategic_gauntlet_execution.txt`.

## AC-05 — Teacher selection is reproducible — PASS
`competitive_score` + `teacher_score` computed from raw gauntlet artifacts (only
external_evidence is pre-registered, with per-candidate justification in the
scorecard). Primary **dragapult** (max teacher_score 0.889), backup **mega_lucario**
(different archetype). Primary is Submission-A eligible. No override.
Evidence: `teacher_scorecard.csv`, `teacher_selection.json`, `teacher_selection.md`.

## AC-06 — Frozen teacher pair — PASS
`frozen_teacher/` holds the exact policy (`main.py`), deck (`deck.csv`), bundled
`cg/`, plus `SOURCE.json` + `FREEZE.json` (canonical deck id, full multiset,
source/adapter hashes, agent version, reuse/attribution).
Evidence: `artifacts/frozen_teacher/`, `frozen_teacher_manifest.json`.

## AC-07 — Valid Submission A archive — PASS
`submission_A_teacher.tar.gz` (500,422 bytes < limit; structure main.py/deck.csv/cg/;
no secrets/training data). Clean extraction; **20** strategic smoke games from the
extracted archive vs the other teachers, **0** invalid / **0** non-terminal, P99 0.33ms.
Decision **SUBMIT**.
Evidence: `submission_A_teacher.tar.gz`, `submission_A_validation.json`,
`test_logs/submission_A_smoke.txt`, `SUBMISSION_A_DECISION.md`, `KAGGLE_SUBMIT_COMMAND.txt`.

## AC-08 — Optional Kaggle submission safely handled — PASS
`PTCG_ALLOW_KAGGLE_SUBMIT` absent → **no upload**; exact command provided; no
credentials read/written; single build (no duplicate submission).
Evidence: `kaggle_submission_status.json`, `test_logs/kaggle_submission.txt`.

## AC-09 — Strategic dataset minimum — PASS
**240** valid completed games, **19,050** teacher decisions (≥8000; stopping
"targets_met"). Both teacher seats (120/120). Required opponents present (backup,
other official, another archetype, engineering control, mirror; 48 games each).
Full schema-v2 observations + legal options + lineage; **0** invalid training records.
Evidence: `artifacts/teacher_dataset/`, `teacher_dataset_manifest.json`,
`test_logs/teacher_dataset_generation.txt`.

## AC-10 — Frozen train/validation/test split — PASS
Split by whole game; **no leakage** (verified); 170/37/33 games ≈ 70/15/15;
stratified by opponent/seat/outcome; **test frozen**.
Evidence: `teacher_dataset/splits.json`, `train.jsonl.gz`, `validation.jsonl.gz`,
`test.jsonl.gz`, `split_report.json`.

## AC-11 — Dataset quality and model readiness — PASS
Streaming validation: 19,050 records, **19,050 unique** deterministic example_ids,
**0** corrupt, **0** leakage, 0 field/label errors; context + selected-index
distributions reported; every record carries the required model inputs + labels.
Evidence: `teacher_dataset/quality_report.json`, `context_report.csv`, `schema.json`,
`test_logs/teacher_dataset_validation.txt`.

## AC-12 — c006 training specification — PASS
Model (structured legal-option scorer, 1–5M params), features, masking, BC loss,
optimizer/LR/epochs/early-stopping/weighting/seeds/checkpointing, CPU-inference +
package-size targets, and evaluation gates fully specified. No training performed.
Evidence: `c006_training_spec.md`, `c006_training_config.json`.

## AC-13 — Git and source integrity — PASS
9 c005 script files committed on the branch; **no** third-party teacher code,
archives, decks, or credentials committed (verified); frozen candidate/teacher
hashes recorded; earlier results untouched; final HEAD recorded.
Evidence: `GIT_REPORT.md`, `artifacts/c005.patch`, `source_snapshot/`,
`CLEAN_CHECKOUT.md`, `test_logs/final_git_status.txt`.

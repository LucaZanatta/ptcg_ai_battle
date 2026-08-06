# Acceptance Checklist — c003

Overall: **PASS** — 9/9 acceptance criteria verified.

## AC-01 — Schema-v2 lineage completeness — PASS
Requirement: complete run/Git/capture/environment/engine/agent/seed/deck lineage.
Verification: `.venv/bin/python -m unittest tests.test_schema_v2_lineage -v`; inspect run metadata + env report.
Result: 8 tests OK. `git.dirty=false`, commit `afe52db` matches HEAD; engine sha/size present; **both** players (`safe_agent` and `random_baseline`) carry full lineage (agent_id/version/policy_type/source_files+sha/configuration) in `run_metadata.agents` — no bare display-string identity (§7.3). The validator asserts every seat's agent_id resolves to a lineage entry.
Evidence: `test_logs/schema_v2_lineage_tests.txt`, `artifacts/validation_run/run_metadata.json`, `artifacts/environment_report.json`.
Notes: capture taken from the clean contract branch after committing source.

## AC-02 — Canonical deck identity — PASS
Requirement: order-independent deck IDs + full canonical multiset.
Verification: `.venv/bin/python -m unittest tests.test_deck_registry -v`.
Result: 7 tests OK — reorder→same id, one-card change→different id, duplicates aggregate, total validated. The validation run references its deck record.
Evidence: `test_logs/deck_registry_tests.txt`, `artifacts/deck_registry.json`, `artifacts/validation_run/deck_registry.json`.

## AC-03 — Honest seed and decision provenance — PASS
Requirement: no ambiguous `game_seed`; explicit controlled/uncontrolled RNG; real decision source/fallback.
Verification: `.venv/bin/python -m unittest tests.test_provenance -v`; scan of the dataset.
Result: 3 tests OK. Dataset: **0 game_seed occurrences**, `engine_rng_controlled` always false, decision_source counts {fallback:966, random_baseline:416}; source tracks the policy in both seats.
Evidence: `test_logs/provenance_tests.txt`, `artifacts/provenance_summary.json`.

## AC-04 — True semantic replay — PASS
Requirement: reproduce every safe-agent decision by reconstructing the serialized observation and invoking the safe agent (not duplicated bounds).
Verification: `.venv/bin/python tools/validate_episodes_v2.py <jsonl|gz> ...`.
Result: **966/966** safe-agent decisions reproduced exactly (convert_ok=966, 0 mismatches) on both jsonl and gzip; cross-field consistency passes. Validator calls `to_observation_class(obs)` then `safe_agent(obs)`.
Evidence: `test_logs/semantic_replay_jsonl.txt`, `test_logs/semantic_replay_gzip.txt`, `artifacts/semantic_replay_report.json`. Unit fixtures (match + 5 corrupt-fixture failures): `test_logs/... ` via `tests.test_semantic_replay`.

## AC-05 — Mutation-safe observation capture — PASS
Requirement: stored observation is the pre-policy input, unaffected by policy mutation.
Verification: `.venv/bin/python -m unittest tests.test_observation_snapshot -v`.
Result: 1 test OK — a fake policy mutating a nested field (`option[0]`) and a top-level field does not change the recorded snapshot (deep copy taken before the call).
Evidence: `test_logs/observation_snapshot_tests.txt`.

## AC-06 — Correct terminal classification — PASS
Requirement: classify from final state; structured normal/error/timeout outcomes.
Verification: `.venv/bin/python -m unittest tests.test_terminal_classification -v`; inspect dataset.
Result: 8 tests OK — normal_win (both seats), draw, agent_error (INVALID & ERROR), timeout, environment_error, unknown. All 30 real games classified (normal_win) from `env.steps[-1]`, not step 0.
Evidence: `test_logs/terminal_classification_tests.txt`, `artifacts/terminal_summary.json`.

## AC-07 — Streaming JSONL/GZIP and schema-v1 compatibility — PASS
Requirement: read/write v2 jsonl+gzip with equivalent streaming validation; read v1 without inventing provenance; reject unsupported versions.
Verification: `tests.test_compression`, `tests.test_schema_v1_compatibility`.
Result: gzip decompressed content **byte-identical** to jsonl (sha256 equal); both validate to identical counts/replay. Real c002 v1 file detected as schema 1 with 8 v2-only fields marked `legacy_unavailable`; `schema_version:99` rejected with a clear error.
Evidence: `test_logs/compression_tests.txt`, `test_logs/schema_v1_compatibility_tests.txt`, `artifacts/schema_v1_compatibility_report.json`.

## AC-08 — Fresh real cabt validation capture — PASS
Requirement: ≥30 completed games (10 per cohort, both seats, varying seeds); no invalid selections/malformed records; every safe decision replays; equivalent plain/gzip.
Verification: capture + `validate_episodes_v2.py`.
Result: **30/30 games** (10 safe-p0-vs-random, 10 random-p0-vs-safe, 10 safe-vs-safe), 1382 decisions, 0 invalid, 0 structural errors, 966/966 semantic replay, gzip≡jsonl. Both seats represented.
Evidence: `artifacts/validation_run/{episodes_v2.jsonl,episodes_v2.jsonl.gz,run_metadata.json,deck_registry.json,validation_report.json,context_report.json,latency_report.json}`, `test_logs/validation_capture_command.txt`, `test_logs/validation_capture_validation.txt`.

## AC-09 — Clean reproducible Git state — PASS
Requirement: source committed on the branch; no c001/c002 results modified; clean-checkout instructions; final HEAD recorded.
Verification: `GIT_REPORT.md`, patch, snapshots, `CLEAN_CHECKOUT.md`.
Result: three `c003:` commits; final HEAD `afe52db`; c003.patch (16 files, 1959 insertions, no whitespace errors); only untracked results packages remain; c001/c002 results untouched.
Evidence: `GIT_REPORT.md`, `artifacts/c003.patch`, `artifacts/source_snapshot/`, `artifacts/CLEAN_CHECKOUT.md`, `test_logs/final_git_status.txt`.

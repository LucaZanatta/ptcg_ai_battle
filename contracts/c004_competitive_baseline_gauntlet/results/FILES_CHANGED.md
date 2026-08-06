# Files Changed — c004

## New source (committed)
| File | Commit | Purpose |
|------|--------|---------|
| `starter_kit/replay_registry.py` | 30189fd | Amendment #3: verify agent id/version/source-hash before replay. |
| `starter_kit/candidates.py` | e584734 | Four frozen deck-agent candidates (policy × deck), adapters, freeze hashes. |
| `starter_kit/gauntlet_stats.py` | e584734 | Stratified-bootstrap seat-balanced CI, regularized Bradley-Terry, bootstrap ranking. |
| `tools/run_gauntlet.py` | e584734 | Freeze + smoke gate + sequential balanced round-robin + gzip schema-v2 capture. |
| `tools/analyze_gauntlet.py` | 9cc8426 | Matchup/seat/interval/BT/bootstrap/worst-matchup/reliability/latency/fallback + selection rule (code). |
| `tools/mine_tactical_failures.py` | 9cc8426 | Decode declined-attack MAIN failures for the c005 hypothesis. |
| `tests/test_c003_amendments.py` | 30189fd | AC-01 regression tests. |
| `tests/test_candidates.py` | e584734 | Candidate registry/adapter/freeze tests. |
| `tests/test_gauntlet_stats.py` | e584734 | AC-06 statistics (incl. BT finiteness). |
| `tests/test_gauntlet_analysis.py` | 9cc8426 | Analysis + mining tool tests (synthetic captures, reproducibility). |

## Modified source (committed)
| File | Commit | Change |
|------|--------|--------|
| `starter_kit/episode_schema.py` | 30189fd | Amendment #1: `final_state_terminal` (final-step error extraction). |
| `tools/validate_episodes_v2.py` | 30189fd | Amendment #2 (metadata equality) + amendment #3 (registry-verified replay). |
| `tools/capture_episodes_v2.py` | 30189fd | Use `final_state_terminal` in the capture path. |
| `tests/_v2_helpers.py`, `tests/test_semantic_replay.py`, `tests/test_compression.py` | 30189fd | Register a matching test agent so hash-verified replay passes on synthetic records. |

No candidate strategy or deck was modified; candidates were only frozen and run.
Snapshots of all 16 changed files at repo-relative paths: `artifacts/source_snapshot/`.

## Generated evidence (NOT committed; results package)
Reports (`SUMMARY.md`, `STATUS.json`, `FILES_CHANGED.md`, `COMMANDS_RUN.md`,
`ACCEPTANCE_CHECKLIST.md`, `GIT_REPORT.md`, `artifacts/CLEAN_CHECKOUT.md`),
`test_logs/*`, all `artifacts/*.json|csv|md`, `artifacts/gauntlet_games.jsonl.gz`
(~700 KB), `artifacts/tactical_failure_examples.jsonl`, `artifacts/source_snapshot/`,
`artifacts/c004.patch`.

## NOT changed / NOT staged
- No c001/c002/c003 contract results modified.
- Pre-existing untracked external assets left as-is.
- The cabt built-in deck is read from the installed env source (not modified).

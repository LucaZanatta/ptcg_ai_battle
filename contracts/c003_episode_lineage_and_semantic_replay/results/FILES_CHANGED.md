# Files Changed — c003

## New tracked source (committed)
| File | Commit | Purpose |
|------|--------|---------|
| `starter_kit/episode_schema.py` | d2e8502 | Schema-v2 lineage collectors, canonical deck registry, seed metadata, terminal classification. |
| `starter_kit/agents.py` | d2e8502 | `AgentDefinition` + policy-owned decision provenance; safe/random identities. |
| `starter_kit/episode_compat.py` | d2e8502 | v1/v2 + gzip streaming reader; legacy_unavailable marking; unsupported-version rejection. |
| `tools/environment_report.py` | d2e8502 | Python/package/platform/engine verification + machine-readable report. |
| `tests/test_schema_v2_lineage.py` | d2e8502 | AC-01 lineage tests. |
| `tests/test_deck_registry.py` | d2e8502 | AC-02 canonical deck tests. |
| `tests/test_schema_v1_compatibility.py` | d2e8502 | AC-07 v1 compatibility tests. |
| `starter_kit/episode_capture_v2.py` | 26363cc | Mutation-safe snapshot, gzip tee writer, structured provenance, final-state terminals. |
| `tools/capture_episodes_v2.py` | 26363cc | Lineage-complete 30-game capture runner. |
| `tools/validate_episodes_v2.py` | 26363cc | Structural + cross-field validation + true semantic replay + context/latency reports. |
| `tests/_v2_helpers.py` | 26363cc | Synthetic schema-v2 record builders (shared, non-test). |
| `tests/test_semantic_replay.py` | 26363cc | AC-04 semantic replay + corrupt-fixture failures. |
| `tests/test_observation_snapshot.py` | 26363cc | AC-05 mutation-safety. |
| `tests/test_terminal_classification.py` | 26363cc | AC-06 terminal classification. |
| `tests/test_provenance.py` | 26363cc | AC-03 provenance / no-game_seed. |
| `tests/test_compression.py` | 26363cc | AC-07 gzip equivalence. |

**Commit `afe52dbb` (c003: serialize random-baseline agent lineage in run
metadata)** further modified `tools/capture_episodes_v2.py` (emit
`run_metadata.agents.random_baseline` lineage), `tools/validate_episodes_v2.py`
(require `agents`/`decks` and assert every seat agent resolves to a lineage
entry), `tests/_v2_helpers.py`, and `tests/test_schema_v2_lineage.py` (new
every-player-lineage test).

No existing project files were modified (c001/c002 source untouched); c003 adds
new modules alongside them. Snapshots of all 16 files at their repo-relative
paths: `artifacts/source_snapshot/`.

## Generated evidence (NOT committed; results package)
Reports (`SUMMARY.md`, `STATUS.json`, `FILES_CHANGED.md`, `COMMANDS_RUN.md`,
`ACCEPTANCE_CHECKLIST.md`, `GIT_REPORT.md`, `artifacts/CLEAN_CHECKOUT.md`),
`test_logs/*`, `artifacts/*.json`, `artifacts/c003.patch`,
`artifacts/validation_run/*` (episodes_v2.jsonl + .gz + lineage + reports),
`artifacts/source_snapshot/`.

## NOT changed / NOT staged
- No c000/c001/c002 contract results modified.
- Pre-existing untracked external assets left as-is (declared in `runtime_assets.json`).
- Generated episode data is not committed (results package only).

# Files Changed — c002

## New tracked source/config (committed)
| File | Commit | Purpose |
|------|--------|---------|
| `runtime_assets.json` | f4b741d | Runtime asset manifest (AC-01). |
| `tools/verify_runtime_assets.py` | f4b741d | Manifest verifier (AC-01). |
| `REPRODUCIBILITY.md` | f4b741d | Clean-checkout reproduction docs (AC-02). |
| `tests/test_runtime_assets.py` | f4b741d | Manifest/verifier/symlink tests (§8 cat 1-4). |
| `.gitignore` | f4b741d | Narrow rule for generated episode data (`/episodes/`, `contracts/*/results/artifacts/episodes/`). |
| `starter_kit/episode_capture.py` | ff6e94b | Schema-v1 capture module (AC-04). |
| `tools/capture_episodes.py` | ff6e94b | 3-cohort seed/seat capture runner + replay-check. |
| `tools/validate_episode_jsonl.py` | ff6e94b | Streaming round-trip validator (AC-05). |
| `tools/context_coverage_report.py` | ff6e94b | Context/latency coverage report (AC-06). |
| `tests/test_episode_capture.py` | ff6e94b | Capture/validation/side-effect/behavior tests (§8 cat 5-13). |

## Modified tracked source (committed)
| File | Commit | Change |
|------|--------|--------|
| `tests/test_safe_policy.py` | ff6e94b | Removed the `enum_context_coverage.json` write; assertions only (§5.4). |
| `tests/test_agent_integration.py` | ff6e94b | Removed the `deck_validation.json` write; assertions only (§5.4). |

## Snapshot mapping (§5.9)
`results/artifacts/source_snapshot/` mirrors every changed file above at its
repository-relative path. `results/artifacts/c002.patch` is the full diff
`283f31c..ff6e94b` (12 files, 1638 insertions / 51 deletions).

## Generated evidence (NOT committed; in the results package)
Reports (`SUMMARY.md`, `STATUS.json`, `FILES_CHANGED.md`, `COMMANDS_RUN.md`,
`ACCEPTANCE_CHECKLIST.md`, `GIT_REPORT.md`), `test_logs/*`, `artifacts/*.json|csv|md`,
`artifacts/episodes/episodes.jsonl` (12 MB, `.gitignore`d), source snapshots,
`failures/AC04_engine_nondeterminism.md`.

## NOT changed / NOT staged
- No c000/c001 contract results were modified.
- Pre-existing untracked files left as-is: `cg`, `check.py`, `tmp.txt`,
  `pokemon-tcg-ai-battle-challenge-strategy/`, and the external starter-kit
  files (`starter_kit/api.py`, `sim.py`, `game.py`, `utils.py`, `__init__.py`,
  `deck.csv`, `libcg.so`, symlinks) — declared in `runtime_assets.json`.
- `starter_kit/main.py` / `safe_policy.py` unchanged by c002 (c001 code); the
  capture layer wraps the agent externally and preserves its behavior.

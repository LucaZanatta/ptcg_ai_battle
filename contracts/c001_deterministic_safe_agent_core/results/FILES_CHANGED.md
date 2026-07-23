# Files Changed — c001

## Project source (committed in the implementation commit)
| File | Why | Summary |
|------|-----|---------|
| `starter_kit/main.py` | F-02 entrypoint | Rewrote `agent` to use the safe policy and a cached validated deck; removed `random`. Was **previously untracked** (starter-kit content), so the committed diff shows it as an added file with its final safe content. |
| `starter_kit/safe_policy.py` | F-01 new module | New pure deterministic selector + validation + deck loader (`MalformedSelection`, `MalformedDeck`, `validate_bounds`, `select_indices`, `select_for`, `validate_selection`, `parse_deck`, `load_deck`, `default_deck_path`). |
| `tests/__init__.py` | make `tests` a package | Empty; enables `python -m unittest tests.test_*`. |
| `tests/test_safe_policy.py` | F-04 unit tests | 25 tests: selector, bounds, validation, deck parsing, all 49 `SelectContext` members. Emits `enum_context_coverage.json`. |
| `tests/test_agent_integration.py` | F-04 / AC-03 / AC-07 | 5 tests: deck determinism + rejection, both-seat harness smoke. Emits `deck_validation.json`. |
| `tools/benchmark_safe_agent.py` | F-05 benchmark | 3-cohort 300-game benchmark; latency/context/validity instrumentation; writes benchmark + runtime-coverage JSON. |

Source-path mapping to the required snapshot filenames (H): identity mapping —
`starter_kit/main.py`→`starter_kit_main.py`, `starter_kit/safe_policy.py`→`starter_kit_safe_policy.py`,
tests/tools by basename. No "approved equivalent path" was needed.

## Generated evidence (committed in the evidence commit, under this contract folder)
`results/SUMMARY.md`, `STATUS.json`, `FILES_CHANGED.md`, `COMMANDS_RUN.md`,
`ACCEPTANCE_CHECKLIST.md`, `GIT_REPORT.md`, `test_logs/*.txt`,
`artifacts/*.json`, `artifacts/committed_diff.patch`,
`artifacts/source_snapshot/*.py`, `failures/NONE.md`.

## Generated (NOT committed)
- `__pycache__/` directories (ignored).

## Unrelated repository files — NOT touched, NOT staged
Pre-existing untracked entries left exactly as found and deliberately excluded
from all commits: `starter_kit/libcg.so`, `starter_kit/api.py`, `starter_kit/sim.py`,
`starter_kit/game.py`, `starter_kit/utils.py`, `starter_kit/deck.csv`,
`starter_kit/__init__.py`, `cg`, `check.py`, `tmp.txt`, `test_engine.py`,
`pokemon-tcg-ai-battle-challenge-strategy/`, `.venv/`.

> Note: only `starter_kit/main.py` and `starter_kit/safe_policy.py` were staged
> from `starter_kit/`, by exact path; the binary engine and other starter-kit
> files remain untracked.

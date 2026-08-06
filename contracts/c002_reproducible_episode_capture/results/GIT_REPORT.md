# Git Report — c002

## Initial state (before work)
- Initial branch: `contract/c001_deterministic_safe_agent_core`
- Initial HEAD: `283f31c102af92040bd7620088921e7424fab656`
- Initial `git status --short`:
  ```
  ?? cg
  ?? check.py
  ?? contracts/c002_reproducible_episode_capture/
  ?? pokemon-tcg-ai-battle-challenge-strategy/
  ?? starter_kit/__init__.py
  ?? starter_kit/api.py
  ?? starter_kit/cg
  ?? starter_kit/deck.csv
  ?? starter_kit/game.py
  ?? starter_kit/sim.py
  ?? starter_kit/utils.py
  ?? tmp.txt
  ```

## Contract branch and final state
- Contract branch: `contract/c002_reproducible_episode_capture` (created from `283f31c`).
- Final HEAD: `ff6e94bd0c81dc173d1704be0337e738458ab05b`

## Commits (both prefixed `c002:`)
- `f4b741d85e8e984f20b8476c61908dd95abfe713` — c002: add reproducible runtime asset verification
- `ff6e94bd0c81dc173d1704be0337e738458ab05b` — c002: add versioned episode capture and validation

No self-referential evidence commit was made (per §13): the results package
records the hashes above. The `results/` folder is intentionally **not** committed.

## `git diff --stat 283f31c..ff6e94b`
```
 .gitignore                       |   6 +
 REPRODUCIBILITY.md               |  95 ++++++++++
 runtime_assets.json              | 170 +++++++++++++++++
 starter_kit/episode_capture.py   | 222 +++++++++++++++++++++
 tests/test_agent_integration.py  |  39 +---
 tests/test_episode_capture.py    | 221 +++++++++++++++++++++
 tests/test_runtime_assets.py     |  90 ++++++++++
 tests/test_safe_policy.py        |  23 +--
 tools/capture_episodes.py        | 322 ++++++++++++++++++++++++++++++++
 tools/context_coverage_report.py | 187 ++++++++++++++++++
 tools/validate_episode_jsonl.py  | 165 ++++++++++++++++
 tools/verify_runtime_assets.py   | 149 +++++++++++++++
 12 files changed, 1638 insertions(+), 51 deletions(-)
```
`git diff --check 283f31c..ff6e94b` → no whitespace errors. Patch:
`artifacts/c002.patch`. The 51 deletions are the removed test side-effect code
(c001 tests no longer write into contract results).

## Final `git status --short` — line-by-line
```
?? cg                                        external symlink (runtime asset; declared in manifest)
?? check.py                                  pre-existing user scratch (not c002)
?? contracts/c002_reproducible_episode_capture/   this contract's package (results NOT committed by design)
?? pokemon-tcg-ai-battle-challenge-strategy/ pre-existing competition card data (not c002)
?? starter_kit/__init__.py                   external starter-kit asset (declared in manifest)
?? starter_kit/api.py                        external starter-kit asset (declared in manifest)
?? starter_kit/cg                            external symlink (declared in manifest)
?? starter_kit/deck.csv                      external competition deck (declared in manifest)
?? starter_kit/game.py                       external starter-kit asset (declared in manifest)
?? starter_kit/sim.py                        external starter-kit asset (declared in manifest)
?? starter_kit/utils.py                      external starter-kit asset (declared in manifest)
?? tmp.txt                                   pre-existing user scratch (not c002)
```
Notes:
- `starter_kit/main.py`, `starter_kit/safe_policy.py`, `starter_kit/episode_capture.py`
  are **tracked** (committed on c001/c002) so they no longer appear as untracked.
- `starter_kit/libcg.so` does not appear because it is `.gitignore`d (`*.so`).
- Generated episode JSONL under the contract results is `.gitignore`d and lives
  only in the results package.

## Confirmations
- **No c000/c001 results were modified** (verified: byte-identical dir hashes
  before/after the test runs; `git status` clean on those tracked files).
- **No pre-existing user changes** were staged, discarded, or committed.
- **No destructive Git command** (`reset --hard`, `clean -fd`, `checkout/restore
  <file>`) was used; no push/rebase/amend/force/remote change.
- Runtime assets that are required but not tracked are declared in
  `runtime_assets.json` with sha256.

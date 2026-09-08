# Git Report — c003

## Initial state (before work)
- Initial branch: `contract/c002_reproducible_episode_capture`
- Initial HEAD: `ff6e94bd0c81dc173d1704be0337e738458ab05b`

## Contract branch and final state
- Contract branch: `contract/c003_episode_lineage_and_semantic_replay` (from `ff6e94b`).
- Final HEAD: `afe52dbbbc75e6ee592bb4a6878fd4dfa43d0525`

## Commits (all prefixed `c003:`)
- `d2e8502739c2fc04413d617b9171b07b98df28de` — c003: add schema v2 lineage, deck registry, and compat reader
- `26363ccd6308ecd319e6e04758825559223cf470` — c003: add v2 capture, semantic replay, terminal validation, gzip
- `afe52dbbbc75e6ee592bb4a6878fd4dfa43d0525` — c003: serialize random-baseline agent lineage in run metadata

Source was committed **before** the 30-game acceptance capture, so the capture's
`run_metadata.git.dirty=false` and its source/engine sha256 values match the
committed branch (commit `afe52db`). No self-referential evidence commit; results
are uncommitted (see below).

## `git diff --stat ff6e94b..afe52db`
```
16 files changed, 1959 insertions(+)
 starter_kit/{agents,episode_schema,episode_capture_v2,episode_compat}.py
 tools/{capture_episodes_v2,validate_episodes_v2,environment_report}.py
 tests/{_v2_helpers,test_schema_v2_lineage,test_deck_registry,test_provenance,
        test_observation_snapshot,test_terminal_classification,test_semantic_replay,
        test_compression,test_schema_v1_compatibility}.py
```
`git diff --check ff6e94b..afe52db` → no whitespace errors. Patch:
`artifacts/c003.patch`.

## Final `git status --short`
```
?? contracts/c002_reproducible_episode_capture/
?? contracts/c003_episode_lineage_and_semantic_replay/
```
plus the pre-existing untracked external assets (`cg`, `check.py`, `tmp.txt`,
`pokemon-tcg-ai-battle-challenge-strategy/`, and the starter-kit files
`starter_kit/{api,sim,game,utils,__init__,deck.csv,cg}` — declared in
`runtime_assets.json`; `libcg.so` is `.gitignore`d). Full listing:
`test_logs/final_git_status.txt`.

## Results policy
Per §11, the contract `results/` package is intentionally **uncommitted** (it is
external review evidence). The generated 30-game episode data (`.jsonl` ~5 MB,
`.jsonl.gz` ~288 KB) lives only in the results package. All required **source**
changes are committed.

## Confirmations
- **No c001/c002 results were modified.**
- No pre-existing user changes were staged or discarded.
- No destructive Git command (`reset --hard`, `clean -fd`, `checkout/restore
  <file>`) was used; no push/rebase/amend/force/remote change.
- Final branch HEAD recorded above.

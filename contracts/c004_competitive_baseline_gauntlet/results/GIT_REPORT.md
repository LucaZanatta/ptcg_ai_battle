# Git Report — c004

## Initial state
- Initial branch: `contract/c003_episode_lineage_and_semantic_replay`
- Initial HEAD: `afe52dbbbc75e6ee592bb4a6878fd4dfa43d0525`

## Contract branch and final state
- Contract branch: `contract/c004_competitive_baseline_gauntlet` (from `afe52db`).
- Final HEAD: `9cc842681fedde99f8aec131a8ef46d052bce7c5`

## Commits (all `c004:`)
- `30189fd1a73491bc3d8aa6afff3a1880dae647ed` — c004: fix competitive replay and terminal validation
- `e584734ae3e69f5a65b1d8eed7d9f142d18ed6a1` — c004: add frozen candidate registry and gauntlet runner
- `9cc842681fedde99f8aec131a8ef46d052bce7c5` — c004: add ranking analysis and baseline selection evidence

Source (Phase-0 amendments + candidates + runner) was committed **before** the
gauntlet capture, so the capture's `run_metadata.git.dirty=false` and its source
hashes match commit `e584734` (candidate/adapter source unchanged thereafter, so
freeze hashes still hold). No self-referential evidence commit; results are
uncommitted (below).

## `git diff --stat afe52db..9cc8426`
```
16 files changed, 1623 insertions(+), 46 deletions(-)
 starter_kit/{episode_schema,replay_registry,candidates,gauntlet_stats}.py
 tools/{validate_episodes_v2,capture_episodes_v2,run_gauntlet,analyze_gauntlet,mine_tactical_failures}.py
 tests/{_v2_helpers,test_semantic_replay,test_compression,test_c003_amendments,
        test_candidates,test_gauntlet_stats,test_gauntlet_analysis}.py
```
`git diff --check afe52db..9cc8426` → no whitespace errors. Patch: `artifacts/c004.patch`.

## Frozen candidate integrity
Candidate freeze hashes recorded **before** and **after** the gauntlet are
identical (`candidate_freeze_hashes_before.json == candidate_freeze_hashes_after.json`);
no candidate strategy or deck was modified. `starter_kit/candidates.py` is
unchanged after commit `e584734`.

## Final `git status --short`
```
?? contracts/c002_reproducible_episode_capture/
?? contracts/c003_episode_lineage_and_semantic_replay/
?? contracts/c004_competitive_baseline_gauntlet/
```
plus the pre-existing untracked external assets (`cg`, `check.py`, `tmp.txt`,
`pokemon-tcg-ai-battle-challenge-strategy/`, starter-kit `api/sim/game/utils/__init__/deck.csv/cg`;
`libcg.so` is `.gitignore`d). Full listing: `test_logs/final_git_status.txt`.

## Confirmations
- **No c001/c002/c003 results modified.**
- No pre-existing user changes staged or discarded.
- No destructive git command; no push/rebase/amend/force/remote change.
- No strategic modification of candidate policies/decks committed.
- Final HEAD recorded above. Contract `results/` intentionally uncommitted
  (external review evidence); the ~700 KB gzip gauntlet capture lives only there.

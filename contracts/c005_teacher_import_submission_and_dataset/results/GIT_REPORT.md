# Git Report — c005

## Initial state
- Initial branch: `contract/c004_competitive_baseline_gauntlet`
- Initial HEAD: `9cc842681fedde99f8aec131a8ef46d052bce7c5`

## Contract branch and final state
- Contract branch: `contract/c005_teacher_import_submission_and_dataset` (from `9cc8426`).
- Final HEAD: `4137d983c6a05c0eea8332718d3e7f3acc7b7830`

## Commits (all `c005:`)
- `5e47d15e55e7f6e621091377c1f9b82de6730e09` — c005: add strategic teacher acquisition and loader
- `53b6fcab08d46b89e9a2dc3df144389cff0291c9` — c005: fix teacher loader test to use a real game observation
- `d052c2843d1a64737563e168e5d21f924285cc6b` — c005: add teacher gauntlet analysis, selection, and submission packaging
- `4137d983c6a05c0eea8332718d3e7f3acc7b7830` — c005: add teacher dataset streaming validator

Gauntlet/dataset captures were run from a clean tracked tree (`git.dirty=false`);
candidate/teacher freeze hashes recorded before==after. Results uncommitted.

## `git diff --stat 9cc8426..4137d98`
```
9 files changed, 1618 insertions(+)
 starter_kit/teachers.py
 tools/{acquire_teachers,run_strategic_gauntlet,analyze_strategic_gauntlet,
        select_teacher,build_submission,generate_teacher_dataset,validate_teacher_dataset}.py
 tests/test_teachers.py
```
`git diff --check 9cc8426..4137d98` → no whitespace errors. Patch: `artifacts/c005.patch`.

## Third-party / credential safety (AC-13)
- **Only c005 scripts are committed.** No third-party teacher code (official
  kernels or the public repo), no decks, no archives, and **no credentials** were
  committed — verified by scanning the committed diff for
  `teacher_sources|frozen_teacher|*.tar.gz|kaggle.json|main.py|deck.csv|ptcg-abc|kiyotah`
  (zero matches).
- Raw third-party downloads, the frozen teacher directory, the submission archive,
  and the dataset all live under this contract's `results/` (uncommitted).

## Final `git status --short`
```
?? contracts/c002_reproducible_episode_capture/
?? contracts/c003_episode_lineage_and_semantic_replay/
?? contracts/c004_competitive_baseline_gauntlet/
?? contracts/c005_teacher_import_submission_and_dataset/
```
plus pre-existing untracked external assets (`cg`, `check.py`, `tmp.txt`,
`pokemon-tcg-ai-battle-challenge-strategy/`, starter-kit `api/sim/game/utils/__init__/deck.csv/cg`;
`libcg.so` `.gitignore`d). Full listing: `test_logs/final_git_status.txt`.

## Confirmations
- No c001–c004 results modified. No pre-existing user changes staged/discarded.
- No destructive git command; no push/rebase/amend/force/remote change.
- Candidate/teacher strategy and decks unchanged after freeze.
- Final HEAD recorded above.

# Commands Run — c005

From repo root `/home/luca/kaggle/ptcg_ai_battle`, interpreter `.venv/bin/python`.
No secrets. Kaggle public kernels read anonymously (no credentials present/used).

## Git init + branch
```bash
git status --short; git branch --show-current; git rev-parse HEAD   # 9cc8426
git switch -c contract/c005_teacher_import_submission_and_dataset
```

## Phase A — acquisition + audit
```bash
.venv/bin/python tools/acquire_teachers.py --out-dir <artifacts>/teacher_sources
# 4 official kiyotah kernels (kaggle kernels output/pull) + git clone wmh/ptcg-abc @1b31d39a
# -> source_evidence.json, teacher_research.md, rules_and_reuse_audit.md
```

## Feasibility de-risk (probes)
```bash
# SDK identical to starter kit (libcg.so sha 75d7d619); teachers run as fresh
# module instances per game per seat (module-level state -> fresh isolation);
# two teachers play with their own decks; competition rules page is a JS shell.
```

## Commit source BEFORE the long runs (clean tree)
```bash
git commit -m "c005: add strategic teacher acquisition and loader"   # 5e47d15
git commit -m "c005: fix teacher loader test to use a real game observation"  # 53b6fca
```

## Phase C — strategic gauntlet (clean tree)
```bash
.venv/bin/python tools/run_strategic_gauntlet.py --base-seed 5150 --require-clean \
  --sources <artifacts>/teacher_sources --out-dir <artifacts>
# -> 80 smoke + 720 gauntlet games, freeze before==after, dirty=false
.venv/bin/python tools/analyze_strategic_gauntlet.py --in-dir <artifacts> --out-dir <artifacts>
.venv/bin/python tools/select_teacher.py --in-dir <artifacts> --out-dir <artifacts>
# -> primary=dragapult, backup=mega_lucario
```

## Phase D — Submission A
```bash
.venv/bin/python tools/build_submission.py --primary dragapult \
  --sources <artifacts>/teacher_sources --out-dir <artifacts>
# -> submission_A_teacher.tar.gz (500422 B), 20 extracted smoke games, 0 defects, SUBMIT
# AC-08: PTCG_ALLOW_KAGGLE_SUBMIT absent -> no upload; command recorded.
git commit -m "c005: add teacher gauntlet analysis, selection, and submission packaging"  # d052c28
```

## Phase E/F — dataset + spec
```bash
.venv/bin/python tools/generate_teacher_dataset.py --primary dragapult --backup mega_lucario \
  --sources <artifacts>/teacher_sources --out-dir <artifacts>/teacher_dataset --base-seed 424242
# -> 240 games, 19050 teacher decisions, whole-game 70/15/15 splits, test frozen
.venv/bin/python tools/validate_teacher_dataset.py --dir <artifacts>/teacher_dataset
# -> 19050 records, unique ids, 0 corrupt, no leakage, PASS
git commit -m "c005: add teacher dataset streaming validator"   # 4137d98 (final HEAD)
```

## Git evidence
```bash
git diff 9cc8426..4137d98 -- starter_kit tools tests > results/artifacts/c005.patch
git diff --check 9cc8426..4137d98          # no whitespace errors
# leak scan of committed diff -> zero third-party/credential matches
git status --short > results/test_logs/final_git_status.txt
```

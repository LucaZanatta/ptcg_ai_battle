# Clean Checkout & Run — c005

Reproduce c005 from a clean checkout of branch
`contract/c005_teacher_import_submission_and_dataset` (final HEAD
`4137d983c6a05c0eea8332718d3e7f3acc7b7830`). Run from repo root with `.venv/bin/python`.

## 1. Runtime assets (as in c002–c004) + Kaggle CLI
Git-tracked: all c001–c005 `starter_kit/*.py` and `tools/*.py`. Provide externally
(see `runtime_assets.json`): starter-kit `api/sim/game/utils/__init__/deck.csv`,
`libcg.so` (`.gitignore`d), the `cg`/`starter_kit/cg` symlinks, and
`kaggle-environments==1.30.1`. The `kaggle` CLI (already in `.venv`) reads public
kernels anonymously — **no credentials required** for acquisition.

## 2. Acquire the teachers (third-party, into results/)
```bash
.venv/bin/python tools/acquire_teachers.py \
  --out-dir contracts/c005_teacher_import_submission_and_dataset/results/artifacts/teacher_sources
```
This downloads the 4 official kiyotah sample kernels and clones `wmh/ptcg-abc`.
Third-party code stays under `results/` and is **not** committed.

## 3. Tests
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v   # 119 tests OK (teacher tests skip if sources absent)
```

## 4. Gauntlet → selection → submission
```bash
SRC=contracts/c005_teacher_import_submission_and_dataset/results/artifacts/teacher_sources
OUT=contracts/c005_teacher_import_submission_and_dataset/results/artifacts
.venv/bin/python tools/run_strategic_gauntlet.py --base-seed 5150 --require-clean --sources $SRC --out-dir $OUT
.venv/bin/python tools/analyze_strategic_gauntlet.py --in-dir $OUT --out-dir $OUT
.venv/bin/python tools/select_teacher.py --in-dir $OUT --out-dir $OUT
.venv/bin/python tools/build_submission.py --primary dragapult --sources $SRC --out-dir $OUT
```

## 5. Dataset
```bash
.venv/bin/python tools/generate_teacher_dataset.py --primary dragapult --backup mega_lucario \
  --sources $SRC --out-dir $OUT/teacher_dataset --base-seed 424242
.venv/bin/python tools/validate_teacher_dataset.py --dir $OUT/teacher_dataset
```

## 6. Actual Kaggle submission (opt-in, NOT run by default)
Upload only with the flag set and Kaggle credentials configured:
```bash
PTCG_ALLOW_KAGGLE_SUBMIT=1 kaggle competitions submit -c pokemon-tcg-ai-battle \
  -f $OUT/submission_A_teacher.tar.gz -m "c005 Submission A: frozen teacher dragapult"
```

## 7. Reproducibility scope
Acquisition (kernel outputs) and selection scoring are reproducible. The gauntlet
and dataset **games** are not bit-reproducible (engine `std::random_device`), but
the qualitative ranking (dragapult ≈ lucario ≫ abomasnow > iono), the teacher
selection, and the dataset **splits** (seeded, from fixed captures) are stable.

## 8. Results policy
The contract `results/` package (reports + third-party sources + submission +
dataset) is review evidence and is **not committed**; only c005 scripts are on the
branch.

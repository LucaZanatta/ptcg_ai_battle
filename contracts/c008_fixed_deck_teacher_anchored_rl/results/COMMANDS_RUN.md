# c008 — Commands Run (reproduction order)

From repo root with `.venv/bin/python`. RL updates use multi-threaded BLAS (RL is
non-reproducible); `OUT=contracts/c008_fixed_deck_teacher_anchored_rl/results`.

```bash
# AC-01 dependency + immutability verification
python tools/c008_verify_deps.py --out-dir $OUT/artifacts --log $OUT/test_logs/dependency_verification.txt

# AC-03/AC-04 masked PPO env + policy + PPO validation (toy positive control, GAE, masking, smoke)
OMP_NUM_THREADS=4 python tools/c008_validate_rl.py --out-dir $OUT/artifacts --log-dir $OUT/test_logs

# AC-02 experiment registration (freeze before training)
python tools/c008_register_experiment.py

# AC-05/06/07 training — each arm/seed as its OWN background process (nproc 7-10, OMP 5-6)
OMP_NUM_THREADS=6 python tools/train_rl.py --arm R0 --seed 101 --out-dir $OUT/artifacts/training --nproc 9
OMP_NUM_THREADS=6 python tools/train_rl.py --arm R0 --seed 202 --out-dir $OUT/artifacts/training --nproc 9
OMP_NUM_THREADS=6 python tools/train_rl.py --arm R1 --seed 101 --out-dir $OUT/artifacts/training --nproc 10
OMP_NUM_THREADS=6 python tools/train_rl.py --arm R1 --seed 202 --out-dir $OUT/artifacts/training --nproc 9
OMP_NUM_THREADS=5 python tools/train_rl.py --arm R2 --seed 101 --out-dir $OUT/artifacts/training --nproc 7
OMP_NUM_THREADS=5 python tools/train_rl.py --arm R2 --seed 202 --out-dir $OUT/artifacts/training --nproc 7
OMP_NUM_THREADS=5 python tools/train_rl.py --arm R2 --seed 303 --out-dir $OUT/artifacts/training --nproc 7

# AC-08 aggregate curves + checkpoint registry + per-arm representative + plots
python tools/c008_aggregate.py

# AC-09/10/11 final eval (best checkpoint per arm; reliability, teacher non-inf, strategic + held-out)
OMP_NUM_THREADS=2 python tools/c008_final_eval.py --candidates '<best-per-arm ckpts>' --nproc 16 \
    --rel-per-seat 40 --noninf-per-seat 200 --strat-per-combo 40

# AC-12/13/15 registered decisions
python tools/c008_decide.py

# AC-14 gated Kaggle (SKIPPED_BY_GATE) + read-only teacher refresh (ref 54948560)
python tools/c008_finalize.py

# AC-16 reports + STATUS/checklist/git/patch/snapshot/immutability recheck (run last, source committed)
python tools/c008_reports.py
```

Notes:
- No `kaggle competitions submit` was executed — `SUBMISSION_D = DO_NOT_SUBMIT`. Only a
  read-only `kaggle competitions submissions` refresh of teacher ref 54948560 was run.
- IMPORTANT: launch each training seed as its OWN background job (not `&` within one
  wrapper) — an orphaned wrapper deadlocks the spawn rollout pool.
- Screening evaluation games do NOT consume the training-game budget.
- One documented pre-training defect (screening control-label) was corrected under the
  registration restart rule before any arm completed.

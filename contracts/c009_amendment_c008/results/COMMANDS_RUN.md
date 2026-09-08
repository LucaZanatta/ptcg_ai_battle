# c009 — Commands Run (reproduction order)

From repo root with `.venv/bin/python`. `OUT=contracts/c009_amendment_c008/results`.
Evaluation-only: no training, no weight mutation, no checkpoint creation.

```bash
# AC-01 dependency + immutability verification (c005-c008 + all candidate checkpoints)
python tools/c009_verify_deps.py --out-dir $OUT/artifacts --log $OUT/test_logs/dependency_verification.txt

# AC-02 reproduce the c008 identity defect (synthetic + real multiprocessing + forensic)
python tools/c009_defect_repro.py --out-dir $OUT/artifacts --log $OUT/test_logs/c008_defect_reproduction.txt

# AC-03 identity-safe evaluator tests (incl. rejection of the c008 positional-zip pattern)
python -m unittest tests.test_c009_eval_identity -v   # -> $OUT/test_logs/evaluator_identity_tests.txt

# AC-04 frozen candidate registry (B0 + frozen teacher + all c008 validation-selected)
python tools/c009_registry.py --out-dir $OUT/artifacts --log $OUT/test_logs/checkpoint_registry_validation.txt

# AC-05/06/07/08 staged identity-safe evaluation (Phase A/B/C, Phase D only if a candidate qualifies)
OMP_NUM_THREADS=2 python tools/c009_eval_repair.py --nproc 16 \
    --phase-a-per-seat 50 --phase-b-per-seat 150 --phase-b-ext-per-seat 200 --phase-c-per-seat 50

# supplementary Phase C batch so a statistical tie is broken on evidence, not sample size
OMP_NUM_THREADS=2 python tools/c009_eval_supplement.py --candidates R2_303 --per-seat 50 --nproc 16 \
    --reason "R2_101 (n=100) and R2_303 (n=400) statistically tied on the teacher score"

# AC-09/10/11 recompute every aggregate from the corrected raw games
python tools/c009_aggregate_repair.py

# AC-10/11/13/15 amended decisions (improvement-over-B0, best checkpoint, feasibility, next step)
python tools/c009_decide.py

# AC-13/14 conditional package + Kaggle (DO_NOT_SUBMIT -> SKIPPED_BY_GATE) + read-only teacher refresh
python tools/c009_finalize.py

# AC-12 content-aware evidence validation (independent bootstrap seed; recomputes from raw)
python tools/c009_validate_evidence.py
python -m unittest tests.test_c009_evidence_validation   # 13 corruptions must be detected

# AC-16 immutability recheck, git report/patch/snapshot, STATUS + acceptance checklist (run last)
python tools/c009_reports.py
```

Notes:
- No `kaggle competitions submit` was executed — `SUBMISSION_D_AMENDED = DO_NOT_SUBMIT`. Only a
  read-only `kaggle competitions submissions -v` refresh of teacher ref `54948560` ran; its
  public score is read from the `publicScore` **column by index**, not by scanning for a float.
- Total evaluation budget consumed: **4,100 games** (contract target 2,000–5,000). No 800-game
  teacher extension was needed — no candidate's upper uncertainty region reached 0.40 — and
  Phase D did not run because no candidate passed non-inferiority.
- Every worker returns its own `job_id / candidate_id / checkpoint_sha256 / opponent_id / seat /
  replicate / phase`, re-hashes the checkpoint it loaded, and fingerprints the deck it played;
  nine assertions run before any aggregation. There is no positional reattachment anywhere.

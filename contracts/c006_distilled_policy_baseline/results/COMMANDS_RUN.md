# c006 — Commands Run (reproduction order)

All from repo root with `.venv/bin/python` and `OMP_NUM_THREADS=1` for training/eval.
`OUT=contracts/c006_distilled_policy_baseline/results`

```bash
# AC-01 dependency/freeze verification + Kaggle teacher refresh
.venv/bin/python tools/c006_verify_deps.py --out $OUT/artifacts/c005_dependency_verification.json
#   (recorded baseline preserved; live `kaggle competitions submissions -v` captured; ref 54948560 -> 674.6 live)

# AC-02/03 ordered sequence dataset + stateless ambiguity (train+val only)
.venv/bin/python tools/build_sequence_dataset.py --out-dir $OUT/artifacts
.venv/bin/python tools/stateless_ambiguity.py --in-dir $OUT/artifacts --out-dir $OUT/artifacts

# AC-04 full legal-card vocabulary
.venv/bin/python tools/c006_build_vocab.py --out-dir $OUT/artifacts

# AC-05 decision taxonomy + decoder coverage
.venv/bin/python tools/c006_taxonomy_decoders.py --in-dir $OUT/artifacts --out-dir $OUT/artifacts

# model-core gradient/parity/param tests (hard gate before training)
OMP_NUM_THREADS=1 .venv/bin/python -m unittest tests.test_c006_models

# §6 experiment registration (freeze BEFORE training)
OMP_NUM_THREADS=1 .venv/bin/python tools/c006_register_experiment.py --art-dir $OUT/artifacts

# AC-06 registered reproducible training (S1x3, S2x3)
OMP_NUM_THREADS=1 .venv/bin/python tools/train_student.py --arch both --in-dir $OUT/artifacts --log-dir $OUT/test_logs
#   reproducibility: re-ran S1 seed 101 -> byte-identical checkpoint sha256

# AC-07 frozen offline evaluation (opens test split once) + memory ablation
OMP_NUM_THREADS=1 .venv/bin/python tools/offline_eval.py --in-dir $OUT/artifacts

# AC-08 reliability smoke + latency
OMP_NUM_THREADS=1 .venv/bin/python tools/c006_gameplay.py --phase smoke   --ckpt-dir $OUT/artifacts/checkpoints --out $OUT/artifacts --nproc 12

# AC-09 student-vs-teacher non-inferiority
OMP_NUM_THREADS=1 .venv/bin/python tools/c006_gameplay.py --phase noninf  --ckpt-dir $OUT/artifacts/checkpoints --out $OUT/artifacts --nproc 16

# AC-10 strategic gauntlet (games) + analysis
OMP_NUM_THREADS=1 .venv/bin/python tools/c006_gameplay.py --phase gauntlet --ckpt-dir $OUT/artifacts/checkpoints --out $OUT/artifacts --nproc 16 --max-per-seat 40
.venv/bin/python tools/analyze_student_gauntlet.py --gz $OUT/artifacts/student_strategic_gauntlet.jsonl.gz --out-dir $OUT/artifacts --log $OUT/test_logs/student_gauntlet_execution.txt

# §16/AC-12 diagnostic package (BEST_STUDENT=NONE -> NOT_FOR_SUBMISSION) + validation
OMP_NUM_THREADS=1 .venv/bin/python tools/build_submission_b.py --arch S1_STATELESS --ckpt-dir $OUT/artifacts/checkpoints --out $OUT/artifacts --games 40

# AC-11/12/13 registered gate decisions (BEST_STUDENT, memory, SUBMISSION_B, PROMOTION, RL_READINESS)
.venv/bin/python tools/c006_decide.py --art $OUT/artifacts

# AC-14 git/source integrity artifacts (patch, source_snapshot, final status) — see GIT_REPORT.md
```

Notes:
- No `kaggle competitions submit` was executed — `SUBMISSION_B=DO_NOT_SUBMIT` (gate).
- Gameplay uses `spawn` multiprocessing so each worker loads `libcg.so` fresh.
- Authoritative per-move latency is the single-process offline/package measurement; the
  parallel gameplay latency is contention-inflated (documented in `model_latency_report.json`).

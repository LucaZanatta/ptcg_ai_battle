# c007 — Commands Run (reproduction order)

From repo root with `.venv/bin/python` and `OMP_NUM_THREADS=1`.
`OUT=contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/results`

```bash
# AC-01 dependency + immutability + baseline verification
python tools/c007_verify_deps.py --out-dir $OUT/artifacts --log $OUT/test_logs/dependency_verification.txt

# Pre-registration census (informs which contexts to register)
python tools/c007_context_census.py --out-dir $OUT/artifacts --log $OUT/test_logs/context_frequency_census.txt

# AC-04 teacher instrumentation parity (replay 19,050 + 100 live dual-call games)
python tools/c007_teacher_parity.py --live-games 100 --nproc 12

# AC-03 state encoder v2 schema + c006-vs-v2 diff + determinism/coverage tests
python tools/c007_state_encoder_audit.py --out-dir $OUT/artifacts --log-dir $OUT/test_logs
python -m unittest tests.test_c007_models          # micrograd/encoder/model gradient checks

# AC-02 experiment registration (freeze BEFORE dependent experiments)
python tools/c007_register_experiment.py --art-dir $OUT/artifacts

# AC-05 expanded v2 dataset (instrumented teacher, both seats vs field + control)
python tools/generate_v2_dataset.py --games-per-combo 90 --control-games 48 --nproc 14
python tools/validate_v2_dataset.py

# AC-06 train V2-A/V2-B x3 seeds; offline eval + ablation (opens test once)
python tools/train_student_v2.py --data-dir $OUT/artifacts/v2_dataset \
   --ckpt-dir $OUT/artifacts/checkpoints --log $OUT/test_logs/v2_training.txt --arch both --max-epochs 22
python tools/offline_eval_v2.py

# AC-08 improvement labels: two-batch controlled-variant A/B (+ reproducibility gate)
python tools/c007_improvement_labels.py --games-per-combo 50 --nproc 10 \
   --variants V_plan_a,V_reset,V_thresh,V_greedy

# AC-07 residual-context admission (<=3)
python tools/c007_residual_admission.py

# Assemble gated hybrid config + calibrated per-context OOD envelope
python tools/c007_build_hybrid.py

# AC-09 one targeted on-policy relabel iteration
python tools/c007_on_policy.py --games-per-combo 20 --nproc 12

# AC-10/11/12 hybrid gameplay (H0 parity, reliability, non-inferiority, gauntlet)
python tools/c007_hybrid_gameplay.py --phase all --nproc 12 \
   --h0-games 30 --rel-games 40 --noninf-per-seat 200 --gauntlet-games 40
python tools/c007_hybrid_gameplay.py --phase noninf --noninf-per-seat 400 --nproc 12   # extend to 800

# AC-13 registered decisions
python tools/c007_decide.py

# AC-14 package (diagnostic, NOT_FOR_SUBMISSION) + Kaggle evidence (SKIPPED_BY_GATE)
python tools/build_submission_c.py --games 80 --nproc 10
python tools/c007_finalize.py       # RL readiness + Kaggle SKIPPED + read-only teacher refresh

# AC-16 git/source integrity + top-level reports (run last, after source committed)
python tools/c007_reports.py
```

Notes:
- No `kaggle competitions submit` executed — `SUBMISSION_C = DO_NOT_SUBMIT`. Only a
  read-only `kaggle competitions submissions` refresh of teacher ref 54948560 was run.
- Games use spawn multiprocessing so each worker loads `libcg.so` fresh; the engine is
  `random_device`-seeded, so game outcomes are statistical (bootstrap seeds fixed).
- Authoritative per-move latency is the single-process `offline_eval_v2` measurement
  (~0.4 ms P99); parallel-gameplay P99 is CPU-contention-inflated.

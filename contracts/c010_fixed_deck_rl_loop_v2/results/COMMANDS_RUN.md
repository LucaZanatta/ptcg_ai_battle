# c010 — COMMANDS_RUN

All commands were run from the repository root with `.venv/bin/python`. `$OUT` is
`contracts/c010_fixed_deck_rl_loop_v2/results`.

## AC-01 — dependency and immutability verification

```bash
.venv/bin/python tools/c010_verify_deps.py \
  --out-dir $OUT/artifacts --log $OUT/test_logs/dependency_verification.txt
```

Verifies the c005→c009 chain and hashes, the frozen deck fingerprint, B0/I0 identity, and
re-derives c009's recorded scores from c009's raw games. Run again mid-experiment as an
integrity check (789 files across c005–c009, all unchanged).

## AC-02/03 — baselines, incumbent, arm registration

```bash
.venv/bin/python tools/c010_register.py
.venv/bin/python -m unittest tests.test_c010_arm_registration
.venv/bin/python -m unittest tests.test_c010_incumbent_protection
```

Resolves the exact c008 R1 recipe from both c008's `experiment_registration.json` and
`tools/train_rl.py` (both hashed) and proves A/B are identical to it while C changes exactly
the three registered values.

## AC-04 — PPO / environment validation

```bash
.venv/bin/python tools/c010_validate_ppo.py
```

Toy positive control, GAE, action masking, `act == evaluate`, checkpoint restore, and the
B0 initialization-fidelity guard.

## AC-05 — identity-safe evaluation protocol

```bash
.venv/bin/python -m unittest tests.test_c010_identity_safe_eval
.venv/bin/python tools/c010_identity_protocol.py
```

## AC-06 — throughput calibration and compute budget

```bash
.venv/bin/python tools/c010_calibrate.py
```

## AC-07/08/09 — training

Each seed is its own process: multiprocessing `spawn` pools cannot be nested, and
`&`-backgrounding several seeds inside one wrapper orphans them. `OMP_NUM_THREADS` is
inherited by every spawned rollout worker, so the parent keeps the BLAS threads (for the PPO
update) while workers are forced to one thread inside `c010_train_loop.py`.

```bash
# Arm A — restart from B0 with the exact c008 R1 recipe
for S in 311 322 333; do
  OMP_NUM_THREADS=1 nohup .venv/bin/python tools/c010_train_loop.py \
      --arm A --seed $S --nproc 7 > $OUT/test_logs/_A$S.txt 2>&1 &
done

# Arm B — continue I0 with the same unchanged recipe
for S in 411 422 433; do
  OMP_NUM_THREADS=1 nohup .venv/bin/python tools/c010_train_loop.py \
      --arm B --seed $S --nproc 6 > $OUT/test_logs/_B$S.txt 2>&1 &
done

# Arm C — minimally stabilized continuation. Launched only after A and B finished, and with
# a budget derived from their ACTUAL totals so rollout-granularity overshoot cannot breach
# the 120,000 hard maximum (see arm_C_budget_derivation.json).
.venv/bin/python $SCRATCH/c010_arm_c_budget.py     # -> BUDGET=19923
for S in 511 522 533; do
  OMP_NUM_THREADS=6 nohup .venv/bin/python tools/c010_train_loop.py \
      --arm C --seed $S --nproc 4 --max-games 19923 > $OUT/test_logs/_C$S.txt 2>&1 &
done
```

Consolidation into the arm-level deliverables:

```bash
.venv/bin/python tools/c010_consolidate.py --arms A,B,C
```

## AC-10 through AC-16 — the post-training pipeline

Driven in registered order by `tools/c010_finish.sh`. Evaluation stages are deliberately
sequential: two `c010_eval.py` processes would rewrite the same evidence file.

```bash
bash tools/c010_finish.sh
```

which runs:

```bash
# AC-10 screening, Sec.17 nomination, confirmation panels
.venv/bin/python tools/c010_eval.py --panel screen --candidates ALL_NEW --nproc 12
.venv/bin/python tools/c010_screen.py --stage nominate
.venv/bin/python tools/c010_eval.py --panel confirmation --candidates "<nominations>" --nproc 12
.venv/bin/python tools/c010_screen.py --stage confirm

# AC-11/12/13 diagnostics, decisions, final panel
.venv/bin/python tools/c010_aggregate.py --stage all
.venv/bin/python tools/c010_eval.py --panel final --candidates "<finalists>" --nproc 12
.venv/bin/python tools/c010_aggregate.py --stage all

# Sec.16 teacher extension -- evaluated for every finalist; none was plausibly
# teacher-non-inferior, so no extension was required. Had one been:
#   .venv/bin/python tools/c010_eval.py --panel final --candidates "<c>" --teacher-extension

# AC-05 / AC-15
.venv/bin/python tools/c010_identity_protocol.py
.venv/bin/python tools/c010_finalize.py

# AC-14 content-aware validation and its corruption tests
.venv/bin/python tools/c010_validate_evidence.py --art-dir $OUT/artifacts --log-dir $OUT/test_logs
.venv/bin/python -m unittest tests.test_c010_content_validation

# unit suites
for t in arm_registration promotion_rules identity_safe_eval incumbent_protection; do
  .venv/bin/python -m unittest tests.test_c010_$t
done

# AC-16 reports, status, checklist, git report, immutability recheck
.venv/bin/python tools/c010_reports.py
```

## Kaggle

`SUBMISSION_E = DO_NOT_SUBMIT`, so **no upload was executed** and no archive was built. The
only Kaggle call made was the read-only teacher refresh required by AC-15:

```bash
kaggle competitions submissions pokemon-tcg-ai-battle -v      # teacher ref 54948560 -> 714.9
```

The command that *would* have run on `SUBMIT` is recorded verbatim in
`artifacts/KAGGLE_SUBMIT_COMMAND.txt`. No credentials appear in any artifact or log.

## Re-runs

The pipeline was run twice end-to-end. The second run followed the floating-point tie fix
(`failures/DEFECT_float_tie_flipped_a_registered_threshold.md`); every evaluation stage is
idempotent and skips panels already played, so the second pass re-derived the decisions from
the same 25,400 evaluation games without replaying any of them. The nomination set was
unchanged by the fix.

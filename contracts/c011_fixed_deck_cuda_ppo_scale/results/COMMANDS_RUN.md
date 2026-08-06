# c011 — COMMANDS_RUN

Run from the repository root with `.venv/bin/python`. `$ART` is
`contracts/c011_fixed_deck_cuda_ppo_scale/results/artifacts`.

## AC-01 dependency, hardware, immutability
```bash
.venv/bin/python tools/c011_verify_deps.py
```

## AC-02 c010 evidence repair (Phase 0)
```bash
.venv/bin/python tools/c011_repair_c010.py --stage enumerate
# 9 promising-but-unconfirmed c010 checkpoints + the frozen teacher, same panel:
.venv/bin/python tools/c011_eval.py --panel confirmation \
    --candidates "A_322_g10115,C_511_g10316,C_511_g15108,C_522_g7624,C_522_g10236,\
C_522_g15424,C_533_g5052,C_533_g7720,C_533_g10356,T_teacher" --nproc 12
.venv/bin/python tools/c011_repair_c010.py --stage select
```

## AC-03/04/05 parity and round trips
```bash
.venv/bin/python tools/c011_parity.py --checkpoint <incumbent.npz>
.venv/bin/python tools/c011_ppo_parity.py --checkpoint <incumbent.npz> --stage all
```
Both pin determinism (`torch.use_deterministic_algorithms`, one thread) per §9.2.

## AC-06/07 benchmarks and CUDA decisions
```bash
.venv/bin/python tools/c011_benchmark.py --checkpoint <incumbent.npz> --stage backend --reps 3
.venv/bin/python tools/c011_benchmark.py --checkpoint <incumbent.npz> --stage workers \
    --probe-games 120 --windows 3
.venv/bin/python tools/c011_train_scale.py --seed 999 --nproc 16 --smoke 500 --device cuda
.venv/bin/python tools/c011_cuda_decision.py
```

## AC-08/09/10 scale training
Per-seed budget derived from the actual calibration/smoke spend so the 124,000 hard maximum
cannot be breached by rollout granularity (`$ART/training_budget_derivation.json`).
```bash
for S in 611 622 633; do
  .venv/bin/python tools/c011_train_scale.py --seed $S --nproc 16 --max-games 39914 --device cuda
done
```
Seeds run sequentially: calibration showed one process with 16 workers is the throughput
optimum.

## AC-11/12/13 evaluation, diagnostics, decisions
```bash
.venv/bin/python tools/c011_eval.py --panel screen --candidates ALL_NEW --nproc 16
.venv/bin/python tools/c011_screen.py --stage nominate
.venv/bin/python tools/c011_eval.py --panel confirmation --candidates "<12 nominations>,C_522_g20220" --nproc 16
.venv/bin/python tools/c011_screen.py --stage confirm
.venv/bin/python tools/c011_aggregate.py --stage diagnostics
.venv/bin/python tools/c011_eval.py --panel final \
    --candidates "T_teacher,C_522_g20220,S_611_g40127,S_622_g39983,S_633_g30176" --nproc 16
.venv/bin/python tools/c011_aggregate.py --stage all
```

## AC-14/15/16 validation, bundle, submission gate, reports
```bash
.venv/bin/python tools/c011_finalize.py
.venv/bin/python tools/c011_validate_evidence.py --quiet
.venv/bin/python tools/c011_build_source_bundle.py --stage all
.venv/bin/python tools/c011_reports.py
```

## Kaggle
`SUBMISSION_F = DO_NOT_SUBMIT`, so **no upload was executed** and no archive was built. The
only Kaggle call was the read-only teacher refresh AC-16 requires:
```bash
kaggle competitions submissions pokemon-tcg-ai-battle -v   # teacher ref 54948560 -> 716.0
```
The command that would run on SUBMIT is recorded verbatim in `$ART/KAGGLE_SUBMIT_COMMAND.txt`.
No credentials appear in any artifact or log.

## Corrections made mid-run
- 100 `B0_v2a` screen games failed with `unknown candidate kind rl_ckpt_from_v2a`: c010 records
  B0's kind in training vocabulary, the evaluator speaks evaluation vocabulary. The registry
  builder now translates; the defective games were purged and re-run.
- The evaluation of one validator check was corrected: `games_done` counts TRAINABLE games, so
  it is compared against terminal-with-transitions, not raw terminal count.

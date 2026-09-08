# c011 Acceptance Checklist

Each criterion requires its evidence files **and** a substantive assertion drawn from their contents. File existence alone never marks a criterion passed (§32).

| AC | evidence | assertion (verified) | passed |
|---|---|---|---|
| AC-01 | present | 17 checks pass; 42 c010 checkpoints hash-verified; preflight all pass | YES |
| AC-02 | present | 42 c010 checkpoints enumerated, 9 newly confirmed; incumbent C_522_g20220 | YES |
| AC-03 | present | fp32 logit 5.434174550345006e-06 <= 1e-5; fp64 semantically exact | YES |
| AC-04 | present | min per-tensor update cosine 0.9999998394682647 >= 0.999 | YES |
| AC-05 | present | NPZ round trip 0.0; trainer state exact (0.0) | YES |
| AC-06 | present | FP32_CUDA; BF16 declined on measurement; smoke 912 games zero defects | YES |
| AC-07 | present | 16 workers over 3 windows; update 14.178x, end-to-end 2.869x | YES |
| AC-08 | present | seed 611 executed: 40127 games, 92 updates | YES |
| AC-09 | present | seed 622 executed: 39983 games, 93 updates | YES |
| AC-10 | present | seed 633 executed: 40064 games, 92 updates | YES |
| AC-11 | present | 22160 evaluation games, identity OK on all 5 batches, 0 defects | YES |
| AC-12 | present | value scored against ACTUAL terminal outcomes by phase (Brier/AUC/calibration/MC error/EV/advantage SNR) | YES |
| AC-13 | present | SCALE_RESULT=EXTENDED; BEST_AGENT=S_633_g30176; teacher same-panel field 0.545 | YES |
| AC-14 | present | 77 content checks, 0 failed | YES |
| AC-15 | present | bundle validates by clean extraction: 18 checks, 0 failed | YES |
| AC-16 | present | SUBMISSION_F=DO_NOT_SUBMIT, KAGGLE_UPLOAD=SKIPPED_BY_GATE, NEXT_STEP=CONTINUE_FIXED_DECK_RL | YES |

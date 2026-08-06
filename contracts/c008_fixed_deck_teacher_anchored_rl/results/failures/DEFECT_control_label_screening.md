# Documented implementation defect (pre-training) — screening control label

**Defect:** `train_rl.screening_eval` looked up the engineering-control score under the
opponent key `"__control__"`, but `rl_env.play_game` labels the control opponent
`"control"`. Result: control score = None in screening, so the registered R0 stop rule
(`score vs control < 0.60 at 2500 games`) and the validation blend's 0.10*control term
would be corrupted.

**Detected:** during R0 seed 101 (first run), at the 1026-game screening (C=None), before
any arm completed. No comparable run had completed.

**Fix:** use key `"control"`. This is the single documented-defect correction permitted by
the experiment registration (§8); it affects all arms equally, so all runs restart fresh
from this fixed code. No thresholds were changed.

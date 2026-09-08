# Next Step (AC-16)

**NEXT_STEP = CONTINUE_FIXED_DECK_RL**

TRAINING_LOOP_STATUS **VALIDATED**, SCALE_RESULT **EXTENDED**.

**Highest-leverage blocker (exactly one, measured):** Absolute strength against the frozen teacher's own strategic field. The loop now demonstrably extends (EXTENDED, three seeds), but the promoted agent scores 0.367 on the field where the FROZEN TEACHER scores 0.545 on the identical panel -- a 0.178 gap, and the §24 submission gate additionally needs a teacher head-to-head lower bound of 0.47 against the measured 0.295. The measured mechanism is early-game credit assignment: value AUC against ACTUAL outcomes is 0.67 in the first fifth of a game versus 0.90 in the fourth fifth, and 40,000 games per seed did not move it (early Brier 0.228 against ~0.25 for a base-rate predictor). More PPO on this value head buys field score slowly; the head itself is the constraint.

`FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE` requires §2's gate (validated loop, reproducibly stronger agent, >= 0.40 against the teacher, no major held-out regression); it is NOT met, so fixed-deck agent work continues.

**Hypotheses (labelled as such, not measured here):** that a distributional or multi-step value target would lift early-game AUC; that opponent-conditioned value heads would reduce field variance. Neither was tested in c011.

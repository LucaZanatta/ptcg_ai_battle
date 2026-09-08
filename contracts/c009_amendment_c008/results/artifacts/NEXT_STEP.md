# Next Step (AC-15)

**NEXT_STEP = FIXED_DECK_SELECTIVE_SEARCH**

- §15 REDESIGN condition a_rl_improves_over_b0: MET
- §15 REDESIGN condition b_two_seeds_or_batches_show_signal: MET
- §15 REDESIGN condition c_best_not_catastrophically_below_teacher: NOT MET
- §15 REDESIGN condition d_one_clear_addressable_blocker: MET

'catastrophically below teacher' is pre-stated here as teacher score < 0.25 OR major regression on more than 50% of field matchups; the best checkpoint scores 0.22 with 3/4 major regressions. Even under a laxer reading of that condition, §15's expected-value clause selects FIXED_DECK_SELECTIVE_SEARCH: the measured improvement rate leaves the 0.47 bound out of reach for a comparable PPO budget.

**Highest-leverage blocker (exactly one):** Sparse terminal-reward credit assignment cannot close the teacher gap at the measured learning rate: c008 spent 95,666 training games to move the teacher score from 0.160 (untouched V2-A) to 0.220, leaving 0.250 to the 0.47 non-inferiority bound — roughly 4x the total improvement achieved so far. Teacher-anchored PPO on the fixed deck improves its own initialization but is the wrong instrument for closing a >2x strength gap.

Recalibrated feasibility: INCONCLUSIVE. Best saved checkpoint: R1_101_ckpt_g10040.

The most valuable algorithmic finding for anyone revisiting RL is recorded in `RL_FEASIBILITY_RECALIBRATED.md`: c008's R2 anchor schedule never reached its registered low-anchor phase, so the teacher-anchored arm never had the opportunity to move away from its initialization.

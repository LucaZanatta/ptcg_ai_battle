# RL Best-Arm & Feasibility (AC-12)

- **BEST_RL_ARM** = NONE
- **RL_FEASIBILITY** = INCONCLUSIVE
- **SUBMISSION_D** = DO_NOT_SUBMIT
- **PROMOTION_DECISION** = NO_RL_SUBMISSION
- **NEXT_STEP** = REVISE_RL

| arm | reliability | non-inf (LB) | repro improvement | major regression | eligible | stops |
|---|---|---|---|---|---|---|
| R0 | True | False (0.042499999999999996) | False | True | False | ['R0_weak_vs_all_at_5000', 'budget_reached'] |
| R1 | True | False (0.155) | False | True | False | ['R1_reject_at_20000', 'R1_reject_at_10000'] |
| R2 | True | False (0.10250000000000001) | False | True | False | ['R2_reject_at_10000', 'R2_reject_at_20000', 'R2_reject_at_20000'] |

**Highest-leverage blocker:** RL learns but no candidate reaches teacher non-inferiority (best one-sided LB 0.155 < 0.47) or a reproducible strategic improvement; the teacher remains stronger on the fixed deck

RL feasibility rule (§17): PROVEN needs an arm that is teacher-non-inferior AND reproducibly stronger AND stable across >=2 seeds; INCONCLUSIVE = learning occurs but none reaches non-inferiority; REJECTED = no meaningful learning curve. Gates were not lowered.

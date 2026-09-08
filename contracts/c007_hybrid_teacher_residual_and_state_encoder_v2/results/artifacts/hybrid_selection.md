# Hybrid Selection & Decisions (AC-13)

- **STATE_ENCODER_V2** = ACCEPT
- **TEACHER_INSTRUMENTATION** = VALID
- **RESIDUAL_CONTEXTS** = ['dragapult_damage_counter']
- **BEST_HYBRID** = NONE
- **SUBMISSION_C** = DO_NOT_SUBMIT
- **PROMOTION_DECISION** = NO_HYBRID_SUBMISSION
- **RESIDUAL_RL_READINESS** = NOT_READY

## BEST_HYBRID conditions (§16 — all required)
- PASS — instrumentation_valid
- PASS — encoder_accepted
- PASS — at_least_one_residual_context
- PASS — reliability_perfect
- FAIL — teacher_non_inferiority_passed
- FAIL — at_least_one_reproducible_improvement
- PASS — no_major_regression

**Highest-leverage blocker:** no controlled variant reproducibly beats the teacher's damage-counter allocation (best 2-batch improvement LCB <= 0); the tuned rule-based teacher has no exploitable seam a one-rule residual can beat

## Why this is an earned negative, not a defect
- Teacher instrumentation is behavior-equivalent (19,050 replay + 100 live, 0 mismatch).
- State encoder v2 accepted (per-slot board, exact multisets, cross-option encoder, real previous-action identity; all 19,050 decisions encode deterministically).
- H2 is safe by construction: it invokes the frozen teacher every decision and overrides only under evidence-backed gates; with no reproducible improvement it defaults to the teacher (0 overrides), so it is action-identical to the teacher and reliable.
- H2-vs-teacher is therefore a MIRROR match (point 0.49124999999999996, one-sided 95% LB 0.4625 over 800 games): non-inferiority is definitional via action identity (0 overrides, cf. H0 parity 0 mismatch); the statistical LB straddles the registered 0.47 threshold as pure mirror-match sampling variance, not real inferiority.
- Four pre-registered one-rule damage-counter variants were A/B'd over two independent batches (800 games/variant); none beat the teacher with a reproducible LCB > 0.
- Gates were NOT lowered to manufacture a submission.

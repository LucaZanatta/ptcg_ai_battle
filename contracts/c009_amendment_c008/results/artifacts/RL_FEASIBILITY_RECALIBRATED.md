# Recalibrated RL Feasibility (AC-11)

**RL_FEASIBILITY_RECALIBRATED = INCONCLUSIVE**
**BEST_SAVED_CHECKPOINT = R1_101_ckpt_g10040**
**TEACHER_NONINFERIORITY = FAIL**

§14 sets INCONCLUSIVE when a saved RL checkpoint clearly improves over B0 but remains below the teacher. Both halves are now established from corrected evidence:

- improves over B0: R1_101 (teacher 0.16 → 0.22, field 0.1525 → 0.255)
- below teacher: best one-sided 95% LB = 0.1875 vs the unchanged 0.47 requirement

## Corrected best within each arm (§11.1)
- **R0 → R0_202** (teacher score statistically tied among ['R0_202', 'R0_101']; broken on strategic-field score (§11.1 #2))
  - R0_101: teacher 0.01 (n=100), field None, held-out None, c008 validation 0.20500000000000002 [c008 best-by-validation]
  - R0_202: teacher 0.03 (n=100), field 0.10000000000000002, held-out 0.07, c008 validation 0.16625 [c008 median representative]
- **R1 → R1_101** (teacher score statistically tied among ['R1_101', 'R1_202']; broken on strategic-field score (§11.1 #2))
  - R1_101: teacher 0.22 (n=400), field 0.255, held-out 0.27, c008 validation 0.405 [c008 best-by-validation]
  - R1_202: teacher 0.17 (n=100), field None, held-out None, c008 validation 0.3375 [c008 median representative]
- **R2 → R2_303** (teacher score statistically tied among ['R2_101', 'R2_303', 'R2_202']; broken on strategic-field score (§11.1 #2))
  - R2_101: teacher 0.16 (n=100), field 0.185, held-out 0.16, c008 validation 0.305
  - R2_202: teacher 0.12 (n=100), field None, held-out None, c008 validation 0.31125 [c008 median representative]
  - R2_303: teacher 0.1575 (n=400), field 0.2275, held-out 0.15000000000000002, c008 validation 0.335 [c008 best-by-validation]

## R2 interpretation limits (§2.5)
c008 registered a replay-coefficient decay to 0.05 and a reference-KL decay to 0.01, but every R2 seed early-stopped at 10k-20k of its 50k budget, so the replay coefficient never fell below ~0.27 and the KL coefficient never below ~0.030. R2 therefore spent its entire life in the high-anchor regime, which is consistent with its teacher score (0.158) being statistically indistinguishable from the untouched initialization B0 (0.160). This is an algorithmic/budget limitation of the c008 run, not evidence that anchoring cannot work.

Additional acknowledged limits: the reference KL anchored to V2-A rather than to the rule teacher; the teacher-replay term was strong relative to the PPO objective; and the multi-select reference KL covered only the first sub-selection. These are algorithmic limitations of the c008 run — no saved checkpoint was altered.

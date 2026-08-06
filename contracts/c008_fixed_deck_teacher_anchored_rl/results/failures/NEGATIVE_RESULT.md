# Failures / Negative-result record — c008

**No blocking failures.** All 16 acceptance criteria were executed and verified; the
contract is `PASS`. A `PASS` does not require successful RL (§24). This file documents the
(acceptable) **negative RL result** and the checks that make it an earned negative.

## The result
Under a bounded, reproducible-protocol simulator budget with the frozen Dragapult deck:
- `BEST_RL_ARM = NONE`, `RL_FEASIBILITY = INCONCLUSIVE`, `SUBMISSION_D = DO_NOT_SUBMIT`,
  `PROMOTION = NO_RL_SUBMISSION`, `NEXT_STEP = REVISE_RL`.
- Teacher head-to-head (400 games each): R0 LB 0.042, R1 LB 0.155, R2 LB 0.103 — none
  reaches the registered 0.47 non-inferiority bound.
- Strategic mean-vs-field: teacher 0.528 vs R1 0.289 / R2 0.189 / R0 0.11; held-out
  Abomasnow: teacher 0.50 vs R1 0.263. Every arm is major-regressed vs the teacher.

## Why this is honest, not a broken experiment
1. **PPO provably works.** The deterministic toy positive control drives P(optimal)->1.0;
   GAE matches a hand-computed trajectory; masked log-probs are exact (illegal prob 0);
   act()==evaluate() so the PPO ratio is 1 at collection; the multi-select log-prob is
   gradient-checked (7e-11). If PPO were broken these would fail.
2. **The value head learns.** Explained variance rises to ~0.8 from step one across arms —
   credit assignment is working; the negative is task difficulty, not a wiring bug.
3. **RL genuinely improves the policy.** R1 (V2-A init) shows a positive learning curve in
   BOTH seeds — validation blend ~0.30 -> ~0.40 peak (teacher screening ~0.32). This is real
   learning above the supervised start; it simply plateaus and PPO-degrades below the teacher.
4. **Zero reliability defects.** All training + evaluation games completed with zero invalid
   actions, exceptions, timeouts, or ordered-decoder blocks; P99 inference ~3.7 ms.
5. **The primary hypothesis was tested fairly and failed.** R2's decayed teacher-replay and
   reference-KL schedules were applied and verified, yet R2 did not exceed R1 or the teacher.
6. **The strongest checkpoint per arm was evaluated** (not the median), so the negative is not
   an artifact of a weak representative — even RL's best checkpoint loses ~81% to the teacher.
7. **No gate was lowered and nothing was submitted for rising reward.** The single documented
   pre-training defect (screening control-label) was fixed under the registration restart rule
   before any arm completed (`DEFECT_control_label_screening.md`).

## Mechanism / highest-leverage blocker
Sparse +/-1 terminal reward over ~70-decision games is a weak credit-assignment signal for
bounded numpy PPO to move a fixed-deck policy past a tuned rule-based teacher; PPO is
unstable (peaks then degrades). Denser value modeling / selective search, longer stabilized
budgets, or tighter trust-region anchoring are the revision directions (`NEXT_STEP=REVISE_RL`).

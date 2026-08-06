# c006 Best-Student & Memory Decision

**BEST_STUDENT = NONE**

Neither student passes teacher non-inferiority (S1 one-sided LB=0.085, S2 LB=0.125; both << 0.45). Per §15, BEST_STUDENT=NONE (a student is not chosen merely for beating the other).

## Eligibility

| student | reliability_eligible | non_inferior_vs_teacher | LB95 vs teacher | gauntlet mean-vs-field | test iw-agree |
|---|---|---|---|---|---|
| S1_STATELESS | True | False | 0.085 | 0.188 | 0.695 |
| S2_RECURRENT | True | False | 0.125 | 0.150 | 0.690 |

## Memory decision: **MEMORY_NOT_JUSTIFIED**

- High-impact test agreement gain (S2−S1): 0.09pp (threshold ≥2pp) — fails.
- Game-level importance-weighted agreement diff 95% CI: [-0.029052024328405642, 0.015547702611435421] (includes 0) — fails.
- S2 vs teacher point 0.170 > S1 0.120, but S2 gauntlet strength 0.150 < S1 0.188; no material gameplay improvement can be claimed for a policy that is not non-inferior. S2 ~ S1 offline (matched inputs), so 'memory does not help' is robust, not an inference-time artifact.

## Note
A negative result is an acceptable PASS (§1). Both students BEAT the deterministic control (S1 0.188, S2 0.150 > control 0.106) — the models learned to imitate; they are simply not teacher-strong in full games.

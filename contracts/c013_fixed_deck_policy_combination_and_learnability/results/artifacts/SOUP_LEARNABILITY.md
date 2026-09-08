# AC-10 — is the weight soup learnable?

**SOUP_LEARNABILITY = NOT_IMPROVED**

## Why this question is being re-asked

c012 concluded that PPO could not improve the `SOUP_622+633` incumbent. But every c012 in-run evaluation after game zero returned **zero scored games** — a per-path checkpoint-hash cache in persistent pool workers meant each worker kept reporting the hash of the first `cur.npz` it saw, so the identity check correctly refused to score any game. c012 measured a broken instrument and read the silence as a negative result. c013 repairs the instrument and re-asks the question.

Phase 2 start `C012_SOUP_622_633`: teacher **0.353**, field **0.333**, composite **0.350** (750 games on the confirmation panel).

## Registered methods, judged on the panel and not on training reward

§17 is explicit that no method may be called working from training reward alone. A method counts only when a candidate beats the Phase 2 start with a bootstrap 95% CI that excludes zero.

| candidate | method | teacher | field | composite | teacher gain (95% CI) | P(gain>0) | confirmed |
|---|---|---|---|---|---|---|---|
| Q1_902_g5184 | VALUE_REFIT | 0.300 | 0.382 | 0.357 | -0.053 [-0.130, +0.020] | 0.075 | no |
| Q2_SOUP_recombined | COMPONENT_CONTINUE_RECOMBINE | 0.297 | 0.373 | 0.350 | -0.057 [-0.133, +0.017] | 0.064 | no |
| Q0_901_g10320 | DIRECT_CONTINUATION | 0.323 | 0.356 | 0.349 | -0.030 [-0.107, +0.047] | 0.206 | no |
| Q1_902_g10256 | VALUE_REFIT | 0.283 | 0.371 | 0.344 | -0.070 [-0.147, +0.007] | 0.032 | no |
| Q2A_903_g5152 | COMPONENT_CONTINUE_RECOMBINE | 0.297 | 0.358 | 0.340 | -0.057 [-0.133, +0.020] | 0.066 | no |
| Q2_PROB_recombined | COMPONENT_CONTINUE_RECOMBINE | 0.307 | 0.353 | 0.337 | -0.047 [-0.120, +0.030] | 0.111 | no |
| Q2_LOGIT_recombined | COMPONENT_CONTINUE_RECOMBINE | 0.307 | 0.344 | 0.335 | -0.047 [-0.120, +0.030] | 0.108 | no |
| Q0_901_g5184 | DIRECT_CONTINUATION | 0.317 | 0.333 | 0.334 | -0.037 [-0.113, +0.040] | 0.162 | no |
| Q2B_904_g5200 | COMPONENT_CONTINUE_RECOMBINE | 0.247 | 0.364 | 0.326 | -0.107 [-0.180, -0.033] | 0.001 | no |

## Training-side context (does not decide anything)

| arm | completed games | in-run evaluations | of which scored |
|---|---|---|---|
| Q0 | 12016 | 3 | 3 |
| Q1 | 12368 | 3 | 3 |
| Q2A | 10192 | 2 | 2 |
| Q2B | 10336 | 2 | 2 |

Every in-run evaluation produced scored games. That column is exactly the one that was silently zero throughout c012, and it is reported here so the repair is visible in the evidence rather than asserted in prose.

### The in-run signal did not survive the registered panel

Q0's in-run teacher score rose from 0.275 to 0.425 across its run, which looked like direct continuation working and would have overturned c012's central negative finding. It does not survive. Those in-run evaluations score in steps of 0.025, i.e. **40 games** per point; the confirmation panel uses **750**. On the panel Q0 sits at 0.323 against a start of 0.353.

This is precisely why §17 forbids concluding that a method works from training-side numbers. Reporting the in-run trajectory as the result would have repeated c012's mistake in the opposite direction — trusting an underpowered instrument because its answer was the interesting one.

### What this does and does not say about c012

c012's conclusion — PPO does not improve this soup — is **re-confirmed** under repaired infrastructure. But c012 reached it with an instrument that was scoring nothing, so it was right for the wrong reason. c013 adds a measurement c012 could not make: all nine continued candidates show a **positive strategic-field tendency** (8 of 9 strictly positive, best P(gain>0) = 0.94), none of which reaches the registered bar at this budget. The honest reading is not 'training cannot help' but 'no registered method produced a confirmed improvement within ~12,000 games per arm'.


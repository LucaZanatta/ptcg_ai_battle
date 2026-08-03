# Score-constant search — notes taken while it ran

Protocol registered before the run in `REGISTERED_PROTOCOL.md`. This file records what happened,
including the parts that only make sense in real time.

## The incumbent's own score is a sixth measurement of the noise floor

The search re-measures the incumbent every round, in the same run as its challengers. For the
first six rounds the incumbent *was the untouched defaults* — the same policy, six times, 1,000
games each:

| round | r0 | r1 | r2 | r3 | r4 | r5 |
|---|---:|---:|---:|---:|---:|---:|
| incumbent (defaults) | 0.511 | 0.508 | 0.504 | 0.515 | 0.493 | 0.498 |

**Range 2.2 points on an unchanged policy**, which lands almost exactly on the 2.4-point figure
`UNRESOLVED_RISKS.md` R4 derived from three independent 1,200-game runs. Two different methods,
the same answer, and this one is free — it falls out of the search's own design.

## The best-of-five gains, under a null that is probably true

| round | best child − incumbent | decision |
|---|---:|---|
| r0 | −0.10 | reject |
| r1 | +1.65 | reject |
| r2 | +2.90 | reject |
| r3 | −0.70 | reject |
| r4 | +3.50 | reject |
| **r5** | **+4.80** | **ACCEPT** |

The accept margin is 4.47 points = 2 × the standard error of the difference. Taking the best of
five draws from a distribution whose SD is ~2.2 points produces a maximum around +2.5 to +3.5
points **even when every child is identical to its parent**, so the first five rounds look
exactly like noise and r5 is at the high end of noise rather than clearly outside it.

That is the expected behaviour, it is why the registered protocol calls the search's output a
*hypothesis*, and it is why `tune_best` must still clear confirmation on a fresh run and
validation on a panel the search never saw.

## The one accepted change is semantically coherent, which is worth noting and not worth trusting

**Parameter 39** — `hand_score`, line 494 of the official Dragapult sample: **28000 → 42956.**

In the original source that constant is the value of wanting **Latias ex** in hand, in the
specific case where our Active is a non-attacker (Fezandipiti ex, Meowth ex or Dreepy) **and there
is no Drakloak or Dragapult ex in play at all**. Raising it means: when the board has not yet
produced the main attacker, fetch the backup attacker harder.

That is a direct answer to **F5, the one failure class the loss mining actually supports** — we
lose the games where the Dreepy → Drakloak → Dragapult ex line comes online late (first attack on
turn 2.80 in losses against 2.24 in wins). Latias ex is a 210 HP Pokémon whose Eon Blade does 200
for two Psychic and a Colourless, i.e. exactly the thing to reach for when the main line has not
arrived.

**A coherent story is not evidence.** With 110 parameters and five children a round, some accepted
change was always going to admit a plausible reading. The reading is recorded because if the
change *does* survive confirmation and validation, this is the mechanism to check — and if it does
not, this note is the reminder that plausibility was available for free.

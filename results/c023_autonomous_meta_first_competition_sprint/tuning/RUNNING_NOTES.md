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

## The search's most useful output is not its winner

A (1+5) search that re-measures its incumbent every round accumulates, over 70 rounds, **70,000
games on essentially one or two policies**. At 1,000 games a measurement the standard error of a
single round's incumbent score is ~1.6 points; over seventy of them it is about **0.2 points**.

So the incumbent series is the most precise strength measurement in this entire campaign — an
order of magnitude tighter than any deliberate arm — and it costs nothing extra. It is what turns
"the accepted change shrank" from an impression into the number below, and it is why the search's
negative result is worth more than its positive one.

## The shrinkage, measured inside the search itself

The registered protocol predicted it: *"the search will report a dev-panel gain, and most of it
will not survive confirmation."* The search does not have to wait for the confirmation stage to
show it, because it re-measures its own incumbent every round.

| incumbent | rounds | scores | mean |
|---|---|---|---:|
| the untouched defaults | r0–r5 | 0.511, 0.508, 0.504, 0.515, 0.493, 0.498 | **0.5048** |
| after the r5 change | r6–r10 | 0.514, 0.5035, 0.505, 0.512, 0.504 | **0.5077** |

**The accepted change was worth +4.80 points when it was selected and +0.29 points when it was
re-measured five times.**

That is selection bias with a number on it, from the campaign's own data and at no extra cost.
Nothing was done differently between the two rows — same policy, same panel, same harness, 1,000
games per measurement. The +4.80 was the maximum of five draws from a distribution whose standard
deviation is ~2.2 points; the +0.29 is what the change is actually worth.

This is the single clearest illustration in the campaign of why `PANEL_SPLIT.json` separates
screening from confirmation, and it is the same lesson `DECK_CHANGE_LEDGER.md` learned the
expensive way when a deck mutation went from +7.25 at 400 games to −0.12 at 1,200.

## D7 — the acceptance rule is asymmetric, and both acceptances prove it

Twenty-three rounds, two acceptances, and **both fired on the two lowest incumbent draws in the
entire run**:

| | incumbent | best child | gain | note |
|---|---:|---:|---:|---|
| all 23 rounds, incumbent | mean **0.5052**, SD **0.0101**, range 0.4750–0.5220 | | | |
| all 23 rounds, best child | | mean **0.5245**, range 0.5050–0.5530 | mean **+1.93** | |
| **r5, ACCEPTED** | **0.4980** | 0.5460 | +4.80 | 2nd-lowest incumbent of 23 |
| **r22, ACCEPTED** | **0.4750** | 0.5240 | +4.90 | **lowest incumbent of 23** |

Look at r22's child: **0.5240, which is *below* the mean best child of 0.5245.** It did not win by
being good. It won because the incumbent drew its minimum.

**The defect.** The rule is `best_child − incumbent ≥ margin`, with the incumbent measured once
per round. That is asymmetric in a way the registered protocol did not notice: re-measuring the
incumbent every round controls for *machine conditions*, but not for the incumbent's own sampling
noise. The child side already takes a maximum over five draws; the incumbent side is a single
draw. A low incumbent is therefore worth exactly as much as a high child, and with SD ≈ 1.0 point
per measurement the incumbent alone supplies a 4.7-point swing across 23 rounds.

**What should have been registered instead:** compare the child against the incumbent's *running
mean* over all previous rounds. After twenty rounds that has a standard error near 0.2 points
rather than 1.0, and a low draw cannot manufacture an acceptance.

**What is being done about it.** The protocol is not changed mid-run — that would be choosing a
rule after seeing which rounds it accepts. Instead:

1. The search runs to completion under the registered rule.
2. `tune_best` is evaluated against the incumbent's **pooled** series in the post-hoc analysis, which
   is the comparison the rule should have made.
3. It still has to clear the registered confirm and validate stages on fresh runs, which the
   defect cannot reach.

Recorded here rather than in `failures/DEFECTS.md` because it is a flaw in an experiment's
analysis rule, not a bug in code — but it is the same species as the rest of them: a comparison
that looks controlled and is not.

## The accepted changes are semantically coherent, which is worth noting and not worth trusting

Four parameters after two acceptances, read back against the original source:

| # | function, line | original | tuned | what the constant means |
|---:|---|---:|---:|---|
| **39** | `hand_score` 494 | 28000 | **42956** | wanting **Latias ex** in hand when the Active is a non-attacker (Fezandipiti ex / Meowth ex / Dreepy) **and no Drakloak or Dragapult ex is in play at all** |
| **56** | `hand_score` 557 | 55000 | **60924** | wanting **Crispin** — the energy fetcher — when we hold a Dragapult ex but **cannot attack and have no benched attacker** |
| 75 | `agent` 667 | −1000 | **−757** | the penalty for promoting **Fezandipiti ex** to the Active Spot |
| 52 | `hand_score` 544 | 5 | **4** | wanting a redundant **Ultra Ball** — a near-zero constant nudged by one |

**Three of the four point the same way, and it is the way the loss mining pointed.** F5 says we
lose the games where the Dreepy → Drakloak → Dragapult ex line comes online late — first attack on
turn 2.80 in losses against 2.24 in wins. Parameters 39 and 56 both raise "reach harder for a way
to attack when the main line has not arrived": Latias ex is a 210 HP body whose Eon Blade does 200,
and Crispin fetches the energy that turns a Dragapult ex into an attacker. Parameter 75 makes the
agent slightly more willing to promote its backup body.

**A coherent story is not evidence, and D7 above is the reason to say so twice.** With 110
parameters and five children a round, some accepted change was always going to admit a plausible
reading — and both acceptances fired on the incumbent's two lowest draws rather than on
exceptional children. The reading is recorded because if these changes *do* survive confirmation
and validation, this is the mechanism to check; and if they do not, this note is the reminder that
plausibility was available for free.

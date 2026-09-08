# Plateau decisions — none were taken, and that is the finding

`CONTRACT §6` requires "matched c021 sample budget and **plateau-governed continuation**".
`TRAINING_AND_EVALUATION` governs when a run may stop early because it has stopped improving.

**No arm in this contract was stopped by a plateau rule.** Every arm ended for a reason that was
not "it stopped improving", and recording which reason is the point of this file — an empty
directory would have implied the rule was applied and found nothing.

| arm | produced decisions | % of matched budget | why it ended |
|---|---:|---:|---|
| `br3_fixed_deck` | 328,601 | 9.11% | **schedule** — the 23:50 deadline, cut 1/2 of the pre-fixed order |
| `br3_end_to_end` | 391,305 | 10.85% | **schedule** — same deadline |
| `br3_fixed_deck_long` | 2,632,369 | 73.0% | **schedule** — the 06:15 deadline of a user-granted window |
| `ctrl_BR0` … `ctrl_BR3` | 120,000 each | — | **registered budget reached**, equal by design |
| `fid_BR0` … `fid_BR3` | 24,000 each | — | **registered budget reached** |

## Why no plateau was reached

The external trajectory of the longest arm, on the same 128-game panel
(`../fixed_deck/fixed_deck_arm.json`):

| | games | field score | Wilson 95% |
|---|---:|---:|---|
| random floor | 128 | 0.0234 | [0.008, 0.0666] |
| early half (6 evals) | 768 | 0.0990 | [0.0798, 0.1221] |
| late half (6 evals) | 768 | 0.1484 | [0.1250, 0.1753] |

The late half is **above** the early half, and the final checkpoint (0.1797) is the highest of the
twelve. A plateau rule requires evidence that improvement has stopped; this arm was still rising
when the clock stopped it. Applying a plateau stop here would have been wrong, and not applying
one is therefore not an omission.

## What this means for the matched-budget requirement

`BYTERL_SCALE=COMPUTE_LIMITED`, which `DECISION_RULES §3` names as the expected outcome when
fidelity passes and paper scale is not approached. The honest statement is:

> The arms did not plateau. They ran out of time at 9.11%, 10.85% and 73.0% of the matched
> budget, and the longest was still improving at the point it was stopped.

`FIDELITY_RULES §5` — "do not convert undertraining into method failure" — applies with full force
here, and `EXTENSION_RESULTS.md` records that the 73% arm's separation from the random floor is
the direct evidence that the earlier flatness was budget rather than method.

## The stopping procedure that WAS applied

Recorded in `../../EXECUTION_BUDGET.md` before it fired: stop on a checkpoint at most 400 updates
old, report `produced_decisions` — the counter the matched budget is defined in — as a fraction of
3,607,599, and log `schedule` as the reason. That procedure was written while it was still a
procedure and executed unchanged.

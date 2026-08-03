# superseded/

Artifacts that were produced, then invalidated by something learned afterwards. They are moved
here rather than deleted, and rather than left in the live tree where a report generator might
read them.

## `plan_screen1` — measured under a wall-clock work budget

**Status: SUPERSEDED as a decisive measurement; retained and cited as a screen.**

The four `chal_dp_plan*` arms in `raw_evaluations/plan_screen1/` were run while the planner's
work budget was **120 ms of wall clock per decision**. A search with a per-decision *time* budget
does not merely run slower under CPU contention — it explores fewer lines and scores worse, and
nothing in the output says so. That artefact has corrupted results in three prior contracts of
this project, once inverting a ranking by 49 points. The run shared a 24-core machine with 20
evaluation workers and an unrelated 100%-CPU job.

`PIVOT_LEDGER P4` records the change: planner effort is now set by `max_root_options ×
max_turn_steps`, and the wall clock is a 700 ms safety valve that should almost never bind. An arm
is then *slower* on a busy machine and never weaker.

**Why the run is still cited.** Its finding does not depend on the budget: the four arms ordered
**monotonically in how often they overrode**, with the most aggressive (`plan2`, planning at every
single-select decision) worst at 0.479 and the most conservative best at 0.4985, all at or below
the 0.506 control. A contention artefact would have depressed every arm together, not ordered them
by override rate. So it is quoted as evidence about the *mechanism* and never as the planner's
strength number.

The files remain in `raw_evaluations/plan_screen1/` because the validator recomputes every summary
from its own raw games and moving them would break that check for no benefit; this note is the
supersession record.

## `chal_dp_bench2`, `chal_dp_bench3`, `chal_dp_bench_prize` — built against an inert rule

**Status: SUPERSEDED by `*f` rebuilds; their evaluations are retained as noise-floor evidence.**

These three candidates enable `bench_discipline_vs_spread`, which could not fire: the `View`
resolved a PLAY option's card through its `area` field, and PLAY options carry no area. The
rule-firing probe measured **0 fires in 1,329 decisions**. Their 1,200-game evaluations in
`raw_evaluations/rule_screen2/` are therefore measurements of the *control policy under a
different name*, and `chal_dp_bench2` vs `chal_dp_base3` (0.5142 vs 0.5042) is now the campaign's
cleanest estimate of run-to-run noise — see `UNRESOLVED_RISKS.md` R4.

They are superseded as *challengers* and retained as *controls*. `chal_dp_bench2f`,
`chal_dp_bench3f` and `chal_dp_bench_prizef` are the rebuilds that actually carry the rule.

## `chal_dp_benchline` — inert by construction, never evaluated

**Status: NOT_RUN, precondition never met.**

The same rule with the Dreepy/Drakloak evolution line protected fires **0 times**: with a 100 HP
threshold the only other card it could veto in this deck is Budew, and the base agent already
declines to play a second Budew. Caught by the firing probe before it cost a single evaluation
game. Recorded because "we tried it and it made no difference" would have been a false negative.

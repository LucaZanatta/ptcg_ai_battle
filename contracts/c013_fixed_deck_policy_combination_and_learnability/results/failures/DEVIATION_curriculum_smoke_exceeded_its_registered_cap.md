# Deviation: the curriculum smoke exceeded its registered 10,000-game maximum by 112 games

**Reported, not rounded away.** §19 sets a maximum of 5,000 completed games per smoke arm.

```text
R0 seed 1001    5,104 completed    +104 over the per-arm cap
R1 seed 1002    5,008 completed      +8 over the per-arm cap
-------------------------------------------------------------
total          10,112              +112 over the 10,000 phase cap  (1.1%)
```

## Cause

Rollouts are atomic. The trainer collects a rollout targeting `rollout_game_target = 256`
completed games, then checks `while completed < max_games`. A rollout that begins at 4,880
therefore finishes at 5,104 before the budget test is next evaluated. The budget is enforced at
rollout granularity, not game granularity.

This is the identical mechanism to c010's
`DEVIATION_rollout_granularity_budget_overshoot.md`. c010 handled it by deriving the final arm's
budget from the earlier arms' measured actuals so the worst case pinned exactly at the ceiling.
That technique was not carried into the smoke trainer, which is the defect: a known overshoot
mode was left unmitigated in new code.

## Why it was not re-run

Re-running both arms under a corrected budget check costs a further ~10,000 completed games,
taking the curriculum smoke to ~20,000 against a registered maximum of 10,000. Doubling a
compute ceiling to remove a 1.1% overshoot of that same ceiling is not a trade that improves the
evidence.

The **62,000-game hard training maximum is not approached**:

```text
learnability      44,912
curriculum smoke  10,112
------------------------
total             55,024   of 62,000
```

## What it does and does not affect

- It does **not** affect `CURRICULUM_SMOKE = PASS`. §20 conditions that verdict on the execution
  machinery, and all eight requirements hold on both arms — including the two real curriculum
  stage changes and the literal trainer-state restore that c012 never achieved.
- It does **not** affect any evaluation result. Smoke games are training games; no panel,
  ranking, or decision in c013 reads them.
- It **does** mean a registered phase ceiling was exceeded, and the validator reports
  `smoke_within_cap` as a failure rather than passing it. That check is left failing on purpose:
  suppressing it to make the run look clean is precisely the behaviour these contracts exist to
  prevent.

## Fix for future runs

Cap the rollout target by the remaining budget before collection begins:

```python
target = min(PPO_CFG["rollout_game_target"], max_games - completed)
```

so the final rollout cannot cross the ceiling. This is committed in the smoke trainer but was
**not** applied retroactively to the two completed arms, since re-running them is the expensive
option rejected above.

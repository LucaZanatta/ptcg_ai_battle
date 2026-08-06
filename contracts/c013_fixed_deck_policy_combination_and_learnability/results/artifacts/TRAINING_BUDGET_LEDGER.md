# c013 training budget ledger

Written **before** the curriculum smoke was launched and before the Q3 gate was evaluated, so
the Q3 contingency below is a decision, not a rationalisation of whatever the numbers turned out
to be. §48 makes exceeding a registered ceiling a `PARTIAL` condition in its own right; c012
already carried one defect into its conclusion rather than breach a ceiling to rescue a result.

## Registered ceilings (§ compute plan)

| item | ceiling |
|---|---|
| combination evaluation | 5,000–12,000 games |
| learnability training | ≤ 50,000 completed games |
| curriculum smoke | ≤ 10,000 completed games |
| overlap analysis | **evaluation only** — not on the training ledger |
| Claude preflight | ≤ 30 primary + 10 repeats |
| **hard training maximum** | **62,000 completed games** |

## Learnability actuals

Every count is `summary.json`'s `completed_games` **independently recounted** from the raw
`training_games.jsonl.gz` line count. They agree exactly, so the ledger is not resting on a
self-reported number.

| arm | seed | summary | raw recount | stop reason |
|---|---|---|---|---|
| Q0 direct continuation | 901 | 12,016 | 12,016 | budget_reached |
| Q1 value reinit + refit + PPO | 902 | 12,368 | 12,368 | budget_reached |
| Q2A S622 separate continuation | 903 | 10,192 | 10,192 | budget_reached |
| Q2B S633 separate continuation | 904 | 10,336 | 10,336 | budget_reached |
| **total** | | **44,912** | **44,912** | ≤ 50,000 ✓ |

Learnability headroom: **5,088** games.

## Projected total

```text
learnability      44,912
curriculum smoke  10,000   (2 arms x 5,000, §-registered)
--------------------------------
total             54,912   of 62,000   headroom 7,088
```

Overlap analysis runs shadow queries inside evaluation games and is explicitly "evaluation only"
in the compute plan, so it does not enter this ledger.

## Q3 contingency — decided now, before the gate is evaluated

Q3 (ensemble→student distillation) runs **only** if a true online ensemble beats every trainable
single/soup candidate on the **confirmation** panel by ≥3pp teacher gain or ≥3pp strategic-field
gain (§16).

If that gate passes, the remaining learnability allowance is **5,088 completed games** — enough
for a distillation pass and a short PPO continuation, but *not* enough for a distillation run
comparable in length to Q0/Q1/Q2 (~10–12k each).

**Decision, fixed in advance:** if the gate passes, Q3 runs within the 5,088-game remainder and
its result is reported as **budget-limited and not length-matched to Q0/Q1/Q2**. It will not be
compared to them as though it had an equal allowance, and the ceiling will not be raised to make
it comparable. If the gate does not pass, `Q3 = SKIPPED_BY_GATE` and no games are spent.

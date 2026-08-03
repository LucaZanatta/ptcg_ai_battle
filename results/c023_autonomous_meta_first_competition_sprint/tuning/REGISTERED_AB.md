# Registered protocol — the powered A/B that replaces the rest of the search

Written and committed **before the run**, and before the search it replaces was stopped.

## Why the search is being cut short

`REGISTERED_PROTOCOL.md` allows "up to 70 rounds, hard-stopped at 2026-08-04T05:00:00Z". It is
being stopped at ~40 rounds because it has already answered its question, and continuing would
buy precision on a conclusion while actively making its own incumbent worse.

Thirty rounds in, the pooled incumbent series says:

| incumbent | rounds | n | mean dev field |
|---|---|---:|---:|
| the untouched defaults | r0–r4 | 5 | **0.5062** |
| + the r5 change (1 parameter) | r5–r21 | 17 | 0.5067 |
| + the r22 change (4 parameters) | r22–r28 | 7 | **0.4984** |
| + the r29 change (9 parameters) | r29– | 1 | 0.4720 |

**The search is walking downhill.** And `RUNNING_NOTES.md` D7 says exactly why: all three
acceptances fired on low incumbent draws rather than on exceptional children —

| accepted round | incumbent | its rank among 30 incumbent draws (lowest = 1) | best child | vs the mean best child (0.5231) |
|---|---:|---:|---:|---|
| r5 | 0.4980 | 10 | 0.5460 | above |
| r22 | 0.4750 | **2** | 0.5240 | at |
| r29 | 0.4720 | **1** | 0.5210 | **below** |

The two most recent acceptances were won by children that were **not better than average**, against
incumbents that drew the run's two lowest scores. More rounds of this produce more of this.

## What replaces it, and why this is the right test

The search's one substantive suggestion is a hypothesis with a mechanism, and it deserves a
powered test rather than another selection pass. Three of the four accepted parameters point the
same way — **reach harder for a way to attack when the main line has not arrived** — which is the
one failure class the loss mining supports (F5: first attack on turn 2.80 in losses against 2.24
in wins).

| # | function, line | original → tuned | what it means |
|---:|---|---|---|
| 39 | `hand_score` 494 | 28000 → 42956 | fetch **Latias ex** when the Active is a non-attacker and **no Drakloak or Dragapult ex is in play at all** |
| 56 | `hand_score` 557 | 55000 → 60924 | fetch **Crispin** (the energy fetcher) when holding a Dragapult ex but unable to attack and with no benched attacker |
| 75 | `agent` 667 | −1000 → −757 | a smaller penalty for promoting **Fezandipiti ex** to the Active Spot |

Each has a clear semantic role, which is the condition the contract sets for a parameter change to
be admissible at all.

## The arms

| arm | parameters changed |
|---|---|
| `ab_ctrl` | none — the untouched defaults, through the same parameterised source |
| `ab_p39` | 39 only |
| `ab_p56` | 56 only |
| `ab_f5` | 39 + 56 + 75 together |

Four arms, so no arm is the maximum of a set: **there is no selection step, and therefore nothing
for regression to the mean to undo.**

## The measurement

| | |
|---|---|
| panel | the registered **dev** panel, five opponents |
| games | **1,000 per opponent per arm = 5,000 per arm**, 20,000 total |
| standard error of one arm's field score | ≈ **0.71 points** |
| standard error of a difference from the control | ≈ **1.0 point** |
| decision threshold | an arm is carried forward only if it beats the control by **≥ 2.0 points**, i.e. two standard errors |
| then | the survivor — if any — goes to the **validation panel** at 1,000 games per opponent, which no tuning or search has ever seen |

The 2.0-point threshold is fixed here, before the run. It is deliberately *below* the campaign's
~2.4-point single-run noise floor, because 5,000 games per arm is four times the sample those
floor measurements used and the standard error scales accordingly.

## What is predicted

**All three arms land within ±2 points of the control.** The r5 parameter has already been
re-measured seventeen times inside the search and is worth **+0.05 points**; there is no reason
for the others to be different, and the honest expectation is that the whole score-constant
direction is worth nothing.

The reason to run it anyway is that this is the first *unselected, powered* test of the hypothesis
— everything before it was a maximum over five children — and a negative from a clean design is
worth considerably more than a negative from a broken one.

**If an arm does clear +2.0 points**, it goes to the validation panel, and only a result that
survives *there* becomes a challenger.

# M11 — the source's own 15 s / 10 s schedule, executed

`PROBE_MATRIX M11`: *"Original-style 15/10-second schedule executes or exact blocker recorded."*

**It executes.** Two arms, 8 games, 279 searched decisions, `budget_delivered: true` on both,
`decision_deadline_stops: 0`, and the schedule — not a simulation count and not the safety
ceiling — is what stopped every search.

```text
src/SearchConfig.cs   FirstMoveDurationSeconds      = 15
                      ContinuousMoveDurationSeconds = 10
Agent.cs              while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))
                          MonteCarloGraphSearch.Search(ref root, searchConfig, statistics);
                      previousNode = root.IsEndTurn ? null : root;
```

The last line is why the 15 s belongs to the first decision after an **end-turn** rather than to
the first decision of the game, and the port reads the identical condition off the aggregate: an
action whose successor is an opponent node ended the turn.

## What the schedule buys

| | serial (nproc 1, 2 games) | parallel (nproc 6, 6 games) |
|---|---:|---:|
| decisions | 57 | 222 |
| **median simulations/decision** | **610** | **593** |
| p25 / p75 / p90 | 457 / 852 / 1190 | 500 / 796 / 1117 |
| max | 2,564,085 | 4,537 |
| mean | 82,540 | 741 |
| top-3 decisions' share of all simulations | **99.2%** | 5.8% |
| wall clock per game | 301 s | 305 s |

**Read the median.** The source's schedule buys about **600 simulations per decision** on this
hardware — roughly 6.4x the 96 the causal K sweeps used, and 3.5x the 176.6 the frozen c021
control measured. That is the number every comparison in this contract should be set against.

**Do not read the mean.** It is 82,540 in the serial arm because two decisions out of fifty-seven
consumed 2.1 M and 2.56 M simulations between them. Taking it at face value would have produced
the finding "the source's schedule buys 860x the search of the causal sweeps", which is false.
Recorded as `D23`.

## The two collapsed decisions, and what they show

They are decisions where the tree policy reached an already-decided line. A rollout from there
terminates in one or two engine steps, so a simulation costs ~128 µs instead of ~29 ms, and the
remaining seconds go on re-confirming a result the search already had. Two of 279 decisions
across both arms did this — 0.7%, rare but not negligible, and both instances landed in the same
2-game serial arm.

This is a **recorded adaptation becoming visible at a budget it was never measured at.** The
source's `Finalise` prunes proven lines; the port disables it, and
`PREREGISTERED_AGGREGATION.json` justified that as observationally nil, citing the frozen c021
control's `finalised: 0`, `terminal_leaves: 0` over 226,277 rollouts. That justification is
correct *at c021's 176 simulations per decision*. It does not hold at the source's budget, and
only an arm run at the source's budget could have shown so. The adaptation ledger's entry stands;
its evidence base is now explicitly bounded to the budget at which it was measured.

## Parallelism is not the constraint

`EXECUTION_BUDGET.md` carried a 7x internal contradiction about this item — "~1 h" in its
schedule table against "20 games is ~7 h alone" in its cut-order row. The probe was built to
settle it, measuring the same quantity at nproc 1 and nproc 6 because the disagreement was
exactly a serial-versus-parallel question.

**Median 610 against 593: parallel efficiency 0.97.** Six workers cost about 3% of what the
schedule buys. A 20-game arm at nproc 6 projects to ~41 minutes, so the "7 h" figure was a
serial extrapolation and the "~1 h" figure was right.

The probe's own first verdict said the opposite — `parallel_efficiency: 0.009`, "M11 must run at
lower nproc or be blocked" — because it divided one unstable mean by another. It has been
rewritten to use medians. A check that ran, produced a confident verdict, and measured the wrong
statistic is the same family as D13/D17/D19/D20, and it is worth noting that this one was caught
by the number being physically implausible rather than by any other check.

## Scale, and what is deliberately not claimed

The registered arm was 20 games. **It was not run**, and this is a scope decision taken at 21:15
with reasons, not the midnight cut order firing:

- M11's pass condition is that the schedule **executes**. It does, with full artifacts.
- The arm's informative output is the simulation distribution above, and that has n = 279
  decisions already. Twenty more games would not sharpen it materially.
- The only thing 20 games adds is a field score, and at 20 games a Wilson interval spans roughly
  35 points against a **measured 5.0 pp** run-to-run floor. It could not support a claim at any
  value it took.

So **no field score is claimed from this arm.** The observed values — 0.5 over 2 completed games
serial, 0.0 over 5 parallel — are recorded in the summaries and are reported here as
uninterpretable rather than as a result. The 41 minutes went to the decisive ByteRL arms, which
are the contract's compute-limited item.

If that trade is judged wrong, the arm runs with `GAMES=20 bash tools/c022_exclusive_block.sh
unrestricted` and costs ~41 minutes on a quiet machine.

## The finding worth carrying forward

At the source's own budget, in **one fixed determinization**, the search's per-decision predicted
win probability averages 0.53 against a realised 0.474 over 57 decisions. That is a far smaller
gap than the 32.3 pp this contract measured at K=1 with 96 simulations — but it rests on two
games, and the honest statement is that **the single-world overconfidence question has not been
measured at the source's budget**, only at the sweeps'.

The measurement that would settle it is a paired K=1 vs K=8 pair at this schedule, which costs
the same wall clock at either K because the clock is the budget and K divides it. That is the
highest-value MCGS measurement this contract has not made.

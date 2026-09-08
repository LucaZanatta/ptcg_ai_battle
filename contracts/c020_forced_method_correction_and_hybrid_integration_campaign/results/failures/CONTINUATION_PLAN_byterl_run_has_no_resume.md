# Continuation plan — the ByteRL run has no `--resume`

Written at LP0 while the context is fresh, not after a failure. `tools/c020_byterl_train.py` has
no resume flag; if the process dies there is no built-in way to continue, and the run is the
campaign's critical path (100,000-game floor, ~9 hours, single overnight window).

## What survives a crash

Everything except the optimizer moments and the RNG streams, because the trainer flushes as it
goes rather than at the end:

| artifact | path | written |
|---|---|---|
| per-round weights | `byterl/checkpoints/c020/c020_v??????.pt` | every round (480 games) |
| frozen per-period weights | `byterl/checkpoints/c020/c020_frozen_lp???_v??????.pt` | every period end |
| immutable historical pool | `byterl/osfp/historical_checkpoints/c020/` | on promotion, read-only |
| raw games | `byterl/raw_games/c020_games.jsonl.gz` | flushed every round |
| optimizer/loss series | `byterl/learner_logs/c020_losses.jsonl.gz` | flushed every round |
| unrolls / multi-select | `byterl/actor_unrolls/`, `byterl/multiselect_records/` | flushed every round |
| period-local G/C | `byterl/osfp/period_local_GC/c020_lp???_GC.json` | period end |
| frozen evaluations | `byterl/osfp/frozen_evaluations/c020_lp???_games.jsonl` | period end |
| promotions | `byterl/osfp/promotion_history.jsonl` | append mode, period end |
| mixtures | `byterl/osfp/opponent_mixtures/c020_mixtures.jsonl` | period end |

`promotion_history.jsonl` is opened in append mode and every row carries `tag`, so a continuation
run adds to it rather than truncating it.

## Continuation procedure if the run dies

1. Identify the last completed period from `byterl/osfp/c020_learning_periods.jsonl` (one row per
   completed LP) and its `frozen_checkpoint` / `frozen_checkpoint_sha256`.
2. Relaunch with `--tag c020b`, and load that frozen checkpoint as the starting weights. This is
   NOT a c019-weight load — `CONTRACT §2` forbids initializing corrected ByteRL from c019, and
   requires fresh random weights at the START of corrected training. Continuing c020's own
   interrupted run from its own frozen checkpoint preserves that requirement; the fresh-random
   initialization already happened and is recorded in `c020_config.json` with
   `init_param_sha256`.
3. Repopulate `HistoricalPopulation` from `byterl/osfp/historical_checkpoints/c020/` by
   re-registering each file with the hash recorded in `promotion_history.jsonl`. Hashes must
   match; a mismatch means the pool was mutated and the run must not continue.
4. Set `lps_without_add` from the promotion history rather than zero, or the force-add clock
   restarts and the two-addition floor becomes unreachable.
5. Report games, steps and periods as the SUM across `c020` and `c020b`, recounted from the raw
   rows of both, and state the interruption in `SUMMARY.md`. Do not report the continuation as
   one uninterrupted run.

## What a continuation cannot claim

The optimizer moments and both RNG streams are not checkpointed, so a continued run is not the
run that would have happened without the interruption. That is the same limitation probe B12
records for c019 and it would be reported the same way: **resume functionality yes, exact
stochastic continuation no**, stated separately and never merged.

## Decision on run length

Configured 8 periods × 13,000 = 104,000 games against a 100,000-game and 6-period floor, i.e.
4,000 games and 2 periods of margin. The margin is deliberate: period-end frozen evaluations add
games that are not part of `games_per_lp`, and a period that fails to complete would otherwise
drop the campaign below the 6-period floor with no way to recover before morning. The run is NOT
being shortened to save wall clock, because a missed floor forces PARTIAL under `CONTRACT §9`
while extra wall clock costs nothing but time inside a 96-hour box.

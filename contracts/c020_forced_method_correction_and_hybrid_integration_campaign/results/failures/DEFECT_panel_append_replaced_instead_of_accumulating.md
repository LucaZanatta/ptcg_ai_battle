# DEFECT — `--append` replaced earlier panel rows instead of accumulating them

**Found:** immediately after using it, by checking that the row counts had grown rather than
assuming they had.

## What was wrong

Panel rows are keyed by `game_id = f"{tag}:{candidate}:{opponent}:{index}"`, and the merge is

```python
seen = {r["game_id"] for r in ordered}
ordered = [r for r in prior if r["game_id"] not in seen] + ordered
```

A later `--append` batch restarts `index` at 0, so its rows carry the SAME ids as the earlier
batch's first N games and are treated as re-runs of them. Adding 200 games to a candidate that had
100 produced 200 rows, not 300: the original 100 were silently dropped.

The dedup itself is right — re-running a game_id should replace it — but the id did not identify
the game, because the seed was missing from it.

## Consequence

Four candidates lost their first batch: `C019_PIMC_PUCT_CONTROL`, `C019_BYTERL_CONTROL` and
`C019_HYBRID_CONTROL` (100 rows each) and `C020_H0` (200 rows). The reported figures for those
four came entirely from the second batch, at a sample size no larger than before — the exact
opposite of the top-up's purpose, and invisible in the output, which showed a plausible n.

It also made `C019_HYBRID_CONTROL`'s apparent 0.19 -> 0.605 movement a comparison between two
DISJOINT sets of games rather than a growing sample, which is a materially different thing to
interpret.

## Fix

`game_id` now includes the seed: `f"{tag}:{candidate}:{opponent}:s{seed}:{index}"`. Batches at
different seeds accumulate; a genuine re-run at the same seed still replaces, which is the
behaviour the dedup was written for.

## Note

This is the third defect in this campaign whose signature was "a number that looks reasonable" —
after a package that searched 0 decisions while winning half its games, and an option resolver
that returned -1 for everything while passing its source check. In all three cases the output was
plausible and the counter was not checked.

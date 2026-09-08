# DEFECT — the packaged ByteRL carried recurrent state from one game into the next

**Found:** ByteRL package rehearsal, `c020_byterl_rehearsal`, on the LP1 frozen checkpoint.

## Symptom

The package validated cleanly by every other measure — 4 of 4 games completed, both seats, 36 of
36 decisions produced by the learned policy, zero fallbacks, `clean_extraction_ok: true` — and
reported **`resets: 1` across 4 games**.

## Cause

The entry point cached the actor in a module-level dict and counted a reset only at construction.
`ByteRLActor` keeps its LSTM state across `act()` calls by design, because that is what a
recurrent policy must do WITHIN a game. Across games it is a leak: game 2 begins with hidden state
summarising game 1, so the policy is conditioned on a history that did not happen.

`CONTRACT §8` lists "recurrent/action-probability mismatch in the packaged ByteRL branch" as a
submission blocker, and probe B07 requires recurrent state to reset only at TRUE episode
boundaries — which cuts both ways: not mid-game, and not never.

## Fix

The no-select observation IS the deck-submission step that begins a game, so it is the episode
boundary the packaged agent can actually observe:

```python
sel = observation.get("select") if isinstance(observation, dict) else None
a = _actor()
if sel is None:
    a.reset()
    STATS["resets"] += 1
```

Verified: **6 resets over 6 games**, one per boundary, with liveness unchanged (44/44 decisions
from the policy, 0 fallbacks).

## Budget

This is a defect in the generated package entry point, not in the corrected ByteRL method — the
repository-side actor resets correctly per game in training and evaluation, which is why 278 of
278 mid-game unrolls carry stored state while none crosses an episode. It is therefore recorded
with the other packaging defects rather than counted against the single consolidated repair pass,
consistent with how `implementation/repair_pass.md` Part 1 treats the earlier packaging fixes.

It is also, independently, a §8 blocker: a package with this defect could not have been submitted
at all, so leaving it unfixed was not an option that preserved a submission.

## Why the win rate did not reveal it

The rehearsal scored 0.0 both before and after. State leakage degrades play subtly and the
checkpoint is early-training, so the outcome carried no signal. The counter did. This is the
second c020 packaging defect caught by an explicit counter rather than by a result — the first
being a package that searched zero decisions while winning half its games.

# LIMITATION — the common panel cannot pair environment randomness across candidates

**Not a bug in the run; a correction to a claim I made about it.**

## The claim that was wrong

`registered_protocol.json` originally recorded:

```json
"identical_schedule_across_candidates": true
```

alongside a `seed_list`. That reads as "every candidate played the same games", and it is not
true.

## What is actually controlled

| property | controlled? |
|---|---|
| opponent for each pairing | yes |
| seat assignment | yes |
| agent-side RNG seed (MCTS determinization sampling, ByteRL action sampling) | yes |
| environment randomness (deck shuffle, coin flips) | **no** |

`kaggle_environments.make("cabt")` exposes no seed. Its configuration is `actTimeout`,
`episodeSteps`, `runTimeout` — there is no field to fix the shuffle, and `make()` takes no seed
argument. So two candidates playing "the same" pairing play different deals.

## How it showed up

The frozen baseline was measured twice, in two panels built from the same seed base and the same
opponent/seat schedule:

```text
panel mcts_gate  baseline field = 0.5167   CI [0.4281, 0.6042]
panel mcts_full  baseline field = 0.5833   CI [0.4939, 0.6676]
```

A 6.7-point spread for an agent that is byte-identical between the two runs. The intervals
overlap heavily, so this is ordinary sampling variance — but it is variance that pairing was
supposed to cancel and does not.

## Consequence for the c019 findings

The MCTS-versus-baseline gaps are far larger than this spread and survive it:

```text
fast config (12x1)        MCTS 0.3917 vs baseline 0.5167   delta -12.5 pts
registered config (48x3)  MCTS 0.3833 vs baseline 0.5833   delta -20.0 pts
```

Both are several times the observed baseline-to-baseline variation, and the direction is
consistent. The conclusion "faithful MCTS does not beat the frozen baseline" is not endangered
by this limitation. What the limitation *does* forbid is reading small differences — anything
inside the Wilson intervals — as method differences.

## What would fix it

Pairing requires either an environment seed the competition harness does not currently expose, or
replaying a recorded deal to both candidates. Neither is available without modifying the
simulator, which is out of scope. The honest response is to state the limitation, keep the Wilson
intervals, and size comparisons accordingly — which is what the protocol now records.

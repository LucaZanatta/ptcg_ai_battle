# Experimental Rationale

## Why one long contract

The workstreams are sequential and separable:

1. Infrastructure repair changes no policy objective.
2. Overlap analysis changes no weights.
3. Adaptive self-play is the only training intervention.
4. Claude is qualification-only and cannot affect c012 training.

This allows an overnight run without confounding the primary curriculum result.

## Why two training arms

Three seeds each for the unchanged control and adaptive curriculum are more valuable
than spreading compute across multiple underpowered variants.

## Why elite population self-play

Pure mirror self-play risks cycling, narrow exploits, and forgetting. The elite pool
retains diverse learned policies, the frozen teacher, official opponents, and
historical checkpoints.

## Why Claude remains separate

Claude must first prove legality, hidden-information discipline, consistency, and
objective action value. Sophisticated rationales are not evidence of teacher quality.

## Winning criterion

The adaptive curriculum must improve teacher performance and broader field strength
without sacrificing Iono, Abomasnow, or historical-policy coverage.

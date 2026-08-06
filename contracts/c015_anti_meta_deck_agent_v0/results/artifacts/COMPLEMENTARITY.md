# Complementarity and targeted matchup (§13)

**c015 vs the target (exact c014 package): 0.36 over 100 games.**

## The number that matters most

| agent playing the Iono deck | score rate vs the Archaludon deck |
|---|---|
| official Iono sample agent (c014's own measurement) | **0.98** |
| this c015 v0 expert | **0.36** |

Same deck, same target, opposite outcome. The counter exists at the deck level; this v0 does not realise it. That separates *the thesis is wrong* from *my expert is weak*, and the evidence points at the second.

## Portfolio complementarity

c014's weakest matchup was the Iono archetype (0.020). c015 **is** that archetype, so the portfolio now covers the lane that beat c014 rather than doubling down on c014's own lane.

**Caveat that cuts against over-reading this:** c014 scored 600.0 publicly while scoring 0.020 against this deck locally, so the four-agent local panel is not representative of the ladder and no local result is claimed to predict a public score.

## Falsifier

Registered before any game: `fails if the agent does not exceed a 0.60 score rate against the exact c014 package on the untouched final panel while executing Electric Streamer on at least 60% of turns where a Basic {L} Energy was in hand`

**Result: FALSIFIED - score vs target 0.36 < 0.60 threshold.** Mechanism A executed at 1.000 when available, so the falsifier failed on the matchup half, not the execution half.


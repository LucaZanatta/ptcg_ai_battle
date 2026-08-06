# Next Step (AC-15)

**NEXT_STEP = SCALE_FIXED_DECK_RL**

Training-loop status: **PROMISING** (reproducibility INCONCLUSIVE, exact continuation INCONCLUSIVE, stabilized continuation EXTENDED).

**Highest-leverage blocker (exactly one):** Early-game credit assignment. The value function explains 0.43 of held-out return variance in the first fifth of a game against 0.80 in the fourth fifth, so opening decisions — the ones the strategic field punishes hardest — train on the noisiest advantage estimates. Continuation is no longer the constraint: a registered arm reached EXTENDED across its seeds, and both exact-recipe arms fell short only on the field dimension.

`BEGIN_DECK_PIPELINE` is gated on a VALIDATED loop with policy variance low enough for deck comparisons to be meaningful (§2); that gate is not met, so fixed-deck agent work continues.

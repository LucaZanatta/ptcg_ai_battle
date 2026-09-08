# P11 — PPO update proof

c017 reported a curriculum in which no game was played and no optimiser ever stepped. Nothing
below is read from the curriculum report except as the claim being tested.

**Games are real.** 81,920 per-game rows exist on disk, written as each block
finished, 81,920 of them terminal. The report claims
81,920 — recounting the rows agrees.

**Updates are real.** 80 update rows sum to
66,604 optimiser steps against 66,604
reported, over 4,252,231 trainable decisions. All losses finite.

**Weights actually moved.** Each update row records the weight hash before and after; all
80/80 blocks changed it, and there are
80 distinct post-update hashes. A block whose before/after hash
agreed would have done nothing regardless of what its loss printed.

**Status: PASS.**

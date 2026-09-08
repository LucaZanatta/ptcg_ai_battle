# B12 — Training continuation

The matrix requires these two be reported SEPARATELY and forbids describing unequal hashes as exact continuation. They are answered here as two independent questions.

**1. Resume functionality — does a checkpoint fully determine the policy?** `34` of `34` parameters load bitwise-equal into a freshly constructed model, and the two models produce identical output on `24` real observations (max absolute difference `0.0`). Equal weights alone would not settle this — behaviour depending on un-checkpointed state would still pass a weight comparison — so the forward pass is checked too. The freshly built model is confirmed to DIFFER before loading, otherwise the comparison would be vacuous.

**Status: PASS.**

**2. Exact stochastic continuation — would resuming reproduce the original training stream?** **No**, and this is answered from what the checkpoint contains rather than from a hash comparison. Missing: `learner_rng_state, actor_rng_states, optimizer_state, queue_contents`. A resumed run draws a different stochastic stream from its first step.

**Status: NOT_SUPPORTED.**

The two are not merged, and resume is nowhere described as exactness.

# B03 — Actor version and staleness

Every unroll records the behavior policy version; every learner update records the queue length and the staleness distribution of its minibatch. 40516 updates logged, mean staleness 1004.08 learner versions.

This is the quantity that makes V-trace necessary rather than decorative: with zero staleness the importance ratios would all be 1 and the correction would do nothing.

**Status: PASS.**

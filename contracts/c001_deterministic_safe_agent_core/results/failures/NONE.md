# Failures

No failures, invalid selections, or unresolved diagnostics for c001.

- Unit tests: 30/30 passed (0 failures, 0 errors).
- Benchmark: 300/300 games completed, 0 failed, **0 invalid safe selections**.
- All 8 acceptance criteria verified.

The one benchmark latency `max` of 87.47 ms is a single first-call warm-up
sample and is **not** a failure: the acceptance bound is on P99 (0.207 ms),
which passes with a large margin. See `SUMMARY.md`.

This file exists to satisfy the mandatory `failures/` directory.

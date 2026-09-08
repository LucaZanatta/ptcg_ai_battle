# P90 — Evidence validator

135/135 checks passed in **final** mode,
0 critical failures, 0 submission
blockers.

**Every check re-derives from raw artifacts.** A summary asserting a number is never accepted as
evidence for that number — games are recounted from per-game JSONL rows, optimiser steps from
per-update rows, and the realised opponent mix from raw opponent labels. That principle was
violated in this validator's own first draft, which read training claims straight out of the
report it was judging (`failures/DEFECT_validator_read_the_report_it_was_judging.md`).

The validator also refuses to pass by omission: in `--final` mode an absent milestone is a
critical failure, not a free pass. Its first run returned PASS with no training on disk at all
(`failures/DEFECT_validator_returned_pass_with_no_training_at_all.md`).

Each rejection is pinned by a unit test that constructs the fabrication and asserts refusal:
static scoring claimed as search, virtual curriculum games, inflated game counts, planned mix
reported as actual, stale lagged-snapshot paths, zero optimiser steps, unchanged checkpoints,
untrusted rows marked trusted, labels outside the option range, and games straddling splits.

Critical failures: none.
Submission blockers: none.
Not exercised: none.

**Status: PASS.**

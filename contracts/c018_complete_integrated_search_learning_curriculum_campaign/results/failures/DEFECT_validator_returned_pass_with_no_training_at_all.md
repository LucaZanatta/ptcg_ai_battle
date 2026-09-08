# DEFECT — the evidence validator returned PASS for a campaign that had trained nothing

**Severity: would have invalidated the contract's own verdict.** Found on the validator's first
run, before it had judged any real work.

## What happened

`tools/c018_validate.py` was written early, deliberately, so it could fail this campaign's work
while there was still time to act. Its first execution returned:

```
n_checks: 36, n_passed: 31, n_critical_failures: 0, overall: PASS
```

with **no distillation report, no curriculum report, and no final panel on disk**. The five
failures were all presence checks, and each had been marked `critical=False` so that an
in-progress run would not look broken.

That is precisely the failure mode the contract names: *skipped criteria counted pass*. A
campaign that did nothing at all would have scored PASS, because absence was indistinguishable
from not-yet.

## Fix

A `require()` wrapper that is non-critical during interim runs and **critical in `--final`
mode**, plus `no_skipped_criteria_counted_as_pass`, which fails in final mode if anything was
recorded as not-yet-exercised. Two unit tests pin both directions:
`test_final_mode_rejects_absent_milestones` and
`test_interim_mode_treats_absent_milestones_as_not_yet_exercised`.

## Generalisable lesson

A validator needs to distinguish "this claim is false" from "this claim was never made", and it
must treat the second as failure at exactly one moment: final judgement. Collapsing the two in
either direction produces a useless validator — always-failing during the run, or always-passing
at the end.

# Non-Blocking Probe Policy

Probe outcomes are:

- `PASS`: expected behavior observed.
- `WARN`: anomaly exists but does not materially invalidate downstream work.
- `FAIL_TAINTED`: defect may invalidate dependent artifacts; continue where technically possible and record dependency taint.
- `NOT_EXERCISED`: path was not reached.

Do not pause the first integrated run to perfect a failed probe unless further execution is technically impossible.

Workflow:

1. record the exact failure, input, traceback, configuration, and source hash;
2. apply only the minimum compatibility fallback needed to continue;
3. propagate taint into downstream artifacts;
4. finish the first full vertical run;
5. rank at most three highest-impact defects;
6. perform one consolidated repair pass;
7. rerun only the affected pipeline from the earliest necessary checkpoint.

Submission blockers for the affected candidate are limited to hidden-information leakage, illegal actions, package/source mismatch, unacceptable crash or timeout risk, evaluation identity corruption, or unresolved reuse permission.

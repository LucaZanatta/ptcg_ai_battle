# Note: the `vram_free_ge_8gib` preflight check fails at report time

`dependency_verification.json` reports one failing check:

```text
[FAIL] vram_free_ge_8gib   7472   (later re-measured at 7654 MiB)
```

## Cause

Unrelated processes hold GPU memory on this machine:

```text
1493231  /opt/tritonserver/bin/tritonserver   1036 MiB
1838136  python3                              1261 MiB
```

Total VRAM is 12,227 MiB, so ~7.5 GiB is free against a preflight threshold of 8 GiB. Neither
process belongs to c013.

## Why this does not invalidate any c013 result

The threshold is a **preflight resource check**, not a property of any measurement. All c013
CUDA work — the Q0/Q1/Q2A/Q2B learnability arms (44,912 completed games) and both curriculum
smoke arms (10,112 completed games) — ran to completion on this GPU with no OOM, no fallback to
CPU, and no degraded path. The relevant evidence is that the training actually finished, which
the raw per-game counts confirm independently of any resource check.

The check is reported as failing rather than suppressed or re-thresholded. Re-running it after
the external processes exit would make it pass, but editing a threshold or waiting for an
unrelated process so a check goes green is exactly the sort of cosmetic adjustment these
contracts exist to prevent, so the failing state is left recorded as measured.

## Effect on status

Non-blocking. It is an environment condition contemporaneous with reporting, disclosed here and
in `STATUS.json`, and it affects no panel, ranking, verdict, or budget figure.

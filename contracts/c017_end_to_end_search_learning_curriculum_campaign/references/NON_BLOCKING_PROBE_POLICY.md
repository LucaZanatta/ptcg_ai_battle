# Non-blocking probe and taint policy

## Purpose

Probes provide observability and reproducibility. They are not independent mini-projects and are not sequential approval gates.

## Rules

- Run probes automatically beside the integrated pipeline.
- A failed probe records exact evidence and taints dependent artifacts.
- Continue downstream when technically possible.
- Do not hide taint or convert `NOT_EXERCISED` into `PASS`.
- Repair at most three highest-impact defects in one consolidated pass.
- Rerun only from the earliest affected milestone.
- Submission eligibility is stricter than experimental execution eligibility.

## Submission blockers

- hidden-information leakage;
- illegal actions;
- package crashes/timeouts;
- evaluation identity corruption;
- stale/wrong checkpoint used for promotion;
- package/source/config/deck/checkpoint mismatch;
- unresolved permission/attribution;
- clean extraction/import failure.

## Non-blocking examples

- search misses tactical fixtures;
- search is weak;
- policy imitation accuracy is low;
- value calibration is noisy;
- curriculum does not promote;
- fallback curriculum is used;
- one matchup regresses;
- a downstream stage is diagnostic only.

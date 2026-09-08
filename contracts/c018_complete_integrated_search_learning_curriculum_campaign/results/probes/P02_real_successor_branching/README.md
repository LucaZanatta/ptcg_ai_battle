# P02 — Real successor branching

Does the search actually advance the simulator, or does it score the root and stop? c017 claimed
search while doing the latter; this probe exists because that claim was believed once.

**Evidence.** 609,875 successful `search_step` calls produced
353,448 distinct successor observations across 42,857 search
roots — 8.25 per root. Maximum depth reached is
4 (a depth-0 scorer cannot exceed 0). 59 of 60 sampled
traces record a chain of depth ≥ 2, and 42,648 decisions saw more than one distinct
successor — i.e. the tree genuinely branched rather than replaying one line.

**Per-decision, not just in aggregate.** An aggregate successor count cannot distinguish a
branching tree from one long line, so each decision was checked individually:
2,937 of 2,952
examined decisions produced **two or more distinct successor observations**, and
2,937 reached depth > 1.
1,610 produced candidates with *different* leaf values —
i.e. the tree discriminated rather than returning a flat score list. Raw rows:
`artifacts/branch_proof.json`.

4,847 steps (0.7880%) returned an engine error; those nodes
are dropped from the beam and the decision falls back rather than being recorded as searched.

**Status: PASS.**

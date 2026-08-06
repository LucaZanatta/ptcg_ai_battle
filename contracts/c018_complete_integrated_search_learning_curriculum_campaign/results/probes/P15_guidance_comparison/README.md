# P15 — Guidance comparison

Heuristic vs learned ordering and leaf values evaluated on the **same real search roots**, so
the difference is the guidance and not a different searcher.

Roots compared: 301. Decisions where learned ordering changed which candidates fit
the budget: 215. Decisions where the learned leaf value picked a different
action than the heuristic leaf value: 133
(0.4419). Rank correlation between the two leaf valuations:
-0.0087.

**Status: PASS.**

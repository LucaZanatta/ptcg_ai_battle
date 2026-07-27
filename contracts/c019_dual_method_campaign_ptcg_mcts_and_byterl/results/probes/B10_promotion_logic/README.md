# B10 — Promotion logic

Synthetic fixtures cover all three paths before any live run: performance promotion, no promotion (including the insufficiently-sampled case, so one lucky game cannot promote), and `FORCED_MAX_LP`. A forced addition is never labelled `PERFORMANCE`.

Live decisions so far: {'FIRST_HISTORICAL': 1, 'NO_PROMOTION': 7, 'PERFORMANCE': 1, 'FORCED_MAX_LP': 1}.

A forced addition is implementation evidence and carries no strategic strength claim; the reason field exists so the two can never be conflated in a report.

**Status: PASS.**

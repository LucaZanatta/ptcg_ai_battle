# B11 — OSFP period reset

Every period allocates `G` and `C` fresh; per-period evaluation-game totals are [0, 160, 160, 159, 160, 160, 160, 160], not a monotone accumulation. Each payoff row cites exactly ONE frozen checkpoint hash, and recording a second checkpoint's result into a row RAISES rather than silently pooling.

c019 accumulated across periods and across changing learner policies (audit #12), so 'the current policy beats historical opponent 0 at 56%' really meant the average of six policies, most of them obsolete.

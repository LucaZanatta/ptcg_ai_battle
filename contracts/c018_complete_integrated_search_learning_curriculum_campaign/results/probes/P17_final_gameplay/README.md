# P17 — Final gameplay panel

2,400 raw games, 2,400 scored, 0 incomplete.
Every candidate faced **the same opponents at the same seeds and seats**
(`all_candidates_same_schedule: True`); the schedule was built
once before any game ran, so no candidate could draw an easier field.

Every reported rate was recomputed from the raw rows using each row's own `candidate_id` /
`opponent_id`: 0 mismatches.

| candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|
| official_mega_lucario | 400 | 0.58 | [0.5311, 0.6274] | mega_abomasnow @ 0.47 |
| m03_curriculum_policy | 400 | 0.2475 | [0.2077, 0.2921] | mega_abomasnow @ 0.16 |
| m04_guided_search | 400 | 0.215 | [0.1776, 0.2579] | mega_abomasnow @ 0.15 |
| m04_guided_ordering_only | 400 | 0.2125 | [0.1752, 0.2552] | dragapult @ 0.12 |
| m01_heuristic_search | 400 | 0.21 | [0.1729, 0.2526] | dragapult @ 0.14 |
| m02_distilled_policy | 400 | 0.175 | [0.1409, 0.2153] | dragapult @ 0.12 |

Ranking rule (pre-registered): overall_rate desc, then worst_matchup_rate desc (pre-registered).

## Does overriding the baseline help?

`m01_heuristic_search` **is** `official_mega_lucario` plus a search that never prunes the
baseline action — it is always candidate 0. If the search were neutral the two would score
identically, so any gap is attributable to the leaf evaluator preferring a worse successor,
never to the search failing to consider the baseline.

Splitting each searching candidate's games at the median rate at which the search overrode the
baseline:

| candidate | games | low-override rate → win | high-override rate → win | overriding more helps |
|---|---|---|---|---|
| m01_heuristic_search | 400 | 0.2052 → 0.195 | 0.3319 → 0.225 | True |
| m04_guided_ordering_only | 400 | 0.2186 → 0.175 | 0.3511 → 0.25 | True |
| m04_guided_search | 400 | 0.163 → 0.165 | 0.3791 → 0.265 | True |

This is observational, not randomised — games where the search overrode more may simply be
longer or more contested — so it is a diagnostic pointer, not a causal claim. It does localise
where to look next.

Leader: **official_mega_lucario** at 0.58 (CI [0.5311, 0.6274]).

**Status: PASS.**

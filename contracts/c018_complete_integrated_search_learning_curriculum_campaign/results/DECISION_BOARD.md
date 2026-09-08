# c018 Decision Board

External evidence outranks local elegance (§39).

| role | id | panel rate | 95% CI | note |
|---|---|---|---|---|
| CHAMPION | dragapult |  |  | externally confirmed control; unbeaten by any post-baseline c018 agent on external evidence |
| CHALLENGER | official_mega_lucario | 0.58 | [0.5311, 0.6274] |  |
| ARCHIVE | m03_curriculum_policy | 0.2475 | [0.2077, 0.2921] |  |
| CHALLENGER | m04_guided_search | 0.215 | [0.1776, 0.2579] |  |
| ARCHIVE | m04_guided_ordering_only | 0.2125 | [0.1752, 0.2552] |  |
| CHALLENGER | m01_heuristic_search | 0.21 | [0.1729, 0.2526] |  |
| ARCHIVE | m02_distilled_policy | 0.175 | [0.1409, 0.2153] |  |
| ARCHIVE | c017_depth_zero_ranker |  |  | c017's static scorer, disproven as search by P01/P02 |
| ARCHIVE | c017_distilled_policy |  |  | not continued by c018; trained on depth-zero labels |
| DIAGNOSTIC | P10 |  |  | WARN |
| DIAGNOSTIC | P14 |  |  | WARN |

**Dragapult remains CHAMPION.** It is the externally confirmed control, and §39 keeps it there
until a post-baseline c018 agent proves otherwise on external evidence. The frozen panel ranks
*local* candidates only, so its leader is a challenger, not a champion — a distinction this
board keeps deliberately, because the project's own history is of local rankings that did not
survive contact with the ladder.

Official Mega Lucario is the calibration challenger. c017's depth-zero ranker and its distilled
policy remain ARCHIVE: P01/P02 disproved the former as search, and c018 does not continue the
latter.

Submission decision and its pre-registered gate: see `../DECISION_RULES.md` §4 as corrected by
Amendment 3, and item 9 of `SUMMARY.md`.

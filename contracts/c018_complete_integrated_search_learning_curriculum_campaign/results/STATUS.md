# c018 — STATUS: PARTIAL

Complete integrated search / learning / curriculum campaign.
Commit `4cbae35888` on `contract/c018_complete_integrated_search_learning_curriculum_campaign`, parent `d8a34b1bac60dc57ec7b0c356c3b261cc10d95da`.

## What this campaign established

**c017's central claim was wrong, and it is now corrected.** c017 concluded that forward
simulation was impossible because `env.clone()` shared native state and segfaulted. The official
search interface — `to_observation_class`, `search_begin`, `search_step`, `search_release`,
`search_end` — was in the same `cg/api.py` file c017 had already read. c018 uses it:
42,857 real search roots, 609,875 successful `search_step`
calls, depth 0, 353,448 distinct successor
observations.

**c017's curriculum did no training.** It sampled a mixture, incremented a counter, and
re-evaluated an unchanged checkpoint. c018's curriculum played
81,920 real simulator games and took
66,604 optimiser steps, with every game and every update written
to a raw JSONL *before* any aggregate was computed, so both numbers can be recounted from disk.

## Execution floors

| floor | actual | required | |
|---|---|---|---|
| real search_begin roots >= 200 | 42,857 | 200 | met |
| real search_step calls >= 5000 | 609,875 | 5,000 | met |
| trusted search-labelled decisions >= 10000 | 42,857 | 10,000 | met |
| actual PPO curriculum games >= 20000 | 81,920 | 20,000 | met |
| optimizer steps total >= 1000 | 73,684 | 1,000 | met |
| final-panel games >= 600 | 2,400 | 600 | met |
| accepted post-baseline submissions >= 1 | 0 | 1 | **MISSED** |

## Final panel

Every candidate faced the same opponents at the same seeds and seats
(2400 scored games). Ranking rule pre-registered in
`DECISION_RULES.md` before the panel ran: overall rate, then worst matchup.

| candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|
| official_mega_lucario | 400 | 0.58 | [0.5311, 0.6274] | mega_abomasnow @ 0.47 |
| m03_curriculum_policy | 400 | 0.2475 | [0.2077, 0.2921] | mega_abomasnow @ 0.16 |
| m04_guided_search | 400 | 0.215 | [0.1776, 0.2579] | mega_abomasnow @ 0.15 |
| m04_guided_ordering_only | 400 | 0.2125 | [0.1752, 0.2552] | dragapult @ 0.12 |
| m01_heuristic_search | 400 | 0.21 | [0.1729, 0.2526] | dragapult @ 0.14 |
| m02_distilled_policy | 400 | 0.175 | [0.1409, 0.2153] | dragapult @ 0.12 |

## Board

| role | id | value |
|---|---|---|
| CHAMPION | dragapult | externally confirmed control; unbeaten by any post-baseline c018 agent on external evidence |
| CHALLENGER | official_mega_lucario | 0.58 |
| ARCHIVE | m03_curriculum_policy | 0.2475 |
| CHALLENGER | m04_guided_search | 0.215 |
| ARCHIVE | m04_guided_ordering_only | 0.2125 |
| CHALLENGER | m01_heuristic_search | 0.21 |
| ARCHIVE | m02_distilled_policy | 0.175 |
| ARCHIVE | c017_depth_zero_ranker | c017's static scorer, disproven as search by P01/P02 |
| ARCHIVE | c017_distilled_policy | not continued by c018; trained on depth-zero labels |
| DIAGNOSTIC | P10 | WARN |
| DIAGNOSTIC | P14 | WARN |

## Probes

| probe | status |
|---|---|
| P01 | PASS |
| P02 | PASS |
| P03 | PASS |
| P04 | PASS |
| P05 | PASS |
| P06 | PASS |
| P07 | PASS |
| P08 | PASS |
| P09 | PASS |
| P10 | WARN |
| P11 | PASS |
| P12 | PASS |
| P13 | PASS |
| P14 | WARN |
| P15 | PASS |
| P16 | PASS |
| P17 | PASS |
| P30 | PASS |
| P90 | PASS |

## Evidence validation (P90)

135/135 checks passed, 0
critical failures, 0 submission blockers. Every training and
search claim is recounted from raw rows; the report's own numbers are treated as the claim being
tested, never as evidence for themselves.

## Honest limits

- **The rising within-block curriculum win rate is not evidence of improvement.** As the
  self-play share grows the opponent field changes, so those rates measure a changing field.
  Only the frozen panel compares like with like.
- **Top-1 agreement is first-pick agreement** — the supervised label stores `label_action[0]`,
  so multi-select decisions are scored on their first option only.
- **Imitating the search is not playing well.** P09/P10 measure imitation; P17 measures play.
- **The public score is a live ladder rating**, not a fixed evaluation. It moves 100+ points
  within minutes and 600.0 is the provisional start value. No strength claim here cites it.

## Missed

- accepted post-baseline submissions >= 1

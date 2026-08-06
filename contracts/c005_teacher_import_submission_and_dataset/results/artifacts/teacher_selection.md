# Teacher Selection — c005

Selection is pre-registered as code (`tools/select_teacher.py`) and applied to the
raw gauntlet artifacts. The only non-computed input is `external_evidence` (a
pre-registered tier, justified per candidate in `teacher_scorecard.csv`).

**Primary teacher: `dragapult`**  |  **Backup teacher: `mega_lucario`**  |  Override: none

## Scores

| candidate | archetype | submission-eligible | reliability-eligible | high-impact ctx | competitive_score | teacher_score |
|---|---|---|---|---|---|---|
| dragapult | spread_setup | yes | yes | 8 | 0.842 | **0.889** |
| mega_lucario | switch_midrange | yes | yes | 6 | 0.930 | 0.746 |
| mega_abomasnow | linear_aggro | yes | yes | 6 | 0.453 | 0.367 |
| iono | disruption_control | yes | yes | 6 | 0.260 | 0.313 |

## Rule
- `competitive_score = 0.50·norm_local_strength + 0.20·norm_worst_matchup_lb + 0.20·external_evidence + 0.10·norm_latency_reliability`
- `teacher_score = 0.70·competitive_score + 0.15·norm_high_impact_coverage + 0.10·norm_action_entropy + 0.05·reproducibility`
- **Primary** = eligible candidate (submission-eligible, reliability-pass, ≥5 high-impact contexts) with highest `teacher_score`.
- **Backup** = highest remaining eligible by `competitive_score`, preferring a different archetype.

## Why dragapult is primary (not the competitive_score leader)
`mega_lucario` has the higher `competitive_score` (0.930) — it is the marginal
Bradley-Terry point leader. But the top candidates are **statistically tied**
(overlapping bootstrap strength intervals; head-to-head balanced ≈ 0.51). The
**primary teacher is chosen by `teacher_score`**, which additionally rewards
teaching richness — and `dragapult` has the most high-impact decision contexts
(8 vs 6) and higher action entropy, i.e. a richer supervision signal for
behavioral cloning. That is exactly the property a distillation teacher needs, and
it matches the research prior. `dragapult` is Submission-A eligible.

## Why mega_lucario is backup
Among the remaining eligible candidates it has the highest `competitive_score`
(0.930) and a **different archetype** (switch_midrange vs spread_setup), giving
policy/archetype diversity for the backup baseline.

## Eligibility
All four candidates are eligible (submission-eligible official samples,
reliability gate 0 defects over 720 gauntlet games, ≥5 high-impact contexts each).
`mega_abomasnow` and `iono` are not selected (lower `teacher_score`).

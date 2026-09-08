# Strategic Candidate Admission — c005

Four **real strategic** rule-based teachers (official Kaggle samples) were
acquired, frozen, smoke-gated, and all four admitted. Engineering controls (the
c004 deterministic/random agents) are NOT strategic teachers and do not count.
The public `wmh/ptcg-abc` repo (no license) was acquired but classified
`LOCAL_BENCHMARK_ONLY` and **not admitted** (not submission-eligible, not copied
into training data).

| candidate | display | archetype | reuse | submission-eligible | deck_id | smoke |
|---|---|---|---|---|---|---|
| dragapult | Dragapult ex | spread_setup | OFFICIAL_REUSABLE | yes | `sha256:8055443275c8…` | 20/20 games, 0 defects |
| mega_lucario | Mega Lucario ex | switch_midrange | OFFICIAL_REUSABLE | yes | `sha256:d05bff224d40…` | 20/20 games, 0 defects |
| mega_abomasnow | Mega Abomasnow ex | linear_aggro | OFFICIAL_REUSABLE | yes | `sha256:3c8145c7e5d9…` | 20/20 games, 0 defects |
| iono | Iono's deck | disruption_control | OFFICIAL_REUSABLE | yes | `sha256:282504e445a4…` | 20/20 games, 0 defects |

## Distinctness
Four distinct rule-based policies AND four distinct deck archetypes (distinct
canonical deck_ids). All four are submission-eligible official samples, so the
strategic field satisfies the ≥3-policies / ≥3-archetypes minimum comfortably.

## Compatibility adaptation (behavior-preserving)
Only `starter_kit/teachers.py` adapts the candidates: it loads a **fresh module
instance per game per seat** (the rule-based teachers keep module-level state and
do not reset on deck selection) and reads each teacher's bundled `deck.csv`. No
action priorities, heuristics, card priorities, deck lists, or fallback behaviour
were changed.

## Freeze
Freeze hashes (main.py sha256, deck.csv sha256, canonical deck_id, policy_type)
were recorded before the gauntlet and re-verified **identical** after — the files
candidate_freeze_before.json and candidate_freeze_after.json are equal.

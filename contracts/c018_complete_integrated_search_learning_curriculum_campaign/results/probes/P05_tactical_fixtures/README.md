# P05 — Tactical fixtures and traces

All 7 §15 categories are covered by **real captured roots**, each
retaining the root select context and option types, every candidate select, the leaf
decomposition per candidate, the chosen line, the dominated lines, and nodes/depth/time.
Raw: `artifacts/tactical_fixtures.json`.

| category | fixtures |
|---|---|
| missed_lethal | 3 |
| wrong_attack_or_target | 3 |
| energy_attachment_route | 3 |
| evolution_timing | 3 |
| bench_liability | 3 |
| resource_reservation | 3 |
| search_card_sequencing | 3 |

**Two categories needed a substantive definition, not a contextual one.** `missed_lethal` was
first defined as an attack context with a single option — but a single-option attack is a
*forced* move that never reaches the search, so that definition guaranteed an empty category.
It now means an attack decision where some candidate's leaf value beats the baseline's by more
than one prize (0.55/6 of the leaf scale), i.e. the search found a knockout the baseline missed.
`bench_liability` likewise now means a decision taken with a bench of ≤ 1, which is where bench
state actually creates risk, rather than only the explicit TO_BENCH context.

Across 13 distinct decision contexts the search changed the baseline
action 11,752 times
(27.4% of searched decisions). A search that never disagrees
with its baseline is an expensive identity function; one that always disagrees is usually broken.

**What these fixtures do not show.** They demonstrate the search machinery is real and
discriminating. They are not evidence the leaf evaluator's preferences are *correct* — that
claim belongs to the gameplay panel (P17).

**Status: PASS.**

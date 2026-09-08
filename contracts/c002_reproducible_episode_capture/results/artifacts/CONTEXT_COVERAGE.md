# SelectContext Coverage & Latency

- **Enum-defined contexts:** 49 (every `SelectContext` member, including zero-count).
- **Runtime-observed contexts:** 11 (22.45% of enum).
- **Total decisions:** 2433; by seat: {'0': 1267, '1': 1166}.

> Enum coverage and runtime coverage are distinct: the selector is compatible with every enum context, but only a subset arises in sampled games.

| context | value | observed | count | seat0 | seat1 | fallback | invalid | p50 ms | p95 ms | p99 ms | max ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 0 | yes | 1646 | 841 | 805 | 1162 | 0 | 0.0548 | 0.1295 | 0.1769 | 1.6505 |
| SETUP_ACTIVE_POKEMON | 1 | yes | 120 | 60 | 60 | 80 | 0 | 0.0570 | 0.1631 | 0.2356 | 0.3074 |
| SETUP_BENCH_POKEMON | 2 | yes | 32 | 18 | 14 | 19 | 0 | 0.0418 | 0.0577 | 0.0619 | 0.0637 |
| SWITCH | 3 | yes | 6 | 3 | 3 | 0 | 0 | 0.0032 | 0.0034 | 0.0034 | 0.0034 |
| TO_ACTIVE | 4 | yes | 59 | 26 | 33 | 36 | 0 | 0.0970 | 0.1587 | 0.2011 | 0.2056 |
| TO_BENCH | 5 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_FIELD | 6 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_HAND | 7 | yes | 268 | 147 | 121 | 206 | 0 | 0.0755 | 0.1142 | 0.1663 | 0.1905 |
| DISCARD | 8 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_DECK | 9 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_DECK_BOTTOM | 10 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_PRIZE | 11 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| NOT_MOVE | 12 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DAMAGE_COUNTER | 13 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DAMAGE_COUNTER_ANY | 14 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DAMAGE | 15 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| REMOVE_DAMAGE_COUNTER | 16 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| HEAL | 17 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| EVOLVES_FROM | 18 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| EVOLVES_TO | 19 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DEVOLVE | 20 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| ATTACH_FROM | 21 | yes | 88 | 41 | 47 | 64 | 0 | 0.0477 | 0.1248 | 9.7721 | 74.0254 |
| ATTACH_TO | 22 | yes | 88 | 41 | 47 | 64 | 0 | 0.0661 | 0.1102 | 0.1591 | 0.1628 |
| DETACH_FROM | 23 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| LOOK | 24 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| EFFECT_TARGET | 25 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DISCARD_ENERGY_CARD | 26 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DISCARD_TOOL_CARD | 27 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| SWITCH_ENERGY_CARD | 28 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DISCARD_CARD_OR_ATTACHED_CARD | 29 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DISCARD_ENERGY | 30 | yes | 29 | 13 | 16 | 0 | 0 | 0.0031 | 0.0036 | 0.0037 | 0.0037 |
| TO_HAND_ENERGY | 31 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| TO_DECK_ENERGY | 32 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| SWITCH_ENERGY | 33 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| SKILL_ORDER | 34 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| ATTACK | 35 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DISABLE_ATTACK | 36 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| EVOLVE | 37 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| DRAW_COUNT | 38 | yes | 37 | 17 | 20 | 23 | 0 | 0.0824 | 0.1626 | 0.3026 | 0.3358 |
| DAMAGE_COUNTER_COUNT | 39 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| REMOVE_DAMAGE_COUNTER_COUNT | 40 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| IS_FIRST | 41 | yes | 60 | 60 | 0 | 40 | 0 | 0.0241 | 0.0300 | 0.0409 | 0.0462 |
| MULLIGAN | 42 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| ACTIVATE | 43 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| FIRST_EFFECT | 44 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| MORE_DEVOLVE | 45 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| COIN_HEAD | 46 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| AFFECT_SPECIAL_CONDITION | 47 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |
| RECOVER_SPECIAL_CONDITION | 48 | no | 0 | 0 | 0 | 0 | 0 |  |  |  |  |

**Not observed (38):** TO_BENCH, TO_FIELD, DISCARD, TO_DECK, TO_DECK_BOTTOM, TO_PRIZE, NOT_MOVE, DAMAGE_COUNTER, DAMAGE_COUNTER_ANY, DAMAGE, REMOVE_DAMAGE_COUNTER, HEAL, EVOLVES_FROM, EVOLVES_TO, DEVOLVE, DETACH_FROM, LOOK, EFFECT_TARGET, DISCARD_ENERGY_CARD, DISCARD_TOOL_CARD, SWITCH_ENERGY_CARD, DISCARD_CARD_OR_ATTACHED_CARD, TO_HAND_ENERGY, TO_DECK_ENERGY, SWITCH_ENERGY, SKILL_ORDER, ATTACK, DISABLE_ATTACK, EVOLVE, DAMAGE_COUNTER_COUNT, REMOVE_DAMAGE_COUNTER_COUNT, MULLIGAN, ACTIVATE, FIRST_EFFECT, MORE_DEVOLVE, COIN_HEAD, AFFECT_SPECIAL_CONDITION, RECOVER_SPECIAL_CONDITION

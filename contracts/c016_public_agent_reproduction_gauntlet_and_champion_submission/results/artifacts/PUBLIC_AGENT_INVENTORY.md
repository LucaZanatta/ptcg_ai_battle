# Public-agent inventory (§11)

7 candidate leads. Title claims are preserved as `PUBLIC_CLAIM` and are not treated as measured truth.

| candidate | author | deck | claim | algorithm | evidence | permission | disposition |
|---|---|---|---|---|---|---|---|
| `official_dragapult` | Kiyota (kiyotah) | Dragapult ex | Dragapult sample scored 719.7 on the public ladder as c005 ref 54948560 | rule-based strategic agent with planning, pr | OFFICIAL_CURRENT | SUBMISSION_REUSE_ALLOWED | CONTROL |
| `official_mega_lucario` | Kiyota (kiyotah) | Mega Lucario ex | no published score claim | rule-based strategic agent with planning, pr | OFFICIAL_CURRENT | SUBMISSION_REUSE_ALLOWED | ADVANCE |
| `official_mega_abomasnow` | Kiyota (kiyotah) | Mega Abomasnow ex | no published score claim | rule-based strategic agent with planning, pr | OFFICIAL_CURRENT | SUBMISSION_REUSE_ALLOWED | ADVANCE |
| `official_iono` | Kiyota (kiyotah) | Iono's deck | no published score claim | rule-based strategic agent with planning, pr | OFFICIAL_CURRENT | SUBMISSION_REUSE_ALLOWED | ADVANCE |
| `community_a-sample-archaludon-75-wr-vs` | masamikobayashi | Archaludon ex / Cinderace | 75% WR vs a 1300+ Starmie | rule-based | PUBLIC_CLAIM | LOCAL_BENCHMARK_ONLY | BENCHMARK_ONLY |
| `community_rule-based-not-psychic-alaka` | ryotasueyoshi | Alakazam | best 5th place | rule-based | PUBLIC_CLAIM | LOCAL_BENCHMARK_ONLY | BENCHMARK_ONLY |
| `community_strong-start-baseline-agent-` | romanrozen | unspecified | LB 950+ | probabilistic expectimax (search) | PUBLIC_CLAIM | LOCAL_BENCHMARK_ONLY | BENCHMARK_ONLY |

### Why the official samples are the reproduction targets

They are **rich implementations**, not priority tables — `official_dragapult` 853 lines, `official_mega_lucario` 508 lines, `official_mega_abomasnow` 267 lines, `official_iono` 415 lines — carrying planning, prize/resource tracking, damage calculation and matchup rules. §3 forbids replacing exactly this kind of implementation with a smaller static priority table, which is the error c014 and c015 made.


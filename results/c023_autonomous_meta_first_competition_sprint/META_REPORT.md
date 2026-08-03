# META_REPORT — what the ladder is actually playing, and what that changes

Retrieved 2026-08-03 18:20–19:00 Europe/Rome. Every number here comes from a public Kaggle
artifact listed in `SOURCES.md`; nothing is inferred from our own games.

This report exists to change decisions, not to describe a field. The three decisions it changes
are named at the end and each one is carried into a specific file.

## 1. The ladder, and where we sit on it

| quantity | value | source |
|---|---:|---|
| teams | 6,113 | keidroid snapshot 2026-08-01 |
| mean / median rating | 622.8 / 637.8 | keidroid |
| P75 / P90 / P95 / P99 | 755.2 / 836.1 / 903.8 / 1035.6 | keidroid |
| maximum | 1262.2 | keidroid |
| top of leaderboard, 2026-08-03 | 1254.3 | `kaggle competitions leaderboard` |
| **our best submission** — official Dragapult sample | **719.7** | our submissions list |
| our official Mega Lucario sample | 593.3 | our submissions list |
| our c014 Archaludon expert | 471.4 | our submissions list |
| our c015 anti-meta expert | 390.7 | our submissions list |

Two facts follow immediately, and both are load-bearing for this contract.

**The four official sample agents are not the field.** They sit between the 40th and 65th
percentile. A local panel built only from them measures a function whose top is roughly the
ladder's median. That is why this campaign put public community agents on the panel.

**Rating, not win rate, is the separating quantity.** keidroid measured a ~1155-rated agent at a
61.2% win rate over 260 public games — because matchmaking pairs by rating, a strong agent still
plays close games. So a local field score is a *proxy* for placement, never a prediction of it,
and this report never converts one into the other.

## 2. Archetype frequency by score band

From `myso1987/ptcg-ai-battle-leaderboard-deck-meta-by-score-band`, which recovers each team's
60-card list from a public episode replay and aggregates by band (snapshot 2026-08-02).

| band | classified teams | 1st | 2nd | 3rd |
|---|---:|---|---|---|
| **1100+** | 17 | **Marnie Grimmsnarl 58.8%** | Mega Lopunny 11.8% | Teal Mask Ogerpon 11.8% |
| 1000–1099 | 95 | **Marnie Grimmsnarl 61.1%** | Alakazam 9.5% | Crustle Wall 9.5% |
| 900–999 | 228 | **Marnie Grimmsnarl 43.4%** | Alakazam 23.7% | Crustle Wall 10.1% |
| 800–899 | 283 | Alakazam 27.6% | Marnie Grimmsnarl 23.7% | Archaludon 16.3% |
| 700–799 | 290 | Archaludon 27.6% | Alakazam 26.2% | Mega Lucario 15.9% |

The gradient is the point. **Marnie's Grimmsnarl ex rises monotonically with rating and owns
roughly 60% of the top two bands.** Alakazam peaks in the 800s. Archaludon and Mega Lucario are
*lower*-band decks: Mega Lucario is 15.9% at 700–799, 3.9% at 800–999, and absent above 1000.

## 3. Archetype win rate against the field

From `busyaprime/what-actually-wins-on-the-ladder` (snapshot 2026-07-31), which pairs archetypes
from public replays. `exp_vs_field` weights each matchup by that opponent's usage.

| archetype | usage % | win rate | exp. vs field | games |
|---|---:|---:|---:|---:|
| Teal Mask Ogerpon ex | 3.4 | 0.608 | **0.693** | 260 |
| Mega Lopunny ex | 5.0 | 0.642 | **0.621** | 386 |
| **Dragapult ex** | 2.6 | 0.592 | **0.567** | 201 |
| Cynthia's Garchomp ex | 3.7 | 0.558 | 0.546 | 283 |
| Mega Kangaskhan ex | 8.4 | 0.509 | 0.508 | 650 |
| **Marnie's Grimmsnarl ex** | **63.8** | 0.488 | 0.480 | 4,924 |
| Fezandipiti ex | 7.5 | 0.488 | 0.470 | 582 |
| Team Rocket's Mewtwo ex | 3.7 | 0.479 | 0.465 | 288 |

Grimmsnarl is *the field*, so its win rate is pinned near 0.5 by construction; its dominance is
a statement about frequency, not about strength. The interesting column is the head-to-head one:

| deck | vs Marnie's Grimmsnarl | games |
|---|---:|---:|
| Teal Mask Ogerpon ex | **0.872** | 141 |
| Cynthia's Garchomp ex | 0.608 | 194 |
| Mega Lopunny ex | 0.590 | 212 |
| **Dragapult ex** | **0.540** | 126 |
| Mega Kangaskhan ex | 0.515 | 396 |

## 4. What is legally available to build on

`SOURCES.md` settles this: the only **submission-eligible** agent code is the four official
samples. Community kernels are `LOCAL_BENCHMARK_ONLY` — runnable here, never packaged. Deck
lists are configuration and are usable.

Intersecting that constraint with §3:

| official base | its archetype's exp. vs field | its archetype vs the 60% meta deck |
|---|---:|---:|
| **`official_dragapult`** | **0.567 (3rd of 8)** | **0.540** |
| `official_mega_lucario` | not ranked — below the reporting threshold | — |
| `official_iono` | not ranked | — |
| `official_mega_abomasnow` | not ranked | — |

**Dragapult is the only official sample whose archetype has a measured positive expectation
against the current ladder field, and it is already our highest-scoring submission (719.7).**

## 5. The archetype ceiling is an agent ceiling, not a deck ceiling

`makthanithin/pokemon-tcg-ai-battle-1084-5-baseline` is a **Mega Lucario** agent — the same
archetype as our 593.3 sample, and a deck differing from the official list by five counts
(+1 Riolu, +1 Boss's Orders, +1 basic Energy, −2 Poké Pad, −1 Gravity Mountain; identical
sha256 to `prvsiyan`'s independently published list, `2a541d7bf3d9`).

The same 60 cards, played by better logic, reach roughly 1084 where the official sample reaches
593. Whatever the exact attribution between deck and agent, **the headroom above an official
sample is large and is reachable without changing archetype.** This is the single most
encouraging measurement in this report for a contract whose legal bases are the official samples.

## 6. Three decisions this report changes

1. **Base selection.** `official_dragapult` is the presumptive base for the challenger branch,
   on §4 — not `official_mega_lucario`, which prior contracts labelled champion on a panel that
   never ran dragapult as a candidate. The label is not inherited; `champion.json` decides it
   from this contract's own round-robin, and §4 is what breaks a statistical tie.
2. **Panel composition.** The evaluation panel is not the four samples. It includes
   `pub_tetsutani_grimmsnarl` — a 47-vote Grimmsnarl implementation standing in for the 60% of
   the top two bands — three Alakazam implementations for the 800s band, and
   `pub_makthanithin_lucario_1084`. Recorded in `MATCHUP_MATRIX.csv`.
3. **Evaluation weighting.** An unweighted mean over panel opponents treats a Grimmsnarl loss and
   an Iono loss as equally costly. They are not: one is 60% of the field above 1000 and the other
   is an official sample nobody plays. `EXECUTIVE_DECISION.md` reports both the unweighted
   off-mirror field score and a usage-weighted field score using the §2 shares, and a candidate
   that improves only against the unweighted panel is not promoted on that basis alone.

## 7. What this report does not establish

- **The usage shares are a two-day-old third-party snapshot**, recovered from replays by someone
  else's classifier, with 17 classified teams in the 1100+ band. Band-level shares there carry
  large uncertainty and are used only for ordering, never as weights with a claimed precision.
- **Our public agents are implementations, not archetypes.** `pub_tetsutani_grimmsnarl` scoring
  well against a candidate does not mean "Grimmsnarl beats it"; it means that agent does.
- **No replay of our own submissions was mined.** The Kaggle episode-replay API can expose them
  and the tooling exists in the public kernels, but at ~2 s per request it does not fit inside
  this contract's window alongside the experiments that need the same hours.

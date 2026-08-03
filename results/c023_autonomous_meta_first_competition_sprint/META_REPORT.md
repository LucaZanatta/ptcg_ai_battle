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

### And the attribution, measured

`PREDICTIONS.md` P-B registered the prediction before the third cell was run: *the archetype's
headroom is agent, not deck.* All three cells, same dev panel, 1,200 games each, one harness:

| | agent | deck | dev field |
|---|---|---|---:|
| A | official Mega Lucario | its own official list | 0.4687 |
| B | official Mega Lucario | the public tuned list `2a541d7bf3d9` | 0.4875 |
| C | **`makthanithin`** | **the same public tuned list** | **0.5442** |

| effect | size |
|---|---:|
| **deck** (B − A) | **+1.9 points** — inside this panel's ~2.4-point noise floor |
| **agent** (C − B) | **+5.7 points** — three times larger, and outside it |

**P-B confirmed.** Holding the deck fixed and changing only the agent is worth three times what
holding the agent fixed and changing only the deck is worth, and only the agent effect clears the
noise floor.

This is the same conclusion `DECK_CHANGE_LEDGER.md` reaches from the opposite direction — 17 deck
mutations of a *different* archetype, none of them worth anything over 1,200 games each — and it
is what makes the deck branch's negative result a statement about this competition rather than
about Dragapult's list in particular.

It also sets the scale for anything that hopes to be a challenger: **+5.7 points is what a better
agent on identical cards actually bought**, and this contract's registered promotion target of
~+4 points sits just below it.

## 5b. What the ladder actually paired us against — our own replays

Sections 2 and 3 are a third party's aggregation over other people's games. This section is ours.

The Kaggle episode API returns the full replay of every public game a submission played, and a
replay contains **both decks** — each agent's 60-card list is its own first action. So the
champion's real ladder record is recoverable directly. `tools/c023_replays.py` does it: list
episodes, fetch each replay, read both decks, classify the opponent by a signature card, record
the reward, delete the 4 MB file.

**`official_dragapult`, submission 54948560, 83 public episodes:**

| opponent archetype | games | share | our score rate |
|---|---:|---:|---:|
| Alakazam | 19 | 22.9% | **0.737** |
| Mega Lucario | 15 | 18.1% | 0.467 |
| Marnie Grimmsnarl | 10 | 12.0% | 0.400 |
| **Crustle Wall** | 9 | 10.8% | **0.222** |
| unclassified | 7 | 8.4% | 0.857 |
| Dragapult (mirror) | 6 | 7.2% | 1.000 |
| Mega Kangaskhan | 5 | 6.0% | 0.600 |
| Team Rocket Mewtwo | 3 | 3.6% | 0.333 |
| Mega Abomasnow | 3 | 3.6% | 0.333 |
| Archaludon | 2 | 2.4% | 0.500 |
| Mega Froslass | 2 | 2.4% | 1.000 |
| Cynthia Garchomp | 1 | 1.2% | 0.000 |
| Teal Mask Ogerpon | 1 | 1.2% | 1.000 |

### This corrects two things about this campaign's own design

**1. The panel over-weighted Grimmsnarl for our rating band.** Marnie's Grimmsnarl is 58.8% of
the 1100+ band, and this campaign built its dev panel and its `field_ladder_weighted` column
around that. But matchmaking is rating-based, and at *our* rating Grimmsnarl is **12%** of
opponents, behind Alakazam and Mega Lucario. Worse, our panel's Grimmsnarl agent puts us at
**0.250** where the real ladder puts us at **0.400** — so the panel opponent is harder than the
archetype we actually meet. Weighting 60% of the objective onto it was optimising for a band we
do not play in.

**2. The champion's actual worst matchup was not on the panel at all.** **Crustle Wall, 10.8% of
our games, 0.222.** No official sample and no panel agent resembles it.

The mechanism is exact, and it is in the card text rather than in a statistic:

> **Crustle — Mysterious Rock Inn:** *Prevent all damage done to this Pokémon by attacks from your
> opponent's Pokémon {ex}.*

**Dragapult ex is a Pokémon ex, and it is this deck's only real attacker.** Against a Crustle in
the Active Spot, Phantom Dive's 200 damage is zero. The sample knows — `no_damage_dex()` lists
Crustle (345) alongside Drednaw, Milotic ex and Sylveon, and the attack planner scores that target
at zero — but knowing a wall is immune is not the same as having an answer to it. The deck's
non-ex attackers are Dreepy (Bite, 40) and Drakloak (Dragon Headbutt, 70) against 150 HP, and the
agent's promotion logic never deliberately brings either in to attack.

`pub_prvsiyan_crustle_wall` was added to the panel on the strength of this measurement — a public
Tusk/Crustle/Terrakion agent running Crustle ×4 and Dwebble ×4.

### What this section does not claim — and the correction that followed

Eighty-three games, thirteen archetypes: most cells have single-digit counts, so the *shares* are
better measured than the *per-archetype score rates*. Crustle Wall at 0.222 is **2 of 9**. It is
enough to say "look here"; it is not enough to put an interval on it.

**And looking there did not confirm it.** `pub_prvsiyan_crustle_wall` was added to the panel and
the matchup was measured properly — 400 games per candidate, one opponent:

| candidate | vs `pub_prvsiyan_crustle_wall` |
|---|---:|
| `official_dragapult` | **0.7325** |
| `chal_dp_base4` (the same policy, wrapper build) | 0.6725 |
| `pub_makthanithin_lucario_1084` | 0.3125 |
| `official_mega_lucario` | 0.0950 |

**The champion beats this Crustle implementation comfortably.** The ladder's 0.222 was two wins in
nine games, and 400 controlled games put the same matchup near 0.70.

So the planned anti-Crustle branch was **killed before a line of it was written**. Two readings of
why, and they are not exclusive:

- **Nine games is nine games.** A true rate of 0.5 produces 2-or-fewer wins in 9 about 9% of the
  time. This is what a nine-game cell looks like when it is unlucky.
- **"Crustle Wall" is not one agent.** `UNRESOLVED_RISKS.md` R3 warns that one implementation
  standing in for an archetype cuts both ways, and here it cut in our favour: the public
  Tusk/Crustle/Terrakion agent available to us may simply be weaker than whatever we met.

Worth keeping, because it is the reason the archetype *looks* frightening on paper: this deck runs
**Neutralization Zone**, a stadium that prevents all damage to Pokémon without a Rule Box from
attacks by Pokémon ex — and every Pokémon in the list is non-ex. With that stadium down, Dragapult
ex cannot damage anything. The champion's answer is already in its list: Team Rocket's Watchtower,
scored **80000** — the highest number in its play table — whenever any stadium is out. The sample
was built to displace stadiums, and against this deck that is the whole matchup.

**The methodological point is the one to keep.** A 10.8%-share, 0.222-score cell from first-hand
ladder data looked like the campaign's best remaining opportunity, and a 400-game controlled
measurement retired it in eighty seconds. Acting on the nine-game number without measuring it
would have spent the last night of the campaign fixing a matchup we win.

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

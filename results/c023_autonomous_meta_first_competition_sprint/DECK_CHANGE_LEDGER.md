# DECK_CHANGE_LEDGER

**Branch B2 (deck co-optimization) = FAIL. Seventeen constrained mutations of the official
Dragapult list, every one of them collapsing onto the control when measured properly.**

That is the finding, and the way it arrived is as informative as the result.

## The protocol

Every mutation is a count change within the cards the base agent already dispatches on. That
restriction is not conservatism, it is a property of the agent: these samples hard-code card IDs,
and an unrecognised trainer falls through to a generic score of 10000 — *above* every named
Supporter in the list. Adding an unknown card does not add a tool; it adds a card the agent will
play eagerly and wrongly.

Every mutation names the failure or matchup it is meant to correct before it is built
(`decks/mut_dragapult.json`), each deck is checked for legality **by the engine** (a real
`BattleStart`, not a rulebook paraphrase), and each is evaluated with its actual agent.

Screen: 400 games on the dev panel. Confirm: 1,200 games on the dev panel. Both against a control
measured **in the same run**.

## The screen, and why it was wrong

`deck_screen1`, 400 games each, dev panel:

| arm | change | dev field | vs control |
|---|---|---:|---:|
| `d01_rarecandy3_helmet0` | −1 Lucky Helmet, +1 Rare Candy | **0.5575** | **+7.25** |
| `d08_dragapult4_latias0` | −1 Latias ex, +1 Dragapult ex | 0.5400 | +5.50 |
| `d05_nightstretcher3_helmet0` | −1 Lucky Helmet, +1 Night Stretcher | 0.5125 | +2.75 |
| control `chal_dp_base` | — | 0.4850 | — |
| …nine further arms | | 0.4450–0.5000 | −4.0 … +1.5 |

Read alone, d01 is a 7-point improvement with a clean story: Rare Candy is the only route to
Dragapult ex on the turn Dreepy lands and the agent scores that line 40000, while Lucky Helmet is
a singleton it scores 15.

## The confirmation, which is the actual result

`deck_confirm1`, **1,200 games each**, same dev panel, same harness:

| arm | dev field | vs control | screen said |
|---|---:|---:|---:|
| `d08_dragapult4_latias0` | 0.5217 | +1.13 | +5.50 |
| `d15_rarecandy3_dragapult4` | 0.5167 | +0.63 | — (built from the screen) |
| **control `chal_dp_base2`** | **0.5104** | — | — |
| `d01_rarecandy3_helmet0` | 0.5092 | **−0.12** | **+7.25** |
| `d17_rarecandy4_dragapult4` | 0.5033 | −0.71 | — |
| `d16_rarecandy3_budew3` | 0.5033 | −0.71 | — |
| `d05_nightstretcher3_helmet0` | 0.5017 | −0.87 | +2.75 |

**d01 went from +7.25 to −0.12 by adding games.** Nothing changed but the sample size.

## Why the screen produced a winner that did not exist

The noise floor was measured, not assumed. Two runs of the *identical* policy on the same panel:

| run | policy | games | dev field |
|---|---|---:|---:|
| `deck_screen1` | `chal_dp_base` (wrapper, no rules) | 400 | 0.4850 |
| `rule_screen1` | `chal_dp_base2` (wrapper, no rules) | 600 | 0.5166 |

**3.2 points apart with nothing changed.** At 400 games a field score's standard error is about
2.5 points, so across thirteen arms the largest is expected to sit 5–6 points above the control
*under the null*. d01's +7.25 was barely outside that, and it did not survive. This is the
failure the deck-search tool's own documentation warned about — "the winner would be noise with a
rationale attached" — reproduced end to end.

## What this says about the official list

Seventeen single- and double-count changes across every axis a deck-builder would try —
consistency (Rare Candy, Poké Pad, Night Stretcher), attackers (a fourth Dragapult ex), reach
(a fourth Boss's Orders), energy, disruption (Crushing Hammer), tempo defence (a third Budew),
and four combination arms — and **not one produced a measurable gain over 1,200 games.**

The honest reading: **the official Dragapult list is already tuned, and this deck's ceiling is
not in its 60 cards.** That matters for where the remaining hours go, and it is consistent with
the strongest external evidence available — `makthanithin`'s Mega Lucario agent reaches a claimed
1084.5 with a deck differing from its official sample by five counts, while the official sample
with the *same* archetype scores 593.3. The headroom in this competition is in the agent.

## Mutations that were rejected before they cost games

| id | reason |
|---|---|
| `d12_ultraball3_poffin4_dreepy4` | count/size rule: Buddy-Buddy Poffin is already at the four-copy limit |

`mldeck_ml_public_tuned` — the Mega Lucario list two independent public agents converged on
(sha256 `2a541d7bf3d9`, one of them titled with a 1084.5 leaderboard score) — was built as a
complementary-candidate arm on the `official_mega_lucario` base. Deck lists are
`CONFIGURATION_NOT_CODE` and reusable; the agent is not. Its result is recorded in
`EXECUTIVE_DECISION.md`.

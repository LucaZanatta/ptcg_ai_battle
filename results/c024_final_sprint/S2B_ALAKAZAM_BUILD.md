# S2b — building our own Alakazam expert: where it is, measured

Our own policy for the 60-card Alakazam / Dudunsparce list, written from the competition's card
table. No kernel source copied; the decklist is configuration and is public in four notebooks.

**Decision point: 2026-08-11.** If this has not reached **0.55 field** on the eleven-opponent
panel by then it does not get a ladder slot, and the remaining days go to protecting the champion.
Written down now, before the number is known, because the failure mode is discovering on the 15th
that it is four points short and submitting anyway.

## The first thing measured: the shortcut does not exist

Before writing a policy, the cheap question — can a legally-reusable official sample simply pilot
this deck? Four candidates, official base plus the Alakazam list, 60 games each:

| base | field |
|---|---:|
| `official_mega_lucario` | 0.183 |
| `official_mega_abomasnow` | 0.017 |
| `official_iono` | 0.017 |
| `official_dragapult` | 0.017 |

The samples' scoring tables are card-id keyed and entirely deck-specific. There is no shortcut;
the policy has to be written.

## The decision surface, measured before writing it

Six games of the reference agent, by `select.context`:

| context | share |
|---|---:|
| MAIN | 58% |
| TO_HAND (search resolution) | 22% |
| TO_ACTIVE / ACTIVATE / TO_BENCH | 15% |
| everything else (SWITCH, EVOLVE, IS_FIRST, SETUP, SKILL_ORDER, TO_DECK, DRAW_COUNT) | 5% |

Thirteen contexts, 419 of 525 selections exactly-one-of. Tractable.

## Three defects found by measurement, not by reading

Each was found by comparing a mechanism metric against `pub_romanrozen_v10_950` on the same deck —
the diagnostic a mirror-deck reference makes possible and a field score never would.

**1. Options scored by the card spent, ignoring the card played *on*.**
`EVOLVE` and `ATTACH` options carry the target in `inPlayArea`/`inPlayIndex`. Scoring only the
hand card meant evolving a benched Abra while the Active stayed a Dunsparce, and spending the
turn's single energy attach on a bench slot. The symptom was precise: our hand at attack matched
the reference **exactly** (9.50 against 9.51) while ATTACK was available in **13.5** decisions a
game against their **25.6**. Same hand, half the attacker uptime.

**2. Promotion order optimised for HP instead of for attacking.**
Dudunsparce is the 140 HP body and looks like the safe promote. Land Crush costs three energy in
a deck holding six, and its retreat is three: promoting it parks the Active on something that can
neither attack nor leave. Our Active was a Dudunsparce or a Dunsparce in 33% of decisions.

**3. The wrong supporter, every time.**
Dawn fetches three cards (net +2) and Hilda fetches two (net +1) — so Dawn outscored Hilda
unconditionally. But Hilda is the only supporter in the list that can find an **Energy**, and this
deck holds six energy in sixty cards with one attach per turn. Measured: we held 0.42 energy per
decision against their 0.72, our Active had no energy in **67%** of decisions against their 53%,
and an attack was available in **27%** against their 47%.

## After the fixes, the mechanism metrics have inverted

Ten games each against `official_dragapult`, same harness:

| | ours | reference | |
|---|---:|---:|---|
| attack available | **58%** | 50% | of MAIN decisions |
| Active with no energy | **38%** | 47% | lower is better |
| hand size at MAIN | 10.08 | 10.29 | |
| hand at attack | 10.83 | 9.51 | 217 vs 190 damage |
| attacks per game | 4.0 | 4.6 | |
| attack mix | 70% Powerful Hand | 67% | |

**On every metric the policy was written to control, it now matches or beats the agent it is
being measured against.**

## And the field score has not moved

| version | change | field (vs dragapult / romanrozen / grimmsnarl / jazivxt) |
|---|---|---:|
| v1 | first working policy | 0.150 |
| v2 | target-aware evolve and attach | 0.200 |
| v3 | promotion order | 0.153 |
| v4 | energy-aware supporters | **0.1875** |

Against the reference agent's **0.6197** and our champion's **0.4967** on the same panel. The
first three steps are inside the campaign's 2.4-point noise floor; only the v1→v2 move is
plausibly real.

## What the gap actually is now, measured

| per game, vs `official_dragapult` | ours | reference |
|---|---:|---:|
| attacks | 4.0 | 4.6 |
| **prizes taken** | **1.90** | **3.50** |
| prizes conceded | 2.80 | 2.90 |
| turns | 10.6 | 11.6 |

**Same attack count, same attack mix, same hand size, same prizes conceded — and we take 1.9
prizes to their 3.5.** The deficit is not tempo, not resources and not damage output. It is
*conversion*: our attacks are not turning into knockouts.

That is the next and only target. The candidate mechanisms, in order of how cheaply they can be
tested: which target the damage is aimed at (Powerful Hand hits the Active, so target choice is
made by Boss's Orders and by whether we finish a damaged Pokémon before it can be switched out);
whether a 200-damage attack into a fresh 320 HP body is being repeated instead of concentrated;
and the off-by-one in the Boss's Orders gate, which tests lethality against the hand size *before*
paying the card that shrinks it.

# Anti-meta thesis coherence and complementarity audit (§13)

**90 games audited, 8,811 decisions sampled** — §13 requires at least 60 decisions with at
least 20 opportunities per mechanism. Both bars are cleared by a wide margin.

## The falsifier fired

I registered this before any game was run, in `ANTI_META_SELECTION.md`:

> The thesis is **falsified** if the agent fails to exceed a **0.60 score rate against the exact
> c014 public-meta-v0 package** while its decision traces show Electric Streamer executed on at
> least **60% of turns** where a Basic {L} Energy was in hand.

| half of the falsifier | required | measured | verdict |
|---|---|---|---|
| score rate vs the c014 target | > 0.60 | **0.36** (n=100) | **FAILED** |
| Mechanism A execution when available | ≥ 0.60 | **1.000** (1206/1206) | passed |

**The thesis is falsified, and it is falsified in the informative direction.** The mechanisms are
not merely present — they execute on *every single* occasion they are available — and the matchup
is still lost. So the failure is not "the agent cannot run the plan". It is that the plan, as
executed by this v0, does not beat the target.

I am not moving the bar. The 0.60 threshold was chosen before the games and it stands.

## Measured

| metric | value |
|---|---|
| setup success rate | 0.933 |
| engine online (Bellibolt ex in play) | 0.789 |
| **Mechanism A — Electric Streamer, execution when available** | **1.000** (1206/1206) |
| **Mechanism B — Voltaic Chain, execution when attacking and legal** | **1.000** |
| attachment-to-engine rate | 1.000 |
| fallback rate | 0.0028 |
| invalid selections / exceptions / timeouts | 0 / 0 / 0 |

### Score rate by opponent

| opponent | role | score rate |
|---|---|---|
| `__c014__` (exact c014 package) | **the target** | **0.36** |
| `__safe__` | deterministic control | 0.61 |
| `__self__` | plumbing only | 0.45 |
| mega_lucario | **predicted difficult matchup** | **0.20** |
| mega_abomasnow | official baseline | 0.12 |
| dragapult | frozen control | 0.04 |

## The pre-registered matchup prediction was correct

`ANTI_META_SELECTION.md` predicted, before any game: *"Fighting ({F}). Every Iono's Pokémon in
this list is weak to {F}. Mega Lucario ex is the {F} baseline on the panel, so this prediction is
directly testable."*

Measured: **0.20 against Mega Lucario**, the second-worst matchup on the panel. The card-level
reasoning that produced the prediction was sound even though the headline thesis was not.

## Complementarity — reported honestly, not favourably

The deck-level counter is real, and it is not what this agent achieved:

| agent playing the Iono deck | score rate vs the Archaludon deck |
|---|---|
| the **official** Iono sample agent (c014's measurement, 100 games) | **0.98** |
| **this c015 v0 expert** (100 games) | **0.36** |

Same deck, same target. The gap is entirely implementation quality. That is the single most
useful number in this report: it separates "the counter does not exist" from "my expert does not
realise it", and the evidence says the second.

A second caveat that cuts against over-reading any of this: **c014 scored 754.5 on the public
ladder while scoring 0.020 against this deck locally.** A four-agent local panel is not the
ladder. No claim is made that beating — or losing to — c014 locally predicts a public score.

## Top three loss categories

1. **dragapult** — 96 losses. Spread pressure outpaces the setup turns the engine needs.
2. **mega_abomasnow** — 88 losses. A 350 HP body races the deck before Voltaic Chain scales.
3. **mega_lucario** — 80 losses. The predicted {F} weakness.

All three share one cause, which is the next loss mode.

## The single next loss mode (§13 requires exactly one)

> **The engine comes online, but the damage arrives too late.** Thunderous Bolt cannot attack on
> consecutive turns, and Voltaic Chain only reaches competitive damage once several {L} are
> already in play, so the deck spends its early turns developing while the opponent scores.

Chosen because it is the only measurement that explains a **1.000** mechanism-execution rate
coexisting with a **0.36** score rate. Every other observed weakness is downstream of arriving
late: the {F} weakness matters because Lucario is fast, and the Dragapult and Abomasnow losses
are both races lost before the scaling attack becomes large.

## What passes and what does not

Per §13, thesis coherence asks whether *"the mechanics are present in the deck, implemented in
the rules, and visibly executed in sampled games"*. All three hold: the cards exist, the rules
are named functions, and both mechanisms fire at 1.000 when available. **Coherence passes.**

The **thesis falsifier fails**. Those are different claims and both are reported.

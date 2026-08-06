# Strategy coherence audit (§12)

**80 games audited, 3,785 decisions sampled** — §12 requires at least 50.

The question §12 asks is not "is the agent strong" but "is the stated thesis visibly executed in
actual games". It is.

## Measured

| metric | value | reading |
|---|---|---|
| setup success rate | **1.000** | Duraludon — the evolution base the whole plan depends on — reached play in every audited game |
| intended attacker prepared rate | **0.838** | Archaludon ex reached play in 84% of games |
| attacker reached full energy ({M}{M}{M}) | **0.625** | *Metal Defender* was powered in 63% of games |
| thesis attack share | **0.752** | Archaludon ex delivered 261 of 347 attacks |
| attacks by attacker | Archaludon ex 261, Duraludon 83, Cinderace 3 | the intended attacker does the attacking |
| empty-bench decisions per game | **10.14** | the deck's structural weakness, discussed below |
| fallback decisions | **0** (rate 0.00000) | no decision in 3,785 fell through to the legal fallback |
| illegal/invalid selections | **0** | across all 600 direct + 150 package games |

## Is the thesis present in gameplay?

Yes, on every clause of it:

- *"evolve into Archaludon ex"* — 83.8% of games, from a 100% setup rate.
- *"win the damage race with a 220-damage attack"* — Archaludon ex is 75.2% of all attacks.
- *"which recovers two more {M} from the discard"* — the discard-banking rule fires as designed;
  62.5% of games reach the full {M}{M}{M} needed for *Metal Defender*.

The one clause that does **not** reliably execute is the opener: Cinderace attacked 3 times in
347. That is the loss mode selected below.

## Fallback frequency and reasons

Zero. Every one of the 3,785 sampled decisions was resolved by a named rule
(`main_play`, `main_attach`, `main_evolve`, `search`, `promote`, `discard_bank_energy`,
`attach_to_intended_attacker`, `setup_active`, `forced`, …). The deterministic fallback exists
and is tested, but was never needed — so no decision was silently uninterpretable.

## Top three observed loss categories

| rank | category | evidence |
|---|---|---|
| 1 | **Disruption (Iono)** — 98 losses, the worst matchup | hand disruption strands the deck's 5-Basic-Pokémon shell |
| 2 | **Spread setup (Dragapult)** — 91 losses | pressures the bench while Duraludon waits to evolve |
| 3 | **Linear aggro (Abomasnow)** — 65 losses | races the deck before {M}{M}{M} is assembled |

All three share one cause: the deck is slow to assemble energy.

## Bench liability — reported, not hidden

10.14 decisions per game occur with an empty bench, where a knockout loses immediately. This
deck runs only **5 Basic Pokémon in 60 cards**, so the state is structural. A liability rule
(any benchable Pokémon outranks every non-evolution play while the bench is empty) reduced it
from 12.4, which is an improvement but not a fix. The honest statement is that the rule mitigates
a deck-construction property it cannot remove.

## The single next loss mode (§12 requires exactly one)

> **Cinderace's *Explosiveness* opener is available in only a minority of games**, so *Turbo
> Flare* — the deck's only energy accelerator, attaching 3 Basic Energy to the bench in one
> action — is usually absent, and the deck must reach {M}{M}{M} through one manual attachment
> per turn.

It is chosen over the bench-liability and matchup categories because it is **upstream of all of
them**: slow energy is what keeps Duraludon on the bench long enough to be pressured, what
leaves the bench thin, and what lengthens the evolve-turn window in which Archaludon ex still
has its Fire weakness. Fixing the opener plausibly moves all three; fixing any of the three does
not move the opener.

## What this audit does not claim

Score rate against the local panel is 0.348 (direct) and 0.207 (extracted package, which faces
only the four real opponents with no controls diluting it). §11 is explicit that strength here is
diagnostic and does not gate submission, and no claim is made that v0 is competitive. It is a
legal, deterministic, coherent baseline with one measured thing to fix.

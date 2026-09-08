# The two counter mechanisms (§11)

Both are implemented as named functions in `tools/c015_iono_expert.py`, so the claim "the
mechanisms are in the rule code" is checkable by reading two functions rather than by trusting
prose.

## Mechanism A — Electric Streamer: unlimited attachment

**Card:** Iono's Bellibolt ex (280 HP {L}, Stage 1 from Iono's Tadbulb)
**Ability text:** "As often as you like during your turn, you may attach a Basic {L} Energy card
from your hand to 1 of your Iono's Pokémon."
**Fuel:** 22 Basic {L} Energy in a 60-card deck.

**Implementation:** `_mechanism_a_electric_streamer(res)` reports availability (a Basic {L} in
hand **and** Bellibolt ex in play). In `_main`, an `ABILITY` option is scored **1000** — above
every other action in the deck — because the ability may be used repeatedly and does not end the
turn.

**Why it counters the target.** The Archaludon metal-tempo deck attaches **once per turn**, and
c014's own selected next loss mode states it "must reach {M}{M}{M} through one manual attachment
per turn" because its accelerator is rarely available. The target is on a clock; this deck is not.

## Mechanism B — Voltaic Chain: damage scaling off the stockpile

**Card:** Iono's Voltorb (70 HP {L}, Basic)
**Attack text:** "20 damage. This attack does 20 more damage for each {L} Energy attached to
**all** of your Iono's Pokémon."

**Implementation:** `_mechanism_b_voltaic_chain_damage(me)` returns `20 + 20 × (total {L} across
active and bench)`. This computation is **required**, not decorative: the engine reports this
attack's static `damage` field as 20, so a naive max-damage comparison ranks it below a
30-damage Tiny Charge forever. The scaled value is substituted when Voltorb is the active
Pokémon, both in `_attack` and — after a smoke run measured **zero** Mechanism B opportunities —
inside `_main`, because the engine presents each legal attack as its own MAIN option rather than
through a separate attack context.

**Why it counters the target.** Mechanism A is Mechanism B's input. Every energy A places
anywhere on the board raises B's damage, so each turn the target spends assembling {M}{M}{M}
increases the damage aimed at it. Five {L} in play is 120; ten is 220.

## How the two are coupled

They are not two independent good cards. A is only worth its top priority because B converts a
stockpile into damage, and B is only strong because A fills the board faster than a
one-attachment-per-turn deck can answer. Measuring them separately is still correct — a high A
rate with a low B rate would mean the deck is hoarding energy it never spends.

## Supporting cards that make the pair repeatable

| card | role |
|---|---|
| **Levincia** (stadium) | returns up to 2 Basic {L} from discard to hand **each turn** — refuels A |
| **Max Rod** | up to 5 Pokémon/Basic Energy from discard to hand |
| **Energy Retrieval** | 2 Basic Energy from discard to hand |
| **Iono's Kilowattrel** — *Flashing Draw* | discard a {L} from itself to draw |
| **Buddy-Buddy Poffin** | 2 Basic Pokémon with ≤70 HP straight onto the bench |
| **Canari** | discard 1, search up to 4 {L} Pokémon |

## Minimal opponent inference (§11 allows only what the thesis needs)

`_target_metal_line_present(op)` reports three booleans: whether the metal-tempo line is on the
board at all, whether an **un-evolved Duraludon** is present, and whether Archaludon ex has
arrived. Nothing else about the opponent is modelled. This is the inference the thesis needs —
Duraludon is 130 HP and must sit on the bench while it waits to evolve — and no more.

## What the mechanisms do **not** claim

Neither mechanism gives a type advantage: Archaludon ex is weak to {R} Fire, and this deck is
{L} Lightning. The counter is structural (tempo and scaling), not elemental. The elemental
counter was the c014 provisional thesis and it was rejected because no exact legal Fire deck
list exists in any captured public source.

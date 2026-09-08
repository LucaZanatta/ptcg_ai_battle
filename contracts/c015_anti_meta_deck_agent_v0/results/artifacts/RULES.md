# Iono's Bellibolt ex — deterministic anti-meta expert rules

Implemented in `tools/c015_iono_expert.py`. Priority tables evaluated against visible state; no
search, no sampling, no learned component. Same state → same selection.

Card IDs are internal; every one is named here (§11).

| ID | name | role |
|---|---|---|
| 4 | Basic {L} Energy | 22 copies — fuel for Mechanism A |
| 269 | Iono's Bellibolt ex | 280 HP Stage 1 — *Electric Streamer* (**Mechanism A**), *Thunderous Bolt* 230 |
| 268 | Iono's Tadbulb | 60 HP Basic — evolves into Bellibolt ex |
| 265 | Iono's Voltorb | 70 HP Basic — *Voltaic Chain* (**Mechanism B**) |
| 270 / 271 | Iono's Wattrel / Kilowattrel | 60/120 HP — *Flashing Draw* draw engine, *Mach Bolt* 70 |
| 1254 | Levincia (stadium) | 2 Basic {L} from discard to hand each turn |
| 1086 | Buddy-Buddy Poffin | 2 Basic Pokémon ≤70 HP onto the bench |
| 1233 | Canari | discard 1, search up to 4 {L} Pokémon |
| 1227 | Lillie's Determination | shuffle hand, draw 6 (8 at 6 prizes) |
| 1121 / 1152 | Ultra Ball / Poké Pad | search |
| 1097 / 1110 / 1118 | Night Stretcher / Max Rod / Energy Retrieval | discard recovery |

## Decision categories

### 1. Opening setup — active and bench

`SETUP_ACTIVE_POKEMON`: **Tadbulb → Voltorb → Wattrel.** Tadbulb leads so the Active Spot becomes
a 280 HP Bellibolt ex rather than a 70 HP Voltorb. Measured during development against the c014
target, 20 games per arm, **before** the final panel was run: Voltorb-first **0.250**,
Tadbulb-first **0.400**.

`SETUP_BENCH` / `TO_BENCH`: **Tadbulb → Voltorb → Wattrel.**

### 2. Bench space and liability

An empty bench loses outright on a knockout. While the bench is empty, playing any of the deck's
Pokémon scores **950**, above every development play and below only the Bellibolt evolution.

### 3. Turn-order and card-play priority (`MAIN`)

| score | action | reason |
|---|---|---|
| **1000** | ABILITY — *Electric Streamer* | **Mechanism A**: usable as often as you like, never ends the turn |
| 960 | EVOLVE → Bellibolt ex | the 280 HP body *and* the engine that grants Mechanism A |
| 950 | play any Pokémon while bench is empty | liability rule |
| 900 | ATTACH energy (if not yet attached) | the once-per-turn manual attachment, on top of A |
| 880 | Buddy-Buddy Poffin | two Basics onto the bench in one card |
| 860 | Canari | searches up to 4 {L} Pokémon |
| 850 | play Tadbulb | the Bellibolt line |
| 840 | Levincia (if no stadium) | refuels Mechanism A every turn |
| 830 | play Voltorb | the Mechanism B attacker |
| 800–700 | Ultra Ball, Night Stretcher, Max Rod, Energy Retrieval, Lillie's Determination, Poké Pad | search and recovery |
| 700 | EVOLVE (other) | Kilowattrel |
| **400 + min(99, dmg/5)** | ATTACK | attacks **end the turn**, so they rank below every developing play while still ordering among themselves by *true* damage |
| 50 | RETREAT | rarely correct |
| 1 | END | last resort |

Ties resolve to the lowest option index.

### 4. Search-target priority (`TO_HAND`)

**Tadbulb → Bellibolt ex → Voltorb → Basic {L} → Wattrel → Kilowattrel → Levincia →
Buddy-Buddy Poffin → Canari → Lillie's Determination → Ultra Ball → Night Stretcher → Max Rod →
Energy Retrieval → Poké Pad.**

Options referencing the **deck** (`area = 1`) are not resolvable from visible state — the player
object exposes `deckCount`, not contents — and are taken deterministically at the lowest index
rather than guessed. Options in the revealed `looking` zone (`area = 12`) are fully prioritised.

### 5. Evolution ordering

Bellibolt ex scores 960; any other evolution 700. Bellibolt is both the durable body and the
Mechanism A engine, so it is never deprioritised behind Kilowattrel.

### 6. Discard selection

**Never discard the engine or its fuel.** Order: Poké Pad → Energy Retrieval → Max Rod → Night
Stretcher → Ultra Ball → Buddy-Buddy Poffin → Canari → Lillie's Determination → Levincia →
Wattrel → Kilowattrel → Voltorb → Basic {L} Energy → Tadbulb → **Bellibolt ex last**.

This is the mirror image of c014's rule, and deliberately so: the Archaludon deck *wants* energy
in the discard because Assemble Alloy recovers it, while this deck wants energy **in hand** where
Electric Streamer can attach it.

### 7. Attachment target (`ATTACH_TO` / `ATTACH_FROM`)

Target order **Bellibolt ex → Voltorb → Tadbulb → Kilowattrel → Wattrel**: Bellibolt first
because it is simultaneously the engine and the body that must survive; every attachment anywhere
still feeds Mechanism B's board-wide count. Source order: Basic {L} Energy.

### 8. Attack selection

True damage, not the static field. Voltaic Chain's static `damage` is 20; the expert substitutes
`20 + 20 × total {L} in play` when Voltorb is active. Thunderous Bolt (230) wins when Bellibolt
is active, with the card's own restriction — it cannot attack on the following turn — making
Voltaic Chain the natural filler.

### 9. Target selection

Handled through the same option-priority path. The minimal opponent inference
(`_target_metal_line_present`) reports whether an un-evolved Duraludon is on the board, which is
the target's documented vulnerable window.

### 10. Promotion after a knockout

**Bellibolt ex → Kilowattrel → Voltorb → Tadbulb → Wattrel** — the largest body that can attack.

### 11. Forced and multi-select handling

A single legal option with `minCount ≥ 1` is taken immediately and recorded as `forced`.
Multi-select applies the priority order, then repairs the selection into `[minCount, maxCount]`,
de-duplicated and range-checked.

### 12. Prize / resource / opponent tracking

Emitted on every decision: turn, prizes both sides, hand size, **{L} in hand**, **{L} in
discard**, **total {L} in play** (Mechanism B's input), the computed Voltaic Chain damage,
whether Bellibolt and Voltorb are in play, bench count and max, stadium, supporter/energy spent,
and the three target-archetype booleans.

### 13. Deterministic fallback

Unknown context, malformed state, or internal exception → the first `minCount` legal options.
Always legal, never random, and the reason is recorded and reported rather than absorbed.

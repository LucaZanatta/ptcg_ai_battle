# Archaludon ex / Cinderace — deterministic expert rules

Implemented in `tools/c014_archaludon_expert.py`. Every rule is a priority table evaluated
against the visible state; there is no search, no sampling, and no learned component. The same
state always yields the same selection.

Card IDs are used internally because the engine speaks IDs. Every ID is named here (§10).

| ID | name | role |
|---|---|---|
| 169 | Duraludon | Basic {M}, 130 HP — the evolution base |
| 190 | Archaludon ex | Stage 1 from Duraludon, 300 HP {M} — the win condition |
| 666 | Cinderace | Stage 2 {R}, 160 HP — setup opener via *Explosiveness*, energy engine via *Turbo Flare* |
| 57 | Relicanth | Basic {F}, 100 HP — *Memory Dive* |
| 8 | Basic {M} Energy | 11 copies — the only energy the attacker uses |
| 1159 | Hero's Cape | ACE SPEC — +100 HP |
| 1244 | Full Metal Lab | Stadium — {M} Pokémon take 30 less damage |
| 1121 | Ultra Ball | search; its discard cost banks {M} for *Assemble Alloy* |
| 1097 | Night Stretcher | recover from discard |
| 1182 | Boss's Orders | gust a benched Pokémon into the Active Spot |
| 1185 / 1227 | Explorer's Guidance / Lillie's Determination | draw Supporters |
| 1122 / 1152 / 1147 | Pokégear 3.0 / Poké Pad / Jumbo Ice Cream | Items |

## Decision categories

### 1. Initial setup — active and bench

`SETUP_ACTIVE_POKEMON`: **Cinderace → Duraludon → Relicanth.** Cinderace is preferred because
*Explosiveness* ("if this Pokémon is in your hand when you are setting up to play, you may put it
face down in the Active Spot") is the only way it ever enters play — it is a Stage 2 and the deck
contains no Raboot — and because its attack is the deck's energy engine.

`SETUP_BENCH_POKEMON` / `TO_BENCH`: **Duraludon → Relicanth → Cinderace.** Duraludon is what
becomes the win condition.

### 2. Bench space and liability

An empty bench loses the game outright when the Active Pokémon is knocked out. This deck runs
only **5 Basic Pokémon in 60 cards**, so that state is common, not exotic — measured at 12.4
decisions per game before this rule existed. **While the bench is empty, playing any benchable
Pokémon outranks every action except evolving into Archaludon ex.**

### 3. Turn-order and card-play priority (`MAIN`)

Scores are absolute so the ordering is inspectable:

| score | action | reason |
|---|---|---|
| 1000 | EVOLVE → Archaludon ex | *Assemble Alloy* attaches 2 Basic {M} from the **discard**, so evolving is also an energy gain |
| 950 | play any Pokémon **while bench is empty** | liability rule above |
| 900 | ABILITY | abilities are free value |
| 880 | ATTACH energy | once per turn, does **not** end the turn, and *Metal Defender* needs {M}{M}{M} |
| 850 | play Duraludon | more bases = more Archaludon |
| 820 | Full Metal Lab (if no stadium in play) | −30 to every {M} Pokémon |
| 810 | Hero's Cape | +100 HP on a 300 HP body |
| 800 | Ultra Ball | its discard cost is a *gain* — see rule 6 |
| 780 | Night Stretcher | recovery |
| 760 / 750 / 740 | Explorer's Guidance / Lillie's Determination / Boss's Orders | Supporters, only if none played this turn |
| 700–680 | Pokégear / Poké Pad / Jumbo Ice Cream | Items |
| 500 | ATTACK | attacking **ends the turn**, so every non-terminal play is deliberately ranked above it |
| 50 | RETREAT | costs energy this deck cannot spare |
| 1 | END | last resort |

Ties resolve to the lowest option index, so the policy is order-stable.

> An earlier revision scored ATTACH at 600 — below most card plays. The agent emptied its hand
> every turn, never attached energy, and therefore never attacked at all. That is why attachment
> now sits above every play except the evolution.

### 4. Search-target priority (`TO_HAND`)

**Duraludon → Archaludon ex → Basic {M} Energy → Full Metal Lab → Hero's Cape → Boss's Orders →
Ultra Ball → Night Stretcher → draw Supporters → Items → Cinderace → Relicanth.**

Search options that reference the **deck** (`area = 1`) are not resolvable from visible state —
the player object exposes `deckCount`, not deck contents. Those are taken deterministically at
the lowest index and are *not* counted as informed choices. Options that reference the revealed
`looking` zone (`area = 12`) are fully resolved and prioritised. This boundary is deliberate:
inferring hidden deck order would violate §11's no-hidden-information gate.

### 5. Evolution ordering

Evolving into Archaludon ex is the highest-scoring action in the deck (1000). Any other
evolution scores 400. There is no second evolution line.

### 6. Discard selection (`DISCARD`, `DISCARD_ENERGY`) — deck-specific inversion

**Basic {M} Energy is discarded first, by design.** *Assemble Alloy* pulls 2 Basic {M} back out
of the discard pile when Archaludon ex evolves, so energy in the discard is **banked, not lost**.
The full order is: Basic {M} Energy → Poké Pad → Jumbo Ice Cream → Pokégear → draw Supporters →
Ultra Ball → Night Stretcher → Relicanth → Full Metal Lab → Hero's Cape → Boss's Orders →
Cinderace → Archaludon ex → **Duraludon last** (never discard the evolution base).

### 7. Attachment target and energy conservation (`ATTACH_TO` / `ATTACH_FROM`)

Target order **Archaludon ex → Duraludon → Cinderace → Relicanth**: energy goes to the intended
attacker, or to the Duraludon that becomes it. Source order **Basic {M} Energy → Hero's Cape**.

### 8. Attack selection

Highest damage among legal attacks. In practice this resolves to *Metal Defender* (220,
{M}{M}{M}) whenever it is available, and *Turbo Flare* (50, one colourless, attaches 3 Basic
Energy to the bench) while building. *Metal Defender* additionally suppresses Archaludon ex's own
{R} weakness during the opponent's next turn.

### 9. Target selection

Handled through the same option-priority path; `Boss's Orders` is scored as a Supporter play so
the gust is available when it is the highest-value legal action.

### 10. Promotion after a knockout (`SWITCH` / `TO_ACTIVE`)

**Archaludon ex → Duraludon → Cinderace → Relicanth** — the largest body that can still attack.

### 11. Forced and multi-select handling

A single legal option with `minCount ≥ 1` is taken immediately and recorded as `forced`. For
multi-select the priority order is applied and the selection is then repaired into
`[minCount, maxCount]`, de-duplicated and range-checked before it is returned.

### 12. Deck-required prize/resource tracking

Tracked each decision and emitted in the decision trace: turn, prizes remaining on both sides,
hand size, **{M} energy in hand**, **{M} energy in the discard** (*Assemble Alloy* fuel), whether
Archaludon ex and Duraludon are in play, bench count and bench maximum, stadium in play, whether
the Supporter and the energy attachment for the turn are already spent, the identity of the
intended attacker and how much {M} is on it.

### 13. Deterministic fallback

Any unknown context, malformed state, or internal exception falls back to the first `minCount`
legal options — always legal, never random. The fallback records its reason, and the reasons are
reported in `strategy_coherence.json` rather than silently absorbed.

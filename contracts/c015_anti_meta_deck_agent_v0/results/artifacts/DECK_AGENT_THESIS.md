# Anti-meta selection (§10)

**Target archetype:** Archaludon ex / Cinderace metal tempo — the lane c014 selected as the
rising public archetype, and the one c015 must beat.

**Selected anti-meta deck:** Iono's Bellibolt ex — Lightning tempo/disruption.
Deck SHA-256 `bb264cca591df66a505b825c819557580606308dca2cee687c027164026bea55`
(60 cards, 15 distinct), **distinct from c014's**
`42165967b565dd42ec426ecccfe79bfa7d72aa8306590e149dface0ee8bd530e`, and not Dragapult.

## The thesis, in the required form

> This deck should beat **Archaludon ex metal tempo** because **Electric Streamer attaches
> unlimited Basic {L} Energy from hand every turn, against a target that can attach only once
> per turn**, and because **Voltaic Chain converts that stockpile directly into damage, scaling
> by +20 for every {L} Energy attached across all of my Iono's Pokémon**, while covering c014's
> weakness to **disruption/tempo decks that punish its slow energy assembly**.

## Candidates compared (§10 requires the c014 provisional plus at least one alternative)

| dimension | **Iono's Bellibolt ex** (selected) | c014 provisional: Fire attacker | Mega Abomasnow ex | Alakazam (public list) |
|---|---|---|---|---|
| exact legal deck list | **yes** — official sample, hash-verified, 60 cards | **no** — no exact Fire list exists in any captured source | yes | yes |
| measured evidence vs the target | **strongest available: c014 scored 0.020 against this deck over 100 games** | none — cannot be played | 0.350 | none |
| counter mechanism specificity | two concrete, card-level mechanisms (below) | type advantage only ({R} beats {M}) | none specific | none specific |
| automation friendliness | 15 distinct, one main line | n/a | 9 distinct (best) | 23 distinct, Stage 2 (worst) |
| materially different from c014 | yes — {L} tempo vs {M} evolution ramp | yes | yes | yes |
| implementation risk in one day | low | **blocking** | low | high |

**The c014 provisional candidate is rejected for exactly the reason Starmie was rejected in
c014: no exact legal deck list exists.** The Fire thesis was sound on card data — Archaludon ex
is weak to {R} — but c015 will not invent a 60-card list to pursue it, because a deck that is not
publicly evidenced makes the result unattributable. This is the same standard applied twice, and
applying it here costs us the more elegant thesis.

**Mega Abomasnow is the runner-up** and is more automation-friendly (9 distinct cards), but c014
scored 0.350 against it versus 0.020 against Iono — an order of magnitude weaker as a counter.

## The two counter mechanisms, at card level

### Mechanism A — Electric Streamer: unlimited energy attachment

**Iono's Bellibolt ex** (280 HP {L}, Stage 1 from Iono's Tadbulb) has the ability:

> *Electric Streamer*: "As often as you like during your turn, you may attach a Basic {L} Energy
> card from your hand to 1 of your Iono's Pokémon."

The deck runs **22 Basic {L} Energy** to feed it.

This attacks the target's measured weakness precisely. c014's own selected next loss mode reads:
*"the deck must reach {M}{M}{M} through one manual attachment per turn"* because Cinderace's
Turbo Flare accelerator is rarely available. The target is on a one-attachment-per-turn clock;
this deck is on no clock at all.

### Mechanism B — Voltaic Chain: damage that scales with the stockpile

**Iono's Voltorb** — *Voltaic Chain*: "20 damage. This attack does 20 more damage for each {L}
Energy attached to **all of your Iono's Pokémon**."

Mechanism A is the input to Mechanism B: every energy attached anywhere on the board raises this
attack's damage. Five energy in play is 120; ten is 220. The target needs three turns to assemble
one attacker, and each of those turns increases the damage aimed at it.

Supporting cards make the pair repeatable rather than one-shot: **Levincia** (stadium) returns
2 Basic {L} from discard to hand each turn, **Max Rod** returns up to 5 Pokémon/Energy,
**Energy Retrieval** returns 2, and **Iono's Kilowattrel**'s *Flashing Draw* converts a spare
{L} into cards.

Secondary line: **Thunderous Bolt** (Bellibolt ex) does 230 but cannot attack on the following
turn — a closing move, not the engine, and the rules treat it as such.

## Expected complementarity with c014

c014's measured weakest matchups were `iono` (0.020) and `dragapult` (0.090). c015 **is** the
archetype c014 could not beat, so the portfolio gains coverage of the lane that beat it rather
than a second entry in the lane it already occupies.

Stated with the caveat it deserves: c014 scored **754.5** on the public ladder despite scoring
0.020 against this deck locally. The four-agent local panel is therefore **not** representative
of the ladder, and no claim is made that beating c014 locally predicts a higher public score.

## Expected difficult matchup

**Fighting ({F}).** Every Iono's Pokémon in this list — Voltorb, Tadbulb, Bellibolt ex — is weak
to {F}. Mega Lucario ex is the {F} baseline on the panel, so this prediction is directly
testable, and it is recorded before the games are run.

## Explicit falsifier (§10)

> The thesis is **falsified** if, on the untouched final panel, the c015 agent fails to exceed a
> **0.60 score rate against the exact c014 public-meta-v0 package** while its decision traces
> show Electric Streamer executed on at least **60% of turns where a Basic {L} Energy was in
> hand**.

The two halves matter separately: if the mechanisms fire but the matchup is not won, the thesis
is wrong about *why* Iono beats metal tempo; if the mechanisms do not fire, the implementation is
wrong and the thesis is untested.

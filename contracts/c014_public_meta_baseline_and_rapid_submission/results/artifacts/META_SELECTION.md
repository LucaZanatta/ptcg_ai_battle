# Deck-agent selection (§9)

**Selected: Archaludon ex / Cinderace metal tempo.** Not Dragapult.

Deck SHA-256 `42165967b565dd42ec426ecccfe79bfa7d72aa8306590e149dface0ee8bd530e` (60 cards,
15 distinct), frozen at `selected_deck.csv`.

## One-sentence branch thesis

> Open with Cinderace in the Active Spot to attack for 50 while it loads three Basic Energy onto
> a benched Duraludon, then evolve into Archaludon ex — which recovers two more {M} from the
> discard as it evolves — and win the damage race with a 220-damage attack that also cancels
> its own Fire weakness.

## Candidates compared

| dimension | **Archaludon ex / Cinderace** | Starmie | Alakazam / Dunsparce | Mega Lucario ex (in-repo) |
|---|---|---|---|---|
| 1. current public evidence | **Strongest.** 06-29 snapshot (updated 2026-07-26, today): "Archaludon rose sharply in field share while keeping one of the strongest score rates," scoring above 60%. Public rule-based agent reports 75% WR vs a 1300+ Starmie | Strong *reported*: 18-July snapshot puts the leading Starmie list at +198.7 schedule-adjusted strength, 69.3% vs high-strength opponents | Field centre 35.7–46.4% share but a near-neutral 50.1% score rate; a rule-based build placed 5th | Declining. 06-29: "the field is no longer solved by asking only whether a Lucario list is playable" |
| 2. automation friendliness / branching | **Best.** 15 distinct cards, one evolution line, one primary attacker | Unknown — no list to assess | Worst of the four: 23 distinct, a **Stage 2** line (Abra→Kadabra→Alakazam) plus a support package | 17 distinct, moderate |
| 3. exact legal deck list | **Yes** — published as a `%%writefile deck.csv` cell, extracted verbatim, 60 cards, all counts legal, and **verified playable by the `cabt` engine this run** | **No.** Discussed in three notebooks; no 60-card list published in any of them | Yes — extracted, 60 cards, legal | Yes — official sample, hash-verified in-repo |
| 4. deterministic sequencing clarity | **Best.** Setup → Turbo Flare → evolve → Metal Defender is a fixed spine with few branch points | n/a | Stage 2 makes the opening fragile and branch-heavy | Clear but the plan is switch-based, not linear |
| 5. package/runtime feasibility | Equal — same SDK, same archive shape | Equal | Equal | Equal |
| 6. matchup relevance | **Best.** Named as the rising pressure lane and benchmarked directly against Starmie and Alakazam | High if obtainable | High — it is the mirror everyone plays | Low and falling |
| 7. implementation risk in one day | **Low** | **Blocking** — cannot implement a deck whose list does not exist | High | Low–medium |

**Starmie is rejected on dimension 3, not on strength.** §9 required investigating it and it is
genuinely the strongest *reported* archetype in the 18-July snapshot. But no exact 60-card
Starmie list appears in any retrieved public source, and §2's BLOCKED condition names "an exact
legal deck." Selecting an archetype whose list I would have to invent would make the deck
unevidenced and the result unattributable.

**Alakazam is rejected on dimensions 2, 4 and 7.** It is the only candidate with a Stage 2
evolution line as its main attacker, in a contract that allows one day and forbids search. Its
score rate is also neutral (50.1%) despite the largest field share.

## Why this deck is mechanically coherent

The list initially looked wrong — Cinderace is Stage 2 from Raboot, and the deck contains no
Raboot and no Scorbunny. Reading the card data resolved it, and the resolution *is* the deck:

| card | mechanism |
|---|---|
| **Cinderace** (160 HP {R}) | Skill *Explosiveness*: "If this Pokémon is in your hand when you are setting up to play, you may put it face down in the Active Spot." It never evolves — it is placed directly at setup |
| **Cinderace — Turbo Flare** | Cost 1 colourless, 50 damage, and searches the deck for **up to 3 Basic Energy attached to Benched Pokémon**. This is the deck's energy engine, not its win condition |
| **Archaludon ex** (300 HP {M}, Stage 1 from Duraludon) | Skill *Assemble Alloy*: evolving it attaches **up to 2 Basic {M} Energy from the discard pile** |
| **Archaludon ex — Metal Defender** | {M}{M}{M} for **220 damage**, and "during your opponent's next turn, this Pokémon has no Weakness" — it cancels its own {R} weakness on the turn it matters |
| **Full Metal Lab** (stadium) | {M} Pokémon take **30 less damage** |
| **Hero's Cape** (ACE SPEC) | **+100 HP** → a 400 HP Archaludon ex |
| **Relicanth** | *Memory Dive*: evolved Pokémon may use attacks from their previous evolutions, so Archaludon ex retains Duraludon's cheap *Hammer In* |
| **Boss's Orders / Night Stretcher** | gust the target that matters; recover a knocked-out attacker |

## Expected default game plan

1. Setup: Cinderace face-down Active via *Explosiveness*; bench Duraludon (up to 2).
2. Turns 1–2: *Turbo Flare* for 50 while attaching up to 3 Basic Energy to the benched Duraludon.
3. Turn 2–3: evolve Duraludon → Archaludon ex, triggering *Assemble Alloy* for 2 {M} from discard.
4. Play *Full Metal Lab*; attach *Hero's Cape* to the intended attacker when available.
5. Attack with *Metal Defender* (220) every turn; use *Boss's Orders* when a gust wins the prize race.

## Expected difficult matchup / failure mode

Fire. Archaludon ex is weak to {R}, and *Metal Defender* only suppresses weakness during the
opponent's **next** turn — so the turn the deck evolves but has not yet attacked is the exposed
window. A fast Fire attacker that removes Duraludon before it evolves, or that knocks out
Archaludon ex in the gap turn, beats the plan. Secondarily, a deck that answers stadiums removes
the −30 from Full Metal Lab.

## Public sources supporting this choice

| ref | what it establishes |
|---|---|
| `makthanithin/pok-mon-tcg-ai-battle-meta-snapshot-06-29` (updated 2026-07-26) | Archaludon rising sharply, score rate above 60%; Starmie and Hop/Trevenant are stress tests |
| `pilkwang/pok-mon-tcg-ai-battle-meta-snapshot-18-july` | field shares and score rates; Starmie's exact-list strength; "finding a powerful 60-card list is easier than reproducing the policy that makes it powerful" |
| `masamikobayashi/a-sample-archaludon-75-wr-vs-my-1300-starmie` | the exact 60-card list, and a reported 75% WR against a 1300+ Starmie |
| `ryotasueyoshi/rule-based-not-psychic-alakazam-best-5th` | the Alakazam alternative and its exact list |

Only the **deck list** — factual card IDs — is taken from a public notebook. The deterministic
expert is written for this contract; no published agent implementation is copied. Note also that
`romanrozen/strong-start-baseline-agent-v10-lb-950`, the strongest public agent found, is an
**expectimax** agent, which §6 forbids outright — so it is evidence about the ceiling, not a
template.

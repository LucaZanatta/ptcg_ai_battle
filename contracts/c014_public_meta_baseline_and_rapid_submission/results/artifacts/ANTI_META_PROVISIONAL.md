# Provisional anti-meta thesis (recorded, NOT implemented in c014)

§6 forbids implementing this branch in c014, and §9 requires recording exactly one provisional
thesis for c015. Nothing in this file is built, tested, or packaged here.

## Thesis

> Punish the rising metal-tempo lane with a fast {R} attacker that removes Duraludon **before it
> evolves**, exploiting the one-turn window in which Archaludon ex is on the board but has not
> yet used Metal Defender and therefore still has its Fire weakness.

## Why this is evidence-based rather than invented

It comes from the card data read during selection, not from a hunch:

- **Archaludon ex is weak to {R}** (`weakness = 2` = Fire) and has 300 HP, so a Fire attack
  hitting weakness needs only 150 raw damage to remove the deck's sole win condition.
- ***Metal Defender* suppresses weakness only "during your opponent's next turn."** The
  suppression is therefore unavailable on the turn Archaludon ex arrives. That gap is a
  structural property of the card, not a misplay, and it cannot be patched by better piloting.
- **Duraludon has 130 HP** and must sit on the bench while Cinderace loads energy onto it. Any
  deck that can reach the bench — the selected deck itself runs Boss's Orders for exactly this
  reason — removes the line before Archaludon ex ever exists.
- **Full Metal Lab reduces damage by 30**, so the counter must either clear the stadium or hit
  hard enough that 30 does not change the number of attacks required.

The counter is thus aimed at two specific, documented windows (pre-evolution Duraludon, and the
evolve-turn weakness gap), not at a general "play Fire" intuition.

## What c015 would have to establish before implementing it

1. An **exact legal 60-card Fire list** with current public evidence. This is precisely the
   dimension on which Starmie was rejected in c014, and the anti-meta branch must not be allowed
   to skip it.
2. That the metal lane is still rising when c015 starts. The 06-29 snapshot is a snapshot; an
   anti-meta deck built against a lane that has already been countered is worse than the meta
   deck it replaces.
3. That the counter survives the rest of the field. Beating Archaludon while losing to the
   Alakazam field centre (35.7–46.4% share) is a net negative on the ladder.

## Relationship to the c014 branch

c014's own worst matchup and this anti-meta thesis are **the same mechanism seen from both
sides**. That is deliberate: whichever branch c015 pursues, the first loss mode c014 measures in
live games is the one that decides it.

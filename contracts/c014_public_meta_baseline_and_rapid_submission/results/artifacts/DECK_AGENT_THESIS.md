# Deck-agent thesis — Archaludon ex / Cinderace metal tempo

## The thesis, in one sentence

> Open with Cinderace in the Active Spot to attack for 50 while it loads three Basic Energy onto
> a benched Duraludon, then evolve into Archaludon ex — which recovers two more {M} from the
> discard as it evolves — and win the damage race with a 220-damage attack that also cancels its
> own Fire weakness.

## Why deck and agent are one object here

The competition scores a **deck-agent pair**, and this deck is the clearest example of why
c005–c013's approach — optimising a policy against a frozen deck — was attacking the wrong
variable. Three of this list's cards are only playable at all because the agent knows a
deck-specific fact:

- **Cinderace is a Stage 2 with no Raboot in the deck.** A generic agent can never play it. It
  enters only through *Explosiveness* during setup.
- **Discarding Basic {M} Energy is a gain, not a cost.** *Assemble Alloy* recovers 2 from the
  discard on evolution, so Ultra Ball's discard is the deck's energy bank. A generic agent
  discards energy last, which is exactly backwards here.
- **Attachment must outrank card plays.** Reaching {M}{M}{M} with one attachment per turn is the
  binding constraint; a generic "play your hand first" heuristic never attacks. This was measured,
  not assumed — see `RULES.md` §3.

No amount of policy optimisation over the Dragapult list produces any of these three rules,
because none of them exists in that deck.

## Expected default game plan

1. **Setup** — Cinderace face-down Active via *Explosiveness*; Duraludon to the bench.
2. **Turns 1–2** — *Turbo Flare*: 50 damage and up to 3 Basic Energy onto the benched Duraludon.
3. **Turn 2–3** — evolve Duraludon → **Archaludon ex**, triggering *Assemble Alloy* for 2 more
   {M} out of the discard.
4. **Support** — Full Metal Lab (−30 to {M}); Hero's Cape (+100 HP → a 400 HP attacker).
5. **Close** — *Metal Defender* for 220 each turn, with Boss's Orders when a gust wins the
   prize race.

## Expected difficult matchup and failure mode

**Fire.** Archaludon ex is weak to {R}, and *Metal Defender* suppresses that weakness only
"during your opponent's next turn" — so the turn it evolves but has not yet attacked is an
exposed window. A Fire attacker that removes Duraludon before it evolves, or that knocks out
Archaludon ex in the gap turn, beats the plan outright. Secondarily, stadium replacement removes
the −30 from Full Metal Lab.

This is recorded here **before** validation results, and it is the same mechanism as the
provisional anti-meta thesis in `ANTI_META_PROVISIONAL.md`, viewed from the other side.

## What v0 deliberately does not do

§6 forbids search, learned components, and multi-deck abstraction, and this v0 respects that
strictly. It has no lookahead, no evaluation function, no opponent model beyond visible state,
and no tuning against the final panel. It is a priority table — the smallest thing that can
execute the thesis and be inspected line by line.

Strength is therefore **diagnostic** for this contract (§11: "Do not block submission merely
because the v0 does not beat every local baseline"). The purpose of v0 is a validated, packaged,
accepted submission plus one measured loss mode to attack next.

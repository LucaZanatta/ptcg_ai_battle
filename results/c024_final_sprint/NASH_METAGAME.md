# Solving the deck-selection game, instead of searching for the best deck

Every contract here has asked *which agent is strongest* and promoted the maximum of a
field score. A matchup matrix also defines a zero-sum game, and its equilibrium answers a
question the average cannot: **does this format have a best deck at all?**

Pooled from `rr_v1,rr_v1b,rr_v1c,c024_screen1,c024_calib13,c024_azam_panel1,calib_panel,calib_panel2,crustle_panel,final_panel` — both orientations of every pairing, minimum 30 games per cell, recounted from raw games.

## The equilibrium mixture

| agent | equilibrium weight | worst single matchup | vs the equilibrium |
|---|---:|---:|---:|
| **pub_tetsutani_grimmsnarl** | 0.714 | -0.062 | -0.000 |
| **official_mega_abomasnow** | 0.184 | -0.725 | +0.000 |
| **official_iono** | 0.102 | -0.688 | +0.000 |
| official_dragapult | 0.000 | -0.426 | -0.271 |
| official_mega_lucario | 0.000 | -0.811 | -0.053 |
| pub_jazivxt_codex_alakazam | 0.000 | -0.525 | -0.204 |
| pub_jazivxt_rising_tide_v21 | 0.000 | -0.550 | -0.251 |
| pub_makthanithin_lucario_1084 | 0.000 | -0.713 | -0.048 |
| pub_prvsiyan_lucario_v12 | 0.000 | -0.688 | -0.101 |
| pub_raunakdey_heuristic | 0.000 | -0.588 | -0.275 |

**Game value: -0.0000** (0 by construction for a symmetric game; deviation measures how far the measured matrix is from antisymmetric, i.e. sampling noise).

## What the support says

**3 agents share the equilibrium support**, so no single deck is unexploitable on this panel. 'Which deck is best' has no answer here — the honest question is *which deck is least punished by the mixture we actually expect to meet*, and that depends on the ladder's composition, not on ours.

This is the formal version of the rock-paper-scissors observation in `EXCHANGE_RATE_CORRECTION.md`, and it is the strongest argument that the campaign's framing — search for a maximum of a field average — was mis-specified from the start.

## Worst-case exposure, which a field score hides entirely

`worst single matchup` is what each agent scores against its *best counter* on this panel. A field average of 0.50 built from cells of 0.95 and 0.05 is a different object from one built from cells of 0.50, and only the first can be targeted by an opponent who picks their deck knowing ours.

- `official_mega_lucario` — worst cell -0.811
- `official_mega_abomasnow` — worst cell -0.725
- `pub_makthanithin_lucario_1084` — worst cell -0.713
- `official_iono` — worst cell -0.688
- `pub_prvsiyan_lucario_v12` — worst cell -0.688
- `pub_raunakdey_heuristic` — worst cell -0.588
- `pub_jazivxt_rising_tide_v21` — worst cell -0.550
- `pub_jazivxt_codex_alakazam` — worst cell -0.525
- `official_dragapult` — worst cell -0.426
- `pub_tetsutani_grimmsnarl` — worst cell -0.062

## What this is not

- **The ladder is not a deck-selection game.** One agent is submitted and meets whatever
  the matchmaker sends; an equilibrium mixture is not playable. This is a diagnostic of
  the format and of how exploitable a fixed choice is.
- **The matrix is ours.** It over-represents Alakazam (three of the panel's agents) and
  contains nothing above ~1100 ladder rating. The equilibrium describes this panel.
- **Cells are 40–400 games**, so entries carry roughly ±0.1 of noise; the support is
  stable in sign, not to three decimals.

## The result, and why it retires the campaign's framing

**`pub_tetsutani_grimmsnarl` carries 71.4% of the equilibrium, and its worst matchup on the whole
panel is −0.062 — a 46.9% score rate against its own best counter.**

Every other agent measured here has a catastrophic worst cell: Mega Lucario −0.811, Mega Abomasnow
−0.725, our champion −0.426. Grimmsnarl is the only deck on this panel that **cannot be
counter-picked**.

That is a different property from "highest field score", and it is the property that matters on a
ladder where you submit one fixed agent and meet whatever the matchmaker sends. A field average
hides it completely: `official_dragapult` and `pub_jazivxt_codex_alakazam` sit within a few points
of each other on field score while their worst cells differ by ten points, and both are dominated
by an agent whose average is unremarkable.

**Our champion scores −0.271 against the equilibrium mixture** — third-worst of the ten. The agent
this project spent eleven contracts defending is one of the *most* exploitable choices available,
and the search that selected it could not have seen that, because it was maximising the wrong
functional.

This is the formal statement of what `EXCHANGE_RATE_CORRECTION.md` observed informally and what
`S0_PUBLIC_AGENT_SCREEN.md` measured: Marnie's Grimmsnarl is 58.8% of the 1100+ ladder band not
because it beats everything, but because **nothing beats it badly**. The ladder had already solved
this game; the equilibrium recovers the answer from our own matrix, independently.

### The one-line version, for the next campaign

> Do not search for the deck with the best average. Search for the deck with the **best worst
> case**, and check it against the equilibrium of the matchup matrix you have already measured.

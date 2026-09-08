# Predictions registered before the runs that test them

Written so that each result below reads as a test rather than as a postmortem. Timestamps are the
file's git history; every prediction here precedes the run named in it.

---

## P-A — `bench_discipline_vs_spread` will not help, and the mining says why

**Registered:** 2026-08-03 19:50 Europe/Rome, before `bench_screen` produced any games.

The rule vetoes playing a Pokémon with ≤100 HP onto a bench that already holds ≥2, when the
opponent shows the Grimmsnarl / Froslass / Munkidori package. After the `opt_card` fix it fires on
**8.4%** of decisions — by far the largest intervention in this campaign.

**Prediction: it will score at or below the control, and the loss will be concentrated in the
Grimmsnarl matchup it was written for.**

Two pieces of evidence, both already in hand:

1. **The loss mining points the other way.** Won games have a mean bench of **3.31**; lost games
   **2.63**. If a wide mid-game bench were the exposure the rule assumes, that sign would be
   reversed.
2. **The rule's entire effect is blocking Dreepy.** With a ≤100 HP threshold the only cards it can
   veto in this deck are Dreepy (70) and Budew (30), and `chal_dp_benchline` — the same rule with
   119/120 protected — measured **INERT, 0 fires**. So every one of those 8.4% of firings is the
   agent being stopped from developing its own evolution line.

**What would falsify the prediction:** a gain against Grimmsnarl specifically, which is the only
place the exposure mechanism (Shadow Bullet's 30 to a benched Pokémon, Froslass's per-checkup
counter) actually operates.

**Why it is being run anyway.** The evidence against it is correlational; `bench_wide_setup` did
lose 6.6 points in this exact matchup, so the exposure mechanism is real at *setup*. A controlled
measurement costs 12 minutes and settles whether it is also real mid-game.

**`chal_dp_bench4f`** — the same rule with the cap raised to 4, firing on 1.4% of decisions — is
the variant expected to be harmless-to-slightly-positive, because it limits over-extension without
touching development.

---

## P-B — the archetype's headroom is agent, not deck

**Registered:** 2026-08-03 19:52 Europe/Rome, before `pub_makthanithin_lucario_1084` was measured
on the dev panel.

Two of the three cells are already measured on the same dev panel over 1,200 games each:

| | agent | deck | dev field |
|---|---|---|---:|
| A | official Mega Lucario | official list | **0.4687** |
| B | official Mega Lucario | public tuned list (`2a541d7bf3d9`) | **0.4875** |
| C | `makthanithin` | the same public tuned list | **?** |

B − A = **+1.9 pp**, inside this panel's noise floor. The public list is two independent authors'
converged build and one of those authors' kernels is titled with a **1084.5** leaderboard score,
against the official sample's measured **593.3**.

**Prediction: C − B will be several times B − A.** If the archetype's ~490 rating points of
headroom were in the 60 cards, B would already have captured a large share of it, and it did not.

**Consequence if confirmed.** The correct next move for this competition is agent engineering on a
legally reusable base, not deck search — which is also what `DECK_CHANGE_LEDGER.md` concluded from
the opposite direction, having found no deck mutation worth anything over 17 arms.

**What would falsify it:** C landing close to B, which would mean the public agents' strength is
not reproducible on this panel and that the 1084.5 figure reflects something the panel does not
measure.

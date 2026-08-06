# EXECUTIVE_DECISION — c023

## Deadline

**The contract's hard stop was 2026-08-05 20:00 Europe/Rome. This report was completed at
2026-08-06 00:2x — 4h22m late.** A power failure killed the machine during the closing window and
the session resumed afterwards.

What was done after the deadline was **only** the close the contract mandates *at* the deadline —
regenerate reports from raw data, run final validation, capture source and Git evidence, build the
archive. **No experiment was run, no candidate was built and no measurement was taken after
2026-08-05 20:00.** The last game played in this campaign predates the deadline. The overrun is
recorded here and in `STATUS.json` rather than absorbed.

## The short version

**The champion changed, and nothing beat it.**

`official_dragapult` — not `official_mega_lucario`, which two prior contracts had labelled our
best candidate — is the strongest submission-eligible agent this repository has. Twenty-eight
challengers across five branches, **392,792 games**, and not one cleared a noise floor that was
itself measured rather than assumed.

That is a negative competitive result, and this report does not dress it as anything else. What
the campaign did produce is three measurements that change what the *next* one should do, and they
are the reason it reads as a research success rather than a wasted forty-eight hours:

1. **The first local↔ladder calibration this project has had, and it is good.** Four submitted
   agents, all re-measured on one 13-player panel at 2,400 games, against the rating the ladder
   gave them: **rating = 347.5 + 646.7 × local field, R² = 0.987**, worst residual 22 rating
   points. **6.47 rating points per local point.** The 534.6 points to the top of the leaderboard
   is **≈ +83 local points** — more than the champion's entire field score.
2. **The headroom is in the agent, not the deck**, measured three ways: 17 deck mutations worth
   nothing over 1,200 games each; a controlled deck-vs-agent decomposition on identical cards
   (**deck +1.9, agent +5.7**); and a ladder record where the same 60 cards reach ~1084 with a
   better agent and 593 with the sample.
3. **A first-action search is the wrong instrument for these agents.** Eleven arms, ~26,000 games,
   all at or below control — with the mechanism measured, not guessed: the expert's turn is nearly
   order-invariant, so an exact-gain override fires on **0.07–0.4%** of decisions.
4. **And why none of it could have worked.** `FAILURE_TAXONOMY` F8, from 83 real ladder games read
   turn by turn: we lose the two-hit race. Dragapult ex attacks for **200** into 320–340 HP
   attackers that hit back for 180–270, and a knocked-out Mega pays them three prizes to our two.
   That is arithmetic in the card text, and no override, constant or search changes it.

## 1. What is the frozen champion?

**`official_dragapult`**, the official Kaggle sample agent, byte-for-byte, with its own 60-card
list.

| | |
|---|---|
| off-mirror field score | **0.4653**, Wilson 95% [0.4291, 0.5018], 720 games |
| seat 0 / seat 1 | 0.4625 / 0.4725 — no meaningful seat effect |
| real ladder score rate | **0.5783** over 83 public games |
| rating at the time | 719.7 (≈ 65th percentile of 6,113 teams) |
| package | `final_packages/c023_champion_dragapult.tar.gz`, sha256 `cf5bcd01…`, 1.5 MB |
| clean validation | executed — extracted to a scratch directory and played out of it: 96 games, 0 errors, both seats, worst decision inside the self-imposed 1000 ms bound |

**It was decided by measurement, not inherited as a label.** c016 named `official_mega_lucario` its
best candidate on a six-opponent panel that never ran dragapult *as a candidate* — only as an
opponent. This contract's round-robin ran all ten players on one panel with one harness:

| submission-eligible base | off-mirror field |
|---|---:|
| **`official_dragapult`** | **0.4653** |
| `official_mega_abomasnow` | 0.3625 |
| `official_mega_lucario` | 0.3521 |
| `official_iono` | 0.3431 |

The Kaggle ladder had agreed with this the whole time: 719.7 against 593.3.

**The strongest player on the panel is not the champion and cannot be.** That is
`pub_jazivxt_rising_tide_v21` at 0.6417. `SOURCES.md` classifies every community kernel
`LOCAL_BENCHMARK_ONLY` — the Kaggle API exposes no licence for any of them, and c016 §12 forbids
inferring permission from visibility. They are opponents, never bases. `champion.json` records both
numbers so the distinction cannot be lost.

## 2. What is the strongest challenger?

**There isn't one.** Twenty-eight candidates across five branches, **392,792 games**, and not one
cleared a noise floor this campaign measured on itself three separate ways.

The closest things to a challenger, all inside the floor:

| candidate | what it changed | dev field | control, same run | Δ |
|---|---|---:|---:|---:|
| `ab_f5` | three score constants (F5-motivated) | 0.5116 | 0.5099 | +0.17 |
| `dpdeck_d08` | −1 Latias ex, +1 Dragapult ex | 0.5217 | 0.5104 | +1.13 |
| `chal_dp_bench_prizef` | bench discipline + exact-gain planner | 0.5285 | 0.5230 | +0.55 |

**The measured run-to-run range on an unchanged policy is 2.4 points at 1,200 games per arm.**
Every number in that Δ column is smaller than the campaign's own measurement error, and the two
arms that were re-measured at higher power (`ab_f5` at 5,000 games, `d08` at 1,200) both shrank.

## 3. How much better or worse is it?

**Zero, to within ±1 point.** The best-powered comparison in the campaign — `ab_dev`, 5,000 games
per arm, four arms, no selection step — puts the whole F5 direction at **+0.17 points** on the dev
panel and **+0.11** on a validation panel it had never seen.

For scale, this contract's registered promotion target was ~+4 points, and the calibration values
that at ≈+26 Kaggle rating.

## 4. Which matchups drive the result?

The champion's panel profile, 80 games per cell:

| opponent | score | | opponent | score |
|---|---:|---|---|---:|
| `official_iono` | 0.6375 | | `official_mega_abomasnow` | 0.4625 |
| `pub_raunakdey_heuristic` | 0.6000 | | `pub_makthanithin_lucario_1084` | 0.3750 |
| `pub_jazivxt_codex_alakazam` | 0.5375 | | `pub_prvsiyan_lucario_v12` | 0.2750 |
| `official_mega_lucario` | 0.5250 | | `pub_tetsutani_grimmsnarl` | 0.2500 |
| `pub_jazivxt_rising_tide_v21` | 0.5250 | | | |

And what the **ladder** actually paired it against, from 83 of our own replays:

| opponent archetype | share | our score |
|---|---:|---:|
| Alakazam | 22.9% | 0.737 |
| Mega Lucario | 18.1% | 0.467 |
| Marnie Grimmsnarl | 12.0% | 0.400 |
| Crustle Wall | 10.8% | 0.222 |
| Dragapult (mirror) | 7.2% | 1.000 |

**The two disagree, and the ladder is right about which matchups matter to us.** Marnie's
Grimmsnarl is 58.8% of the 1100+ band and this campaign built its dev panel around that — but
matchmaking pairs by rating, and at *our* band Grimmsnarl is 12%. Our panel's Grimmsnarl agent puts
us at 0.250 where the real ladder puts us at 0.400: the panel opponent is harder than the archetype
we meet.

The one place the ladder pointed somewhere new — Crustle Wall at 0.222 — **did not survive
measurement**. A public Crustle agent was added to the panel and the matchup measured at 400
games: the champion scores **0.7325**. The ladder number was two wins in nine games. That branch
was killed before a line of it was written, which is the campaign's cleanest example of a
measurement paying for itself in eighty seconds.

## 5. Which candidate should be submitted first?

**The champion — and it was, because the wrong agent was on the ladder.**

The user granted submission authorization directly in session on 2026-08-05
(`SUBMISSION_AUTHORIZATION.md`, recorded in the repository before it was used). Checking the
ladder then showed something this campaign had not looked at: **our most recent submission was
`official_mega_lucario` at 581.1 and still drifting, while `official_dragapult` sat frozen at
719.7.** The most recent submission is the one that plays, so our active agent had been the weaker
of the two for ten days.

| ref | agent | submitted | reading |
|---|---|---|---:|
| **55254872** | **c023 champion, `official_dragapult`** | 2026-08-05 03:38 | **788.1** |
| 55011215 | `official_mega_lucario` | 2026-07-26 | 578.4 |

**+209.7 rating over the agent that was live.** That is the campaign's only competitive gain, and
it is important to say exactly what produced it: **not a better agent — the same agent, correctly
deployed.** Nothing this campaign built is in that package; it is the official Kaggle sample,
byte-for-byte.

Two things it is *not* evidence of:

- **Not an improvement over the baseline.** 788.1 against the 719.7 the *same agent* scored in
  July is two readings of a live rating taken twelve days apart against different ladder
  populations. c015 recorded this agent's own readings moving 150+ points inside an hour. The
  comparison that means something is 788.1 against the 578.4 that was actually playing.
- **Not a validation of the calibration.** The model predicted 716.6 and the observed reading is
  788.1. One point, in a quantity that drifts, is not a test.

## 6. Is there a complementary second candidate?

**No.** The one considered was `mldeck_ml_public_tuned` — the official Mega Lucario agent on the
60-card list two independent public authors converged on (deck lists are `CONFIGURATION_NOT_CODE`
and reusable). It scores **0.4875** against that agent's own 0.4687, a +1.9-point difference inside
the noise floor, and both are well below the champion's 0.4653-on-a-harder-panel. It has a
genuinely different matchup profile — 0.812 against `official_iono`, 0.096 against Alakazam — but
"different" is not "complementary" when it is also worse everywhere it matters.

## 7. What was killed?

| branch / rule | arms | games | verdict |
|---|---:|---:|---|
| **B2 deck co-optimization** | 17 | ~14,000 | **FAIL** — best screen arm went +7.25 → −0.12 between 400 and 1,200 games |
| F1 turn order (`go_first`) | 1 | 600 | KILLED — −2.8 overall, −9.1 against Grimmsnarl |
| F2a bench Dreepy when first | 1 | 600 | KILLED — inside the floor |
| F2b wide opening bench | 1 | 600 | KILLED — −5.0, and −6.6 against Grimmsnarl |
| F3 turn planner, board evaluator | 4 | 5,000 | KILLED — **monotone in override rate** |
| F3 turn planner, exact gate | 4 | ~5,000 | KILLED — fires on 0.07–0.4% of decisions |
| F3 expert shortlist | 2 | 2,400 | KILLED — both below control |
| F4 bench discipline vs spread | 4 | ~9,000 | KILLED — and the registered prediction held |
| **P7 anti-Crustle** | 0 | 1,600 (measurement only) | **KILLED before implementation** — the premise did not reproduce |

## 8. What pivots occurred?

Four, each with the evidence that forced it, in `PIVOT_LEDGER.md`: the champion changed from
mega_lucario to dragapult (P1); the panel was rebuilt from four official samples to a
meta-representative ten (P2); deck co-optimization was abandoned for agent work (P3); and the
planner's work budget was changed from a wall clock to a count, because a latency-budgeted search
gets *weaker* under CPU contention and this repository has had three results corrupted that way
(P4). A fifth is recorded as an amendment: Crustle Wall joined the **validation** panel rather than
dev, so anti-Crustle work would be measured on evidence the tuner never saw.

## 9. Did ByteRL provide measurable value?

**No, and no component was admitted.** c022 registered the admission condition before its transfer
arms ran — the value head must beat a constant predictor at the observed base rate — and measured
**−0.06** and **−0.10**. Both policy-prior and rollout-policy arms came back INCONCLUSIVE inside a
noise floor measured before they ran, and the rollout policy spent 78% of its wall clock inside the
network for it. `BYTERL_COMPONENT_RESULTS.md` names the one cheap measurement that would reopen the
question and states plainly that it was not run.

What *did* carry over from that lineage is engineering, not weights: the identity-carrying
job/result contract, the recompute-every-aggregate-from-raw-rows discipline, and the knowledge that
a latency-budgeted search must not share a machine.

## 10. What remains uncertain?

Ten risks in `UNRESOLVED_RISKS.md`. The three that would change a conclusion:

- **R4, the noise floor.** `chal_dp_base3` — one candidate, three separate 1,200-game runs —
  measured 0.5042, 0.5125 and **0.5279**. Range 2.4 points on an unchanged policy. Nothing under
  ~2.5 points at 1,200 games is evidence, which retires most of the small positive deltas here.
- **R3, one implementation per archetype.** Every "Grimmsnarl matchup" claim is about one agent.
  Crustle showed this cutting in our favour; it can cut the other way.
- **R1, the local↔ladder mapping.** Now partly measured (§ the calibration), but from two locally
  measured agents and a straight line through them.

## 11. What should happen in the next 24–48 hours?

**Not more local rule surgery on a sample agent.** This campaign spent 60,000 games establishing
that the reachable levers there are exhausted, and the calibration says the target is ≈ +48 local
points.

The evidence points to one thing: **whole-agent quality on a legally reusable base.** The
decomposition measured a better agent on identical cards at **+5.7 points**; the public record has
the same 60 cards reaching ~1084 against the sample's 593. The visible differences in those public
agents are structural, not parametric — matchup detection branches, evolution-line denial in target
selection, deck-out guards — and the sample has none of them.

Concretely, in priority order:

1. **Build matchup detection into the base's target and energy scoring**, the way the public 1084
   agent does. This campaign tested *overrides* of the expert's output; that agent changes the
   expert's *scores*, which is a much larger intervention and the only one with measured evidence
   behind it.
2. **Mine the ladder replays for losses, not just archetypes.** `tools/c023_replays.py` already
   returns full observation streams for 380 of our own games. This contract used only the decks
   and the rewards. The turn-by-turn record of how we lost is sitting there unread — the single
   largest piece of available evidence this campaign did not use.
3. **Only then, a deck-specific expert from scratch**, and only with weeks rather than hours:
   c015 measured a from-scratch expert at 0.36 where an official agent scored 0.98 on the same
   target.

## 12. Was this a competitive success, a research success, or a failure?

**Research success; competitive non-improvement.** Stated plainly:

- **Competitively: no.** No challenger was promoted. The champion is retained unchanged, packaged
  and clean-validated, and the contract's own rule — "do not manufacture a PASS because substantial
  work was completed" — is what stops this being written any other way. Every candidate that looked
  positive did so inside a noise floor this campaign measured on itself, three times.
- **As research: yes.** The champion label was wrong for two contracts and is now right and
  evidenced. The project has, for the first time, a local↔ladder conversion, a first-hand record of
  what the ladder actually pairs us against, a controlled deck-versus-agent decomposition, and a
  measured reason why search does not help these agents. Four branches were killed on evidence
  rather than abandoned, two registered predictions were tested and held, and three harness defects
  were caught — one of them by a probe built specifically because that failure is invisible to
  every outcome-based check.

The most useful sentence in the campaign is the one it can now say with a number: *the gap to the
top of this leaderboard is about forty-eight local points, and it is in the agent.*

# Unresolved reference choices

`FIDELITY_RULES §4`: "Unspecified details belong in `UNRESOLVED_REFERENCE_CHOICES.md`, with
alternatives and sensitivity tests. Never silently inherit c021 values."

Each entry states whether the reference **states** the value or whether it was **chosen**, what
the alternatives were, and how sensitive the result is to the choice. A detail that is merely
listed without alternatives is not resolved, it is asserted.

---

## Stated by the reference — reproduced exactly

`FIDELITY_RULES §4` lists these as "minimum disclosed Hearthstone settings to preserve". They are
constants in `c022_byterl_learn.py` and `test_disclosed_settings_are_the_disclosed_values`
asserts every one, because a drifted constant is a silent fidelity failure that no loss curve
would reveal.

| setting | value | where |
|---|---|---|
| LSTM hidden size | 256 | `c022_byterl_model.LSTM_HIDDEN`, probe B01 |
| gamma, B1 and above | 1.0 | `GAMMA_B1_PLUS` |
| learning rate | 7e-5 | `LEARNING_RATE` |
| sample reuse | 2 | `SAMPLE_REUSE` |
| entropy coefficient | 0.01 | `ENTROPY_COEF` |
| value / PPO / UPGO weights | 1 / 1 / 1 | `VALUE_COEF`, `PPO_COEF`, `UPGO_COEF` |
| importance-ratio bounds | [0.001, 1.007] | `RHO_LOWER_B3`, `RHO_UPPER_B3`, probe B13 |
| PPO clip epsilon | 0.2 | `PPO_CLIP_EPS` |
| OSFP self-play probability | 0.6 | `OSFP_SELFPLAY_PROB` |
| promotion threshold | 0.55 | `OSFP_PROMOTION_THRESHOLD` |
| max periods without promotion | 6 | `OSFP_MAX_PERIODS_WITHOUT_PROMOTION` |

---

## U01 — B0's discount

**Status:** CHOSEN.

`FIDELITY_RULES §4` defines B1 as "B0 with gamma changed to 1.0", which fixes B1 but leaves B0's
value unstated. 0.99 is used.

- **Alternatives:** 0.999, or any value < 1.
- **Why 0.99:** it is the common default in the IMPALA line the papers inherit from, and the only
  property the ladder needs is that B0's gamma is NOT 1.0 — otherwise the B0→B1 rung delta is
  nothing at all.
- **Sensitivity:** `test_discount_of_one_and_of_gamma_give_different_targets` asserts the two
  produce different V-trace targets on the test data, so the rung difference is real whatever the
  exact value. The *magnitude* of the B0→B1 effect does depend on it, and the controlled rung
  comparison reports both gammas alongside the result.

---

## U02 — rho_bar and c_bar for B0 through B2

**Status:** CHOSEN.

The two-sided bounds [0.001, 1.007] are stated for b3. The papers do not restate the one-sided
V-trace bars for the lower rungs.

- **Chosen:** 1.0 for both, IMPALA's stated default.
- **Alternatives:** 1.007 for both (making b3's only delta the LOWER bound plus the PPO
  surrogate), or an untruncated ratio.
- **Sensitivity:** this changes what the b3 rung delta *is*. With rho_bar = 1.0 at B2, b3 changes
  both the upper bound (1.0 → 1.007) and adds a lower bound; with rho_bar = 1.007 it would add
  only the lower bound. The controlled rung comparison reports the bars for both arms so the
  delta is legible either way.

---

## U03 — the number of tokens the count head can express

**Status:** CHOSEN.

The count is scored from a bilinear form against the pooled option features, modulated by an
index scale, rather than from a fixed-size head.

- **Why:** PTCG `maxCount` varies per select and can exceed any fixed head width. A fixed head
  would truncate.
- **Alternatives:** a fixed head sized to the largest observed `maxCount`; a separate small MLP.
- **Sensitivity:** probe B04 samples counts 1/2/3 at 16/9/15 on a synthetic 1..3 select, so the
  head is not degenerate. Whether it is the *best* parameterization is untested and is not
  claimed.

---

## U04 — OSFP historical-mixture function

**Status:** CHOSEN, with the sensitivity variant `MANDATORY_IMPLEMENTATION B5` requires.

`B5` says: "If the exact historical-mixture function is underspecified, preregister the closest
supported interpretation and one sensitivity variant."

- **Chosen:** `sigma ∝ exp(−mean_payoff / eta)` with `eta = 0.1`, uniform before any game in a
  period. This weights the opponents the current policy is LOSING to, which is what "optimistic"
  smooth fictitious play means, and the period-locality is the detail the Hearthstone paper is
  explicit about.
- **Sensitivity variant:** `eta = 0.3` (a flatter mixture, closer to uniform).
- **Tests:** `test_osfp_weights_the_opponents_it_is_losing_to` asserts the ordering is by payoff
  and not by index; `test_osfp_self_play_probability_is_0_6_and_uniform_before_evidence` asserts
  the uniform prior and the 0.6 rate to within 3 pp over 4000 draws.

---

## U05 — OSFP history capacity and eviction

**Status:** CHOSEN.

- **Chosen:** capacity 16, evict the oldest.
- **Alternatives:** unbounded (memory-limited), reservoir sampling to keep an unbiased sample of
  history, or evict the least-played.
- **Why it matters less than it looks:** whatever is evicted, what remains is byte-immutable —
  `test_b16_history_survives_eviction` asserts the remaining checkpoints still verify and do not
  alias each other after five promotions into a capacity-2 pool.
- **Sensitivity:** untested at scale. Recorded as a limitation rather than claimed as neutral.

---

## U06 — minimum games before a promotion decision

**Status:** CHOSEN.

- **Chosen:** 32 games.
- **Why:** the 0.55 threshold is stated but the sample size is not, and at 8 games a 0.55 reading
  has a Wilson interval spanning roughly [0.27, 0.80] — a promotion decision on that is a coin
  flip. `test_b17_promotion_threshold_and_forced_promotion` asserts a 0.90 win rate on 4 games
  does NOT promote.
- **Alternative:** promote on any evaluation regardless of count, which the forced-promotion rule
  after six barren periods already covers as a fallback.

---

## U07 — unroll length and burn-in

**Status:** CHOSEN.

- **Chosen:** unroll length 32, no burn-in; the learner replays from the actor's stored
  `(h0, c0)`.
- **Why no burn-in:** burn-in is R2D2's answer to storing a stale hidden state in a replay
  buffer. This system has no replay buffer — the FIFO is consume-once and the stored state is the
  one the actor actually held — so there is no staleness for burn-in to correct. Probe B06
  confirms the stored state reproduces exactly at the behaviour weights.
- **Alternative:** a burn-in prefix of 8 decisions whose gradients are discarded.
- **Sensitivity:** untested. If the recurrence check ever failed, burn-in would be the first
  thing to try; it has not.

---

## U08 — the card index

**Status:** CHOSEN.

- **Chosen:** a dense contiguous remapping of the shipped card database (1267 cards), with index 0
  reserved for EMPTY.
- **Why:** raw engine ids are sparse; an embedding sized to the maximum raw id would be mostly
  dead rows, and `n_cards` would move if the id space ever changed, silently invalidating every
  checkpoint.
- **Alternative:** hash the raw id into a fixed-width table, accepting collisions.

---

## U09 — the discount used for construction decisions

**Status:** follows from the published gamma, not chosen independently.

With gamma = 1.0 (B1 and above) the discounted return at every step equals the terminal reward,
so placing the game's outcome on the last step propagates it unchanged to all 60 construction
decisions. Probe B19 measures this directly: the V-trace target at an unroll's first step is 1.0
against a terminal reward of 1.0.

Under B0's gamma = 0.99 the construction decisions are discounted by roughly `0.99^(60 + battle
length)`, which is a real difference between the rungs and is reported as such rather than
corrected.

---

## U10 — c021 values NOT inherited

`FIDELITY_RULES §4` forbids silently inheriting c021 values. These were re-derived from the
papers rather than carried across:

| quantity | c021 | c022 | basis |
|---|---|---|---|
| architecture | feed-forward residual stack | LSTM-256 over a shared torso | `FIDELITY_RULES §4` |
| gamma | not varied by rung | 0.99 at B0, 1.0 above | published rung meaning |
| importance clipping | one-sided rho_bar/c_bar | two-sided [0.001, 1.007] at b3 | published b3 |
| policy objective | `-A·log π` at every rung | PPO-style clipped surrogate at b3 | published b3 |
| sample reuse | 1 (one step per trajectory) | 2, learner-side | disclosed setting |
| actor/learner | synchronous per-iteration gather | asynchronous, bounded blocking FIFO | published b2 |
| stage names | B0..B3 with local meanings | the published meanings | `FIDELITY_RULES §4` |

The last row is the one most likely to mislead a reader: **a c021 rung label and a c022 rung
label of the same name denote different systems.** Every comparison in this contract that crosses
the c021 boundary names the artifact, not the rung.

## The M12 deploy arm's clock — read off c021, not chosen (recorded 19:52, before the arm ran)

`PROBE_MATRIX M12` asks only that "Kaggle budget changes do not modify reference branch". It
does not state the budget, and `MANDATORY_IMPLEMENTATION §115` says only "legal cumulative
clock/resource controls". So the numbers had to come from somewhere, and the honest options were
to take them from a source or to declare them chosen.

They come from a source. The frozen `C021_MCGS_K1_CONTROL` config, in
`results/controls/control_manifest.json`:

```json
"match_clock_seconds": 90.0,
"first_move_seconds": 0.9,
"continuing_move_seconds": 0.7
```

That is the 2019 source's own 15 s / 10 s schedule scaled by ~16.7x to fit the Kaggle budget
c021 actually played under. The c022 deploy arm uses those three values unchanged, which makes
it a re-measurement of a known deployment configuration under the multi-determinization search
rather than a new configuration invented alongside its own result.

**What was NOT adopted.** An earlier draft of the deploy script used `--decision-cap 5` and a
count-budgeted protocol. Both were invented: nothing in the contract, the source or c021
specifies a 5-second per-decision cap, and c021's deploy agent was time-budgeted, so a
count-budgeted arm would not have been the same question. The draft was replaced before any arm
ran, which is the only time such a replacement is worth anything.

**K is not fixed by this file.** The arm runs at K=1 and K=8. The 200-game paired result does not
license K=8 as the deployment configuration: under a 90 s cumulative clock, K=8 divides the same
clock eight ways, which is a different question from the paired comparison and has to be measured
rather than inferred.

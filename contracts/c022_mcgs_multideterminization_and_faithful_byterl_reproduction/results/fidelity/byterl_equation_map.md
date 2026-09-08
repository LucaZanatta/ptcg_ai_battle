# ByteRL equation map

Every published formula, where it lives in this repository, and **the test that would fail if it
were wrong**. A formula with no failing test is not evidence of fidelity — it is a claim.

Authority is the papers (arXiv:2303.04096 LOCM, arXiv:2303.05197 Hearthstone) plus IMPALA
(arXiv:1802.01561) where they explicitly inherit. No author implementation exists; see
`byterl_source_search.md`, re-verified 2026-07-30.

The references in `tests/test_c022_byterl_objectives.py` are written from the EQUATIONS, in plain
Python over plain floats, and import nothing from `c022_byterl_learn`. A reference that calls the
implementation it checks proves only that the code equals itself.

---

## V-trace (IMPALA eq. 1, adopted by ByteRL)

| quantity | formula | implementation | pinned by |
|---|---|---|---|
| importance ratio | ρ_t = min(ρ̄, π(a_t\|s_t)/μ(a_t\|s_t)) | `importance_ratio` | `test_b11_clips_the_importance_ratio_at_rho_bar` |
| trace coefficient | c_t = min(c̄, π/μ) | `importance_ratio` | same |
| temporal difference | δV_t = ρ_t (r_t + γV(s_{t+1}) − V(s_t)) | `vtrace` | `test_b11_is_a_fixed_point_when_values_are_already_correct` |
| value target | v_t = V(s_t) + δV_t + γ c_t (v_{t+1} − V(s_{t+1})) | `vtrace`, backward accumulation | `test_b11_vtrace_matches_independent_reference` (5 seeds), `test_b11_on_policy_zero_values_reduces_to_monte_carlo_return` |
| policy gradient | ∇ ∝ ρ_t (r_t + γ v_{t+1} − V(s_t)) ∇log π | `vtrace["pg_advantage"]` | `test_b11_advantage_uses_next_step_vs_not_current` |

**The advantage uses v_{t+1}, not v_t.** Using v_t leaks the current action's own return into its
own baseline and shrinks every advantage toward zero. The test constructs a case where the two
formulas give different numbers and asserts they differ, so it cannot pass against the wrong one.

---

## UPGO (AlphaStar, adopted by ByteRL)

| quantity | formula | implementation | pinned by |
|---|---|---|---|
| upgoing return | G_t = r_t + γ·(G_{t+1} if Q_{t+1} ≥ V(s_{t+1}) else V(s_{t+1})) | `upgo_returns` | `test_b12_upgo_matches_independent_reference` (3 seeds) |
| one-step value | Q_{t+1} = r_{t+1} + γ V(s_{t+2}) | `upgo_returns` | same |
| advantage | (G_t − V(s_t))₊ · ρ_t | `byterl_losses` | `test_full_objective_is_finite_and_backpropagates` |

**The conditional switch is the whole method.** Always following the trajectory makes this plain
Monte-Carlo; always cutting makes it one-step TD.
`test_b12_is_not_monte_carlo_and_not_one_step_td` computes both degenerate forms on the same data
and asserts the implementation equals neither.

---

## The b3 objective (Hearthstone improvements paper)

`FIDELITY_RULES §4` defines b3 as "B2 with two-sided clipped V-trace and PPO-style clipped policy
objective". `MANDATORY_IMPLEMENTATION B4` names ordinary PPO a hard failure, so b3 is two distinct
changes and conflating them is the failure:

| quantity | formula | implementation | pinned by |
|---|---|---|---|
| two-sided ratio clip | ρ_t = clip(π/μ, 0.001, 1.007) | `importance_ratio(two_sided=True)` | `test_b13_two_sided_clipping_bounds_from_BOTH_sides` |
| the clip actually binds | — | — | `test_b13_one_sided_and_two_sided_actually_differ` |
| PPO-style surrogate | L = −min(r·A, clip(r, 1−ε, 1+ε)·A), ε = 0.2 | `byterl_losses(ppo_clip=True)` | `test_b13_ppo_surrogate_matches_independent_reference` |
| the surrogate's advantage is V-TRACE's | A = ρ_t(r_t + γv_{t+1} − V(s_t)) | `byterl_losses` | `test_b13_ordinary_ppo_and_byterl_b3_differ_by_the_ADVANTAGE_not_only_the_clip` |
| the clip band is exercised | — | — | `test_b13_ppo_clip_actually_binds_on_this_data` |

Two of these tests exist only to stop the others being decoration. A clipping test on data where
nothing clips passes trivially; a "b3 differs from PPO" test passes trivially if the advantages
happen to coincide. Both assert the discriminating condition explicitly.

**The ratio is the COMPLETE autoregressive joint.** Applying the bounds to the first token alone
is `B4`'s "first-token-only ratios" hard failure, and nothing downstream could detect it because
the shapes are identical. Probe B05 checks the joint at its source instead: the learner's
recomputed joint log-probability against the actor's accumulated one, measured at **0.0 exactly**
over 36 real sequences and 2.4e-7 over 40 synthetic multi-select sequences.

---

## Total objective

```text
L = ppo_coef·L_policy + upgo_coef·L_upgo + value_coef·L_value + entropy_coef·L_entropy
L_value = ½ (V(s_t) − v_t)²
```

with `value / PPO / UPGO weights = 1 / 1 / 1` and `entropy coefficient = 0.01` — all four STATED
by `FIDELITY_RULES §4` and asserted by `test_disclosed_settings_are_the_disclosed_values`,
because a drifted constant is a silent fidelity failure that no loss curve would reveal.

---

## OSFP

| quantity | rule | implementation | pinned by |
|---|---|---|---|
| payoff accumulation | G[i] += payoff, C[i] += 1, **within the current period** | `OSFP.record` | `test_b15_osfp_accumulators_are_period_local` |
| mean payoff | Ḡ[i] = G[i]/C[i] | `OSFP.mean_payoff` | same |
| meta-strategy | σ ∝ exp(−Ḡ[i]/η) | `opponent_distribution` | `test_osfp_weights_the_opponents_it_is_losing_to` |
| prior | uniform before any game in a period | same | `test_osfp_self_play_probability_is_0_6_and_uniform_before_evidence` |
| self-play rate | 0.6 | `sample_opponent` | same (4000 draws, within 3 pp) |
| promotion | ≥ 0.55, or forced after 6 barren periods | `should_promote` | `test_b17_promotion_threshold_and_forced_promotion` |
| immutable history | freeze, append, reset G and C | `HistoricalPolicy.freeze` | `test_b16_history_is_byte_immutable_as_the_learner_trains` |

**Period-locality is the detail the Hearthstone paper is explicit about, and the one c019 and
c020 both got wrong.** A lifetime average cannot change, so the meta-strategy stops tracking who
beats the CURRENT policy.

**History holds serialized BYTES, not tensors.** c021's "frozen" checkpoint was a `.numpy()` view
sharing storage with the live network, so the historical opponent mutated as the learner trained
and every measurement against it was against a moving target. Storing bytes makes aliasing
impossible rather than merely avoided, and `test_b16` mutates the live network after freezing and
asserts the blob still verifies and no longer matches.

---

## Autoregressive joint action

```text
log π(a_1..a_k | s) = Σ_i log π(a_i | s, a_1..a_{i−1})
```

with the mask updated after each element so no option repeats, and the COUNT as its own masked
categorical whenever `minCount < maxCount`.

| property | pinned by |
|---|---|
| sampled joint == recomputed joint | probe B05 — 0.0 exactly |
| every sequence is one legal action | probe B04 |
| the count is a real decision, not always the maximum | probe B04's synthetic multi-select: counts 1/2/3 sampled 16/9/15, `always_took_the_maximum: false` |

The last row is c021's specific defect: its sampler looped to `k_max` unconditionally, so the
policy ALWAYS took the maximum and could never learn to discard two cards instead of three.

---

## Recurrence

Not an equation, but the property every off-policy correction above depends on: the learner must
replay an unroll from the actor's stored `(h0, c0)` and reproduce it.

| property | pinned by |
|---|---|
| recomputed end-of-unroll (h, c) == actor's | probe B06 — 138 checks, max delta **0.0** |
| recomputed joint log-prob == behaviour's | probe B06 — max delta **0.0** |
| checked at the EXACT behaviour weights | `recurrence_fidelity_check` reloads the published version |

Recomputing under the learner's *current* weights measures staleness, not fidelity — it is
nonzero by design. Reading it as a defect is how the first diagnosis of D06 went wrong, and the
two quantities are now named separately (`drift_recurrence` vs the exact-weights check).

# ByteRL — paper equation map

Transcribed from arXiv:2303.04096 (LOCM) and arXiv:2303.05197 (Hearthstone improvements), plus
the IMPALA and AlphaStar results they cite. **No author implementation exists** — see
`byterl_source_search.md` — so these are the papers' formulas, not a codebase's.

Each row names where the formula lives in this repository and the test that would fail if it were
wrong. A formula with no failing test is not evidence of fidelity.

## V-trace (Espeholt et al., adopted by ByteRL)

| Quantity | Formula | Implementation | Pinned by |
|---|---|---|---|
| importance ratio | ρ_t = min(ρ̄, π(a_t\|s_t) / μ(a_t\|s_t)) | `vtrace`, `clipped_rho` | `test_vtrace_clips_importance_ratio_at_rho_bar` |
| trace coefficient | c_t = min(c̄, π/μ) | `vtrace`, `clipped_c` | same |
| temporal difference | δV_t = ρ_t (r_t + γV(s_{t+1}) − V(s_t)) | `deltas` | `test_vtrace_is_a_fixed_point_when_values_are_already_correct` |
| value target | v_t = V(s_t) + δV_t + γ c_t (v_{t+1} − V(s_{t+1})) | backward accumulation | `test_vtrace_on_policy_zero_values_reduces_to_monte_carlo_return`, `test_vtrace_with_discount_matches_hand_computed_return` |
| policy gradient | ∇ ∝ ρ_t (r_t + γ v_{t+1} − V(s_t)) ∇log π(a_t\|s_t) | `pg_advantage` | `test_vtrace_advantage_uses_next_step_vs_not_current` |

The advantage uses **v_{t+1}**, not v_t. Using v_t leaks the current action's own return into its
baseline and shrinks every advantage toward zero.

## UPGO (AlphaStar, adopted by ByteRL)

| Quantity | Formula | Implementation | Pinned by |
|---|---|---|---|
| return | G_t = r_t + γ · (G_{t+1} if Q_{t+1} ≥ V(s_{t+1}) else V(s_{t+1})) | `upgo_returns` | `test_upgo_cuts_to_the_baseline_when_the_trajectory_underperforms` |
| one-step value | Q_{t+1} = r_{t+1} + γ V(s_{t+2}) | `q_tp1` | `test_upgo_follows_the_trajectory_when_it_outperforms` |
| advantage | (G_t − V(s_t))_+ · ρ_t | `upgo_adv` | `test_losses_are_finite_and_backprop` |

The conditional switch is the whole content: always following the trajectory makes this plain
Monte-Carlo, always cutting makes it one-step TD.

## Objective

    L = L_pg(V-trace) + L_upgo + c_v · L_value + c_H · L_entropy
    L_value = ½ (V(s_t) − v_t)²

Coefficients are **Chosen**, not **Stated** — see `UNRESOLVED_REFERENCE_CHOICES §1`.

## OSFP

| Quantity | Formula / rule | Implementation | Pinned by |
|---|---|---|---|
| payoff | G[i] += payoff, C[i] += 1, **within the current period** | `OSFP.record` | `test_osfp_g_and_c_are_period_local` |
| mean payoff | Ḡ[i] = G[i] / C[i] | `mean_payoff` | same |
| meta-strategy | σ ∝ exp(−Ḡ[i] / η) | `opponent_distribution` | `test_osfp_weights_the_opponents_it_loses_to` |
| prior | uniform before any game in a period | same | `test_osfp_distribution_is_uniform_before_any_games` |
| promotion | freeze the current weights, append to history, reset G and C | `add_checkpoint` + `reset_period` | `test_osfp_history_is_immutable_even_when_the_buffer_evicts` |

Period-locality is the detail the Hearthstone paper is explicit about, and the one c019 and c020
both got wrong.

## Autoregressive joint action

    log π(a_1..a_k | s) = Σ_i log π(a_i | s, a_1..a_{i−1})

with the mask updated after each element so no option repeats. Implemented in
`ByteRLNet.select_logprob` / `sample_select`; the sampled and recomputed joint log-probabilities
are asserted equal, which is the invariant every V-trace ratio depends on.

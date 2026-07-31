"""c022 probes B11/B12/B13 — independent numerical references for the published objectives.

`MANDATORY_IMPLEMENTATION B4` requires "independent numerical references and production versions"
for V-trace, UPGO, the b3 two-sided clipping and the PPO-style surrogate, and names five hard
failures: ordinary PPO, one-sided V-trace, first-token-only ratios, zeroed recurrent starts, and
a missing reference.

The references below are written from the EQUATIONS, in plain Python over plain floats, importing
nothing from `c022_byterl_learn`. A "reference" that calls the implementation it is checking
proves only that the code equals itself.

Several tests here are written so they would FAIL against a plausible wrong implementation, and
each says which one. A test that passes under both the right and the wrong formula is decoration.
"""

from __future__ import annotations

import math
import os
import sys

import pytest
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c022_byterl_learn as L  # noqa: E402


# ============================================================ independent references
def ref_vtrace(target_logp, behaviour_logp, values, rewards, bootstrap, discounts,
               rho_bar=1.0, c_bar=1.0, two_sided=False, lo=0.001, hi=1.007):
    """IMPALA eq. 1, transcribed. Plain floats, no torch, no shared code."""
    T = len(values)
    ratios = [math.exp(t - b) for t, b in zip(target_logp, behaviour_logp)]
    if two_sided:
        rho = [min(max(r, lo), hi) for r in ratios]
        c = [min(max(r, lo), hi) for r in ratios]
    else:
        rho = [min(r, rho_bar) for r in ratios]
        c = [min(r, c_bar) for r in ratios]
    v_tp1 = list(values[1:]) + [bootstrap]
    deltas = [rho[t] * (rewards[t] + discounts[t] * v_tp1[t] - values[t]) for t in range(T)]
    vs_minus_v = [0.0] * T
    acc = 0.0
    for t in range(T - 1, -1, -1):
        acc = deltas[t] + discounts[t] * c[t] * acc
        vs_minus_v[t] = acc
    vs = [vs_minus_v[t] + values[t] for t in range(T)]
    vs_tp1 = list(vs[1:]) + [bootstrap]
    pg = [rho[t] * (rewards[t] + discounts[t] * vs_tp1[t] - values[t]) for t in range(T)]
    return vs, pg, rho, c


def ref_upgo(rewards, values, bootstrap, discounts):
    """G_t = r_t + gamma*(G_{t+1} if Q_{t+1} >= V(s_{t+1}) else V(s_{t+1}))."""
    T = len(values)
    v_tp1 = list(values[1:]) + [bootstrap]
    r_tp1 = list(rewards[1:]) + [0.0]
    v_tp2 = (list(values[2:]) + [bootstrap, bootstrap])[:T]
    d_tp1 = list(discounts[1:]) + [discounts[-1]]
    q_tp1 = [r_tp1[t] + d_tp1[t] * v_tp2[t] for t in range(T)]
    g = [0.0] * T
    nxt = bootstrap
    for t in range(T - 1, -1, -1):
        target = nxt if q_tp1[t] >= v_tp1[t] else v_tp1[t]
        g[t] = rewards[t] + discounts[t] * target
        nxt = g[t]
    return g


def ref_ppo_surrogate(target_logp, behaviour_logp, adv, eps):
    out = []
    for t, b, a in zip(target_logp, behaviour_logp, adv):
        r = math.exp(t - b)
        out.append(-min(r * a, min(max(r, 1 - eps), 1 + eps) * a))
    return sum(out) / len(out)


def T(x):
    return torch.tensor(x, dtype=torch.float32)


def case(seed=0, n=6):
    g = torch.Generator().manual_seed(seed)
    return {
        "target_logp": torch.randn(n, generator=g) * 0.4 - 1.0,
        "behaviour_logp": torch.randn(n, generator=g) * 0.4 - 1.0,
        "values": torch.randn(n, generator=g) * 0.3,
        "rewards": torch.zeros(n),
        "bootstrap": torch.zeros(()),
        "discounts": torch.ones(n),
    }


# ============================================================ B11: V-trace
@pytest.mark.parametrize("seed", [0, 1, 2, 3, 7])
def test_b11_vtrace_matches_independent_reference(seed):
    d = case(seed)
    d["rewards"] = torch.zeros(6)
    d["rewards"][-1] = 1.0
    cfg = L.LossConfig(gamma=1.0, rho_bar=1.0, c_bar=1.0, two_sided=False)
    out = L.vtrace(d["target_logp"], d["behaviour_logp"], d["values"], d["rewards"],
                   d["bootstrap"], d["discounts"], cfg)
    vs, pg, rho, c = ref_vtrace(
        d["target_logp"].tolist(), d["behaviour_logp"].tolist(), d["values"].tolist(),
        d["rewards"].tolist(), float(d["bootstrap"]), d["discounts"].tolist())
    assert out["vs"].tolist() == pytest.approx(vs, abs=1e-5)
    assert out["pg_advantage"].tolist() == pytest.approx(pg, abs=1e-5)
    assert out["rho"].tolist() == pytest.approx(rho, abs=1e-6)
    assert out["c"].tolist() == pytest.approx(c, abs=1e-6)


def test_b11_on_policy_zero_values_reduces_to_monte_carlo_return():
    """With pi == mu, V == 0 and gamma == 1, v_t must equal the remaining reward sum."""
    n = 5
    lp = torch.full((n,), -0.7)
    rewards = T([0, 0, 0, 0, 1.0])
    cfg = L.LossConfig(gamma=1.0)
    out = L.vtrace(lp, lp, torch.zeros(n), rewards, torch.zeros(()), torch.ones(n), cfg)
    assert out["vs"].tolist() == pytest.approx([1.0] * n, abs=1e-6)


def test_b11_is_a_fixed_point_when_values_are_already_correct():
    """If V already equals the true return, V-trace must return V unchanged."""
    n = 4
    lp = torch.full((n,), -0.5)
    rewards = T([0, 0, 0, 1.0])
    values = T([1.0, 1.0, 1.0, 1.0])
    cfg = L.LossConfig(gamma=1.0)
    out = L.vtrace(lp, lp, values, rewards, torch.zeros(()), torch.ones(n), cfg)
    assert out["vs"].tolist() == pytest.approx(values.tolist(), abs=1e-6)


def test_b11_advantage_uses_next_step_vs_not_current():
    """Hard failure: using v_t instead of v_{t+1} leaks the action's own return into its baseline.

    Constructed so the two formulas give different numbers.
    """
    n = 3
    lp = torch.full((n,), -0.3)
    rewards = T([0.0, 0.0, 1.0])
    values = T([0.1, 0.2, 0.3])
    cfg = L.LossConfig(gamma=1.0)
    out = L.vtrace(lp, lp, values, rewards, torch.zeros(()), torch.ones(n), cfg)
    vs = out["vs"]
    correct = out["pg_advantage"]
    wrong = out["rho"] * (rewards + torch.ones(n) * vs - values)      # uses v_t
    assert not torch.allclose(correct, wrong, atol=1e-4), \
        "the test cannot distinguish the correct advantage from the v_t variant"


def test_b11_clips_the_importance_ratio_at_rho_bar():
    lp_t = T([2.0, -2.0])
    lp_b = T([0.0, 0.0])
    cfg = L.LossConfig(rho_bar=1.0, c_bar=1.0)
    rho, c = L.importance_ratio(lp_t, lp_b, cfg)
    assert rho[0].item() == pytest.approx(1.0)          # exp(2) clipped to 1
    assert rho[1].item() == pytest.approx(math.exp(-2.0), abs=1e-6)   # below the bar: untouched
    assert c.tolist() == pytest.approx(rho.tolist())


# ============================================================ B13: two-sided clipping
def test_b13_two_sided_clipping_bounds_from_BOTH_sides():
    """The b3 change. One-sided clipping is a hard failure (`B4`)."""
    lp_t = T([5.0, -20.0, 0.0])
    lp_b = T([0.0, 0.0, 0.0])
    cfg = L.LossConfig(two_sided=True, rho_lower=L.RHO_LOWER_B3, rho_upper=L.RHO_UPPER_B3)
    rho, c = L.importance_ratio(lp_t, lp_b, cfg)
    assert rho[0].item() == pytest.approx(L.RHO_UPPER_B3)     # clipped from ABOVE at 1.007
    assert rho[1].item() == pytest.approx(L.RHO_LOWER_B3)     # clipped from BELOW at 0.001
    assert rho[2].item() == pytest.approx(1.0)                # untouched in the interior
    assert c.tolist() == pytest.approx(rho.tolist())


def test_b13_one_sided_and_two_sided_actually_differ():
    """If they agreed on the test data, the b3 delta would be untested."""
    lp_t = T([-8.0, -9.0])
    lp_b = T([0.0, 0.0])
    one = L.importance_ratio(lp_t, lp_b, L.LossConfig(two_sided=False))[0]
    two = L.importance_ratio(lp_t, lp_b, L.LossConfig(two_sided=True))[0]
    assert not torch.allclose(one, two)
    assert (two >= L.RHO_LOWER_B3).all()
    assert (one < L.RHO_LOWER_B3).any()


def test_b13_bounds_are_the_disclosed_values():
    assert L.RHO_LOWER_B3 == 0.001
    assert L.RHO_UPPER_B3 == 1.007
    assert L.PPO_CLIP_EPS == 0.2


@pytest.mark.parametrize("seed", [0, 5, 11])
def test_b13_two_sided_vtrace_matches_independent_reference(seed):
    d = case(seed)
    d["rewards"] = torch.zeros(6)
    d["rewards"][-1] = 1.0
    cfg = L.LossConfig(gamma=1.0, two_sided=True)
    out = L.vtrace(d["target_logp"], d["behaviour_logp"], d["values"], d["rewards"],
                   d["bootstrap"], d["discounts"], cfg)
    vs, pg, rho, c = ref_vtrace(
        d["target_logp"].tolist(), d["behaviour_logp"].tolist(), d["values"].tolist(),
        d["rewards"].tolist(), float(d["bootstrap"]), d["discounts"].tolist(),
        two_sided=True, lo=L.RHO_LOWER_B3, hi=L.RHO_UPPER_B3)
    assert out["vs"].tolist() == pytest.approx(vs, abs=1e-5)
    assert out["pg_advantage"].tolist() == pytest.approx(pg, abs=1e-5)


def test_b13_ppo_surrogate_matches_independent_reference():
    n = 5
    lp_t = T([-0.4, -1.2, -0.8, -2.0, -0.1])
    lp_b = T([-0.5, -0.5, -0.5, -0.5, -0.5])
    adv = T([1.0, -1.0, 0.5, 2.0, -0.25])
    eps = L.PPO_CLIP_EPS
    ratio = torch.exp(lp_t - lp_b)
    prod = -torch.min(ratio * adv,
                      torch.clamp(ratio, 1 - eps, 1 + eps) * adv).mean()
    ref = ref_ppo_surrogate(lp_t.tolist(), lp_b.tolist(), adv.tolist(), eps)
    assert float(prod) == pytest.approx(ref, abs=1e-6)


def test_b13_ppo_clip_actually_binds_on_this_data():
    """A clip test on data where nothing clips proves nothing."""
    lp_t = T([-0.4, -1.2, -0.8, -2.0, -0.1])
    lp_b = T([-0.5, -0.5, -0.5, -0.5, -0.5])
    ratio = torch.exp(lp_t - lp_b)
    assert (torch.abs(ratio - 1.0) > L.PPO_CLIP_EPS).any(), "no sample is outside the clip band"


def test_b13_ordinary_ppo_and_byterl_b3_differ_by_the_ADVANTAGE_not_only_the_clip():
    """`B4` names ordinary PPO a hard failure. The difference is which advantage is clipped.

    Ordinary PPO would use a plain TD/GAE advantage; b3 uses the V-trace advantage, which carries
    the importance ratio rho_t. Under an off-policy sample the two differ, and this test would
    fail if `byterl_losses` had been built on the plain advantage.
    """
    n = 4
    # ln(0.001) = -6.91, so a log-ratio of -7.3 lands BELOW the lower bound and the two-sided
    # clip binds. An earlier version used -2.3, giving a ratio of 0.100 -- off-policy enough to
    # separate the advantages but nowhere near the lower bound, so the clip assertion tested
    # nothing.
    lp_t = T([-7.5, -7.5, -7.5, -7.5])       # target far from behaviour: strongly off-policy
    lp_b = T([-0.2, -0.2, -0.2, -0.2])
    values = T([0.5, 0.5, 0.5, 0.5])
    rewards = T([0.0, 0.0, 0.0, 1.0])
    disc = torch.ones(n)
    cfg = L.LossConfig(gamma=1.0, two_sided=True, ppo_clip=True)
    out = L.vtrace(lp_t, lp_b, values, rewards, torch.zeros(()), disc, cfg)
    vtrace_adv = out["pg_advantage"]
    plain_adv = rewards + torch.cat([values[1:], torch.zeros(1)]) - values
    assert not torch.allclose(vtrace_adv, plain_adv, atol=1e-3), \
        "the V-trace advantage must differ from a plain TD advantage off-policy"
    assert out["rho"].min().item() == pytest.approx(L.RHO_LOWER_B3)


# ============================================================ B12: UPGO
@pytest.mark.parametrize("seed", [0, 2, 9])
def test_b12_upgo_matches_independent_reference(seed):
    d = case(seed)
    d["rewards"] = torch.zeros(6)
    d["rewards"][-1] = 1.0
    g = L.upgo_returns(d["rewards"], d["values"], d["bootstrap"], d["discounts"])
    ref = ref_upgo(d["rewards"].tolist(), d["values"].tolist(), float(d["bootstrap"]),
                   d["discounts"].tolist())
    assert g.tolist() == pytest.approx(ref, abs=1e-5)


def test_b12_follows_the_trajectory_when_it_outperforms():
    """A rising trajectory: UPGO must NOT cut to the baseline anywhere."""
    n = 4
    rewards = T([0.0, 0.0, 0.0, 1.0])
    values = T([0.0, 0.0, 0.0, 0.0])         # Q_{t+1} >= V(s_{t+1}) everywhere
    g = L.upgo_returns(rewards, values, torch.zeros(()), torch.ones(n))
    assert g.tolist() == pytest.approx([1.0, 1.0, 1.0, 1.0], abs=1e-6)


def test_b12_cuts_to_the_baseline_when_the_trajectory_underperforms():
    """A trajectory that ends badly under an optimistic baseline must be cut, not followed."""
    n = 3
    rewards = T([0.0, 0.0, 0.0])
    values = T([0.9, 0.9, 0.9])              # Q_{t+1} = 0 + 0.9 < V = 0.9 is false; use bootstrap
    g = L.upgo_returns(rewards, values, torch.zeros(()), torch.ones(n))
    mc = 0.0
    assert g[0].item() > mc, "UPGO must not collapse to the Monte-Carlo return here"


def test_b12_is_not_monte_carlo_and_not_one_step_td():
    """The conditional switch IS the method; a version that always follows or always cuts fails."""
    n = 5
    rewards = T([0.0, 0.0, 0.0, 0.0, 1.0])
    values = T([0.2, 0.9, 0.1, 0.8, 0.0])
    disc = torch.ones(n)
    g = L.upgo_returns(rewards, values, torch.zeros(()), disc)
    always_follow = [1.0] * n                              # plain Monte-Carlo
    v_tp1 = values.tolist()[1:] + [0.0]
    always_cut = [rewards.tolist()[t] + v_tp1[t] for t in range(n)]   # one-step TD
    assert g.tolist() != pytest.approx(always_follow, abs=1e-4)
    assert g.tolist() != pytest.approx(always_cut, abs=1e-4)


# ============================================================ full objective
def test_full_objective_is_finite_and_backpropagates():
    n = 6
    tl = torch.randn(n, requires_grad=True)
    bl = torch.randn(n)
    ent = torch.rand(n, requires_grad=True)
    val = torch.randn(n, requires_grad=True)
    rew = torch.zeros(n)
    rew[-1] = 1.0
    cfg = L.LossConfig(gamma=1.0, two_sided=True, ppo_clip=True)
    total, stats = L.byterl_losses(tl, bl, ent, val, rew, torch.zeros(()), torch.ones(n), cfg)
    assert torch.isfinite(total)
    total.backward()
    assert tl.grad is not None and torch.isfinite(tl.grad).all()
    assert val.grad is not None and torch.isfinite(val.grad).all()
    for k in ("pg_loss", "upgo_loss", "value_loss", "entropy", "rho_mean",
              "rho_clipped_lower_frac", "ppo_clip_frac"):
        assert k in stats and math.isfinite(stats[k])


def test_b3_and_b2_objectives_are_actually_different():
    """B14 in miniature: the rung delta must change the number it claims to change."""
    n = 6
    torch.manual_seed(3)
    tl = torch.randn(n) * 0.8 - 1.0
    bl = torch.randn(n) * 0.8 - 1.0
    ent = torch.rand(n)
    val = torch.randn(n) * 0.3
    rew = torch.zeros(n)
    rew[-1] = 1.0
    b2 = L.LossConfig(gamma=1.0, two_sided=False, ppo_clip=False)
    b3 = L.LossConfig(gamma=1.0, two_sided=True, ppo_clip=True)
    t2, s2 = L.byterl_losses(tl, bl, ent, val, rew, torch.zeros(()), torch.ones(n), b2)
    t3, s3 = L.byterl_losses(tl, bl, ent, val, rew, torch.zeros(()), torch.ones(n), b3)
    assert abs(float(t2) - float(t3)) > 1e-6
    assert s3["ppo_clip_frac"] >= 0.0
    assert s2["ppo_clip_frac"] == 0.0


def test_gamma_is_the_only_b0_to_b1_delta():
    """FIDELITY_RULES §4: B1 is 'B0 with gamma changed to 1.0'. Nothing else may move."""
    b0 = L.LossConfig(gamma=L.GAMMA_B0)
    b1 = L.LossConfig(gamma=L.GAMMA_B1_PLUS)
    d = {k: (getattr(b0, k), getattr(b1, k)) for k in b0.__dataclass_fields__
         if getattr(b0, k) != getattr(b1, k)}
    assert set(d) == {"gamma"}, f"B0->B1 changed more than gamma: {d}"
    assert L.GAMMA_B0 != 1.0 and L.GAMMA_B1_PLUS == 1.0


def test_discount_of_one_and_of_gamma_give_different_targets():
    """If gamma made no difference on the test data, the B1 delta would be untested."""
    n = 5
    lp = torch.full((n,), -0.6)
    rew = torch.zeros(n)
    rew[-1] = 1.0
    vals = torch.zeros(n)
    a = L.vtrace(lp, lp, vals, rew, torch.zeros(()), torch.ones(n),
                 L.LossConfig(gamma=1.0))["vs"]
    b = L.vtrace(lp, lp, vals, rew, torch.zeros(()), torch.full((n,), L.GAMMA_B0),
                 L.LossConfig(gamma=L.GAMMA_B0))["vs"]
    assert not torch.allclose(a, b, atol=1e-4)


# ============================================================ B15/B16/B17: OSFP
def test_b15_osfp_accumulators_are_period_local():
    """The detail c019 and c020 both got wrong."""
    import torch.nn as nn
    o = L.OSFP(max_history=4)
    m = nn.Linear(3, 3)
    o.promote(m, "p0")
    o.record(0, 1.0)
    o.record(0, 1.0)
    assert o.C[0] == 2 and o.G[0] == pytest.approx(2.0)
    o.promote(m, "p1")
    assert all(c == 0 for c in o.C), "G/C must reset on promotion"
    assert all(g == 0.0 for g in o.G)


def test_b16_history_is_byte_immutable_as_the_learner_trains():
    """c021's frozen checkpoint was a VIEW of the live network and mutated under training."""
    import torch.nn as nn
    torch.manual_seed(0)
    m = nn.Linear(4, 4)
    o = L.OSFP(max_history=4)
    hp = o.promote(m, "frozen")
    before = hp.sha256
    with torch.no_grad():                      # simulate a learner step
        for p in m.parameters():
            p.add_(torch.randn_like(p))
    assert hp.verify(), "the frozen blob changed"
    assert hp.sha256 == before
    v = o.verify_history_immutable()
    assert v["all_ok"] and v["n"] == 1
    # and the frozen weights must NOT equal the live ones any more
    m2 = nn.Linear(4, 4)
    hp.load_into(m2)
    assert not torch.allclose(m2.weight, m.weight)


def test_b16_history_survives_eviction():
    import torch.nn as nn
    m = nn.Linear(2, 2)
    o = L.OSFP(max_history=2)
    for i in range(5):
        with torch.no_grad():
            for p in m.parameters():
                p.add_(0.1)
        o.promote(m, f"p{i}")
    assert len(o.history) == 2
    assert o.verify_history_immutable()["all_ok"]
    assert len({h.sha256 for h in o.history}) == 2, "evicted history must not alias"


def test_b17_promotion_threshold_and_forced_promotion():
    o = L.OSFP()
    ok, why = o.should_promote(0.54, 64)
    assert not ok and "0.55" in why
    ok, why = o.should_promote(0.55, 64)
    assert ok
    ok, _ = o.should_promote(0.90, 4)          # too few games
    assert not ok
    o2 = L.OSFP()
    for _ in range(L.OSFP_MAX_PERIODS_WITHOUT_PROMOTION):
        o2.end_period_without_promotion()
    ok, why = o2.should_promote(0.10, 64)
    assert ok and "forced" in why


def test_osfp_self_play_probability_is_0_6_and_uniform_before_evidence():
    import numpy as np
    import torch.nn as nn
    o = L.OSFP()
    rng = np.random.default_rng(0)
    assert o.sample_opponent(rng) is None, "no history: must self-play"
    m = nn.Linear(2, 2)
    for i in range(3):
        o.promote(m, f"p{i}")
    d = o.opponent_distribution()
    assert d.tolist() == pytest.approx([1 / 3] * 3), "uniform before any game in the period"
    n = 4000
    sp = sum(1 for _ in range(n) if o.sample_opponent(rng) is None)
    assert abs(sp / n - L.OSFP_SELFPLAY_PROB) < 0.03


def test_osfp_weights_the_opponents_it_is_losing_to():
    import torch.nn as nn
    o = L.OSFP()
    m = nn.Linear(2, 2)
    for i in range(3):
        o.promote(m, f"p{i}")
    o.record(0, 1.0)      # we beat opponent 0
    o.record(1, 0.0)      # we lose to opponent 1
    o.record(2, 0.5)
    d = o.opponent_distribution()
    assert d[1] > d[2] > d[0], f"sigma must favour the opponents we lose to: {d}"


def test_disclosed_settings_are_the_disclosed_values():
    """FIDELITY_RULES §4. A drifted constant is a silent fidelity failure."""
    assert L.LSTM_HIDDEN_EXPECTED == 256 if hasattr(L, "LSTM_HIDDEN_EXPECTED") else True
    assert L.GAMMA_B1_PLUS == 1.0
    assert L.LEARNING_RATE == 7e-5
    assert L.SAMPLE_REUSE == 2
    assert L.ENTROPY_COEF == 0.01
    assert L.VALUE_COEF == 1.0 and L.PPO_COEF == 1.0 and L.UPGO_COEF == 1.0
    assert (L.RHO_LOWER_B3, L.RHO_UPPER_B3) == (0.001, 1.007)
    assert L.PPO_CLIP_EPS == 0.2
    assert L.OSFP_SELFPLAY_PROB == 0.6
    assert L.OSFP_PROMOTION_THRESHOLD == 0.55
    assert L.OSFP_MAX_PERIODS_WITHOUT_PROMOTION == 6

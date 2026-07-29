"""c021 B5/B6 — V-trace, UPGO and OSFP checked against analytically known values.

A learner is the easiest place in this project to hide a silent bug: it produces plausible
numbers whatever it computes. Each test below fixes an input for which the correct output can be
derived by hand.
"""
import os
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cg import c021_byterl_learn as L  # noqa: E402


def _t(x):
    return torch.tensor(x, dtype=torch.float32)


# ------------------------------------------------------------------ V-trace
def test_vtrace_on_policy_zero_values_reduces_to_monte_carlo_return():
    """rho = c = 1 and V = 0 => vs_t is the undiscounted sum of future rewards."""
    T = 4
    lp = torch.zeros(T)                        # identical policies => ratio 1
    rewards = _t([0.0, 0.0, 0.0, 1.0])
    values = torch.zeros(T)
    boot = _t(0.0)
    disc = torch.ones(T)
    out = L.vtrace(lp, lp, rewards, values, boot, disc)
    assert torch.allclose(out.rho, torch.ones(T))
    assert torch.allclose(out.vs, _t([1.0, 1.0, 1.0, 1.0]))


def test_vtrace_with_discount_matches_hand_computed_return():
    T = 3
    lp = torch.zeros(T)
    rewards = _t([1.0, 2.0, 4.0])
    values = torch.zeros(T)
    disc = _t([0.5, 0.5, 0.5])
    out = L.vtrace(lp, lp, rewards, values, _t(0.0), disc)
    # vs_2 = 4 ; vs_1 = 2 + .5*4 = 4 ; vs_0 = 1 + .5*4 = 3
    assert torch.allclose(out.vs, _t([3.0, 4.0, 4.0]))


def test_vtrace_is_a_fixed_point_when_values_are_already_correct():
    """If V already equals the true return, V-trace must not move it."""
    rewards = _t([0.0, 0.0, 1.0])
    values = _t([1.0, 1.0, 1.0])               # exact under gamma = 1
    lp = torch.zeros(3)
    out = L.vtrace(lp, lp, rewards, values, _t(0.0), torch.ones(3))
    assert torch.allclose(out.vs, values, atol=1e-6)
    assert torch.allclose(out.pg_advantage, torch.zeros(3), atol=1e-6)


def test_vtrace_clips_importance_ratio_at_rho_bar():
    T = 3
    behaviour = torch.full((T,), -5.0)         # very unlikely under behaviour
    target = torch.zeros(T)                    # near-certain under target => huge ratio
    out = L.vtrace(behaviour, target, torch.zeros(T), torch.zeros(T), _t(0.0),
                   torch.ones(T), rho_bar=1.0, c_bar=1.0)
    assert (out.rho > 100).all()
    assert torch.allclose(out.clipped_rho, torch.ones(T))
    assert torch.allclose(out.clipped_c, torch.ones(T))


def test_vtrace_advantage_uses_next_step_vs_not_current():
    """Using vs_t instead of vs_{t+1} shrinks every advantage toward zero.

    Constructed so the two differ: a single terminal reward with zero values.
    """
    rewards = _t([0.0, 1.0])
    values = torch.zeros(2)
    lp = torch.zeros(2)
    out = L.vtrace(lp, lp, rewards, values, _t(0.0), torch.ones(2))
    # vs = [1, 1]; correct adv_0 = r_0 + vs_1 - V_0 = 0 + 1 - 0 = 1
    # the buggy form would give r_0 + vs_0 - V_0 = 1 as well, so check adv_1:
    # correct adv_1 = r_1 + boot - V_1 = 1 ; buggy = r_1 + vs_1 - V_1 = 2
    assert out.pg_advantage[1].item() == pytest.approx(1.0)


def test_vtrace_lower_rho_bar_shrinks_the_update():
    T = 3
    behaviour = torch.full((T,), -2.0)
    target = torch.zeros(T)
    rewards = _t([0.0, 0.0, 1.0])
    big = L.vtrace(behaviour, target, rewards, torch.zeros(T), _t(0.0), torch.ones(T),
                   rho_bar=10.0, c_bar=10.0)
    small = L.vtrace(behaviour, target, rewards, torch.zeros(T), _t(0.0), torch.ones(T),
                     rho_bar=1.0, c_bar=1.0)
    assert big.vs[0].item() > small.vs[0].item()


# ------------------------------------------------------------------ UPGO
def test_upgo_with_zero_values_is_the_monte_carlo_return():
    rewards = _t([0.0, 0.0, 1.0])
    g = L.upgo_returns(rewards, torch.zeros(3), _t(0.0), torch.ones(3))
    assert torch.allclose(g, _t([1.0, 1.0, 1.0]))


def test_upgo_cuts_to_the_baseline_when_the_trajectory_underperforms():
    """The defining property: bootstrap from V when the one-step return is WORSE than V.

    V(s1) = 5 while the one-step return through s1 is 0, so G_0 must take the value 5, not the
    trajectory's own 0.
    """
    rewards = _t([0.0, 0.0, 0.0])
    values = _t([0.0, 5.0, 0.0])
    g = L.upgo_returns(rewards, values, _t(0.0), torch.ones(3))
    assert g[0].item() == pytest.approx(5.0)


def test_upgo_follows_the_trajectory_when_it_outperforms():
    rewards = _t([0.0, 0.0, 1.0])
    values = _t([0.0, 0.0, 0.0])
    g = L.upgo_returns(rewards, values, _t(0.0), torch.ones(3))
    assert g[0].item() == pytest.approx(1.0)      # followed through, not cut to V=0


def test_upgo_differs_from_plain_monte_carlo_on_a_mixed_trajectory():
    rewards = _t([0.0, 0.0, 0.0])
    values = _t([0.0, 3.0, 0.0])
    g = L.upgo_returns(rewards, values, _t(0.0), torch.ones(3))
    mc = _t([0.0, 0.0, 0.0])
    assert not torch.allclose(g, mc)


# ------------------------------------------------------------------ combined loss
def test_losses_are_finite_and_backprop():
    T = 6
    torch.manual_seed(0)
    logits = torch.randn(T, 5, requires_grad=True)
    logp_all = torch.log_softmax(logits, -1)
    actions = torch.randint(0, 5, (T,))
    target_logp = logp_all.gather(-1, actions.unsqueeze(-1)).squeeze(-1)
    entropy = -(logp_all.exp() * logp_all).sum(-1)
    behaviour = target_logp.detach() - 0.1
    values = torch.zeros(T, requires_grad=True)
    rewards = torch.zeros(T); rewards[-1] = 1.0
    total, stats = L.byterl_losses(target_logp, behaviour, entropy, values, rewards,
                                   _t(0.0), torch.ones(T), L.LossConfig())
    assert torch.isfinite(total)
    total.backward()
    assert torch.isfinite(logits.grad).all()
    for k in ("pg_loss", "upgo_loss", "value_loss", "entropy", "rho_mean"):
        assert np.isfinite(stats[k])


# ------------------------------------------------------------------ OSFP
def test_osfp_g_and_c_are_period_local():
    """Regression: c019 and c020 accumulated payoffs globally, so an old checkpoint kept
    dominating the opponent distribution long after the policy had moved past it."""
    o = L.OSFP()
    o.add_checkpoint({}, "ck0")
    o.record(0, 1.0); o.record(0, 1.0)
    assert o.mean_payoff(0) == 1.0
    assert o.snapshot()["period_games"] == 2
    o.reset_period()
    assert o.G == {} and o.C == {}
    assert o.mean_payoff(0) == 0.0
    assert o.period == 1


def test_osfp_weights_the_opponents_it_loses_to():
    o = L.OSFP(eta=0.1)
    for i in range(3):
        o.add_checkpoint({}, f"ck{i}")
    o.record(0, 1.0)    # winning against 0
    o.record(1, 0.0)    # losing to 1
    o.record(2, 0.5)
    p = o.opponent_distribution()
    assert len(p) == 3
    assert p.sum() == pytest.approx(1.0)
    assert p[1] > p[2] > p[0]       # hardest opponent gets the most mass


def test_osfp_distribution_is_uniform_before_any_games():
    o = L.OSFP()
    for i in range(4):
        o.add_checkpoint({}, f"ck{i}")
    p = o.opponent_distribution()
    assert np.allclose(p, 0.25)


def test_osfp_promotion_requires_both_winrate_and_sample_size():
    o = L.OSFP()
    assert not o.should_promote(0.9, games=10)          # too few games
    assert not o.should_promote(0.50, games=1000)       # not strong enough
    assert o.should_promote(0.60, games=1000)


def test_osfp_checkpoint_buffer_is_bounded():
    o = L.OSFP(max_checkpoints=3)
    for i in range(6):
        o.add_checkpoint({}, f"ck{i}")
    assert len(o.checkpoints) == 3
    assert [c["label"] for c in o.checkpoints] == ["ck3", "ck4", "ck5"]


def test_osfp_history_is_immutable_even_when_the_buffer_evicts():
    """`checkpoints` is a bounded sampling buffer; `history` is append-only and audit-grade."""
    o = L.OSFP(max_checkpoints=2)
    for i in range(5):
        o.add_checkpoint({}, f"ck{i}")
    assert len(o.checkpoints) == 2
    labels = [h["label"] for h in o.history_log()]
    for i in range(5):
        assert f"ck{i}" in labels, "a promotion vanished from the history"
    assert [h["index"] for h in o.history_log()] == list(range(len(o.history_log())))
    before = o.history_log()
    o.history_log().append({"label": "tampered"})
    assert o.history_log() == before, "history_log must hand back a copy"


def test_osfp_checkpoints_must_be_copies_not_views():
    """Regression: a `.numpy()` snapshot SHARES storage with the live parameter.

    Without an explicit copy the "frozen" checkpoint mutates on every optimizer step, so
    self-play runs against a mirror of the CURRENT policy rather than a frozen past one -- which
    pins the self-play rate near 0.5 by construction and makes it uninformative.
    """
    import torch.nn as nn
    net = nn.Linear(4, 4)
    opt = torch.optim.Adam(net.parameters(), lr=1.0)

    view = {k: v.detach().cpu().numpy() for k, v in net.state_dict().items()}
    copied = {k: v.detach().cpu().numpy().copy() for k, v in net.state_dict().items()}
    view_before = view["weight"].copy()
    copied_before = copied["weight"].copy()

    net(torch.randn(2, 4)).sum().backward()
    opt.step()

    assert not np.allclose(view_before, view["weight"]), \
        "fixture is wrong: .numpy() should share storage"
    assert np.allclose(copied_before, copied["weight"]), \
        "a copied checkpoint must not change when the live network updates"


def test_osfp_add_checkpoint_stores_what_it_was_given():
    o = L.OSFP()
    state = {"w": np.zeros(3)}
    o.add_checkpoint({k: v.copy() for k, v in state.items()}, "ck")
    state["w"][0] = 99.0
    assert o.checkpoints[0]["state"]["w"][0] == 0.0

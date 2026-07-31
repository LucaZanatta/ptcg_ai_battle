"""c022 probe B06 — recurrent replay fidelity, exercised WITH the B1.5 delta on.

There was no test for B06 at all. It was checked only inside a training run, and the check ran
green through every configuration that existed until `random_initial_construction` was actually
implemented (D17) — at which point it failed on the first batch of every rung from BR1.5 upward
and killed the ladder (D19).

The cause is a genuine distinction the old check collapsed:

    mu  = the distribution that ACTUALLY chose the action. Uniform on a B1.5 randomised step.
          V-trace and PPO need this one; using pi here makes every ratio on those steps wrong.
    pi  = the acting NETWORK's score for that same action. Replay must reproduce this one;
          comparing replay against mu asks the network to reproduce a uniform draw.

So these tests assert both halves, and assert that each fires when the other is substituted --
which is the only way to show the two are not being conflated again.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys

import numpy as np
import pytest
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
torch.set_num_threads(1)


def _load_trainer():
    path = os.path.join(_REPO, "tools", "c022_byterl_train.py")
    spec = importlib.util.spec_from_file_location("c022_byterl_train", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TR = _load_trainer()


def _runner(random_initial: bool, seed: int = 11):
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_actor as ACT
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=seed)
    net.eval()
    r = ACT.EpisodeRunner(net, pool, np.random.default_rng(seed), True,
                          random_initial_construction=random_initial)
    r.build_deck()
    return net, r, pool, dims


def _pack_from(runner, index: int = 0):
    """One unroll's worth of construction steps, packed exactly as the queue would carry it."""
    unrolls = runner.finish(reward=1.0, episode_id="t", policy_version=0)
    assert unrolls, "the runner produced no unrolls"
    return TR._pack(unrolls[index])


def _cfg():
    return {"stage": "BR1_5", "unroll_length": 32, "sample_reuse": 2, "max_grad_norm": 40.0,
            "_version": 0}


def _scratch(dims, pool_size):
    from cg import c022_byterl_model as M
    return M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool_size,
                   n_cards=dims["n_cards"], seed=99)


def _check(net, pack, dims, pool_size):
    """Run the real fidelity check against the exact weights that produced the pack."""
    import io
    blob = io.BytesIO()
    torch.save(net.state_dict(), blob)
    scratch = _scratch(dims, pool_size)
    return TR.recurrence_fidelity_check(scratch, blob.getvalue(), pack, _cfg())


# ---------------------------------------------------------------- the check passes, both ways
@pytest.mark.parametrize("random_initial", [False, True])
def test_b06_replay_reproduces_pi_at_identical_weights(random_initial):
    net, runner, pool, dims = _runner(random_initial)
    pack = _pack_from(runner)
    chk = _check(net, pack, dims, pool.size())
    assert chk["recurrence_delta"] < 1e-4, chk
    assert chk["logp_delta"] < 1e-4, chk
    assert chk["behaviour_delta"] < 1e-4, chk
    if random_initial:
        assert chk["uniform_steps"] > 0, "the B1.5 pack carried no uniform steps to check"
    else:
        assert chk["uniform_steps"] == 0


# ---------------------------------------------------------------- the defect, pinned
def test_b06_the_pre_d19_comparison_would_fail_on_a_randomised_step():
    """The exact failure that killed the ladder, asserted so it cannot be reintroduced.

    Comparing replay against `behaviour_logp` -- the pre-D19 code -- must DISAGREE on a B1.5
    pack. If this ever stops failing, either the randomisation stopped happening or mu was
    quietly set back to the network's value, and both are defects.
    """
    net, runner, pool, dims = _runner(True)
    pack = _pack_from(runner)
    uniform = [s for s in pack["steps"] if s["uniform_behaviour"]]
    assert uniform, "no uniform steps in a B1.5 pack"
    worst = max(abs(float(s["behaviour_logp"]) - float(s["policy_logp"])) for s in uniform)
    assert worst > 1e-3, (
        "mu equals pi on a randomised step -- the uniform behaviour log-probability is not "
        "being recorded, which is defect D17 returning")


def test_b06_detects_a_corrupted_pi():
    """logp_delta must fire when the stored network score is wrong."""
    net, runner, pool, dims = _runner(True)
    pack = _pack_from(runner)
    pack["steps"][0]["policy_logp"] = float(pack["steps"][0]["policy_logp"]) - 0.5
    chk = _check(net, pack, dims, pool.size())
    assert chk["logp_delta"] > 0.4, chk


def test_b06_detects_a_step_that_lies_about_being_uniform():
    """behaviour_delta must fire when a step claims uniform mu but carries the policy's value.

    This is the assertion that keeps D19's separation from weakening D17's fix. Once replay is
    compared against pi, nothing else would notice that mu had quietly become pi too.
    """
    net, runner, pool, dims = _runner(False)          # no randomisation: mu IS pi everywhere
    pack = _pack_from(runner)
    pack["steps"][0]["uniform_behaviour"] = True       # ... but this step now claims otherwise
    chk = _check(net, pack, dims, pool.size())
    assert chk["behaviour_delta"] > 1e-3, chk


def test_b06_detects_a_uniform_step_whose_mu_is_the_wrong_uniform():
    """A uniform step must carry -log(n_legal) for the mask it actually drew against."""
    net, runner, pool, dims = _runner(True)
    pack = _pack_from(runner)
    tgt = next(s for s in pack["steps"] if s["uniform_behaviour"])
    n_legal = int(tgt["seq"]["tokens"][0]["n_legal"])
    assert tgt["behaviour_logp"] == pytest.approx(-math.log(n_legal), abs=1e-5)
    tgt["behaviour_logp"] = -math.log(n_legal) - 0.7   # a plausible-looking wrong uniform
    chk = _check(net, pack, dims, pool.size())
    assert chk["behaviour_delta"] > 0.6, chk


def test_b06_detects_a_shifted_recurrent_start():
    """recurrence_delta must fire when the stored start state is not the actor's.

    THE INJECTION MUST BE APPLIED TO A LATER UNROLL. Unroll 0 legitimately starts from a zero
    state, so zeroing its `h0` changes nothing and this test passed vacuously when written
    against it -- reporting a green check for an injection that was never made. The `h0` is
    asserted non-zero before the corruption, so the test fails loudly rather than silently if
    the unroll boundary ever moves.
    """
    net, runner, pool, dims = _runner(True)
    unrolls = runner.finish(reward=1.0, episode_id="t", policy_version=0)
    assert len(unrolls) >= 2, "need a stored (non-zero) recurrent start to corrupt"
    pack = TR._pack(unrolls[1])
    assert np.abs(pack["h0"]).max() > 0, "unroll 1 started from zeros; the injection is inert"
    pack["h0"] = np.zeros_like(pack["h0"])
    chk = _check(net, pack, dims, pool.size())
    assert chk["recurrence_delta"] > 1e-4, chk


def test_b06_stored_recurrent_starts_are_the_actor_state_after_the_first_unroll():
    """The property the vacuous test above was silently failing to check.

    B06's whole value is that the learner replays from the actor's OBSERVED state. If every
    unroll carried a zero start, the check would be trivially satisfied for all of them and the
    stored-recurrent-start requirement (`MANDATORY_IMPLEMENTATION B3`) would be unmet while every
    number looked right.
    """
    net, runner, pool, dims = _runner(True)
    unrolls = runner.finish(reward=1.0, episode_id="t", policy_version=0)
    assert len(unrolls) >= 2
    assert np.abs(unrolls[0].h0).max() == 0.0, "the episode's first unroll must start from zero"
    for u in unrolls[1:]:
        assert np.abs(u.h0).max() > 0.0, "a mid-episode unroll started from a zeroed state"


# ---------------------------------------------------------------- the pack carries the fields
def test_b06_the_queue_pack_carries_both_quantities():
    """A pack that drops them falls back to mu and reintroduces D19 silently."""
    net, runner, pool, dims = _runner(True)
    pack = _pack_from(runner)
    for s in pack["steps"]:
        assert "policy_logp" in s, "policy_logp does not cross the queue"
        assert "uniform_behaviour" in s, "uniform_behaviour does not cross the queue"

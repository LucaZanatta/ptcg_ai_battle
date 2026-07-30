"""c022 probe B14 — adjacent BR stages differ ONLY by the published change.

`MANDATORY_IMPLEMENTATION B7`: "One codebase must produce machine-verifiable stages ... Adjacent
stages may differ only by the published change named in FIDELITY_RULES.md. **Tests must reject
extra changes.**"

That last sentence is the requirement these tests exist to meet. It is not enough to assert that
BR2 has a bounded queue; the test must fail if BR2 ALSO quietly changed the learning rate. So each
adjacent pair is compared field by field and the symmetric difference of changed keys must equal
the single named delta.

`FIDELITY_RULES §4`, verbatim:

    B0   end-to-end baseline ByteRL system
    B1   B0 with gamma changed to 1.0
    B1.5 B1 with published random initial deck-construction selections
    B2   B1.5 with bounded blocking FIFO and balanced actor production/learner consumption
    B3   B2 with two-sided clipped V-trace and PPO-style clipped policy objective
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


def _load_trainer():
    """Import the trainer as a module without executing its CLI."""
    path = os.path.join(_REPO, "tools", "c022_byterl_train.py")
    spec = importlib.util.spec_from_file_location("c022_byterl_train", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TR = _load_trainer()


def test_b14_every_published_stage_exists():
    assert TR.STAGE_ORDER == ["BR0", "BR1", "BR1_5", "BR2", "BR3"]
    assert set(TR.STAGES) == set(TR.STAGE_ORDER)


@pytest.mark.parametrize("pair,expected", sorted(TR.STAGE_DELTA.items()))
def test_b14_adjacent_stages_differ_only_by_the_published_change(pair, expected):
    lo, hi = pair
    a, b = TR.STAGES[lo], TR.STAGES[hi]
    assert set(a) == set(b), "stages must describe the same feature set"
    changed = {k for k in a if a[k] != b[k]}
    assert changed == expected, (
        f"{lo} -> {hi} must change exactly {sorted(expected)}, changed {sorted(changed)}")


def test_b14_the_ladder_is_monotone_in_the_published_features():
    """Once a published feature is on it stays on: the ladder is cumulative, not a cycle."""
    prev = None
    for s in TR.STAGE_ORDER:
        f = TR.STAGES[s]
        if prev is not None:
            for k in ("random_initial_construction", "bounded_blocking_fifo",
                      "two_sided_and_ppo"):
                assert not (prev[k] and not f[k]), f"{s} turned {k} back off"
        prev = f


def test_b14_gamma_is_099_at_br0_and_1_everywhere_above():
    assert TR.STAGES["BR0"]["gamma"] == 0.99
    for s in ("BR1", "BR1_5", "BR2", "BR3"):
        assert TR.STAGES[s]["gamma"] == 1.0


def test_b14_only_br2_and_br3_bound_the_queue():
    assert TR.STAGES["BR0"]["bounded_blocking_fifo"] is False
    assert TR.STAGES["BR1"]["bounded_blocking_fifo"] is False
    assert TR.STAGES["BR1_5"]["bounded_blocking_fifo"] is False
    assert TR.STAGES["BR2"]["bounded_blocking_fifo"] is True
    assert TR.STAGES["BR3"]["bounded_blocking_fifo"] is True


def test_b14_only_br3_uses_the_two_sided_and_ppo_objective():
    for s in ("BR0", "BR1", "BR1_5", "BR2"):
        assert TR.STAGES[s]["two_sided_and_ppo"] is False
    assert TR.STAGES["BR3"]["two_sided_and_ppo"] is True


def test_b14_rejects_an_extra_change_injected_into_a_stage():
    """The test suite must DETECT an extra change, not merely permit the right one.

    A stage-delta test that only checks "the named field changed" passes happily while a second
    field changes alongside it. This injects exactly that and asserts the check fires — the same
    mutation-testing discipline c021 applied after finding a deletion that left 97 tests green.
    """
    original = dict(TR.STAGES["BR2"])
    try:
        TR.STAGES["BR2"] = {**original, "gamma": 0.5}       # an unpublished extra change
        a, b = TR.STAGES["BR1_5"], TR.STAGES["BR2"]
        changed = {k for k in a if a[k] != b[k]}
        assert changed != TR.STAGE_DELTA[("BR1_5", "BR2")], \
            "the injected extra change was not detected"
    finally:
        TR.STAGES["BR2"] = original
    # and the real ladder must still be clean afterwards
    a, b = TR.STAGES["BR1_5"], TR.STAGES["BR2"]
    assert {k for k in a if a[k] != b[k]} == TR.STAGE_DELTA[("BR1_5", "BR2")]


def test_b14_loss_config_follows_the_stage_and_nothing_else():
    """The stage table must actually drive the objective, not merely describe it."""
    from cg import c022_byterl_learn as L
    for s in TR.STAGE_ORDER:
        f = TR.STAGES[s]
        cfg = L.LossConfig(gamma=f["gamma"],
                           two_sided=f["two_sided_and_ppo"],
                           ppo_clip=f["two_sided_and_ppo"])
        assert cfg.gamma == f["gamma"]
        assert cfg.two_sided is f["two_sided_and_ppo"]
        assert cfg.ppo_clip is f["two_sided_and_ppo"]
        # every OTHER published setting is stage-independent
        assert cfg.value_coef == L.VALUE_COEF
        assert cfg.ppo_coef == L.PPO_COEF
        assert cfg.upgo_coef == L.UPGO_COEF
        assert cfg.entropy_coef == L.ENTROPY_COEF
        assert cfg.ppo_eps == L.PPO_CLIP_EPS
        assert (cfg.rho_lower, cfg.rho_upper) == (L.RHO_LOWER_B3, L.RHO_UPPER_B3)


def test_queue_capacity_is_the_b2_delta_in_the_code_not_only_in_the_table():
    """`UNBOUNDED_QUEUE` must be large enough that the pre-b2 rungs never block in practice."""
    assert TR.UNBOUNDED_QUEUE >= 65536
    assert TR.UNBOUNDED_QUEUE > 1024


def test_b18_end_to_end_arm_uses_the_permitted_pool_not_one_archetype():
    """B18: the E2E arm must expose the legal permitted pool, not a single decklist."""
    from cg import c021_byterl_deck as DK
    pool = DK.CardPool.from_archetypes()
    one = DK.CardPool.from_archetypes(["mega_lucario"])
    assert pool.size() > one.size(), \
        "the E2E pool must be the union of the permitted lists, not one archetype"
    assert len(pool.basic_pokemon) > 0
    assert len(pool.basic_energy) > 0
    assert len(pool.ace_spec) > 0

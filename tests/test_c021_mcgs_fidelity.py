"""c021 — source-fidelity fixtures for the MCGS port.

These assert the CONSTANTS and FORMULAS transcribed from the official 2019 archive, plus the A4
invariants. A fidelity claim that no test can fail is not evidence.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cg import c021_mcgs as S      # noqa: E402
from cg import c021_mcgs_graph as G  # noqa: E402


# ------------------------------------------------------------------ source constants
def test_source_constants_match_the_shipped_config():
    assert G.UCT_CONSTANT == 0.285
    assert G.SAMPLE_WIDTH == 24
    assert G.DAMPING_PARAMETER == 2.0
    assert G.DETERMINIZATION_NUMBER == 200
    assert G.FIRST_MOVE_SECONDS == 15.0 and G.CONTINUING_MOVE_SECONDS == 10.0
    assert G.STORE_VISITS_AT_EDGES and G.SIMPLE_ABSTRACTION and G.TRANSPOSITION
    assert G.DAMPED_SAMPLING
    assert G.CHANCE_SPARSE_THRESHOLD == 5
    assert G.ROLLOUT_STEP_CAP == 1000 and G.ROLLOUT_TURN_CAP == 45 and G.ROLLOUT_RETRIES == 5


def test_pimc_stays_false():
    """`PIMC` is NOT a local branch selector.

    The PTCG API forces root-only determinization, which resembles the source's PIMC regime, and
    it is tempting to flip this flag. Do not: the same flag also gates a reward sign flip in
    `Node.Update`, disables `Node.Finalise`, and selects the END_TURN expansion path. Flipping it
    to justify one chance-node decision silently changes three unrelated behaviours. The port is
    the `!PIMC` configuration minus the interior-determinization operations the API does not
    expose -- see results/fidelity/A4_chance_node_api_constraint.md.
    """
    assert G.PIMC is False


def test_ucd_default_recursion_is_inert():
    assert G.UCDParams(1, 0).recursion_is_active is False
    assert G.UCDParams(2, 0).recursion_is_active is True
    assert G.UCDParams(1, 1).recursion_is_active is True
    with pytest.raises(ValueError):
        G.UCDParams(0, 0)


# ------------------------------------------------------------------ UCB1, not PUCT
def test_edge_value_is_ucb1_with_no_prior_term():
    p = G.Node(); c = G.Node()
    p.total_visit = 100; p.visit_count = 40
    c.visit_count = 10; c.rewards = 4.0
    e = G.Edge.connect(p, c, 0)
    e.visit_count = 10
    assert e.value(0.0) == pytest.approx(0.4)
    expected = 0.4 + 0.285 * math.sqrt(2.0 * math.log(100) / 10)   # ln of TOTAL_VISIT under UCD
    assert e.value(0.285) == pytest.approx(expected)
    # and NOT the PUCT form, which would use sqrt(N)/(1+n) times a prior
    assert e.value(0.285) != pytest.approx(0.4 + 0.285 * math.sqrt(100) / 11)


def test_edge_value_uses_total_visit_under_ucd_not_visit_count():
    p = G.Node(); c = G.Node()
    p.total_visit = 1000; p.visit_count = 10
    c.visit_count = 5; c.rewards = 0.0
    e = G.Edge.connect(p, c, 0); e.visit_count = 5
    ucd = e.value(0.285, ucd=True)
    plain = e.value(0.285, ucd=False)
    assert ucd > plain
    assert ucd == pytest.approx(0.285 * math.sqrt(2 * math.log(1000) / 5))


def test_unvisited_edge_dominates():
    p = G.Node(); c = G.Node(); p.total_visit = 50
    e = G.Edge.connect(p, c, 0)
    assert e.value(0.285) == float("inf")


def test_terminal_values_are_plus_minus_ten_not_one_zero():
    w = G.Node(is_terminal=True, play_state="WON")
    l = G.Node(is_terminal=True, play_state="LOST")
    d = G.Node(is_terminal=True, play_state=None)
    assert w.value(0.0) == 10.0 and l.value(0.0) == -10.0 and d.value(0.0) == 0.0


def test_opponent_node_flips_reward_sign():
    n = G.Node(is_opponent=True)
    n.update(1.0)
    assert n.rewards == -1.0 and n.visit_count == 1
    m = G.Node(is_opponent=False)
    m.update(1.0)
    assert m.rewards == 1.0


# ------------------------------------------------------------------ damped sampling
def test_reduce_function_matches_the_source_rounding():
    assert G.Node.reduce_function(24, 0) == 24
    assert G.Node.reduce_function(24, 1) == 12
    assert G.Node.reduce_function(24, 2) == 6
    assert G.Node.reduce_function(24, 3) == 3
    assert G.Node.reduce_function(24, 5) == 1


def test_chance_node_full_expansion_uses_sample_count_sum_and_damping():
    ch = G.Node(is_random=True)
    kids = [G.Node() for _ in range(2)]
    edges = [G.Edge.connect(ch, k, i) for i, k in enumerate(kids)]
    for e in edges:
        e.sample_count = 1                      # total 2
    assert ch.is_fully_expanded(0) is False     # needs 24
    assert ch.is_fully_expanded(4) is True      # damped threshold is 24/2^4 = 2 (rounds to 2)
    edges[0].sample_count = 23                  # total 24
    assert ch.is_fully_expanded(0) is True


def test_damping_is_keyed_on_samples_traversed_not_depth():
    """Regression: keying the damping on node depth made deep chance nodes fully expanded at
    one sample regardless of how many chance nodes the descent had actually passed."""
    ch = G.Node(is_random=True, depth=9)
    G.Edge.connect(ch, G.Node(), 0)
    assert ch.is_fully_expanded(0) is False     # depth 9 must NOT imply a reduced threshold


# ------------------------------------------------------------------ A4 invariants
def test_manual_coin_contexts_are_marked_random_and_never_ucb_selected():
    stats = S.new_stats()
    for ctx in sorted(G.MANUAL_COIN_CONTEXTS):
        n = G.Node(select_context=ctx, is_random=True)
        for i in range(2):
            G.Edge.connect(n, G.Node(), i)
        child, inc = n.best_child(0.285, np.random.default_rng(0), stats)
        assert child is not None
        assert inc == 0                          # 2 edges is under the sparse threshold of 5
    assert stats["chance_samples"] == len(G.MANUAL_COIN_CONTEXTS)
    assert stats["manual_coin_node_ucb_selected"] == 0


def test_the_ucb_guard_fires_if_a_coin_context_is_left_unmarked():
    """The guard must be able to detect the bug it exists for, or it proves nothing."""
    stats = S.new_stats()
    n = G.Node(select_context=46, is_random=False)   # deliberately NOT marked random
    for i in range(2):
        G.Edge.connect(n, G.Node(), i)
    n.best_child(0.285, np.random.default_rng(0), stats)
    assert stats["manual_coin_node_ucb_selected"] == 1


def test_chance_node_sparse_threshold_increments_past_five_edges():
    stats = S.new_stats()
    n = G.Node(select_context=46, is_random=True)
    for i in range(6):
        G.Edge.connect(n, G.Node(), i)
    _, inc = n.best_child(0.285, np.random.default_rng(0), stats)
    assert inc == 1


def test_sample_child_is_weighted_by_sample_count():
    n = G.Node(is_random=True)
    a, b = G.Node(), G.Node()
    ea = G.Edge.connect(n, a, 0)
    eb = G.Edge.connect(n, b, 1)
    ea.sample_count, eb.sample_count = 99, 1
    rng = np.random.default_rng(0)
    hits = sum(1 for _ in range(400) if n._sample_child(rng) is a)
    assert hits > 340          # ~99% expected; a uniform sampler would give ~200


# ------------------------------------------------------------------ dummy edges
def test_dummy_edge_never_outranks_its_own_twin():
    """What `IsDummy` actually guarantees in the source -- and what it does not.

    A first draft of this test asserted a dummy edge loses to ANY edge. It does not, and the
    source agrees: `Edge.Value` returns `Successor.Value(0)` plus a bonus, and parking VisitCount
    at int.MaxValue only drives the BONUS to ~0. The exploitation term survives untouched.

    The real invariant is narrower. A dummy edge is created only when an edge from the same
    predecessor to the same successor already exists, so the two share an identical value term
    and the twin -- which keeps a real visit count -- always has the strictly larger bonus.
    """
    p = G.Node(); p.total_visit = 100
    target = G.Node(); target.visit_count, target.rewards = 5, 5.0     # value 1.0
    twin = G.Edge.connect(p, target, 0); twin.visit_count = 5
    dummy = G.Edge.connect(p, target, 1); dummy.is_dummy = True
    assert dummy.visit_count == G.DUMMY_VISITS == (1 << 31) - 1
    assert dummy.value(0.285) < twin.value(0.285)
    assert dummy.value(0.285) == pytest.approx(target.value(0.0), abs=1e-3)


def test_dummy_edge_keeps_its_successor_value_and_loses_only_exploration():
    """Guards against 'fixing' the dummy edge to -inf, which would break transposition."""
    p = G.Node(); p.total_visit = 100
    good = G.Node(); good.visit_count, good.rewards = 5, 5.0
    e = G.Edge.connect(p, good, 0); e.is_dummy = True
    assert e.value(0.0) == 1.0
    assert e.value(0.285) == pytest.approx(1.0, abs=1e-3)


def test_dummy_edge_blocks_recursive_update():
    stats = S.new_stats()
    p = G.Node(); c = G.Node()
    e = G.Edge.connect(p, c, 0)
    e.is_dummy = True
    e.recursive_update(1.0, 5, 5, stats)
    assert p.rewards == 0.0 and p.total_visit == 0

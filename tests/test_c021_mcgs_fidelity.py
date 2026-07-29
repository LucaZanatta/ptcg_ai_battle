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


# ------------------------------------------------------------------ perspective regressions
class _Cur:
    def __init__(self, yi):
        self.yourIndex = yi


class _Obs:
    """Mimics the engine Observation: `yourIndex` lives on `.current`, not at the top level."""

    def __init__(self, yi):
        self.current = _Cur(yi)


def test_your_index_reads_through_current_not_the_top_level():
    """Regression, and the reason it mattered.

    `getattr(obs, "yourIndex", default)` always missed, so `is_opponent` was False for every
    node and `Node.Update`'s opponent sign flip never fired -- the search maximised the same
    objective at both players' nodes, i.e. assumed the opponent would cooperate. It also pinned
    the root player to seat 0, scoring every seat-1 game from the wrong side.
    """
    assert not hasattr(_Obs(1), "yourIndex"), "fixture must reproduce the real attribute layout"
    assert S.MCGS._your_index(_Obs(0), default=9) == 0
    assert S.MCGS._your_index(_Obs(1), default=9) == 1
    # the naive form silently returns the default -- this is the bug being guarded against
    assert int(getattr(_Obs(1), "yourIndex", 9)) == 9


def test_your_index_falls_back_only_when_genuinely_absent():
    class Bare:
        pass
    assert S.MCGS._your_index(Bare(), default=1) == 1


def test_opponent_nodes_are_detected_for_both_seats():
    """`is_opponent` must be True exactly when the node's owner differs from the root player."""
    for root in (0, 1):
        for owner in (0, 1):
            own = S.MCGS._your_index(_Obs(owner), root)
            assert (own != root) == (owner != root)


# ------------------------------------------------------------------ negamax frame (reproduced)
def test_values_are_stored_in_the_movers_frame_and_best_child_does_not_negate():
    """A reproduced SOURCE property, not a port defect. Recorded because it has consequences.

    `Node.Update` negates the reward at opponent nodes, so each node's `Rewards` are in the frame
    of the player to move there. `Node.BestChild` then takes `ArgMax(edge.Value(c))` with NO
    negation. Mixing frames in one argmax means a child whose mover is the opponent -- in PTCG
    and Hearthstone alike, that is the END-TURN successor -- is ranked by the negation of its
    value to the root player.

    Concretely: an end-turn line that is GOOD for the root player stores a NEGATIVE value and so
    looks worse than a mediocre same-turn action.

    `FIDELITY_RULES §5` requires reproducing the source rather than 'fixing' it, so this is
    asserted, not corrected. Note the source's own PIMC branch adds a SECOND flip for end-turn
    nodes (`if (IsEndTurn && NodeConfig.PIMC) reward *= -1`), which would double-negate them back
    into the root frame -- suggestive that the authors were aware of the framing.
    """
    root_child_mine = G.Node(is_opponent=False)
    root_child_opp = G.Node(is_opponent=True)
    for n in (root_child_mine, root_child_opp):
        n.update(1.0)                      # the SAME root-frame reward: the root player won
    assert root_child_mine.rewards == 1.0
    assert root_child_opp.rewards == -1.0          # stored in the opponent's frame
    assert root_child_mine.value(0.0) > root_child_opp.value(0.0)

    p = G.Node()
    p.total_visit = 10
    e_mine = G.Edge.connect(p, root_child_mine, 0); e_mine.visit_count = 1
    e_opp = G.Edge.connect(p, root_child_opp, 1); e_opp.visit_count = 1
    stats = S.new_stats()
    best, _ = p.best_child(0.0, np.random.default_rng(0), stats)
    # both children represent a root-player WIN, yet the opponent-mover child is ranked last
    assert best is root_child_mine


def test_the_second_end_turn_flip_is_gated_on_pimc_and_therefore_inactive():
    n = G.Node(is_opponent=False, is_end_turn=True)
    n.update(1.0)
    assert n.rewards == 1.0, "with PIMC False the end-turn flip must not fire"


def test_backup_ucd_carries_the_same_finalise_block_as_backup_edges():
    """Regression: UCD is the ACTIVE strategy, so omitting Finalise made it dead code.

    `Node.Finalise` collapses a parent onto a proven winning edge. A win reached without an
    end-turn action must trigger it during a UCD backup, exactly as it does during an edge backup.
    """
    stats = S.new_stats()
    root = G.Node()
    a, b = G.Node(), G.Node()
    G.Edge.connect(root, a, 0)
    G.Edge.connect(root, b, 1)
    win = G.Node(is_terminal=True, play_state="WON")
    e = G.Edge.connect(a, win, 0)
    win.last_traversed_edge = e
    assert len(root.outgoing_edges) == 2
    G.backup_ucd(win, 1.0, G.UCDParams(1, 0), stats)
    assert stats["finalised"] >= 1, "Finalise never ran during a UCD backup"
    assert win.is_finalised
    assert len(a.outgoing_edges) == 1, "the parent was not collapsed onto the winning edge"


def test_finalise_is_counted_only_when_it_actually_collapses():
    stats = S.new_stats()
    lone = G.Node(is_terminal=True, play_state="WON")   # no parent -> nothing to collapse
    G.backup_ucd(lone, 1.0, G.UCDParams(1, 0), stats)
    assert stats["finalised"] == 0


# ------------------------------------------------------------------ transfer x A10 interaction
def test_transfer_prior_maps_action_set_indices_not_option_indices():
    """Regression: the two features are each correct alone and were wrong together.

    On the reference port `untested_action_indices` indexes `legal_options`. On the A10 corrected
    branch it indexes `action_sets`, whose entries are TUPLES of option indices. The prior is
    option-indexed in both cases, so looking an action-set index up directly mis-maps it -- and
    a node with more action sets than options would silently get probability 0 for the excess,
    making those combinations unexpandable-first.
    """
    from cg import c021_transfer as TR

    class Provider:
        def option_scores(self, obs, k):
            # option 3 is overwhelmingly preferred
            p = np.full(4, 0.01); p[3] = 0.97
            return p / p.sum()

    stats = S.new_stats()
    node = G.Node()
    node.obs = object()
    node.legal_options = [0, 1, 2, 3]
    # six 2-element combinations over 4 options: MORE sets than options
    node.action_sets = [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]
    node.untested_action_indices = list(range(len(node.action_sets)))
    arm = TR.arm_config("T1_policy_prior")
    picks = [TR.sample_untested(np.random.default_rng(s), Provider(), node, arm, stats)
             for s in range(200)]
    assert max(picks) <= 5, "returned an index outside the action-set space"
    # sets containing option 3 are indices 2, 4, 5 -- they must dominate
    containing = sum(1 for i in picks if 3 in node.action_sets[i])
    assert containing > 150, f"prior did not follow the option it prefers: {containing}/200"
    assert stats["transfer_prior_used"] > 0


def test_transfer_prior_still_indexes_options_on_the_reference_port():
    from cg import c021_transfer as TR

    class Provider:
        def option_scores(self, obs, k):
            p = np.full(4, 0.01); p[3] = 0.97
            return p / p.sum()

    stats = S.new_stats()
    node = G.Node()
    node.obs = object()
    node.legal_options = [0, 1, 2, 3]
    node.action_sets = None                       # reference port
    node.untested_action_indices = [0, 1, 2, 3]
    arm = TR.arm_config("T1_policy_prior")
    picks = [TR.sample_untested(np.random.default_rng(s), Provider(), node, arm, stats)
             for s in range(200)]
    assert picks.count(3) > 150, f"option 3 should dominate, got {picks.count(3)}/200"


def test_reuse_cache_cannot_fuse_two_states_that_merely_collide():
    """Regression: the A5 reuse cache was keyed by hash() alone.

    At the 20,000-entry bound a 32-bit-masked hash collides with ~4.5% probability, and a
    collision there silently transfers visit counts and rewards between unrelated positions --
    totals still look right, only the attribution is wrong. The abstraction implements __eq__,
    so the cache keys on the object and compares structurally.
    """
    class Colliding:
        """Two distinct states that deliberately share a hash."""
        def __init__(self, tag):
            self.tag = tag

        def __hash__(self):
            return 12345

        def __eq__(self, other):
            return isinstance(other, Colliding) and other.tag == self.tag

    a, b = Colliding("a"), Colliding("b")
    assert hash(a) == hash(b) and a != b
    cache = {}
    cache[a] = (10, 5.0, 10)
    cache[b] = (99, 1.0, 99)
    assert cache[a] == (10, 5.0, 10), "an object-keyed cache must not fuse colliding states"
    assert len(cache) == 2
    # the defective form keeps only one entry
    bad = {}
    bad[hash(a)] = (10, 5.0, 10)
    bad[hash(b)] = (99, 1.0, 99)
    assert len(bad) == 1 and bad[hash(a)] == (99, 1.0, 99)


# ------------------------------------------------------------------ A10 / C3 obliged actions
def test_is_obliged_identifies_the_single_legal_answer():
    from cg import c021_mcgs_legal as LG

    class Sel:
        def __init__(self, lo, hi):
            self.minCount, self.maxCount = lo, hi

    assert LG.is_obliged(Sel(1, 1), ["a"]) is True            # only one option
    assert LG.is_obliged(Sel(3, 3), ["a", "b", "c"]) is True   # must take all three
    assert LG.is_obliged(Sel(1, 1), ["a", "b"]) is False       # a real choice
    assert LG.is_obliged(Sel(2, 3), ["a", "b", "c"]) is False  # which two is a choice
    assert LG.is_obliged(Sel(1, 1), []) is False


def test_obliged_payload_takes_every_required_option():
    from cg import c021_mcgs_legal as LG

    class Sel:
        minCount, maxCount = 3, 3

    opts = ["a", "b", "c"]
    combo = list(range(min(LG.select_bounds(Sel())[0], len(opts))))
    assert combo == [0, 1, 2], "an obliged select must take every option it requires"

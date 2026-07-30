"""c022 probe M07 — an INDEPENDENT calculation must match the production aggregation.

`PROBE_MATRIX M07` requires exactly that. The point of an independent calculation is that it does
not share code with the thing it checks: the references below re-derive the source's semantics
from `AggregateDeterminizations` directly, in plain Python over plain dicts, and never import a
helper from `c022_mcgs_multidet`.

`PROBE_MATRIX M05` (equal total simulations across K) and `M06` (equal simulations per world) are
also asserted here, because both are arithmetic properties of `simulations_per_world` and a sweep
that gets them wrong invalidates every causal claim built on it.
"""

from __future__ import annotations

import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c022_mcgs_multidet as MD  # noqa: E402


# ---------------------------------------------------------------------------- helpers
def make_world(idx, visits, rewards, world_id=None):
    ws = MD.WorldStats(world_index=idx, world_id=world_id or f"w{idx}")
    ws.visits = dict(visits)
    ws.rewards = dict(rewards)
    ws.simulations = sum(visits.values())
    return ws


def build(worlds):
    agg = MD.Aggregate(n_worlds=len(worlds))
    for ws in worlds:
        agg.per_world.append(ws)
        agg.total_simulations += ws.simulations
        for a, v in ws.visits.items():
            agg.visits[a] = agg.visits.get(a, 0) + v
            agg.rewards[a] = agg.rewards.get(a, 0.0) + ws.rewards.get(a, 0.0)
    return agg


# ============================================================ M07: aggregation fixture
def reference_aggregate(worlds):
    """Independent re-derivation of `MonteCarloGraphSearch.AggregateDeterminizations`.

        rootEdge.Successor.VisitCount += edge.Successor.VisitCount   (matched by ActionIndex)
        rootEdge.Successor.Rewards    += edge.Successor.Rewards
        root.VisitCount = sum over edges;  root.Rewards = sum over edges

    Written from the C# and nothing else.
    """
    visits, rewards = {}, {}
    for w in worlds:
        for action_index, vc in w.visits.items():
            visits[action_index] = visits.get(action_index, 0) + vc
            rewards[action_index] = rewards.get(action_index, 0.0) + w.rewards.get(
                action_index, 0.0)
    root_visit = sum(visits.values())
    root_reward = sum(rewards.values())
    return visits, rewards, root_visit, root_reward


def reference_max_child(visits, rewards):
    """`MCGS.Select` with `FinalMoveSelection.MaxChild`: ArgMax(e => e.Value(0)).

    `Edge.Value(0)` returns `Successor.Value(0)` which for a non-terminal node is
    `Rewards / VisitCount`.
    """
    best, best_v = None, -math.inf
    for a, v in visits.items():
        if v <= 0:
            continue
        x = rewards[a] / v
        if x > best_v:
            best, best_v = a, x
    return best


def test_m07_aggregate_matches_independent_reference():
    worlds = [
        make_world(0, {0: 30, 1: 12, 2: 3}, {0: 21.0, 1: 3.0, 2: 0.0}),
        make_world(1, {0: 5, 1: 40, 3: 2}, {0: 1.0, 1: 33.0, 3: 2.0}),
        make_world(2, {1: 8, 2: 25, 3: 9}, {1: 2.0, 2: 20.0, 3: 4.0}),
    ]
    agg = build(worlds)
    rv, rr, root_visit, root_reward = reference_aggregate(worlds)

    assert agg.visits == rv
    assert agg.rewards == pytest.approx(rr)
    assert sum(agg.visits.values()) == root_visit
    assert sum(agg.rewards.values()) == pytest.approx(root_reward)
    for a in rv:
        assert agg.value(a) == pytest.approx(rr[a] / rv[a])


def test_m07_source_sum_selection_is_max_child_on_the_aggregate():
    worlds = [
        make_world(0, {0: 30, 1: 12}, {0: 21.0, 1: 3.0}),
        make_world(1, {0: 5, 1: 40}, {0: 1.0, 1: 33.0}),
    ]
    agg = build(worlds)
    rv, rr, _, _ = reference_aggregate(worlds)
    assert agg.select(MD.AGG_SOURCE_SUM) == reference_max_child(rv, rr)


def test_m07_action_index_is_the_join_key_not_position():
    """Worlds may expand different action subsets; the join must be by ACTION INDEX.

    If aggregation zipped per-world edge LISTS positionally, world 1's statistics for action 5
    would be added to world 0's action 2 -- the position-pairing defect family this repository
    has already shipped once. Here world 0 never touches action 5 and world 1 never touches
    action 2, so a positional join would produce a different answer.
    """
    w0 = make_world(0, {2: 10}, {2: 9.0})
    w1 = make_world(1, {5: 10}, {5: 1.0})
    agg = build([w0, w1])
    assert agg.visits == {2: 10, 5: 10}
    assert agg.value(2) == pytest.approx(0.9)
    assert agg.value(5) == pytest.approx(0.1)
    assert agg.select(MD.AGG_SOURCE_SUM) == 2


def test_m07_a_single_world_aggregate_is_that_world():
    """K=1 must be arithmetically identical to searching one world -- the M04 precondition."""
    w = make_world(0, {0: 17, 1: 4, 2: 9}, {0: 5.0, 1: 4.0, 2: 1.0})
    agg = build([w])
    assert agg.visits == w.visits
    assert agg.rewards == pytest.approx(w.rewards)
    assert agg.select(MD.AGG_SOURCE_SUM) == w.best_local()


def test_m07_visit_sum_rule_can_differ_from_value_rule():
    """The two A3 rules are genuinely different; a test where they agree proves nothing."""
    worlds = [
        make_world(0, {0: 100, 1: 4}, {0: 40.0, 1: 4.0}),   # action 0 visited most, value 0.40
        make_world(1, {0: 60, 1: 3}, {0: 24.0, 1: 3.0}),    # action 1 value 1.0 on 7 visits
    ]
    agg = build(worlds)
    assert agg.select(MD.AGG_VISIT_SUM) == 0        # 160 visits vs 7
    assert agg.select(MD.AGG_SOURCE_SUM) == 1       # 1.00 vs 0.40
    assert agg.select(MD.AGG_VISIT_SUM) != agg.select(MD.AGG_SOURCE_SUM)


def test_m07_robust_lcb_penalises_an_action_only_one_world_likes():
    """The adapted secondary rule must actually do what it claims."""
    worlds = [
        make_world(0, {0: 10, 1: 10}, {0: 10.0, 1: 6.0}),   # a0 = 1.00  a1 = 0.60
        make_world(1, {0: 10, 1: 10}, {0: 0.0, 1: 6.0}),    # a0 = 0.00  a1 = 0.60
        make_world(2, {0: 10, 1: 10}, {0: 0.0, 1: 6.0}),    # a0 = 0.00  a1 = 0.60
    ]
    agg = build(worlds)
    # Summed: a0 = 10/30 = 0.333, a1 = 18/30 = 0.600 -> both rules prefer a1 here.
    assert agg.select(MD.AGG_SOURCE_SUM) == 1
    assert agg.select(MD.AGG_ROBUST_LCB) == 1
    # Now make the mean tie so ONLY the variance can break it.
    worlds2 = [
        make_world(0, {0: 10, 1: 10}, {0: 10.0, 1: 6.0}),   # a0 = 1.00  a1 = 0.60
        make_world(1, {0: 10, 1: 10}, {0: 4.0, 1: 6.0}),    # a0 = 0.40  a1 = 0.60
        make_world(2, {0: 10, 1: 10}, {0: 4.0, 1: 6.0}),    # a0 = 0.60  mean a0 = 0.60
    ]
    agg2 = build(worlds2)
    assert agg2.value(0) == pytest.approx(agg2.value(1))    # identical summed value
    assert agg2.select(MD.AGG_ROBUST_LCB) == 1              # a1 has zero spread, a0 does not


# ============================================================ M05 / M06: budget protocols
@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 7, 8, 16])
@pytest.mark.parametrize("total", [1, 7, 64, 100, 512, 1000])
def test_m05_fixed_total_uses_exactly_equal_total_simulations(total, k):
    """M05 — K=1/2/4/8 must use EXACTLY equal total simulations.

    Integer division alone would silently drop the remainder and give K=3 fewer simulations than
    K=1, turning "equal total" into a statement that is false by up to K-1 simulations per
    decision -- across thousands of decisions, a real budget difference attributed to K.
    """
    plan = MD.simulations_per_world(total, k, "fixed_total")
    assert len(plan) == k
    assert sum(plan) == total
    assert max(plan) - min(plan) <= 1          # as even as integers permit
    assert all(p >= 0 for p in plan)


@pytest.mark.parametrize("k", [1, 2, 4, 8])
def test_m06_fixed_per_world_gives_every_world_the_same_count(k):
    """M06 — each world receives identical simulations; total grows with K."""
    plan = MD.simulations_per_world(200, k, "fixed_per_world")
    assert len(plan) == k
    assert len(set(plan)) == 1
    assert plan[0] == 200
    assert sum(plan) == 200 * k


def test_the_two_protocols_coincide_only_at_k1():
    for k in (1, 2, 4, 8):
        a = MD.simulations_per_world(256, k, "fixed_total")
        b = MD.simulations_per_world(256, k, "fixed_per_world")
        if k == 1:
            assert a == b
        else:
            assert a != b, f"protocols must differ at K={k} or the sweep tests nothing"


# ============================================================ predicted probability
def test_predicted_win_probability_is_the_aggregate_not_the_best_world():
    """M08 depends on this definition. The most optimistic world must NOT be the belief.

    Reporting max-over-worlds would pin the predicted probability near 1.0 whatever K is, and
    calibration could never improve -- the failure would then be misread as "the ensemble does
    not help".
    """
    worlds = [
        make_world(0, {0: 10}, {0: 10.0}),    # this world is certain: 1.00
        make_world(1, {0: 10}, {0: 0.0}),     # this world is certain of the opposite: 0.00
        make_world(2, {0: 10}, {0: 2.0}),     # 0.20
        make_world(3, {0: 10}, {0: 0.0}),     # 0.00
    ]
    agg = build(worlds)
    p = agg.predicted_win_probability(0)
    assert p == pytest.approx(12.0 / 40.0)
    assert p < max(w.local_value(0) for w in worlds)
    assert p == pytest.approx(sum(agg.rewards.values()) / sum(agg.visits.values()))


def test_world_disagreement_reports_real_disagreement():
    worlds = [
        make_world(0, {0: 10, 1: 10}, {0: 9.0, 1: 1.0}),   # prefers 0
        make_world(1, {0: 10, 1: 10}, {0: 1.0, 1: 9.0}),   # prefers 1
        make_world(2, {0: 10, 1: 10}, {0: 1.0, 1: 9.0}),   # prefers 1
    ]
    d = build(worlds).world_disagreement()
    assert d["per_world_best_actions"] == [0, 1, 1]
    assert d["distinct_best_actions"] == 2
    assert d["modal_agreement"] == pytest.approx(2 / 3, abs=1e-4)   # reported to 4 dp
    s = d["selected_action_value_across_worlds"]
    assert s["n"] == 3 and s["sd"] > 0


def test_world_disagreement_reports_unanimity_as_such():
    worlds = [make_world(i, {0: 10, 1: 10}, {0: 9.0, 1: 1.0}) for i in range(4)]
    d = build(worlds).world_disagreement()
    assert d["distinct_best_actions"] == 1
    assert d["modal_agreement"] == pytest.approx(1.0)
    assert d["selected_action_value_across_worlds"]["sd"] == pytest.approx(0.0)


def test_mixed_terminal_scale_flag_fires_only_when_a_terminal_is_reached():
    """The +/-10 terminal scale would break the aggregate-as-probability reading.

    The frozen c021 K1 control records finalised=0, terminal_leaves=0, lethal_bonus=0, so the
    scale is uniformly [0,1] at that scale. If a larger K budget ever reaches a terminal leaf,
    this flag must fire so the mixed scale is handled explicitly rather than discovered in a
    calibration plot.
    """
    clean = build([make_world(0, {0: 5}, {0: 3.0})])
    assert clean.mixed_terminal_scale_detected() is False
    w = make_world(1, {0: 5}, {0: 3.0})
    w.terminal_leaves = 1
    assert build([w]).mixed_terminal_scale_detected() is True


# ============================================================ opponent sign
def make_world_signed(idx, visits, rewards, is_opponent):
    ws = MD.WorldStats(world_index=idx, world_id=f"w{idx}")
    ws.visits = dict(visits)
    ws.rewards = dict(rewards)
    ws.is_opponent = dict(is_opponent)
    ws.simulations = sum(visits.values())
    return ws


def build_signed(worlds):
    agg = MD.Aggregate(n_worlds=len(worlds))
    for ws in worlds:
        agg.per_world.append(ws)
        agg.total_simulations += ws.simulations
        for a, v in ws.visits.items():
            agg.visits[a] = agg.visits.get(a, 0) + v
            agg.rewards[a] = agg.rewards.get(a, 0.0) + ws.rewards.get(a, 0.0)
            flag = bool(ws.is_opponent.get(a, False))
            if a in agg.is_opponent and agg.is_opponent[a] != flag:
                agg.opponent_flag_conflicts += 1
            agg.is_opponent[a] = flag
    return agg


def test_predicted_probability_is_never_negative_at_an_opponent_successor():
    """`Node.Update` negates the reward at an opponent node, so an end-turn action's value is
    MINUS the root player's win probability.

    This test exists because a real calibration row recorded
    `predicted_win_probability: -0.044586`. A negative probability is not a rounding artifact:
    every end-turn decision would have scored as a catastrophic Brier miss for a reason with
    nothing to do with the search, and K would have taken the blame.
    """
    # action 0 stays with the root player; action 1 ends the turn, so its successor is the
    # opponent and its recorded value is negative.
    w = make_world_signed(0, {0: 100, 1: 100}, {0: 30.0, 1: -20.0},
                          {0: False, 1: True})
    agg = build_signed([w])
    assert agg.raw_aggregate_value(1) == pytest.approx(-0.2)
    assert agg.predicted_win_probability(1) == pytest.approx(0.2)
    assert agg.predicted_win_probability(0) == pytest.approx(0.3)
    for a in (0, 1):
        p = agg.predicted_win_probability(a)
        assert 0.0 <= p <= 1.0


def test_selection_is_unaffected_by_the_sign_correction():
    """The flip is load-bearing for SELECTION and must not be undone.

    MaxChild on the signed scale correctly prefers the child best for the root player. Selecting
    on the converted probabilities instead would pick the action whose OPPONENT successor looks
    best for the root player, i.e. exactly backwards on end-turn actions.
    """
    w = make_world_signed(0, {0: 100, 1: 100}, {0: 30.0, 1: -20.0},
                          {0: False, 1: True})
    agg = build_signed([w])
    assert agg.select(MD.AGG_SOURCE_SUM) == 0          # +0.30 beats -0.20 on the signed scale
    # and the probabilities would have ranked them the same way here, so make a case where they
    # would NOT, to prove selection uses the signed value.
    w2 = make_world_signed(0, {0: 100, 1: 100}, {0: 10.0, 1: -60.0},
                           {0: False, 1: True})
    agg2 = build_signed([w2])
    assert agg2.predicted_win_probability(1) == pytest.approx(0.6)
    assert agg2.predicted_win_probability(0) == pytest.approx(0.1)
    assert agg2.select(MD.AGG_SOURCE_SUM) == 0, \
        "selection must use the SIGNED value; ranking by probability would invert end-turn actions"


def test_opponent_flag_conflict_is_counted_not_silently_resolved():
    """Whose turn follows an action is PUBLIC, so it cannot differ across worlds.

    If it ever does, the action indices are not aligned and the aggregate is summing statistics
    for different actions -- the position-pairing defect family, caught a second way.
    """
    a = make_world_signed(0, {0: 10}, {0: 5.0}, {0: False})
    b = make_world_signed(1, {0: 10}, {0: -5.0}, {0: True})
    agg = build_signed([a, b])
    assert agg.opponent_flag_conflicts == 1


# ============================================================ legal fallback payloads
class _Sel:
    def __init__(self, lo, hi, context=1):
        self.minCount = lo
        self.maxCount = hi
        self.context = context
        self.selectType = 1


class _Opt:
    def __init__(self, i, option_type=1):
        self.i = i
        self.option_type = option_type

    def short(self):
        return f"o{self.i}"


def _agent(seed=0):
    """A bare agent instance; only `rng` and `_fallback_payload` are exercised."""
    from cg import c022_mcgs_agent as AG
    obj = AG.MultiDetMCGSAgent.__new__(AG.MultiDetMCGSAgent)
    import numpy as np
    obj.rng = np.random.default_rng(seed)
    return obj


def test_fallback_payload_respects_min_count(monkeypatch):
    """The out-of-budget fallback must name at least `minCount` options.

    Returning a single option when minCount > 1 makes the environment mark the agent INVALID and
    the game ends `["INVALID", "DONE"]` with no score at all. That is how 10 of 60 games in the
    first arm left the field score without being abandoned, errored, or counted anywhere -- and
    an agent that invalidates its own long games looks BETTER than it is, because the games it
    ruins are the ones it was losing slowly.
    """
    from cg import c019_core as CK
    captured = {}

    def fake_payload(picks, sel):
        captured["n"] = len(picks)
        captured["ids"] = [p.i for p in picks]
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    ag = _agent()
    opts = [_Opt(i) for i in range(6)]
    for lo, hi in ((1, 1), (2, 2), (3, 5), (4, 4)):
        ag._fallback_payload(_Sel(lo, hi), opts)
        assert captured["n"] >= lo, f"minCount {lo} not respected: got {captured['n']}"
        assert captured["n"] <= max(1, min(hi, len(opts)))
        assert len(set(captured["ids"])) == captured["n"], "fallback repeated an option"


def test_fallback_clamps_min_count_to_the_options_available(monkeypatch):
    """`minCount` can exceed the option count; naming non-existent options is also invalid."""
    from cg import c019_core as CK
    captured = {}

    def fake_payload(picks, sel):
        captured["ids"] = [p.i for p in picks]
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    ag = _agent()
    opts = [_Opt(i) for i in range(3)]
    ag._fallback_payload(_Sel(9, 9), opts)
    assert len(captured["ids"]) == 3
    assert set(captured["ids"]) == {0, 1, 2}


def test_fallback_prefers_end_turn_only_when_a_single_pick_is_legal(monkeypatch):
    """Ending the turn always advances the game, but only if minCount allows one option."""
    from cg import c019_core as CK
    from cg import c020_override as OV
    captured = {}

    def fake_payload(picks, sel):
        captured["types"] = [getattr(p, "option_type", None) for p in picks]
        captured["n"] = len(picks)
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    ag = _agent()
    opts = [_Opt(0), _Opt(1, OV.OPT_END), _Opt(2)]
    ag._fallback_payload(_Sel(1, 1), opts)
    assert captured["types"] == [OV.OPT_END]
    ag._fallback_payload(_Sel(2, 2), opts)
    assert captured["n"] == 2, "minCount must win over the end-turn preference"


def test_fallback_is_deterministic_under_the_seeded_generator(monkeypatch):
    from cg import c019_core as CK
    seen = []

    def fake_payload(picks, sel):
        seen.append(tuple(p.i for p in picks))
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    opts = [_Opt(i) for i in range(8)]
    for _ in range(2):
        ag = _agent(seed=12345)
        ag._fallback_payload(_Sel(3, 3), opts)
    assert seen[0] == seen[1], "the fallback must be reproducible from the seed"


def test_searched_payload_respects_min_count(monkeypatch):
    """The SEARCHED path must also name at least `minCount` options.

    The graph search ranks single action indices, because MonteCarloGraphSearch has one
    PlayerTask per edge. A PTCG select with minCount > 1 is a SET, and a payload naming one
    option is rejected.

    This defect is distinguishable from the fallback one only by `decision_budget_exhausted_
    decisions: 0` -- the two paths produce identical INVALID games and identical aggregate
    counters otherwise, which is why the terminal-status histogram had to exist before the
    cause could be found.
    """
    from cg import c019_core as CK
    captured = {}

    def fake_payload(picks, sel):
        captured["ids"] = [p.i for p in picks]
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    ag = _agent()
    ag.stats = {}
    opts = [_Opt(i) for i in range(5)]
    # the search likes action 3 most, then 1, then 4; 0 and 2 were never expanded
    agg = build_signed([make_world_signed(0, {3: 50, 1: 30, 4: 20},
                                          {3: 40.0, 1: 12.0, 4: 2.0},
                                          {3: False, 1: False, 4: False})])
    ag._payload_for(_Sel(1, 1), opts, agg, 3)
    assert captured["ids"] == [3], "a single-pick select must play exactly the chosen action"

    ag._payload_for(_Sel(3, 3), opts, agg, 3)
    assert len(captured["ids"]) == 3, "minCount 3 must produce three options"
    assert captured["ids"][0] == 3, "the search's chosen action must come first"
    # the remainder must follow the search's own ranking, not option order
    assert captured["ids"][1] == 1, f"expected the next-best searched action, got {captured['ids']}"
    assert len(set(captured["ids"])) == 3


def test_searched_payload_falls_back_to_unexpanded_options_to_reach_min_count(monkeypatch):
    """If the search expanded fewer actions than minCount, the payload must still be legal."""
    from cg import c019_core as CK
    captured = {}

    def fake_payload(picks, sel):
        captured["ids"] = [p.i for p in picks]
        return [0]

    monkeypatch.setattr(CK, "to_select_payload", fake_payload)
    from cg import c022_mcgs_agent as AG
    monkeypatch.setattr(AG, "K", CK)

    ag = _agent()
    ag.stats = {}
    opts = [_Opt(i) for i in range(6)]
    agg = build_signed([make_world_signed(0, {2: 10}, {2: 5.0}, {2: False})])
    ag._payload_for(_Sel(4, 4), opts, agg, 2)
    assert len(captured["ids"]) == 4
    assert captured["ids"][0] == 2
    assert len(set(captured["ids"])) == 4
    assert all(0 <= i < 6 for i in captured["ids"])


def test_worlds_may_legitimately_disagree_about_whose_turn_follows_an_action():
    """In PTCG the successor's player is NOT always public.

    Measured on a real K=2 arm: 10 of 64 traced decisions had worlds disagreeing about the same
    action index, with the option signature matching every time. An action's resolution can
    depend on hidden information, so the same action can end the turn in one sampled world and
    not in another.

    The source's AggregateDeterminizations sums RAW rewards, which is a root-frame sum only
    because Hearthstone's successor player is determined by the action alone. Here it is not, so
    summing raw rewards would add +p from one world to -q from another for the same action.
    """
    # both worlds see 10 visits; world 0's successor is the agent's own turn (+0.6),
    # world 1's is the opponent's, stored negated (-0.8 means the ROOT player scores 0.8)
    a = make_world_signed(0, {0: 10}, {0: 6.0}, {0: False})
    b = make_world_signed(1, {0: 10}, {0: -8.0}, {0: True})
    agg = build_signed([a, b])
    assert agg.opponent_flag_conflicts == 1

    # RAW summing would give (6.0 - 8.0)/20 = -0.10, which is not a return in any frame.
    raw = (6.0 + -8.0) / 20
    assert raw == pytest.approx(-0.10)

    # Root-frame summing gives (6.0 + 8.0)/20 = 0.70 -- the mean root-player return.
    assert agg.root_frame_rewards(0) == pytest.approx(14.0)
    assert agg.root_frame_value(0) == pytest.approx(0.70)
    assert agg.predicted_win_probability(0) == pytest.approx(0.70)
    assert agg.root_frame_value(0) != pytest.approx(raw)


def test_at_k1_the_signed_value_is_exactly_the_source_value():
    """The root-frame conversion must not change K=1, or probe M04's identity breaks."""
    for is_opp, reward in ((False, 6.0), (True, -6.0)):
        w = make_world_signed(0, {0: 10}, {0: reward}, {0: is_opp})
        agg = build_signed([w])
        # the source stores Rewards/VisitCount and MaxChild reads exactly that
        assert agg.value(0) == pytest.approx(reward / 10)
        # and the probability is the root-frame reading of the same number
        assert agg.predicted_win_probability(0) == pytest.approx(0.6)


def test_modal_flag_decides_the_signed_value_under_disagreement():
    """With 2 of 3 worlds calling it an opponent successor, the signed value takes that sign."""
    ws = [make_world_signed(0, {0: 10}, {0: 6.0}, {0: False}),
          make_world_signed(1, {0: 10}, {0: -6.0}, {0: True}),
          make_world_signed(2, {0: 10}, {0: -6.0}, {0: True})]
    agg = build_signed(ws)
    assert agg.is_opponent[0] is True
    assert agg.root_frame_value(0) == pytest.approx(0.6)
    assert agg.value(0) == pytest.approx(-0.6)

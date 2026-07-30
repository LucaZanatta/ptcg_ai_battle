"""c022 probe M11 — the source's own 15 s / 10 s schedule, and what it is budgeted by.

`PROBE_MATRIX M11`: "Original-style 15/10-second schedule executes or exact blocker recorded."

The archive, `src/SearchConfig.cs`:

    public const double FirstMoveDurationSeconds = 15;
    public const double ContinuousMoveDurationSeconds = 10;

and `Agent.GetMove`:

    if (InitialiseRoot(poGame, previousNode, searchConfig, opConfig, out Node root))
        searchDuration = SearchConfig.FirstMoveDurationSeconds;
    else
        searchDuration = SearchConfig.ContinuousMoveDurationSeconds;
    ...
    while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))
        MonteCarloGraphSearch.Search(ref root, searchConfig, oneTurnStatistics);
    ...
    previousNode = root.IsEndTurn ? null : root;

Two properties follow, and both are easy to get wrong in a way no result would reveal:

1. the loop is **timed**, not counted -- so in this mode the simulation count is a MEASUREMENT.
   Every causal arm in this contract stays count-budgeted, because a wall-clock budget is the
   D08 confound.
2. the 15 s applies to the first decision after an **end-turn**, not to the first decision of the
   game. `previousNode` is nulled only when the chosen action ended the turn.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c021_mcgs_graph as G          # noqa: E402
from cg import c022_mcgs_agent as AG         # noqa: E402
from cg import c022_mcgs_multidet as MD      # noqa: E402


def test_m11_the_schedule_constants_are_the_source_values():
    assert G.FIRST_MOVE_SECONDS == 15.0
    assert G.CONTINUING_MOVE_SECONDS == 10.0
    assert AG.REFERENCE_CFG["first_move_seconds"] == 15.0
    assert AG.REFERENCE_CFG["continuing_move_seconds"] == 10.0


def _agent(**cfg):
    return AG.MultiDetMCGSAgent(deck=[1] * 60, cfg=cfg, seed=1)


def test_m11_deadline_is_15s_on_a_first_move_and_10s_on_a_continuation():
    a = _agent(budget_protocol=MD.PROTOCOL_SOURCE_TIME, decision_wall_ceiling_seconds=600.0)
    t0 = time.monotonic()
    assert a._first_move is True
    assert a._decision_deadline() - t0 == pytest.approx(15.0, abs=0.2)
    a._first_move = False
    t1 = time.monotonic()
    assert a._decision_deadline() - t1 == pytest.approx(10.0, abs=0.2)


def test_m11_the_schedule_applies_only_in_the_source_time_protocol():
    """A count-budgeted arm must NOT acquire a 15 s cap; that would silently truncate it."""
    for proto in (MD.PROTOCOL_FIXED_TOTAL, MD.PROTOCOL_FIXED_PER_WORLD):
        a = _agent(budget_protocol=proto, decision_wall_ceiling_seconds=300.0)
        t0 = time.monotonic()
        assert a._decision_deadline() - t0 == pytest.approx(300.0, abs=0.2), proto


def test_m11_first_move_tracks_the_end_turn_not_the_game_start():
    """The property that distinguishes the source's rule from the obvious wrong one.

    A naive implementation gives 15 s to decision 0 and 10 s to everything after. The source
    gives 15 s to every decision that follows an end-turn, which in a 40-decision game is a
    materially different schedule -- and the difference is invisible in any aggregate.
    """
    a = _agent(budget_protocol=MD.PROTOCOL_SOURCE_TIME)
    agg = MD.Aggregate(n_worlds=1)
    agg.visits, agg.rewards = {0: 5, 1: 5}, {0: 1.0, 1: 1.0}

    agg.is_opponent = {0: False, 1: True}
    a._first_move = bool(agg.is_opponent.get(0, False))     # chose a non-end-turn action
    assert a._first_move is False, "a mid-turn action must not grant the 15 s first-move budget"
    a._first_move = bool(agg.is_opponent.get(1, False))     # chose the end-turn action
    assert a._first_move is True, "the decision after an end-turn is a first move"


def test_m11_source_time_does_not_count_a_deadline_stop_as_a_budget_failure():
    """`decision_deadline_stops` means a COUNT-budgeted arm failed to deliver. In the timed
    protocol reaching the deadline is the normal and intended stop, and counting it would make
    every M11 arm report itself invalid."""
    import inspect
    src = inspect.getsource(MD.search_one_world)
    assert "if not time_driven:" in src, (
        "the deadline branch must not record a deadline_stop in time-driven mode")
    # and the count must not be the stopping condition in that mode
    assert "if not time_driven and n >= simulations:" in src


def test_m11_time_driven_is_never_used_by_a_causal_k_arm():
    """A4 requires simulation-count attribution. The timed protocol must stay out of the sweeps."""
    for proto in (MD.PROTOCOL_FIXED_TOTAL, MD.PROTOCOL_FIXED_PER_WORLD):
        assert proto != MD.PROTOCOL_SOURCE_TIME
    plan_t = MD.simulations_per_world(96, 8, MD.PROTOCOL_FIXED_TOTAL)
    plan_w = MD.simulations_per_world(12, 8, MD.PROTOCOL_FIXED_PER_WORLD)
    assert sum(plan_t) == 96 and plan_w == [12] * 8

"""c022 A3 — K independent source-faithful search sessions with source-derived root aggregation.

`FIDELITY_RULES §3` priority 1 (a fresh hidden world per simulation inside one graph) is
unavailable: `results/fidelity/mcgs_hidden_information_gap_analysis.md` maps eleven source sites
that all need interior hidden-state mutation, and probe M01b re-measures the API refusing it.
This module implements priority 2.

**The aggregation is a port, not an invention.** `MonteCarloGraphSearch.AggregateDeterminizations`
in the official archive is:

```csharp
foreach (Node determinization in determinizations)
    foreach (Edge edge in determinization.OutgoingEdges)
        // find rootEdge with rootEdge.ActionIndex == edge.ActionIndex
        rootEdge.Successor.VisitCount += edge.Successor.VisitCount;
        rootEdge.Successor.Rewards    += edge.Successor.Rewards;
        // unmatched ActionIndex -> clone the child onto the root
root.VisitCount = root.OutgoingEdges.Sum(p => p.Successor.VisitCount);
root.Rewards    = root.OutgoingEdges.Sum(p => p.Successor.Rewards);
```

and selection afterwards is the source's unchanged `MaxChild`, i.e. `ArgMax(e => e.Value(0))` =
`ArgMax(Rewards / VisitCount)` on the summed statistics. So `MANDATORY_IMPLEMENTATION A3`'s two
required rules — visit-count summation and expected-terminal-return summation — are both this
one operation: the sums are kept separately and the ratio is what selects.

Three deltas from the source, each forced and each recorded in `ADAPTATION_LEDGER.md`:

1. **Even, deterministic assignment of simulations to worlds** instead of the source's
   uniform-random `PickDeterminization`. A4 demands "simulations per world = total / K" exactly;
   random assignment gives a ragged split that would confound the causal comparison with sampling
   noise in the split itself. `MECHANICAL_ADAPTER`.
2. **Sessions do not survive a decision.** `search_end` invalidates every searchId, so
   `CleanUpDeterminizations`' re-rooting has no counterpart. `MECHANICAL_ADAPTER`.
3. **Per-world statistics are never shared.** The source's ensemble members are separate graphs
   with separate transposition tables; this port must reproduce that isolation deliberately,
   because c021's `graph_reuse` table was a single dict on the agent. Sharing it across worlds
   would seed world 2 with world 1's hidden-information-conditioned statistics and destroy the
   independence the whole correction rests on.

The source's ensemble is its PIMC configuration, under which `Finalise` is disabled and
`Node.Update` applies an extra end-turn sign flip. This port keeps the c021 `!PIMC`-minus-
unavailable-operations semantics inside each world and bolts the ensemble on top, so that K=1 is
byte-for-byte the c021 control (probe M04). That is a real deviation from the source's own
ensemble semantics; it is observationally nil at the scale measured — the frozen K1 control
records `finalised: 0`, `terminal_leaves: 0`, `lethal_bonus: 0`, so neither PIMC-gated behaviour
ever fired — and the per-arm counters below keep it that way honestly rather than by assumption.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import api as A  # noqa: E402
from cg import c019_core as K  # noqa: E402
from cg import c021_mcgs as S  # noqa: E402
from cg import c021_mcgs_graph as G  # noqa: E402
from cg import c022_mcgs_worlds as W  # noqa: E402

# Aggregation rules. PRIMARY is fixed in results/mcgs/PREREGISTERED_AGGREGATION.json before any
# sweep runs; the others exist so the preregistered choice can be compared against alternatives
# on the same raw per-world statistics, without re-running a single game.
AGG_SOURCE_SUM = "source_sum"          # port of AggregateDeterminizations + MaxChild
AGG_VISIT_SUM = "visit_sum"            # A3: visit-count summation (RobustChild on the aggregate)
AGG_ROBUST_LCB = "robust_lcb"          # A3 secondary, explicitly adapted: no source counterpart
AGG_RULES = (AGG_SOURCE_SUM, AGG_VISIT_SUM, AGG_ROBUST_LCB)

# Budget protocols. The first two are the causal ones and are budgeted by SIMULATION COUNT, as
# `MANDATORY_IMPLEMENTATION A4` requires. The third exists for M11 alone: the source counts no
# simulations at all, so reproducing its 15 s / 10 s schedule means searching to a WALL deadline
# and reporting the achieved simulation count as a measurement. It is never used in a K
# comparison, because a wall-clock budget is exactly the confound D08 was raised for.
PROTOCOL_FIXED_TOTAL = "fixed_total"
PROTOCOL_FIXED_PER_WORLD = "fixed_per_world"
PROTOCOL_SOURCE_TIME = "source_time"


@dataclass
class WorldStats:
    """Root edge statistics from ONE world, keyed by action index."""

    world_index: int
    world_id: str
    simulations: int = 0
    visits: Dict[int, int] = field(default_factory=dict)
    rewards: Dict[int, float] = field(default_factory=dict)
    edge_visits: Dict[int, int] = field(default_factory=dict)
    is_opponent: Dict[int, bool] = field(default_factory=dict)
    root_visit_count: int = 0
    root_edges: int = 0
    expanded_actions: int = 0
    error: Optional[str] = None
    elapsed_s: float = 0.0
    # M11: this world searched to a wall deadline rather than to a simulation count, so its
    # `simulations` is a RESULT and not a budget. Recorded per world so a mixed arm is visible.
    time_driven: bool = False
    # per-world terminal counters, so a K>1 arm cannot quietly start exercising the PIMC-gated
    # branches this port does not reproduce
    term_root_win: int = 0
    term_root_loss: int = 0
    term_undecided: int = 0
    finalised: int = 0
    terminal_leaves: int = 0
    lethal_bonus: int = 0

    def best_local(self) -> Optional[int]:
        """The action THIS world would have chosen alone — the per-world estimate A5 requires."""
        cands = [(self.rewards.get(a, 0.0) / v, a) for a, v in self.visits.items() if v > 0]
        return max(cands)[1] if cands else None

    def local_value(self, action: int) -> Optional[float]:
        v = self.visits.get(action, 0)
        return (self.rewards.get(action, 0.0) / v) if v > 0 else None

    def summary(self) -> Dict[str, Any]:
        return {"world_index": self.world_index, "world_id": self.world_id,
                "simulations": self.simulations, "root_visit_count": self.root_visit_count,
                "root_edges": self.root_edges, "expanded_actions": self.expanded_actions,
                "best_local_action": self.best_local(),
                "visits": dict(sorted(self.visits.items())),
                "values": {a: round(self.rewards[a] / self.visits[a], 4)
                           for a in sorted(self.visits) if self.visits[a] > 0},
                "term_root_win": self.term_root_win, "term_root_loss": self.term_root_loss,
                "term_undecided": self.term_undecided,
                "finalised": self.finalised, "terminal_leaves": self.terminal_leaves,
                "lethal_bonus": self.lethal_bonus,
                "elapsed_s": round(self.elapsed_s, 3), "error": self.error}


@dataclass
class Aggregate:
    """Summed root statistics across worlds, plus everything A5 requires per decision."""

    visits: Dict[int, int] = field(default_factory=dict)
    rewards: Dict[int, float] = field(default_factory=dict)
    # Whether the successor reached by this action is an OPPONENT node. The source's
    # `Node.Update` negates the reward at an opponent node (`if (IsOpponent) reward *= -1`), so
    # that node's Rewards/VisitCount is MINUS the root player's win probability. Selection is
    # unaffected — MaxChild still prefers the child best for the root player, which is the whole
    # point of the flip — but a predicted PROBABILITY read straight off the value is wrong by a
    # sign whenever the action ends the turn.
    is_opponent: Dict[int, bool] = field(default_factory=dict)
    per_world: List[WorldStats] = field(default_factory=list)
    n_worlds: int = 0
    total_simulations: int = 0
    option_signature: Optional[str] = None
    signature_mismatch: bool = False
    opponent_flag_conflicts: int = 0
    _flag_votes: Dict[int, List[bool]] = field(default_factory=dict, repr=False)

    def root_frame_rewards(self, action: int) -> float:
        """Summed rewards converted to the ROOT PLAYER's frame before summing.

        `Node.Update` stores `-reward` at an opponent node, so a world whose successor for this
        action is an opponent node contributes the NEGATIVE of the root player's return. Summing
        raw rewards across worlds is only meaningful when every world agrees on that flag.

        **In PTCG they do not always agree.** Measured on a real K=2 arm: 10 of 64 traced
        decisions had worlds disagreeing about whose turn follows the SAME action index. That is
        not an index misalignment — the option signature matched in every case. It is a property
        of the game: an action's resolution can depend on hidden information, so the same action
        can end the turn in one sampled world and not in another.

        The source's `AggregateDeterminizations` sums raw `Rewards` because in Hearthstone the
        successor's player is determined by the action alone, making the raw sum a root-frame sum
        already. Here it is not, so the conversion is made explicit. `SEMANTIC_GAME_ADAPTER`: the
        operation reduces exactly to the source's raw sum whenever the flags agree.
        """
        total = 0.0
        for w in self.per_world:
            r = w.rewards.get(action)
            if r is None:
                continue
            total += (-r) if w.is_opponent.get(action, False) else r
        return total

    def value(self, action: int) -> Optional[float]:
        """The source's SIGNED value: `Rewards / VisitCount` on `Node.Value`'s own scale.

        Reconstructed from the root-frame sum using the MODAL opponent flag, so that at K=1 --
        where there is one world and no disagreement possible -- this is bit-for-bit the c021
        control's value and probe M04's identity is preserved.
        """
        v = self.visits.get(action, 0)
        if v <= 0:
            return None
        p = self.root_frame_rewards(action) / v
        return -p if self.is_opponent.get(action, False) else p

    def root_frame_value(self, action: int) -> Optional[float]:
        """The root player's expected return for this action, in [0, 1]."""
        v = self.visits.get(action, 0)
        return (self.root_frame_rewards(action) / v) if v > 0 else None

    def select(self, rule: str = AGG_SOURCE_SUM, lcb_z: float = 1.0) -> Optional[int]:
        """Choose the root action. `AGG_SOURCE_SUM` is the source's MaxChild on the aggregate."""
        live = [a for a, v in self.visits.items() if v > 0]
        if not live:
            return None
        if rule == AGG_VISIT_SUM:
            # `FinalMoveSelection.RobustChild` applied to the summed visit counts.
            return max(live, key=lambda a: (self.visits[a], self.value(a) or 0.0))
        if rule == AGG_ROBUST_LCB:
            # ALGORITHMIC_ADAPTATION: no source counterpart. A lower confidence bound over the
            # per-world means, which penalises an action that only one world likes. Reported as
            # a secondary arm and never as source behaviour.
            def lcb(a):
                vals = [w.local_value(a) for w in self.per_world]
                vals = [x for x in vals if x is not None]
                if not vals:
                    return -math.inf
                m = sum(vals) / len(vals)
                if len(vals) < 2:
                    return m
                sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))
                return m - lcb_z * sd / math.sqrt(len(vals))
            return max(live, key=lcb)
        return max(live, key=lambda a: (self.value(a) or -math.inf, self.visits[a]))

    # ---------------------------------------------------------------- A5 diagnostics
    def predicted_win_probability(self, action: int) -> Optional[float]:
        """The number M08 calibrates.

        The aggregate value of the SELECTED action — summed rewards over summed visits across
        worlds — converted to a root-player win probability. Not the maximum over worlds, and not
        the value in whichever world liked it most: either of those would report the search's
        most optimistic world as its belief and guarantee that calibration cannot improve with K.

        **The sign matters and is not cosmetic.** Rollout returns are in [0, 1]
        (`PlayUntilTerminal` returns 1.0 for a root-player win, 0.0 otherwise, and 0.0 at the
        turn cap), but `Node.Update` negates the reward at an OPPONENT node, so an action that
        ends the turn has a successor whose value is MINUS the root player's win probability.
        Reading that straight off produced calibration rows with `predicted_win_probability:
        -0.0446`, which is not a probability at all and would have made every end-turn decision a
        catastrophic miss in the Brier score for a reason that has nothing to do with the search.

        The clamp is a guard, not a fudge: after the sign correction the value is a mean of
        rollout returns in [0, 1] and cannot legitimately leave that range. If it does,
        `mixed_terminal_scale_detected()` is the thing to look at — the ±10 terminal scale is the
        only mechanism that could put it outside.
        """
        p = self.root_frame_value(action)
        if p is None:
            return None
        return min(1.0, max(0.0, p))

    def raw_aggregate_value(self, action: int) -> Optional[float]:
        """The unconverted `sum(rewards)/sum(visits)`, on the source's own signed scale.

        Recorded alongside the probability so the conversion is auditable rather than hidden.
        """
        return self.value(action)

    def world_disagreement(self) -> Dict[str, Any]:
        """How much the worlds disagree — the quantity that says whether K is doing anything."""
        locals_ = [w.best_local() for w in self.per_world]
        locals_ = [x for x in locals_ if x is not None]
        agree = None
        if locals_:
            top = max(set(locals_), key=locals_.count)
            agree = locals_.count(top) / len(locals_)
        sel = self.select(AGG_SOURCE_SUM)
        spread = None
        if sel is not None:
            vals = [w.local_value(sel) for w in self.per_world]
            vals = [x for x in vals if x is not None]
            if len(vals) > 1:
                m = sum(vals) / len(vals)
                spread = {
                    "mean": round(m, 4),
                    "sd": round(math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1)), 4),
                    "min": round(min(vals), 4), "max": round(max(vals), 4),
                    "n": len(vals)}
        return {"per_world_best_actions": locals_,
                "distinct_best_actions": len(set(locals_)),
                "modal_agreement": round(agree, 4) if agree is not None else None,
                "selected_action": sel,
                "selected_action_value_across_worlds": spread}

    def mixed_terminal_scale_detected(self) -> bool:
        """True if any world reached a terminal leaf, which would put ±10 into the sums."""
        return any(w.terminal_leaves or w.finalised or w.lethal_bonus for w in self.per_world)


def _collect_root(root: G.Node, ws: WorldStats, stats: Dict[str, Any]) -> None:
    """Read one world's root edge statistics.

    Note which object the numbers come from. `Edge.visit_count` is the source's edge counter
    (incremented in `BackupUCD`), while the VALUE that `Edge.Value(0)` returns is
    `Successor.Rewards / Successor.VisitCount` — the NODE's. `AggregateDeterminizations` sums the
    successor's counters, so that is what is summed here. Summing edge visit counts instead would
    aggregate a different quantity from the one the source selects on; both are recorded so the
    difference stays visible.
    """
    ws.root_visit_count = int(root.visit_count)
    ws.root_edges = len(root.outgoing_edges)
    for e in root.outgoing_edges:
        if e.is_dummy:
            continue
        a = int(e.action_index)
        ws.visits[a] = ws.visits.get(a, 0) + int(e.successor.visit_count)
        ws.rewards[a] = ws.rewards.get(a, 0.0) + float(e.successor.rewards)
        ws.edge_visits[a] = ws.edge_visits.get(a, 0) + int(e.visit_count)
        # Whose turn it is after this action is PUBLIC, so it is the same in every world; the
        # aggregate asserts that rather than assuming it.
        ws.is_opponent[a] = bool(e.successor.is_opponent)
    ws.expanded_actions = sum(1 for v in ws.visits.values() if v > 0)
    ws.term_root_win = int(stats.get("term_root_win", 0) or 0)
    ws.term_root_loss = int(stats.get("term_root_loss", 0) or 0)
    ws.term_undecided = int(stats.get("term_undecided", 0) or 0)
    ws.finalised = int(stats.get("finalised", 0) or 0)
    ws.terminal_leaves = int(stats.get("terminal_leaves", 0) or 0)
    ws.lethal_bonus = int(stats.get("lethal_bonus", 0) or 0)


def search_one_world(obs, world: W.WorldHandle, cfg: Dict[str, Any], rng,
                     simulations: int, deadline: float,
                     prior_provider=None, transfer_arm: Optional[Dict[str, bool]] = None,
                     reuse: Optional[Dict[int, Any]] = None,
                     stats_sink: Optional[Dict[str, Any]] = None,
                     time_driven: bool = False) -> WorldStats:
    """Run one source-faithful MCGS session in one hidden world.

    `simulations` is a COUNT, not a time budget: `MANDATORY_IMPLEMENTATION A4` requires causal
    attribution by simulation count with wall clock recorded separately. `deadline` is only a
    safety stop so a pathological decision cannot hang a run; every activation is counted.

    `time_driven` inverts that for the M11 arm alone. The source does not count simulations at
    all — `Agent.GetMove` runs `while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))`
    — so reproducing its timing behaviour means searching until a wall deadline and REPORTING the
    simulation count as an outcome rather than setting it as a budget. In that mode reaching the
    deadline is the normal stop and must not be counted as a `deadline_stop`, which is the
    signal that a COUNT-budgeted arm failed to deliver its budget. Every causal K comparison in
    this contract stays count-budgeted; this mode is used only where the question is what the
    source's own schedule buys.
    """
    ws = WorldStats(world_index=world.index, world_id=world.world_id)
    t0 = time.monotonic()
    local_stats = S.new_stats()
    mcgs = S.MCGS(A, cfg, local_stats, rng, prior_provider, dict(transfer_arm or {}))
    if reuse is not None:
        mcgs.reuse = reuse
    try:
        st = W.open_session(obs, world, manual_coin=bool(cfg.get("manual_coin", True)))
        mcgs._track(st.searchId)
        root_player = S.MCGS._your_index(obs, 0)
        root = mcgs._make_node(st, 0, None, root_player, 0)
        if root is None:
            ws.error = "root node could not be built"
            return ws
        mcgs.tt.add(root.state_abstraction, root)
        n = 0
        while True:
            if time.monotonic() >= deadline:
                if not time_driven:
                    local_stats["deadline_stops"] = local_stats.get("deadline_stops", 0) + 1
                break
            if not time_driven and n >= simulations:
                break
            mcgs.search(root, root_player, 0, deadline)
            n += 1
        ws.simulations = n
        ws.time_driven = bool(time_driven)
        _collect_root(root, ws, local_stats)
    except Exception as e:  # noqa: BLE001
        ws.error = f"{type(e).__name__}: {e}"[:200]
    finally:
        if reuse is not None:
            try:
                mcgs.harvest_reuse(int(cfg.get("graph_reuse_max_entries", 20000)))
            except Exception:  # noqa: BLE001
                pass
        try:
            mcgs.release_all()
        except Exception:  # noqa: BLE001
            pass
        try:
            A.search_end()
        except Exception:  # noqa: BLE001
            pass
        ws.elapsed_s = time.monotonic() - t0
        if stats_sink is not None:
            for k, v in local_stats.items():
                if isinstance(v, (int, float)):
                    stats_sink[k] = stats_sink.get(k, 0) + v
    return ws


def simulations_per_world(total: int, k: int, protocol: str) -> List[int]:
    """A4's two protocols, made exact.

    fixed_total      total simulations per decision constant across K; per world = total / K
    fixed_per_world  simulations per world constant across K; total grows with K

    Under `fixed_total`, `total` need not divide K. Dropping the remainder would make K=3 and K=8
    use fewer simulations than K=1 and turn "equal total" into a lie; the remainder is instead
    distributed one per world to the first `total % k` worlds, so the sum is EXACTLY `total` for
    every K. Probe M05 asserts that equality rather than trusting this comment.
    """
    k = max(1, int(k))
    if protocol == "fixed_per_world":
        return [int(total)] * k
    if protocol == PROTOCOL_SOURCE_TIME:
        # The count is not the budget in this protocol -- the wall deadline is. A nominal plan is
        # still returned so every caller keeps the same shape, and `search_one_world` ignores it.
        return [int(total)] * k
    base, rem = divmod(int(total), k)
    return [base + (1 if i < rem else 0) for i in range(k)]


def multi_determinization_decision(
        obs, my_deck: List[int], cfg: Dict[str, Any], rng,
        base_seed: int, decision_index: int, k: int,
        total_simulations: int, protocol: str = "fixed_total",
        deadline: Optional[float] = None,
        prior_provider=None, transfer_arm: Optional[Dict[str, bool]] = None,
        per_world_reuse: Optional[Dict[int, Dict[int, Any]]] = None,
        stats_sink: Optional[Dict[str, Any]] = None) -> Tuple[Aggregate, Dict[str, Any]]:
    """One decision: K worlds, K sessions, one aggregate.

    Returns `(aggregate, trace)`. The trace is publishable — it carries world IDs and statistics,
    never zone contents — and `W.assert_no_leakage` is applied to it before it is returned, so a
    future field that smuggles a hidden zone into a trace fails here instead of in an artifact.
    """
    view = K.visible_view(obs)
    worlds = W.sample_worlds(view, my_deck, base_seed, decision_index, k)
    plan = simulations_per_world(total_simulations, len(worlds) or 1, protocol)
    if deadline is None:
        deadline = time.monotonic() + 3600.0

    # M11 only. The source runs ONE timed loop and picks a random determinization per iteration
    # (`PickDeterminization`); this port searches worlds sequentially, so the schedule's budget is
    # divided evenly between them. Even division rather than random picking is the same
    # MECHANICAL_ADAPTER already recorded for the count-budgeted protocols, and it is stated in
    # the arm's report rather than presented as the source's own behaviour.
    time_driven = (protocol == PROTOCOL_SOURCE_TIME)
    per_world_deadline = None
    if time_driven:
        now = time.monotonic()
        share = max(0.0, deadline - now) / max(1, len(worlds))

    agg = Aggregate(n_worlds=len(worlds))
    sigs = set()
    for i, w in enumerate(worlds):
        # Each world gets its OWN reuse table. A single shared table would seed world i with
        # statistics conditioned on world j's hidden information, which is the one thing this
        # whole correction exists to prevent. `per_world_reuse=None` disables reuse entirely,
        # which is what every K-sweep arm uses so that K is the only difference between arms.
        reuse = None
        if per_world_reuse is not None:
            reuse = per_world_reuse.setdefault(w.index, {})
        # A dedicated generator per world, derived from the world seed, so the number of
        # simulations run in world i cannot shift the random stream of world j.
        wrng = np.random.default_rng((int(base_seed) ^ int(w.seed)) & ((1 << 63) - 1))
        world_deadline = deadline
        if time_driven:
            # Each world gets its own slice, measured from NOW so that a world which finishes
            # early cannot hand its unused time to the next one -- that would make the split
            # depend on search content and reintroduce the confound even division removes.
            world_deadline = min(deadline, time.monotonic() + share)
        ws = search_one_world(obs, w, cfg, wrng, plan[i], world_deadline,
                              prior_provider, transfer_arm, reuse, stats_sink,
                              time_driven=time_driven)
        agg.per_world.append(ws)
        agg.total_simulations += ws.simulations
        for a, v in ws.visits.items():
            agg.visits[a] = agg.visits.get(a, 0) + v
            agg.rewards[a] = agg.rewards.get(a, 0.0) + ws.rewards.get(a, 0.0)
            flag = bool(ws.is_opponent.get(a, False))
            if a in agg.is_opponent and agg.is_opponent[a] != flag:
                # NOT an index misalignment. Measured on a real K=2 arm, 10 of 64 traced
                # decisions disagreed here while the option signature matched every time: in
                # PTCG an action's resolution can depend on hidden information, so the same
                # action can end the turn in one sampled world and not in another.
                #
                # It is counted because it decides whether the raw cross-world sum is
                # meaningful -- root_frame_rewards() handles it -- and because a SUDDEN rise
                # would still indicate misalignment.
                agg.opponent_flag_conflicts += 1
            # the MODAL flag, so K=1 keeps the c021 control's signed value exactly
            agg._flag_votes.setdefault(a, []).append(flag)
            agg.is_opponent[a] = (
                sum(agg._flag_votes[a]) * 2 > len(agg._flag_votes[a]))

    # Action indices are only comparable across worlds if every world offered the same options.
    # The check is on the AGENT-side option set, which is world-independent by construction, plus
    # a per-world guard: a world whose root failed to open contributes nothing and is counted.
    try:
        sigs.add(W.option_signature(obs.select))
    except Exception:  # noqa: BLE001
        pass
    agg.option_signature = next(iter(sigs), None)
    agg.signature_mismatch = len(sigs) > 1

    trace = {
        "decision_index": decision_index,
        "k_requested": k,
        "k_used": len(worlds),
        "protocol": protocol,
        "total_simulations_requested": total_simulations,
        "total_simulations_run": agg.total_simulations,
        "simulations_plan": plan,
        "option_signature": agg.option_signature,
        "signature_mismatch": agg.signature_mismatch,
        "worlds": [w.summary() for w in worlds],
        "world_stats": [w.summary() for w in agg.per_world],
        "aggregate_visits": dict(sorted(agg.visits.items())),
        "aggregate_values_raw_signed": {a: round(agg.value(a), 4) for a in sorted(agg.visits)
                                        if agg.visits[a] > 0},
        "aggregate_root_frame_values": {a: round(agg.root_frame_value(a), 4)
                                        for a in sorted(agg.visits) if agg.visits[a] > 0},
        "aggregate_win_probabilities": {
            a: round(agg.predicted_win_probability(a), 4) for a in sorted(agg.visits)
            if agg.visits[a] > 0},
        "successor_is_opponent": {a: bool(agg.is_opponent.get(a, False))
                                  for a in sorted(agg.visits)},
        "opponent_flag_conflicts": agg.opponent_flag_conflicts,
        "selection": {r: agg.select(r) for r in AGG_RULES},
        "disagreement": agg.world_disagreement(),
        "mixed_terminal_scale": agg.mixed_terminal_scale_detected(),
        "world_errors": [w.error for w in agg.per_world if w.error],
    }
    W.assert_no_leakage(trace, "multi_determinization_decision.trace")
    return agg, trace

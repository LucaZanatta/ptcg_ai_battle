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


@dataclass
class WorldStats:
    """Root edge statistics from ONE world, keyed by action index."""

    world_index: int
    world_id: str
    simulations: int = 0
    visits: Dict[int, int] = field(default_factory=dict)
    rewards: Dict[int, float] = field(default_factory=dict)
    edge_visits: Dict[int, int] = field(default_factory=dict)
    root_visit_count: int = 0
    root_edges: int = 0
    expanded_actions: int = 0
    error: Optional[str] = None
    elapsed_s: float = 0.0
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
    per_world: List[WorldStats] = field(default_factory=list)
    n_worlds: int = 0
    total_simulations: int = 0
    option_signature: Optional[str] = None
    signature_mismatch: bool = False

    def value(self, action: int) -> Optional[float]:
        v = self.visits.get(action, 0)
        return (self.rewards.get(action, 0.0) / v) if v > 0 else None

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

        Defined ONCE, here, as the aggregate value of the SELECTED action: summed rewards over
        summed visits across worlds. Not the maximum over worlds, and not the value in whichever
        world liked it most — either of those would report the search's most optimistic world as
        its belief and guarantee that calibration cannot improve with K.

        Rollout returns are in [0, 1] (`PlayUntilTerminal` returns 1.0 for a root-player win, 0.0
        otherwise, and 0.0 at the turn cap), so the aggregate value is already a probability. The
        source's terminal ±10 scale would break that, which is why `terminal_leaves` is counted
        per world: if it ever becomes nonzero the mixed scale must be handled explicitly rather
        than discovered in a calibration plot.
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
                     stats_sink: Optional[Dict[str, Any]] = None) -> WorldStats:
    """Run one source-faithful MCGS session in one hidden world.

    `simulations` is a COUNT, not a time budget: `MANDATORY_IMPLEMENTATION A4` requires causal
    attribution by simulation count with wall clock recorded separately. `deadline` is only a
    safety stop so a pathological decision cannot hang a run; every activation is counted.
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
        while n < simulations:
            if time.monotonic() >= deadline:
                local_stats["deadline_stops"] = local_stats.get("deadline_stops", 0) + 1
                break
            mcgs.search(root, root_player, 0, deadline)
            n += 1
        ws.simulations = n
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
        ws = search_one_world(obs, w, cfg, wrng, plan[i], deadline,
                              prior_provider, transfer_arm, reuse, stats_sink)
        agg.per_world.append(ws)
        agg.total_simulations += ws.simulations
        for a, v in ws.visits.items():
            agg.visits[a] = agg.visits.get(a, 0) + v
            agg.rewards[a] = agg.rewards.get(a, 0.0) + ws.rewards.get(a, 0.0)

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
        "aggregate_values": {a: round(agg.value(a), 4) for a in sorted(agg.visits)
                             if agg.visits[a] > 0},
        "selection": {r: agg.select(r) for r in AGG_RULES},
        "disagreement": agg.world_disagreement(),
        "mixed_terminal_scale": agg.mixed_terminal_scale_detected(),
        "world_errors": [w.error for w in agg.per_world if w.error],
    }
    W.assert_no_leakage(trace, "multi_determinization_decision.trace")
    return agg, trace

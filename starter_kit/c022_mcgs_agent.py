"""c022 — the multi-determinization MCGS agent.

One agent class covers every arm the contract names, because an arm that is a different CLASS is
an arm whose difference cannot be attributed:

```text
MCGS_K1_CONTROL                 K=1, reuse off      the K sweep's control
MCGS_K1_CONTROL_REUSE           K=1, reuse on       probe M04 identity vs the c021 control
MCGS_MULTI_DET_K2 / K4 / K8     K>1, reuse off      the correction
```

`K` and the budget protocol are configuration, so a sweep varies exactly one thing.

Search is budgeted by SIMULATION COUNT, not wall clock (`MANDATORY_IMPLEMENTATION A4`: "Use
simulation counts for causal attribution, not wall-clock. Record elapsed time separately."). c021
budgeted by time, which is why its own worker-scaling measurement found `sims_per_decision`
collapsing to 8% at 24 workers while the field score revealed nothing. A simulation-budgeted arm
cannot be corrupted that way: contention makes it slower, not weaker.

The deployment arm re-introduces a clock, because Kaggle imposes one. It is a separately named
branch and `FIDELITY_RULES §2` forbids judging source transfer by it.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import api as A  # noqa: E402
from cg import c019_core as K  # noqa: E402
from cg import c020_override as OV  # noqa: E402
from cg import c021_mcgs as S  # noqa: E402
from cg import c021_mcgs_graph as G  # noqa: E402
from cg import c022_mcgs_multidet as MD  # noqa: E402
from cg import c022_mcgs_worlds as W  # noqa: E402

BRANCH_REFERENCE = "MCGS_2019_PTCG_MULTI_DET_REFERENCE"
BRANCH_DEPLOY = "MCGS_2019_PTCG_MULTI_DET_KAGGLE_DEPLOY"
BRANCH_K1 = "MCGS_K1_CONTROL"

# Simulation-budgeted reference configuration. Every field the c021 port used that is a SEARCH
# property is inherited unchanged; every field that is a BUDGET property is replaced by a count.
REFERENCE_CFG: Dict[str, Any] = {
    # ---- source constants, unchanged from the c021 port
    "uct_constant": G.UCT_CONSTANT,
    "sample_width": G.SAMPLE_WIDTH,
    "damping_parameter": G.DAMPING_PARAMETER,
    "ucd_d1": 1, "ucd_d2": 0,
    "selection_strategy": "UCD",
    "final_move_selection": "MaxChild",
    "manual_coin": True,

    # ---- c022 multi-determinization
    "branch": BRANCH_REFERENCE,
    "k_worlds": 1,
    "budget_protocol": "fixed_total",          # or "fixed_per_world"
    "simulations_per_decision": 512,           # total (fixed_total) or per world (per_world)
    "aggregation_rule": MD.AGG_SOURCE_SUM,
    "world_base_seed": 0,                      # set per game by the runner

    # ---- reuse. OFF for every K-sweep arm; see PREREGISTERED_AGGREGATION.json.
    "graph_reuse": False,
    "graph_reuse_max_entries": 20000,

    # ---- clocks. Zero disables. The reference arm is simulation-budgeted and has NO clock;
    # the deploy arm sets these.
    "match_clock_seconds": 0.0,
    "decision_seconds_cap": 0.0,
    # A safety stop so one pathological decision cannot hang a whole run. Every activation is
    # counted in `decision_deadline_stops`, and an arm with a nonzero count has not delivered its
    # simulation budget and must say so rather than quietly reporting fewer simulations.
    "decision_wall_ceiling_seconds": 120.0,
    # MECHANICAL_ADAPTER, and the one that keeps the K sweep causal. Past this many SEARCHED
    # decisions the agent still plays every decision, it simply stops searching -- exactly as a
    # real player out of time must.
    #
    # It must be a DECISION count, not a wall clock. A per-game wall clock cuts a K=8 arm eight
    # times earlier in decision space than a K=1 arm under fixed_per_world, and since abandoned
    # games are excluded from the field score, the K=8 survivors would be systematically shorter
    # games. "K=8 is worse" would then be indistinguishable from "K=8 dropped its long games" --
    # the same shape as c021's contention artifact, where the counts looked right and the
    # attribution was wrong. A decision cap truncates every K identically.
    "decision_budget": 260,

    # ---- source timing, recorded for the unrestricted arm
    "first_move_seconds": G.FIRST_MOVE_SECONDS,
    "continuing_move_seconds": G.CONTINUING_MOVE_SECONDS,
}


class MultiDetMCGSAgent:
    """Plays one seat with K independent hidden worlds per decision."""

    def __init__(self, deck: List[int], cfg: Optional[Dict[str, Any]] = None, seed: int = 0,
                 prior_provider=None, transfer_arm: Optional[Dict[str, bool]] = None):
        self.deck = list(deck)
        self.cfg = {**REFERENCE_CFG, **(cfg or {})}
        self.seed = int(seed)
        self.rng = np.random.default_rng(seed)
        self.prior_provider = prior_provider
        self.transfer_arm = dict(transfer_arm or {})

        self.stats: Dict[str, Any] = S.new_stats()
        self.stats.update({
            "decisions": 0, "searched_decisions": 0, "single_option_decisions": 0,
            "k_used_total": 0, "world_errors": 0, "decision_deadline_stops": 0,
            "match_clock_exhausted_decisions": 0, "signature_mismatches": 0,
            "mixed_terminal_scale_decisions": 0, "aggregate_empty_decisions": 0,
            "decision_budget_exhausted_decisions": 0, "opponent_flag_conflicts": 0,
            "multiselect_decisions": 0, "obliged_decisions": 0,
        })
        self.decision_index = 0
        self.match_search_ms = 0.0
        self.traces: List[Dict[str, Any]] = []
        self.calibration: List[Dict[str, Any]] = []
        self.exceptions: List[Dict[str, Any]] = []
        self._first_move_done = False
        # world index -> reuse table. Only populated when graph_reuse is on, and NEVER shared
        # between world indices.
        self._per_world_reuse: Optional[Dict[int, Dict[int, Any]]] = (
            {} if self.cfg.get("graph_reuse") else None)

    # ------------------------------------------------------------------ budget
    def _decision_deadline(self) -> float:
        """Wall ceiling only. The real budget is a simulation count.

        The deploy arm additionally imposes a per-decision cap and a cumulative match clock,
        which is what makes it a deployment arm and not a reference arm.
        """
        ceiling = float(self.cfg.get("decision_wall_ceiling_seconds") or 0.0) or 3600.0
        cap = float(self.cfg.get("decision_seconds_cap") or 0.0)
        if cap > 0:
            ceiling = min(ceiling, cap)
        clock = float(self.cfg.get("match_clock_seconds") or 0.0)
        if clock > 0:
            left = clock - self.match_search_ms / 1000.0
            if left <= 0:
                return -1.0
            ceiling = min(ceiling, left)
        return time.monotonic() + ceiling

    def _payload_for(self, sel, opts, agg, action: int) -> List[int]:
        """Turn the search's chosen ACTION INDEX into a legal payload.

        The graph search ranks single action indices, because that is what
        `MonteCarloGraphSearch` does: one `PlayerTask` per edge. A PTCG select with
        `minCount > 1` is not a single pick — it is a SET, and a payload naming one option is
        rejected outright.

        Emitting `[opts[action]]` unconditionally is what made 10 of 60 games in the m04 arm end
        `["INVALID", "DONE"]` with `decision_budget_exhausted_decisions: 0` — so it was not the
        out-of-budget fallback at all, it was the SEARCHED path. The two look identical in every
        aggregate counter, which is why the terminal-status histogram had to exist before the
        cause could be found.

        `SEMANTIC_GAME_ADAPTER`. The extension is the smallest one that keeps the search's own
        ranking: take the top `minCount` action indices by the aggregate value the search already
        computed, with the chosen action first. Any other rule — a random completion, the first
        `minCount` options — would discard the search's opinion about every element after the
        first, which is precisely the c019/c020 defect of scoring a k-element select as if it
        were a single pick.
        """
        n = len(opts)
        lo = int(getattr(sel, "minCount", 1) or 1)
        hi = int(getattr(sel, "maxCount", 1) or 1)
        hi = max(1, min(hi, n))
        lo = max(1, min(lo, hi))
        if lo <= 1:
            return K.to_select_payload([opts[action]], sel)
        self.stats["multiselect_decisions"] = self.stats.get("multiselect_decisions", 0) + 1
        ranked = sorted((a for a in agg.visits if agg.visits[a] > 0 and a < n),
                        key=lambda a: -(agg.value(a) if agg.value(a) is not None else -1e9))
        picks = [action] + [a for a in ranked if a != action]
        # an option the search never expanded is still legal, and the payload must reach `lo`
        picks += [i for i in range(n) if i not in picks]
        return K.to_select_payload([opts[i] for i in picks[:lo]], sel)

    def _fallback_payload(self, sel, opts) -> List[int]:
        """An out-of-budget move that is LEGAL and guarantees the game advances.

        A PTCG select carries `minCount..maxCount`, and the engine rejects a payload naming fewer
        than `minCount` options. The first version of this returned a SINGLE option always, which
        is invalid whenever `minCount > 1` — the environment then marks the agent INVALID and the
        game ends with statuses `["INVALID", "DONE"]`, producing no score at all.

        That is how 10 of 60 games in the first arm vanished from the field score: not abandoned,
        not errored, just never scored, and folded into no category. An arm's field score is
        computed over completed games, so an agent that invalidates its own long games looks
        better than it is — the games it ruins are exactly the ones it was losing slowly.

        Ending the turn is preferred because it always advances the game; a repeatable action
        that does not change state can otherwise be replayed forever. Everything else is drawn
        from the SEEDED generator, never the global one.
        """
        n = len(opts)
        lo = int(getattr(sel, "minCount", 1) or 1)
        hi = int(getattr(sel, "maxCount", 1) or 1)
        hi = max(1, min(hi, n))
        lo = max(1, min(lo, hi))
        if lo <= 1:
            for o in opts:
                if int(getattr(o, "option_type", -1) or -1) == OV.OPT_END:
                    return K.to_select_payload([o], sel)
        idx = list(self.rng.permutation(n)[:lo])
        return K.to_select_payload([opts[int(i)] for i in idx], sel)

    # ------------------------------------------------------------------ act
    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(self.deck)                       # deck submission step
        self.stats["decisions"] += 1
        self.decision_index += 1
        opts = K.canonical_options(sel)
        if not opts:
            return [0]
        if len(opts) == 1:
            self.stats["single_option_decisions"] += 1
            return K.to_select_payload([opts[0]], sel)
        # An OBLIGED decision -- minCount already requires every option on offer -- has exactly
        # one legal answer, so searching it spends the whole budget proving the only legal move
        # is the only legal move.
        _lo = int(getattr(sel, "minCount", 1) or 1)
        if _lo >= len(opts):
            self.stats["obliged_decisions"] = self.stats.get("obliged_decisions", 0) + 1
            return K.to_select_payload(list(opts), sel)

        budget = int(self.cfg.get("decision_budget") or 0)
        if budget and self.stats["searched_decisions"] >= budget:
            self.stats["decision_budget_exhausted_decisions"] += 1
            return self._fallback_payload(sel, opts)

        t0 = time.monotonic()
        deadline = self._decision_deadline()
        if deadline < 0:
            self.stats["match_clock_exhausted_decisions"] += 1
            return self._fallback_payload(sel, opts)

        k = max(1, int(self.cfg.get("k_worlds", 1)))
        sims = int(self.cfg.get("simulations_per_decision", 512))
        protocol = str(self.cfg.get("budget_protocol", "fixed_total"))
        chosen = None
        try:
            o = A.to_observation_class(obs_dict)
            agg, trace = MD.multi_determinization_decision(
                o, self.deck, self.cfg, self.rng,
                base_seed=int(self.cfg.get("world_base_seed", self.seed)),
                decision_index=self.decision_index, k=k,
                total_simulations=sims, protocol=protocol, deadline=deadline,
                prior_provider=self.prior_provider, transfer_arm=self.transfer_arm,
                per_world_reuse=self._per_world_reuse, stats_sink=self.stats)

            self.stats["k_used_total"] += trace["k_used"]
            self.stats["world_errors"] += len(trace["world_errors"])
            if trace["signature_mismatch"]:
                self.stats["signature_mismatches"] += 1
            self.stats["opponent_flag_conflicts"] = (
                self.stats.get("opponent_flag_conflicts", 0)
                + int(trace.get("opponent_flag_conflicts", 0)))
            if trace["mixed_terminal_scale"]:
                self.stats["mixed_terminal_scale_decisions"] += 1

            action = agg.select(str(self.cfg.get("aggregation_rule", MD.AGG_SOURCE_SUM)))
            if action is None:
                self.stats["aggregate_empty_decisions"] += 1
            elif action < len(opts):
                chosen = self._payload_for(sel, opts, agg, action)
                self.stats["searched_decisions"] += 1
                p = agg.predicted_win_probability(action)
                raw = agg.raw_aggregate_value(action)
                # One calibration row per decision. The realised outcome is stapled on by the
                # runner once the game finishes -- a predicted probability with no realised
                # outcome is not a calibration record, it is a log line.
                self.calibration.append({
                    "decision": self.decision_index,
                    "k": trace["k_used"],
                    "protocol": protocol,
                    "simulations": trace["total_simulations_run"],
                    "action": int(action),
                    "n_options": len(opts),
                    "predicted_win_probability": round(float(p), 6) if p is not None else None,
                    "raw_aggregate_value_signed": round(float(raw), 6)
                    if raw is not None else None,
                    "successor_is_opponent": bool(agg.is_opponent.get(action, False)),
                    "visits": int(agg.visits.get(action, 0)),
                    "modal_agreement": trace["disagreement"]["modal_agreement"],
                    "distinct_best_actions": trace["disagreement"]["distinct_best_actions"],
                    "selected_value_sd": (
                        trace["disagreement"]["selected_action_value_across_worlds"] or {}
                    ).get("sd"),
                })
            if len(self.traces) < 400:
                self.traces.append(trace)
            if any(w.error and "deadline" in str(w.error) for w in agg.per_world):
                self.stats["decision_deadline_stops"] += 1
            if trace["total_simulations_run"] < trace["total_simulations_requested"]:
                self.stats["decision_deadline_stops"] += 1
        except Exception as e:  # noqa: BLE001
            if len(self.exceptions) < 200:
                import traceback
                self.exceptions.append({"decision": self.decision_index,
                                        "type": type(e).__name__, "msg": str(e)[:240],
                                        "tb": traceback.format_exc()[-700:]})
        finally:
            self.match_search_ms += (time.monotonic() - t0) * 1000.0
            self._first_move_done = True

        if chosen is None:
            chosen = self._fallback_payload(sel, opts)
        return list(chosen)

    # ------------------------------------------------------------------ report
    def report(self) -> Dict[str, Any]:
        s = dict(self.stats)
        s["branch"] = self.cfg["branch"]
        s["k_worlds"] = self.cfg["k_worlds"]
        s["budget_protocol"] = self.cfg["budget_protocol"]
        s["simulations_per_decision_config"] = self.cfg["simulations_per_decision"]
        s["aggregation_rule"] = self.cfg["aggregation_rule"]
        s["graph_reuse"] = bool(self.cfg.get("graph_reuse"))
        s["decision_budget"] = self.cfg.get("decision_budget")
        s["match_search_ms"] = round(self.match_search_ms, 1)
        sd = max(1, s.get("searched_decisions", 0))
        s["sims_per_decision"] = round(s.get("searches", 0) / sd, 1)
        s["mean_k_used"] = round(s.get("k_used_total", 0) / sd, 3)
        s["transfer_arm"] = self.transfer_arm
        s["ucd_recursion_active"] = G.UCDParams(
            self.cfg["ucd_d1"], self.cfg["ucd_d2"]).recursion_is_active
        W.assert_no_leakage(s, "MultiDetMCGSAgent.report")
        return s

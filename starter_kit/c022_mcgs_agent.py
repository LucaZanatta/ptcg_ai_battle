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

    def _progress_option(self, opts):
        """An out-of-budget move that guarantees the game advances.

        Ending the turn always advances; otherwise a uniform draw from the SEEDED generator.
        c021 shipped a bare `random.choice` here once, which injected non-determinism into runs
        that were otherwise identically seeded.
        """
        for o in opts:
            if int(getattr(o, "option_type", -1) or -1) == OV.OPT_END:
                return o
        return opts[int(self.rng.integers(len(opts)))]

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

        t0 = time.monotonic()
        deadline = self._decision_deadline()
        if deadline < 0:
            self.stats["match_clock_exhausted_decisions"] += 1
            return K.to_select_payload([self._progress_option(opts)], sel)

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
            if trace["mixed_terminal_scale"]:
                self.stats["mixed_terminal_scale_decisions"] += 1

            action = agg.select(str(self.cfg.get("aggregation_rule", MD.AGG_SOURCE_SUM)))
            if action is None:
                self.stats["aggregate_empty_decisions"] += 1
            elif action < len(opts):
                chosen = K.to_select_payload([opts[action]], sel)
                self.stats["searched_decisions"] += 1
                p = agg.predicted_win_probability(action)
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
            chosen = K.to_select_payload([self._progress_option(opts)], sel)
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
        s["match_search_ms"] = round(self.match_search_ms, 1)
        sd = max(1, s.get("searched_decisions", 0))
        s["sims_per_decision"] = round(s.get("searches", 0) / sd, 1)
        s["mean_k_used"] = round(s.get("k_used_total", 0) / sd, 3)
        s["transfer_arm"] = self.transfer_arm
        s["ucd_recursion_active"] = G.UCDParams(
            self.cfg["ucd_d1"], self.cfg["ucd_d2"]).recursion_is_active
        W.assert_no_leakage(s, "MultiDetMCGSAgent.report")
        return s

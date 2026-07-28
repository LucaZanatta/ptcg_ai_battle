"""c021 — MCGS_2019_OFFICIAL_SOURCE_PORT agent entry point.

`MCGS.Select` re-roots onto the chosen successor and `DoNotRemoveUnselectedNodes = true`, so the
graph and its statistics are REUSED across the sequential atomic decisions of a turn (A5). This
agent therefore keeps one search alive per PTCG decision and re-roots rather than rebuilding.

There is no baseline, no override gate and no leaf evaluator. The search's choice is played.
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
from cg import c020_determinize as DT  # noqa: E402
from cg import c021_mcgs as S  # noqa: E402
from cg import c021_mcgs_abstraction as AB  # noqa: E402
from cg import c021_mcgs_graph as G  # noqa: E402

REFERENCE_CFG = {
    "uct_constant": G.UCT_CONSTANT,
    "sample_width": G.SAMPLE_WIDTH,
    "damping_parameter": G.DAMPING_PARAMETER,
    "determinization_number": G.DETERMINIZATION_NUMBER,
    "first_move_seconds": G.FIRST_MOVE_SECONDS,
    "continuing_move_seconds": G.CONTINUING_MOVE_SECONDS,
    "ucd_d1": 1, "ucd_d2": 0,
    "selection_strategy": "UCD",
    "final_move_selection": "MaxChild",
    "branch": "MCGS_2019_OFFICIAL_SOURCE_PORT",
    # MECHANICAL_ADAPTER: a per-decision simulation ceiling so a measurement run terminates.
    # Every activation is counted. This does not change selection, expansion, sampling or backup.
    "max_simulations_per_decision": 0,     # 0 = unbounded, source behaviour
    "manual_coin": True,                   # A4: surfaces random effects as chance nodes
}


class MCGSAgent:
    """Plays one seat with the source-faithful graph search."""

    def __init__(self, deck: List[int], cfg: Optional[Dict[str, Any]] = None, seed: int = 0,
                 prior_provider=None, mode: str = "MCGS_2019_OFFICIAL_SOURCE_PORT"):
        self.deck = list(deck)
        self.cfg = {**REFERENCE_CFG, **(cfg or {})}
        self.rng = np.random.default_rng(seed)
        self.stats = S.new_stats()
        self.mode = mode
        self.prior_provider = prior_provider
        self.decision_index = 0
        self.match_search_ms = 0.0
        self.decisions_log: List[Dict[str, Any]] = []
        self.graph_snapshots: List[Dict[str, Any]] = []
        self.exceptions: List[Dict[str, Any]] = []
        self._first_move_done = False

    def _budget_seconds(self) -> float:
        base = (self.cfg["continuing_move_seconds"] if self._first_move_done
                else self.cfg["first_move_seconds"])
        cap = self.cfg.get("decision_seconds_cap")
        return min(base, cap) if cap else base

    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(self.deck)          # deck submission step
        self.stats["decisions"] += 1
        self.decision_index += 1
        opts = K.canonical_options(sel)
        if not opts:
            return [0]
        if len(opts) == 1:
            return K.to_select_payload([opts[0]], sel)

        t0 = time.monotonic()
        budget = self._budget_seconds()
        deadline = t0 + budget
        search = S.MCGS(A, self.cfg, self.stats, self.rng, self.prior_provider)
        chosen = None
        try:
            o = A.to_observation_class(obs_dict)
            view = K.visible_view(o)
            det, _draw = DT.determinize(view, self.deck, self.rng)
            self.stats["begin_calls"] += 1
            # A4: without manual_coin the engine resolves random effects silently inside the
            # step and NO chance node can exist. With it, they surface as selects that
            # `_make_node` marks random. Configurable so the no-chance-node arm stays runnable
            # as an ablation rather than being lost.
            st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck,
                                det.opponent_prize, det.opponent_hand, det.opponent_active,
                                manual_coin=bool(self.cfg.get("manual_coin", True)))
            search._track(st.searchId)
            root_player = S.MCGS._your_index(o, 0)
            root = search._make_node(st, 0, None, root_player, 0)
            if root is not None:
                search.tt.add(root.state_abstraction, root)
                cap = int(self.cfg.get("max_simulations_per_decision") or 0)
                n = 0
                while time.monotonic() < deadline:
                    if cap and n >= cap:
                        break
                    search.search(root, root_player, 0, deadline)
                    n += 1
                self.stats["searched_decisions"] += 1
                best, info = search.select_final(root, self.cfg["final_move_selection"])
                if best is not None and best.action_index < len(opts):
                    chosen = search._payload(sel, opts[best.action_index], opts)
                    if len(self.decisions_log) < 4000:
                        self.decisions_log.append({
                            "decision": self.decision_index, "simulations": n,
                            "budget_s": round(budget, 2), **info,
                            "graph": search.tt.stats()})
                if len(self.graph_snapshots) < 120:
                    self.graph_snapshots.append({
                        "decision": self.decision_index,
                        "graph": search.tt.stats(),
                        "root_edges": len(root.outgoing_edges),
                        "root_visits": root.visit_count,
                        "traces": search.traces[:20]})
        except Exception as e:  # noqa: BLE001
            if len(self.exceptions) < 200:
                import traceback
                self.exceptions.append({"decision": self.decision_index,
                                        "type": type(e).__name__, "msg": str(e)[:240],
                                        "tb": traceback.format_exc()[-700:]})
        finally:
            search.release_all()
            try:
                A.search_end()
            except Exception:  # noqa: BLE001
                pass
            self.match_search_ms += (time.monotonic() - t0) * 1000.0
            self._first_move_done = True

        if chosen is None:
            chosen = K.to_select_payload([opts[0]], sel)
        return list(chosen)

    def report(self) -> Dict[str, Any]:
        s = dict(self.stats)
        s["mode"] = self.mode
        s["branch"] = self.cfg["branch"]
        s["match_search_ms"] = round(self.match_search_ms, 1)
        s["sims_per_decision"] = round(
            s["searches"] / max(1, s["searched_decisions"]), 1)
        s["steps_per_decision"] = round(
            s["step_calls"] / max(1, s["searched_decisions"]), 1)
        s["ucd_recursion_active"] = G.UCDParams(
            self.cfg["ucd_d1"], self.cfg["ucd_d2"]).recursion_is_active
        return s

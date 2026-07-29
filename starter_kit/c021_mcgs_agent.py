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
from cg import c020_override as OV  # noqa: E402
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
    # A5. `MCGS.Select` re-roots onto the chosen successor with DoNotRemoveUnselectedNodes = true,
    # so statistics survive across the sequential atomic decisions of a turn.
    #
    # The PTCG API cannot reuse the ENGINE STATES: `search_end` invalidates every searchId, and an
    # interior observation carries no `search_begin_input`, so the next decision must open a fresh
    # session. What CAN carry over is the part that matters -- the statistics keyed by state
    # abstraction. A node whose abstraction was already searched is seeded with the visits and
    # rewards it accumulated, which is exactly what re-rooting preserves.
    "graph_reuse": True,
    "graph_reuse_max_entries": 20000,
    # MECHANICAL_ADAPTER: a CUMULATIVE MATCH CLOCK, in seconds of search across the whole game.
    # The source has a per-move budget and no match budget, but PTCG competition play is governed
    # by a cumulative clock, so this is closer to the deployment constraint than an unbounded
    # per-move budget is.
    #
    # It also fixes a measured pathology: one game ran 10+ minutes at a 0.9 s per-decision budget
    # while every other worker had finished, blocking the pool barrier. A game that reaches
    # several hundred decisions spends its budget on each one, and a single such game stalls a
    # whole run. Past the clock the agent still plays every decision -- it simply stops searching
    # and takes the first legal option, exactly as a real player out of time must. Every
    # activation is counted in `match_clock_exhausted_decisions`.
    "match_clock_seconds": 90.0,
}


class MCGSAgent:
    """Plays one seat with the source-faithful graph search."""

    def __init__(self, deck: List[int], cfg: Optional[Dict[str, Any]] = None, seed: int = 0,
                 prior_provider=None, mode: str = "MCGS_2019_OFFICIAL_SOURCE_PORT",
                 transfer_arm: Optional[Dict[str, bool]] = None):
        self.deck = list(deck)
        self.cfg = {**REFERENCE_CFG, **(cfg or {})}
        self.rng = np.random.default_rng(seed)
        self.stats = S.new_stats()
        self.mode = mode
        self.prior_provider = prior_provider
        self.transfer_arm = dict(transfer_arm or {})
        self.decision_index = 0
        self.match_search_ms = 0.0
        self.decisions_log: List[Dict[str, Any]] = []
        self.graph_snapshots: List[Dict[str, Any]] = []
        self.exceptions: List[Dict[str, Any]] = []
        self._first_move_done = False
        # A5: abstraction -> (visit_count, rewards, total_visit), carried across decisions
        self._reuse: Dict[int, Any] = {}

    def _budget_seconds(self) -> float:
        base = (self.cfg["continuing_move_seconds"] if self._first_move_done
                else self.cfg["first_move_seconds"])
        cap = self.cfg.get("decision_seconds_cap")
        if cap:
            base = min(base, cap)
        clock = float(self.cfg.get("match_clock_seconds") or 0.0)
        if clock > 0:
            left = clock - self.match_search_ms / 1000.0
            if left <= 0:
                return 0.0                       # out of time: play, do not search
            base = min(base, left)
        return base

    def _progress_option(self, opts):
        """An out-of-time move that GUARANTEES the game advances.

        Always taking `opts[0]` can livelock: if the first option is a repeatable action that
        does not change state, the agent replays it forever and the game never terminates. Three
        workers were measured pinned at 100% CPU for eighteen minutes on exactly that.

        Ending the turn always advances the game, so it is preferred; otherwise a uniform random
        legal option, which terminates with probability 1.
        """
        for o in opts:
            if int(getattr(o, "option_type", -1) or -1) == OV.OPT_END:
                return o
        # self.rng, NOT the unseeded global `random`. Every other stochastic choice in this
        # agent draws from the seeded generator; a bare random.choice here injected
        # non-determinism into runs that were otherwise identically seeded, which is one of the
        # sources behind two same-configuration runs differing by 6.4 points.
        return opts[int(self.rng.integers(len(opts)))]

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
        # A10 / C3: an OBLIGED decision admits exactly one legal answer -- minCount already
        # requires every option on offer. The reference port still searches it, spending the
        # whole per-decision budget proving that the only legal move is the only legal move.
        # This was defined in c021_mcgs_legal.is_obliged and documented in the change manifest
        # but never invoked, so the manifest was claiming a correction that was not applied.
        if self.cfg.get("branch") == "MCGS_2019_PTCG_LEGAL_CORRECTED" \
                and self.cfg.get("C3_obliged_actions", True):
            from cg import c021_mcgs_legal as LG
            if LG.is_obliged(sel, opts):
                self.stats["obliged_collapsed"] = self.stats.get("obliged_collapsed", 0) + 1
                lo, _hi = LG.select_bounds(sel)
                return LG.payload_for(sel, opts, list(range(min(lo, len(opts)))))

        t0 = time.monotonic()
        budget = self._budget_seconds()
        if budget <= 0.0:
            # Match clock exhausted. Still a legal move, just an unsearched one.
            self.stats["match_clock_exhausted_decisions"] = (
                self.stats.get("match_clock_exhausted_decisions", 0) + 1)
            return K.to_select_payload([self._progress_option(opts)], sel)
        deadline = t0 + budget
        search = S.MCGS(A, self.cfg, self.stats, self.rng, self.prior_provider,
                        self.transfer_arm)
        if self.cfg.get("graph_reuse", True):
            search.reuse = self._reuse
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
            if self.cfg.get("graph_reuse", True):
                search.harvest_reuse(int(self.cfg.get("graph_reuse_max_entries", 20000)))
            search.release_all()
            try:
                A.search_end()
            except Exception:  # noqa: BLE001
                pass
            self.match_search_ms += (time.monotonic() - t0) * 1000.0
            self._first_move_done = True

        if chosen is None:
            chosen = K.to_select_payload([self._progress_option(opts)], sel)
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
        s["transfer_arm"] = self.transfer_arm
        s["ucd_recursion_active"] = G.UCDParams(
            self.cfg["ucd_d1"], self.cfg["ucd_d2"]).recursion_is_active
        return s

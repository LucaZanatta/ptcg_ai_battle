"""c020 — the corrected MCTS agent: N determinizations, ONE shared table, conservative override.

This is where A1, A7 and A8 meet. Each decision:

  1. samples `determinizations` legal worlds, drawing the archetype from the recorded prior
     mixture rather than defaulting to Dragapult (A7);
  2. runs simulations across all of them against ONE `InfoSetTable` (A1);
  3. asks the branch-local baseline what it would play (A2);
  4. lets the override gate decide whether the search has earned the right to replace it (A8).

The baseline action is what gets played unless the gate says otherwise, so the agent degrades to
the frozen baseline rather than to noise when the search is uncertain — which is the behaviour
c018 and c019 measured as strictly better than overriding freely.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import api as A  # noqa: E402
from cg import c019_core as K  # noqa: E402
from cg import c020_baseline_memory as BM  # noqa: E402
from cg import c020_determinize as DT  # noqa: E402
from cg import c020_infoset as IS  # noqa: E402
from cg import c020_ismcts as SEARCH  # noqa: E402
from cg import c020_override as OV  # noqa: E402


class CorrectedMCTSAgent:
    """Plays one seat. Owns its own baseline memory across the real game."""

    def __init__(self, deck: List[int], cfg: Optional[Dict[str, Any]] = None, seed: int = 0,
                 prior_provider=None, value_provider=None, neural_adapter=None,
                 mode: str = "C020_CORRECTED_MCTS"):
        self.deck = list(deck)
        self.cfg = {**SEARCH.DEFAULT_CFG, **(cfg or {})}
        self.rng = np.random.default_rng(seed)
        self.stats = SEARCH.new_stats()
        self.memory = BM.initial_memory()
        self.mode = mode
        self.prior_provider = prior_provider
        self.value_provider = value_provider
        self.neural_adapter = neural_adapter
        self.override_log: List[Dict[str, Any]] = []
        self.det_log: List[Dict[str, Any]] = []
        self.infoset_dumps: List[Dict[str, Any]] = []
        self.tree_traces: List[Dict[str, Any]] = []
        self.leaf_samples: List[Dict[str, Any]] = []
        self.match_search_ms = 0.0
        self.decision_index = 0
        self.exceptions: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- entry point
    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            # the no-select observation is the DECK SUBMISSION step
            return list(self.deck)

        self.stats["decisions"] += 1
        self.decision_index += 1

        # branch-local baseline recommendation is the DEFAULT action (A8)
        try:
            baseline_action, _proposed = BM.recommend(obs_dict, self.memory)
        except Exception:  # noqa: BLE001
            baseline_action = None

        opts = K.canonical_options(sel)
        if not opts:
            return list(baseline_action or [0])
        base_key = None
        if baseline_action:
            base_key = next((o.key() for o in opts if o.option_index in list(baseline_action)),
                            None)

        budget_ms = self._budget_ms()
        result = None
        if budget_ms > 0 and len(opts) > 1:
            try:
                result = self._search(obs_dict, sel, opts, base_key, budget_ms)
            except Exception as e:  # noqa: BLE001
                self.stats["timeouts"] += 1
                if len(self.exceptions) < 200:
                    import traceback
                    self.exceptions.append({"decision": self.decision_index,
                                            "type": type(e).__name__, "msg": str(e)[:300],
                                            "tb": traceback.format_exc()[-900:]})
                result = None

        chosen = baseline_action
        if result is not None:
            decision, chosen_key = result
            self.stats["override_opportunities"] += 1
            if decision.override:
                self.stats["overrides"] += 1
                opt = next((o for o in opts if o.key() == decision.selected_action), None)
                if opt is not None:
                    chosen = K.to_select_payload([opt], sel)
            else:
                self.stats["vetoes"] += 1
            rec = decision.to_json()
            rec.update({"decision": self.decision_index,
                        "executed": "override" if decision.override else "baseline"})
            if len(self.override_log) < 4000:
                self.override_log.append(rec)

        chosen = list(chosen or [opts[0].option_index])
        # A2: advance memory along what was ACTUALLY executed, not what was proposed
        try:
            self.memory = BM.advance_after_executed(obs_dict, chosen, self.memory)
        except Exception:  # noqa: BLE001
            pass
        return chosen

    # ---------------------------------------------------------------- budget
    def _budget_ms(self) -> float:
        """Cumulative ten-minute match clock with safety margin (CONTRACT §5)."""
        remaining = 600_000.0 * 0.55 - self.match_search_ms      # 45% safety margin
        if remaining <= 0:
            return 0.0
        return max(0.0, min(float(self.cfg["max_ms_per_decision"]), remaining))

    # ---------------------------------------------------------------- the search
    def _search(self, obs_dict, sel, opts, base_key, budget_ms: float):
        t0 = time.monotonic()
        o = A.to_observation_class(obs_dict)
        view = K.visible_view(o)
        search = SEARCH.InfoSetSearch(A, self.cfg, self.stats, self.rng,
                                      prior_fn=self.prior_provider,
                                      value_fn=self.value_provider,
                                      neural_adapter=self.neural_adapter)
        n_det = int(self.cfg["determinizations"])
        per_det = max(1, int(self.cfg["simulations_total"]) // max(1, n_det))
        deadline = t0 + budget_ms / 1000.0
        roots: List[SEARCH.WorldNode] = []
        det_records = []

        try:
            for det_id in range(n_det):
                if time.monotonic() >= deadline:
                    break
                self.stats["determinizations_attempted"] += 1
                try:
                    det, draw = DT.determinize(view, self.deck, self.rng)
                except Exception:  # noqa: BLE001
                    self.stats["determinizations_rejected"] += 1
                    continue
                ok, why = (det.validate() if hasattr(det, "validate") else (True, {}))
                if not ok:
                    self.stats["determinizations_rejected"] += 1
                    det_records.append({"det_id": det_id, "rejected": True, "why": str(why)[:200]})
                    continue
                self.stats["determinizations_legal"] += 1
                self.stats["begin_calls"] += 1
                try:
                    st = A.search_begin(o, det.your_deck, det.your_prize, det.opponent_deck,
                                        det.opponent_prize, det.opponent_hand,
                                        det.opponent_active)
                except Exception:  # noqa: BLE001
                    self.stats["begin_errors"] += 1
                    continue
                search._track(st.searchId)
                root = SEARCH.WorldNode(
                    search_id=int(st.searchId),
                    obs=getattr(st, "observation", None) or o,
                    det_id=det_id, depth=0,
                    player=int(getattr(o, "yourIndex", 0) or 0),
                    memory=BM.clone_memory(self.memory),
                    neural=(self.neural_adapter.initial() if self.neural_adapter else None))
                roots.append(root)
                rec = {"det_id": det_id, "rejected": False, **draw.to_json()}
                if hasattr(det, "to_json"):
                    try:
                        rec["determinization"] = det.to_json()
                    except Exception:  # noqa: BLE001
                        pass
                det_records.append(rec)

            if not roots:
                return None
            if len(roots) >= 4:
                self.stats["decisions_with_4_determinizations"] += 1
            if len(roots) >= 2:
                self.stats["decisions_with_2plus_determinizations"] += 1

            # A1: interleave worlds so the SHARED table accumulates cross-determinization
            # evidence as the search proceeds, rather than one world finishing before the next
            # begins.
            for i in range(per_det):
                for root in roots:
                    if time.monotonic() >= deadline:
                        break
                    search.simulate(root, deadline)
                if time.monotonic() >= deadline:
                    break

            self.stats["searched_decisions"] += 1
            return self._decide(search, roots, base_key, opts, det_records, t0)
        finally:
            search.release_all()
            try:
                A.search_end()
            except Exception:  # noqa: BLE001
                pass
            self.match_search_ms += (time.monotonic() - t0) * 1000.0

    # ---------------------------------------------------------------- override
    def _decide(self, search, roots, base_key, opts, det_records, t0):
        root_key = roots[0].info_key
        if root_key is None:
            return None
        shared = search.table.get(root_key)

        # per-world preference, for the agreement statistic (A8)
        agree: Dict[Any, float] = {}
        prefs = []
        for r in roots:
            k = r.info_key
            if k is None:
                continue
            st = search.table.get(k)
            best = max(st.actions.items(), key=lambda kv: kv[1].n, default=(None, None))[0]
            if best is not None:
                prefs.append(best)
        for k in set(prefs):
            agree[k] = prefs.count(k) / max(1, len(prefs))

        baseline_productive = base_key is not None and not OV.looks_like_end_turn(
            base_key, next((o for o in opts if o.key() == base_key), None))
        ctx = {
            "simulations": sum(a.n for a in shared.actions.values()),
            "determinizations": len(roots),
            "agreement": agree,
            "baseline_productive": baseline_productive,
            "pivotal": len(opts) > 6,
            "unsafe_latency": self.match_search_ms > 600_000 * 0.5,
            "candidate_option": None,
        }
        decision = OV.decide_override(shared, base_key, ctx)

        if len(self.det_log) < 3000:
            self.det_log.extend(det_records)
        if len(self.infoset_dumps) < 120:
            self.infoset_dumps.append({"decision": self.decision_index,
                                       **search.table.dump(limit=24)})
        if len(self.tree_traces) < 300:
            self.tree_traces.append({"decision": self.decision_index,
                                     "determinizations": len(roots),
                                     "traces": search.traces[:40],
                                     "table": search.table.stats()})
        if len(self.leaf_samples) < 1500:
            self.leaf_samples.extend(search.leaf_samples[:40])
        return decision, decision.selected_action

    # ---------------------------------------------------------------- reporting
    def report(self) -> Dict[str, Any]:
        s = dict(self.stats)
        s["mode"] = self.mode
        s["match_search_ms"] = round(self.match_search_ms, 1)
        s["override_rate"] = round(s["overrides"] / max(1, s["override_opportunities"]), 4)
        return s

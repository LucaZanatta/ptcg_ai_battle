"""c019 Branch A — PTCG_ISMCTS_V0 agent: multi-determinization search with aggregation.

Runs one tree per legal determinization and aggregates canonical root actions across them (M09).
Aggregation is by CANONICAL KEY, not by option index, because the option list can be ordered
differently in different sampled worlds — summing by index would add visits for one action onto
another and produce a confidently wrong answer.

Match-clock safety (§8.3, M11): a per-decision deadline and a cumulative per-match budget, both
enforced, with a baseline fallback on overrun. The baseline is always a candidate and is never
pruned, so degrading to it is a real safety net — but c018 proved that is only true when the
baseline's branch memory is intact, which is why `BranchLocalBaseline` exists.
"""

from __future__ import annotations

import collections
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c019_determinize as D  # noqa: E402
from cg import c019_leaf as LEAF  # noqa: E402
from cg import c019_mcts as M  # noqa: E402

AGENT_VERSION = "PTCG_ISMCTS_V0"


class ISMCTSAgent:
    """Information-set MCTS over the official forward API."""

    def __init__(self, deck: List[int], cfg: Optional[dict] = None, seed: int = 1900,
                 baseline=None, prior_provider=None, value_provider=None,
                 collect_traces: int = 0):
        from cg import c019_baseline as B
        self.deck = list(deck)
        self.cfg = dict(M.DEFAULT_CFG)
        if cfg:
            self.cfg.update(cfg)
        self.rng = np.random.default_rng(seed)
        self.baseline = baseline if baseline is not None else B.BranchLocalBaseline()
        self.stats = M.new_stats()
        self.memory = self.baseline.initial_memory()
        # hybrid adapters (§10) -- both default OFF so the pure branch cannot depend on ByteRL
        self.prior_provider = prior_provider
        self.value_provider = value_provider
        self.traces: List[Dict[str, Any]] = []
        self.collect_traces = collect_traces
        self.match_ms = 0.0

    # ---------------------------------------------------------------- main entry
    def act(self, obs_dict: dict) -> List[int]:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            action, self.memory = self.baseline.act(obs_dict, self.memory)
            return action
        self.stats["decisions"] += 1
        base_action, base_next = self.baseline.act(obs_dict, self.memory)
        opts = K.canonical_options(sel)

        if len(opts) < 2 or self.match_ms > self.cfg["max_match_ms"]:
            self.stats["fallbacks"] += 1
            self.memory = base_next
            return base_action

        t0 = time.perf_counter()
        result = self._search(obs_dict, sel, base_action)
        dt = (time.perf_counter() - t0) * 1000.0
        self.match_ms += dt
        self.stats["match_ms"] = round(self.match_ms, 2)

        if not result["searched"] or not result["agg"]:
            self.stats["fallbacks"] += 1
            self.memory = base_next
            return base_action

        best_key = result["agg"][0]["action_key"]
        chosen = next((o for o in opts if o.key() == best_key), None)
        if chosen is None:
            self.stats["fallbacks"] += 1
            self.memory = base_next
            return base_action
        try:
            payload = K.to_select_payload([chosen], sel)
        except KeyError:
            self.stats["fallbacks"] += 1
            self.memory = base_next
            return base_action

        self.stats["searched"] += 1
        if payload == list(base_action):
            self.stats["baseline_retained"] += 1
            self.memory = base_next
        else:
            self.stats["changed_action"] += 1
            self.memory = self.baseline.observe_executed(obs_dict, payload, self.memory)
        if self.collect_traces and len(self.traces) < self.collect_traces:
            self.traces.append({**result["trace"], "chosen": payload,
                                "baseline": list(base_action), "ms": round(dt, 2)})
        return payload

    # ---------------------------------------------------------------- search
    def _search(self, obs_dict: dict, sel, base_action) -> Dict[str, Any]:
        from cg import api as A
        deadline = time.perf_counter() + self.cfg["max_ms_per_decision"] / 1000.0
        try:
            o = A.to_observation_class(obs_dict)
            view = K.visible_view(o)
        except K.HiddenInformationAccess:
            self.stats["hidden_information_violations"] += 1
            return {"searched": False, "agg": [], "trace": {}}
        except Exception:  # noqa: BLE001
            return {"searched": False, "agg": [], "trace": {}}

        agg: Dict[Tuple, Dict[str, Any]] = {}
        det_records, shapes = [], []
        n_det = self.cfg["determinizations"]

        for di in range(n_det):
            if time.perf_counter() > deadline:
                break
            d = D.determinize(view, self.deck, self.rng)
            self.stats["determinizations_sampled"] += 1
            if not d.legal:
                self.stats["determinizations_rejected"] += 1
                det_records.append(d.summary())
                continue
            self.stats["determinizations_legal"] += 1

            tree = M.SearchTree(A, self.cfg, self.stats, self.rng, self.baseline,
                                LEAF.make_leaf_fn(), self.prior_provider)
            self.stats["begin_calls"] += 1
            try:
                root_state = A.search_begin(o, d.your_deck, d.your_prize, d.opponent_deck,
                                            d.opponent_prize, d.opponent_hand,
                                            d.opponent_active)
                self.stats["begin_ok"] += 1
            except Exception:  # noqa: BLE001
                self.stats["begin_errors"] += 1
                det_records.append({**d.summary(), "begin_failed": True})
                try:
                    A.search_end()
                    self.stats["end_calls"] += 1
                except Exception:  # noqa: BLE001
                    pass
                continue

            try:
                tree._track(root_state.searchId)
                root = M.MCTSNode(search_id=int(root_state.searchId),
                                  obs=root_state.observation,
                                  obs_hash=K.observation_hash(root_state.observation),
                                  det_id=d.det_id, memory=self.memory, depth=0)
                tree.root = root
                tree._set_priors(root, obs_dict)
                for _ in range(self.cfg["simulations_per_determinization"]):
                    if not tree.simulate(deadline):
                        break
                # M09: aggregate by canonical key across determinizations
                for k, ch in root.children.items():
                    e = agg.setdefault(k, {"action_key": k, "visits": 0, "value_sum": 0.0,
                                           "determinizations": 0,
                                           "option_index": ch.action_from_parent.option_index})
                    e["visits"] += ch.visits
                    e["value_sum"] += ch.value_sum
                    e["determinizations"] += 1
                shapes.append(M.tree_shape(root, 120))
                det_records.append({**d.summary(), "root_visits": root.visits,
                                    "root_children": len(root.children),
                                    "root_actions": M.summarize_root(root)[:8]})
            finally:
                tree.release_all()
                try:
                    A.search_end()
                    self.stats["end_calls"] += 1
                except Exception:  # noqa: BLE001
                    self.stats["end_errors"] += 1

        ranked = sorted(agg.values(),
                        key=lambda e: (-e["visits"], -(e["value_sum"] / max(1, e["visits"]))))
        for e in ranked:
            e["q"] = round(e["value_sum"] / e["visits"], 6) if e["visits"] else 0.0
        return {"searched": bool(ranked), "agg": ranked,
                "trace": {"determinizations": det_records, "aggregate": ranked[:10],
                          "tree_shapes": shapes[:2],
                          "config": {k: self.cfg[k] for k in
                                     ("c_puct", "simulations_per_determinization",
                                      "determinizations", "k_pw", "alpha_pw",
                                      "max_ms_per_decision")}}}

    def reset_match(self):
        self.memory = self.baseline.initial_memory()
        self.match_ms = 0.0


def make_agent(deck, cfg=None, seed=1900, **kw):
    a = ISMCTSAgent(deck, cfg, seed, **kw)
    return a

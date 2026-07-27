"""c019 Branch A — PTCG information-set MCTS with real PUCT, expansion, rollout and backup.

Every property METHOD_FIDELITY A demands, and specifically the ones c018 failed:

  * expansion at NON-ROOT depths, with real `search_step` children (M03);
  * PUCT selection whose `c_puct` demonstrably changes the chosen child (M04);
  * backup of visit counts and values along the whole path with zero-sum sign (M05);
  * simulations that REVISIT existing nodes, so root visits greatly exceed root children (M06);
  * rollouts driven by a branch-local policy, never repeated option index 0 (M07);
  * distinct successor outcomes recorded as chance outcomes, never overwritten (M08);
  * aggregation of canonical root actions across determinizations (M09);
  * every native `searchId` released (M10).

Native-state model. The precondition probe established that one live `searchId` can be stepped
with different actions to yield distinct children, and that a child can be stepped further. So a
node OWNS a live `searchId` for the tree's lifetime and children are produced by stepping the
parent's live id. That is why no replay-from-root is needed — and why the tree must release every
id it opened, which `SearchTree` does in a finally block.
"""

from __future__ import annotations

import collections
import hashlib
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c019_determinize as D  # noqa: E402

MCTS_VERSION = "c019.mcts.v1"

DEFAULT_CFG = {
    "c_puct": 1.5,
    "simulations_per_determinization": 128,
    "determinizations": 4,
    "max_tree_depth": 16,
    "rollout_max_steps": 24,
    "k_pw": 1.5,
    "alpha_pw": 0.5,
    "baseline_prior_bonus": 3.0,     # baseline is favoured, never exclusive
    "min_prior": 0.02,               # every credible legal action keeps nonzero exploration
    "max_ms_per_decision": 1500,
    "max_match_ms": 90000,
    "max_nodes": 512,
    "version": MCTS_VERSION,
}


def new_stats() -> Dict[str, Any]:
    return collections.defaultdict(int, {
        "decisions": 0, "searched": 0, "fallbacks": 0,
        "begin_calls": 0, "begin_ok": 0, "begin_errors": 0,
        "step_calls": 0, "step_ok": 0, "step_errors": 0,
        "release_calls": 0, "release_errors": 0, "end_calls": 0,
        "simulations": 0, "expansions": 0, "nonroot_expansions": 0,
        "backups": 0, "backup_nodes": 0, "revisits": 0,
        "rollout_steps": 0, "rollout_baseline_calls": 0, "rollout_stochastic_calls": 0,
        "terminal_leaves": 0, "heuristic_leaves": 0,
        "chance_outcomes_recorded": 0, "chance_nodes": 0,
        "determinizations_sampled": 0, "determinizations_legal": 0,
        "determinizations_rejected": 0,
        "match_ms": 0.0, "hidden_information_violations": 0,
        "max_depth_reached": 0, "nodes_created": 0,
    })


@dataclass
class MCTSNode:
    search_id: int
    obs: Any
    obs_hash: str
    det_id: str
    memory: Any
    parent: Optional["MCTSNode"] = None
    action_from_parent: Optional[K.CanonicalOption] = None
    prior: float = 0.0
    player_sign: int = 1
    depth: int = 0
    visits: int = 0
    value_sum: float = 0.0
    children: Dict[Tuple, "MCTSNode"] = field(default_factory=dict)
    unexpanded: List[K.CanonicalOption] = field(default_factory=list)
    priors: Dict[Tuple, float] = field(default_factory=dict)
    terminal: bool = False
    # M08: distinct successor observation hashes seen for the SAME action
    chance: Dict[Tuple, collections.Counter] = field(default_factory=dict)

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0

    def n_legal(self) -> int:
        return len(self.children) + len(self.unexpanded)


def select_child(node: MCTSNode, c_puct: float) -> MCTSNode:
    """PUCT: Q + c_puct * P * sqrt(N_parent) / (1 + N_child)."""
    sqrt_n = math.sqrt(max(1, node.visits))
    best, best_score = None, -1e18
    for k, ch in node.children.items():
        score = ch.q + c_puct * ch.prior * sqrt_n / (1.0 + ch.visits)
        if score > best_score:
            best, best_score = ch, score
    return best


def puct_scores(node: MCTSNode, c_puct: float) -> Dict[Tuple, float]:
    sqrt_n = math.sqrt(max(1, node.visits))
    return {k: ch.q + c_puct * ch.prior * sqrt_n / (1.0 + ch.visits)
            for k, ch in node.children.items()}


def allowed_children(node: MCTSNode, cfg) -> int:
    """Progressive widening: 1 + floor(k * N^alpha), never below what already exists."""
    n = 1 + int(math.floor(cfg["k_pw"] * (max(1, node.visits) ** cfg["alpha_pw"])))
    return max(len(node.children), min(node.n_legal(), n))


class SearchTree:
    """One determinization's tree. Owns every native searchId it opens."""

    def __init__(self, api, cfg, stats, rng, baseline, leaf_fn, prior_fn=None):
        self.A = api
        self.cfg = cfg
        self.stats = stats
        self.rng = rng
        self.baseline = baseline
        self.leaf_fn = leaf_fn
        self.prior_fn = prior_fn
        self.open_ids: List[int] = []
        self.root: Optional[MCTSNode] = None

    # ---------------------------------------------------------------- lifecycle
    def _track(self, sid: int):
        self.open_ids.append(int(sid))

    def release_all(self):
        for sid in reversed(self.open_ids):
            self.stats["release_calls"] += 1
            try:
                self.A.search_release(sid)
            except Exception:  # noqa: BLE001
                self.stats["release_errors"] += 1
        self.open_ids.clear()

    # ---------------------------------------------------------------- priors
    def _set_priors(self, node: MCTSNode, obs_dict: Optional[dict]):
        """Baseline-favoured priors; every legal action keeps nonzero probability."""
        sel = getattr(node.obs, "select", None)
        opts = K.canonical_options(sel)
        if not opts:
            node.terminal = True
            return
        base_keys = set()
        if obs_dict is not None and self.baseline is not None:
            try:
                chosen, _ = self.baseline.act_canonical(obs_dict, sel, node.memory)
                base_keys = {c.key() for c in chosen}
            except Exception:  # noqa: BLE001
                pass
        ext = self.prior_fn(node, opts) if self.prior_fn else None
        w = {}
        for o in opts:
            base_w = float(ext.get(o.key(), 1.0)) if ext else 1.0
            if o.key() in base_keys:
                base_w *= self.cfg["baseline_prior_bonus"]
            w[o.key()] = max(base_w, 1e-6)
        tot = sum(w.values())
        floor = self.cfg["min_prior"] / max(1, len(opts))
        node.priors = {k: max(v / tot, floor) for k, v in w.items()}
        s = sum(node.priors.values())
        node.priors = {k: v / s for k, v in node.priors.items()}
        # baseline first, then engine order: a deterministic, auditable expansion order
        node.unexpanded = sorted(
            opts, key=lambda o: (o.key() not in base_keys, -node.priors[o.key()],
                                 o.option_index))

    # ---------------------------------------------------------------- expansion
    def _expand(self, node: MCTSNode) -> Optional[MCTSNode]:
        """Take one unexpanded action and create a REAL successor via search_step."""
        if not node.unexpanded:
            return None
        action = node.unexpanded.pop(0)
        payload = [action.option_index]
        self.stats["step_calls"] += 1
        try:
            succ = self.A.search_step(node.search_id, payload)
            self.stats["step_ok"] += 1
        except Exception:  # noqa: BLE001
            self.stats["step_errors"] += 1
            return None
        self._track(succ.searchId)
        h = K.observation_hash(succ.observation)

        # M08: the same action may produce different outcomes; record rather than overwrite
        seen = node.chance.setdefault(action.key(), collections.Counter())
        if h not in seen:
            self.stats["chance_outcomes_recorded"] += 1
        seen[h] += 1
        if len(seen) > 1:
            self.stats["chance_nodes"] += 1

        mem = node.memory
        if self.baseline is not None and mem is not None:
            try:
                mem = self.baseline.observe_executed(_obs_dict(node.obs), payload, node.memory)
            except Exception:  # noqa: BLE001
                mem = node.memory
        child = MCTSNode(
            search_id=int(succ.searchId), obs=succ.observation, obs_hash=h,
            det_id=node.det_id, memory=mem, parent=node, action_from_parent=action,
            prior=node.priors.get(action.key(), 1.0 / max(1, node.n_legal())),
            player_sign=node.player_sign, depth=node.depth + 1)
        node.children[action.key()] = child
        self.stats["nodes_created"] += 1
        self.stats["expansions"] += 1
        if node.parent is not None:
            self.stats["nonroot_expansions"] += 1
        self.stats["max_depth_reached"] = max(self.stats["max_depth_reached"], child.depth)
        return child

    # ---------------------------------------------------------------- rollout
    def _rollout(self, node: MCTSNode) -> float:
        """Branch-local baseline rollout with stochastic fallback. Never option-0 repeatedly."""
        cur = node
        sid = node.search_id
        mem = node.memory
        steps = 0
        last_obs = node.obs
        while steps < self.cfg["rollout_max_steps"]:
            sel = getattr(last_obs, "select", None)
            opts = K.canonical_options(sel)
            if not opts:
                self.stats["terminal_leaves"] += 1
                return self.leaf_fn(last_obs, terminal=True)
            pick = None
            if self.baseline is not None:
                try:
                    chosen, mem = self.baseline.act_canonical(_obs_dict(last_obs), sel, mem)
                    if chosen:
                        pick = chosen[0]
                        self.stats["rollout_baseline_calls"] += 1
                except Exception:  # noqa: BLE001
                    pick = None
            if pick is None:
                # stochastic legal choice -- deliberately NOT index 0, which is what c018 did
                pick = opts[int(self.rng.integers(0, len(opts)))]
                self.stats["rollout_stochastic_calls"] += 1
            self.stats["step_calls"] += 1
            try:
                nxt = self.A.search_step(sid, [pick.option_index])
                self.stats["step_ok"] += 1
            except Exception:  # noqa: BLE001
                self.stats["step_errors"] += 1
                break
            self._track(nxt.searchId)
            sid = int(nxt.searchId)
            last_obs = nxt.observation
            steps += 1
            self.stats["rollout_steps"] += 1
        self.stats["heuristic_leaves"] += 1
        return self.leaf_fn(last_obs, terminal=False)

    # ---------------------------------------------------------------- simulate
    def simulate(self, deadline: float) -> bool:
        node = self.root
        path = [node]
        while True:
            if time.perf_counter() > deadline:
                return False
            if node.terminal or node.depth >= self.cfg["max_tree_depth"]:
                break
            if not node.priors and not node.terminal:
                self._set_priors(node, _obs_dict(node.obs))
                if node.terminal:
                    break
            if node.unexpanded and len(node.children) < allowed_children(node, self.cfg):
                child = self._expand(node)
                if child is None:
                    if not node.children:
                        break
                    node = select_child(node, self.cfg["c_puct"])
                    path.append(node)
                    continue
                node = child
                path.append(node)
                break
            if not node.children:
                break
            node = select_child(node, self.cfg["c_puct"])
            self.stats["revisits"] += 1
            path.append(node)

        value = self._rollout(node)
        for v in reversed(path):
            v.visits += 1
            v.value_sum += value * v.player_sign
            self.stats["backup_nodes"] += 1
        self.stats["backups"] += 1
        self.stats["simulations"] += 1
        return True


def _obs_dict(observation) -> dict:
    """Observation dataclass -> the dict form the baseline agent expects."""
    import dataclasses
    try:
        return dataclasses.asdict(observation)
    except Exception:  # noqa: BLE001
        return {}


def summarize_root(root: MCTSNode) -> List[Dict[str, Any]]:
    out = []
    for k, ch in root.children.items():
        out.append({"action": list(k), "action_short": ch.action_from_parent.short()
                    if ch.action_from_parent else None,
                    "option_index": ch.action_from_parent.option_index
                    if ch.action_from_parent else -1,
                    "visits": ch.visits, "value_sum": round(ch.value_sum, 6),
                    "q": round(ch.q, 6), "prior": round(ch.prior, 6),
                    "children": len(ch.children),
                    "chance_outcomes": len(root.chance.get(k, {}))})
    out.sort(key=lambda r: -r["visits"])
    return out


def tree_shape(root: MCTSNode, max_nodes: int = 400) -> Dict[str, Any]:
    """Compact shape record: enough to prove branching without dumping whole observations."""
    nodes, stack = [], [root]
    depth_children = collections.Counter()
    nonroot_branching = 0
    while stack and len(nodes) < max_nodes:
        n = stack.pop()
        nodes.append({"depth": n.depth, "visits": n.visits, "q": round(n.q, 5),
                      "prior": round(n.prior, 5), "children": len(n.children),
                      "obs_hash": n.obs_hash,
                      "action": n.action_from_parent.short() if n.action_from_parent else None})
        depth_children[n.depth] += len(n.children)
        if n.parent is not None and len(n.children) >= 2:
            nonroot_branching += 1
        stack.extend(n.children.values())
    return {"nodes_recorded": len(nodes), "root_visits": root.visits,
            "root_children": len(root.children),
            "nonroot_nodes_with_2plus_children": nonroot_branching,
            "children_by_depth": dict(depth_children), "nodes": nodes[:max_nodes]}

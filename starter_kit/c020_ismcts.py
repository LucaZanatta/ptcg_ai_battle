"""c020 A3/A4/A5 — information-set MCTS over a SHARED statistics table.

The structural difference from c019 in one sentence: c019 built one `SearchTree` per
determinization and combined them at the root; here every determinization walks its own native
world but reads and writes ONE `InfoSetTable`, so evidence gathered in world 3 informs selection
in world 7 at the same information set.

What stays determinization-private is exactly what must: the native `searchId`, the concrete
observation, the sampled hidden zones, the branch-local baseline memory, and (for the hybrid) the
branch-local recurrent state. What is shared is exactly what must be: the action statistics at
each information set.

The simulation loop follows `IMPLEMENTATION_GUIDE §3`. Expansion happens at ANY depth through
`search_step`, never root-only, and rollouts follow the branch-local baseline rather than option
index 0.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_baseline_memory as BM  # noqa: E402
from cg import c020_infoset as IS  # noqa: E402
from cg import c020_tactical_leaf as TL  # noqa: E402

DEFAULT_CFG = {
    "c_puct": 1.5,
    "determinizations": 4,
    "simulations_total": 128,        # across ALL determinizations, per CONTRACT §5
    "max_depth": 16,
    "credible_alternatives": 3,      # baseline + up to 3
    "max_ms_per_decision": 700,
    "rollout_max_steps": 12,
    "rollout_stochastic_p": 0.10,    # preregistered low-probability alternative (A5)
    "progressive_k": 1.0,
    "progressive_alpha": 0.5,
    "baseline_prior_bonus": 3.0,
    "min_prior": 0.05,
    "availability_aware": True,
    # M09 ablation switches, ON in every submitted configuration
    "override_enabled": True,
    "veto_enabled": True,
}


def new_stats() -> Dict[str, Any]:
    return {k: 0 for k in (
        "decisions", "searched_decisions", "simulations", "step_calls", "step_ok",
        "step_errors", "begin_calls", "begin_errors", "release_calls", "release_errors",
        "expansions", "nonroot_expansions", "rollout_steps", "rollout_baseline_calls",
        "rollout_stochastic_calls", "backups", "backup_nodes", "leaf_evals", "terminal_leaves",
        "determinizations_attempted", "determinizations_legal", "determinizations_rejected",
        "chance_outcomes", "depth_sum", "max_depth_seen", "overrides", "override_opportunities",
        "vetoes", "infoset_shared_updates", "timeouts",
        # counted DIRECTLY, never derived by dividing a total: a run where every
        # decision got 2 worlds must not report the same number as one where half
        # got 4 (CONTRACT §9 counts DECISIONS, not determinizations)
        "decisions_with_4_determinizations", "decisions_with_2plus_determinizations")}


@dataclass
class WorldNode:
    """A determinization-PRIVATE node. Statistics live in the shared table, not here."""

    search_id: int
    obs: Any
    det_id: int
    depth: int
    player: int
    memory: BM.BaselineMemory
    neural: Any = None                       # hybrid branch-local recurrent state (C1)
    info_key: Optional[IS.InfoSetKey] = None
    children: Dict[Any, "WorldNode"] = field(default_factory=dict)
    terminal: bool = False
    line: TL.LineContext = field(default_factory=TL.LineContext)


def make_infoset_key(obs, player: int, memory: BM.BaselineMemory) -> IS.InfoSetKey:
    """A1: built from visible information only.

    There is deliberately no parameter here through which a sampled hidden value could arrive.
    `observation_hash` hashes the visible view; the select signature and legal signature come
    from the option list the engine offers, which is public to the acting player.
    """
    sel = getattr(obs, "select", None)
    opts = K.canonical_options(sel)
    legal_sig = tuple(sorted(o.key() for o in opts))
    sel_sig = (int(getattr(sel, "selectType", -1) or -1),
               int(getattr(sel, "context", -1) or -1),
               int(getattr(sel, "minCount", 0) or 0),
               int(getattr(sel, "maxCount", 0) or 0)) if sel is not None else ()
    # public part of the baseline memory: how far the scripted plan has advanced, not its content
    mem_sig = (int(memory.depth), bool(memory.values.get("ability_used")),
               int(memory.values.get("pre_turn") or 0))
    return IS.InfoSetKey(visible_hash=K.observation_hash(obs), player=int(player),
                         select_signature=sel_sig, legal_signature=legal_sig,
                         public_memory_signature=mem_sig)


def select_bounds(sel) -> Tuple[int, int]:
    lo = int(getattr(sel, "minCount", 0) or 0)
    hi = int(getattr(sel, "maxCount", 0) or 0)
    lo = max(1, lo)
    hi = max(lo, hi if hi > 0 else lo)
    return lo, hi


def build_payload(sel, primary, opts, priors=None) -> List[int]:
    """Environment payload honouring minCount..maxCount (A3).

    Stepping a multi-select context with a single option raises
    `minCount <= len(select) <= maxCount` and the branch is lost, so the search silently cannot
    explore ANY multi-select position. The primary option leads; the remainder are filled by
    prior order so the payload is deterministic given the priors, not arbitrary.
    """
    lo, _hi = select_bounds(sel)
    chosen = [primary]
    if lo > 1:
        rest = [o for o in opts if o.key() != primary.key()]
        if priors:
            rest.sort(key=lambda o: -float(priors.get(o.key(), 0.0)))
        chosen.extend(rest[:max(0, lo - 1)])
    try:
        return K.to_select_payload(chosen, sel)
    except Exception:  # noqa: BLE001
        return [o.option_index for o in chosen]


class InfoSetSearch:
    """One decision's search: N determinizations sharing one information-set table."""

    def __init__(self, api, cfg, stats, rng, leaf_fn=None, prior_fn=None, value_fn=None,
                 neural_adapter=None):
        self.A = api
        self.cfg = {**DEFAULT_CFG, **(cfg or {})}
        self.stats = stats
        self.rng = rng
        self.table = IS.InfoSetTable()
        self.leaf_fn = leaf_fn or (lambda obs, terminal=False, line=None:
                                   TL.evaluate(obs, terminal, None, line)[0])
        self.prior_fn = prior_fn          # hybrid H1/H3/H4
        self.value_fn = value_fn          # hybrid H2/H3/H4
        self.neural = neural_adapter      # hybrid C1
        self.open_ids: List[int] = []
        self.traces: List[Dict[str, Any]] = []
        self.leaf_samples: List[Dict[str, Any]] = []
        # step failures are classified rather than counted: a legal-move rejection deep in a
        # rollout is expected, a native lifecycle error is not, and one number cannot say which
        self.step_error_kinds: Dict[str, int] = {}
        self.step_error_samples: List[str] = []

    # ---------------------------------------------------------------- lifecycle
    def _track(self, sid):
        self.open_ids.append(int(sid))

    def release_all(self):
        for sid in reversed(self.open_ids):
            self.stats["release_calls"] += 1
            try:
                self.A.search_release(sid)
            except Exception:  # noqa: BLE001
                self.stats["release_errors"] += 1
        self.open_ids.clear()

    def _note_step_error(self, e, depth, where):
        k = f"{type(e).__name__}|{where}"
        self.step_error_kinds[k] = self.step_error_kinds.get(k, 0) + 1
        if len(self.step_error_samples) < 12:
            self.step_error_samples.append(f"[d{depth}|{where}] {type(e).__name__}: "
                                           f"{str(e)[:180]}")

    # ---------------------------------------------------------------- priors
    def _priors(self, node: WorldNode, opts, obs_dict) -> Tuple[Dict[Any, float], set]:
        """Baseline-favoured priors, with an optional external (ByteRL) provider for H1/H3/H4."""
        base_keys = set()
        try:
            action, _prop = BM.recommend(obs_dict, node.memory)
            for o in opts:
                if [o.option_index] == list(action) or o.option_index in list(action):
                    base_keys.add(o.key())
        except Exception:  # noqa: BLE001
            pass
        ext = None
        if self.prior_fn is not None:
            try:
                ext = self.prior_fn(node, opts)
            except Exception:  # noqa: BLE001
                ext = None
        w = {}
        for o in opts:
            base = float(ext.get(o.key(), 1.0)) if ext else 1.0
            if o.key() in base_keys:
                base *= self.cfg["baseline_prior_bonus"]
            w[o.key()] = max(base, 1e-6)
        tot = sum(w.values()) or 1.0
        floor = self.cfg["min_prior"] / max(1, len(opts))
        pri = {k: max(v / tot, floor) for k, v in w.items()}
        s = sum(pri.values()) or 1.0
        return {k: v / s for k, v in pri.items()}, base_keys

    def _credible(self, opts, priors, base_keys, visits: int) -> List[Any]:
        """A3: baseline action + up to 3 credible alternatives, widened by visit count."""
        keys = [o.key() for o in opts]
        ranked = sorted(keys, key=lambda k: (k not in base_keys, -priors.get(k, 0.0)))
        cap = 1 + self.cfg["credible_alternatives"]
        grow = int(self.cfg["progressive_k"] * (max(visits, 1) ** self.cfg["progressive_alpha"]))
        return ranked[:max(1, min(len(ranked), max(cap, grow)))]

    # ---------------------------------------------------------------- expansion
    def _expand(self, node: WorldNode, action_key, opts, priors=None) -> Optional[WorldNode]:
        """A3: create a REAL successor through search_step, at ANY depth."""
        opt = next((o for o in opts if o.key() == action_key), None)
        if opt is None:
            return None
        sel = getattr(node.obs, "select", None)
        payload = build_payload(sel, opt, opts, priors) if sel is not None \
            else [opt.option_index]
        self.stats["step_calls"] += 1
        try:
            succ = self.A.search_step(node.search_id, payload)
            self.stats["step_ok"] += 1
        except Exception as e:  # noqa: BLE001
            self.stats["step_errors"] += 1
            self._note_step_error(e, node.depth, "expand")
            return None
        self._track(succ.searchId)
        self.stats["expansions"] += 1
        if node.depth > 0:
            self.stats["nonroot_expansions"] += 1
        obs = getattr(succ, "observation", None) or getattr(succ, "obs", None)
        try:
            nxt_mem = BM.advance_after_executed(_obs_dict(node.obs), payload,
                                                node.memory)
        except Exception:  # noqa: BLE001
            nxt_mem = BM.clone_memory(node.memory)
        line = TL.LineContext(**{**vars(node.line)})
        from cg import c020_override as _OV
        _annotate_line(line, opt,
                       productive_available=any(_OV.is_productive(o.key(), o) for o in opts))
        child = WorldNode(search_id=int(succ.searchId), obs=obs, det_id=node.det_id,
                          depth=node.depth + 1,
                          player=int(getattr(obs, "yourIndex", node.player) or node.player)
                          if obs is not None else node.player,
                          memory=nxt_mem, neural=node.neural, line=line)
        if self.neural is not None:
            try:
                child.neural = self.neural.advance(node.neural, node.obs, payload)
            except Exception:  # noqa: BLE001
                child.neural = node.neural
        node.children[action_key] = child
        return child

    # ---------------------------------------------------------------- rollout
    def _rollout(self, node: WorldNode, deadline: float) -> float:
        """A5: baseline-guided continuation. Option index 0 is never the default policy."""
        cur = node
        for _ in range(self.cfg["rollout_max_steps"]):
            if time.monotonic() >= deadline or cur.obs is None:
                break
            sel = getattr(cur.obs, "select", None)
            if sel is None:
                break
            opts = K.canonical_options(sel)
            if not opts:
                break
            pick = None
            if self.rng.random() < self.cfg["rollout_stochastic_p"]:
                # preregistered low-probability alternative (A5)
                pick = opts[int(self.rng.integers(len(opts)))]
                self.stats["rollout_stochastic_calls"] += 1
            else:
                try:
                    action, _p = BM.recommend(_obs_dict(cur.obs), cur.memory)
                    self.stats["rollout_baseline_calls"] += 1
                    pick = next((o for o in opts if o.option_index in list(action)), None)
                except Exception:  # noqa: BLE001
                    pick = None
                if pick is None:
                    pick = opts[int(self.rng.integers(len(opts)))]
                    self.stats["rollout_stochastic_calls"] += 1
            payload = build_payload(sel, pick, opts)
            self.stats["step_calls"] += 1
            try:
                succ = self.A.search_step(cur.search_id, payload)
                self.stats["step_ok"] += 1
            except Exception as e:  # noqa: BLE001
                self.stats["step_errors"] += 1
                self._note_step_error(e, cur.depth, "rollout")
                break
            self._track(succ.searchId)
            self.stats["rollout_steps"] += 1
            obs = getattr(succ, "observation", None) or getattr(succ, "obs", None)
            line = TL.LineContext(**{**vars(cur.line)})
            from cg import c020_override as _OV2
            _annotate_line(line, pick,
                           productive_available=any(_OV2.is_productive(o.key(), o)
                                                    for o in opts))
            try:
                mem = BM.advance_after_executed(_obs_dict(cur.obs), payload,
                                                cur.memory)
            except Exception:  # noqa: BLE001
                mem = cur.memory
            cur = WorldNode(search_id=int(succ.searchId), obs=obs, det_id=cur.det_id,
                            depth=cur.depth + 1, player=cur.player, memory=mem,
                            neural=cur.neural, line=line)
            # A5 stop conditions: attack executed or turn ended
            if line.attacked or line.ended_turn:
                break
        return self._evaluate(cur)

    def _evaluate(self, node: WorldNode) -> float:
        self.stats["leaf_evals"] += 1
        if node.obs is None:
            return 0.0
        # hybrid H2/H3/H4 leaf value, with the tactical heuristic as the fallback
        if self.value_fn is not None:
            try:
                v = self.value_fn(node.obs, node.terminal, node.neural)
                if v is not None:
                    return float(v)
            except Exception:  # noqa: BLE001
                pass
        score, feats = TL.evaluate(node.obs, node.terminal, None, node.line)
        if len(self.leaf_samples) < 400:
            self.leaf_samples.append({"det_id": node.det_id, "depth": node.depth,
                                      **feats.to_json()})
        return score

    # ---------------------------------------------------------------- one simulation
    def simulate(self, root: WorldNode, deadline: float) -> float:
        """`IMPLEMENTATION_GUIDE §3`, with shared statistics and root-perspective backup."""
        path: List[Tuple[IS.SharedInfoSetStats, Any, int]] = []
        node = root
        root_player = root.player
        depth_seen = 0

        while True:
            if node.obs is None or node.terminal or node.depth >= self.cfg["max_depth"] \
                    or time.monotonic() >= deadline:
                value = self._evaluate(node)
                break
            sel = getattr(node.obs, "select", None)
            if sel is None:
                node.terminal = True
                self.stats["terminal_leaves"] += 1
                value = self._evaluate(node)
                break
            opts = K.canonical_options(sel)
            if not opts:
                node.terminal = True
                value = self._evaluate(node)
                break

            key = node.info_key or make_infoset_key(node.obs, node.player, node.memory)
            node.info_key = key
            shared = self.table.get(key)
            self.table.note_visit(key, node.det_id)

            obs_dict = _obs_dict(node.obs)
            priors, base_keys = self._priors(node, opts, obs_dict)
            for k, p in priors.items():
                shared.ensure(k, p)
            legal_keys = [o.key() for o in opts]
            shared.update_availability(legal_keys, node.det_id)

            candidate_keys = self._credible(opts, priors, base_keys, shared.n)
            action_key = IS.select_puct(shared, candidate_keys, self.cfg["c_puct"],
                                        self.cfg["availability_aware"])
            if action_key is None:
                value = self._evaluate(node)
                break

            path.append((shared, action_key, node.player))
            shared.ensure(action_key).det_ids.add(node.det_id)
            self.stats["infoset_shared_updates"] += 1
            depth_seen = max(depth_seen, node.depth)

            child = node.children.get(action_key)
            if child is None:
                child = self._expand(node, action_key, opts, priors)
                if child is None:
                    value = self._evaluate(node)
                    break
                value = self._rollout(child, deadline)
                break
            node = child

        n = IS.backup(path, value, root_player)
        self.stats["backups"] += 1
        self.stats["backup_nodes"] += n
        self.stats["simulations"] += 1
        self.stats["depth_sum"] += depth_seen
        self.stats["max_depth_seen"] = max(self.stats["max_depth_seen"], depth_seen)
        if len(self.traces) < 200:
            self.traces.append({"det_id": root.det_id, "path_len": len(path),
                                "max_depth": depth_seen, "value": round(value, 5),
                                "backup_nodes": n})
        return value


def _annotate_line(line: TL.LineContext, opt, productive_available: bool = False) -> None:
    """Record what the simulated line DID, which the leaf position cannot show.

    Read from the engine's OptionType rather than by matching words against a tuple of integers,
    which is what the first version did and why `attacked` and `ended_turn` were never set.
    """
    from cg import c020_override as OV
    t = OV.option_type_of(opt.key(), opt)
    if t == OV.OPT_END:
        line.ended_turn = True
    elif t == OV.OPT_ATTACK:
        line.attacked = True
        line.damage_dealt = max(line.damage_dealt, 1)
    if t in (7, 9, 10):          # PLAY, EVOLVE, ABILITY consume real resources
        line.critical_resources_used += 1
    if productive_available:
        line.productive_action_was_available = True


def _obs_dict(observation) -> dict:
    """Observation dataclass -> the dict form the baseline agent expects."""
    from cg import c019_mcts as M19
    return M19._obs_dict(observation)

"""c021 A3/A4/A5/A7 — the MCGS search loop, ported from `src/MCGS.cs`.

Control flow reproduced from the official archive:

    Search(root):
        TreePolicy(root, UCTConstant)      # descend, expanding when not fully expanded
        reward = SingleThreadRollout(leaf) # uniform-random rollout to terminal
        Backup(leaf, reward)

    TreePolicy:
        loop:
            if root.IsTerminal: return
            if not root.IsFullyExpanded(chanceTraversed):
                if root.Expand(out root): continue
                return
            if not root.BestChild(out root, c, ref chanceTraversed): return

The rollout is UNIFORM RANDOM (`src/DefaultPolicy/UniformRandomRollout.cs`), returns 1.0 for a win
and 0.0 otherwise, aborts to -1 past 1000 steps, returns 0.0 at turn 45, and the caller retries up
to 5 times while the value is negative. `FIDELITY_RULES §3` forbids substituting a handcrafted or
neural leaf evaluator here, which is precisely what c020 did.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c021_mcgs_abstraction as AB  # noqa: E402
from cg import c021_mcgs_graph as G  # noqa: E402


def new_stats() -> Dict[str, Any]:
    return {k: 0 for k in (
        "searches", "tree_policy_steps", "expansions", "nonroot_expansions",
        "transposition_hits", "transposition_merges", "dummy_edges", "sample_merges",
        "chance_nodes_created", "chance_samples", "chance_sparse_cutoffs",
        "rollouts", "rollout_steps", "rollout_retries", "rollout_aborts", "rollout_turn_caps",
        "terminal_leaves", "backups", "backup_nodes", "lethal_bonus", "finalised",
        "recursive_update_noops", "recursive_reward_updates", "recursive_visit_updates",
        "step_calls", "step_ok", "step_errors", "begin_calls", "begin_errors",
        "release_calls", "release_errors", "max_depth", "decisions", "searched_decisions",
        "graph_reuse_reroots", "time_budget_exhausted")}


class MCGS:
    """One decision's graph search. The graph is REUSED across atomic decisions (A5)."""

    def __init__(self, api, cfg: Dict[str, Any], stats: Dict[str, Any], rng,
                 prior_provider=None):
        self.A = api
        self.cfg = cfg
        self.stats = stats
        self.rng = rng
        self.tt = G.TranspositionTable()
        self.ucd = G.UCDParams(cfg.get("ucd_d1", 1), cfg.get("ucd_d2", 0))
        self.open_ids: List[int] = []
        self.root: Optional[G.Node] = None
        self.prior_provider = prior_provider     # transfer lab only; None in the reference
        self.traces: List[Dict[str, Any]] = []

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

    # ---------------------------------------------------------------- node construction
    def _make_node(self, search_state, depth: int, action: Optional[AB.ActionAbstraction],
                   root_player: int, start_turn: int) -> Optional[G.Node]:
        obs = getattr(search_state, "observation", None)
        if obs is None:
            return None
        sel = getattr(obs, "select", None)
        terminal = sel is None
        play = None
        if terminal:
            play = self._terminal_playstate(obs, root_player)
        try:
            own = int(getattr(obs, "yourIndex", root_player) or root_player)
        except Exception:  # noqa: BLE001
            own = root_player
        n = G.Node(state_abstraction=AB.StateAbstraction(obs, action, None,
                                                         G.SIMPLE_ABSTRACTION),
                   search_id=int(getattr(search_state, "searchId", -1)),
                   obs=obs, depth=depth,
                   is_opponent=(own != root_player),
                   is_random=False,
                   is_end_turn=bool(action.is_end_turn_action) if action else False,
                   is_terminal=terminal, play_state=play, start_turn=start_turn)
        n.action_abstraction = action
        if not terminal:
            n.legal_options = K.canonical_options(sel)
            n.untested_action_indices = list(range(len(n.legal_options)))
        self.stats["max_depth"] = max(self.stats["max_depth"], depth)
        return n

    @staticmethod
    def _terminal_playstate(obs, root_player: int) -> Optional[str]:
        try:
            v = K.visible_view(obs, None)
            c = v.counts()
            if c["my_prize"] == 0:
                return "WON"
            if c["opp_prize"] == 0:
                return "LOST"
        except Exception:  # noqa: BLE001
            pass
        return None

    # ---------------------------------------------------------------- expansion (A3)
    def expand(self, node: G.Node, root_player: int, start_turn: int
               ) -> Tuple[Optional[G.Node], bool]:
        """`Node.Expand` + `MCGS.TranspositionCheck`.

        Returns (next_node, continue_descending). The second value reproduces the source's
        `Expand(out root)` boolean: a transposition merge continues the descent from the matched
        node rather than rolling out immediately.
        """
        if not node.untested_action_indices:
            return None, False
        # `Node.TreePolicy()`: uniform random over untested actions, then remove.
        j = int(self.rng.integers(len(node.untested_action_indices)))
        idx = node.untested_action_indices.pop(j)
        if idx >= len(node.legal_options):
            return None, False
        opt = node.legal_options[idx]
        sel = getattr(node.obs, "select", None)
        aa = AB.action_abstraction_of(opt, sel)
        payload = self._payload(sel, opt, node.legal_options)

        self.stats["step_calls"] += 1
        try:
            succ = self.A.search_step(node.search_id, payload)
            self.stats["step_ok"] += 1
        except Exception:  # noqa: BLE001
            self.stats["step_errors"] += 1
            return None, False
        self._track(succ.searchId)

        child = self._make_node(succ, node.depth + 1, aa, root_player, start_turn)
        if child is None:
            return None, False
        edge = G.Edge.connect(node, child, idx, traverse=True, action_abstraction=aa)
        self.stats["expansions"] += 1
        if node.depth > 0:
            self.stats["nonroot_expansions"] += 1

        # `Node.Expand` returns TRUE only when the tree phase must loop again -- which happens
        # when TranspositionCheck merged into an existing node. A freshly created node returns
        # FALSE and is rolled out from. Returning True unconditionally made the descent expand
        # until the time budget was gone, so every rollout returned 0.0 at the deadline check.
        merged, cont = self._transposition_check(child, node)
        return merged, cont

    def _payload(self, sel, opt, opts) -> List[int]:
        """minCount..maxCount honoured. c020 R1: a single index into a multi-select is illegal."""
        lo = max(1, int(getattr(sel, "minCount", 1) or 1))
        chosen = [opt]
        if lo > 1:
            chosen.extend([o for o in opts if o.key() != opt.key()][:lo - 1])
        try:
            return K.to_select_payload(chosen, sel)
        except Exception:  # noqa: BLE001
            return [o.option_index for o in chosen]

    def _transposition_check(self, node: G.Node, parent: G.Node) -> Tuple[G.Node, bool]:
        """`MCGS.TranspositionCheck`: merge into the single rooted DAG.

        Returns (node, continue_descending). FALSE for a newly inserted node -- the caller rolls
        out from it. TRUE when a match was merged, so the tree phase loops again.
        """
        if not G.TRANSPOSITION:
            return node, False
        match = self.tt.try_get(node.state_abstraction)
        if match is None:
            self.tt.add(node.state_abstraction, node)
            return node, False

        self.stats["transposition_hits"] += 1
        match.is_transposition = True

        common = next((e for e in match.incoming_edges if e.predecessor is parent), None)
        if common is not None:
            # Already connected: mark the fresh edge dummy so UCB never selects it, and
            # return to the parent -- the source's `node = parent; return true`.
            if not parent.is_random:
                node.last_traversed_edge.is_dummy = True
                node.last_traversed_edge.change_successor(match)
                self.tt.dummy_edges += 1
                self.stats["dummy_edges"] += 1
                return parent, True
            common.sample_count += 1
            self.tt.sample_merges += 1
            self.stats["sample_merges"] += 1
            node.last_traversed_edge.disconnect()
            match.last_traversed_edge = common
            return match, True

        edge = node.last_traversed_edge
        edge.change_successor(match)
        match.last_traversed_edge = edge
        self.tt.merges += 1
        self.stats["transposition_merges"] += 1
        return match, True

    # ---------------------------------------------------------------- tree policy
    def tree_policy(self, root: G.Node, c: float, root_player: int, start_turn: int,
                    deadline: float) -> G.Node:
        node = root
        chance_traversed = 0
        while True:
            if node.is_terminal:
                self.stats["terminal_leaves"] += 1
                return node
            if time.monotonic() >= deadline:
                self.stats["time_budget_exhausted"] += 1
                return node
            if not node.is_fully_expanded(chance_traversed):
                nxt, cont = self.expand(node, root_player, start_turn)
                if nxt is None:
                    return node
                node = nxt
                self.stats["tree_policy_steps"] += 1
                if cont:
                    continue
                return node
            nxt, inc = node.best_child(c, self.rng, self.stats)
            if nxt is None:
                return node
            chance_traversed += inc
            if inc:
                self.stats["chance_sparse_cutoffs"] += (
                    1 if chance_traversed >= G.CHANCE_SPARSE_THRESHOLD else 0)
            node = nxt
            self.stats["tree_policy_steps"] += 1

    # ---------------------------------------------------------------- rollout (A7)
    def rollout(self, leaf: G.Node, deadline: float) -> float:
        """`SingleThreadRollout` + `PlayUntilTerminal`, uniform random, retry while value < 0."""
        for attempt in range(G.ROLLOUT_RETRIES):
            v = self._play_until_terminal(leaf, deadline)
            if v >= 0:
                self.stats["rollouts"] += 1
                return v
            self.stats["rollout_retries"] += 1
        self.stats["rollout_aborts"] += 1
        return 0.0

    def _play_until_terminal(self, leaf: G.Node, deadline: float) -> float:
        """`PlayUntilTerminal`. NO time check inside the rollout.

        The source bounds a rollout by a 1000-step cap and a turn cap, never by the move clock:
        the time budget governs how many SEARCHES run, not whether a started rollout finishes.
        Checking the deadline here aborted every rollout at 0.0, so 4,140 simulations returned an
        identical reward and UCB selection was pure noise.
        """
        sid = leaf.search_id
        obs = leaf.obs
        count = 0
        while True:
            if count > G.ROLLOUT_STEP_CAP:
                self.stats["rollout_aborts"] += 1
                return -1.0
            sel = getattr(obs, "select", None)
            if sel is None:
                self.stats["rollout_terminals"] = self.stats.get("rollout_terminals", 0) + 1
                return self._terminal_reward(obs)
            opts = K.canonical_options(sel)
            if not opts:
                # SEMANTIC_ADAPTER. The engine signals a finished game by offering a select with
                # an EMPTY option list rather than a null select, and under uniform-random play
                # the game almost always ends by DECK-OUT rather than by prizes -- the PTCG
                # counterpart of the fatigue death the source's turn-45 cap anticipates.
                # Reading the engine's own terminal state here is not a leaf evaluator: no
                # position is scored, only a finished game's winner is decided by the rules.
                self.stats["rollout_terminals"] = self.stats.get("rollout_terminals", 0) + 1
                return self._terminal_reward(obs)
            pick = opts[int(self.rng.integers(len(opts)))]      # UNIFORM RANDOM (source policy)
            payload = self._payload(sel, pick, opts)
            self.stats["step_calls"] += 1
            try:
                succ = self.A.search_step(sid, payload)
                self.stats["step_ok"] += 1
            except Exception:  # noqa: BLE001
                self.stats["step_errors"] += 1
                return -1.0
            self._track(succ.searchId)
            sid = succ.searchId
            obs = getattr(succ, "observation", None)
            if obs is None:
                return 0.0
            self.stats["rollout_steps"] += 1
            count += 1

    def _terminal_reward(self, obs) -> float:
        """`PlayUntilTerminal`'s `isWinner ? 1.0 : 0.0`, decided by PTCG's own win conditions.

        Order matters and follows the rules: prizes first, then deck-out. Only a genuinely
        undecidable state returns the source's draw value.
        """
        try:
            c = K.visible_view(obs, None).counts()
        except Exception:  # noqa: BLE001
            return -1.0
        if c["my_prize"] == 0:
            self.stats["term_prize_win"] = self.stats.get("term_prize_win", 0) + 1
            return 1.0
        if c["opp_prize"] == 0:
            self.stats["term_prize_loss"] = self.stats.get("term_prize_loss", 0) + 1
            return 0.0
        my_out, opp_out = c["my_deck"] == 0, c["opp_deck"] == 0
        if opp_out and not my_out:
            self.stats["term_deckout_win"] = self.stats.get("term_deckout_win", 0) + 1
            return 1.0
        if my_out and not opp_out:
            self.stats["term_deckout_loss"] = self.stats.get("term_deckout_loss", 0) + 1
            return 0.0
        self.stats["term_undecided"] = self.stats.get("term_undecided", 0) + 1
        return 0.0

    # ---------------------------------------------------------------- one search
    def search(self, root: G.Node, root_player: int, start_turn: int, deadline: float):
        leaf = self.tree_policy(root, self.cfg.get("uct_constant", G.UCT_CONSTANT),
                                root_player, start_turn, deadline)
        reward = self.rollout(leaf, deadline)
        reward = G.apply_lethal_bonus(leaf, reward, self.stats)
        if self.cfg.get("selection_strategy", "UCD") == "UCD":
            n = G.backup_ucd(leaf, reward, self.ucd, self.stats)
        else:
            n = G.backup_edges(leaf, reward, self.stats)
        self.stats["backups"] += 1
        self.stats["backup_nodes"] += n
        self.stats["searches"] += 1
        if len(self.traces) < 300:
            self.traces.append({"leaf_depth": leaf.depth, "reward": round(reward, 4),
                                "backup_nodes": n, "terminal": leaf.is_terminal})

    # ---------------------------------------------------------------- final selection
    def select_final(self, root: G.Node, mode: str = "MaxChild"
                     ) -> Tuple[Optional[G.Edge], Dict[str, Any]]:
        """`MCGS.Select`. NO override gate: the search's choice is played (FIDELITY_RULES §3)."""
        live = [e for e in root.outgoing_edges if not e.is_dummy]
        if not live:
            return None, {}
        if mode == "RobustChild":
            best = max(live, key=lambda e: e.successor.visit_count)
        else:
            best = max(live, key=lambda e: e.value(0.0))
        info = {"mode": mode, "edges": len(live),
                "visits": [e.visit_count for e in live][:24],
                "values": [round(e.value(0.0), 4) for e in live][:24],
                "chosen_value": round(best.value(0.0), 4),
                "chosen_visits": best.visit_count,
                "chosen_action": best.action_abstraction.short()
                if best.action_abstraction else None}
        return best, info

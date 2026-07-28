"""c021 A2/A3 — MCGS graph: Node, Edge, transposition DAG, modified UCD.

Ported behaviourally from the official 2019 archive (SHA-256
f00a54f310a8f868deb59964c17e71357d67ecfcedba01c0245053dcc5aa920a), files
`src/Node.cs`, `src/Edge.cs`, `src/Algorithms/UCD.cs`, `src/MCGS.cs`. No C# text is copied; the
formulas are transcribed in `results/fidelity/mcgs_paper_equation_map.md` and reproduced here.

Fidelity points that differ from anything c020 built, and that `FIDELITY_RULES §3` forbids
substituting:

  * selection is UCB1 (`Q + c*sqrt(2*ln N / n)`), with NO prior term — not PUCT;
  * statistics live on EDGES (`StoreVisitsAtEdges = true` in the source config);
  * `Edge.Value` in UCD mode divides by `Predecessor.TotalVisit`, which recursive updates inflate,
    rather than by the predecessor's own visit count;
  * terminal nodes are valued +10 / -10 while rollouts return 1.0 / 0.0;
  * `Node.Update` flips the reward sign at opponent nodes;
  * `UCDParams` defaults to (d1=1, d2=0), at which `RecursiveUpdate` is INERT. That is reproduced,
    not fixed (`FIDELITY_RULES §5`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- source constants
UCT_CONSTANT = 0.285          # SearchConfig.UCTConstant
SAMPLE_WIDTH = 24             # NodeConfig.SampleWidth
DAMPING_PARAMETER = 2.0       # NodeConfig.DampingParameter
DAMPED_SAMPLING = True        # NodeConfig.DampedSampling
DETERMINIZATION_NUMBER = 200  # SearchConfig.DeterminizationNumber
FIRST_MOVE_SECONDS = 15.0     # SearchConfig.FirstMoveDurationSeconds
CONTINUING_MOVE_SECONDS = 10.0
STORE_VISITS_AT_EDGES = True  # NodeConfig.StoreVisitsAtEdges
SIMPLE_ABSTRACTION = True     # NodeConfig.SimpleAbstraction
TRANSPOSITION = True          # NodeConfig.Transposition
PIMC = False                  # NodeConfig.PIMC
DO_NOT_REMOVE_UNSELECTED = True
CHANCE_SPARSE_THRESHOLD = 5   # Node.BestChild: OutgoingEdges.Count > 5

# A4. The chance-node surface, taken from the ENGINE'S OWN ENUM rather than inferred.
#
#     api.SelectContext.COIN_HEAD = 46   # "YesNo. Do you want to choose heads?"
#
# Under `search_begin(manual_coin=True)` the engine stops resolving a coin flip silently inside
# the step and presents it as this select. It is the only genuine chance surface the API exposes.
#
# This set previously also held contexts 4 and 5. Both were wrong. They are
# `SelectContext.TO_ACTIVE` and `SelectContext.TO_BENCH` -- ordinary player decisions about where
# to put a Pokemon. Marking them random made the search SAMPLE its own placement decisions
# instead of optimising them.
#
# They were included on two bad arguments, both worth recording because the reasoning failed in a
# way that looked like evidence:
#   1. a set-difference between a manual_coin walk and a normal walk. That is confounded: once a
#      coin resolves differently the trajectories diverge, so contexts that exist in both runs
#      show up as "only with manual_coin".
#   2. a "direct check" that stepped every option from one state and found several distinct
#      successors. That property holds for EVERY decision node -- it demonstrates branching, not
#      randomness, and could never have distinguished a chance node from a normal choice.
# The engine's enum settles it in one line, and is the authority used here.
#
# A manual-coin node that reaches the UCB path lets the search pick the favourable flip and become
# clairvoyant; `manual_coin_node_ucb_selected` proves that never happens and must stay 0.
COIN_HEAD_CONTEXT = 46
MANUAL_COIN_CONTEXTS = frozenset({COIN_HEAD_CONTEXT})
ROLLOUT_STEP_CAP = 1000
ROLLOUT_TURN_CAP = 45
ROLLOUT_RETRIES = 5
LETHAL_BACKUP_MULTIPLIER = 10.0
TERMINAL_WON = 10.0
TERMINAL_LOST = -10.0
# `Edge.IsDummy` setter parks VisitCount at C# int.MaxValue. That does NOT make the edge
# unselectable: `Edge.Value` still returns `Successor.Value(0)` plus a bonus that this divisor
# drives to ~0. What it guarantees is that a dummy edge never outranks its OWN TWIN -- the
# already-existing edge to the same successor, which keeps a real visit count and so a strictly
# larger bonus. A dummy edge can still outrank an edge to a genuinely worse state, and should:
# it is a real transition into a node the graph already reaches another way.
DUMMY_VISITS = (1 << 31) - 1  # C# int.MaxValue exactly


@dataclass(frozen=True)
class UCDParams:
    """`src/Algorithms/UCD.cs::UCDParams`. Source default is (1, 0)."""

    d1: int = 1
    d2: int = 0

    def __post_init__(self):
        if self.d1 < 1:
            raise ValueError("d1 of UCD parameter must be larger than 1.")

    @property
    def recursion_is_active(self) -> bool:
        """At the source default (1, 0) both guards are false and the recursion does nothing."""
        return (self.d1 > 1) or (self.d2 > 0)


class Edge:
    """`src/Edge.cs`. Carries VisitCount and SampleCount; statistics live here."""

    __slots__ = ("predecessor", "successor", "action_index", "action_abstraction",
                 "visit_count", "sample_count", "_dummy")

    def __init__(self, predecessor: "Node", successor: "Node", action_index: int,
                 action_abstraction: Any = None):
        if action_index < 0:
            raise ValueError("negative action index")
        self.predecessor = predecessor
        self.successor = successor
        self.action_index = action_index
        self.action_abstraction = action_abstraction
        self.visit_count = 0
        self.sample_count = 1          # source default
        self._dummy = False

    # ---- IsDummy: setting it parks VisitCount at the max so UCB never picks it
    @property
    def is_dummy(self) -> bool:
        return self._dummy

    @is_dummy.setter
    def is_dummy(self, value: bool):
        self._dummy = bool(value)
        self.visit_count = DUMMY_VISITS if value else 0

    def value(self, c: float, ucd: bool = True) -> float:
        """`Edge.Value(double c)` exactly.

        x = Successor.Value(0); bonus uses Predecessor.TotalVisit under UCD, else VisitCount.
        """
        x = self.successor.value(0.0)
        if c == 0:
            return x
        n = self.predecessor.total_visit if ucd else self.predecessor.visit_count
        if self.visit_count <= 0 or n <= 0:
            return float("inf")        # unvisited edges dominate, as ln/0 would in the source
        return x + c * math.sqrt(2.0 * math.log(n) / self.visit_count)

    def traverse(self) -> "Node":
        self.successor.last_traversed_edge = self
        return self.successor

    def change_successor(self, successor: "Node", traverse: bool = False):
        self.successor.incoming_edges.remove(self)
        if self.successor.last_traversed_edge is self:
            self.successor.last_traversed_edge = None
        self.successor = successor
        successor.incoming_edges.append(self)
        if traverse:
            successor.last_traversed_edge = self

    def change_predecessor(self, predecessor: "Node"):
        self.predecessor.outgoing_edges.remove(self)
        self.predecessor = predecessor
        predecessor.outgoing_edges.append(self)

    def disconnect(self) -> int:
        self.predecessor.outgoing_edges.remove(self)
        self.successor.incoming_edges.remove(self)
        if self.successor.last_traversed_edge is self:
            self.successor.last_traversed_edge = None
        idx = self.action_index
        self.predecessor = None
        self.successor = None
        self.action_abstraction = None
        return idx

    def recursive_update(self, reward: float, d1: int, d2: int, stats: Dict[str, int]):
        """`Edge.RecursiveUpdate` exactly, including the early return.

        At the source default (d1=1, d2=0) both flags are false and this returns immediately.
        The guard is reproduced rather than removed -- see FIDELITY_RULES §5.
        """
        if self._dummy:
            return
        f1 = d1 > 1
        f2 = d2 > 0
        if not f1 and not f2:
            stats["recursive_update_noops"] = stats.get("recursive_update_noops", 0) + 1
            return
        p = self.predecessor
        if f1:
            p.update(reward)
            stats["recursive_reward_updates"] = stats.get("recursive_reward_updates", 0) + 1
        if f2:
            self.visit_count += 1
            p.total_visit += 1
            stats["recursive_visit_updates"] = stats.get("recursive_visit_updates", 0) + 1
        for e in list(p.incoming_edges):
            e.recursive_update(reward, d1 - 1, d2 - 1, stats)

    @staticmethod
    def connect(predecessor: "Node", successor: "Node", action_index: int,
                traverse: bool = True, action_abstraction: Any = None) -> "Edge":
        e = Edge(predecessor, successor, action_index, action_abstraction)
        predecessor.outgoing_edges.append(e)
        successor.incoming_edges.append(e)
        if predecessor.is_random:
            successor.is_sample = True
        if traverse:
            successor.last_traversed_edge = e
        return e

    def __repr__(self):
        return (f"[N:{self.visit_count}]"
                f"{'x' + str(self.sample_count) if self.sample_count > 1 else ''}")


class Node:
    """`src/Node.cs`. A graph node; may have MANY incoming edges (this is a DAG, not a tree)."""

    __slots__ = ("state_abstraction", "search_id", "obs", "depth", "is_opponent", "is_random",
                 "is_end_turn", "is_terminal", "play_state", "visit_count", "rewards",
                 "total_visit", "incoming_edges", "outgoing_edges", "last_traversed_edge",
                 "untested_action_indices", "legal_options", "is_transposition", "is_sample",
                 "is_finalised", "is_not_in_main_tree", "stashed_edges", "start_turn",
                 "chance_outcomes", "_cached_hash", "action_abstraction", "select_context",
                 "random_action_type", "action_sets")

    def __init__(self, state_abstraction: Any = None, search_id: int = -1, obs: Any = None,
                 depth: int = 0, is_opponent: bool = False, is_random: bool = False,
                 is_end_turn: bool = False, is_terminal: bool = False,
                 play_state: Optional[str] = None, start_turn: int = 0,
                 select_context: int = -1, random_action_type: str = "FALSE"):
        self.select_context = select_context
        self.random_action_type = random_action_type
        self.action_sets = None      # A10 branch only: multi-select combinations as actions
        self.state_abstraction = state_abstraction
        self.search_id = search_id
        self.obs = obs
        self.depth = depth
        self.is_opponent = is_opponent
        self.is_random = is_random
        self.is_end_turn = is_end_turn
        self.is_terminal = is_terminal
        self.play_state = play_state
        self.start_turn = start_turn
        self.visit_count = 0
        self.rewards = 0.0
        self.total_visit = 0
        self.incoming_edges: List[Edge] = []
        self.outgoing_edges: List[Edge] = []
        self.last_traversed_edge: Optional[Edge] = None
        self.untested_action_indices: List[int] = []
        self.legal_options: List[Any] = []
        self.chance_outcomes: List[Any] = []
        self.is_transposition = False
        self.is_sample = False
        self.is_finalised = False
        self.is_not_in_main_tree = False
        self.stashed_edges: List[Edge] = []
        self.action_abstraction = None
        self._cached_hash = None

    # ---------------------------------------------------------------- value / update
    def value(self, c: float) -> float:
        """`Node.Value(double c)` exactly: terminals are +/-10, otherwise mean reward."""
        if self.is_terminal:
            if self.play_state == "WON":
                x = TERMINAL_WON
            elif self.play_state == "LOST":
                x = TERMINAL_LOST
            else:
                x = 0.0
        else:
            x = (self.rewards / self.visit_count) if self.visit_count else 0.0
        if c == 0:
            return x
        parent = self.parent
        pn = parent.visit_count if parent is not None else 0
        if self.visit_count <= 0 or pn <= 0:
            return float("inf")
        return x + c * math.sqrt(2.0 * math.log(pn) / self.visit_count)

    def update(self, reward: float):
        """`Node.Update(double reward)`: sign flip at opponent nodes, then accumulate."""
        if self.is_opponent:
            reward *= -1.0
        if self.is_end_turn and PIMC:
            reward *= -1.0
        self.visit_count += 1
        self.rewards += reward

    def ucd_update(self, reward: float, params: UCDParams, stats: Dict[str, int]):
        """`Node.UCDUpdate`: own update, then recurse into non-traversed incoming edges."""
        self.update(reward)
        self.total_visit += 1
        if len(self.incoming_edges) > 1:
            for e in list(self.incoming_edges):
                if e is self.last_traversed_edge or e.is_dummy:
                    continue
                e.recursive_update(reward, params.d1, params.d2, stats)

    # ---------------------------------------------------------------- structure
    @property
    def parent(self) -> Optional["Node"]:
        return self.last_traversed_edge.predecessor if self.last_traversed_edge else None

    def is_fully_expanded(self, num_sample_traversed: int) -> bool:
        """`Node.IsFullyExpanded(int numSampleTraversed)` exactly.

        Decision node: fully expanded when no untested action remains.
        Chance node with DampedSampling: the threshold is SampleWidth divided by
        DampingParameter raised to the number of chance nodes ALREADY TRAVERSED IN THIS DESCENT
        (not by depth), floored at 1, compared against the SUM of outgoing edge SampleCounts.
        """
        if self.is_terminal:
            return True
        if not self.is_random:
            return not self.untested_action_indices
        total_samples = sum(e.sample_count for e in self.outgoing_edges)
        if DAMPED_SAMPLING:
            if num_sample_traversed == 0:
                return SAMPLE_WIDTH <= total_samples
            reduced = self.reduce_function(SAMPLE_WIDTH, num_sample_traversed)
            if reduced == 0:
                reduced = 1
            return reduced <= total_samples
        return self.visit_count <= total_samples

    @staticmethod
    def reduce_function(sample_width: int, num_sample_traversed: int) -> int:
        """`ReduceFunction`: sampleWidth / DampingParameter^numSampleTraversed, C#-rounded."""
        return int(round(sample_width / (DAMPING_PARAMETER ** num_sample_traversed)))

    def sample_budget(self, num_sample_traversed: int = 0) -> int:
        if not DAMPED_SAMPLING:
            return SAMPLE_WIDTH
        if num_sample_traversed == 0:
            return SAMPLE_WIDTH
        return max(1, self.reduce_function(SAMPLE_WIDTH, num_sample_traversed))

    def best_child(self, c: float, rng, stats: Dict[str, int]
                   ) -> Tuple[Optional["Node"], int]:
        """`Node.BestChild`: sample at chance nodes, argmax edge value at decision nodes."""
        if not self.outgoing_edges:
            return None, 0
        if self.is_random:
            child = self._sample_child(rng)
            stats["chance_samples"] = stats.get("chance_samples", 0) + 1
            inc = 1 if len(self.outgoing_edges) > CHANCE_SPARSE_THRESHOLD else 0
            return child, inc
        # A4 guard. Reaching the UCB branch below with a chance context would let the search
        # CHOOSE its coin flips. Counted rather than silently tolerated; must remain 0.
        if self.select_context in MANUAL_COIN_CONTEXTS:
            stats["manual_coin_node_ucb_selected"] = (
                stats.get("manual_coin_node_ucb_selected", 0) + 1)
        if STORE_VISITS_AT_EDGES:
            best = max(self.outgoing_edges, key=lambda e: e.value(c))
        else:
            best = max(self.outgoing_edges, key=lambda e: e.successor.value(c))
        return best.traverse(), 0

    def _sample_child(self, rng) -> "Node":
        """`Node.SampleChild`: weighted random over outgoing edges by SampleCount."""
        weights = [max(1, e.sample_count) for e in self.outgoing_edges]
        total = sum(weights)
        r = rng.random() * total
        acc = 0.0
        for e, w in zip(self.outgoing_edges, weights):
            acc += w
            if r <= acc:
                return e.traverse()
        return self.outgoing_edges[-1].traverse()

    def finalise(self) -> bool:
        """`Node.Finalise`: collapse a parent onto a proven-winning edge. Inactive under PIMC."""
        if PIMC:
            return False
        self.is_finalised = True
        parent = self.last_traversed_edge.predecessor if self.last_traversed_edge else None
        if parent is None or parent.is_random:
            return False
        parent.outgoing_edges.clear()
        parent.outgoing_edges.append(self.last_traversed_edge)
        parent.untested_action_indices.clear()
        return True

    def __repr__(self):
        tags = "".join(t for t, f in (("F", self.is_finalised), ("O", self.is_opponent),
                                      ("C", self.is_random), ("T", self.is_transposition))
                       if f)
        body = ("[Terminal]" if self.is_terminal else
                f"[V:{round(self.value(0), 2)}][R:{round(self.rewards, 2)}]"
                f"[N:{self.visit_count}]")
        return f"[{tags}][D:{self.depth}]{body}"


class TranspositionTable:
    """`NodeConfig.Transposition = true`. Keyed by state abstraction; builds one rooted DAG."""

    def __init__(self):
        self.table: Dict[Any, Node] = {}
        self.lookups = 0
        self.hits = 0
        self.merges = 0
        self.dummy_edges = 0
        self.sample_merges = 0
        self.collisions_audited = 0

    def try_get(self, key) -> Optional[Node]:
        self.lookups += 1
        n = self.table.get(key)
        if n is not None:
            self.hits += 1
        return n

    def add(self, key, node: Node):
        self.table[key] = node

    def stats(self) -> Dict[str, Any]:
        return {"entries": len(self.table), "lookups": self.lookups, "hits": self.hits,
                "hit_rate": round(self.hits / self.lookups, 4) if self.lookups else None,
                "merges": self.merges, "dummy_edges": self.dummy_edges,
                "sample_merges": self.sample_merges,
                "is_a_dag": self.merges > 0 or self.dummy_edges > 0}


def backup_edges(node: Node, reward: float, stats: Dict[str, int]) -> int:
    """`MCGS.BackupEdges`: walk LastTraversedEdge upward, incrementing edge visits."""
    terminal = (node.is_terminal and not node.is_finalised
                and not getattr(node.action_abstraction, "is_end_turn_action", False)
                and node.play_state == "WON")
    n = 0
    cur = node
    while True:
        cur.update(reward)
        n += 1
        if terminal:
            terminal = cur.finalise()
            if terminal:
                stats["finalised"] = stats.get("finalised", 0) + 1
        e = cur.last_traversed_edge
        if e is None:
            break
        e.visit_count += 1
        cur = e.predecessor
    return n


def backup_ucd(node: Node, reward: float, params: UCDParams, stats: Dict[str, int]) -> int:
    """`MCGS.BackupUCD`: UCD update at each node on the traversed path.

    The terminal / `Finalise` block is the SAME one `BackupEdges` carries -- the source repeats it
    verbatim in both. An earlier version of this function omitted it, and because `UCD` is the
    active selection strategy that meant `Node.Finalise` never ran at all: the lethal-sequence
    collapse, which prunes a parent onto a proven winning edge, was dead code in the configuration
    actually being executed.
    """
    terminal = (node.is_terminal and not node.is_finalised
                and not getattr(node.action_abstraction, "is_end_turn_action", False)
                and node.play_state == "WON")
    n = 0
    cur = node
    while True:
        cur.ucd_update(reward, params, stats)
        n += 1
        if terminal:
            terminal = cur.finalise()
            if terminal:
                stats["finalised"] = stats.get("finalised", 0) + 1
        e = cur.last_traversed_edge
        if e is None:
            break
        e.visit_count += 1
        cur = e.predecessor
    return n


def apply_lethal_bonus(node: Node, reward: float, stats: Dict[str, int]) -> float:
    """`MCGS.Backup`: a terminal win on the turn the search started is worth ten times more."""
    if node.is_terminal and node.play_state == "WON" and node.depth_turn_equals_start():
        stats["lethal_bonus"] = stats.get("lethal_bonus", 0) + 1
        return reward * LETHAL_BACKUP_MULTIPLIER
    return reward


def _depth_turn_equals_start(self) -> bool:
    """`node.Game.Turn == node.StartTurn` -- a win found without ceding the turn."""
    return not self.is_end_turn


Node.depth_turn_equals_start = _depth_turn_equals_start

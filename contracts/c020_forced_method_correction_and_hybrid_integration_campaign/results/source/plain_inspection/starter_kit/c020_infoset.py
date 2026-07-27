"""c020 A1 — shared information-set statistics across determinizations.

This is the correction that separates ISMCTS from what c019 actually built. c019 created one
independent PUCT tree per determinization and combined them only at the root, which is PIMC: each
tree learned about its own sampled world and none of them pooled evidence about the *information
set* the acting player is really in.

Here every determinization-private node reads and writes action statistics from ONE shared table,
keyed by information available to the acting player alone. Sampled opponent hands, sampled prizes,
sampled deck order and native search IDs are excluded from the key by construction — if any of
them entered it, two determinizations of the same visible state would key differently and the
sharing would silently degrade back to c019's behaviour.

Availability accounting is the other half. An action legal in world X but not in world Y must not
be charged a loss for the visits it never had: its Q is an average over the worlds where it could
actually be played, and its exploration term uses the parent visits over those same worlds.
Without this, actions that are situationally strong but often illegal are systematically buried.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

C_PUCT_DEFAULT = 1.5


@dataclass(frozen=True)
class InfoSetKey:
    """Identity of an information set. Contains ONLY what the acting player can observe.

    `MANDATORY_CHANGES A1` enumerates what must be excluded. The exclusions are enforced by
    construction — this key is built from a visible-only observation view, so there is no code
    path that could add a sampled value to it.
    """

    visible_hash: str
    player: int
    select_signature: Tuple
    legal_signature: Tuple
    public_memory_signature: Tuple

    def short(self) -> str:
        return f"{self.visible_hash[:12]}|p{self.player}|{hash(self.legal_signature) & 0xFFFFFF:06x}"


@dataclass
class SharedActionStats:
    """Statistics for ONE action at ONE information set, pooled across determinizations."""

    n: int = 0
    w: float = 0.0
    prior: float = 0.0
    availability: int = 0            # determinization-visits where this action was legal
    det_ids: set = field(default_factory=set)   # which worlds contributed (M02 evidence)

    @property
    def q(self) -> float:
        return self.w / self.n if self.n else 0.0

    def to_json(self) -> Dict[str, Any]:
        return {"n": self.n, "w": round(self.w, 6), "q": round(self.q, 6),
                "prior": round(self.prior, 6), "availability": self.availability,
                "determinizations": sorted(self.det_ids)[:16],
                "distinct_determinizations": len(self.det_ids)}


@dataclass
class SharedInfoSetStats:
    """All actions at one information set, plus how many times the set itself was visited."""

    n: int = 0
    actions: Dict[Any, SharedActionStats] = field(default_factory=dict)
    det_ids: set = field(default_factory=set)

    def ensure(self, action_key, prior: float = 0.0) -> SharedActionStats:
        st = self.actions.get(action_key)
        if st is None:
            st = SharedActionStats(prior=prior)
            self.actions[action_key] = st
        elif prior and not st.prior:
            st.prior = prior
        return st

    def update_availability(self, legal_keys: Iterable, det_id: int) -> None:
        """Record that this info set was reached in `det_id` with exactly `legal_keys` legal.

        Availability is incremented ONLY for actions legal in this world. An action absent here
        keeps its previous availability, so its Q stays an average over the worlds where it was
        actually playable (A1, probe M03).
        """
        self.det_ids.add(det_id)
        for k in legal_keys:
            self.ensure(k).availability += 1

    def to_json(self, limit: int = 32) -> Dict[str, Any]:
        items = sorted(self.actions.items(), key=lambda kv: -kv[1].n)[:limit]
        return {"n": self.n, "distinct_determinizations": len(self.det_ids),
                "actions": {str(k): v.to_json() for k, v in items}}


class InfoSetTable:
    """The shared table. ONE instance per decision, shared by every determinization."""

    def __init__(self):
        self.table: Dict[InfoSetKey, SharedInfoSetStats] = {}
        self.reads = 0
        self.writes = 0
        self.cross_det_hits = 0     # info sets reached from >=2 distinct determinizations

    def get(self, key: InfoSetKey) -> SharedInfoSetStats:
        st = self.table.get(key)
        if st is None:
            st = SharedInfoSetStats()
            self.table[key] = st
        self.reads += 1
        return st

    def note_visit(self, key: InfoSetKey, det_id: int) -> None:
        st = self.get(key)
        before = len(st.det_ids)
        st.det_ids.add(det_id)
        if before == 1 and len(st.det_ids) == 2:
            self.cross_det_hits += 1

    def stats(self) -> Dict[str, Any]:
        multi = [k for k, v in self.table.items() if len(v.det_ids) >= 2]
        shared_actions = sum(1 for v in self.table.values()
                             for a in v.actions.values() if len(a.det_ids) >= 2)
        return {
            "info_sets": len(self.table),
            "info_sets_reached_by_multiple_determinizations": len(multi),
            "action_stats_updated_by_multiple_determinizations": shared_actions,
            "reads": self.reads, "writes": self.writes,
            # the single number that distinguishes A1 from c019: if this is 0, every
            # determinization kept to itself and the search is PIMC, not ISMCTS
            "sharing_is_real": bool(shared_actions > 0),
        }

    def dump(self, limit: int = 64) -> Dict[str, Any]:
        rows = sorted(self.table.items(), key=lambda kv: -kv[1].n)[:limit]
        return {"stats": self.stats(),
                "info_sets": {k.short(): v.to_json() for k, v in rows}}


def puct_scores(stats: SharedInfoSetStats, legal_keys: List[Any],
                c_puct: float = C_PUCT_DEFAULT,
                availability_aware: bool = True) -> Dict[Any, float]:
    """`score = Q + c_puct * P * sqrt(parent_N) / (1 + action_N)` (A4).

    With `availability_aware`, the parent count for an action is its own availability rather than
    the info-set total, so an action legal in few worlds is not compared against a parent count it
    never had the chance to accumulate against.
    """
    out = {}
    for k in legal_keys:
        st = stats.ensure(k)
        parent_n = (st.availability if availability_aware and st.availability else stats.n)
        u = c_puct * st.prior * math.sqrt(max(parent_n, 1)) / (1 + st.n)
        out[k] = st.q + u
    return out


def select_puct(stats: SharedInfoSetStats, legal_keys: List[Any],
                c_puct: float = C_PUCT_DEFAULT,
                availability_aware: bool = True):
    if not legal_keys:
        return None
    sc = puct_scores(stats, legal_keys, c_puct, availability_aware)
    return max(legal_keys, key=lambda k: sc[k])


def backup(path: List[Tuple[SharedInfoSetStats, Any, int]], value: float,
           root_player: int) -> int:
    """Backpropagate ONE simulation from the ROOT PLAYER's perspective (A4).

    `path` entries are `(shared_stats, action_key, player_to_move)`. The leaf value is already in
    root-player terms; where the mover differs from the root player the sign flips, because a
    position good for the opponent is bad for us. Getting this wrong makes more search reliably
    worse, which is exactly the c019 symptom (#3) and worth stating explicitly.
    """
    n = 0
    for stats, action_key, mover in path:
        stats.n += 1
        st = stats.ensure(action_key)
        st.n += 1
        st.w += value if mover == root_player else -value
        n += 1
    return n

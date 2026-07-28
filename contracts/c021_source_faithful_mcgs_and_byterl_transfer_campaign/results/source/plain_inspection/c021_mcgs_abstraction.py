"""c021 A2 — PTCG state and action abstraction for the MCGS transposition DAG.

Functional port of `src/Abstraction/StateAbstraction.cs` and `ActionAbstraction.cs`.

The source hashes, in this order and with this combiner:

    hash = ArrayHashCode(_ids)                       # choice info, own hand, ..., opponent hand
    hash = hash * 17 + ArrayHashCode(_boards)        # own board, opponent board
    hash = hash * 17 + _opDeckCount
    hash = hash * 17 + ArrayHashCode(_deck)
    hash = hash * 17 + _actionHashCode

The `* 17` combiner and the field ORDER are preserved because they define which distinct states
collide, which is the property the transposition table is built on. What each field contains is a
`SEMANTIC_ADAPTER`: Hearthstone's minion board becomes PTCG's active plus bench slots, hero
becomes prizes and deck counts, and so on.

`SimpleAbstraction = true` in the shipped config, so the source's simplified variant is the one
ported.

The abstraction covers the ACTIVE PLAYER'S INFORMATION SET only: it reads through
`c019_core.visible_view`, which raises on opponent hand contents, deck order and unrevealed
prizes. The source's known information-set limitation is reproduced separately in A9 rather than
being smuggled in here.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_cards as CD  # noqa: E402

MASK32 = 0xFFFFFFFF


def _arr_hash(xs) -> int:
    """`Utils/IntArrayComparer.ArrayHashCode` role: order-sensitive integer array hash."""
    h = 17
    for x in xs:
        if isinstance(x, (list, tuple)):
            h = (h * 31 + _arr_hash(x)) & MASK32
        else:
            h = (h * 31 + (int(x) & MASK32)) & MASK32
    return h


def _combine(*parts: int) -> int:
    """The source's `hash = hash * 17 + next` chain, preserved exactly."""
    it = iter(parts)
    h = next(it)
    for p in it:
        h = (h * 17 + p) & MASK32
    return h


@dataclass(frozen=True)
class ActionAbstraction:
    """`ActionAbstraction`: an action identified by type/source/target, not by list position."""

    select_type: int
    context: int
    option_type: int
    source_ref: int
    target_ref: int
    card_id: int
    attack_id: int

    @property
    def is_end_turn_action(self) -> bool:
        from cg import c020_override as OV
        return self.option_type == OV.OPT_END

    def hash_code(self) -> int:
        return _arr_hash((self.select_type, self.context, self.option_type,
                          self.source_ref, self.target_ref, self.card_id, self.attack_id))

    def short(self) -> str:
        return (f"t{self.option_type}:s{self.source_ref}:g{self.target_ref}"
                f"{':c' + str(self.card_id) if self.card_id >= 0 else ''}")


def action_abstraction_of(opt, sel) -> ActionAbstraction:
    """Build an ActionAbstraction from a canonical option, using structured engine fields."""
    from cg import c020_byterl_encode as E
    f = opt.fields
    def fld(name, default=-1):
        i = E._F.get(name)
        return int(f[i]) if (i is not None and i < len(f)) else default
    return ActionAbstraction(
        select_type=int(getattr(opt, "select_type", -1)),
        context=int(getattr(opt, "select_context", -1)),
        option_type=int(getattr(opt, "option_type", -1)),
        source_ref=fld("area") * 16 + max(0, fld("index")),
        target_ref=fld("inPlayArea") * 16 + max(0, fld("inPlayIndex")),
        card_id=int(getattr(opt, "referenced_card_id", -1) or -1),
        attack_id=int(getattr(opt, "referenced_attack_id", -1) or -1))


class StateAbstraction:
    """The transposition key. Hash is computed ONCE and cached.

    Phase 1 measured `observation_hash` at 37.5 us against an 83.9 us forward step, so re-hashing
    per lookup would cost ~45% of a step. The source caches in `_hashCode`; so does this.
    """

    __slots__ = ("_ids", "_boards", "_deck", "_op_deck_count", "_action_hash", "_hash",
                 "simple", "contains_deck")

    def __init__(self, observation, action: Optional[ActionAbstraction] = None,
                 your_index: Optional[int] = None, simple: bool = True):
        self.simple = simple
        self.contains_deck = not simple
        v = K.visible_view(observation, your_index)
        counts = v.counts()
        mine = v.board("mine")
        theirs = v.board("theirs")

        def pk_row(p) -> Tuple:
            """One board slot. Identity-preserving: card, hp, energy BY TYPE, status, tool."""
            if p is None:
                return (0,)
            att = CD.attached_energy(p)
            hp, mx = CD.hp_now(p)
            return (int(getattr(p, "id", 0) or 0), hp, mx,
                    tuple(sorted(att.items())),
                    1 if (getattr(p, "tools", None) or []) else 0,
                    CD.energy_shortfall(p))

        def side(b) -> Tuple:
            act = (b.get("active") or [None])
            bench = [x for x in (b.get("bench") or [])]
            return (pk_row(act[0] if act else None),
                    tuple(pk_row(x) for x in bench))

        # _boards: own board, opponent board
        self._boards = (side(mine), side(theirs))
        # _ids: [choice info, own hand, discards, prizes/turn, opponent visible hand size]
        sel = getattr(observation, "select", None)
        choice = ((int(getattr(sel, "selectType", -1) or -1),
                   int(getattr(sel, "context", -1) or -1),
                   int(getattr(sel, "minCount", 0) or 0),
                   int(getattr(sel, "maxCount", 0) or 0)) if sel is not None else (-1,))
        hand = tuple(sorted(int(getattr(c, "id", 0) or 0) for c in v.my_hand()))
        my_disc = tuple(sorted(int(getattr(c, "id", 0) or 0) for c in v.discard("mine")))
        op_disc = tuple(sorted(int(getattr(c, "id", 0) or 0) for c in v.discard("theirs")))
        self._ids = (choice, hand, my_disc, op_disc,
                     (counts["opp_hand"],))          # opponent hand SIZE only -- not contents
        # _deck / _opDeckCount
        self._deck = (counts["my_deck"], counts["my_prize"], counts["opp_prize"])
        self._op_deck_count = counts["opp_deck"]
        self._action_hash = action.hash_code() if action is not None else 0
        self._hash = None

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = _combine(_arr_hash(self._ids), _arr_hash(self._boards),
                                  self._op_deck_count, _arr_hash(self._deck),
                                  self._action_hash)
        return self._hash

    def __eq__(self, other) -> bool:
        """Full structural equality, so a hash collision cannot merge two distinct states.

        The source implements `IEquatable<StateAbstraction>` alongside `GetHashCode` for the same
        reason; relying on the hash alone would silently fuse unrelated positions in the DAG.
        """
        if not isinstance(other, StateAbstraction):
            return NotImplemented
        return (self._ids == other._ids and self._boards == other._boards
                and self._deck == other._deck
                and self._op_deck_count == other._op_deck_count
                and self._action_hash == other._action_hash)

    def fields(self) -> Dict[str, Any]:
        return {"ids": self._ids, "boards": self._boards, "deck": self._deck,
                "op_deck_count": self._op_deck_count, "action_hash": self._action_hash,
                "hash": hash(self)}

    def short(self) -> str:
        return f"{hash(self) & 0xFFFFFF:06x}"

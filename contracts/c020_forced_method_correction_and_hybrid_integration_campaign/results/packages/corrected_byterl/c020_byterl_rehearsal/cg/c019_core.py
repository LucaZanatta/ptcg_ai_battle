"""c019 shared PTCG core — canonical options, visible-only observation, identity.

One serializer serves evaluation identity, neural option encoding, MCTS root aggregation across
determinizations, and package execution. If those disagreed about what "the same action" means,
aggregation would sum visits across different actions and the panel would compare different
agents under one name.

CONTRACT §7 limits this module to what BOTH methods genuinely need. It is deliberately not a
generic multi-game framework.

HIDDEN INFORMATION (P02). `VisibleObservation` is the only accessor the ByteRL encoder may use,
and it RAISES rather than returns when asked for a genuinely hidden zone. §7: "The ByteRL branch
must never receive hidden sampled state as observation." A structural guard makes a leak a crash
in a probe instead of a silent advantage — the MCTS determinizer is separately allowed to
*predict* hidden zones, but never to read them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Option field order is FROZEN. It defines the canonical key, so appending a field mid-campaign
# would silently change every action identity and invalidate cross-run aggregation.
OPTION_FIELDS = ("number", "area", "index", "playerIndex", "toolIndex", "energyIndex",
                 "count", "inPlayArea", "inPlayIndex", "serial", "specialConditionType")
CANON_VERSION = "c019.canon.v1"


class HiddenInformationAccess(Exception):
    """Raised when something reaches for a zone the submitted agent may not see."""


def _iv(x) -> int:
    """Options carry IntEnums, ints and Nones; the key must be hashable and stable."""
    if x is None:
        return -1
    try:
        return int(x)
    except (TypeError, ValueError):
        return -1


@dataclass(frozen=True)
class CanonicalOption:
    """A legal option identified independently of its position in the option list.

    Index-based identity would break the moment the engine reorders options between a search
    successor and the live game, which is exactly where MCTS aggregation and package execution
    have to agree.
    """

    select_type: int
    select_context: int
    option_type: int
    fields: Tuple[int, ...]
    referenced_card_id: int = 0
    referenced_attack_id: int = 0
    option_index: int = -1        # positional index in the ORIGINATING option list; not in key

    def key(self) -> Tuple:
        return (self.select_type, self.select_context, self.option_type, self.fields,
                self.referenced_card_id, self.referenced_attack_id)

    def short(self) -> str:
        return hashlib.sha256(repr(self.key()).encode()).hexdigest()[:16]


def canonical_option(opt: Any, select_type: int, select_context: int,
                     index: int = -1) -> CanonicalOption:
    """API option -> CanonicalOption. Accepts dataclass or dict form."""
    def g(name):
        return opt.get(name) if isinstance(opt, dict) else getattr(opt, name, None)
    return CanonicalOption(
        select_type=_iv(select_type), select_context=_iv(select_context),
        option_type=_iv(g("type")),
        fields=tuple(_iv(g(f)) for f in OPTION_FIELDS),
        referenced_card_id=_iv(g("cardId")), referenced_attack_id=_iv(g("attackId")),
        option_index=int(index))


def canonical_options(sel: Any) -> List[CanonicalOption]:
    """All legal options of a select, in engine order."""
    if sel is None:
        return []
    def g(name):
        return sel.get(name) if isinstance(sel, dict) else getattr(sel, name, None)
    st, ctx = _iv(g("type")), _iv(g("context"))
    return [canonical_option(o, st, ctx, i) for i, o in enumerate(g("option") or [])]


def to_select_payload(chosen: List[CanonicalOption], sel: Any) -> List[int]:
    """CanonicalOption -> the index payload the simulator expects.

    Resolved by KEY against the live option list rather than by remembered index, so an option
    list reordered between planning and execution cannot cause a different action to be played.
    """
    live = canonical_options(sel)
    by_key = {o.key(): o.option_index for o in live}
    out = []
    for c in chosen:
        i = by_key.get(c.key())
        if i is None:
            raise KeyError(f"canonical option not present in the live option set: {c.short()}")
        out.append(int(i))
    return out


def round_trip_ok(sel: Any) -> Tuple[bool, Dict[str, Any]]:
    """P01: every option round-trips API -> canonical -> payload, and keys are unique."""
    live = canonical_options(sel)
    if not live:
        return True, {"n": 0, "note": "no options"}
    keys = [o.key() for o in live]
    dupes = len(keys) - len(set(keys))
    bad = []
    for o in live:
        try:
            p = to_select_payload([o], sel)
            if p != [o.option_index]:
                bad.append({"opt": o.short(), "expected": o.option_index, "got": p})
        except KeyError as e:  # noqa: BLE001
            bad.append({"opt": o.short(), "error": str(e)[:120]})
    return (not bad and dupes == 0), {"n": len(live), "duplicate_keys": dupes,
                                      "failures": bad[:6]}


# ------------------------------------------------------------------ visible observation

@dataclass
class VisibleObservation:
    """The ONLY state accessor the ByteRL encoder may use (P02).

    Own hand is visible to us. Opponent hand CONTENTS, either deck's contents/order, and
    unrevealed prize IDs are not, and asking for them raises.
    """

    _state: Any
    _yi: int
    reads: List[str] = field(default_factory=list)

    def _log(self, what: str):
        self.reads.append(what)

    @property
    def me(self):
        return self._state.players[self._yi]

    @property
    def opp(self):
        return self._state.players[1 - self._yi]

    # ---- permitted ----
    def my_hand(self) -> List[Any]:
        self._log("my_hand")
        return [c for c in (self.me.hand or []) if c is not None]

    def board(self, side: str) -> Dict[str, List[Any]]:
        self._log(f"board:{side}")
        p = self.me if side == "mine" else self.opp
        return {"active": list(getattr(p, "active", None) or []),
                "bench": list(getattr(p, "bench", None) or [])}

    def discard(self, side: str) -> List[Any]:
        self._log(f"discard:{side}")
        p = self.me if side == "mine" else self.opp
        return [c for c in (getattr(p, "discard", None) or []) if c is not None]

    def counts(self) -> Dict[str, int]:
        self._log("counts")
        return {
            "my_deck": int(getattr(self.me, "deckCount", 0) or 0),
            "my_hand": len(self.my_hand()),
            "my_prize": len(getattr(self.me, "prize", None) or []),
            "opp_deck": int(getattr(self.opp, "deckCount", 0) or 0),
            "opp_hand": int(getattr(self.opp, "handCount", 0) or 0),
            "opp_prize": len(getattr(self.opp, "prize", None) or []),
        }

    # ---- forbidden: raise rather than return ----
    def opponent_hand_contents(self):
        raise HiddenInformationAccess("opponent hand contents are hidden")

    def deck_contents(self, side: str):
        raise HiddenInformationAccess(f"{side} deck contents/order are hidden")

    def prize_contents(self, side: str):
        raise HiddenInformationAccess(f"{side} prize contents are hidden")


def visible_view(observation, your_index: Optional[int] = None) -> VisibleObservation:
    st = observation.current if hasattr(observation, "current") else observation
    yi = st.yourIndex if your_index is None else your_index
    return VisibleObservation(st, yi)


# ------------------------------------------------------------------ identity

def observation_hash(observation) -> str:
    """Structural hash over VISIBLE state plus the live option set.

    Used for transposition detection and for telling successor outcomes apart (M08). It reads
    only fields `VisibleObservation` permits, so hashing cannot become a hidden-state side
    channel.
    """
    parts = [CANON_VERSION]
    try:
        sel = observation.select
        parts.append(f"ctx={_iv(getattr(sel, 'context', None))}")
        parts.append(f"lo={_iv(getattr(sel, 'minCount', None))}")
        parts.append(f"hi={_iv(getattr(sel, 'maxCount', None))}")
        for o in canonical_options(sel):
            parts.append(o.short())
    except Exception:  # noqa: BLE001
        parts.append("terminal")
    try:
        v = visible_view(observation)
        c = v.counts()
        parts.append("|".join(f"{k}={c[k]}" for k in sorted(c)))
        for side in ("mine", "theirs"):
            b = v.board(side)
            for z in ("active", "bench"):
                for card in b[z]:
                    parts.append("_" if card is None else
                                 f"{side[0]}{z[0]}:{getattr(card, 'id', '?')}:"
                                 f"{getattr(card, 'hp', '?')}:"
                                 f"{len(getattr(card, 'energyCards', None) or [])}")
            parts.append(f"{side[0]}disc={len(v.discard(side))}")
    except Exception:  # noqa: BLE001
        pass
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def game_id(prefix: str, index: int, seed: int, seat: int, opponent: str) -> str:
    return f"{prefix}:g{index:06d}:s{seed}:seat{seat}:vs{opponent}"

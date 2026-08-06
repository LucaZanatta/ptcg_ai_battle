"""Observation normalization for stateless-ambiguity analysis (c006).

Defines a *documented* canonicalization of a schema-v2 observation into the
strategic state that a stateless policy can actually condition on, dropping only
non-strategic volatile identifiers:

  - ``remainingOverageTime`` (a wall-clock budget, not board state)
  - ``step`` (a monotone global counter that trivially separates every decision)
  - ``serial`` (per-instance card tags; two strategically identical boards differ
    only in these)

Everything strategic is kept: card ids, hp/energies, board zones, counts, the
select context and its bounds, and the full legal-option list. Two decisions are
*exactly stateless-equivalent* when their canonical (state, options) match but the
teacher's chosen action differs — a genuinely history-dependent decision a
stateless model cannot separate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

_VOLATILE_TOP = ("remainingOverageTime", "step")
_DROP_KEYS = ("serial",)


def _strip(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in _DROP_KEYS}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def canon_state(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical strategic state: current board + select metadata, volatile ids removed."""
    sel = obs.get("select") or {}
    cur = obs.get("current")
    ctx_card = sel.get("contextCard")
    effect = sel.get("effect")
    return {
        "current": _strip(cur),
        "select_meta": {
            "context": sel.get("context"),
            "type": sel.get("type"),
            "minCount": sel.get("minCount"),
            "maxCount": sel.get("maxCount"),
            "remainDamageCounter": sel.get("remainDamageCounter"),
            "remainEnergyCost": sel.get("remainEnergyCost"),
            "contextCard_id": None if ctx_card is None else ctx_card.get("id"),
            "effect_id": None if effect is None else effect.get("id"),
            "has_deck": sel.get("deck") is not None,
            "deck": _strip(sel.get("deck")),
        },
    }


def canon_options(legal_options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Canonical legal-option list (volatile ids removed; order preserved)."""
    return [_strip(o) for o in legal_options]


def _dumps(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), default=str)


def exact_hash(obs: Dict[str, Any], legal_options: List[Dict[str, Any]]) -> str:
    payload = _dumps([canon_state(obs), canon_options(legal_options)])
    return hashlib.sha256(payload.encode()).hexdigest()


def action_key(legal_options: List[Dict[str, Any]], indices: List[int]) -> str:
    """Order-independent semantic key for the chosen action (by option content)."""
    co = canon_options(legal_options)
    chosen = sorted(_dumps(co[i]) for i in indices)
    return _dumps(chosen)


def _multiset_ids(cards: Any) -> List[int]:
    out = []
    for c in (cards or []):
        if isinstance(c, dict) and "id" in c:
            out.append(c["id"])
    return sorted(out)


def near_hash(obs: Dict[str, Any], legal_options: List[Dict[str, Any]]) -> str:
    """Coarse near-duplicate bucket: context + option shape + board summary.

    Groups states that share strategic structure (same context, same option-type
    multiset and count, same active/bench card-id multisets, prize counts, turn)
    but may differ in fine detail. Documented, deterministic.
    """
    sel = obs.get("select") or {}
    cur = obs.get("current") or {}
    yi = cur.get("yourIndex", 0)
    players = cur.get("players") or [{}, {}]
    me = players[yi] if yi < len(players) else {}
    op = players[1 - yi] if (1 - yi) < len(players) else {}
    feat = {
        "ctx": sel.get("context"),
        "lo": sel.get("minCount"),
        "hi": sel.get("maxCount"),
        "n_opt": len(legal_options),
        "opt_types": sorted(o.get("type") for o in legal_options),
        "turn": cur.get("turn"),
        "my_active": _multiset_ids(me.get("active")),
        "my_bench": _multiset_ids(me.get("bench")),
        "my_hand": _multiset_ids(me.get("hand")),
        "my_prize_n": len(me.get("prize") or []),
        "op_active": _multiset_ids(op.get("active")),
        "op_bench": _multiset_ids(op.get("bench")),
        "op_prize_n": len(op.get("prize") or []),
        "remain_dmg": sel.get("remainDamageCounter"),
    }
    return hashlib.sha256(_dumps(feat).encode()).hexdigest()

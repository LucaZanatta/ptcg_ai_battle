"""Deterministic engineering control (c006 §14): the deterministic-first safe
policy playing the exact frozen Dragapult deck. Isolates deck strength from
strategy — reported separately from the students."""

from __future__ import annotations

from typing import Any, Dict, List

from cg.safe_policy import select_indices


class DetControl:
    def __init__(self, deck: List[int]):
        self.deck = list(deck)

    def __call__(self, obs: Any) -> List[int]:
        sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
        if sel is None:
            return list(self.deck)
        return select_indices(len(sel.get("option", [])), sel.get("minCount"), sel.get("maxCount"))

    def classify_decision(self, obs: Any, res: List[int]) -> Dict[str, Any]:
        return {"decision_source": "deterministic", "used_fallback": False, "fallback_reason": None}

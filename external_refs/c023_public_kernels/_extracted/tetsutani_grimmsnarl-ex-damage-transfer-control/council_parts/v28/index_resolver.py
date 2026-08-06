from __future__ import annotations
from .resource_ledger import action_signature

def resolve_index(options: list[dict], selected: list[int], legacy: list[int]) -> list[int]:
    if len(selected) == 1 and len(legacy) == 1:
        if action_signature(options[selected[0]]) == action_signature(options[legacy[0]]):
            return legacy
    return selected

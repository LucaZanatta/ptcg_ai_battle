from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def _resolve_root() -> Path:
    candidates = []
    if "__file__" in globals():
        candidates.append(Path(globals()["__file__"]).resolve().parent)
    candidates.extend((Path.cwd(), Path("/kaggle_simulations/agent")))
    for candidate in candidates:
        if (candidate / "deck.csv").is_file() and (candidate / "policy_core.py").is_file():
            return candidate.resolve()
    return Path("/kaggle_simulations/agent")


ROOT = _resolve_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_deck_csv() -> list[int]:
    path = ROOT / "deck.csv"
    if not path.is_file():
        path = Path("/kaggle_simulations/agent/deck.csv")
    values = [int(line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(values) != 60:
        raise ValueError(f"deck must contain 60 cards, got {len(values)}")
    return values


DECK = read_deck_csv()
EXPECTED_DECK = tuple(DECK)
_POLICY = None


def _select_value(observation):
    if isinstance(observation, dict):
        return observation.get("select")
    return getattr(observation, "select", None)


def _load_policy():
    global _POLICY
    if _POLICY is None:
        importlib.invalidate_caches()
        _POLICY = importlib.import_module("policy_core")
    return _POLICY


def _fallback_action(observation) -> list[int]:
    select = _select_value(observation) or {}
    if isinstance(select, dict):
        options = select.get("option") or []
        minimum = int(select.get("minCount", 0) or 0)
        maximum = int(select.get("maxCount", 0) or 0)
    else:
        options = getattr(select, "option", None) or []
        minimum = int(getattr(select, "minCount", 0) or 0)
        maximum = int(getattr(select, "maxCount", 0) or 0)
    count = min(len(options), maximum)
    if count < minimum:
        count = min(len(options), minimum)
    return list(range(count))


def _legal(observation, action) -> bool:
    select = _select_value(observation) or {}
    if isinstance(select, dict):
        options = select.get("option") or []
        minimum = int(select.get("minCount", 0) or 0)
        maximum = int(select.get("maxCount", 0) or 0)
    else:
        options = getattr(select, "option", None) or []
        minimum = int(getattr(select, "minCount", 0) or 0)
        maximum = int(getattr(select, "maxCount", 0) or 0)
    return (
        isinstance(action, list)
        and minimum <= len(action) <= maximum
        and len(action) == len(set(action))
        and all(isinstance(index, int) and 0 <= index < len(options) for index in action)
    )


def agent(obs_dict: dict) -> list[int]:
    # Match the competition sample exactly: select=None is the deck handshake.
    if _select_value(obs_dict) is None:
        if _POLICY is not None:
            try:
                _POLICY.agent(obs_dict)
            except Exception:
                pass
        return read_deck_csv()

    try:
        action = list(_load_policy().agent(obs_dict))
    except Exception:
        action = _fallback_action(obs_dict)
    if not _legal(obs_dict, action):
        action = _fallback_action(obs_dict)
    return action

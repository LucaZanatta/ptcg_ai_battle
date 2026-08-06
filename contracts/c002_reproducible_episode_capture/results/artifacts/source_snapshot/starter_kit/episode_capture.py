"""Versioned episode capture for cabt games (schema version 1).

Records one JSONL record per agent option-selection decision, bracketed by a
``game_start`` record and a ``game_terminal`` record per game. Capture is a thin
external wrapper around an agent callable; it never alters the returned action,
so the c001 deterministic-safe behaviour is preserved exactly.

Record types (field ``record_type``):
- ``game_start``   : game_id, cohort, seed, seat assignment, agents, decks.
- ``decision``     : one option-selection decision (context, bounds, indices...).
- ``game_terminal``: winner, terminal reason, per-agent decision counts, timing.

Deck-selection calls (``obs["select"] is None``) are NOT emitted as ``decision``
records: they return a 60-card deck, not option indices, and have no legal
bounds to validate. The deck used by each seat is captured in ``game_start``.

Serialization is portable JSON only (no pickle). Non-JSON observation values are
replaced with ``null`` and their paths listed in ``omitted_observation_fields``.
Text is UTF-8.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Tuple

from cg.api import SelectContext
from cg.safe_policy import MalformedSelection, validate_selection

SCHEMA_VERSION = 1


def derive_seed(base_seed: int, game_index: int) -> int:
    """Deterministically derive a unique per-game seed from a base seed + index.

    Stable and reproducible: identical (base_seed, game_index) always yields the
    same value. Uses odd multipliers to spread indices across the 63-bit range.
    """
    return (int(base_seed) * 6364136223846793005 + int(game_index) * 1442695040888963407 + 1) % (2 ** 63)


def context_name(value: Any) -> str:
    try:
        return SelectContext(value).name
    except (ValueError, TypeError):
        return f"UNKNOWN_{value}"


def deck_identifier(deck: List[int]) -> str:
    """Stable identifier for a deck list (size + short content hash)."""
    digest = hashlib.sha256(",".join(str(c) for c in deck).encode("utf-8")).hexdigest()
    return f"deck{len(deck)}_{digest[:12]}"


def normalize_observation(obs: Any) -> Tuple[Any, List[str]]:
    """Convert an observation (dict-like) into a JSON-safe structure.

    Returns ``(normalized, omitted_paths)``. Non-JSON scalars become ``null`` and
    their dotted paths are collected in ``omitted_paths`` (normally empty, since
    cabt observations originate from engine JSON).
    """
    omitted: List[str] = []

    def convert(node: Any, path: str) -> Any:
        if node is None or isinstance(node, (str, int, float, bool)):
            return node
        if isinstance(node, dict):
            return {str(k): convert(v, f"{path}.{k}") for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [convert(v, f"{path}[{i}]") for i, v in enumerate(node)]
        omitted.append(path)
        return None

    return convert(obs, "obs"), omitted


class JsonlWriter:
    """Append-only JSONL writer with flush discipline (UTF-8)."""

    def __init__(self, path: str):
        self._path = path
        self._fh = open(path, "w", encoding="utf-8")
        self.records_written = 0

    def write(self, record: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()
        self.records_written += 1

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class GameRecorder:
    """Records decisions for a single game to a shared :class:`JsonlWriter`."""

    def __init__(self, writer: JsonlWriter, *, game_id: str, cohort: str, game_seed: int,
                 safe_seat: Any, agents_by_seat: Dict[int, str], decks_by_seat: Dict[int, str]):
        self._writer = writer
        self.game_id = game_id
        self.cohort = cohort
        self.game_seed = game_seed
        self.safe_seat = safe_seat
        self.agents_by_seat = agents_by_seat
        self.decks_by_seat = decks_by_seat
        self._decision_index = 0
        self.decisions_by_player: Dict[int, int] = {0: 0, 1: 0}
        self.invalid_by_player: Dict[int, int] = {0: 0, 1: 0}

    def write_start(self) -> None:
        self._writer.write({
            "schema_version": SCHEMA_VERSION,
            "record_type": "game_start",
            "game_id": self.game_id,
            "cohort": self.cohort,
            "game_seed": self.game_seed,
            "safe_seat": self.safe_seat,
            "agents_by_seat": {str(k): v for k, v in self.agents_by_seat.items()},
            "decks_by_seat": {str(k): v for k, v in self.decks_by_seat.items()},
        })

    def record_decision(self, *, agent_name: str, player_index: int, seat: int,
                        is_safe_agent: bool, obs: Any, result: List[int],
                        latency_ns: int, decision_ts_ns: int) -> str:
        select = obs["select"]
        num_options = len(select.get("option", []))
        min_count = select.get("minCount")
        max_count = select.get("maxCount")
        ctx_value = select.get("context")
        validation = "valid"
        try:
            validate_selection(list(result), num_options, min_count, max_count)
        except MalformedSelection as exc:
            validation = f"invalid: {exc}"
            self.invalid_by_player[player_index] = self.invalid_by_player.get(player_index, 0) + 1
        norm_obs, omitted = normalize_observation(obs)
        idx = self._decision_index
        self._decision_index += 1
        self.decisions_by_player[player_index] = self.decisions_by_player.get(player_index, 0) + 1
        self._writer.write({
            "schema_version": SCHEMA_VERSION,
            "record_type": "decision",
            "game_id": self.game_id,
            "decision_index": idx,
            "player_index": player_index,
            "seat": seat,
            "game_seed": self.game_seed,
            "agent_name": agent_name,
            "deck_identifier": self.decks_by_seat.get(seat),
            "timestamp_monotonic_ns": decision_ts_ns,
            "observation": norm_obs,
            "omitted_observation_fields": omitted,
            "context_name": context_name(ctx_value),
            "context_value": ctx_value,
            "legal_option_count": num_options,
            "legal_option_metadata": select.get("option"),
            "min_count": min_count,
            "max_count": max_count,
            "selected_indices": list(result),
            "policy_latency_ns": latency_ns,
            "used_fallback": bool(is_safe_agent),
            "validation_status": validation,
        })
        return validation

    def write_terminal(self, *, winner: Any, terminal_reason: str, duration_s: float,
                       error_status: Any, statuses: List[str], rewards: List[Any]) -> None:
        total_invalid = sum(self.invalid_by_player.values())
        self._writer.write({
            "schema_version": SCHEMA_VERSION,
            "record_type": "game_terminal",
            "game_id": self.game_id,
            "cohort": self.cohort,
            "game_seed": self.game_seed,
            "safe_seat": self.safe_seat,
            "agents_by_seat": {str(k): v for k, v in self.agents_by_seat.items()},
            "decks_by_seat": {str(k): v for k, v in self.decks_by_seat.items()},
            "initial_seat_assignment": {str(k): v for k, v in self.agents_by_seat.items()},
            "winner": winner,
            "terminal_reason": terminal_reason,
            "statuses": statuses,
            "rewards": rewards,
            "decisions_by_player": {str(k): v for k, v in self.decisions_by_player.items()},
            "invalid_selection_count": total_invalid,
            "error_status": error_status,
            "game_duration_s": duration_s,
        })


def make_capturing_agent(recorder: GameRecorder, inner: Callable[[Any], List[int]], *,
                         agent_name: str, player_index: int, seat: int,
                         is_safe_agent: bool) -> Callable[[Any], List[int]]:
    """Wrap ``inner`` so each option-selection decision is recorded.

    The wrapper returns ``inner``'s result unchanged (behaviour-preserving) and
    measures only the inner call's latency (engine time excluded).
    """

    def wrapped(obs: Any) -> List[int]:
        select = obs["select"]
        ts_ns = time.perf_counter_ns()
        result = inner(obs)
        latency_ns = time.perf_counter_ns() - ts_ns
        if select is None:
            return result  # deck selection: captured at game level, not a decision record
        recorder.record_decision(
            agent_name=agent_name, player_index=player_index, seat=seat,
            is_safe_agent=is_safe_agent, obs=obs, result=result,
            latency_ns=latency_ns, decision_ts_ns=ts_ns,
        )
        return result

    return wrapped

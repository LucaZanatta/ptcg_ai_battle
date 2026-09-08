"""Schema-v2 episode capture.

Key improvements over v1 (c002):
- **Mutation-safe snapshot** (§7.7/AC-05): the observation is deep-normalized
  BEFORE the policy is invoked, so policy-side mutation cannot alter the record.
- **Structured provenance** (§7.4): decision_source/used_fallback/fallback_reason
  come from the agent's own ``classify_decision`` (policy property, not seat).
- **Honest seeds** (§7.5): no ``game_seed``; explicit runner/opponent/requested
  engine seed block with ``engine_rng_controlled=false``.
- **gzip tee** (§7.11): each record is streamed to both ``.jsonl`` and
  ``.jsonl.gz`` so the two files carry a byte-identical record stream.
- **Terminal from final state** (§7.10): via ``classify_terminal``.
"""

from __future__ import annotations

import gzip
import json
import time
from typing import Any, Dict, List, Optional

from cg.episode_capture import context_name, normalize_observation
from cg.episode_schema import SCHEMA_VERSION, classify_terminal
from cg.safe_policy import MalformedSelection, validate_selection


class RunWriter:
    """Streams JSON records to a .jsonl and (optionally) a .jsonl.gz in lockstep.

    The same serialized line is written to both handles, so the decompressed gz
    content is byte-identical to the plain jsonl. Flushes at each game terminal
    and every ``flush_interval`` records.
    """

    def __init__(self, jsonl_path: str, gzip_path: Optional[str] = None,
                 flush_interval: int = 50):
        self.jsonl_path = jsonl_path
        self.gzip_path = gzip_path
        self._jsonl = open(jsonl_path, "w", encoding="utf-8")
        self._gz = gzip.open(gzip_path, "wt", encoding="utf-8") if gzip_path else None
        self.records_written = 0
        self._since_flush = 0
        self._flush_interval = max(1, flush_interval)

    def write(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        self._jsonl.write(line + "\n")
        if self._gz is not None:
            self._gz.write(line + "\n")
        self.records_written += 1
        self._since_flush += 1
        if self._since_flush >= self._flush_interval:
            self.flush()

    def flush(self) -> None:
        self._jsonl.flush()
        if self._gz is not None:
            self._gz.flush()
        self._since_flush = 0

    def close(self) -> None:
        self.flush()
        self._jsonl.close()
        if self._gz is not None:
            self._gz.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class GameRecorderV2:
    def __init__(self, writer: RunWriter, *, run_id: str, game_id: str, cohort: str,
                 seat_agent_ids: Dict[int, str], seat_deck_ids: Dict[int, str],
                 seed_meta: Dict[str, Any], seq: List[int]):
        self._writer = writer
        self.run_id = run_id
        self.game_id = game_id
        self.cohort = cohort
        self.seat_agent_ids = seat_agent_ids
        self.seat_deck_ids = seat_deck_ids
        self.seed_meta = seed_meta
        self._seq = seq
        self._decision_index = 0
        self.decisions_by_player: Dict[int, int] = {0: 0, 1: 0}
        self.invalid_by_player: Dict[int, int] = {0: 0, 1: 0}
        self.fallback_by_player: Dict[int, int] = {0: 0, 1: 0}

    def _record_id(self) -> str:
        self._seq[0] += 1
        return f"{self.run_id}:{self._seq[0]:08d}"

    def write_game_start(self) -> None:
        self._writer.write({
            "schema_version": SCHEMA_VERSION,
            "record_type": "game_start",
            "record_id": self._record_id(),
            "run_id": self.run_id,
            "game_id": self.game_id,
            "cohort": self.cohort,
            "seat_agent_ids": {str(k): v for k, v in self.seat_agent_ids.items()},
            "seat_deck_ids": {str(k): v for k, v in self.seat_deck_ids.items()},
            "seed": self.seed_meta,
        })

    def record_decision(self, *, player_index: int, seat: int, agent_def: Any,
                        obs_snapshot: Dict[str, Any], result: List[int],
                        latency_ns: int, ts_ns: int) -> Dict[str, Any]:
        select = obs_snapshot["select"]
        num_options = len(select.get("option", []))
        min_count = select.get("minCount")
        max_count = select.get("maxCount")
        ctx_value = select.get("context")
        provenance = agent_def.classify_decision(obs_snapshot, result)
        validation = "valid"
        try:
            validate_selection(list(result), num_options, min_count, max_count)
        except MalformedSelection as exc:
            validation = f"invalid: {exc}"
            self.invalid_by_player[player_index] = self.invalid_by_player.get(player_index, 0) + 1
        idx = self._decision_index
        self._decision_index += 1
        self.decisions_by_player[player_index] = self.decisions_by_player.get(player_index, 0) + 1
        if provenance.get("used_fallback"):
            self.fallback_by_player[player_index] = self.fallback_by_player.get(player_index, 0) + 1
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "decision",
            "record_id": self._record_id(),
            "run_id": self.run_id,
            "game_id": self.game_id,
            "decision_index": idx,
            "player_index": player_index,
            "seat": seat,
            "agent_id": agent_def.agent_id,
            "decision_source": provenance["decision_source"],
            "used_fallback": provenance["used_fallback"],
            "fallback_reason": provenance["fallback_reason"],
            "timestamp_monotonic_ns": ts_ns,
            "policy_latency_ns": latency_ns,
            "observation": obs_snapshot,
            # top-level duplicates of observation.select for cross-field checks:
            "select_context": ctx_value,
            "context_name": context_name(ctx_value),
            "min_count": min_count,
            "max_count": max_count,
            "legal_option_count": num_options,
            "legal_option_metadata": select.get("option"),
            "selected_indices": list(result),
            "validation_status": validation,
        }
        self._writer.write(record)
        return record

    def write_terminal(self, *, statuses: List[str], rewards: List[Any],
                       error: Optional[str], exception: Optional[str],
                       duration_s: float) -> Dict[str, Any]:
        terminal = classify_terminal(statuses, rewards, error=error, exception=exception)
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "game_terminal",
            "record_id": self._record_id(),
            "run_id": self.run_id,
            "game_id": self.game_id,
            "cohort": self.cohort,
            "seed": self.seed_meta,
            "seat_agent_ids": {str(k): v for k, v in self.seat_agent_ids.items()},
            **terminal,
            "decisions_by_player": {str(k): v for k, v in self.decisions_by_player.items()},
            "fallback_by_player": {str(k): v for k, v in self.fallback_by_player.items()},
            "invalid_selection_count": sum(self.invalid_by_player.values()),
            "game_duration_s": duration_s,
        }
        self._writer.write(record)
        self._writer.flush()  # flush at game terminal (§7.11)
        return record


def make_capturing_agent(recorder: GameRecorderV2, agent_def: Any, *,
                         player_index: int, seat: int):
    """Wrap ``agent_def`` so each option-selection decision is recorded.

    The observation is deep-normalized (snapshot) BEFORE invoking the policy, so
    any policy-side mutation of ``obs`` cannot change the stored record.
    """

    def wrapped(obs: Any) -> List[int]:
        select = obs["select"]
        snapshot = normalize_observation(obs)[0]  # deep copy taken BEFORE the call
        ts_ns = time.perf_counter_ns()
        result = agent_def(obs)
        latency_ns = time.perf_counter_ns() - ts_ns
        if select is None:
            return result  # deck selection captured at game level
        recorder.record_decision(player_index=player_index, seat=seat, agent_def=agent_def,
                                 obs_snapshot=snapshot, result=result,
                                 latency_ns=latency_ns, ts_ns=ts_ns)
        return result

    return wrapped

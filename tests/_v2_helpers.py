"""Shared synthetic-record builders for schema-v2 tests (not a test module)."""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_schema import SCHEMA_VERSION, seed_metadata


def decision_obs(num_options, min_count, max_count, context):
    """A full observation dict accepted by to_observation_class / the safe agent."""
    return {
        "select": {
            "type": 1,
            "context": context,
            "minCount": min_count,
            "maxCount": max_count,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": [{"type": 1, "index": i} for i in range(num_options)],
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "logs": [],
        "current": None,
    }


def run_metadata_record(run_id="run_test"):
    return {
        "schema_version": SCHEMA_VERSION, "record_type": "run_metadata", "run_id": run_id,
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "git": {"commit": "deadbeef", "branch": "test", "dirty": False},
        "capture": {"implementation_sha256": "x", "command": "test", "compression": "none+gzip"},
        "environment": {"python_version": "3.13.0"},
        "engine": {"path": "starter_kit/libcg.so", "sha256": "y", "size_bytes": 1},
    }


def game_start_record(run_id="run_test", game_id="g0", seq=1):
    return {
        "schema_version": SCHEMA_VERSION, "record_type": "game_start",
        "record_id": f"{run_id}:{seq:08d}", "run_id": run_id, "game_id": game_id,
        "cohort": "unit", "seat_agent_ids": {"0": "safe_agent", "1": "safe_agent"},
        "seat_deck_ids": {"0": "sha256:d", "1": "sha256:d"},
        "seed": seed_metadata(runner_seed=1, opponent_policy_seed=2, requested_engine_seed=1),
    }


def decision_record(num_options, lo, hi, ctx, selected, *, run_id="run_test", game_id="g0",
                    decision_index=0, seq=2, agent_id="safe_agent",
                    decision_source="fallback", used_fallback=True,
                    fallback_reason="no_strategy_policy_configured", corrupt=None):
    obs = decision_obs(num_options, lo, hi, ctx)
    rec = {
        "schema_version": SCHEMA_VERSION, "record_type": "decision",
        "record_id": f"{run_id}:{seq:08d}", "run_id": run_id, "game_id": game_id,
        "decision_index": decision_index, "player_index": 0, "seat": 0, "agent_id": agent_id,
        "decision_source": decision_source, "used_fallback": used_fallback,
        "fallback_reason": fallback_reason, "timestamp_monotonic_ns": 1, "policy_latency_ns": 1000,
        "observation": obs, "select_context": ctx, "context_name": "MAIN",
        "min_count": lo, "max_count": hi, "legal_option_count": num_options,
        "legal_option_metadata": obs["select"]["option"], "selected_indices": selected,
        "validation_status": "valid",
    }
    if corrupt:
        rec.update(corrupt)
    return rec


def terminal_record(run_id="run_test", game_id="g0", seq=3, decisions_by_player=None):
    return {
        "schema_version": SCHEMA_VERSION, "record_type": "game_terminal",
        "record_id": f"{run_id}:{seq:08d}", "run_id": run_id, "game_id": game_id,
        "cohort": "unit", "seed": seed_metadata(runner_seed=1, opponent_policy_seed=2, requested_engine_seed=1),
        "seat_agent_ids": {"0": "safe_agent", "1": "safe_agent"},
        "terminal_type": "normal_win", "winner": 0, "loser": 1, "draw": False,
        "timeout_player": None, "error_player": None, "error": None,
        "statuses": ["DONE", "DONE"], "rewards": [1, -1],
        "decisions_by_player": decisions_by_player or {"0": 1},
        "fallback_by_player": {"0": 1}, "invalid_selection_count": 0, "game_duration_s": 0.01,
    }

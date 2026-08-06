"""Minimal replay-agent registry (c004 Phase 0 amendment #3).

Semantic replay must verify a recorded agent's identity, version, and source
hashes against the *current* implementation before invoking it. This registry
maps ``agent_id`` -> current lineage + callable + a deterministic flag, and
``resolve`` returns a status so the validator can:
  - OK: invoke the current callable (hashes match);
  - HASH_MISMATCH: refuse — recorded code differs from current, mark unavailable;
  - UNREGISTERED: no current implementation for this agent_id;
  - STOCHASTIC: agent is not deterministically replayable (e.g. random baseline).

This is intentionally minimal — not a general plugin framework.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from cg.agents import random_baseline_definition, safe_agent_definition

OK = "ok"
HASH_MISMATCH = "hash_mismatch"
UNREGISTERED = "unregistered"
STOCHASTIC = "stochastic_not_replayable"


def _hash_map(lineage: Dict[str, Any]) -> Dict[str, Any]:
    return {sf.get("path"): sf.get("sha256") for sf in (lineage or {}).get("source_files", [])}


def build_registry(repo_root: str) -> Dict[str, Dict[str, Any]]:
    """Default registry for known deterministic/stochastic agents."""
    safe = safe_agent_definition(repo_root)
    # The random baseline is registered so replay can classify it STOCHASTIC
    # (not "unavailable"); its callable is never invoked for replay.
    rnd = random_baseline_definition(repo_root, seed=0, deck=[0] * 60)
    return {
        "safe_agent": {"lineage": safe.lineage(), "deterministic": True, "callable": safe},
        "random_baseline": {"lineage": rnd.lineage(), "deterministic": False, "callable": None},
    }


def resolve(registry: Dict[str, Dict[str, Any]], agent_id: str,
            recorded_lineage: Optional[Dict[str, Any]]) -> Tuple[str, Optional[Callable]]:
    """Return ``(status, callable_or_None)`` for replaying ``agent_id``.

    ``recorded_lineage`` is the run_metadata.agents[agent_id] entry from the file.
    """
    entry = registry.get(agent_id)
    if entry is None:
        return UNREGISTERED, None
    if not entry.get("deterministic"):
        return STOCHASTIC, None
    current = entry["lineage"]
    if not recorded_lineage:
        return HASH_MISMATCH, None
    if recorded_lineage.get("agent_version") != current.get("agent_version"):
        return HASH_MISMATCH, None
    if _hash_map(recorded_lineage) != _hash_map(current):
        return HASH_MISMATCH, None
    return OK, entry["callable"]

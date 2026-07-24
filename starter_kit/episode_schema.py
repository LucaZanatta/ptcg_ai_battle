"""Schema-v2 lineage, canonical deck registry, and terminal classification.

Schema v2 makes each capture self-describing: run/Git/capture/environment/engine
provenance, order-independent deck identity, honest seed semantics, and terminal
classification derived from the *final* environment state. Pure/JSON-only; no
pickle. All hashes are sha256.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = (1, 2)

# Structured decision sources (§7.4).
DECISION_SOURCES = (
    "forced", "rule", "heuristic", "search", "model", "fallback",
    "random_baseline", "unknown",
)

# Terminal classifications (§7.10).
TERMINAL_TYPES = (
    "normal_win", "draw", "timeout", "agent_error", "environment_error",
    "aborted", "unknown",
)


def sha256_file(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Canonical deck registry (§7.6)
# --------------------------------------------------------------------------

def canonical_deck(cards: List[int], *, source_path: Optional[str] = None,
                   repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Order-independent canonical deck record.

    ``deck_id`` is ``sha256:<hex>`` over the multiset of card IDs (aggregated
    counts sorted by numeric card ID), so line reordering yields the same id and
    a single-card change yields a different id.
    """
    counts = Counter(int(c) for c in cards)
    cards_list = [{"card_id": cid, "count": counts[cid]} for cid in sorted(counts)]
    canonical_repr = ";".join(f"{c['card_id']}:{c['count']}" for c in cards_list)
    deck_id = "sha256:" + sha256_bytes(canonical_repr.encode("utf-8"))
    source = None
    if source_path is not None:
        rel = os.path.relpath(source_path, repo_root) if repo_root else source_path
        source = {"path": rel, "sha256": sha256_file(source_path)}
    return {
        "deck_id": deck_id,
        "card_count": len(cards),
        "distinct_cards": len(cards_list),
        "cards": cards_list,
        "source": source,
    }


# --------------------------------------------------------------------------
# Run-level lineage (§7.2, §7.3)
# --------------------------------------------------------------------------

def _git(args: List[str], repo_root: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", repo_root, *args], capture_output=True,
                             text=True, timeout=15)
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:
        return None


def collect_git_info(repo_root: str) -> Dict[str, Any]:
    commit = _git(["rev-parse", "HEAD"], repo_root)
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    # dirty ignores untracked files (results/external assets do not count).
    porcelain = _git(["status", "--porcelain", "--untracked-files=no"], repo_root)
    dirty = bool(porcelain) if porcelain is not None else None
    return {"commit": commit, "branch": branch, "dirty": dirty}


def collect_environment() -> Dict[str, Any]:
    try:
        import kaggle_environments
        ke_version = getattr(kaggle_environments, "__version__", None)
    except Exception:
        ke_version = None
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "kaggle_environments_version": ke_version,
    }


def collect_engine_info(engine_path: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    rel = os.path.relpath(engine_path, repo_root) if repo_root else engine_path
    return {
        "path": rel,
        "sha256": sha256_file(engine_path),
        "size_bytes": (os.path.getsize(engine_path) if os.path.isfile(engine_path) else None),
    }


def source_files_lineage(paths: List[str], repo_root: str) -> List[Dict[str, Any]]:
    out = []
    for p in paths:
        ap = os.path.join(repo_root, p) if not os.path.isabs(p) else p
        out.append({"path": os.path.relpath(ap, repo_root), "sha256": sha256_file(ap)})
    return out


def implementation_sha256(paths: List[str], repo_root: str) -> str:
    """Combined hash of capture-critical source files (order-independent)."""
    h = hashlib.sha256()
    for p in sorted(paths):
        ap = os.path.join(repo_root, p) if not os.path.isabs(p) else p
        h.update((os.path.relpath(ap, repo_root) + "\n").encode("utf-8"))
        h.update(((sha256_file(ap) or "MISSING") + "\n").encode("utf-8"))
    return h.hexdigest()


def seed_metadata(*, runner_seed: Optional[int], opponent_policy_seed: Optional[int],
                  requested_engine_seed: Optional[int]) -> Dict[str, Any]:
    """Honest seed semantics (§7.5). Engine RNG is never claimed controlled."""
    return {
        "runner_seed": runner_seed,
        "opponent_policy_seed": opponent_policy_seed,
        "requested_engine_seed": requested_engine_seed,
        "engine_rng_controlled": False,
        "engine_rng_note": (
            "cabt libcg.so seeds std::mt19937 from std::random_device (OS entropy); "
            "no seed API is exported and configuration.seed does not control the "
            "engine trajectory. Repeated requested_engine_seed does NOT reproduce "
            "identical games."
        ),
    }


# --------------------------------------------------------------------------
# Terminal classification (§7.10) — pure function of the FINAL state.
# --------------------------------------------------------------------------

def classify_terminal(statuses: List[str], rewards: List[Any], *,
                      error: Optional[str] = None,
                      exception: Optional[str] = None) -> Dict[str, Any]:
    """Classify a terminal from final per-player statuses/rewards + errors.

    Does not inspect any non-final step. Returns structured terminal fields.
    """
    result = {
        "terminal_type": "unknown", "winner": None, "loser": None, "draw": False,
        "timeout_player": None, "error_player": None, "error": error,
        "statuses": list(statuses), "rewards": list(rewards),
    }
    if exception:
        result["terminal_type"] = "environment_error"
        result["error"] = exception
        return result

    def _find(status):
        for i, s in enumerate(statuses):
            if s == status:
                return i
        return None

    timeout_i = _find("TIMEOUT")
    if timeout_i is not None:
        result["terminal_type"] = "timeout"
        result["timeout_player"] = timeout_i
        return result
    err_i = _find("ERROR")
    inv_i = _find("INVALID")
    if err_i is not None or inv_i is not None:
        result["terminal_type"] = "agent_error"
        result["error_player"] = err_i if err_i is not None else inv_i
        return result
    if all(s == "DONE" for s in statuses) and len(statuses) == 2:
        r0, r1 = (rewards + [None, None])[:2]
        if r0 == r1:
            result["terminal_type"] = "draw"
            result["draw"] = True
        else:
            winner = 0 if (r0 or 0) > (r1 or 0) else 1
            result["terminal_type"] = "normal_win"
            result["winner"] = winner
            result["loser"] = 1 - winner
        return result
    return result

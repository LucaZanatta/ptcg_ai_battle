"""Frozen competitive candidates for the c004 gauntlet (NO strategic modification).

Four complete deck-agent pairs over a policy x deck factorial — the only complete
baselines available locally (the repo/starter kit ship no strategic agents):

  det_starter    : deterministic "first maxCount" policy + starter deck.csv
  det_cabt       : deterministic "first maxCount" policy + cabt built-in deck
  random_starter : uniform random legal policy         + starter deck.csv
  random_cabt    : uniform random legal policy         + cabt built-in deck

Transparency: the two deterministic candidates share IDENTICAL agent source
(only the deck differs); likewise the two random candidates. The material axes
are policy (deterministic vs stochastic) and deck (starter vs cabt) — both part
of candidate identity per the completeness definition. No candidate's strategy
or deck is modified by this contract; only deck plumbing and a per-game seed for
the stochastic policy (allowed compatibility adaptations) are applied.

Policies here are deliberately re-implemented locally (not imported from
safe_policy) so each candidate's adapter source hash is self-contained and
meaningful for freezing.
"""

from __future__ import annotations

import ast
import os
import random
from typing import Any, Dict, List, Optional

from cg.agents import AgentDefinition
from cg.episode_schema import canonical_deck, sha256_file

_THIS = os.path.abspath(__file__)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(_THIS))


def _starter_deck(repo_root: str):
    path = os.path.join(repo_root, "starter_kit", "deck.csv")
    with open(path, "r", encoding="utf-8") as fh:
        deck = [int(x) for x in fh if x.strip()]
    return deck, path


def _cabt_source(repo_root: str) -> Optional[str]:
    """Locate the installed cabt env source that defines the built-in deck."""
    try:
        import kaggle_environments as ke
        return os.path.join(os.path.dirname(ke.__file__), "envs", "cabt", "cabt.py")
    except Exception:
        return None


def _cabt_deck(repo_root: str):
    src_path = _cabt_source(repo_root)
    if not src_path or not os.path.isfile(src_path):
        return None, None
    with open(src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "deck" for t in node.targets):
            return list(ast.literal_eval(node.value)), src_path
    return None, src_path


# ---- policies (self-contained; no strategic logic) -----------------------

def _deterministic_first(select: Dict[str, Any]) -> List[int]:
    return list(range(select["maxCount"]))


class CandidateAgent(AgentDefinition):
    """AgentDefinition adapter for a candidate: returns its own deck at deck
    selection, applies its (deterministic or random) policy otherwise."""

    def __init__(self, spec: Dict[str, Any], repo_root: str, seed: Optional[int]):
        super().__init__(agent_id=spec["candidate_id"], agent_version=spec["candidate_version"],
                         policy_type=spec["policy_type"], source_paths=["starter_kit/candidates.py"],
                         configuration={"deck_id": spec["deck"]["deck_id"], "seed": seed},
                         policy=self._run, repo_root=repo_root)
        self._deck = spec["_deck_list"]
        self._deterministic = spec["deterministic"]
        self._rng = random.Random(seed) if not spec["deterministic"] else None

    def _run(self, obs: Any) -> List[int]:
        select = obs["select"]
        if select is None:
            return list(self._deck)
        if self._deterministic:
            return _deterministic_first(select)
        return self._rng.sample(range(len(select["option"])), select["maxCount"])

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        if self._deterministic:
            return {"decision_source": "fallback", "used_fallback": True,
                    "fallback_reason": "no_strategy_policy_configured"}
        return {"decision_source": "random_baseline", "used_fallback": False, "fallback_reason": None}


def get_candidate_specs(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    repo_root = repo_root or _repo_root()
    starter_deck, starter_path = _starter_deck(repo_root)
    cabt_deck, cabt_path = _cabt_deck(repo_root)
    adapter_sha = sha256_file(_THIS)

    decks = {
        "starter": {"list": starter_deck,
                    "canonical": canonical_deck(starter_deck, source_path=starter_path, repo_root=repo_root),
                    "source": {"kind": "starter_kit", "path": os.path.relpath(starter_path, repo_root),
                               "sha256": sha256_file(starter_path)}},
        "cabt": {"list": cabt_deck,
                 "canonical": (canonical_deck(cabt_deck, repo_root=repo_root) if cabt_deck else None),
                 "source": {"kind": "kaggle_environments_cabt_builtin",
                            "path": (os.path.relpath(cabt_path, repo_root) if cabt_path and cabt_path.startswith(repo_root) else cabt_path),
                            "sha256": (sha256_file(cabt_path) if cabt_path else None)}},
    }

    specs = []
    for cid, policy, deterministic, deck_name, source in [
        ("det_starter", "deterministic_first", True, "starter", "current_safe_baseline_policy (c001) on starter deck"),
        ("det_cabt", "deterministic_first", True, "cabt", "official cabt 'first' policy on cabt built-in deck"),
        ("random_starter", "uniform_random_legal", False, "starter", "c002/c003 random baseline policy on starter deck"),
        ("random_cabt", "uniform_random_legal", False, "cabt", "official cabt 'random' policy on cabt built-in deck"),
    ]:
        d = decks[deck_name]
        specs.append({
            "candidate_id": cid,
            "candidate_version": "c004.1",
            "policy_type": policy,
            "deterministic": deterministic,
            "deck_name": deck_name,
            "deck": d["canonical"],
            "_deck_list": d["list"],
            "deck_source": d["source"],
            "agent_source": {"path": os.path.relpath(_THIS, repo_root), "sha256": adapter_sha},
            "adapter_source_sha256": adapter_sha,
            "attribution": source,
            "runnable": d["list"] is not None,
        })
    return specs


def make_agent(candidate_id: str, repo_root: Optional[str] = None, seed: Optional[int] = None) -> CandidateAgent:
    repo_root = repo_root or _repo_root()
    spec = next(s for s in get_candidate_specs(repo_root) if s["candidate_id"] == candidate_id)
    return CandidateAgent(spec, repo_root, seed)


def freeze_hashes(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Freeze record: agent/adapter source hash, deck_id, deck source hash,
    policy_type, configuration — per candidate."""
    repo_root = repo_root or _repo_root()
    out = {}
    for s in get_candidate_specs(repo_root):
        out[s["candidate_id"]] = {
            "agent_source_sha256": s["adapter_source_sha256"],
            "adapter_source_sha256": s["adapter_source_sha256"],
            "deck_id": (s["deck"] or {}).get("deck_id"),
            "deck_source_sha256": s["deck_source"]["sha256"],
            "policy_type": s["policy_type"],
            "deterministic": s["deterministic"],
        }
    return out

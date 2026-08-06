"""Loader for acquired strategic teacher candidates (c005), behavior-preserving.

Each official-sample teacher is a rule-based policy that keeps module-level state
(turn counters, attack plan, ability flags) and does NOT reset on deck selection.
So this loader creates a FRESH module instance **per game per seat**, with the
teacher's own 60-card deck baked in at import (read from its bundled deck.csv).

The third-party teacher source is provided at runtime under a `sources_dir`
(the contract results/, NOT committed). This loader only isolates instances and
reads the bundled deck — it changes no strategy, priority, or deck. The bundled
`cg` SDK is byte-identical to this repo's starter kit, so the repo `cg` is used.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any, Callable, Dict, List, Optional

from cg.episode_schema import canonical_deck, sha256_file

# Registry of admitted strategic teachers. `dir` is the sub-directory under the
# runtime sources_dir; all are official reusable samples except the local-only
# benchmark. Engineering controls (c004 det/random) are NOT teachers.
TEACHERS: Dict[str, Dict[str, Any]] = {
    "dragapult": {"dir": "dragapult", "display_name": "Dragapult ex", "archetype": "spread_setup",
                  "source_type": "official_kaggle_sample",
                  "source_reference": "kaggle:kiyotah/a-sample-rule-based-agent-dragapult-ex-deck",
                  "reuse_classification": "OFFICIAL_REUSABLE", "submission_eligible": True,
                  "policy_type": "rule_based_strategic"},
    "mega_lucario": {"dir": "mega_lucario", "display_name": "Mega Lucario ex", "archetype": "switch_midrange",
                     "source_type": "official_kaggle_sample",
                     "source_reference": "kaggle:kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck",
                     "reuse_classification": "OFFICIAL_REUSABLE", "submission_eligible": True,
                     "policy_type": "rule_based_strategic"},
    "mega_abomasnow": {"dir": "mega_abomasnow", "display_name": "Mega Abomasnow ex", "archetype": "linear_aggro",
                       "source_type": "official_kaggle_sample",
                       "source_reference": "kaggle:kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck",
                       "reuse_classification": "OFFICIAL_REUSABLE", "submission_eligible": True,
                       "policy_type": "rule_based_strategic"},
    "iono": {"dir": "iono", "display_name": "Iono's deck", "archetype": "disruption_control",
             "source_type": "official_kaggle_sample",
             "source_reference": "kaggle:kiyotah/a-sample-rule-based-agent-iono-s-deck",
             "reuse_classification": "OFFICIAL_REUSABLE", "submission_eligible": True,
             "policy_type": "rule_based_strategic"},
}

_load_counter = [0]


def _teacher_dir(candidate_id: str, sources_dir: str) -> str:
    return os.path.join(sources_dir, TEACHERS[candidate_id]["dir"])


class LoadedTeacher:
    """A fresh instance of a teacher: a callable agent + provenance for capture."""

    def __init__(self, candidate_id: str, agent_callable: Callable[[Any], List[int]], deck: List[int]):
        self.agent_id = candidate_id
        self.candidate_id = candidate_id
        self._agent = agent_callable
        self.deck = deck
        self.meta = TEACHERS[candidate_id]

    def __call__(self, obs: Any) -> List[int]:
        return self._agent(obs)

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        # Strategic rule-based policy: decisions are rule-sourced, not fallbacks.
        return {"decision_source": "rule", "used_fallback": False, "fallback_reason": None}


def make_fresh(candidate_id: str, sources_dir: str) -> LoadedTeacher:
    """Load a FRESH module instance of the teacher (state-isolated), deck baked in."""
    tdir = os.path.abspath(_teacher_dir(candidate_id, sources_dir))
    main_path = os.path.join(tdir, "main.py")
    _load_counter[0] += 1
    modname = f"teacher_{candidate_id}_{_load_counter[0]}"
    old = os.getcwd()
    os.chdir(tdir)  # so the teacher's relative deck.csv read resolves at import
    try:
        spec = importlib.util.spec_from_file_location(modname, main_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # bakes my_deck at import; state starts fresh
    finally:
        os.chdir(old)
    deck = mod.agent({"select": None, "logs": [], "current": None})
    return LoadedTeacher(candidate_id, mod.agent, list(deck))


def read_deck(candidate_id: str, sources_dir: str) -> List[int]:
    path = os.path.join(_teacher_dir(candidate_id, sources_dir), "deck.csv")
    with open(path, "r", encoding="utf-8") as fh:
        return [int(x) for x in fh if x.strip()]


def canonical_deck_record(candidate_id: str, sources_dir: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    deck = read_deck(candidate_id, sources_dir)
    path = os.path.join(_teacher_dir(candidate_id, sources_dir), "deck.csv")
    return canonical_deck(deck, source_path=path, repo_root=repo_root)


def freeze_hashes(sources_dir: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    out = {}
    for cid in TEACHERS:
        tdir = _teacher_dir(cid, sources_dir)
        main_sha = sha256_file(os.path.join(tdir, "main.py"))
        deck_sha = sha256_file(os.path.join(tdir, "deck.csv"))
        deck_rec = canonical_deck_record(cid, sources_dir, repo_root)
        out[cid] = {"main_sha256": main_sha, "deck_sha256": deck_sha,
                    "deck_id": deck_rec["deck_id"], "policy_type": TEACHERS[cid]["policy_type"],
                    "reuse_classification": TEACHERS[cid]["reuse_classification"]}
    return out


def agent_lineage(candidate_id: str, sources_dir: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    m = TEACHERS[candidate_id]
    tdir = _teacher_dir(candidate_id, sources_dir)
    return {"agent_id": candidate_id, "agent_version": m["source_reference"],
            "policy_type": m["policy_type"],
            "source_files": [{"path": "main.py", "sha256": sha256_file(os.path.join(tdir, "main.py"))}]}

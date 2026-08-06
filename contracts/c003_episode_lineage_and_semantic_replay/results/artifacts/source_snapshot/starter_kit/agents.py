"""Agent definitions with lineage and decision provenance (schema v2 §7.3/§7.4).

An ``AgentDefinition`` bundles a policy callable with its identity
(agent_id/version/policy_type), source-file hashes, configuration, and a
``classify_decision`` method that reports the *structured decision source* for a
given decision. Crucially, ``decision_source``/``used_fallback`` are properties
of the policy, NOT of the seat / player index — so a future strategic agent that
occasionally falls back is represented correctly.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional

from cg.main import agent as _safe_agent
from cg.episode_schema import source_files_lineage


class AgentDefinition:
    def __init__(self, *, agent_id: str, agent_version: str, policy_type: str,
                 source_paths: List[str], configuration: Dict[str, Any],
                 policy: Callable[[Any], List[int]], repo_root: str):
        self.agent_id = agent_id
        self.agent_version = agent_version
        self.policy_type = policy_type
        self.source_paths = source_paths
        self.configuration = configuration
        self._policy = policy
        self._repo_root = repo_root

    def __call__(self, obs: Any) -> List[int]:
        return self._policy(obs)

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        """Structured decision source. Overridden per policy; never seat-based."""
        raise NotImplementedError

    def lineage(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "policy_type": self.policy_type,
            "source_files": source_files_lineage(self.source_paths, self._repo_root),
            "configuration": self.configuration,
        }


class SafeAgent(AgentDefinition):
    """The c001 deterministic legal fallback. Every decision is a fallback: it has
    no strategy layer, so it always selects the first maxCount legal options."""

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        # Property of THIS policy: it has no strategy stage, so the source is the
        # deterministic legal fallback for every decision. A future mixed policy
        # would instead return e.g. "rule"/"search" when it does NOT fall back.
        return {
            "decision_source": "fallback",
            "used_fallback": True,
            "fallback_reason": "no_strategy_policy_configured",
        }


class RandomBaselineAgent(AgentDefinition):
    """Uniform-random legal opponent (isolated RNG). Never a fallback."""

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        return {
            "decision_source": "random_baseline",
            "used_fallback": False,
            "fallback_reason": None,
        }


def safe_agent_definition(repo_root: str) -> SafeAgent:
    return SafeAgent(
        agent_id="safe_agent",
        agent_version="c001.1",
        policy_type="deterministic_safe_fallback",
        source_paths=["starter_kit/main.py", "starter_kit/safe_policy.py"],
        configuration={},
        policy=_safe_agent,
        repo_root=repo_root,
    )


def make_random_baseline(seed: int, deck: List[int]) -> Callable[[Any], List[int]]:
    rng = random.Random(seed)

    def policy(obs: Any) -> List[int]:
        select = obs["select"]
        if select is None:
            return deck
        return rng.sample(range(len(select["option"])), select["maxCount"])

    return policy


def random_baseline_definition(repo_root: str, *, seed: int, deck: List[int]) -> RandomBaselineAgent:
    return RandomBaselineAgent(
        agent_id="random_baseline",
        agent_version="c002.1",
        policy_type="uniform_random_legal",
        source_paths=["starter_kit/agents.py"],
        configuration={"opponent_policy_seed": seed},
        policy=make_random_baseline(seed, deck),
        repo_root=repo_root,
    )

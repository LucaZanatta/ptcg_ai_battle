"""c019 Branch A prerequisite — branch-local memory for the stateful official baseline.

c019 exists because c018 discovered that overriding a stateful scripted agent destroys it: the
official Mega Lucario agent keeps `plan`, `pre_turn` and `ability_used` in module globals and its
recommendations assume its own previous recommendations were executed. Inside an MCTS tree the
problem is worse than in c018's linear wrapper — sibling branches would share one global plan, so
exploring child B would corrupt the memory that child A's subtree was built from.

METHOD_FIDELITY A: "Refactors any stateful baseline/rollout policy into explicit branch-local
memory." That is what this module does, without editing the official agent:

  * the agent is loaded once, from the c016 artifact, unmodified;
  * `PolicyMemory` is a snapshot of exactly the mutable globals it declares;
  * `act()` installs a memory, calls the agent, and returns the resulting memory — pure from the
    caller's view, so a node can hand each child its own forked copy.

Cloning a snapshot is correct here precisely BECAUSE the agent's state is small and explicit. If
it ever grows a mutable global not listed in `STATE_GLOBALS`, `verify_state_coverage()` fails
rather than letting a branch silently share state.
"""

from __future__ import annotations

import copy
import importlib.util
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

BASELINE_DIR = os.path.join(
    _REPO, "contracts", "c016_public_agent_reproduction_gauntlet_and_champion_submission",
    "results", "artifacts", "candidates", "official_mega_lucario")
BASELINE_MAIN = os.path.join(BASELINE_DIR, "main.py")

# The exact mutable module globals the official agent declares. Derived from its own `global`
# statements, and re-verified at runtime rather than trusted.
STATE_GLOBALS = ("plan", "pre_turn", "ability_used")

_MODULE = None


def baseline_module():
    """Load the official agent once, unmodified, under a private module name.

    The agent resolves `deck.csv` relative to the working directory (falling back to the
    Kaggle runtime path), so it is imported with the cwd set to its own directory. Copying the
    file or editing the path would modify a c016 artifact, which §2 forbids.
    """
    global _MODULE
    if _MODULE is None:
        prev = os.getcwd()
        try:
            os.chdir(BASELINE_DIR)
            spec = importlib.util.spec_from_file_location("c019_official_baseline",
                                                          BASELINE_MAIN)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        finally:
            os.chdir(prev)
        _MODULE = m
    return _MODULE


def verify_state_coverage() -> Dict[str, Any]:
    """Every `global X` the agent declares must be covered by STATE_GLOBALS.

    A new mutable global would otherwise be shared across MCTS branches invisibly — the same
    class of defect this module exists to prevent.
    """
    src = open(BASELINE_MAIN, encoding="utf-8-sig").read()
    declared = sorted(set(re.findall(r"^\s*global\s+([A-Za-z_][A-Za-z0-9_]*)", src, re.M)))
    missing = [d for d in declared if d not in STATE_GLOBALS]
    extra = [s for s in STATE_GLOBALS if s not in declared]
    return {"declared_globals": declared, "tracked": list(STATE_GLOBALS),
            "untracked_mutable_globals": missing, "tracked_but_not_declared": extra,
            "covered": not missing}


@dataclass
class PolicyMemory:
    """Explicit branch-local state. Forkable; never shared between sibling branches."""

    values: Dict[str, Any] = field(default_factory=dict)
    depth: int = 0

    def fork(self) -> "PolicyMemory":
        return PolicyMemory(values=copy.deepcopy(self.values), depth=self.depth + 1)

    def summary(self) -> Dict[str, Any]:
        p = self.values.get("plan")
        return {"pre_turn": self.values.get("pre_turn"),
                "ability_used": self.values.get("ability_used"),
                "plan": None if p is None else
                        {k: getattr(p, k, None) for k in
                         ("attacker", "target", "attack_index", "remain_hp", "energy")},
                "depth": self.depth}


class BranchLocalBaseline:
    """The official agent as a pure function of (observation, memory)."""

    def __init__(self):
        self.m = baseline_module()
        self.calls = 0

    def initial_memory(self) -> PolicyMemory:
        """A fresh game's state, captured from the module's own initial values."""
        mod = self.m
        return PolicyMemory(values={
            "plan": copy.deepcopy(getattr(mod, "plan", None)),
            "pre_turn": 0,
            "ability_used": False,
        })

    def _install(self, mem: PolicyMemory):
        for k in STATE_GLOBALS:
            if k in mem.values:
                setattr(self.m, k, copy.deepcopy(mem.values[k]))

    def _capture(self, depth: int) -> PolicyMemory:
        return PolicyMemory(values={k: copy.deepcopy(getattr(self.m, k, None))
                                    for k in STATE_GLOBALS}, depth=depth)

    def act(self, obs_dict: dict, mem: Optional[PolicyMemory] = None
            ) -> Tuple[List[int], PolicyMemory]:
        """Return the baseline's action and the memory produced by taking it.

        The input memory is not mutated: callers hold one memory per branch, and a child gets
        the memory produced by the action ACTUALLY executed on that branch.
        """
        mem = mem or self.initial_memory()
        self._install(mem)
        action = self.m.agent(obs_dict)
        self.calls += 1
        return list(action), self._capture(mem.depth)

    def act_canonical(self, obs_dict: dict, sel: Any,
                      mem: Optional[PolicyMemory] = None
                      ) -> Tuple[List[K.CanonicalOption], PolicyMemory]:
        action, nxt = self.act(obs_dict, mem)
        opts = K.canonical_options(sel)
        chosen = [opts[i] for i in action if 0 <= i < len(opts)]
        return chosen, nxt

    def observe_executed(self, obs_dict: dict, executed: List[int],
                         mem: PolicyMemory) -> PolicyMemory:
        """Advance branch memory for an action the SEARCH chose, not the baseline.

        METHOD_FIDELITY A: "Search overrides must update branch memory according to the action
        actually executed." The agent has no API for "I did something else", so the honest
        thing this can do is record the divergence in the branch's own memory and let the
        rollout continue from a memory that is at least not silently attributed to a plan the
        baseline never made.
        """
        mem = mem.fork()
        p = mem.values.get("plan")
        if p is not None and hasattr(p, "attacker"):
            base_action, _ = self.act(obs_dict, mem)
            if list(base_action) != list(executed):
                # the baseline's cached attack plan assumed its own move was played; it is no
                # longer a description of this branch and must not be reused as one
                for k in ("attacker", "target", "attack_index", "remain_hp"):
                    if hasattr(p, k):
                        setattr(p, k, -1)
                if hasattr(p, "energy"):
                    p.energy = False
                mem.values["diverged"] = True
        return mem

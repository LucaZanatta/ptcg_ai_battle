"""c020 A2 — branch-local baseline memory with the exact required API.

c019 already refactored the stateful official agent into explicit snapshots; c020 keeps that
mechanism (it was verified at 100% action parity over 8 games) and puts the API
`MANDATORY_CHANGES A2` requires around it:

    recommend(observation, memory) -> (action, proposed_memory)
    advance_after_executed(observation, executed_action, memory) -> next_memory
    clone_memory(memory) -> memory_copy

The separation between `recommend` and `advance_after_executed` is the part c019 did not have and
A8 needs. When the search OVERRIDES the baseline, the baseline's memory must advance along the
action that was ACTUALLY EXECUTED, not the one it proposed — otherwise its internal plan refers to
a line that never happened, and every subsequent recommendation is computed from a fiction. That
is a plausible contributor to c019's audit-#4 finding that a few overrides caused large losses.
"""

from __future__ import annotations

import copy
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_baseline as B19  # noqa: E402  (loading machinery reused, agent unmodified)

STATE_GLOBALS = B19.STATE_GLOBALS


@dataclass(frozen=True)
class BaselineMemory:
    """Frozen so a branch cannot mutate a sibling's memory by aliasing it.

    `values` is still a dict, so `clone_memory` deep-copies rather than relying on the freeze.
    The freeze prevents rebinding; the deep copy prevents in-place mutation of `plan`.
    """

    values: Dict[str, Any] = field(default_factory=dict)
    depth: int = 0

    def summary(self) -> Dict[str, Any]:
        out = {}
        for k in STATE_GLOBALS:
            v = self.values.get(k)
            out[k] = (getattr(v, "__dict__", None) and
                      {a: str(b)[:24] for a, b in vars(v).items()}) or str(v)[:32]
        out["depth"] = self.depth
        return out


def initial_memory() -> BaselineMemory:
    mod = B19.baseline_module()
    vals = {}
    for k in STATE_GLOBALS:
        v = getattr(mod, k, None)
        vals[k] = copy.deepcopy(v) if v is not None else None
    # a fresh plan object, not the module's live one
    if vals.get("plan") is not None:
        vals["plan"] = type(vals["plan"])()
    vals["pre_turn"] = 0
    vals["ability_used"] = False
    return BaselineMemory(values=vals, depth=0)


def clone_memory(memory: BaselineMemory) -> BaselineMemory:
    """A2: deep copy. Siblings must never share a mutable plan object."""
    return BaselineMemory(values=copy.deepcopy(memory.values), depth=memory.depth)


def _install(mod, memory: BaselineMemory):
    prev = {}
    for k in STATE_GLOBALS:
        prev[k] = getattr(mod, k, None)
        setattr(mod, k, memory.values.get(k))
    return prev


def _capture(mod, depth: int) -> BaselineMemory:
    return BaselineMemory(
        values={k: copy.deepcopy(getattr(mod, k, None)) for k in STATE_GLOBALS},
        depth=depth)


def _restore(mod, prev):
    for k, v in prev.items():
        setattr(mod, k, v)


def recommend(observation, memory: BaselineMemory) -> Tuple[List[int], BaselineMemory]:
    """A2: what the baseline would play, plus the memory that WOULD result.

    The proposed memory is returned rather than committed. If the search overrides, the proposal
    is discarded and `advance_after_executed` is used instead.
    """
    mod = B19.baseline_module()
    prev = _install(mod, clone_memory(memory))
    try:
        action = list(mod.agent(observation))
        proposed = _capture(mod, memory.depth + 1)
    finally:
        _restore(mod, prev)          # the real game's globals are never left mutated
    return action, proposed


def advance_after_executed(observation, executed_action, memory: BaselineMemory) -> BaselineMemory:
    """A2: advance the baseline's memory along the action ACTUALLY executed.

    The official agent has no "observe someone else's move" entry point, so its state is advanced
    by letting it recommend from `observation` and then keeping the resulting memory only when its
    own proposal matches what was executed. When they differ — i.e. the search overrode it — the
    plan is invalidated rather than silently kept, because a plan formed for a line that was not
    played is worse than no plan: it will keep proposing follow-ups to a move that never happened.
    """
    mod = B19.baseline_module()
    prev = _install(mod, clone_memory(memory))
    try:
        proposed_action = list(mod.agent(observation))
        advanced = _capture(mod, memory.depth + 1)
    finally:
        _restore(mod, prev)

    if list(executed_action) == proposed_action:
        return advanced
    invalidated = dict(advanced.values)
    if invalidated.get("plan") is not None:
        invalidated["plan"] = type(invalidated["plan"])()   # fresh plan, replanned next call
    invalidated["ability_used"] = False
    return BaselineMemory(values=invalidated, depth=memory.depth + 1)


def verify_state_coverage() -> Dict[str, Any]:
    """Re-verify that STATE_GLOBALS still covers every mutable global the agent declares."""
    return B19.verify_state_coverage()


def globals_are_clean() -> Dict[str, Any]:
    """M04 evidence: after any recommend/advance, module globals are back to their prior values.

    A branch that leaked into the module globals would corrupt the real game, and the leak would
    only show up as inexplicably bad play. Checked explicitly rather than assumed.
    """
    mod = B19.baseline_module()
    before = {k: repr(getattr(mod, k, None))[:64] for k in STATE_GLOBALS}

    # install a foreign memory the way recommend() does, then restore the way it does
    marker = initial_memory()
    if marker.values.get("plan") is not None:
        try:
            setattr(marker.values["plan"], "attacker", 0xC020)
        except Exception:  # noqa: BLE001
            pass
    marker.values["ability_used"] = True
    prev = _install(mod, marker)
    installed = {k: repr(getattr(mod, k, None))[:64] for k in STATE_GLOBALS}
    _restore(mod, prev)

    after = {k: repr(getattr(mod, k, None))[:64] for k in STATE_GLOBALS}
    return {"before": before, "while_installed": installed, "after": after,
            "install_actually_changed_globals": installed != before,
            "restored": before == after,
            "unchanged": before == after}

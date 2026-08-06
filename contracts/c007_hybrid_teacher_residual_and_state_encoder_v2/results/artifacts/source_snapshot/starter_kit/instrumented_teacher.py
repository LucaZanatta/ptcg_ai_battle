"""c007 AC-04/§8: behavior-equivalent instrumented copy of the frozen Dragapult teacher.

Loads a FRESH module instance of the instrumented teacher copy per game per seat,
mirroring ``cg.teachers.make_fresh`` (unique module name, ``os.chdir`` so the baked
``deck.csv`` resolves at import, deck-extraction call on load). The instrumented copy
is byte-identical to the frozen ``main.py`` except for ONE side-effect-free statement
that exposes the local decision internals as ``mod._c007_capture``.

After each real decision (``select`` is not ``None``) the wrapper snapshots the
teacher's PERSISTENT planning globals plus the captured locals as privileged plan
labels. Snapshots are READ-ONLY deep copies taken AFTER ``agent()`` returns, so the
shipped decision logic is unchanged and behavior-equivalence to the frozen teacher
holds by construction (proven by ``tools/c007_teacher_parity.py``). These labels may
be auxiliary training targets ONLY; they are never runtime inputs to the hybrid.

Hazards respected (see AC-04 manifest): ``plan_*.counter`` is deep-copied because it
is aliased (main.py L284) and can be stale; ``card_counts`` is snapshotted via
``dict(...)`` which iterates existing keys only (never probes a missing key, which
would mutate the ``defaultdict``); the ``select is None`` deck-extraction call is not
snapshotted; teacher loads stay sequential within a process (``os.chdir``).
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any, Dict, List, Optional

# SelectContext.MAIN integer (planner runs only at MAIN); read lazily to avoid a hard
# import at module load in worker processes.
_MAIN_CTX = None


def _main_ctx_value() -> int:
    global _MAIN_CTX
    if _MAIN_CTX is None:
        from cg.api import SelectContext
        _MAIN_CTX = int(SelectContext.MAIN)
    return _MAIN_CTX


# The privileged plan-label schema this wrapper emits per decision.
PLAN_LABEL_FIELDS = [
    "plan_a_attack", "plan_a_counter", "plan_b_attack", "plan_b_counter",
    "use_support", "bench_attacker", "can_switch", "can_attack", "can_main_attack",
    "prize_inference_count", "prize_inference",
    "scores", "argmax_option", "top1_score", "top2_score", "score_margin",
    "prize_diff", "do_switch", "no_draw", "damage", "no_more_dex",
    "plan_recomputed_this_decision", "select_context",
]

_load_counter = [0]


def _obs_context(obs: Any) -> Optional[int]:
    sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
    if sel is None:
        return None
    if isinstance(sel, dict):
        return sel.get("context")
    return getattr(sel, "context", None)


class InstrumentedTeacher:
    """Fresh instrumented teacher instance: callable agent + per-decision plan labels."""

    def __init__(self, candidate_id: str, mod: Any, deck: List[int]):
        self.agent_id = candidate_id
        self.candidate_id = candidate_id
        self._mod = mod
        self.deck = deck
        self.captures: List[Dict[str, Any]] = []
        self.n_decisions = 0

    def __call__(self, obs: Any) -> List[int]:
        ctx = _obs_context(obs)
        action = self._mod.agent(obs)
        if ctx is not None:  # skip the select==None deck-extraction call
            self.captures.append(self._snapshot(ctx, action))
            self.n_decisions += 1
        return action

    def _snapshot(self, ctx: Any, action: List[int]) -> Dict[str, Any]:
        m = self._mod
        cap = getattr(m, "_c007_capture", None) or {}
        scores = list(cap.get("scores", []))
        # top-1/top-2 score margin = the teacher's own confidence / "two meaningful
        # choices" signal, used by AC-07 admission and AC-09 near-threshold capture.
        srt = sorted(scores, reverse=True)
        top1 = srt[0] if srt else None
        top2 = srt[1] if len(srt) > 1 else None
        margin = (top1 - top2) if (top1 is not None and top2 is not None) else None
        pa = m.plan_a
        pb = m.plan_b
        prize = list(m.prize)
        try:
            ctx_i = int(ctx)
        except (TypeError, ValueError):
            ctx_i = ctx
        return {
            "plan_a_attack": int(pa.attack),
            "plan_a_counter": list(pa.counter),
            "plan_b_attack": int(pb.attack),
            "plan_b_counter": list(pb.counter),
            "use_support": int(m.use_support),
            "bench_attacker": bool(m.bench_attacker),
            "can_switch": bool(m.can_switch),
            "can_attack": bool(m.can_attack),
            "can_main_attack": bool(m.can_main_attack),
            "prize_inference_count": len(prize),
            "prize_inference": prize,
            "scores": scores,
            "argmax_option": (int(action[0]) if action else None),
            "top1_score": top1,
            "top2_score": top2,
            "score_margin": margin,
            "prize_diff": cap.get("prize_diff"),
            "do_switch": bool(cap.get("do_switch")) if "do_switch" in cap else None,
            "no_draw": bool(cap.get("no_draw")) if "no_draw" in cap else None,
            "damage": cap.get("damage"),
            "no_more_dex": bool(cap.get("no_more_dex")) if "no_more_dex" in cap else None,
            "plan_recomputed_this_decision": bool(ctx_i == _main_ctx_value()),
            "select_context": ctx_i,
        }

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        return {"decision_source": "rule", "used_fallback": False, "fallback_reason": None}


def make_fresh(instr_dir: str, candidate_id: str = "dragapult") -> InstrumentedTeacher:
    """Load a FRESH instrumented teacher instance (state-isolated, deck baked in).

    ``instr_dir`` holds the instrumented ``main.py`` + ``deck.csv`` copy controlled by
    c007 (results/artifacts/instrumented_teacher).
    """
    tdir = os.path.abspath(instr_dir)
    main_path = os.path.join(tdir, "main.py")
    _load_counter[0] += 1
    modname = f"instr_teacher_{candidate_id}_{_load_counter[0]}"
    old = os.getcwd()
    os.chdir(tdir)  # baked deck.csv read resolves at import
    try:
        spec = importlib.util.spec_from_file_location(modname, main_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old)
    deck = mod.agent({"select": None, "logs": [], "current": None})
    return InstrumentedTeacher(candidate_id, mod, list(deck))

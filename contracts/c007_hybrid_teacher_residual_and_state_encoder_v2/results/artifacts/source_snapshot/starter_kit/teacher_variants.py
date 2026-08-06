"""c007 AC-08 (§12 fallback): controlled deterministic teacher variants.

Each variant is a COPY of the frozen Dragapult teacher that alters exactly ONE
semantic rule — the Phantom Dive spread damage-counter allocation (DAMAGE_COUNTER_ANY,
frozen main.py L703-714) — and is byte-identical everywhere else. A variant is a full
deterministic policy; its improvement over the teacher is measured POLICY-LEVEL by
balanced full-game A/B (never fabricated per-state labels, §12). Variants build from the
frozen source at runtime; the build verifies the change is confined to the intended
block and that the result compiles.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROZEN_MAIN = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                           "results", "artifacts", "frozen_teacher", "main.py")
FROZEN_DECK = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                           "results", "artifacts", "frozen_teacher", "deck.csv")

# Exact anchors copied from frozen main.py (indentation-sensitive).
_ANCHOR_PLAN_B = "                            if index in plan_b.counter:\n"

_ANCHOR_RESET = (
    "    plan_a.attack = -1\n"
    "    plan_b.attack = -1\n"
    "    if not can_main_attack and not (bench_attacker and can_switch):\n"
    "        return\n"
)

_ANCHOR_THRESH = "                                if 210 <= hp <= 200 + remain_damage:\n"

_ANCHOR_BLOCK = (
    "                        else:\n"
    "                            index = o.index + 1\n"
    "                            if index in plan_b.counter:\n"
    "                                score += 100000\n"
    "                            else:\n"
    "                                remain_damage = select.remainDamageCounter * 10\n"
    "                                if 210 <= hp <= 200 + remain_damage:\n"
    "                                    score += 30000\n"
    "                                elif 20 <= hp <= 60 + remain_damage:\n"
    "                                    score += 10000\n"
    "                                elif hp == 10:\n"
    "                                    score -= 100000\n"
)

VARIANTS: Dict[str, Dict[str, Any]] = {
    "V_plan_a": {
        "rule": "spread allocation uses plan_a.counter when the planned main target is a "
                "benched Pokemon (plan_a.attack != 0), matching the ACTUAL attack plan "
                "instead of the active-target plan_b.counter (main.py L705).",
        "anchor": _ANCHOR_PLAN_B,
        "replacement": "                            if index in (plan_a.counter if plan_a.attack != 0 else plan_b.counter):\n",
    },
    "V_reset": {
        "rule": "reset plan_a.counter/plan_b.counter at the start of MAIN planning so a "
                "stale spread allocation from a prior turn can never leak into a later "
                "DAMAGE_COUNTER_ANY (AttackPlan.counter is a class attr never reset; main.py L55/L213-216).",
        "anchor": _ANCHOR_RESET,
        "replacement": (
            "    plan_a.attack = -1\n"
            "    plan_b.attack = -1\n"
            "    plan_a.counter = []\n"
            "    plan_b.counter = []\n"
            "    if not can_main_attack and not (bench_attacker and can_switch):\n"
            "        return\n"
        ),
    },
    "V_thresh": {
        "rule": "correct the DAMAGE_COUNTER_ANY HP-band threshold so targets just above the "
                "200 main-damage line are still prioritised when few counters remain "
                "(main.py L709: 210<=hp<=200+remain becomes 200<hp<=200+max(remain,60)).",
        "anchor": _ANCHOR_THRESH,
        "replacement": "                                if 200 < hp <= 200 + max(remain_damage, 60):\n",
    },
    "V_greedy": {
        "rule": "replace the plan_b/HP-band spread heuristic with a knockout-maximizing "
                "rule computed from the CURRENT board: prioritise targets KO-able by the "
                "remaining counters (weighted by prize value), then near-KO targets, with "
                "plan_b as a small tiebreak (main.py L703-714).",
        "anchor": _ANCHOR_BLOCK,
        "replacement": (
            "                        else:\n"
            "                            remain_damage = select.remainDamageCounter * 10\n"
            "                            index = o.index + 1\n"
            "                            if 0 < hp <= remain_damage:\n"
            "                                score += 60000 + prize_count(card, False) * 8000 - hp\n"
            "                            elif hp <= remain_damage + 100:\n"
            "                                score += 15000 - hp\n"
            "                            if index in plan_b.counter:\n"
            "                                score += 3000\n"
        ),
    },
}

_load_counter = [0]


def build_variant(name: str, out_root: str) -> Dict[str, Any]:
    spec = VARIANTS[name]
    src = open(FROZEN_MAIN).read()
    if src.count(spec["anchor"]) != 1:
        raise ValueError(f"anchor for {name} matched {src.count(spec['anchor'])} times (need 1)")
    out = src.replace(spec["anchor"], spec["replacement"])
    vdir = os.path.join(out_root, name)
    os.makedirs(vdir, exist_ok=True)
    mp = os.path.join(vdir, "main.py")
    open(mp, "w").write(out)
    # deck copy (unchanged)
    import shutil
    shutil.copyfile(FROZEN_DECK, os.path.join(vdir, "deck.csv"))
    py_compile.compile(mp, doraise=True)
    # confined-diff check: only the intended lines changed
    import difflib
    added = [l for l in difflib.unified_diff(src.splitlines(), out.splitlines(), lineterm="", n=0)
             if l.startswith("+") and not l.startswith("+++")]
    removed = [l for l in difflib.unified_diff(src.splitlines(), out.splitlines(), lineterm="", n=0)
               if l.startswith("-") and not l.startswith("---")]
    return {"variant": name, "rule": spec["rule"], "dir": vdir,
            "added_lines": len(added), "removed_lines": len(removed),
            "compiles": True}


class VariantAgent:
    def __init__(self, name: str, mod: Any, deck: List[int]):
        self.agent_id = name
        self._mod = mod
        self.deck = deck

    def __call__(self, obs):
        return self._mod.agent(obs)

    def classify_decision(self, obs, result):
        return {"decision_source": "rule", "used_fallback": False, "fallback_reason": None}


def load_variant(name: str, variants_root: str) -> VariantAgent:
    vdir = os.path.abspath(os.path.join(variants_root, name))
    main_path = os.path.join(vdir, "main.py")
    _load_counter[0] += 1
    modname = f"variant_{name}_{_load_counter[0]}"
    old = os.getcwd()
    os.chdir(vdir)
    try:
        spec = importlib.util.spec_from_file_location(modname, main_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old)
    deck = mod.agent({"select": None, "logs": [], "current": None})
    return VariantAgent(name, mod, list(deck))

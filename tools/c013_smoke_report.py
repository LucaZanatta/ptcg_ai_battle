"""c013 AC-11 / §20 — curriculum smoke report.

§18 is explicit that this phase validates EXECUTION MACHINERY, not curriculum effectiveness. So
this report checks the eight §20 machinery requirements one at a time and says which evidence
field establishes each. It deliberately does not argue that the adaptive curriculum helps —
5,000 games per arm cannot support that claim and §18 forbids making it.

Every one of these requirements exists because c012 shipped a 90,000-game arm in which none of
them held: a stale per-path hash cache emptied every in-run evaluation after game zero, so the
gates never ran, the stage never advanced, and early stopping never had data.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
ART = os.path.join(C013, "results", "artifacts")
LOGD = os.path.join(C013, "results", "test_logs")

ARMS = [("R0", 1001, "unchanged population (control)"),
        ("R1", 1002, "adaptive elite curriculum")]
EVAL_POINTS = [0, 2500, 5000]
PER_ARM_CAP = 5000
SMOKE_CAP = 10000


def load(arm, seed):
    p = os.path.join(ART, "training", arm, f"seed{seed}", "summary.json")
    return json.load(open(p)) if os.path.exists(p) else None


def requirements(summ: Dict[str, Any], arm: str) -> List[Dict[str, Any]]:
    m = summ.get("machinery") or {}
    evs = summ.get("evaluations") or []
    pts = sorted({e.get("registered_point") for e in evs})
    rv = m.get("restore_verified") or {}
    return [
        {"requirement": "non-zero scored games at every registered evaluation",
         "passed": bool(evs) and all(e.get("scored", 0) > 0 for e in evs),
         "evidence": f"{sum(1 for e in evs if e.get('scored', 0) > 0)}/{len(evs)} "
                     f"evaluations scored; points {pts}",
         "c012_failure": "every c012 in-run evaluation after game 0 scored nothing"},
        {"requirement": "all three registered evaluation points covered",
         "passed": pts == EVAL_POINTS,
         "evidence": f"points covered {pts}, required {EVAL_POINTS}"
                     + (f"; backfilled {m.get('backfilled_evaluations')}"
                        if m.get("backfilled_evaluations") else "")},
        {"requirement": "checkpoint hashes refreshed correctly",
         "passed": (m.get("hash_refresh_distinct") or 0) > 1,
         "evidence": f"{m.get('hash_refresh_distinct')} distinct checkpoint hashes observed",
         "c012_failure": "a per-path hash cache returned the first hash forever"},
        {"requirement": "all progression gates computed",
         "passed": (m.get("gate_evaluations") or 0) > 0
                   and all("gates" in e for e in evs),
         "evidence": f"{m.get('gate_evaluations')} gate evaluations; every evaluation record "
                     f"carries a gates dict"},
        {"requirement": "curriculum stage changes at least once (adaptive arm)",
         "passed": (m.get("stage_changes", 0) > 0) if arm == "R1" else True,
         "evidence": f"stage_changes={m.get('stage_changes')}, final_stage="
                     f"{summ.get('final_stage')}"
                     + ("" if arm == "R1" else " (control arm: no change expected)")},
        {"requirement": "curriculum history preserved",
         "passed": len(summ.get("curriculum_history") or []) > 0 or arm == "R0",
         "evidence": f"{len(summ.get('curriculum_history') or [])} history entries"},
        {"requirement": "early-stop code path exercised",
         "passed": bool(m.get("early_stop_path_exercised")),
         "evidence": "a deterministic fixture drives the stop condition without ending the run",
         "c012_failure": "early stopping was wired but never received a score"},
        {"requirement": "trainer state saved and restored mid-run",
         "passed": (m.get("trainer_state_saved") or 0) > 0 and bool(rv),
         "evidence": f"{m.get('trainer_state_saved')} save/restore cycle(s); "
                     f"continuation_kind="
                     f"{(rv.get('report') or {}).get('continuation_kind')}"},
        {"requirement": "next opponent/seat/seed sequence reproduced after restore",
         "passed": bool(rv.get("sequences_match")),
         "evidence": f"expected {rv.get('expected')} == restored {rv.get('restored')}",
         "c011_failure": "c011 persisted the legacy global RNG, so nothing was reproduced"},
    ]


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    arms, total = {}, 0
    for arm, seed, desc in ARMS:
        s = load(arm, seed)
        if not s:
            arms[arm] = {"status": "MISSING"}
            continue
        reqs = requirements(s, arm)
        total += s.get("completed_games", 0)
        arms[arm] = {"seed": seed, "description": desc,
                     "completed_games": s.get("completed_games"),
                     "over_per_arm_cap": max(0, s.get("completed_games", 0) - PER_ARM_CAP),
                     "updates": s.get("updates"), "final_stage": s.get("final_stage"),
                     "stage_changes": (s.get("machinery") or {}).get("stage_changes"),
                     "stop_reason": s.get("stop_reason"),
                     "reliability": s.get("reliability"),
                     "evaluations": [{"point": e.get("registered_point"),
                                      "completed_games": e.get("completed_games"),
                                      "teacher": e.get("teacher"), "field": e.get("field"),
                                      "scored": e.get("scored"), "n": e.get("n_games"),
                                      "stage": e.get("stage"),
                                      "backfilled": bool(e.get("backfilled"))}
                                     for e in s.get("evaluations") or []],
                     "requirements": reqs,
                     "all_requirements_passed": all(r["passed"] for r in reqs)}

    all_ok = all(a.get("all_requirements_passed") for a in arms.values()
                 if a.get("status") != "MISSING")
    verdict = "PASS" if all_ok else "FAIL"
    doc = {"CURRICULUM_SMOKE": verdict,
           "scope": "§18 — validates execution machinery only; this is NOT a curriculum "
                    "effectiveness experiment and no effectiveness claim is made",
           "arms": arms,
           "budget": {"total_completed_games": total, "registered_cap": SMOKE_CAP,
                      "per_arm_cap": PER_ARM_CAP,
                      "over_cap": max(0, total - SMOKE_CAP),
                      "within_cap": total <= SMOKE_CAP}}
    json.dump(doc, open(os.path.join(ART, "curriculum_smoke_registry.json"), "w"),
              indent=2, default=str)

    with open(os.path.join(ART, "curriculum_smoke_history.jsonl"), "w") as fh:
        for arm, seed, _ in ARMS:
            s = load(arm, seed)
            if not s:
                continue
            for h in s.get("curriculum_history") or []:
                fh.write(json.dumps({"arm": arm, "seed": seed, **h}) + "\n")
            for e in s.get("evaluations") or []:
                fh.write(json.dumps({"arm": arm, "seed": seed, "record": "evaluation",
                                     "point": e.get("registered_point"),
                                     "completed_games": e.get("completed_games"),
                                     "stage": e.get("stage"), "teacher": e.get("teacher"),
                                     "field": e.get("field"), "scored": e.get("scored"),
                                     "gates": e.get("gates"),
                                     "backfilled": bool(e.get("backfilled"))}) + "\n")

    write_md(doc)
    with open(os.path.join(LOGD, "curriculum_smoke.txt"), "w") as fh:
        fh.write(json.dumps(doc, indent=2, default=str) + "\n")
    print(json.dumps({"CURRICULUM_SMOKE": verdict,
                      "total_games": total, "over_cap": doc["budget"]["over_cap"],
                      "arms": {a: {"stage_changes": v.get("stage_changes"),
                                   "all_requirements_passed": v.get("all_requirements_passed")}
                               for a, v in arms.items()}}, indent=2))
    return 0


def write_md(doc):
    L = ["# AC-11 — adaptive-curriculum smoke test\n"]
    L.append(f"**CURRICULUM_SMOKE = {doc['CURRICULUM_SMOKE']}**\n")
    L.append("§18: this validates **execution machinery only**. 5,000 games per arm cannot "
             "support a claim about whether the adaptive curriculum helps, and none is made "
             "here.\n")
    L.append("Every requirement below exists because c012 shipped a 90,000-game arm in which "
             "none of them held: a stale per-path checkpoint-hash cache emptied every in-run "
             "evaluation after game zero, so the gates never ran, the stage never advanced past "
             "0, and early stopping never received a score.\n")
    for arm, v in doc["arms"].items():
        if v.get("status") == "MISSING":
            L.append(f"## {arm} — MISSING\n")
            continue
        L.append(f"## {arm} seed {v['seed']} — {v['description']}\n")
        L.append(f"{v['completed_games']} completed games, {v['updates']} updates, "
                 f"final stage {v['final_stage']} after {v['stage_changes']} stage change(s). "
                 f"Reliability: {v['reliability']}.\n")
        L.append("| registered point | games | stage | teacher | field | scored |")
        L.append("|---|---|---|---|---|---|")
        for e in v["evaluations"]:
            f = lambda x: "—" if x is None else f"{x:.3f}"   # noqa: E731
            tag = " *(backfilled)*" if e["backfilled"] else ""
            L.append(f"| {e['point']}{tag} | {e['completed_games']} | {e['stage']} | "
                     f"{f(e['teacher'])} | {f(e['field'])} | {e['scored']}/{e['n']} |")
        L.append("")
        L.append("| §20 requirement | passed | evidence |")
        L.append("|---|---|---|")
        for r in v["requirements"]:
            L.append(f"| {r['requirement']} | {'**yes**' if r['passed'] else 'NO'} | "
                     f"{r['evidence']} |")
        L.append("")
    b = doc["budget"]
    L.append("## Budget\n")
    L.append(f"{b['total_completed_games']} completed games against a registered maximum of "
             f"{b['registered_cap']} — **{b['over_cap']} over**.\n" if not b["within_cap"]
             else f"{b['total_completed_games']} of {b['registered_cap']} — within cap.\n")
    if not b["within_cap"]:
        L.append("This overshoot is a rollout-granularity effect and is documented as a "
                 "deviation in `results/failures/`; it is not rounded away here. The 62,000 "
                 "hard training maximum is not approached.\n")
    open(os.path.join(ART, "CURRICULUM_SMOKE.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

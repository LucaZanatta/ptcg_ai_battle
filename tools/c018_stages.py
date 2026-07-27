"""c018 §29 — the six preserved candidate stages, with explicit non-production records.

§29: "A stage that is unavailable or tainted receives an explicit `NOT_PRODUCED.json` or
`NON_SUBMITTABLE.json`; it is not silently omitted." An absent directory reads as "not
applicable"; an explicit record reads as "we looked, and here is why".
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
STG = os.path.join(C18, "stages")

STAGES = [
    ("BASELINE_OFFICIAL_LUCARIO", "official_mega_lucario", None, None,
     "the official sample agent, byte-identical; the incumbent anchor"),
    ("SEARCH_HEURISTIC_REAL", "m01_heuristic_search", "submission_K_official_search_v0",
     None, "baseline under real official-API forward search with the heuristic leaf evaluator"),
    ("POLICY_DISTILLED_REAL_SEARCH", "m02_distilled_policy", None, "m02_distilled.npz",
     "the search-distilled policy playing directly; isolates what distillation alone bought"),
    ("POLICY_CURRICULUM_BEST", "m03_curriculum_policy", "submission_M_trained_policy_v0",
     "m03_curriculum.npz", "the PPO curriculum policy playing directly, via the same RLAgent "
                           "the curriculum trained"),
    ("SEARCH_POLICY_ORDERED_REAL", "m04_guided_ordering_only", None, "m03_curriculum.npz",
     "real search with learned candidate ordering and the HEURISTIC leaf evaluator"),
    ("SEARCH_POLICY_VALUE_GUIDED_REAL", "m04_guided_search", "submission_L_guided_search_v0",
     "m03_curriculum.npz", "real search with learned ordering AND learned leaf values"),
]


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else d


def main():
    os.makedirs(STG, exist_ok=True)
    panel = jload("final_panel/final_panel_results.json", []) or []
    by_cand = {r["candidate_id"]: r for r in panel}
    out = []
    for name, cid, pkg, ckpt, desc in STAGES:
        d = os.path.join(STG, name)
        os.makedirs(d, exist_ok=True)
        row = by_cand.get(cid)
        val = jload(f"packages/{pkg}_clean_validation.json") if pkg else None
        man = jload(f"packages/{pkg}_manifest.json") if pkg else None
        rec = {
            "stage": name, "candidate_id": cid, "description": desc,
            "produced": row is not None,
            "checkpoint": ckpt,
            "checkpoint_sha256": sha(os.path.join(C18, "checkpoints", ckpt)) if ckpt else None,
            "panel_result": ({"games": row["games"], "overall_rate": row["overall_rate"],
                              "overall_ci": row["overall_ci"],
                              "worst_matchup": row["worst_matchup"],
                              "worst_matchup_rate": row["worst_matchup_rate"]}
                             if row else None),
            "package": pkg,
            "package_sha256": (man or {}).get("sha256"),
            "clean_extraction_ok": (val or {}).get("clean_extraction_ok"),
            "submittable": bool(pkg and (val or {}).get("clean_extraction_ok")),
        }
        if not rec["produced"]:
            rec["status"] = "NOT_PRODUCED"
            rec["reason"] = ("the final panel has not been run yet, or this stage produced no "
                             "scored games")
            json.dump(rec, open(os.path.join(d, "NOT_PRODUCED.json"), "w"), indent=2,
                      default=str)
        elif not rec["submittable"]:
            rec["status"] = "NON_SUBMITTABLE"
            rec["reason"] = ("no clean-validated inference-only package exists for this stage; "
                             "it is evaluated and archived but cannot be uploaded"
                             if not pkg else
                             "a package exists but did not pass clean-extraction validation")
            json.dump(rec, open(os.path.join(d, "NON_SUBMITTABLE.json"), "w"), indent=2,
                      default=str)
            for stale in glob.glob(os.path.join(d, "NOT_PRODUCED.json")):
                os.remove(stale)
        else:
            rec["status"] = "SUBMITTABLE"
            for stale in glob.glob(os.path.join(d, "NO*.json")):
                os.remove(stale)
        json.dump(rec, open(os.path.join(d, "stage.json"), "w"), indent=2, default=str)
        out.append(rec)
        print(f"  {name:34s} {rec['status']:16s} "
              f"{rec['panel_result']['overall_rate'] if rec['panel_result'] else '-'}")
    json.dump({"stages": out,
               "produced": sum(1 for r in out if r["produced"]),
               "submittable": sum(1 for r in out if r["status"] == "SUBMITTABLE"),
               "total": len(out)},
              open(os.path.join(STG, "stage_registry.json"), "w"), indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

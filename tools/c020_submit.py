"""c020 §10 — gate evaluation and automatic submission.

`CONTRACT §10` says to upload every credible materially different package as soon as its gate
passes, and `DECISION_RULES` says not to upload a known-weak or tainted candidate merely to
complete the contract. Both halves are enforced here: the gate is computed from the frozen panel
and the package validation, and a failed gate is RECORDED rather than substituted.

The gates differ per branch (§10) and are implemented separately rather than collapsed into one
"is it better" test, because the ByteRL gate additionally requires beating its own fresh
initialization and the c019 control — improvement over its own past is part of what the contract
asks, and a single field-score comparison would not express it.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
SUB = os.path.join(C20, "submissions")
COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE = os.path.join(_REPO, ".venv", "bin", "kaggle")
MAX_UPLOADS = 2
BASELINE = "BASELINE_OFFICIAL_MEGA_LUCARIO"


def run(args, timeout=900):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=_REPO)
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except Exception as e:  # noqa: BLE001
        return {"returncode": -1, "stdout": "", "stderr": repr(e)[:500]}


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C20, p)
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return d


def panel_row(panel: Dict[str, Any], cid: str) -> Optional[Dict[str, Any]]:
    for r in panel.get("results", []):
        if r["candidate_id"] == cid:
            return r
    return None


def gate_mcts(panel, cid, pkg) -> Dict[str, Any]:
    base, cand = panel_row(panel, BASELINE), panel_row(panel, cid)
    if not base or not cand:
        return {"eligible": False, "reason": "candidate or baseline absent from the panel"}
    d = cand["field_score"] - base["field_score"]
    per = {o: round(cand[f"{o}_rate"] - base[f"{o}_rate"], 4)
           for o in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")
           if cand.get(f"{o}_rate") is not None and base.get(f"{o}_rate") is not None}
    val = (pkg or {}).get("validation") or {}
    checks = {
        "package_reliability": bool(val.get("clean_extraction_ok")),
        "method_actually_ran": bool(val.get("method_actually_ran")),
        "zero_incomplete_games": cand.get("incomplete_games", 1) == 0,
        "match_clock_safe": (cand.get("max_search_match_ms") or 0) < 600_000 * 0.6,
        "field_plus_3pts": d >= 0.03,
        "matchup_plus_5_without_2pt_regression": (
            any(v >= 0.05 for v in per.values()) and d >= -0.02),
    }
    checks["eligible"] = bool(
        checks["package_reliability"] and checks["method_actually_ran"]
        and checks["zero_incomplete_games"] and checks["match_clock_safe"]
        and (checks["field_plus_3pts"] or checks["matchup_plus_5_without_2pt_regression"]))
    return {"branch": "mcts", "candidate": cid, "baseline_field": base["field_score"],
            "candidate_field": cand["field_score"],
            "delta_field_points": round(d * 100, 1), "per_matchup_delta": per,
            "checks": checks, "eligible": checks["eligible"],
            "games": cand["games"] + base["games"],
            "rule": "CONTRACT §10 corrected-MCTS gate"}


def gate_byterl(panel, cid, pkg) -> Dict[str, Any]:
    base, cand = panel_row(panel, BASELINE), panel_row(panel, cid)
    c19 = panel_row(panel, "C019_BYTERL_CONTROL")
    if not base or not cand:
        return {"eligible": False, "reason": "candidate or baseline absent from the panel"}
    d = cand["field_score"] - base["field_score"]
    val = (pkg or {}).get("validation") or {}
    beats_c19 = (c19 is not None and c19.get("field_score") is not None
                 and cand["field_score"] > c19["field_score"] + 0.02)
    checks = {
        "package_reliability": bool(val.get("clean_extraction_ok")),
        "method_actually_ran": bool(val.get("method_actually_ran")),
        "legal_rate_100pct": cand.get("incomplete_games", 1) == 0,
        "materially_beats_c019_byterl": bool(beats_c19),
        "field_plus_2pts": d >= 0.02,
        "direct_vs_baseline_at_least_55pct": (cand.get("mega_lucario_rate") or 0) >= 0.55,
    }
    checks["eligible"] = bool(
        checks["package_reliability"] and checks["method_actually_ran"]
        and checks["legal_rate_100pct"] and checks["materially_beats_c019_byterl"]
        and (checks["field_plus_2pts"] or checks["direct_vs_baseline_at_least_55pct"]))
    return {"branch": "byterl", "candidate": cid, "baseline_field": base["field_score"],
            "candidate_field": cand["field_score"],
            "c019_control_field": (c19 or {}).get("field_score"),
            "delta_field_points": round(d * 100, 1),
            "checks": checks, "eligible": checks["eligible"],
            "games": cand["games"] + base["games"],
            "rule": "CONTRACT §10 corrected-ByteRL gate"}


def gate_hybrid(panel, cid, pkg) -> Dict[str, Any]:
    """§10: the hybrid compares against the STRONGER CORRECTED PURE PARENT, not the baseline."""
    cand = panel_row(panel, cid)
    parents = [panel_row(panel, p) for p in ("C020_CORRECTED_MCTS", "C020_CORRECTED_BYTERL")]
    parents = [p for p in parents if p and p.get("field_score") is not None]
    if not cand or not parents:
        return {"eligible": False, "reason": "candidate or pure parents absent from the panel"}
    best = max(parents, key=lambda p: p["field_score"])
    d = cand["field_score"] - best["field_score"]
    per = {o: round(cand[f"{o}_rate"] - best[f"{o}_rate"], 4)
           for o in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")
           if cand.get(f"{o}_rate") is not None and best.get(f"{o}_rate") is not None}
    val = (pkg or {}).get("validation") or {}
    manifest = jload(f"hybrid/configs/{cid.replace('C020_', '')}.json", {}) or {}
    cheaper = ((cand.get("max_search_match_ms") or 1e18)
               <= 0.7 * (best.get("max_search_match_ms") or 0)) and abs(d) < 0.02
    checks = {
        "adapters_admitted": bool(manifest.get("promotable")),
        "package_reliability": bool(val.get("clean_extraction_ok")),
        "beats_best_parent_by_3pts": d >= 0.03,
        "matchup_plus_5_without_2pt_regression": (
            any(v >= 0.05 for v in per.values()) and d >= -0.02),
        "strength_retained_at_30pct_lower_cost": bool(cheaper),
    }
    checks["eligible"] = bool(
        checks["adapters_admitted"] and checks["package_reliability"]
        and (checks["beats_best_parent_by_3pts"]
             or checks["matchup_plus_5_without_2pt_regression"]
             or checks["strength_retained_at_30pct_lower_cost"]))
    return {"branch": "hybrid", "candidate": cid, "best_parent": best["candidate_id"],
            "best_parent_field": best["field_score"], "candidate_field": cand["field_score"],
            "delta_vs_best_parent_points": round(d * 100, 1), "per_matchup_delta": per,
            "checks": checks, "eligible": checks["eligible"],
            "rule": "CONTRACT §10 hybrid gate -- must beat the stronger corrected pure parent; "
                    "a more complex hybrid that only ties a parent at higher runtime is rejected"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--branch", choices=("mcts", "byterl", "hybrid"), required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--panel-tag", default="final")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(SUB, "responses"), exist_ok=True)

    panel = jload(f"final_panel/{a.panel_tag}_aggregates.json", {}) or {}
    pkg = None
    for p in glob.glob(os.path.join(C20, "packages", "*", f"{a.package}_manifest.json")):
        pkg = json.load(open(p))
    gate = {"mcts": gate_mcts, "byterl": gate_byterl, "hybrid": gate_hybrid}[a.branch](
        panel, a.candidate, pkg)
    gate.update({"package": a.package, "panel_tag": a.panel_tag,
                 "package_sha256": (pkg or {}).get("sha256"),
                 "checkpoint_sha256": (pkg or {}).get("checkpoint_sha256")})
    json.dump(gate, open(os.path.join(SUB, f"{a.package}_gate.json"), "w"), indent=2)

    refs = jload("submissions/references.json", {}) or {}
    if not gate.get("eligible"):
        refs[a.package] = {"branch": a.branch, "candidate": a.candidate,
                           "submission_ref": None, "status": "BLOCKED_BY_GATE",
                           "gate": gate}
        json.dump(refs, open(os.path.join(SUB, "references.json"), "w"), indent=2)
        print(json.dumps({"upload": "BLOCKED_BY_GATE", "candidate": a.candidate,
                          "checks": gate.get("checks"),
                          "delta": gate.get("delta_field_points")
                          or gate.get("delta_vs_best_parent_points")}, indent=2))
        return 1

    used = len([v for v in refs.values() if v.get("submission_ref")])
    if used >= MAX_UPLOADS:
        print(json.dumps({"upload": "BLOCKED_BUDGET", "uploads_used": used}, indent=2))
        return 1
    if not a.execute:
        print(json.dumps({"upload": "DRY_RUN_ELIGIBLE", "gate": gate.get("checks")}, indent=2))
        return 0

    short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
                           capture_output=True, text=True).stdout.strip()
    desc = f"c020 {a.candidate} {short}"
    arch = (pkg or {}).get("zip")
    r = run([KAGGLE, "competitions", "submit", COMPETITION, "-f",
             os.path.relpath(arch, _REPO), "-m", desc])
    ref = None
    if r["returncode"] == 0:
        for line in (r["stdout"] or "").splitlines():
            if "successfully" in line.lower():
                ref = desc
    refs[a.package] = {"branch": a.branch, "candidate": a.candidate,
                       "submission_ref": ref, "description": desc,
                       "status": "SUBMITTED" if ref else "UPLOAD_FAILED",
                       "score": "PENDING", "gate": gate}
    json.dump(refs, open(os.path.join(SUB, "references.json"), "w"), indent=2)
    json.dump(r, open(os.path.join(SUB, "responses", f"{a.package}_response.json"), "w"),
              indent=2)
    print(json.dumps({"upload": refs[a.package]["status"], "ref": ref,
                      "stdout": (r["stdout"] or "")[-300:]}, indent=2))
    return 0 if ref else 1


if __name__ == "__main__":
    raise SystemExit(main())

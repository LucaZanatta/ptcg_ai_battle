"""c019 §13 — gated Kaggle submission, one per pure branch.

The DECISION_RULES credibility gates are evaluated HERE, in code, from the frozen panel. A gate
that lives only in a markdown file constrains nothing: c018 nearly uploaded an agent its own
pre-registered rule forbade, because the rule was never implemented in the tool that uploads.

Maximum two c019 uploads, one per pure branch. Credentials are resolved by the CLI and are never
read, printed, or written here.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
PKG = os.path.join(C19, "packages")
SUB = os.path.join(C19, "submissions")
COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE = os.path.join(_REPO, ".venv", "bin", "kaggle")
MAX_UPLOADS = 2
POLL_MAX, POLL_S = 20, 30

BASELINE = "baseline_official_mega_lucario"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(args, timeout=900):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=_REPO)
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except Exception as e:  # noqa: BLE001
        return {"returncode": -1, "stdout": "", "stderr": repr(e)[:500]}


def list_submissions():
    r = run([KAGGLE, "competitions", "submissions", COMPETITION, "-v"], 300)
    rows = []
    if r["returncode"] == 0 and r["stdout"].strip():
        import csv
        import io
        lines = [l for l in r["stdout"].splitlines() if l.strip()]
        start = next((i for i, l in enumerate(lines)
                      if l.lower().startswith(("filename", "ref"))), 0)
        rows = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))
    return rows, r


def panel_rows(tag: str) -> Dict[str, Dict[str, Any]]:
    p = os.path.join(C19, "final_panel", f"{tag}_aggregates.json")
    if not os.path.exists(p):
        return {}
    return {r["candidate_id"]: r for r in json.load(open(p))["results"]}


def mcts_gate(tag: str) -> Dict[str, Any]:
    """DECISION_RULES -- MCTS credibility."""
    rows = panel_rows(tag)
    b, m = rows.get(BASELINE), rows.get("ptcg_ismcts_v0")
    if not b or not m:
        return {"eligible": False, "reason": "no frozen panel result for MCTS vs baseline"}
    delta = (m["field_score"] or 0) - (b["field_score"] or 0)
    per = {o: round((m.get(f"{o}_rate") or 0) - (b.get(f"{o}_rate") or 0), 4)
           for o in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")
           if m.get(f"{o}_rate") is not None and b.get(f"{o}_rate") is not None}
    a_clause = delta >= 0.03
    b_clause = (max(per.values()) if per else -1) >= 0.05 and delta >= -0.02
    return {"branch": "mcts", "panel_tag": tag,
            "baseline_field": b["field_score"], "candidate_field": m["field_score"],
            "delta_field_points": round(delta, 4), "per_matchup_delta": per,
            "clause_field_plus_3pts": a_clause,
            "clause_matchup_plus_5pts": b_clause,
            "eligible": bool(a_clause or b_clause),
            "rule": "field >= baseline+3pts, OR a matchup +5pts without >2pt field regression"}


def byterl_gate(tag: str) -> Dict[str, Any]:
    """DECISION_RULES -- ByteRL credibility."""
    rows = panel_rows(tag)
    b = rows.get(BASELINE)
    m = next((v for k, v in rows.items() if k.startswith("ptcg_byterl")), None)
    if not b or not m:
        return {"eligible": False, "reason": "no frozen panel result for ByteRL vs baseline"}
    delta = (m["field_score"] or 0) - (b["field_score"] or 0)
    vs_base = m.get("mega_lucario_rate")     # the baseline's own deck/agent is the mirror
    ev = json.load(open(os.path.join(C19, "byterl", "evaluations", "milestone_ladder.json"))) \
        if os.path.exists(os.path.join(C19, "byterl", "evaluations",
                                       "milestone_ladder.json")) else {}
    return {"branch": "byterl", "panel_tag": tag,
            "baseline_field": b["field_score"], "candidate_field": m["field_score"],
            "delta_field_points": round(delta, 4),
            "direct_vs_baseline_agent": vs_base,
            "beats_initial_policy": ev.get("beats_initial"),
            "beats_two_historical": ev.get("beats_two_historical"),
            "clause_field_plus_2pts": delta >= 0.02,
            "clause_direct_55pct": (vs_base or 0) >= 0.55,
            "eligible": bool((delta >= 0.02 or (vs_base or 0) >= 0.55)
                             and ev.get("beats_initial") is not False
                             and ev.get("beats_two_historical") is not False),
            "rule": ("field >= baseline+2pts OR direct vs baseline >= 55%, AND the final "
                     "checkpoint beats the initial policy and >=2 historical checkpoints")}


def preflight(name: str, branch: str, panel_tag: str) -> Dict[str, Any]:
    man = json.load(open(os.path.join(PKG, name, "manifest.json")))
    val = json.load(open(os.path.join(PKG, name, "clean_validation.json")))
    fid = json.load(open(os.path.join(C19, "method_fidelity", f"{branch}_fidelity.json"))) \
        if os.path.exists(os.path.join(C19, "method_fidelity", f"{branch}_fidelity.json")) \
        else {}
    arch = os.path.join(PKG, name, man["archive"])
    used = len(glob.glob(os.path.join(SUB, "*_upload.json")))
    gate = mcts_gate(panel_tag) if branch == "mcts" else byterl_gate(panel_tag)
    games = val.get("games_played", 0)

    gates = {
        "archive_hash_matches_manifest": os.path.exists(arch)
        and sha_file(arch) == man["sha256"],
        "clean_extraction_ok": bool(val.get("clean_extraction_ok")),
        "both_seats_exercised": bool(val.get("both_seats")),
        "at_least_100_validation_games": games >= 100,
        "zero_errors_in_validation": not (val.get("errors") or []),
        "method_actually_ran_in_package": bool(val.get("method_actually_ran")),
        "method_fidelity_validator_passes": fid.get("method_fidelity") == "PASS",
        "no_submission_blockers": (fid.get("submission_blockers") or 0) == 0,
        "no_dependency_on_other_branch": man.get("depends_on_other_branch") is False,
        "upload_budget_remaining": used < MAX_UPLOADS,
        "credibility_gate": bool(gate.get("eligible")),
    }
    return {"name": name, "branch": branch, "gates": gates,
            "all_gates_pass": all(gates.values()),
            "failed_gates": [k for k, v in gates.items() if not v],
            "credibility": gate, "uploads_used": used, "uploads_allowed": MAX_UPLOADS,
            "archive": os.path.relpath(arch, C19), "archive_sha256": man["sha256"],
            "clean_validation": {k: val.get(k) for k in
                                 ("games_played", "games_completed", "win_rate",
                                  "max_game_seconds", "method_actually_ran")}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--branch", choices=("mcts", "byterl"), required=True)
    ap.add_argument("--panel-tag", default="mcts_gate")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(SUB, exist_ok=True)
    os.makedirs(os.path.join(SUB, "responses"), exist_ok=True)

    pre = preflight(a.name, a.branch, a.panel_tag)
    json.dump(pre, open(os.path.join(SUB, f"{a.name}_preflight.json"), "w"), indent=2,
              default=str)
    if not pre["all_gates_pass"]:
        print(json.dumps({"upload": "BLOCKED_BY_GATE", "failed_gates": pre["failed_gates"],
                          "credibility": pre["credibility"]}, indent=2, default=str))
        return 1

    short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
                           capture_output=True, text=True).stdout.strip()
    desc = f"c019 {a.name} {short}"
    existing, _ = list_submissions()
    if [r for r in existing if (r.get("description") or "").strip() == desc]:
        print(json.dumps({"upload": "BLOCKED_DUPLICATE", "description": desc}, indent=2))
        return 1
    arch_rel = os.path.relpath(os.path.join(C19, pre["archive"]), _REPO)
    cmd = [KAGGLE, "competitions", "submit", COMPETITION, "-f", arch_rel, "-m", desc]
    open(os.path.join(SUB, f"{a.name}_KAGGLE_COMMAND.txt"), "w").write(
        "# credentials are resolved by the CLI and never read or written here\n"
        + " ".join(cmd) + "\n")
    if not a.execute:
        print(json.dumps({"upload": "PREFLIGHT_ONLY", "all_gates_pass": True,
                          "description": desc}, indent=2))
        return 0

    before = {r.get("ref") for r in existing}
    t0 = datetime.datetime.now(datetime.timezone.utc)
    r = run(cmd)
    ref = status = score = None
    poll = []
    for i in range(POLL_MAX):
        rows, _ = list_submissions()
        new = [x for x in rows if x.get("ref") not in before]
        cand = [x for x in new if (x.get("description") or "").strip() == desc] or new
        if cand:
            ref = cand[0].get("ref")
            status = (cand[0].get("status") or "").replace("SubmissionStatus.", "")
            score = cand[0].get("publicScore")
        poll.append({"attempt": i + 1, "ref": ref, "status": status, "score": score})
        if ref and status in ("COMPLETE", "ERROR", "CANCELLED"):
            break
        time.sleep(POLL_S)

    doc = {"name": a.name, "branch": a.branch, "description": desc,
           "kaggle_upload": "SUBMITTED" if (r["returncode"] == 0 and ref) else "FAILED",
           "submitted_utc": t0.isoformat(), "submission_ref": ref,
           "status": status or ("PENDING" if ref else None), "public_score": score,
           "public_score_note": ("the public score is a LIVE ladder rating, not a fixed "
                                 "evaluation; 600.0 is the provisional start value"),
           "archive_sha256": pre["archive_sha256"], "returncode": r["returncode"],
           "stdout": r["stdout"][:3000], "stderr": r["stderr"][:3000], "poll_log": poll,
           "preflight": pre}
    json.dump(doc, open(os.path.join(SUB, f"{a.name}_upload.json"), "w"), indent=2, default=str)
    refs = {}
    p = os.path.join(SUB, "references.json")
    if os.path.exists(p):
        refs = json.load(open(p))
    refs[a.name] = {"branch": a.branch, "submission_ref": ref, "status": status,
                    "public_score": score, "submitted_utc": t0.isoformat()}
    json.dump(refs, open(p, "w"), indent=2, default=str)
    print(json.dumps({k: doc[k] for k in ("kaggle_upload", "submission_ref", "status",
                                          "public_score")}, indent=2, default=str))
    return 0 if ref else 1


if __name__ == "__main__":
    raise SystemExit(main())

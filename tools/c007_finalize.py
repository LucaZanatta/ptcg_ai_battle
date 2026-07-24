"""c007 AC-14 (gated) + AC-15: RL-readiness artifacts and the Kaggle evidence.

When SUBMISSION_C == DO_NOT_SUBMIT, no upload is performed (record SKIPPED_BY_GATE), but
the teacher's public score (ref 54948560) is refreshed READ-ONLY for a timestamped
teacher/hybrid comparison, and the required Kaggle evidence files are written with the
gated status. RESIDUAL_RL_READINESS artifacts are derived from the decisions.
"""

import argparse
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
LOG_DIR = os.path.join(os.path.dirname(C007_ART), "test_logs")
TEACHER_REF = "54948560"
COMPETITION = "pokemon-tcg-ai-battle"


def _refresh_teacher():
    """Read-only fetch of the current submissions CSV; extract teacher ref 54948560."""
    try:
        r = subprocess.run(["kaggle", "competitions", "submissions", COMPETITION, "-v"],
                           capture_output=True, text=True, timeout=90)
        raw = r.stdout
        open(os.path.join(C007_ART, "kaggle_submissions_after_submit.csv"), "w").write(raw)
        teacher_row = None
        score = None
        for line in raw.splitlines():
            if TEACHER_REF in line:
                teacher_row = line
                for tok in line.replace(",", " ").split():
                    try:
                        v = float(tok)
                        if 0 <= v <= 100000 and v > 10:  # public score magnitude
                            score = v
                            break
                    except ValueError:
                        continue
                break
        return {"ok": r.returncode == 0, "teacher_row": teacher_row,
                "teacher_public_score_same_run": score, "stderr": r.stderr[:400]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e), "teacher_public_score_same_run": None}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(LOG_DIR, exist_ok=True)
    sel = json.load(open(os.path.join(C007_ART, "hybrid_selection.json")))
    base = json.load(open(os.path.join(_REPO, "contracts",
                    "c007_hybrid_teacher_residual_and_state_encoder_v2", "inputs",
                    "kaggle_teacher_baseline.json")))
    submit = sel["submission_C"] == "SUBMIT"

    # ---- AC-15 RESIDUAL_RL_READINESS ----
    rl = {
        "contract": "c007",
        "residual_rl_readiness": sel["residual_rl_readiness"],
        "conditions": sel["rl_readiness_conditions"],
        "highest_leverage_blocker": sel["highest_leverage_blocker"],
        "rationale": ("READY requires H2 local non-inferiority AND a reproducible improvement AND "
                      "stable residual contexts/gates AND valid on-policy sync AND constrained "
                      "override telemetry AND a frozen H2 AND no major regression. The reproducible-"
                      "improvement condition is not met, so residual RL is NOT_READY: there is no "
                      "validated positive residual action-space for RL to safely optimise within."),
    }
    json.dump(rl, open(os.path.join(C007_ART, "residual_rl_readiness.json"), "w"), indent=2)
    open(os.path.join(C007_ART, "RESIDUAL_RL_READINESS.md"), "w").write(
        f"# Residual-RL Readiness (AC-15)\n\n**RESIDUAL_RL_READINESS = {sel['residual_rl_readiness']}**\n\n"
        + "\n".join(f"- {'PASS' if v else 'FAIL'} — {k}" for k, v in sel["rl_readiness_conditions"].items())
        + f"\n\n**Highest-leverage blocker:** {sel['highest_leverage_blocker']}\n\n{rl['rationale']}\n")

    # ---- AC-14 Kaggle evidence ----
    kaggle_status = "SUBMITTED" if submit else "SKIPPED_BY_GATE"
    refresh = _refresh_teacher()
    teacher_score = refresh.get("teacher_public_score_same_run")

    comparison = {
        "contract": "c007",
        "teacher_submission_ref": TEACHER_REF,
        "teacher_recorded_public_score": base.get("initial_recorded_public_score"),
        "teacher_public_score_same_run": teacher_score,
        "hybrid_submission_ref": None,
        "hybrid_public_score": None,
        "best_hybrid": sel["best_hybrid"],
        "submission_C": sel["submission_C"],
        "note": ("DO_NOT_SUBMIT: no hybrid was uploaded (SKIPPED_BY_GATE). Teacher score refreshed "
                 "read-only for the record; the frozen teacher remains the standing submission. "
                 "Do not infer superiority from any single immature score snapshot."),
        "refresh_detail": refresh,
    }
    json.dump(comparison, open(os.path.join(C007_ART, "kaggle_teacher_hybrid_comparison.json"), "w"), indent=2)

    status = {"kaggle_upload": kaggle_status, "submission_C": sel["submission_C"],
              "best_hybrid": sel["best_hybrid"], "submission_ref": None, "status": None,
              "public_score": None,
              "note": "No upload: local submission gate = DO_NOT_SUBMIT (no reproducible improvement)."}
    json.dump(status, open(os.path.join(C007_ART, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(C007_ART, "kaggle_submission_history.jsonl"), "w").write(
        json.dumps({"event": "skipped_by_gate", "reason": "DO_NOT_SUBMIT",
                    "best_hybrid": sel["best_hybrid"]}) + "\n")

    short_sha = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
    cmd = (f"# SKIPPED_BY_GATE (SUBMISSION_C=DO_NOT_SUBMIT). Command that WOULD run on SUBMIT:\n"
           f"kaggle competitions submit {COMPETITION} \\\n"
           f"  -f contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/results/artifacts/"
           f"submission_C_hybrid.tar.gz \\\n"
           f"  -m \"c007 Submission C: hybrid residual {short_sha}\"\n"
           f"# Teacher refresh (read-only, executed this run):\n"
           f"kaggle competitions submissions {COMPETITION} -v\n")
    open(os.path.join(C007_ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(cmd)

    subval = {"submission_C": sel["submission_C"], "archive": None,
              "status": "SKIPPED_BY_GATE",
              "note": "No submission archive built for upload — DO_NOT_SUBMIT. A diagnostic "
                      "archive + validation is produced separately by build_submission_c.py if run."}
    # if a diagnostic validation exists, fold it in
    diag = os.path.join(C007_ART, "submission_C_validation_diagnostic.json")
    if os.path.exists(diag):
        subval["diagnostic_validation"] = json.load(open(diag))
    json.dump(subval, open(os.path.join(C007_ART, "submission_C_validation.json"), "w"), indent=2)

    open(os.path.join(C007_ART, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision (AC-14)\n\n"
        f"**PROMOTION_DECISION = {sel['promotion_decision']}**\n\n"
        f"- BEST_HYBRID = {sel['best_hybrid']}; SUBMISSION_C = {sel['submission_C']}; "
        f"kaggle_upload = {kaggle_status}.\n"
        f"- Teacher ref {TEACHER_REF}: recorded {base.get('initial_recorded_public_score')}, "
        f"same-run refresh {teacher_score}.\n"
        f"- No hybrid submitted; the frozen teacher remains the standing competition submission. "
        f"Superiority is never declared from a single immature snapshot.\n")

    for fn, txt in [("submission_C_smoke.txt", f"SKIPPED_BY_GATE: {sel['submission_C']} (no archive built for upload)\n"),
                    ("kaggle_submission.txt", f"kaggle_upload={kaggle_status}; no `kaggle competitions submit` executed (DO_NOT_SUBMIT gate).\n"),
                    ("kaggle_submission_retrieval.txt", f"teacher refresh (read-only) ok={refresh.get('ok')}; teacher_public_score_same_run={teacher_score}\n")]:
        open(os.path.join(LOG_DIR, fn), "w").write(txt)

    print(json.dumps({"residual_rl_readiness": sel["residual_rl_readiness"],
                      "kaggle_upload": kaggle_status,
                      "teacher_public_score_same_run": teacher_score,
                      "promotion_decision": sel["promotion_decision"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

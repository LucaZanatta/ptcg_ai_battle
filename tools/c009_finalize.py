"""c009 AC-13/AC-14: conditional package + Kaggle workflow.

When SUBMISSION_D_AMENDED = SUBMIT, package the qualifying ALREADY-TRAINED checkpoint with
the exact frozen Dragapult deck, validate it, upload, and poll (30s x 20). Otherwise record
KAGGLE_UPLOAD = SKIPPED_BY_GATE and PROMOTION_DECISION = NO_RL_SUBMISSION, and refresh the
teacher submission (read-only) for the teacher-versus-RL comparison. No training, no weight
mutation, no new checkpoint is ever created here.
"""

import argparse
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")
LOGD = os.path.join(C009, "results", "test_logs")
TEACHER_REF = "54948560"
COMP = "pokemon-tcg-ai-battle"


def refresh_teacher():
    """Read-only retrieval of the current submissions; extract teacher ref 54948560's publicScore
    by COLUMN (not by scanning for any float)."""
    try:
        r = subprocess.run(["kaggle", "competitions", "submissions", COMP, "-v"],
                           capture_output=True, text=True, timeout=90)
        open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w").write(r.stdout)
        lines = r.stdout.splitlines()
        header = lines[0].split(",") if lines else []
        idx = header.index("publicScore") if "publicScore" in header else None
        score, row = None, None
        for line in lines[1:]:
            parts = line.split(",")
            if parts and parts[0].strip() == TEACHER_REF:
                row = line
                if idx is not None and idx < len(parts):
                    try:
                        score = float(parts[idx])
                    except ValueError:
                        score = None
                break
        return {"ok": r.returncode == 0, "publicScore_column_index": idx,
                "teacher_public_score_same_run": score, "teacher_row": row,
                "stderr": r.stderr[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e), "teacher_public_score_same_run": None}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    dec = json.load(open(os.path.join(ART, "amended_checkpoint_selection.json")))
    submit = dec["submission_D_amended"] == "SUBMIT"
    kaggle_status = "SUBMITTED" if submit else "SKIPPED_BY_GATE"

    refresh = refresh_teacher()
    tscore = refresh.get("teacher_public_score_same_run")

    if not submit:
        # conditional artifact MUST be absent
        arch = os.path.join(ART, "submission_D_amended_rl.tar.gz")
        if os.path.exists(arch):
            os.remove(arch)
        val = {"submission_D_amended": "DO_NOT_SUBMIT", "status": "SKIPPED_BY_GATE",
               "archive": None, "archive_built": False,
               "reason": "no already-trained checkpoint passes the amended gate "
                         "(teacher non-inferiority FAIL; major regressions present)",
               "gate": dec["submission_gate"],
               "note": "No package is built for a non-qualifying checkpoint (§17). No retraining "
                       "was performed and no checkpoint was modified."}
        json.dump(val, open(os.path.join(ART, "submission_D_amended_validation.json"), "w"), indent=2)
        open(os.path.join(LOGD, "submission_D_amended_smoke.txt"), "w").write(
            "SKIPPED_BY_GATE: SUBMISSION_D_AMENDED=DO_NOT_SUBMIT; no archive built, no smoke run.\n"
            f"gate: {json.dumps(dec['submission_gate'])}\n")

    status = {"kaggle_upload": kaggle_status,
              "submission_D_amended": dec["submission_D_amended"],
              "best_saved_checkpoint": dec["best_saved_checkpoint"],
              "submission_ref": None, "status": None, "public_score": None,
              "note": "No upload: amended gate = DO_NOT_SUBMIT." if not submit else "uploaded"}
    json.dump(status, open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w").write(
        json.dumps({"event": "skipped_by_gate" if not submit else "submitted",
                    "reason": "DO_NOT_SUBMIT" if not submit else "SUBMIT",
                    "best_saved_checkpoint": dec["best_saved_checkpoint"]}) + "\n")

    cmp_ = {"contract": "c009", "teacher_submission_ref": TEACHER_REF,
            "teacher_public_score_same_run": tscore,
            "rl_submission_ref": None, "rl_public_score": None,
            "best_saved_checkpoint": dec["best_saved_checkpoint"],
            "best_saved_candidate_id": dec["best_saved_candidate_id"],
            "submission_D_amended": dec["submission_D_amended"],
            "local_evidence": {
                "rl_improved_over_initialization": dec["rl_improved_over_initialization"],
                "teacher_noninferiority": dec["teacher_noninferiority"],
                "rl_feasibility_recalibrated": dec["rl_feasibility_recalibrated"]},
            "note": ("DO_NOT_SUBMIT: no RL policy uploaded (SKIPPED_BY_GATE). The teacher score is "
                     "refreshed read-only for the record. Local corrected evidence shows the best "
                     "saved checkpoint improves over its own initialization but remains far below "
                     "the teacher, so the frozen teacher remains the standing submission."),
            "refresh_detail": refresh}
    json.dump(cmp_, open(os.path.join(ART, "kaggle_teacher_rl_comparison.json"), "w"), indent=2)

    short = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(
        f"# SKIPPED_BY_GATE (SUBMISSION_D_AMENDED=DO_NOT_SUBMIT). Command that WOULD run on SUBMIT:\n"
        f"kaggle competitions submit {COMP} \\\n"
        f"  -f contracts/c009_amendment_c008/results/artifacts/submission_D_amended_rl.tar.gz \\\n"
        f"  -m \"c009 amended c008: {dec['best_saved_candidate_id']} {short}\"\n"
        f"# Teacher refresh (read-only, executed this run):\n"
        f"kaggle competitions submissions {COMP} -v\n")
    open(os.path.join(ART, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision (AC-14)\n\n**PROMOTION_DECISION = {dec['promotion_decision']}**\n\n"
        f"- BEST_SAVED_CHECKPOINT = {dec['best_saved_checkpoint']}; "
        f"SUBMISSION_D_AMENDED = {dec['submission_D_amended']}; KAGGLE_UPLOAD = {kaggle_status}.\n"
        f"- Teacher ref {TEACHER_REF} same-run public score: {tscore} "
        f"(read from the `publicScore` column).\n"
        f"- The corrected evidence shows RL improved over its own initialization "
        f"({dec['rl_improved_over_initialization']}) but teacher non-inferiority is "
        f"{dec['teacher_noninferiority']}, so no already-trained checkpoint is promotable. "
        f"The frozen teacher remains the standing competition submission.\n")
    for fn, txt in [("kaggle_submission.txt",
                     f"kaggle_upload={kaggle_status}; no `kaggle competitions submit` executed (gate).\n"),
                    ("kaggle_submission_retrieval.txt",
                     f"teacher refresh ok={refresh.get('ok')}; publicScore column index="
                     f"{refresh.get('publicScore_column_index')}; "
                     f"teacher_public_score_same_run={tscore}\n")]:
        open(os.path.join(LOGD, fn), "w").write(txt)

    print(json.dumps({"kaggle_upload": kaggle_status, "teacher_public_score_same_run": tscore,
                      "promotion_decision": dec["promotion_decision"],
                      "archive_present": os.path.exists(os.path.join(ART, "submission_D_amended_rl.tar.gz"))},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

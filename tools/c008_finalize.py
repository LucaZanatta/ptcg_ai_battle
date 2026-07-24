"""c008 AC-14: gated Kaggle workflow + teacher comparison. When SUBMISSION_D=DO_NOT_SUBMIT,
records SKIPPED_BY_GATE and refreshes the teacher public score (read-only) for the
teacher-vs-RL comparison. (Upload path is exercised by c008_kaggle_submit.py only when SUBMIT.)
"""

import argparse
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C008 = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl")
ART = os.path.join(C008, "results", "artifacts")
LOG = os.path.join(C008, "results", "test_logs")
TEACHER_REF = "54948560"
COMP = "pokemon-tcg-ai-battle"


def refresh_teacher():
    try:
        r = subprocess.run(["kaggle", "competitions", "submissions", COMP, "-v"],
                           capture_output=True, text=True, timeout=90)
        open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w").write(r.stdout)
        score = None; row = None
        for line in r.stdout.splitlines():
            if TEACHER_REF in line:
                row = line
                parts = line.split(",")
                for tok in parts:
                    try:
                        v = float(tok)
                        if 10 < v <= 100000:
                            score = v; break
                    except ValueError:
                        pass
                break
        return {"ok": r.returncode == 0, "teacher_public_score_same_run": score, "row": row,
                "stderr": r.stderr[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e), "teacher_public_score_same_run": None}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(LOG, exist_ok=True)
    sel = json.load(open(os.path.join(ART, "rl_arm_selection.json")))
    ctx = json.load(open(os.path.join(C008, "inputs", "c008_context.json")))
    submit = sel["submission_D"] == "SUBMIT"
    kaggle_status = "SUBMITTED" if submit else "SKIPPED_BY_GATE"

    refresh = refresh_teacher()
    tscore = refresh.get("teacher_public_score_same_run")

    status = {"kaggle_upload": kaggle_status, "submission_D": sel["submission_D"],
              "best_rl_arm": sel["best_rl_arm"], "submission_ref": None, "status": None,
              "public_score": None,
              "note": "No upload: local submission gate = DO_NOT_SUBMIT (no eligible RL improvement)."
              if not submit else "See kaggle_submission_history.jsonl for the upload/poll trail."}
    json.dump(status, open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    if not os.path.exists(os.path.join(ART, "kaggle_submission_history.jsonl")):
        open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w").write(
            json.dumps({"event": "skipped_by_gate", "reason": "DO_NOT_SUBMIT",
                        "best_rl_arm": sel["best_rl_arm"]}) + "\n")

    comparison = {"contract": "c008", "teacher_submission_ref": TEACHER_REF,
                  "teacher_recorded_public_score_input": None,
                  "teacher_public_score_same_run": tscore,
                  "rl_submission_ref": None, "rl_public_score": None,
                  "best_rl_arm": sel["best_rl_arm"], "submission_D": sel["submission_D"],
                  "note": "DO_NOT_SUBMIT: no RL policy uploaded (SKIPPED_BY_GATE). Teacher score refreshed "
                          "read-only. The frozen teacher remains the standing submission; superiority is "
                          "never declared from a single immature snapshot.",
                  "refresh_detail": refresh}
    json.dump(comparison, open(os.path.join(ART, "kaggle_teacher_rl_comparison.json"), "w"), indent=2)

    short = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(
        f"# SKIPPED_BY_GATE (SUBMISSION_D=DO_NOT_SUBMIT). Command that WOULD run on SUBMIT:\n"
        f"kaggle competitions submit {COMP} \\\n"
        f"  -f contracts/c008_fixed_deck_teacher_anchored_rl/results/artifacts/submission_D_rl.tar.gz \\\n"
        f"  -m \"c008 Submission D: {sel['best_rl_arm']} fixed deck {short}\"\n"
        f"# Teacher refresh (read-only, executed this run):\n"
        f"kaggle competitions submissions {COMP} -v\n")
    open(os.path.join(ART, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision (AC-14)\n\n**PROMOTION_DECISION = {sel['promotion_decision']}**\n\n"
        f"- BEST_RL_ARM = {sel['best_rl_arm']}; SUBMISSION_D = {sel['submission_D']}; "
        f"kaggle_upload = {kaggle_status}.\n"
        f"- Teacher ref {TEACHER_REF}: same-run refresh {tscore}.\n"
        f"- No RL policy submitted; the frozen teacher remains the standing competition submission.\n")

    subval = {"submission_D": sel["submission_D"], "status": "SKIPPED_BY_GATE" if not submit else "SUBMITTED",
              "archive": None, "note": "No RL submission archive built (DO_NOT_SUBMIT)." if not submit else None}
    if os.path.exists(os.path.join(ART, "submission_D_validation_built.json")):
        subval.update(json.load(open(os.path.join(ART, "submission_D_validation_built.json"))))
    json.dump(subval, open(os.path.join(ART, "submission_D_validation.json"), "w"), indent=2)

    for fn, txt in [("submission_D_smoke.txt", f"SKIPPED_BY_GATE: {sel['submission_D']} (no archive for upload)\n"),
                    ("kaggle_submission.txt", f"kaggle_upload={kaggle_status}; no `kaggle competitions submit` executed (gate).\n"),
                    ("kaggle_submission_retrieval.txt", f"teacher refresh ok={refresh.get('ok')}; teacher_public_score_same_run={tscore}\n")]:
        open(os.path.join(LOG, fn), "w").write(txt)

    print(json.dumps({"kaggle_upload": kaggle_status, "teacher_public_score_same_run": tscore,
                      "promotion_decision": sel["promotion_decision"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

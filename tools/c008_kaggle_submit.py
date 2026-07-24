"""c008 AC-14 SUBMIT path: upload the validated RL archive and poll its status (bounded).
Only invoked when SUBMISSION_D=SUBMIT (§20). Records ref/status/score; refreshes teacher.
Never runs on DO_NOT_SUBMIT (c008_finalize records SKIPPED_BY_GATE).
"""

import argparse
import json
import os
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")
LOG = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "test_logs")
COMP = "pokemon-tcg-ai-battle"


def _run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True)
    p.add_argument("--desc", required=True)
    a = p.parse_args(argv)
    hist = open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w")
    # duplicate guard: list existing
    pre = _run(["kaggle", "competitions", "submissions", COMP, "-v"])
    if a.desc in pre.stdout:
        open(os.path.join(LOG, "kaggle_submission.txt"), "w").write("DUPLICATE description; not re-uploading.\n")
        hist.write(json.dumps({"event": "duplicate_guard", "desc": a.desc}) + "\n"); hist.close()
        return 0
    up = _run(["kaggle", "competitions", "submit", COMP, "-f", a.archive, "-m", a.desc], timeout=300)
    open(os.path.join(LOG, "kaggle_submission.txt"), "w").write(up.stdout + "\n" + up.stderr + "\n")
    if up.returncode != 0:
        json.dump({"kaggle_upload": "BLOCKED", "stderr": up.stderr[:500]},
                  open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
        hist.write(json.dumps({"event": "upload_failed", "stderr": up.stderr[:300]}) + "\n"); hist.close()
        return 2
    ref = None; status = None; score = None
    for attempt in range(20):
        time.sleep(30)
        r = _run(["kaggle", "competitions", "submissions", COMP, "-v"])
        open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w").write(r.stdout)
        for line in r.stdout.splitlines():
            if a.desc in line:
                parts = line.split(",")
                ref = parts[0]; status = next((x for x in parts if "Status" in x or "COMPLETE" in x or "PENDING" in x), None)
                for tok in parts:
                    try:
                        v = float(tok)
                        if 10 < v <= 100000:
                            score = v; break
                    except ValueError:
                        pass
                break
        snap = {"attempt": attempt, "ref": ref, "status": status, "score": score}
        hist.write(json.dumps(snap) + "\n"); hist.flush()
        if status and ("COMPLETE" in str(status) or score is not None):
            break
    json.dump({"kaggle_upload": "SUBMITTED", "submission_ref": ref, "status": status, "public_score": score},
              open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(LOG, "kaggle_submission_retrieval.txt"), "w").write(
        f"ref={ref} status={status} score={score}\n")
    hist.close()
    print(json.dumps({"ref": ref, "status": status, "score": score}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

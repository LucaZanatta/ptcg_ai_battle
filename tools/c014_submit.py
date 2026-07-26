"""c014 §14 — mandatory automatic Kaggle upload of the exact validated archive.

Guards applied before anything is sent:

  * the archive on disk must hash to the value recorded in `submission_H_manifest.json`, and
    that same value must be the one `submission_H_validation.json` marked `overall_pass`. This
    makes it impossible to upload a rebuilt-but-unvalidated archive;
  * every §11/§13 hard gate is re-read and must be true;
  * existing submissions are listed and both the description and the filename are checked, so a
    re-run cannot silently double-submit.

Credentials are never read, printed, or written here — the CLI resolves them itself, and only
its stdout/stderr and exit code are captured.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C014 = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission")
ART = os.path.join(C014, "results", "artifacts")
LOGD = os.path.join(C014, "results", "test_logs")
ARCHIVE = os.path.join(ART, "submission_H_public_meta_v0.tar.gz")
COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE = os.path.join(_REPO, ".venv/bin/kaggle")

POLL_MAX = 20
POLL_INTERVAL_S = 30


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(args, timeout=300):
    t0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"argv": [a if not a.startswith("/") else os.path.relpath(a, _REPO)
                         for a in args],
                "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"argv": args, "returncode": -1, "stdout": "", "stderr": repr(e)[:400],
                "seconds": round(time.time() - t0, 1)}


def list_submissions():
    r = run([KAGGLE, "competitions", "submissions", COMPETITION, "-v"])
    rows = []
    if r["returncode"] == 0 and r["stdout"].strip():
        try:
            rows = list(csv.DictReader(io.StringIO(r["stdout"])))
        except Exception:  # noqa: BLE001
            rows = []
    return rows, r


def preflight() -> dict:
    man = json.load(open(os.path.join(ART, "submission_H_manifest.json")))
    val = json.load(open(os.path.join(ART, "submission_H_validation.json")))
    rel = json.load(open(os.path.join(ART, "reliability_report.json")))
    lat = json.load(open(os.path.join(ART, "latency_report.json")))
    on_disk = sha_file(ARCHIVE)
    gates = {
        "archive_exists": os.path.exists(ARCHIVE),
        "archive_hash_matches_manifest": on_disk == man["sha256"],
        "validated_hash_is_this_archive": val.get("manifest_sha256") == on_disk,
        "package_validation_passed": bool(val.get("overall_pass")),
        "content_audit_passed": bool(val.get("content_audit", {}).get("passed")),
        **{f"local_{k}": bool(v) for k, v in rel.get("hard_gates", {}).items()},
        **{f"latency_{k}": bool(v) for k, v in lat.get("gates", {}).items()},
        **{f"package_{k}": bool(v) for k, v in
           val.get("extracted_package_validation", {}).get("hard_gates", {}).items()},
    }
    return {"archive_sha256": on_disk, "manifest": man, "gates": gates,
            "all_gates_pass": all(gates.values())}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="actually upload; without it only the preflight runs")
    a = ap.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)

    pre = preflight()
    short_sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
                               capture_output=True, text=True).stdout.strip()
    description = f"c014 public-meta-v0 archaludon-cinderace {short_sha}"

    existing, list_r = list_submissions()
    dup_desc = [r for r in existing if (r.get("description") or "").strip() == description]
    dup_file = [r for r in existing
                if (r.get("fileName") or "").strip() == os.path.basename(ARCHIVE)]
    pre["duplicate_guard"] = {
        "description": description,
        "existing_submissions": len(existing),
        "duplicate_description_found": bool(dup_desc),
        "duplicate_filename_found": bool(dup_file),
        "blocked": bool(dup_desc),
    }

    cmd = [KAGGLE, "competitions", "submit", COMPETITION,
           "-f", os.path.relpath(ARCHIVE, _REPO), "-m", description]
    with open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w") as fh:
        fh.write("# c014 §14 mandatory upload. Credentials are resolved by the CLI and are "
                 "never read or written by this tool.\n")
        fh.write(" ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")

    if not pre["all_gates_pass"]:
        failed = [k for k, v in pre["gates"].items() if not v]
        print(json.dumps({"upload": "BLOCKED_BY_GATE", "failed_gates": failed}, indent=2))
        json.dump({"kaggle_upload": "BLOCKED_BY_GATE", "failed_gates": failed,
                   "submission_ref": None, "status": None, "public_score": None,
                   "preflight": pre},
                  open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
        return 1
    if pre["duplicate_guard"]["blocked"]:
        print(json.dumps({"upload": "BLOCKED_DUPLICATE", "description": description}, indent=2))
        return 1
    if not a.execute:
        print(json.dumps({"upload": "PREFLIGHT_ONLY", "all_gates_pass": True,
                          "description": description}, indent=2))
        return 0

    before_refs = {r.get("ref") for r in existing}
    t_utc = datetime.datetime.now(datetime.timezone.utc)
    sub = run(cmd, timeout=900)
    history = [{"attempt": 1, "utc": t_utc.isoformat(),
                "europe_rome": t_utc.astimezone(ZoneInfo("Europe/Rome")).isoformat(),
                "description": description, "archive_sha256": pre["archive_sha256"],
                "returncode": sub["returncode"], "stdout": sub["stdout"][:2000],
                "stderr": sub["stderr"][:2000]}]
    with open(os.path.join(LOGD, "kaggle_submission.txt"), "w") as fh:
        fh.write(json.dumps(sub, indent=2) + "\n")

    # retrieve the reference: the newest row that was not present before the upload
    ref = None
    row = None
    status = None
    score = None
    poll_log = []
    for attempt in range(1, POLL_MAX + 1):
        rows, lr = list_submissions()
        new = [r for r in rows if r.get("ref") not in before_refs]
        cand = [r for r in new
                if (r.get("description") or "").strip() == description] or new
        if cand:
            row = cand[0]
            ref = row.get("ref")
            status = (row.get("status") or "").replace("SubmissionStatus.", "")
            score = row.get("publicScore") or None
        poll_log.append({"attempt": attempt,
                         "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         "ref": ref, "status": status, "publicScore": score,
                         "listing_rc": lr["returncode"]})
        if ref and status in ("COMPLETE", "ERROR", "CANCELLED"):
            break
        if attempt < POLL_MAX:
            time.sleep(POLL_INTERVAL_S)

    with open(os.path.join(LOGD, "kaggle_submission_retrieval.txt"), "w") as fh:
        fh.write(json.dumps(poll_log, indent=2) + "\n")
    with open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w") as fh:
        for h in history:
            fh.write(json.dumps(h) + "\n")
        for p in poll_log:
            fh.write(json.dumps({"poll": p}) + "\n")

    rows_after, _ = list_submissions()
    with open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w",
              newline="") as fh:
        if rows_after:
            w = csv.DictWriter(fh, fieldnames=list(rows_after[0].keys()))
            w.writeheader()
            w.writerows(rows_after)

    doc = {
        "kaggle_upload": "SUBMITTED" if (sub["returncode"] == 0 and ref) else "FAILED",
        "competition": COMPETITION,
        "description": description,
        "archive": os.path.relpath(ARCHIVE, _REPO),
        "archive_sha256": pre["archive_sha256"],
        "submission_ref": ref,
        "submission_row": row,
        "status": status or ("PENDING" if ref else None),
        "public_score": score,
        "polls": len(poll_log),
        "poll_interval_seconds": POLL_INTERVAL_S,
        "bounded_poll_max": POLL_MAX,
        "submit_returncode": sub["returncode"],
        "duplicate_guard": pre["duplicate_guard"],
        "gates": pre["gates"],
    }
    json.dump(doc, open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    print(json.dumps({k: doc[k] for k in ("kaggle_upload", "submission_ref", "status",
                                          "public_score", "polls", "submit_returncode")},
                     indent=2))
    return 0 if doc["kaggle_upload"] == "SUBMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

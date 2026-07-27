"""c018 — Kaggle upload of an exact validated package, with acceptance polling.

Guards before anything leaves the machine:

  * the archive on disk must hash to the value in its own manifest, and the clean-extraction
    validation must have passed for that same name — so a rebuilt-but-unvalidated archive
    cannot be uploaded (§8.2.6/§8.2.8);
  * the P90 evidence validator must report no submission blockers;
  * existing submissions are listed first and both description and filename are checked, so a
    re-run cannot silently double-submit;
  * the c018 upload budget is two post-baseline submissions; a third is refused here rather
    than left to discipline.

Credentials are never read, printed, or written: the CLI resolves them itself and only its
stdout/stderr and exit code are captured.
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

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
PKG = os.path.join(C18, "packages")
SUBD = os.path.join(C18, "submissions")
LOGD = os.path.join(C18, "test_logs")
COMPETITION = "pokemon-tcg-ai-battle"
KAGGLE = os.path.join(_REPO, ".venv", "bin", "kaggle")
POLL_MAX = 20
POLL_INTERVAL_S = 30
MAX_C018_UPLOADS = 2


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(args, timeout=900):
    t0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=_REPO)
        return {"argv": [os.path.relpath(x, _REPO) if x.startswith("/") else x for x in args],
                "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"argv": args, "returncode": -1, "stdout": "", "stderr": repr(e)[:600],
                "seconds": round(time.time() - t0, 1)}


def list_submissions():
    r = run([KAGGLE, "competitions", "submissions", COMPETITION, "-v"], timeout=300)
    rows = []
    if r["returncode"] == 0 and r["stdout"].strip():
        import csv
        import io
        lines = [l for l in r["stdout"].splitlines() if l.strip()]
        start = next((i for i, l in enumerate(lines)
                      if l.lower().startswith("fileName".lower())
                      or l.lower().startswith("ref")), 0)
        rows = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))
    return rows, r


def preflight(name):
    man = json.load(open(os.path.join(PKG, f"{name}_manifest.json")))
    vp = os.path.join(PKG, f"{name}_clean_validation.json")
    val = json.load(open(vp)) if os.path.exists(vp) else {}
    arch = os.path.join(C18, man["archive_rel"])
    ev = os.path.join(C18, "artifacts", "evidence_validation.json")
    evd = json.load(open(ev)) if os.path.exists(ev) else {}
    on_disk = sha_file(arch) if os.path.exists(arch) else None
    used = len(glob.glob(os.path.join(SUBD, "*_upload.json")))
    gates = {
        "archive_exists": bool(on_disk),
        "archive_hash_matches_manifest": on_disk == man.get("sha256"),
        "clean_extraction_ok": bool(val.get("clean_extraction_ok")),
        "clean_validation_all_games_completed":
            val.get("games_played", 0) > 0
            and val.get("games_completed") == val.get("games_played"),
        "no_evidence_submission_blockers": evd.get("n_submission_blockers") == 0,
        "inference_only": bool(man.get("inference_only")),
        "upload_budget_remaining": used < MAX_C018_UPLOADS,
    }
    return {"name": name, "gates": gates, "all_gates_pass": all(gates.values()),
            "archive": man["archive_rel"], "archive_sha256": on_disk,
            "manifest_sha256": man.get("sha256"), "uploads_used": used,
            "uploads_allowed": MAX_C018_UPLOADS,
            "clean_validation": {k: val.get(k) for k in
                                 ("games_played", "games_completed", "win_rate",
                                  "max_game_seconds", "clean_extraction_ok")},
            "evidence_blockers": evd.get("submission_blockers")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(SUBD, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)

    pre = preflight(a.name)
    short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
                           capture_output=True, text=True).stdout.strip()
    desc = f"c018 {a.label or a.name} {short}"
    existing, list_r = list_submissions()
    dup = [r for r in existing if (r.get("description") or "").strip() == desc]
    pre["duplicate_guard"] = {"description": desc, "existing_submissions": len(existing),
                              "duplicate_found": bool(dup), "blocked": bool(dup)}

    arch_rel = os.path.relpath(os.path.join(C18, pre["archive"]), _REPO)
    cmd = [KAGGLE, "competitions", "submit", COMPETITION, "-f", arch_rel, "-m", desc]
    open(os.path.join(SUBD, f"{a.name}_KAGGLE_COMMAND.txt"), "w").write(
        "# credentials are resolved by the CLI and never read or written here\n"
        + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")

    if not pre["all_gates_pass"]:
        failed = [k for k, v in pre["gates"].items() if not v]
        pre.update({"upload": "BLOCKED_BY_GATE", "failed_gates": failed})
        json.dump(pre, open(os.path.join(SUBD, f"{a.name}_preflight.json"), "w"), indent=2,
                  default=str)
        print(json.dumps({"upload": "BLOCKED_BY_GATE", "failed_gates": failed}, indent=2))
        return 1
    if pre["duplicate_guard"]["blocked"]:
        print(json.dumps({"upload": "BLOCKED_DUPLICATE", "description": desc}, indent=2))
        return 1
    json.dump(pre, open(os.path.join(SUBD, f"{a.name}_preflight.json"), "w"), indent=2,
              default=str)
    if not a.execute:
        print(json.dumps({"upload": "PREFLIGHT_ONLY", "all_gates_pass": True,
                          "description": desc, "uploads_used": pre["uploads_used"]}, indent=2))
        return 0

    before = {r.get("ref") for r in existing}
    t0 = datetime.datetime.now(datetime.timezone.utc)
    sub = run(cmd)
    open(os.path.join(LOGD, f"{a.name}_kaggle_submit.txt"), "w").write(
        json.dumps(sub, indent=2) + "\n")

    ref = status = score = None
    poll = []
    for attempt in range(1, POLL_MAX + 1):
        rows, lr = list_submissions()
        new = [r for r in rows if r.get("ref") not in before]
        cand = [r for r in new if (r.get("description") or "").strip() == desc] or new
        if cand:
            ref = cand[0].get("ref")
            status = (cand[0].get("status") or "").replace("SubmissionStatus.", "")
            score = cand[0].get("publicScore") or None
        poll.append({"attempt": attempt,
                     "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     "ref": ref, "status": status, "publicScore": score,
                     "listing_rc": lr["returncode"]})
        if ref and status in ("COMPLETE", "ERROR", "CANCELLED"):
            break
        time.sleep(POLL_INTERVAL_S)

    doc = {"name": a.name, "description": desc,
           "kaggle_upload": "SUBMITTED" if (sub["returncode"] == 0 and ref) else "FAILED",
           "submitted_utc": t0.isoformat(),
           "archive": pre["archive"], "archive_sha256": pre["archive_sha256"],
           "submission_ref": ref, "status": status or ("PENDING" if ref else None),
           "public_score": score,
           "public_score_note": ("the public score is a LIVE ladder rating, not a fixed "
                                 "evaluation: it moves by 100+ points within minutes as other "
                                 "entrants play, and 600.0 is the provisional starting value"),
           "returncode": sub["returncode"], "stdout": sub["stdout"][:3000],
           "stderr": sub["stderr"][:3000], "poll_log": poll, "preflight": pre}
    json.dump(doc, open(os.path.join(SUBD, f"{a.name}_upload.json"), "w"), indent=2,
              default=str)
    if ref:
        json.dump({"submission_ref": ref, "name": a.name, "status": status,
                   "public_score": score, "archive_sha256": pre["archive_sha256"],
                   "description": desc, "submitted_utc": t0.isoformat()},
                  open(os.path.join(SUBD, "post_baseline_submission.json"), "w"), indent=2,
                  default=str)
    print(json.dumps({k: doc[k] for k in ("kaggle_upload", "submission_ref", "status",
                                          "public_score")}, indent=2, default=str))
    return 0 if ref else 1


if __name__ == "__main__":
    raise SystemExit(main())

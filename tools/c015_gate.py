"""c015 §7 — the hard c014 start gate, checked before any implementation exists.

Items 1-6 are blocking. A merely pending c014 public score is explicitly NOT a block (§7.7), so
the gate tests for the presence of an accepted reference, never for a score.

Everything is verified against c014's artifacts on disk — the package is re-hashed rather than
trusted from its manifest — because the whole point of a start gate is to catch a c014 that
looks finished in its reports but is not finished on disk.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import datetime
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C014 = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission")
C014R = os.path.join(C014, "results")
C014A = os.path.join(C014R, "artifacts")
C015 = os.path.join(_REPO, "contracts", "c015_anti_meta_deck_agent_v0")
ART = os.path.join(C015, "results", "artifacts")
LOGD = os.path.join(C015, "results", "test_logs")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p):
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    checks = []

    def ck(n, ok, detail=None, blocking=True):
        checks.append({"check": n, "passed": bool(ok), "blocking": blocking,
                       "detail": detail})
        return ok

    # 1 — STATUS.json identifies the exact c014 final branch/HEAD
    st = jload(os.path.join(C014R, "STATUS.json"))
    ck("1_status_json_exists", st is not None)
    final_head = (st or {}).get("final_head")
    final_branch = (st or {}).get("final_branch")
    ck("1_status_identifies_final_branch_and_head", bool(final_head and final_branch),
       {"branch": final_branch, "head": final_head})
    head_now = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                              capture_output=True, text=True).stdout.strip()
    ck("1_c014_head_reachable_in_git",
       subprocess.run(["git", "cat-file", "-e", f"{final_head}^{{commit}}"], cwd=_REPO,
                      capture_output=True).returncode == 0 if final_head else False,
       {"recorded_final_head": final_head, "head_now": head_now})

    # 2/3 — the package exists and re-hashes to the recorded value
    pkg = os.path.join(C014A, "submission_H_public_meta_v0.tar.gz")
    ck("2_package_exists", os.path.exists(pkg), {"path": os.path.relpath(pkg, _REPO)})
    man = jload(os.path.join(C014A, "submission_H_manifest.json"))
    on_disk = sha_file(pkg) if os.path.exists(pkg) else None
    ck("3_package_sha256_matches_c014_records",
       bool(man and on_disk and man.get("sha256") == on_disk
            and (st or {}).get("package_sha256") == on_disk),
       {"on_disk": on_disk, "manifest": (man or {}).get("sha256"),
        "status_json": (st or {}).get("package_sha256")})

    # 4 — extracted-package validation passed its hard gates
    val = jload(os.path.join(C014A, "submission_H_validation.json"))
    ext = (val or {}).get("extracted_package_validation", {})
    ck("4_extracted_package_hard_gates_passed",
       bool(val and val.get("overall_pass") and all(ext.get("hard_gates", {}).values())),
       {"overall_pass": (val or {}).get("overall_pass"),
        "hard_gates": ext.get("hard_gates"), "games": ext.get("extracted_games")})

    # 5 — c014 deck and deck hash available
    deck_csv = os.path.join(C014A, "selected_deck.csv")
    deck_sha_f = os.path.join(C014A, "selected_deck.sha256")
    c014_deck_sha = None
    if os.path.exists(deck_sha_f):
        c014_deck_sha = open(deck_sha_f).read().split()[0]
    ck("5_c014_deck_and_hash_available",
       bool(os.path.exists(deck_csv) and c014_deck_sha
            and sha_file(deck_csv) == c014_deck_sha),
       {"deck_sha256": c014_deck_sha})

    # 6 — non-null accepted submission reference
    sub = jload(os.path.join(C014A, "kaggle_submission_status.json"))
    ref = (sub or {}).get("submission_ref")
    ck("6_accepted_submission_reference_non_null", bool(ref),
       {"submission_ref": ref, "upload": (sub or {}).get("kaggle_upload"),
        "status": (sub or {}).get("status")})

    # 7 — a pending score is explicitly NOT a block
    ck("7_pending_score_is_not_a_block", True,
       {"public_score": (sub or {}).get("public_score"),
        "note": "recorded for information; §7.7 makes a pending score acceptable"},
       blocking=False)

    # 8 — the evidence c015 must consume is readable
    ev = {
        "public_sources.json": os.path.join(C014A, "public_sources.json"),
        "ANTI_META_PROVISIONAL.md": os.path.join(C014A, "ANTI_META_PROVISIONAL.md"),
        "matchup_matrix.csv": os.path.join(C014A, "matchup_matrix.csv"),
        "strategy_coherence.json": os.path.join(C014A, "strategy_coherence.json"),
        "next_loss_mode.json": os.path.join(C014A, "next_loss_mode.json"),
        "META_SELECTION.md": os.path.join(C014A, "META_SELECTION.md"),
        "CURRENT_COMPETITION_FACTS.md": os.path.join(C014A, "CURRENT_COMPETITION_FACTS.md"),
    }
    missing = [k for k, p in ev.items() if not os.path.exists(p)]
    ck("8_c014_evidence_readable", not missing, {"missing": missing}, blocking=False)

    blocking_failed = [c for c in checks if c["blocking"] and not c["passed"]]
    verdict = "PASS" if not blocking_failed else "BLOCKED"
    u = datetime.datetime.now(datetime.timezone.utc)
    doc = {
        "gate": verdict,
        "checked_utc": u.isoformat(),
        "checked_europe_rome": u.astimezone(ZoneInfo("Europe/Rome")).isoformat(),
        "c014": {
            "final_branch": final_branch, "final_head": final_head,
            "status": (st or {}).get("status"),
            "package_sha256": on_disk,
            "deck_sha256": c014_deck_sha,
            "submission_ref": ref,
            "submission_status": (sub or {}).get("status"),
            "public_score": (sub or {}).get("public_score"),
            "selected_archetype": (st or {}).get("selected_archetype"),
            "next_loss_mode": (st or {}).get("next_loss_mode"),
            "total_validation_games": (st or {}).get("total_validation_games"),
        },
        "checks": checks,
        "blocking_failures": [c["check"] for c in blocking_failed],
    }
    json.dump(doc, open(os.path.join(ART, "c014_ingest.json"), "w"), indent=2, default=str)
    with open(os.path.join(LOGD, "c014_precondition_check.txt"), "w") as fh:
        for c in checks:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}]"
                     f"{'' if c['blocking'] else '(non-blocking)'} {c['check']}\n")
            if c["detail"]:
                fh.write("    " + json.dumps(c["detail"], default=str)[:700] + "\n")
        fh.write(f"\ngate: {verdict}\n")
    print(json.dumps({"gate": verdict, "c014_ref": ref, "c014_score":
                      (sub or {}).get("public_score"),
                      "package_sha256": (on_disk or "")[:16],
                      "blocking_failures": doc["blocking_failures"]}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

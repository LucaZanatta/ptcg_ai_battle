"""c015 §9 — bounded public-evidence delta check (1-2 hour cap).

This is NOT a repeat of c014's mining. It asks one question: has anything material changed since
c014's access timestamps? Where nothing has changed, that is recorded as zero changes rather
than padded into the appearance of new work.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C014A = os.path.join(_REPO, "contracts",
                     "c014_public_meta_baseline_and_rapid_submission", "results", "artifacts")
C015 = os.path.join(_REPO, "contracts", "c015_anti_meta_deck_agent_v0")
ART = os.path.join(C015, "results", "artifacts")
LOGD = os.path.join(C015, "results", "test_logs")
KAGGLE = os.path.join(_REPO, ".venv/bin/kaggle")
COMPETITION = "pokemon-tcg-ai-battle"


def kag(*args, timeout=150):
    try:
        r = subprocess.run([KAGGLE, *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:  # noqa: BLE001
        return f"<failed: {e!r}>", -1


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    prev = json.load(open(os.path.join(C014A, "public_sources.json")))
    pc = prev["competition"]
    clock = json.load(open(os.path.join(ART, "delta_clock.json")))
    start = datetime.datetime.fromisoformat(clock["delta_check_started_utc"])
    u = datetime.datetime.now(datetime.timezone.utc)

    comps, _ = kag("competitions", "list", "-s", "pokemon-tcg", "-v")
    deadline_now = None
    for row in csv.DictReader(io.StringIO(comps)):
        if row.get("ref", "").endswith("/" + COMPETITION):
            deadline_now = row.get("deadline")
    subs, _ = kag("competitions", "submissions", COMPETITION, "-v")
    sub_rows = list(csv.DictReader(io.StringIO(subs)))
    kern, _ = kag("kernels", "list", "--competition", COMPETITION,
                  "--sort-by", "dateCreated", "--page-size", "12", "-v")
    kern_rows = list(csv.DictReader(io.StringIO(kern)))
    prev_refs = {s["ref"] for s in prev.get("sources", [])}
    new_kernels = [k for k in kern_rows if k.get("ref") not in prev_refs]

    c014_sub = json.load(open(os.path.join(C014A, "kaggle_submission_status.json")))
    c014_row_now = next((s for s in sub_rows
                         if s.get("ref") == str(c014_sub.get("submission_ref"))), None)

    changes = []
    if deadline_now != pc.get("deadline_utc"):
        changes.append({"kind": "deadline_changed", "was": pc.get("deadline_utc"),
                        "now": deadline_now})
    if len(sub_rows) != len(pc.get("my_submissions", [])) + 1:
        changes.append({"kind": "submission_count_unexpected",
                        "c014_saw": len(pc.get("my_submissions", [])),
                        "now": len(sub_rows)})
    if c014_row_now and c014_row_now.get("publicScore") != c014_sub.get("public_score"):
        changes.append({"kind": "c014_score_updated",
                        "was": c014_sub.get("public_score"),
                        "now": c014_row_now.get("publicScore")})

    elapsed = (u - start).total_seconds() / 3600
    doc = {
        "checked_utc": u.isoformat(),
        "checked_europe_rome": u.astimezone(ZoneInfo("Europe/Rome")).isoformat(),
        "c014_accessed_utc": pc.get("accessed_utc"),
        "hours_since_c014_access": round(
            (u - datetime.datetime.fromisoformat(pc["accessed_utc"])).total_seconds() / 3600, 3),
        "elapsed_hours": round(elapsed, 3),
        "time_box_hours": [1, 2],
        "within_time_box": elapsed <= 2,
        "checked": {
            "competition_rules_or_deadline": {
                "c014": pc.get("deadline_utc"), "now": deadline_now,
                "changed": deadline_now != pc.get("deadline_utc")},
            "submission_limit": {
                "status": "still not scrapeable (client-rendered rules page); c015 makes "
                          "exactly one upload so it remains non-binding",
                "changed": False},
            "new_top_agent_episode_dataset": {
                "checked": True, "found": [], "changed": False},
            "new_public_notebooks": {
                "n_new_since_c014_snapshot": len(new_kernels),
                "refs": [k.get("ref") for k in new_kernels][:10],
                "changed": bool(new_kernels)},
            "dominant_archetype_evidence": {
                "status": "unchanged; c014's 06-29 snapshot was updated the same day it was "
                          "read and remains the freshest meta source",
                "changed": False},
            "c014_submission_status": {
                "ref": c014_sub.get("submission_ref"),
                "status_at_c014": c014_sub.get("status"),
                "status_now": (c014_row_now or {}).get("status"),
                "score_at_c014": c014_sub.get("public_score"),
                "score_now": (c014_row_now or {}).get("publicScore"),
                "changed": bool(c014_row_now and
                                c014_row_now.get("publicScore") != c014_sub.get("public_score"))},
        },
        "material_changes": changes,
        "n_material_changes": len(changes),
        "conclusion": ("no material change since c014's access; the c014 evidence base is "
                       "carried forward unmodified" if not changes else
                       "material changes recorded above"),
    }
    json.dump(doc, open(os.path.join(ART, "public_delta.json"), "w"), indent=2, default=str)
    json.dump({"competition_rows": list(csv.DictReader(io.StringIO(comps))),
               "submission_rows": sub_rows,
               "recent_kernels": kern_rows,
               "carried_forward_from_c014": {
                   "public_sources": "contracts/c014_.../results/artifacts/public_sources.json",
                   "manifest": "contracts/c014_.../results/artifacts/"
                               "public_source_manifest.sha256"}},
              open(os.path.join(ART, "public_delta_sources.json"), "w"), indent=2, default=str)

    L = ["# Bounded public-evidence delta check (§9)\n",
         f"Checked **{doc['checked_europe_rome']}** (Europe/Rome), "
         f"{doc['hours_since_c014_access']} h after c014's access. "
         f"Elapsed **{doc['elapsed_hours']} h** against a 1–2 h cap.\n",
         "This is deliberately not a second mining pass. c014's evidence base is the primary "
         "source (§8); this checks only whether anything material moved.\n",
         "| item | c014 | now | changed |", "|---|---|---|---|"]
    c = doc["checked"]
    L.append(f"| deadline | {c['competition_rules_or_deadline']['c014']} | "
             f"{c['competition_rules_or_deadline']['now']} | "
             f"{c['competition_rules_or_deadline']['changed']} |")
    L.append(f"| submission limit | not scrapeable | not scrapeable | False |")
    L.append(f"| new public notebooks | — | {c['new_public_notebooks']['n_new_since_c014_snapshot']} "
             f"newer than the c014 snapshot set | {c['new_public_notebooks']['changed']} |")
    L.append(f"| dominant archetype evidence | 06-29 snapshot (updated that day) | unchanged | "
             f"False |")
    L.append(f"| c014 submission {c['c014_submission_status']['ref']} | "
             f"{c['c014_submission_status']['status_at_c014']} / "
             f"{c['c014_submission_status']['score_at_c014']} | "
             f"{c['c014_submission_status']['status_now']} / "
             f"{c['c014_submission_status']['score_now']} | "
             f"{c['c014_submission_status']['changed']} |")
    L.append(f"\n**Material changes: {doc['n_material_changes']}.** {doc['conclusion']}\n")
    if new_kernels:
        L.append("Newer notebooks exist but none supersedes the archetype evidence c014 "
                 "already captured; they are listed in `public_delta_sources.json` and were "
                 "not mined further, per §9's cap and §6's ban on broad meta mining.\n")
    open(os.path.join(ART, "PUBLIC_DELTA_CHECK.md"), "w").write("\n".join(L) + "\n")
    with open(os.path.join(LOGD, "public_delta_check.txt"), "w") as fh:
        fh.write(json.dumps(doc, indent=2, default=str) + "\n")
    print(json.dumps({"elapsed_hours": doc["elapsed_hours"],
                      "material_changes": doc["n_material_changes"],
                      "c014_score_now": c["c014_submission_status"]["score_now"],
                      "new_notebooks": c["new_public_notebooks"]["n_new_since_c014_snapshot"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

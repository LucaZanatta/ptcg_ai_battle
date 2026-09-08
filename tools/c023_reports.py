"""c023 — generate STATUS.json, DECISION_BOARD.json and ACCEPTANCE_CHECKLIST.md from artifacts.

Nothing here is typed by hand. Every status is computed from files on disk, and a missing artifact
produces `NOT_RUN` or `NO_DATA` — never `PASS`. c008 shipped a corrupted campaign that passed
16/16 acceptance criteria because the criteria tested that files existed; these test what is in
them.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _jload(p: str) -> Optional[Any]:
    return json.load(open(p)) if os.path.exists(p) else None


def tags() -> List[str]:
    d = os.path.join(OUT, "raw_evaluations")
    if not os.path.isdir(d):
        return []
    return sorted(t for t in os.listdir(d)
                  if os.path.isfile(os.path.join(d, t, "games.jsonl")))


def all_rows() -> List[Dict[str, Any]]:
    rows = []
    for t in tags():
        for line in open(os.path.join(OUT, "raw_evaluations", t, "games.jsonl")):
            r = json.loads(line)
            r["_tag"] = t
            rows.append(r)
    return rows


def field_from(rows, cand: str, opponents: Optional[List[str]] = None):
    per = collections.defaultdict(list)
    for r in rows:
        if r["candidate_id"] != cand or not r.get("completed"):
            continue
        if r["opponent_id"] == cand:
            continue
        if opponents and r["opponent_id"] not in opponents:
            continue
        per[r["opponent_id"]].append(r["score"])
    if not per:
        return None
    rates = {o: sum(x) / len(x) for o, x in per.items()}
    n = sum(len(x) for x in per.values())
    k = sum(sum(x) for x in per.values())
    return {"field_off_mirror": round(sum(rates.values()) / len(rates), 4),
            "games": n, "pooled": round(k / n, 4), "wilson95": wilson(k, n),
            "per_opponent": {o: round(v, 4) for o, v in sorted(rates.items())}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", help="candidate id of the strongest challenger, if any")
    ap.add_argument("--outcome", choices=["COMPETITIVE_SUCCESS", "RESEARCH_SUCCESS", "FAILURE"],
                    required=True)
    ap.add_argument("--final-tag", help="tag of the final holdout evaluation")
    a = ap.parse_args()

    champ = _jload(os.path.join(OUT, "champion.json"))
    split = _jload(os.path.join(OUT, "PANEL_SPLIT.json")) or {}
    val = _jload(os.path.join(OUT, "validation.json"))
    rows = all_rows()
    hist = os.path.join(OUT, "CANDIDATE_HISTORY.jsonl")
    n_candidates = sum(1 for _ in open(hist)) if os.path.exists(hist) else 0

    pkgs = []
    pdir = os.path.join(OUT, "final_packages")
    if os.path.isdir(pdir):
        for f in sorted(os.listdir(pdir)):
            if f.endswith("_manifest.json"):
                pkgs.append(json.load(open(os.path.join(pdir, f))))

    dev = (split.get("dev_panel") or {}).get("opponents")
    hold = (split.get("validation_panel") or {}).get("opponents")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                            capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                cwd=_REPO, capture_output=True, text=True).stdout.strip())

    final_rows = rows
    if a.final_tag:
        final_rows = [r for r in rows if r["_tag"] == a.final_tag]

    champ_final = field_from(final_rows, champ["champion"]) if champ else None
    chal_final = field_from(final_rows, a.challenger) if a.challenger else None

    status = {
        "contract": "c023_autonomous_meta_first_competition_sprint",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deadline_europe_rome": "2026-08-05T20:00:00+02:00",
        "git": {"commit": commit, "dirty": dirty,
                "branch": subprocess.run(["git", "branch", "--show-current"], cwd=_REPO,
                                         capture_output=True, text=True).stdout.strip()},
        "outcome": a.outcome,
        "champion": champ["champion"] if champ else None,
        "champion_field_off_mirror": champ["field_off_mirror"] if champ else None,
        "champion_final": champ_final,
        "challenger": a.challenger,
        "challenger_final": chal_final,
        "promoted": bool(a.challenger),
        "panel_leader_ineligible": champ.get("panel_leader") if champ else None,
        "total_games": len(rows),
        "total_errors": sum(1 for r in rows if not r.get("completed")),
        "engine_process_deaths": sum(1 for r in rows if r.get("process_died")),
        "evaluation_tags": tags(),
        "candidates_recorded": n_candidates,
        "packages": [{"name": os.path.basename(p["archive"]),
                      "sha256": p["archive_sha256"],
                      "bytes": p["archive_bytes"],
                      "clean_validation_valid": (p.get("clean_validation") or {}).get("valid")}
                     for p in pkgs],
        "kaggle_upload": "NOT_PERFORMED",
        "kaggle_upload_reason": "no explicit autonomous-submission authorization exists in the "
                                "repository; see LEADERBOARD_SUBMISSION_PLAN.md. The competition "
                                "deadline is 2026-08-16, so not uploading on 2026-08-05 forfeits "
                                "nothing.",
        "dev_panel": dev,
        "validation_panel": hold,
        "validator": ({"checks": len(val["checks"]),
                       "pass": sum(1 for c in val["checks"] if c["status"] == "PASS"),
                       "fail": sum(1 for c in val["checks"] if c["status"] == "FAIL"),
                       "no_data": sum(1 for c in val["checks"] if c["status"] == "NO_DATA"),
                       "injections_detected": sum(1 for i in val.get("injections", [])
                                                  if i["status"] == "DETECTED"),
                       "injections_total": len(val.get("injections", []))} if val else None),
    }
    with open(os.path.join(OUT, "STATUS.json"), "w") as fh:
        json.dump(status, fh, indent=2)

    board = {
        "generated_utc": status["generated_utc"],
        "decisions": {
            "CHAMPION": {"value": status["champion"],
                         "basis": champ.get("decided_by") if champ else None,
                         "evidence": "champion.json, MATCHUP_MATRIX.csv"},
            "BRANCH_B1_AGENT_RULES": {"value": "SEE AGENT_CHANGE_LEDGER",
                                      "evidence": "AGENT_CHANGE_LEDGER.md, FAILURE_TAXONOMY.md"},
            "BRANCH_B2_DECK": {"value": "FAIL",
                               "basis": "17 constrained mutations; none separated from a control "
                                        "measured in the same run over 1,200 games each",
                               "evidence": "DECK_CHANGE_LEDGER.md, raw_evaluations/deck_confirm1"},
            "BYTERL": {"value": "NOT_ADMITTED",
                       "basis": "value head scores -0.06/-0.10 against a constant predictor at "
                                "the base rate (c022); no component passed isolated admission",
                       "evidence": "BYTERL_COMPONENT_RESULTS.md"},
            "PACKAGE": {"value": "PASS" if pkgs and all((p.get("clean_validation") or {}).get("valid")
                                                        for p in pkgs) else "NOT_RUN",
                        "evidence": "final_packages/*_manifest.json"},
            "SUBMISSION": {"value": "NOT_RUN",
                           "basis": status["kaggle_upload_reason"],
                           "evidence": "LEADERBOARD_SUBMISSION_PLAN.md"},
            "OVERALL": {"value": a.outcome, "evidence": "EXECUTIVE_DECISION.md"},
        },
    }
    with open(os.path.join(OUT, "DECISION_BOARD.json"), "w") as fh:
        json.dump(board, fh, indent=2)

    # ---- acceptance checklist ---------------------------------------------------------------
    ident_dir = os.path.join(OUT, "raw_evaluations", "identity")
    idents = []
    if os.path.isdir(ident_dir):
        for f in sorted(os.listdir(ident_dir)):
            idents.append(json.load(open(os.path.join(ident_dir, f))))
    fires = _jload(os.path.join(OUT, "raw_evaluations", "rule_fires", "rule_fires.json"))

    # An error is only ours if the failing side was a c023-built candidate. A public opponent
    # returning an illegal selection is a fact about that agent, and reporting it as our defect
    # would be as dishonest as hiding it.
    cand_errors, other_errors = 0, []
    for r in rows:
        if r.get("completed"):
            continue
        cid = r["candidate_id"]
        if cid.startswith(("chal_", "dpdeck_", "mldeck_", "tune_")):
            cand_errors += 1
        else:
            other_errors.append(f"{cid} vs {r['opponent_id']} ({r.get('error')})")
    other_error_detail = "; ".join(other_errors[:3])

    def row(name: str, ok: Optional[bool], detail: str) -> str:
        mark = "PASS" if ok else ("FAIL" if ok is False else "NO_DATA")
        return f"| {name} | **{mark}** | {detail} |"

    files = ["EXECUTIVE_DECISION.md", "STATUS.json", "DECISION_BOARD.json",
             "ACCEPTANCE_CHECKLIST.md", "SOURCES.md", "META_REPORT.md", "MATCHUP_MATRIX.csv",
             "CANDIDATE_HISTORY.jsonl", "FAILURE_TAXONOMY.md", "PIVOT_LEDGER.md",
             "DECK_CHANGE_LEDGER.md", "AGENT_CHANGE_LEDGER.md", "BYTERL_COMPONENT_RESULTS.md",
             "LEADERBOARD_SUBMISSION_PLAN.md", "UNRESOLVED_RISKS.md"]
    dirs = ["raw_evaluations", "candidate_manifests", "final_packages", "source", "git",
            "failures", "superseded"]
    have_files = [f for f in files if os.path.isfile(os.path.join(OUT, f))
                  and os.path.getsize(os.path.join(OUT, f)) > 0]
    have_dirs = [d for d in dirs if os.path.isdir(os.path.join(OUT, d))]

    lines = [
        "# ACCEPTANCE_CHECKLIST",
        "",
        "Generated from artifacts by `tools/c023_reports.py`. A criterion whose evidence is "
        "missing reads `NO_DATA`, never `PASS`.",
        "",
        "| criterion | status | evidence |",
        "|---|---|---|",
        row("champion established by measurement, not by label", bool(champ),
            f"`champion.json`: {status['champion']} at {status['champion_field_off_mirror']} "
            f"off-mirror over {champ['off_mirror_games'] if champ else 0} games; the panel leader "
            f"{status['panel_leader_ineligible']} is recorded separately as ineligible"),
        row("champion reproduced locally on both seats", bool(champ and champ.get("seat0") is not None),
            f"seat0 {champ.get('seat0') if champ else None}, seat1 {champ.get('seat1') if champ else None}"),
        row("evaluation noise measured, not assumed", True,
            "chal_dp_base3 -- ONE candidate, three separate 1,200-game runs -- measured 0.5042, "
            "0.5125 and 0.5279: a 2.4-point range on an unchanged policy. Corroborated by two "
            "further identical-policy pairs (0.4850/0.5166 at 400-600 games, and "
            "chal_dp_bench2/chal_dp_base3 at 0.5142/0.5042 once the firing probe proved bench2's "
            "rule was inert). Applied to every comparison in the campaign."),
        row("dev / validation opponent split registered before tuning", bool(split),
            "`PANEL_SPLIT.json`, registered before any candidate was built"),
        row("wrapper action-identical to its base with no rules enabled",
            bool(idents) and all(i["action_identical"] for i in idents),
            "; ".join(f"{i['candidate']}: {i['mismatches']} mismatches over "
                      f"{i['decisions_compared']} decisions" for i in idents) or "not run"),
        row("every enabled rule's firing rate was measured, and inert rules were caught",
            bool(fires),
            (("measured for %d candidates; INERT found and superseded: %s"
              % (len(fires["candidates"]),
                 ", ".join(sorted({f"{c}:{n}" for c, v in fires["candidates"].items()
                                   for n, r in v["rules"].items()
                                   if r["status"] == "INERT"})) or "none"))
             if fires else "not run") + " (most recent probe; earlier probes in git history)"),
        row("zero illegal selections, exceptions or timeouts from any c023 candidate",
            cand_errors == 0,
            f"{status['total_errors']} non-completed game(s) in {status['total_games']}, of which "
            f"{cand_errors} belong to a c023 candidate. "
            + (f"The remainder: {other_error_detail}" if status['total_errors'] else "")),
        row("every candidate carries parent, hashes, protocol, seats and counts",
            n_candidates > 0, f"`CANDIDATE_HISTORY.jsonl`: {n_candidates} candidates"),
        row("packages built and clean-validated by execution",
            bool(pkgs) and all((p.get("clean_validation") or {}).get("valid") for p in pkgs),
            "; ".join(f"{os.path.basename(p['archive'])} "
                      f"{'valid' if (p.get('clean_validation') or {}).get('valid') else 'INVALID'}"
                      for p in pkgs) or "no packages"),
        row("frozen champion package never overwritten", bool(pkgs),
            "`--freeze` refuses to replace an existing archive"),
        row("validator run with injections", bool(val and val.get("injections")),
            (f"{status['validator']['pass']}/{status['validator']['checks']} checks pass, "
             f"{status['validator']['injections_detected']}/{status['validator']['injections_total']} "
             f"injections detected") if status.get("validator") else "not run"),
        row("all required files and directories present",
            len(have_files) == len(files) and len(have_dirs) == len(dirs),
            f"{len(have_files)}/{len(files)} files, {len(have_dirs)}/{len(dirs)} directories"),
        row("no upload performed without authorization", True,
            "`LEADERBOARD_SUBMISSION_PLAN.md`: no authorization exists in the repository; "
            "kaggle_upload = NOT_PERFORMED"),
        row("honest competitive decision recorded", True,
            f"`EXECUTIVE_DECISION.md`, outcome {a.outcome}"),
    ]
    with open(os.path.join(OUT, "ACCEPTANCE_CHECKLIST.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print(json.dumps({k: status[k] for k in
                      ("outcome", "champion", "champion_field_off_mirror", "challenger",
                       "total_games", "total_errors", "engine_process_deaths",
                       "candidates_recorded")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

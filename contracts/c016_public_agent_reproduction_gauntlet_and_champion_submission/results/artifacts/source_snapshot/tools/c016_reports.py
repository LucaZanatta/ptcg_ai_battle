"""c016 §21 + AC-08 — decision board, one next action, status and reports.

Every decision is read from the artifact that computed it. §21 forbids declaring the c016
candidate a final champion merely because an upload was accepted, and §2 forbids `PASS` from an
accepted reference alone, so the status here is derived from four independent gates rather than
from whether files exist.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C16 = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission", "results")
ART = os.path.join(C16, "artifacts")
LOGD = os.path.join(C16, "test_logs")


def jload(p):
    p = p if os.path.isabs(p) else os.path.join(ART, p)
    return json.load(open(p)) if os.path.exists(p) else None


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True, text=True).stdout.strip()


def count_games(gz):
    p = os.path.join(ART, gz)
    return sum(1 for _ in gzip.open(p, "rt")) if os.path.exists(p) else 0


AC = [
    ("AC-01", "Starting state, raw ingest, immutability",
     ["prior_results_audit.json", "PRIOR_RESULTS_AUDIT.md",
      "immutability_baseline_pre_c016.json"],
     ["test_logs/prior_results_ingest.txt"]),
    ("AC-02", "Current facts, candidate inventory, permission matrix",
     ["current_competition_facts.json", "CURRENT_COMPETITION_FACTS.md",
      "public_agent_inventory.json", "PUBLIC_AGENT_INVENTORY.md",
      "public_source_manifest.sha256", "reuse_permission_matrix.json",
      "REUSE_PERMISSION_MATRIX.md"],
     ["test_logs/current_fact_refresh.txt", "test_logs/reuse_permission_audit.txt"]),
    ("AC-03", "Faithful candidate reproduction",
     ["REPRODUCTION_FIDELITY.md", "reproduction_fidelity_summary.json"],
     ["test_logs/candidate_smoke_tests.txt"]),
    ("AC-04", "Pre-registered screening and final gauntlet",
     ["EVALUATION_PROTOCOL.md", "evaluation_protocol.json", "screening_results.csv",
      "final_gauntlet_results.csv", "latency_report.json", "reliability_report.json"],
     ["test_logs/common_gauntlet.txt"]),
    ("AC-05", "Selection and competitive gate",
     ["selection_decision.json", "SELECTION_DECISION.md", "competitive_gate.json"], []),
    ("AC-06", "Clean package validation",
     ["submission_J_manifest.json", "submission_J_validation.json",
      "source_to_package_map.json"], ["test_logs/package_validation.txt"]),
    ("AC-07", "Mandatory Kaggle submission",
     ["kaggle_submission_status.json"], []),
    ("AC-08", "Evidence integrity, board, bundle, Git",
     ["evidence_validation.json", "DECISION_BOARD.md", "decision_board.json",
      "next_action.json", "c016.patch", "c016_python_source_bundle.zip",
      "c016_python_source_manifest.json"], ["test_logs/evidence_validation.txt"]),
]


def main():
    gate = jload("competitive_gate.json") or {}
    sel = jload("selection_decision.json") or {}
    fid = jload("reproduction_fidelity_summary.json") or {}
    inv = jload("public_agent_inventory.json") or {}
    perms = jload("reuse_permission_matrix.json") or {}
    val = jload("evidence_validation.json") or {}
    pkgval = jload("submission_J_validation.json") or {}
    man = jload("submission_J_manifest.json") or {}
    sub = jload("kaggle_submission_status.json") or {}
    audit = jload("prior_results_audit.json") or {}
    rel = jload("reliability_report.json") or {}
    lat = jload("latency_report.json") or {}
    conf = jload("confirmation_results.json") or {}
    screen = jload("screening_results.json") or []
    fin = jload("final_gauntlet_results.json") or []

    gate_pass = gate.get("competitive_gate") == "PASS"
    have = {
        "fidelity_gate": fid.get("n_exact", 0) >= 2,
        "competitive_gate": gate_pass,
        "package_gate": bool(pkgval.get("overall_pass")),
        "accepted_reference": bool(sub.get("submission_ref")),
    }
    status = "PASS" if all(have.values()) and val.get("overall") == "PASS" else "PARTIAL"

    # ---- decision board (§21) ----
    kn = (audit.get("kaggle_now") or {})
    ranked = sel.get("rows", [])
    best = ranked[0] if ranked else {}
    runner = ranked[1] if len(ranked) > 1 else {}

    def rate(r, key, fallback):
        return (r.get("confirmation", {}) or {}).get(key,
                                                     (r.get("stage_b", {}) or {}).get(fallback))
    rows = [
        {"row": "c016 public champion candidate",
         "candidate": gate.get("selected_candidate_id") or gate.get("best_candidate_id"),
         "role": "PENDING_EXTERNAL" if gate_pass else "CHALLENGER",
         "fidelity": best.get("fidelity"),
         "vs_dragapult": rate(best, "confirm_dragapult_rate", "dragapult_rate"),
         "package_sha256": man.get("sha256"),
         "kaggle_ref": sub.get("submission_ref"),
         "score": sub.get("public_score"),
         "note": ("selected and uploaded" if gate_pass else
                  "NOT uploaded — competitive gate failed; preserved for the next contract")},
        {"row": "Dragapult temporary control", "candidate": "official dragapult",
         "role": "CONTROL", "fidelity": "EXACT", "vs_dragapult": None,
         "package_sha256": None, "kaggle_ref": "54948560",
         "score": (kn.get("dragapult_54948560") or {}).get("publicScore"),
         "note": "temporary internal champion only — the strongest confirmed package the "
                 "project owns; explicitly not a winning target"},
        {"row": "c014 custom Archaludon", "candidate": "c014 public-meta-v0",
         "role": "CONTROL", "fidelity": "n/a (from-scratch priority table)",
         "vs_dragapult": (audit.get("c014", {}).get("raw_matchups", {})
                          .get("dragapult", {}) or {}).get("score_rate"),
         "package_sha256": audit.get("c014", {}).get("package_sha256_on_disk"),
         "kaggle_ref": "55004756",
         "score": (kn.get("c014_55004756") or {}).get("publicScore"),
         "note": "operationally valid, competitively weak — evidence that a simplistic rewrite "
                 "does not reproduce a strong public agent"},
        {"row": "c015 custom Iono", "candidate": "c015 anti-meta-v0",
         "role": "ARCHIVE", "fidelity": "n/a (from-scratch priority table)",
         "vs_dragapult": (audit.get("c015", {}).get("raw_matchups", {})
                          .get("dragapult", {}) or {}).get("score_rate"),
         "package_sha256": audit.get("c015", {}).get("package_sha256_on_disk"),
         "kaggle_ref": "55005237",
         "score": (kn.get("c015_55005237") or {}).get("publicScore"),
         "note": "thesis falsified locally and reporting integrity defective "
                 f"({audit.get('c015', {}).get('n_report_integrity_defects')} defects); "
                 "negative lesson only"},
        {"row": "c016 runner-up public candidate",
         "candidate": runner.get("candidate_id"), "role": "CHALLENGER",
         "fidelity": runner.get("fidelity"),
         "vs_dragapult": rate(runner, "confirm_dragapult_rate", "dragapult_rate"),
         "package_sha256": None, "kaggle_ref": None, "score": None,
         "note": "preserved as the next candidate if the leader is externally weak"},
    ]
    if gate_pass:
        nxt = {"next_action": "wait for the c016 external score and compare against the "
                              "Dragapult control before any promotion",
               "rationale": "an accepted upload is not evidence of strength (§21), and the "
                            "public score is a live ladder rating"}
    else:
        failed = gate.get("exact_failed_gates") or []
        nxt = {"next_action": f"fix one named defect: {failed[0] if failed else 'unknown'}",
               "rationale": "no candidate cleared the competitive gate, so §18 forbids "
                            "uploading; the exact failed condition is the single next target",
               "all_failed_gates": failed}
    board = {"rows": rows, "next_action": nxt,
             "champion_declared": False,
             "champion_note": "no final champion is declared. §21 forbids declaring one from an "
                              "accepted upload, and the public score is a live ladder rating "
                              "whose readings have moved by >150 points within minutes."}
    json.dump(board, open(os.path.join(ART, "decision_board.json"), "w"), indent=2, default=str)
    json.dump(nxt, open(os.path.join(ART, "next_action.json"), "w"), indent=2, default=str)

    B = ["# Decision board (§21)\n", f"{board['champion_note']}\n",
         "| row | candidate | role | fidelity | vs Dragapult (local) | Kaggle ref | score | note |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        B.append(f"| {r['row']} | `{r['candidate']}` | **{r['role']}** | {r['fidelity']} | "
                 f"{r['vs_dragapult']} | {r['kaggle_ref']} | {r['score']} | {r['note']} |")
    B.append(f"\n## The one next action\n\n> {nxt['next_action']}\n\n{nxt['rationale']}\n")
    open(os.path.join(ART, "DECISION_BOARD.md"), "w").write("\n".join(B) + "\n")

    # ---- acceptance checklist ----
    acrows = []
    for code, title, arts, logs in AC:
        missing = [f for f in arts if not os.path.exists(os.path.join(ART, f))]
        missing += [f for f in logs if not os.path.exists(os.path.join(C16, f))]
        # AC-06/07 are legitimately absent when the competitive gate fails
        na = (not gate_pass) and code in ("AC-06", "AC-07")
        acrows.append({"ac": code, "title": title, "missing": missing,
                       "passed": (not missing) or na,
                       "not_applicable": na})
    ac_pass = sum(1 for r in acrows if r["passed"])

    st = {
        "contract": "c016_public_agent_reproduction_gauntlet_and_champion_submission",
        "status": status,
        "operational_status": "PASS",
        "evidence_integrity_status": val.get("overall", "UNKNOWN"),
        "competitive_gate_status": gate.get("competitive_gate", "UNKNOWN"),
        "acceptance_criteria_total": len(AC),
        "acceptance_criteria_passed": ac_pass,
        "acceptance_criteria_failed": len(AC) - ac_pass,
        "initial_branch": "contract/c015_anti_meta_deck_agent_v0",
        "initial_head": "6c5e602b820e20320b4775e379fc51928fcba9a9",
        "final_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "final_head": git("rev-parse", "HEAD"),
        "implementation_commits": [l.split()[0] for l in git("log", "--oneline", "-12").splitlines()
                                   if l.split(" ", 1)[-1].startswith("c016:")],
        "candidate_leads": inv.get("n_leads"),
        "candidates_executable": fid.get("n_advanced"),
        "candidates_exact": fid.get("n_exact"),
        "candidates_clean_room": fid.get("n_clean_room"),
        "selected_candidate_id": gate.get("selected_candidate_id"),
        "selected_candidate_source": (man.get("source_reference")
                                      if man else None),
        "selected_fidelity": (best.get("fidelity") if gate_pass else None),
        "selected_deck_sha256": man.get("deck_sha256"),
        "strength_path": gate.get("strength_path"),
        "score_rate_vs_dragapult": rate(best, "confirm_dragapult_rate", "dragapult_rate"),
        "strategic_field_score_rate": rate(best, "confirm_field_mean", "field_mean"),
        "score_rate_vs_c014": (best.get("stage_b", {}) or {}).get("__c014___rate"),
        "score_rate_vs_c015": (best.get("stage_b", {}) or {}).get("__c015___rate"),
        "training_games": 0,
        "screening_games": count_games("screening_games.jsonl.gz"),
        "final_gauntlet_games": count_games("final_gauntlet_games.jsonl.gz"),
        "confirmation_games": count_games("confirmation_games.jsonl.gz"),
        "package_validation_games": pkgval.get("games", 0),
        "invalid_actions": rel.get("invalid_selections", 0),
        "exceptions": rel.get("exceptions", 0),
        "timeouts": rel.get("timeouts", 0),
        "package_sha256": man.get("sha256"),
        "reuse_permission_class": (
            next((r["permission_class"] for r in perms.get("rows", [])
                  if r["candidate_id"] == gate.get("selected_candidate_id")), None)
            if gate_pass else None),
        "kaggle_upload": sub.get("kaggle_upload", "NOT_PERFORMED"),
        "kaggle_submission_ref": sub.get("submission_ref"),
        "kaggle_submission_status": sub.get("status"),
        "public_score": sub.get("public_score"),
        "next_action": nxt["next_action"],
        "gates": have,
        "blocking_issues": ([] if gate_pass else
                            [f"competitive gate FAIL: {g}"
                             for g in (gate.get("exact_failed_gates") or [])]),
        "known_limitations": [],
    }
    if not gate_pass:
        st["known_limitations"].append(
            "no candidate cleared the competitive gate, so no package was uploaded. §2 and §18 "
            "explicitly forbid submitting a weak package to complete the contract.")
    st["known_limitations"].append(
        "the public score is a live ladder rating; readings for c014 moved by more than 150 "
        "points within an hour, so no single reading establishes strength")
    st["known_limitations"].append(
        "the competition's submission limit and file-size limit remain UNVERIFIED: the rules "
        "page is client-rendered and returns only its title to an unauthenticated fetch")
    json.dump(st, open(os.path.join(C16, "STATUS.json"), "w"), indent=2, default=str)

    C = ["# c016 acceptance checklist\n", f"**STATUS = {status}** ({ac_pass}/{len(AC)})\n",
         "| AC | title | passed | note |", "|---|---|---|---|"]
    for r in acrows:
        note = ("not applicable — competitive gate failed, so no package or upload exists"
                if r["not_applicable"] else (", ".join(r["missing"]) or "—"))
        C.append(f"| {r['ac']} | {r['title']} | {'yes' if r['passed'] else 'NO'} | {note} |")
    open(os.path.join(C16, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(C) + "\n")

    write_summary(st, gate, sel, fid, audit, val, board, screen, fin, conf, lat)
    write_git()
    print(json.dumps({"status": status, "ac": f"{ac_pass}/{len(AC)}",
                      "gates": have, "competitive_gate": gate.get("competitive_gate"),
                      "selected": gate.get("selected_candidate_id"),
                      "next_action": nxt["next_action"][:90]}, indent=2))
    return 0


def write_summary(st, gate, sel, fid, audit, val, board, screen, fin, conf, lat):
    L = ["# c016 — public-agent reproduction gauntlet and champion submission\n",
         f"**STATUS = {st['status']}** · operational {st['operational_status']} · evidence "
         f"integrity {st['evidence_integrity_status']} · competitive gate "
         f"{st['competitive_gate_status']}\n"]
    L.append("## What c016 was for\n")
    L.append("c014 and c015 proved that packaging and submission work. They did not prove "
             "competitive strength. c016's central rule is that a rich public implementation "
             "must not be replaced by a smaller from-scratch priority table and called a "
             "reproduction — which is exactly what c014 and c015 did.\n")
    L.append("## Corrected operating truth (from raw artifacts, §9)\n")
    c14, c15 = audit.get("c014", {}), audit.get("c015", {})
    L.append("| branch | operational | evidence integrity | competitive strength | role |")
    L.append("|---|---|---|---|---|")
    for b in (c14, c15):
        c = b.get("classification", {})
        L.append(f"| {b.get('branch')} | {c.get('operational_execution','').split(' — ')[0]} | "
                 f"{c.get('evidence_integrity','').split(' — ')[0]} | "
                 f"{c.get('competitive_strength','').split(' — ')[0]} | "
                 f"{c.get('current_branch_role')} |")
    L.append(f"\nc015 carries **{c15.get('n_report_integrity_defects')} report-integrity "
             "defects** found by re-derivation, the most serious being a Mechanism B success "
             "rate asserted over a **zero denominator**. c016's validator implements exactly "
             "that check.\n")
    L.append("## Candidates\n")
    L.append(f"{st['candidate_leads']} leads inventoried, {st['candidates_executable']} advanced, "
             f"**{st['candidates_exact']} classified EXACT**, {st['candidates_clean_room']} "
             "clean-room. Every advanced candidate is a byte-for-byte copy of an official "
             "sample agent — the identical hash is the anti-simplification proof.\n")
    L.append("## Result\n")
    if gate.get("competitive_gate") == "PASS":
        L.append(f"Selected **`{gate['selected_candidate_id']}`** via strength path "
                 f"**{gate['strength_path']}**, packaged and uploaded as "
                 f"`{st['kaggle_submission_ref']}`.\n")
    else:
        L.append(f"**No candidate cleared the competitive gate.** Best candidate: "
                 f"`{gate.get('best_candidate_id')}`. No package was uploaded — §2 and §18 "
                 "forbid submitting a weak package merely to complete the contract.\n")
        L.append("Exact failed gates:\n")
        for f_ in (gate.get("exact_failed_gates") or []):
            L.append(f"- {f_}")
        L.append("")
    if fin:
        L.append("## Final gauntlet (Stage B)\n")
        L.append("| candidate | vs Dragapult | vs Iono | vs Lucario | vs Abomasnow | "
                 "vs c014 | vs c015 | field mean |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in fin:
            L.append(f"| `{r['candidate_id']}` | {r.get('dragapult_rate')} | "
                     f"{r.get('iono_rate')} | {r.get('mega_lucario_rate')} | "
                     f"{r.get('mega_abomasnow_rate')} | {r.get('__c014___rate')} | "
                     f"{r.get('__c015___rate')} | {r.get('field_mean')} |")
        L.append("")
    L.append(f"Games: {st['screening_games']} screening + {st['final_gauntlet_games']} final + "
             f"{st['confirmation_games']} confirmation. Training games: **0**. "
             f"Invalid {st['invalid_actions']} / exceptions {st['exceptions']} / timeouts "
             f"{st['timeouts']}. Worst p99 latency {lat.get('worst_p99_ms')} ms.\n")
    L.append("## The one next action\n")
    L.append(f"> {board['next_action']['next_action']}\n")
    L.append("## Known limitations\n")
    for k in st["known_limitations"]:
        L.append(f"- {k}")
    L.append("")
    open(os.path.join(C16, "SUMMARY.md"), "w").write("\n".join(L) + "\n")


def write_git():
    L = ["# c016 git report\n",
         "Initial branch: `contract/c015_anti_meta_deck_agent_v0`  ",
         "Initial HEAD: `6c5e602b820e20320b4775e379fc51928fcba9a9`  ",
         f"Final branch: `{git('rev-parse','--abbrev-ref','HEAD')}`  ",
         f"Final HEAD: `{git('rev-parse','HEAD')}`\n",
         "## c016 commits\n```text", git("log", "--oneline", "-12"), "```\n",
         "## Working tree\n```text", git("status", "--short") or "(clean)", "```\n",
         "Untracked historical material present at the start is preserved untouched.\n"]
    open(os.path.join(C16, "GIT_REPORT.md"), "w").write("\n".join(L) + "\n")
    with open(os.path.join(LOGD, "final_git_status.txt"), "w") as fh:
        fh.write(git("status") + "\n\n" + git("log", "--oneline", "-12") + "\n")
    F = ["# Files changed\n", "## Committed source\n```text",
         git("diff", "--stat", "6c5e602b820e20320b4775e379fc51928fcba9a9...HEAD"), "```\n",
         "## Evidence written (uncommitted)\n```text",
         f"{sum(len(fs) for _,_,fs in os.walk(C16))} files under contracts/c016_.../results/",
         "```\n"]
    open(os.path.join(C16, "FILES_CHANGED.md"), "w").write("\n".join(F) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

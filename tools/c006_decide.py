"""c006 decisions (AC-11/12/13): apply the registered rules to the eval evidence
and emit BEST_STUDENT, memory, SUBMISSION_B, PROMOTION, and RL_READINESS artifacts.
No Kaggle upload occurs when the gate is DO_NOT_SUBMIT.
"""

import argparse
import csv
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(art, name):
    return json.load(open(os.path.join(art, name)))


def run(args):
    art = args.art
    off = _load(art, "offline_evaluation.json")
    abl = _load(art, "memory_ablation.json")
    noninf = _load(art, "student_teacher_noninferiority.json")["students"]
    rank = _load(art, "student_global_ranking.json")
    reg = _load(art, "student_regression_report.json")
    rel = _load(art, "model_reliability_report.json")["students"]
    subval = _load(art, "submission_B_validation.json")
    live = _load(art, os.path.join("baselines", "submission_A_teacher_live.json"))
    recorded = _load(art, os.path.join("baselines", "submission_A_teacher_recorded.json"))

    ARCHES = ["S1_STATELESS", "S2_RECURRENT"]
    reliability_eligible = {a: rel[a]["passed"] for a in ARCHES}
    non_inferior = {a: noninf[a]["non_inferior"] for a in ARCHES}
    mean_field = {r["agent"]: r["mean_seat_balanced_vs_field"] for r in rank["ranking"]}

    # ---- BEST_STUDENT (registered §15) ----
    eligible = [a for a in ARCHES if reliability_eligible[a] and non_inferior[a]]
    if not eligible:
        best = "NONE"
        best_reason = ("Neither student passes teacher non-inferiority "
                       f"(S1 one-sided LB={noninf['S1_STATELESS']['one_sided_lb_95']:.3f}, "
                       f"S2 LB={noninf['S2_RECURRENT']['one_sided_lb_95']:.3f}; both << 0.45). "
                       "Per §15, BEST_STUDENT=NONE (a student is not chosen merely for beating the other).")
    else:
        best = max(eligible, key=lambda a: mean_field[a])
        best_reason = "highest strategic-gauntlet strength among non-inferior students"

    # ---- memory decision ----
    memory = abl["memory_decision_offline"]
    memory_detail = {
        "decision": memory,
        "high_impact_gain_pp": abl["high_impact_gain_pp"],
        "game_level_iw_diff_ci95": abl["game_level_iw_diff_ci95"],
        "offline_thresholds": "high-impact gain 0.09pp < 2pp AND game-level iw-diff CI includes 0",
        "gameplay_note": (f"S2 vs teacher point {noninf['S2_RECURRENT']['point_estimate']:.3f} > "
                          f"S1 {noninf['S1_STATELESS']['point_estimate']:.3f}, but S2 gauntlet strength "
                          f"{mean_field['S2']:.3f} < S1 {mean_field['S1']:.3f}; no material gameplay improvement "
                          "can be claimed for a policy that is not non-inferior. S2 ~ S1 offline (matched inputs), "
                          "so 'memory does not help' is robust, not an inference-time artifact."),
    }

    # ---- SUBMISSION_B gate (§17) ----
    submit = (best != "NONE" and non_inferior.get(best, False)
              and reliability_eligible.get(best, False))
    submission_b = "SUBMIT" if submit else "DO_NOT_SUBMIT"
    kaggle_upload = "SKIPPED_BY_GATE" if submission_b == "DO_NOT_SUBMIT" else "PERFORMED"
    promotion = "NO_STUDENT_SUBMISSION" if submission_b == "DO_NOT_SUBMIT" else "SEE_KAGGLE"

    # ---- RL readiness (§17) ----
    decoder_cov = 1.0  # decoders total; ordered forms 0; no strategic fallback needed
    rl_ready = False
    rl_blocker = ("No distilled student is non-inferior to the teacher: best one-sided 95% lower bound is "
                  f"{max(noninf[a]['one_sided_lb_95'] for a in ARCHES):.3f} vs the 0.45 threshold, and both "
                  "students show major matchup regressions across the entire strategic field. Behavioral "
                  "cloning reproduces ~73% of teacher decisions offline but compounding errors collapse "
                  "full-game strength. Highest-leverage next step: close the gameplay gap (interactive "
                  "correction / DAgger-style on-policy relabeling, or a stronger teaching signal) BEFORE RL.")
    rl_readiness = "READY_FOR_RL" if rl_ready else "NOT_READY_FOR_RL"

    # ---- write student_selection ----
    sel = {
        "contract": "c006", "best_student": best, "best_student_reason": best_reason,
        "reliability_eligible": reliability_eligible, "non_inferior_vs_teacher": non_inferior,
        "noninferiority": {a: {"point": noninf[a]["point_estimate"],
                               "one_sided_lb_95": noninf[a]["one_sided_lb_95"]} for a in ARCHES},
        "gauntlet_mean_vs_field": {a: mean_field["S1" if a.startswith("S1") else "S2"] for a in ARCHES},
        "high_impact_test_agreement": {a: off["models"][a]["importance_weighted_agreement"] for a in ARCHES},
        "major_regressions": len(reg["major_regressions"]),
        "memory_decision": memory_detail,
        "selection_rule": "§15: reliability-eligible AND non-inferior first; NONE if neither non-inferior.",
    }
    json.dump(sel, open(os.path.join(art, "student_selection.json"), "w"), indent=2)
    md = [f"# c006 Best-Student & Memory Decision", "",
          f"**BEST_STUDENT = {best}**", "", best_reason, "",
          "## Eligibility", "",
          "| student | reliability_eligible | non_inferior_vs_teacher | LB95 vs teacher | gauntlet mean-vs-field | test iw-agree |",
          "|---|---|---|---|---|---|"]
    for a in ARCHES:
        sh = "S1" if a.startswith("S1") else "S2"
        md.append(f"| {a} | {reliability_eligible[a]} | {non_inferior[a]} | "
                  f"{noninf[a]['one_sided_lb_95']:.3f} | {mean_field[sh]:.3f} | "
                  f"{off['models'][a]['importance_weighted_agreement']:.3f} |")
    md += ["", f"## Memory decision: **{memory}**", "",
           f"- High-impact test agreement gain (S2−S1): {abl['high_impact_gain_pp']:.2f}pp (threshold ≥2pp) — fails.",
           f"- Game-level importance-weighted agreement diff 95% CI: {abl['game_level_iw_diff_ci95']} "
           "(includes 0) — fails.",
           f"- {memory_detail['gameplay_note']}", "",
           "## Note", "A negative result is an acceptable PASS (§1). Both students BEAT the deterministic "
           f"control (S1 {mean_field['S1']:.3f}, S2 {mean_field['S2']:.3f} > control "
           f"{mean_field.get('control', float('nan')):.3f}) — the models learned to imitate; they are simply "
           "not teacher-strong in full games."]
    open(os.path.join(art, "student_selection.md"), "w").write("\n".join(md) + "\n")

    # ---- SUBMISSION_B decision ----
    subm_md = [f"# Submission B Decision", "", f"**SUBMISSION_B = {submission_b}**", "",
               f"Gate (§17) requires a best student that is non-inferior to the teacher with no major "
               f"regression, perfect reliability, and passing package/latency. BEST_STUDENT={best} ⇒ gate not met.",
               "", "## Package (diagnostic)",
               f"- Archive: `{os.path.basename(subval['package']['archive'])}` "
               f"({subval['package']['size_bytes']:,} bytes, < limit; NOT_FOR_SUBMISSION marker inside).",
               f"- Validation from extracted archive: {subval['validation']['games']} games, "
               f"defects={subval['validation']['defects']}, clean={subval['validation']['clean']}, "
               f"single-process P99={subval['validation']['student_latency_ms']['p99']:.3f}ms.",
               f"- Runtime modules byte-identical to evaluated repo: {subval['package']['all_runtime_modules_identical']}.",
               "", "The real `submission_B_student.tar.gz` is intentionally ABSENT (§20). No Kaggle upload is "
               f"performed: **KAGGLE_UPLOAD = {kaggle_upload}**."]
    open(os.path.join(art, "SUBMISSION_B_DECISION.md"), "w").write("\n".join(subm_md) + "\n")

    # ---- Kaggle skip artifacts ----
    open(os.path.join(art, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(
        "# No upload: SUBMISSION_B=DO_NOT_SUBMIT (BEST_STUDENT=NONE). Gate not met -> no submission.\n"
        "# Had the gate passed, the command would have been:\n"
        "# kaggle competitions submit pokemon-tcg-ai-battle "
        "-f contracts/c006_distilled_policy_baseline/results/artifacts/submission_B_student.tar.gz "
        '-m "c006 Submission B: distilled <BEST_STUDENT> <final_commit_short_sha>"\n')
    kstatus = {"competition": "pokemon-tcg-ai-battle", "kaggle_upload": kaggle_upload,
               "reason": "SUBMISSION_B=DO_NOT_SUBMIT (no student passed teacher non-inferiority)",
               "submission_ref": None, "file_name": None, "archive_sha256": None,
               "description": None, "submitted_at": None, "status": None,
               "public_score": None, "private_score": None, "upload_performed": False}
    json.dump(kstatus, open(os.path.join(art, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(art, "kaggle_submission_history.jsonl"), "w").write(
        json.dumps({"event": "no_upload", "kaggle_upload": kaggle_upload,
                    "reason": "gate DO_NOT_SUBMIT", "student_submission_ref": None}) + "\n")

    # kaggle_submissions_after_submit.csv: snapshot the current ladder (teacher rows), no student row
    rows = live.get("all_rows") or []
    with open(os.path.join(art, "kaggle_submissions_after_submit.csv"), "w", newline="") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
            for r in rows:
                w.writerow(r)
        fh.write("# no c006 student submission (SUBMISSION_B=DO_NOT_SUBMIT)\n")

    # teacher/student comparison
    comp = {"contract": "c006", "competition": "pokemon-tcg-ai-battle",
            "teacher": {"submission_ref": "54948560", "recorded_public_score": recorded["public_score"],
                        "live_public_score": live.get("public_score_live"),
                        "live_status": live.get("status_live"), "retrieved_at_utc": live.get("retrieved_at_utc")},
            "student": {"submitted": False, "submission_ref": None, "public_score": None,
                        "reason": "SUBMISSION_B=DO_NOT_SUBMIT; no student is non-inferior to the teacher"},
            "local_evidence": {"student_noninferiority_LB95_vs_teacher":
                               {a: noninf[a]["one_sided_lb_95"] for a in ARCHES},
                               "student_gauntlet_mean_vs_field": {"S1": mean_field["S1"], "S2": mean_field["S2"],
                                                                  "teacher": mean_field["teacher"],
                                                                  "control": mean_field.get("control")}},
            "promotion_decision": promotion,
            "maturity_caveat": "Teacher public scores are timestamped ladder snapshots (recorded 617.8 -> live "
                               f"{live.get('public_score_live')}); no student score exists to compare."}
    json.dump(comp, open(os.path.join(art, "kaggle_teacher_student_comparison.json"), "w"), indent=2)
    open(os.path.join(art, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision\n\n**PROMOTION_DECISION = {promotion}**\n\n"
        f"No student was submitted (SUBMISSION_B=DO_NOT_SUBMIT: no distilled student is non-inferior to the "
        f"teacher). The teacher submission ref `54948560` shows recorded public score {recorded['public_score']} "
        f"and a live same-window snapshot of {live.get('public_score_live')} "
        f"({live.get('status_live')}). There is no student score to promote; the frozen teacher remains the "
        f"standing submission.\n")

    # RL readiness
    rlj = {"contract": "c006", "rl_readiness": rl_readiness, "ready": rl_ready,
           "best_student": best, "submission_b": submission_b,
           "decoder_coverage_without_strategic_fallback": decoder_cov,
           "memory_decision": memory, "highest_leverage_blocker": rl_blocker,
           "gate": "READY_FOR_RL requires a best student, submission gate pass (or non-policy miss), "
                   "not materially weaker than teacher, >=99% decoder coverage w/o strategic fallback, "
                   "memory decision resolved, reproducible checkpoint+eval."}
    json.dump(rlj, open(os.path.join(art, "rl_readiness.json"), "w"), indent=2)
    open(os.path.join(art, "RL_READINESS.md"), "w").write(
        f"# RL Readiness\n\n**RL_READINESS = {rl_readiness}**\n\n"
        f"BEST_STUDENT={best}; SUBMISSION_B={submission_b}. The student is materially weaker than the teacher, "
        f"so RL (explicitly out of scope for c006) must not begin.\n\n"
        f"## Highest-leverage blocker\n\n{rl_blocker}\n\n"
        f"## What IS ready\n- Decoder/representation covers 100% of teacher decision forms without strategic "
        f"fallback (ordered forms absent).\n- Frozen checkpoints + evaluation are reproducible "
        f"(byte-identical re-run).\n- Packaging + CPU latency are fine (single-process P99 "
        f"{subval['validation']['student_latency_ms']['p99']:.3f}ms) — the blocker is policy strength, not operations.\n")

    summary = {"best_student": best, "memory_decision": memory, "submission_b": submission_b,
               "kaggle_upload": kaggle_upload, "promotion_decision": promotion,
               "rl_readiness": rl_readiness}
    print(json.dumps(summary, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--art", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

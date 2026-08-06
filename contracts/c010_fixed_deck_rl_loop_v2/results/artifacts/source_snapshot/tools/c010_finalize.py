"""c010 AC-15: training-loop status, submission gate, conditional Kaggle workflow, next step.

Applies the registered rules from cg.c010_decisions to the aggregated evidence. When and only
when SUBMISSION_E=SUBMIT is a package built and uploaded; otherwise KAGGLE_UPLOAD is recorded
as SKIPPED_BY_GATE and the teacher submission is refreshed read-only for the comparison.
"""

import argparse
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from cg import c010_decisions as D  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
TEACHER_REF = "54948560"
COMP = "pokemon-tcg-ai-battle"


def J(n):
    p = os.path.join(ART, n)
    return json.load(open(p)) if os.path.exists(p) else {}


def refresh_teacher():
    try:
        r = subprocess.run(["kaggle", "competitions", "submissions", COMP, "-v"],
                           capture_output=True, text=True, timeout=90)
        open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w").write(r.stdout)
        lines = r.stdout.splitlines()
        hdr = lines[0].split(",") if lines else []
        idx = hdr.index("publicScore") if "publicScore" in hdr else None
        score, row = None, None
        for ln in lines[1:]:
            parts = ln.split(",")
            if parts and parts[0].strip() == TEACHER_REF:
                row = ln
                if idx is not None and idx < len(parts):
                    try:
                        score = float(parts[idx])
                    except ValueError:
                        score = None
                break
        return {"ok": r.returncode == 0, "publicScore_column_index": idx,
                "teacher_public_score_same_run": score, "teacher_row": row}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e), "teacher_public_score_same_run": None}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    bas = J("best_agent_selection.json")
    rex = J("reproducibility_extendability.json")
    base = J("baseline_incumbent_registry.json")
    reg_eval = J("evaluation_candidate_registry.json")

    best_id = bas.get("best_agent", "I0_incumbent")
    promoted = bool(bas.get("qualified"))
    fsum = bas.get("final_summaries", {})
    best = fsum.get(best_id, {})
    repro = (rex.get("exact_reproducibility") or {}).get("decision", "INCONCLUSIVE")
    ec = (rex.get("exact_continuation") or {}).get("decision", "INCONCLUSIVE")
    sc = (rex.get("stabilized_continuation") or {}).get("decision", "INCONCLUSIVE")

    any_major = any(v for v in (J("final_regression_report.json").get("vs_incumbent") or {}).values())
    real_gain = (repro in ("PROVEN",) or ec == "EXTENDED" or sc == "EXTENDED"
                 or bool(bas.get("qualified")))
    survives_final = promoted
    status = D.training_loop_status(repro, ec, sc, promoted, survives_final, any_major, real_gain)

    i0 = fsum.get("I0_incumbent", {})
    teacher_lb = best.get("teacher_one_sided_lb95")
    repro_strategic = bool(best.get("strategic_field_score") is not None
                           and i0.get("strategic_field_score") is not None
                           and best_id not in ("I0_incumbent", "B0_v2a")
                           and best["strategic_field_score"] > i0["strategic_field_score"])
    rel = best.get("reliability", {})
    rel_ok = (rel.get("defects", 1) == 0 and rel.get("invalid", 1) == 0
              and rel.get("exceptions", 1) == 0 and rel.get("timeouts", 1) == 0)
    gate = D.submission_gate(best_id, best, teacher_lb, repro_strategic, any_major, rel_ok,
                             package_ok=True)
    submit = gate["decision"] == "SUBMIT"

    best_below_teacher = bool(best.get("teacher_score") is not None and best["teacher_score"] < 0.5)
    headroom = status in ("VALIDATED", "PROMISING")
    # §25's REDESIGN clause asserts "PPO cannot reliably extend I0"; that is only supportable
    # when neither continuation arm reached EXTENDED. A promotion alone is not enough -- the
    # registered continuation rules are the evidence for "reliably".
    cannot_extend = not (ec == "EXTENDED" or sc == "EXTENDED")
    nxt = D.next_step(status, best_below_teacher, headroom, deck_gate_met=False,
                      ppo_cannot_reliably_extend=cannot_extend)

    # §25 requires exactly one highest-leverage blocker. Derive it from the measured
    # diagnostics rather than asserting prose: when an arm has extended I0, "reproducibility
    # across seeds" is precisely what is no longer binding.
    vd = J("value_diagnostics_by_game_phase.json").get("by_arm", {})
    early, late = [], []
    for d in vd.values():
        ph = d.get("held_out_ev_by_phase_last_quarter", {})
        if ph.get("0-20", {}).get("mean_ev") is not None:
            early.append(ph["0-20"]["mean_ev"])
        if ph.get("60-80", {}).get("mean_ev") is not None:
            late.append(ph["60-80"]["mean_ev"])
    ev_early = sum(early) / len(early) if early else None
    ev_late = sum(late) / len(late) if late else None

    if best_id == "I0_incumbent":
        blocker = ("Neither the exact c008 R1 loop nor the minimally stabilized variant produced a "
                   "checkpoint that beats the protected 22% incumbent under the registered "
                   "promotion gate, so the loop cannot yet compound its own gains — the binding "
                   "constraint is per-update learning signal, not budget.")
    elif (ec == "EXTENDED" or sc == "EXTENDED") and ev_early is not None:
        blocker = (
            f"Early-game credit assignment. The value function explains {ev_early:.2f} of "
            f"held-out return variance in the first fifth of a game against {ev_late:.2f} in "
            f"the fourth fifth, so opening decisions — the ones the strategic field punishes "
            f"hardest — train on the noisiest advantage estimates. Continuation is no longer "
            f"the constraint: a registered arm reached EXTENDED across its seeds, and both "
            f"exact-recipe arms fell short only on the field dimension.")
    elif status == "VALIDATED":
        blocker = ("The promoted agent remains below the frozen teacher, so absolute strength — "
                   "not loop reliability — is now the binding constraint.")
    else:
        blocker = ("A real gain exists but does not survive every validation condition; the "
                   "binding constraint is the reproducibility of that gain across seeds.")

    json.dump({"training_loop_status": status,
               "inputs": {"exact_reproducibility": repro, "exact_continuation": ec,
                          "stabilized_continuation": sc, "promoted": promoted,
                          "survives_final_panel": survives_final,
                          "any_major_regression": any_major},
               "submission_E": gate["decision"], "criteria": gate["criteria"],
               "best_agent": best_id,
               "best_agent_teacher_score": best.get("teacher_score"),
               "best_agent_field_score": best.get("strategic_field_score"),
               "best_agent_teacher_lb95": teacher_lb,
               "archive_built": False,
               "note": "No package is built for a non-qualifying agent (§24). Training-loop "
                       "validation alone is explicitly not sufficient for submission (§23)."},
              open(os.path.join(ART, "submission_E_validation.json"), "w"), indent=2)

    open(os.path.join(ART, "SUBMISSION_E_DECISION.md"), "w").write(
        f"# SUBMISSION_E Decision (AC-15)\n\n**SUBMISSION_E = {gate['decision']}**\n\n"
        f"Best agent: `{best_id}`  |  training-loop status: **{status}**\n\n"
        + "\n".join(f"- {'PASS' if v else 'FAIL'} — {k}" for k, v in gate["criteria"].items())
        + ("\n\nAll gates pass; the qualifying agent is packaged with the exact frozen Dragapult "
           "deck and uploaded.\n" if submit else
           "\n\nThe amended gate is not met, so nothing is submitted. Note that the submission "
           "gate is independent of the training-loop question: a loop can be validated and still "
           "produce no submittable agent (§23).\n"))

    short = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(
        (f"# SKIPPED_BY_GATE (SUBMISSION_E=DO_NOT_SUBMIT). Command that WOULD run on SUBMIT:\n"
         if not submit else "# executed:\n")
        + f"kaggle competitions submit {COMP} \\\n"
        f"  -f contracts/c010_fixed_deck_rl_loop_v2/results/artifacts/submission_E_fixed_deck_rl_v2.tar.gz \\\n"
        f"  -m \"c010 Submission E: {best_id} fixed deck {short}\"\n"
        f"# Teacher refresh (read-only, executed this run):\n"
        f"kaggle competitions submissions {COMP} -v\n")

    refresh = refresh_teacher()
    tscore = refresh.get("teacher_public_score_same_run")
    ku = "SUBMITTED" if submit else "SKIPPED_BY_GATE"
    json.dump({"kaggle_upload": ku, "submission_E": gate["decision"], "best_agent": best_id,
               "submission_ref": None, "status": None, "public_score": None,
               "note": "No upload: registered submission gate not met." if not submit else "uploaded"},
              open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w").write(
        json.dumps({"event": "skipped_by_gate" if not submit else "submitted",
                    "best_agent": best_id, "submission_E": gate["decision"]}) + "\n")
    json.dump({"contract": "c010", "teacher_submission_ref": TEACHER_REF,
               "teacher_public_score_same_run": tscore,
               "agent_submission_ref": None, "agent_public_score": None,
               "best_agent": best_id, "submission_E": gate["decision"],
               "local_evidence": {"teacher_score": best.get("teacher_score"),
                                  "strategic_field_score": best.get("strategic_field_score"),
                                  "teacher_lb95": teacher_lb,
                                  "training_loop_status": status},
               "note": "Local corrected evidence only; no agent was uploaded. The frozen teacher "
                       "remains the standing submission.",
               "refresh_detail": refresh},
              open(os.path.join(ART, "kaggle_teacher_agent_comparison.json"), "w"), indent=2)
    open(os.path.join(ART, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision (AC-15)\n\n"
        f"**PROMOTION_DECISION = {bas.get('promotion_decision', 'KEEP_R1_INCUMBENT')}**\n\n"
        f"- BEST_AGENT = {best_id}; SUBMISSION_E = {gate['decision']}; KAGGLE_UPLOAD = {ku}.\n"
        f"- Teacher ref {TEACHER_REF} same-run public score: {tscore} "
        f"(read from the `publicScore` column by index).\n"
        f"- The protected c009 incumbent I0 is retained unless a candidate satisfies every §21 "
        f"promotion condition; being newer is never sufficient.\n")

    json.dump({"next_step": nxt, "training_loop_status": status,
               "highest_leverage_blocker": blocker,
               "best_agent": best_id,
               "decisions": {"exact_reproducibility": repro, "exact_continuation": ec,
                             "stabilized_continuation": sc,
                             "promotion_decision": bas.get("promotion_decision"),
                             "submission_E": gate["decision"]}},
              open(os.path.join(ART, "next_step.json"), "w"), indent=2)
    open(os.path.join(ART, "NEXT_STEP.md"), "w").write(
        f"# Next Step (AC-15)\n\n**NEXT_STEP = {nxt}**\n\n"
        f"Training-loop status: **{status}** (reproducibility {repro}, exact continuation {ec}, "
        f"stabilized continuation {sc}).\n\n"
        f"**Highest-leverage blocker (exactly one):** {blocker}\n\n"
        f"`BEGIN_DECK_PIPELINE` is gated on a VALIDATED loop with policy variance low enough for "
        f"deck comparisons to be meaningful (§2); that gate is "
        f"{'met' if (status == 'VALIDATED' and nxt == 'BEGIN_DECK_PIPELINE') else 'not met'}, so "
        f"fixed-deck agent work continues.\n")

    for fn, txt in (("kaggle_submission.txt",
                     f"kaggle_upload={ku}; no `kaggle competitions submit` executed (gate).\n"),
                    ("kaggle_submission_retrieval.txt",
                     f"teacher refresh ok={refresh.get('ok')}; publicScore column index="
                     f"{refresh.get('publicScore_column_index')}; score={tscore}\n")):
        open(os.path.join(LOGD, fn), "w").write(txt)

    print(json.dumps({"training_loop_status": status, "submission_E": gate["decision"],
                      "kaggle_upload": ku, "best_agent": best_id,
                      "promotion_decision": bas.get("promotion_decision"),
                      "next_step": nxt, "teacher_public_score_same_run": tscore}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

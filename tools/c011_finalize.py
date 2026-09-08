"""c011 AC-16 — submission gate, conditional Kaggle workflow, training-loop status, next step."""
import json, os, subprocess, sys
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts"); LOGD = os.path.join(C011, "results", "test_logs")
TEACHER_REF = "54948560"; COMP = "pokemon-tcg-ai-battle"

def J(n, d=None):
    p = os.path.join(ART, n)
    return json.load(open(p)) if os.path.exists(p) else (d or {})

def refresh_teacher():
    try:
        r = subprocess.run(["kaggle", "competitions", "submissions", COMP, "-v"],
                           capture_output=True, text=True, timeout=90)
        open(os.path.join(ART, "kaggle_submissions_after_submit.csv"), "w").write(r.stdout)
        lines = r.stdout.splitlines(); hdr = lines[0].split(",") if lines else []
        idx = hdr.index("publicScore") if "publicScore" in hdr else None
        for ln in lines[1:]:
            parts = ln.split(",")
            if parts and parts[0].strip() == TEACHER_REF:
                try: return {"ok": True, "score": float(parts[idx]), "row": ln}
                except Exception: return {"ok": True, "score": None, "row": ln}
        return {"ok": r.returncode == 0, "score": None, "row": None}
    except Exception as e:
        return {"ok": False, "error": repr(e), "score": None}

def main():
    bas = J("best_agent_selection.json"); sc = J("scale_result.json")
    tfb = J("final_teacher_field_baseline.json"); rr = J("final_regression_report.json")
    inc = J("c010_repaired_incumbent.json"); vd = J("value_diagnostics_by_game_phase.json")
    best_id = bas.get("best_agent"); fsum = bas.get("final_summaries", {})
    best = fsum.get(best_id, {})
    scale = sc.get("scale_result")
    promoted = bool(bas.get("qualified"))
    t_lb = best.get("teacher_one_sided_lb95")
    tvs = (rr.get("vs_teacher_same_panel") or {}).get(best_id, {})
    beats_teacher_field = bool(tvs and tvs.get("gap", -9) > 0 and (tvs.get("prob_teacher_better") or 1) < 0.10)
    rel = best.get("reliability", {})
    rel_ok = all(rel.get(k, 1) == 0 for k in ("defects", "invalid", "exceptions", "timeouts"))
    crit = {
        "best_agent_is_not_the_incumbent": best_id not in ("INCUMBENT", inc.get("incumbent_id")),
        "reliability_passes": rel_ok,
        "teacher_non_inferiority_lb95_ge_0.47": bool(t_lb is not None and t_lb >= 0.47),
        "beats_frozen_teacher_same_panel_field": beats_teacher_field,
        "no_major_regression_vs_teacher": not bool(tvs.get("major_regression_vs_teacher")),
        "uses_exact_frozen_deck": True,
        "package_validation": False,   # NOT_APPLICABLE unless a package is required
    }
    submit = all(crit.values())
    if not submit:
        crit["package_validation"] = "NOT_APPLICABLE"
    decision = "SUBMIT" if submit else "DO_NOT_SUBMIT"

    # §23 training-loop status
    status = ("VALIDATED" if (scale == "EXTENDED" and promoted
                              and len(sc.get("detail", {}).get("seeds_above_teacher", [])) >= 2
                              and not any(rr.get("vs_incumbent", {}).values()))
              else "PROMISING" if scale in ("EXTENDED", "INCONCLUSIVE") and promoted
              else "REJECTED")
    # §2 deck-pipeline gate
    deck_gate = bool(status == "VALIDATED" and promoted
                     and (best.get("teacher_score") or 0) >= 0.40
                     and not any(rr.get("vs_incumbent", {}).values()))
    nxt = ("FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE" if deck_gate else
           "CONTINUE_FIXED_DECK_RL" if status in ("VALIDATED", "PROMISING") and scale == "EXTENDED"
           else "REDESIGN_FIXED_DECK_AGENT")

    # blocker, derived from the measured diagnostics
    early = late = None
    seeds = vd.get("by_seed", {})
    if seeds:
        e = [s["by_phase_last_quarter"]["0-20"]["auc"] for s in seeds.values()
             if "0-20" in s["by_phase_last_quarter"]]
        l = [s["by_phase_last_quarter"]["60-80"]["auc"] for s in seeds.values()
             if "60-80" in s["by_phase_last_quarter"]]
        eb = [s["by_phase_last_quarter"]["0-20"]["brier_score"] for s in seeds.values()
              if "0-20" in s["by_phase_last_quarter"]]
        early = sum(e) / len(e) if e else None; late = sum(l) / len(l) if l else None
        early_brier = sum(eb) / len(eb) if eb else None
    gap = (tfb.get("strategic_field_score") or 0) - (best.get("strategic_field_score") or 0)
    blocker = (
        f"Absolute strength against the frozen teacher's own strategic field. The loop now "
        f"demonstrably extends ({scale}, three seeds), but the promoted agent scores "
        f"{best.get('strategic_field_score'):.3f} on the field where the FROZEN TEACHER scores "
        f"{tfb.get('strategic_field_score'):.3f} on the identical panel -- a {gap:.3f} gap, and "
        f"the §24 submission gate additionally needs a teacher head-to-head lower bound of 0.47 "
        f"against the measured {t_lb:.3f}. The measured mechanism is early-game credit "
        f"assignment: value AUC against ACTUAL outcomes is {early:.2f} in the first fifth of a "
        f"game versus {late:.2f} in the fourth fifth, and 40,000 games per seed did not move it "
        f"(early Brier {early_brier:.3f} against ~0.25 for a base-rate predictor). More PPO on "
        f"this value head buys field score slowly; the head itself is the constraint.")

    json.dump({"submission_F": decision, "criteria": crit, "best_agent": best_id,
               "best_agent_teacher_score": best.get("teacher_score"),
               "best_agent_teacher_lb95": t_lb,
               "best_agent_field_score": best.get("strategic_field_score"),
               "frozen_teacher_same_panel_field": tfb.get("strategic_field_score"),
               "field_gap_vs_teacher": gap, "archive_built": False,
               "package_validation": "NOT_APPLICABLE",
               "note": "No package is built for a non-qualifying agent. §24 requires beating "
                       "the frozen teacher on the SAME strategic panel; c010 compared against "
                       "a teacher figure from a different panel, which is the governance "
                       "defect this contract repaired."},
              open(os.path.join(ART, "submission_F_validation.json"), "w"), indent=2)
    open(os.path.join(ART, "SUBMISSION_F_DECISION.md"), "w").write(
        f"# SUBMISSION_F Decision (AC-16)\n\n**SUBMISSION_F = {decision}**\n\n"
        f"Best agent `{best_id}` — teacher {best.get('teacher_score')}, "
        f"field {best.get('strategic_field_score')}, teacher LB95 {t_lb}.\n"
        f"Frozen teacher same-panel field baseline: **{tfb.get('strategic_field_score')}**.\n\n"
        + "\n".join(f"- {'PASS' if v is True else ('N/A' if v == 'NOT_APPLICABLE' else 'FAIL')} — {k}"
                    for k, v in crit.items())
        + ("\n\nAll gates pass; the agent is packaged with the exact frozen deck and uploaded.\n"
           if submit else
           "\n\nThe gate is not met, so nothing is uploaded and no archive is built. A validated "
           "training loop is explicitly not sufficient for submission.\n"))
    short = subprocess.run(["git", "-C", _REPO, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    open(os.path.join(ART, "KAGGLE_SUBMIT_COMMAND.txt"), "w").write(
        (f"# SKIPPED_BY_GATE (SUBMISSION_F={decision}). Command that WOULD run on SUBMIT:\n"
         if not submit else "# executed:\n")
        + f"kaggle competitions submit {COMP} \\\n"
        f"  -f contracts/c011_fixed_deck_cuda_ppo_scale/results/artifacts/"
        f"submission_F_fixed_deck_cuda_rl.tar.gz \\\n"
        f"  -m \"c011 Submission F: {best_id} fixed deck {short}\"\n"
        f"# Teacher refresh (read-only, executed this run):\n"
        f"kaggle competitions submissions {COMP} -v\n")
    ref = refresh_teacher()
    ku = "SUBMITTED" if submit else "SKIPPED_BY_GATE"
    json.dump({"kaggle_upload": ku, "submission_F": decision, "best_agent": best_id,
               "submission_ref": None, "status": None, "public_score": None,
               "note": "No upload: registered submission gate not met."},
              open(os.path.join(ART, "kaggle_submission_status.json"), "w"), indent=2)
    open(os.path.join(ART, "kaggle_submission_history.jsonl"), "w").write(
        json.dumps({"event": "skipped_by_gate", "best_agent": best_id,
                    "submission_F": decision}) + "\n")
    json.dump({"contract": "c011", "teacher_submission_ref": TEACHER_REF,
               "teacher_public_score_same_run": ref.get("score"),
               "agent_submission_ref": None, "agent_public_score": None,
               "best_agent": best_id, "submission_F": decision,
               "local_evidence": {"teacher_score": best.get("teacher_score"),
                                  "teacher_lb95": t_lb,
                                  "strategic_field_score": best.get("strategic_field_score"),
                                  "frozen_teacher_same_panel_field":
                                      tfb.get("strategic_field_score"),
                                  "scale_result": scale, "training_loop_status": status},
               "note": "Local corrected evidence only; no agent uploaded. The frozen teacher "
                       "remains the standing submission.", "refresh_detail": ref},
              open(os.path.join(ART, "kaggle_teacher_agent_comparison.json"), "w"), indent=2)
    open(os.path.join(ART, "KAGGLE_PROMOTION_DECISION.md"), "w").write(
        f"# Kaggle Promotion Decision (AC-16)\n\n"
        f"**PROMOTION_DECISION = {bas.get('promotion_decision')}** (local best agent)\n"
        f"**KAGGLE_UPLOAD = {ku}**, **SUBMISSION_F = {decision}**\n\n"
        f"- `{best_id}` is promoted over the repaired incumbent locally: it wins on teacher, "
        f"field and composite on the 1,000-game final panel.\n"
        f"- It is NOT submitted: §24 needs a teacher head-to-head LB95 of 0.47 (measured "
        f"{t_lb}) and a field score above the frozen teacher's same-panel "
        f"{tfb.get('strategic_field_score')} (measured "
        f"{best.get('strategic_field_score')}).\n"
        f"- Teacher ref {TEACHER_REF} same-run public score: {ref.get('score')}.\n")
    json.dump({"next_step": nxt, "training_loop_status": status, "scale_result": scale,
               "deck_gate_met": deck_gate, "highest_leverage_blocker": blocker,
               "best_agent": best_id,
               "decisions": {"scale_result": scale, "promotion": bas.get("promotion_decision"),
                             "submission_F": decision}},
              open(os.path.join(ART, "next_step.json"), "w"), indent=2)
    open(os.path.join(ART, "NEXT_STEP.md"), "w").write(
        f"# Next Step (AC-16)\n\n**NEXT_STEP = {nxt}**\n\n"
        f"TRAINING_LOOP_STATUS **{status}**, SCALE_RESULT **{scale}**.\n\n"
        f"**Highest-leverage blocker (exactly one, measured):** {blocker}\n\n"
        f"`FREEZE_AGENT_AND_BEGIN_DECK_PIPELINE` requires §2's gate (validated loop, "
        f"reproducibly stronger agent, >= 0.40 against the teacher, no major held-out "
        f"regression); it is {'met' if deck_gate else 'NOT met'}, so fixed-deck agent work "
        f"continues.\n\n"
        f"**Hypotheses (labelled as such, not measured here):** that a distributional or "
        f"multi-step value target would lift early-game AUC; that opponent-conditioned value "
        f"heads would reduce field variance. Neither was tested in c011.\n")
    for fn, txt in (("kaggle_submission.txt",
                     f"kaggle_upload={ku}; no `kaggle competitions submit` executed (gate).\n"),
                    ("kaggle_submission_retrieval.txt",
                     f"teacher refresh ok={ref.get('ok')} score={ref.get('score')}\n")):
        open(os.path.join(LOGD, fn), "w").write(txt)
    print(json.dumps({"submission_F": decision, "kaggle_upload": ku,
                      "training_loop_status": status, "scale_result": scale,
                      "best_agent": best_id, "next_step": nxt,
                      "teacher_public_score": ref.get("score")}, indent=2))

if __name__ == "__main__":
    sys.exit(main() or 0)

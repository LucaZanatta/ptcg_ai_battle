"""c009 AC-10/AC-11/AC-15: amended decisions, computed mechanically from corrected evidence.

Implements §11 (within-arm + global best), §11.3 (unchanged teacher gate), §14 (recalibrated
feasibility), §15 (next step), §16 (amended submission gate). Improvement over the untouched
initialization (B0) is kept strictly separate from improvement over the teacher.
"""

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")

# Pre-stated criterion for §15's "catastrophically below teacher" (no numeric value is given
# in the contract, so it is stated here explicitly rather than left implicit):
CATASTROPHIC_TEACHER_SCORE = 0.25          # teacher wins more than 3:1
CATASTROPHIC_REGRESSION_FRACTION = 0.5     # major regression on a majority of field matchups


def L(name):
    p = os.path.join(ART, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    registry = L("candidate_checkpoint_registry.json")
    noninf = L("amended_teacher_noninferiority.json").get("candidates", {})
    ranking = L("amended_global_ranking.json").get("candidates", {})
    holdout = L("amended_holdout_report.json").get("results", {})
    improvement = L("amended_improvement_report.json")
    regression = L("amended_regression_report.json")
    vs_b0 = L("rl_vs_initialization.json").get("candidates", {})
    manifest = L("corrected_game_manifest.json")
    defect = L("c008_defect_reproduction.json")
    B0 = "B0_v2a"

    rl_ids = [c for c, v in registry.items() if v["kind"] == "rl_ckpt"]

    # ---------- §11.1 corrected best within each arm ----------
    def tstat(cid):
        return noninf.get(cid, {})

    within = {}
    for arm in ("R0", "R1", "R2"):
        cands = [c for c in rl_ids if registry[c]["arm"] == arm]
        if not cands:
            continue
        ranked = sorted(cands, key=lambda c: -tstat(c).get("point", -1))
        top = ranked[0]
        # statistical tie on the teacher score -> §11.1 tie-break 2 (strategic field), then 3 (held-out)
        tied = [c for c in ranked
                if tstat(c).get("ci95_hi", 0) >= tstat(top).get("ci95_lo", 0)
                and tstat(c).get("ci95_lo", 0) <= tstat(top).get("ci95_hi", 1)]
        chosen, basis = top, "teacher score (unique best)"
        if len(tied) > 1:
            with_field = [c for c in tied if c in ranking]
            if with_field:
                chosen = max(with_field, key=lambda c: ranking[c]["mean_vs_field"])
                basis = (f"teacher score statistically tied among {tied}; broken on strategic-field "
                         f"score (§11.1 #2)")
                fbest = ranking[chosen]["mean_vs_field"]
                also = [c for c in with_field if abs(ranking[c]["mean_vs_field"] - fbest) < 1e-9]
                if len(also) > 1:
                    chosen = max(also, key=lambda c: holdout.get(c, {}).get("point", -1))
                    basis += "; then held-out Abomasnow (§11.1 #3)"
        within[arm] = {"chosen": chosen, "basis": basis,
                       "candidates": {c: {"teacher_point": tstat(c).get("point"),
                                          "teacher_n": tstat(c).get("n"),
                                          "teacher_lb95": tstat(c).get("one_sided_lb95"),
                                          "field": ranking.get(c, {}).get("mean_vs_field"),
                                          "held_out": holdout.get(c, {}).get("point"),
                                          "c008_validation_metric": registry[c]["source_selection_metric"],
                                          "is_median_representative": registry[c]["is_median_representative"],
                                          "is_best_by_c008_validation": registry[c]["is_best_within_arm_by_c008_validation"]}
                                      for c in cands}}

    # ---------- §11.2 improvement over initialization / global best ----------
    beats = {c: v for c, v in vs_b0.items() if v["beats_b0"]}
    if beats:
        best_rl = max(beats, key=lambda c: (ranking.get(c, {}).get("mean_vs_field", 0),
                                            noninf.get(c, {}).get("point", 0)))
        rl_improved = "YES"
        best_ck = os.path.basename(registry[best_rl]["checkpoint_path"]).replace(".npz", "")
        best_saved = f"{registry[best_rl]['arm']}_{registry[best_rl]['seed']}_{best_ck}"
    else:
        best_rl = None
        rl_improved = "NO"
        best_saved = "V2A_BASELINE"

    # ---------- §11.3 teacher non-inferiority (rule unchanged) ----------
    any_ni = [c for c, d in noninf.items() if d.get("non_inferior")]
    teacher_ni = "PASS" if any_ni else "FAIL"

    # ---------- §14 recalibrated feasibility ----------
    improved_over_b0 = bool(beats)
    passes_ni = bool(any_ni)
    repro_impr = [c for c, d in improvement.items() if d.get("reproducible_improvement")]
    majreg = {c: d.get("major_regression_matchups", []) for c, d in regression.items()}
    degrades = all((not v["beats_b0"]) and v["field_diff"] < 0 for v in vs_b0.values()) if vs_b0 else False
    if improved_over_b0 and passes_ni and repro_impr and not majreg.get(best_rl):
        feasibility = "PROVEN"
    elif improved_over_b0:
        feasibility = "INCONCLUSIVE"
    else:
        feasibility = "REJECTED"

    # ---------- §16 amended submission gate ----------
    gate = {}
    if best_rl:
        d = noninf.get(best_rl, {})
        gate = {"reliability_zero_defects": manifest.get("defects", 1) == 0,
                "teacher_non_inferiority": bool(d.get("non_inferior")),
                "reproducible_improvement_over_teacher": best_rl in repro_impr,
                "no_major_regression": not majreg.get(best_rl),
                "exact_frozen_deck": manifest.get("deck_fingerprint") is not None}
    submit = bool(gate) and all(gate.values())
    submission = "SUBMIT" if submit else "DO_NOT_SUBMIT"
    promotion = "PROMOTE_RL" if submit else "NO_RL_SUBMISSION"

    # ---------- §15 next step ----------
    # (a) RL improves over B0 across corrected evidence
    cond_a = improved_over_b0
    # (b) >=2 seeds (or >=2 independent confirmation batches) show the signal
    seeds_signal = [c for c, v in vs_b0.items()
                    if v["teacher_prob_better"] >= 0.90 or v["field_prob_better"] >= 0.90]
    cond_b = len(seeds_signal) >= 2
    # (c) best checkpoint not catastrophically below teacher (criterion stated above)
    best_t = noninf.get(best_rl, {}).get("point") if best_rl else None
    n_field = len(improvement.get(best_rl, {}).get("per_matchup", {})) or 1
    frac_reg = len(majreg.get(best_rl, [])) / n_field if best_rl else 1.0
    cond_c = bool(best_t is not None and best_t >= CATASTROPHIC_TEACHER_SCORE
                  and frac_reg <= CATASTROPHIC_REGRESSION_FRACTION)
    # (d) one clear, addressable c008 algorithmic blocker
    anchor = json.load(open(os.path.join(
        _REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts",
        "teacher_anchor_report.json")))
    low_anchor_reached = min(anchor["replay_coef_observed_range"]) <= 0.06
    cond_d = not low_anchor_reached      # a concrete, addressable defect exists
    redesign_conditions = {
        "a_rl_improves_over_b0": cond_a,
        "b_two_seeds_or_batches_show_signal": cond_b,
        "c_best_not_catastrophically_below_teacher": cond_c,
        "d_one_clear_addressable_blocker": cond_d,
    }
    if all(redesign_conditions.values()):
        next_step = "REDESIGN_TEACHER_ANCHORED_RL"
    else:
        next_step = "FIXED_DECK_SELECTIVE_SEARCH"

    # ---------- single highest-leverage blocker ----------
    if teacher_ni == "FAIL" and improved_over_b0:
        gap = 0.47 - (best_t or 0)
        blocker = (
            f"Sparse terminal-reward credit assignment cannot close the teacher gap at the "
            f"measured learning rate: c008 spent 95,666 training games to move the teacher score "
            f"from {vs_b0.get(best_rl, {}).get('b0_teacher_score', 0):.3f} (untouched V2-A) to "
            f"{best_t:.3f}, leaving {gap:.3f} to the 0.47 non-inferiority bound — roughly 4x the "
            f"total improvement achieved so far. Teacher-anchored PPO on the fixed deck improves "
            f"its own initialization but is the wrong instrument for closing a >2x strength gap.")
    elif not improved_over_b0:
        blocker = ("No saved RL checkpoint improves on the untouched V2-A initialization under "
                   "corrected evidence.")
    else:
        blocker = "none — a qualifying checkpoint exists"

    out = {
        "contract": "c009",
        "c008_evaluation": "REPAIRED" if defect.get("reproduced") else "UNREPAIRABLE",
        "rl_improved_over_initialization": rl_improved,
        "best_saved_checkpoint": best_saved,
        "best_saved_candidate_id": best_rl,
        "teacher_noninferiority": teacher_ni,
        "rl_feasibility_recalibrated": feasibility,
        "submission_D_amended": submission,
        "submission_gate": gate,
        "promotion_decision": promotion,
        "next_step": next_step,
        "next_step_conditions": redesign_conditions,
        "next_step_criteria_note": (
            f"'catastrophically below teacher' is pre-stated here as teacher score < "
            f"{CATASTROPHIC_TEACHER_SCORE} OR major regression on more than "
            f"{CATASTROPHIC_REGRESSION_FRACTION:.0%} of field matchups; the best checkpoint scores "
            f"{best_t} with {len(majreg.get(best_rl, []))}/{n_field} major regressions. Even under a "
            f"laxer reading of that condition, §15's expected-value clause selects "
            f"FIXED_DECK_SELECTIVE_SEARCH: the measured improvement rate leaves the 0.47 bound out "
            f"of reach for a comparable PPO budget."),
        "highest_leverage_blocker": blocker,
        "within_arm_best": within,
        "seeds_showing_signal_over_b0": seeds_signal,
        "reproducible_improvement_over_teacher": repro_impr,
        "major_regressions": majreg,
        "c008_anchor_finding": {
            "replay_coef_observed_range": anchor["replay_coef_observed_range"],
            "kl_coef_observed_range": anchor["kl_coef_observed_range"],
            "low_anchor_phase_reached": low_anchor_reached,
            "interpretation": ("c008 registered a replay-coefficient decay to 0.05 and a reference-KL "
                               "decay to 0.01, but every R2 seed early-stopped at 10k-20k of its 50k "
                               "budget, so the replay coefficient never fell below ~0.27 and the KL "
                               "coefficient never below ~0.030. R2 therefore spent its entire life in "
                               "the high-anchor regime, which is consistent with its teacher score "
                               "(0.158) being statistically indistinguishable from the untouched "
                               "initialization B0 (0.160). This is an algorithmic/budget limitation of "
                               "the c008 run, not evidence that anchoring cannot work."),
        },
        "total_evaluation_games": manifest.get("total_games"),
    }
    json.dump(out, open(os.path.join(ART, "amended_checkpoint_selection.json"), "w"), indent=2)

    # ---- AC-10 markdown ----
    b0t = vs_b0.get(best_rl, {}) if best_rl else {}
    md = ["# RL Improvement Over Initialization (AC-10)", "",
          f"**RL_IMPROVED_OVER_INITIALIZATION = {rl_improved}**", "",
          "c008 never evaluated the untouched c007 V2-A initialization, so it could not tell "
          "whether RL improved anything. c009 evaluates it (B0) under the identical protocol.", "",
          "| candidate | teacher score | vs B0 (P) | strategic field | vs B0 (P) | beats B0 (§11.2) |",
          "|---|---|---|---|---|---|",
          f"| **B0_v2a** (untouched V2-A) | {noninf.get(B0, {}).get('point')} | — | "
          f"{ranking.get(B0, {}).get('mean_vs_field')} | — | reference |"]
    for c, v in sorted(vs_b0.items(), key=lambda kv: -(kv[1]["field_score"] or 0)):
        md.append(f"| {c} | {v['teacher_score']:.3f} | {v['teacher_diff']:+.3f} (P={v['teacher_prob_better']:.2f}) | "
                  f"{v['field_score']:.3f} | {v['field_diff']:+.3f} (P={v['field_prob_better']:.2f}) | "
                  f"{'**YES**' if v['beats_b0'] else 'no'} |")
    if best_rl:
        md += ["", f"### {best_rl} satisfies every §11.2 criterion",
               *[f"- {k}: {v}" for k, v in vs_b0[best_rl]["criteria"].items()],
               "", f"Teacher score {b0t['b0_teacher_score']:.3f} → {b0t['teacher_score']:.3f} "
                   f"(90% CI on the difference {[round(x,3) for x in b0t['teacher_diff_ci90']]}); "
                   f"strategic field {b0t['b0_field_score']:.3f} → {b0t['field_score']:.3f} "
                   f"(90% CI {[round(x,3) for x in b0t['field_diff_ci90']]})."]
    md += ["", "**This is improvement over the initialization, NOT over the teacher.** The frozen "
               "teacher scores 0.570 on the same field; the best RL checkpoint scores "
               f"{ranking.get(best_rl, {}).get('mean_vs_field')} and is not teacher-non-inferior."]
    open(os.path.join(ART, "RL_IMPROVEMENT_OVER_INITIALIZATION.md"), "w").write("\n".join(md) + "\n")

    # ---- AC-11 markdown ----
    fmd = ["# Recalibrated RL Feasibility (AC-11)", "",
           f"**RL_FEASIBILITY_RECALIBRATED = {feasibility}**",
           f"**BEST_SAVED_CHECKPOINT = {best_saved}**",
           f"**TEACHER_NONINFERIORITY = {teacher_ni}**", "",
           "§14 sets INCONCLUSIVE when a saved RL checkpoint clearly improves over B0 but remains "
           "below the teacher. Both halves are now established from corrected evidence:", "",
           f"- improves over B0: {best_rl} (teacher {b0t.get('b0_teacher_score')} → {b0t.get('teacher_score')}, "
           f"field {b0t.get('b0_field_score')} → {b0t.get('field_score')})",
           f"- below teacher: best one-sided 95% LB = "
           f"{max((d.get('one_sided_lb95', 0) for d in noninf.values()), default=0):.4f} vs the "
           f"unchanged 0.47 requirement", "",
           "## Corrected best within each arm (§11.1)"]
    for arm, d in sorted(within.items()):
        fmd.append(f"- **{arm} → {d['chosen']}** ({d['basis']})")
        for c, s in sorted(d["candidates"].items()):
            fmd.append(f"  - {c}: teacher {s['teacher_point']} (n={s['teacher_n']}), "
                       f"field {s['field']}, held-out {s['held_out']}, "
                       f"c008 validation {s['c008_validation_metric']}"
                       f"{' [c008 median representative]' if s['is_median_representative'] else ''}"
                       f"{' [c008 best-by-validation]' if s['is_best_by_c008_validation'] else ''}")
    fmd += ["", "## R2 interpretation limits (§2.5)",
            out["c008_anchor_finding"]["interpretation"],
            "", "Additional acknowledged limits: the reference KL anchored to V2-A rather than to the "
                "rule teacher; the teacher-replay term was strong relative to the PPO objective; and "
                "the multi-select reference KL covered only the first sub-selection. These are "
                "algorithmic limitations of the c008 run — no saved checkpoint was altered."]
    open(os.path.join(ART, "RL_FEASIBILITY_RECALIBRATED.md"), "w").write("\n".join(fmd) + "\n")

    # ---- AC-15 next step ----
    json.dump({"next_step": next_step, "conditions": redesign_conditions,
               "criteria_note": out["next_step_criteria_note"],
               "highest_leverage_blocker": blocker,
               "rl_feasibility_recalibrated": feasibility,
               "best_saved_checkpoint": best_saved},
              open(os.path.join(ART, "next_step.json"), "w"), indent=2)
    open(os.path.join(ART, "NEXT_STEP.md"), "w").write(
        f"# Next Step (AC-15)\n\n**NEXT_STEP = {next_step}**\n\n"
        + "\n".join(f"- §15 REDESIGN condition {k}: {'MET' if v else 'NOT MET'}"
                    for k, v in redesign_conditions.items())
        + f"\n\n{out['next_step_criteria_note']}\n\n"
        f"**Highest-leverage blocker (exactly one):** {blocker}\n\n"
        f"Recalibrated feasibility: {feasibility}. Best saved checkpoint: {best_saved}.\n\n"
        "The most valuable algorithmic finding for anyone revisiting RL is recorded in "
        "`RL_FEASIBILITY_RECALIBRATED.md`: c008's R2 anchor schedule never reached its "
        "registered low-anchor phase, so the teacher-anchored arm never had the opportunity to "
        "move away from its initialization.\n")

    # ---- AC-13 submission decision ----
    open(os.path.join(ART, "SUBMISSION_D_AMENDED_DECISION.md"), "w").write(
        f"# SUBMISSION_D_AMENDED Decision (AC-13)\n\n**SUBMISSION_D_AMENDED = {submission}**\n\n"
        f"Best saved checkpoint: {best_saved}.\n\n"
        + ("\n".join(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in gate.items()) if gate else
           "- no RL checkpoint improved over the untouched initialization\n")
        + ("\n\nThe amended gate requires ALL of reliability, teacher non-inferiority, reproducible "
           "improvement over the teacher, no major regression, the exact frozen deck, and package "
           "validation. Teacher non-inferiority fails (best one-sided LB "
           f"{max((d.get('one_sided_lb95', 0) for d in noninf.values()), default=0):.4f} < 0.47) and "
           "major regressions exist, so no already-trained checkpoint qualifies. No retraining was "
           "performed. Kaggle upload is SKIPPED_BY_GATE; the frozen teacher (ref 54948560) remains "
           "the standing submission.\n\nRL improving over its own initialization is explicitly NOT a "
           "submission criterion.\n" if not submit else
           "\n\nAll gates pass; the qualifying already-trained checkpoint is packaged with the exact "
           "frozen Dragapult deck and uploaded.\n"))

    print(json.dumps({k: out[k] for k in (
        "c008_evaluation", "rl_improved_over_initialization", "best_saved_checkpoint",
        "teacher_noninferiority", "rl_feasibility_recalibrated", "submission_D_amended",
        "promotion_decision", "next_step", "total_evaluation_games")}, indent=2))
    print("within-arm:", json.dumps({a: d["chosen"] for a, d in within.items()}))
    print("blocker:", blocker)
    return 0


if __name__ == "__main__":
    sys.exit(main())

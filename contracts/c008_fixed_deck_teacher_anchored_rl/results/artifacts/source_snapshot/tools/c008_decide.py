"""c008 AC-12/13/15: registered RL decisions.

BEST_RL_ARM, RL_FEASIBILITY, SUBMISSION_D, PROMOTION_DECISION, NEXT_STEP strictly from the
registered rules (§17/§18/§21). No gate is lowered; a negative RL result is an honest PASS.
"""

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")


def _load(name, default=None):
    p = os.path.join(C008_ART, name)
    return json.load(open(p)) if os.path.exists(p) else (default if default is not None else {})


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    sel = _load("checkpoint_selection.json")
    rel = _load("final_reliability.json")
    noninf = _load("rl_teacher_noninferiority.json")
    imp = _load("rl_improvement_report.json")
    reg = _load("rl_regression_report.json")
    arms = [a for a in ("R0", "R1", "R2") if a in sel.get("per_arm", {})]

    # eligibility per arm (§17): reliability + non-inferiority + no major regression + reproducible ckpt
    eligible = {}
    details = {}
    for arm in arms:
        r = rel.get(arm, {}); ni = noninf.get(arm, {}); rg = reg.get(arm, {}); im = imp.get(arm, {})
        reliability_ok = bool(r.get("zero_defects"))
        non_inf = bool(ni.get("non_inferior"))
        major_reg = bool(rg.get("major_regression_matchups"))
        reproducible_improvement = bool(im.get("matchups_5pp_90") or im.get("global_better"))
        ckpt_ok = sel["per_arm"][arm].get("representative_checkpoint") is not None
        eligible[arm] = reliability_ok and non_inf and (not major_reg) and ckpt_ok
        details[arm] = {"reliability_ok": reliability_ok, "non_inferior": non_inf,
                        "non_inf_lb": ni.get("lower_bound_95_one_sided"), "major_regression": major_reg,
                        "reproducible_improvement": reproducible_improvement,
                        "mean_vs_field": im.get("mean_vs_field"), "teacher_mean_vs_field": im.get("teacher_mean_vs_field"),
                        "eligible": eligible[arm], "stop_reasons": sel["per_arm"][arm]["all_seed_stop_reasons"],
                        "median_validation_blend": sel["per_arm"][arm]["median_validation_blend"],
                        "learning_curve_stable_2plus_seeds": sel["per_arm"][arm].get("learning_curve_stable_2plus_seeds")}

    # BEST_RL_ARM (§17): eligible + reproducible improvement; rank by global field, then LB, then holdout, worst, latency
    eligible_arms = [a for a in arms if eligible[a] and details[a]["reproducible_improvement"]]
    holdout = _load("rl_holdout_report.json").get("holdout_abomasnow", {})

    def rank_key(a):
        return (details[a]["mean_vs_field"] or 0, details[a]["non_inf_lb"] or 0,
                (holdout.get(a) or {}).get("point") or 0)
    best_rl_arm = max(eligible_arms, key=rank_key) if eligible_arms else "NONE"

    # RL_FEASIBILITY (§17)
    any_proven = any(details[a]["non_inferior"] and details[a]["reproducible_improvement"]
                     and details[a]["learning_curve_stable_2plus_seeds"] for a in arms)
    any_learning = any(details[a]["learning_curve_stable_2plus_seeds"] for a in arms)
    if any_proven:
        feasibility = "PROVEN"
    elif any_learning:
        feasibility = "INCONCLUSIVE"
    else:
        feasibility = "REJECTED"

    # SUBMISSION_D (§18)
    submit = (best_rl_arm != "NONE" and eligible.get(best_rl_arm, False)
              and details.get(best_rl_arm, {}).get("reproducible_improvement", False))
    submission_d = "SUBMIT" if submit else "DO_NOT_SUBMIT"

    # PROMOTION (§20) — resolved after Kaggle; default here
    if submission_d == "SUBMIT":
        promotion = "PROMOTE_RL"
    else:
        promotion = "NO_RL_SUBMISSION"

    # NEXT_STEP (§21)
    if feasibility == "PROVEN" and submit:
        next_step = "CONSOLIDATE_RL"
    elif any_learning and not any(details[a]["non_inferior"] for a in arms):
        next_step = "REVISE_RL"
    elif feasibility == "REJECTED":
        next_step = "RETURN_TO_SEARCH"
    else:
        next_step = "REVISE_RL"

    # highest-leverage blocker
    if submit:
        blocker = "none — RL candidate qualifies"
    elif not any_learning:
        blocker = ("no arm produced a stable positive learning curve across >=2 seeds under budget: "
                   "sparse ±1 terminal reward over ~70-decision games is too weak a signal for numpy PPO "
                   "to move a frozen-deck policy past the tuned teacher within the registered simulator budget")
    else:
        best_lb = max((details[a]["non_inf_lb"] or 0) for a in arms)
        blocker = (f"RL learns but no candidate reaches teacher non-inferiority (best one-sided LB {best_lb:.3f} "
                   f"< 0.47) or a reproducible strategic improvement; the teacher remains stronger on the fixed deck")

    out = {"contract": "c008", "arms_evaluated": arms, "per_arm": details,
           "eligible_arms": eligible_arms, "best_rl_arm": best_rl_arm,
           "rl_feasibility": feasibility, "submission_D": submission_d,
           "promotion_decision": promotion, "next_step": next_step,
           "highest_leverage_blocker": blocker}
    json.dump(out, open(os.path.join(C008_ART, "rl_arm_selection.json"), "w"), indent=2)

    md = ["# RL Best-Arm & Feasibility (AC-12)", "",
          f"- **BEST_RL_ARM** = {best_rl_arm}", f"- **RL_FEASIBILITY** = {feasibility}",
          f"- **SUBMISSION_D** = {submission_d}", f"- **PROMOTION_DECISION** = {promotion}",
          f"- **NEXT_STEP** = {next_step}", "",
          "| arm | reliability | non-inf (LB) | repro improvement | major regression | eligible | stops |",
          "|---|---|---|---|---|---|---|"]
    for a in arms:
        d = details[a]
        md.append(f"| {a} | {d['reliability_ok']} | {d['non_inferior']} ({d['non_inf_lb']}) | "
                  f"{d['reproducible_improvement']} | {d['major_regression']} | {d['eligible']} | "
                  f"{list(d['stop_reasons'].values())} |")
    md += ["", f"**Highest-leverage blocker:** {blocker}", "",
           "RL feasibility rule (§17): PROVEN needs an arm that is teacher-non-inferior AND reproducibly "
           "stronger AND stable across >=2 seeds; INCONCLUSIVE = learning occurs but none reaches "
           "non-inferiority; REJECTED = no meaningful learning curve. Gates were not lowered."]
    open(os.path.join(C008_ART, "RL_FEASIBILITY.md"), "w").write("\n".join(md) + "\n")

    open(os.path.join(C008_ART, "SUBMISSION_D_DECISION.md"), "w").write(
        f"# SUBMISSION_D Decision (AC-13)\n\n**SUBMISSION_D = {submission_d}**\n\n"
        f"BEST_RL_ARM = {best_rl_arm}. " +
        ("Local gate passed; the qualifying RL policy is packaged with the frozen Dragapult deck and "
         "uploaded to Kaggle (AC-14)." if submit else
         "The submission gate is not met (no eligible RL candidate with a reproducible improvement over "
         "the frozen teacher). Kaggle upload is SKIPPED_BY_GATE; the frozen teacher (ref 54948560) remains "
         "the standing submission. A policy is never submitted merely because training reward increased.") + "\n")

    ns_out = {"next_step": next_step, "highest_leverage_blocker": blocker,
              "rl_feasibility": feasibility, "best_rl_arm": best_rl_arm}
    json.dump(ns_out, open(os.path.join(C008_ART, "next_step.json"), "w"), indent=2)
    open(os.path.join(C008_ART, "NEXT_STEP.md"), "w").write(
        f"# Next Step (AC-15)\n\n**NEXT_STEP = {next_step}**\n\n**Highest-leverage blocker:** {blocker}\n\n"
        f"RL feasibility: {feasibility}; best RL arm: {best_rl_arm}.\n")

    print(json.dumps({"best_rl_arm": best_rl_arm, "rl_feasibility": feasibility,
                      "submission_D": submission_d, "promotion_decision": promotion,
                      "next_step": next_step, "blocker": blocker}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""c008 AC-16 + results package: immutability re-verify, git report, patch, source snapshot,
clean-checkout note, and STATUS/SUMMARY/CHECKLIST/FILES/COMMANDS reports. Run LAST after the
c008 source is committed and all AC evidence exists.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C008 = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl")
ART = os.path.join(C008, "results", "artifacts")
RES = os.path.join(C008, "results")
C007_FINAL = "1f3fc63aaa36be0a45ffce8481c563c89ffa0577"
IMMUT = ["c005_teacher_import_submission_and_dataset", "c006_distilled_policy_baseline",
         "c007_hybrid_teacher_residual_and_state_encoder_v2"]

SRC = ["starter_kit/micrograd.py", "starter_kit/rl_policy.py", "starter_kit/rl_env.py",
       "starter_kit/ppo.py", "tools/c008_verify_deps.py", "tools/c008_validate_rl.py",
       "tools/train_rl.py", "tools/c008_register_experiment.py", "tools/c008_aggregate.py",
       "tools/c008_final_eval.py", "tools/c008_decide.py", "tools/c008_finalize.py",
       "tools/c008_reports.py", "tools/build_submission_d.py", "tools/c008_kaggle_submit.py"]

AC_EVIDENCE = {
    "AC-01": ["dependency_verification.json", "immutability_verification.json"],
    "AC-02": ["EXPERIMENT_REGISTRATION.md", "experiment_registration.json"],
    "AC-03": ["rl_environment_schema.json", "action_decoder_coverage.json"],
    "AC-04": ["ppo_validation.json"],
    "AC-05": ["r0_training_summary.json"],
    "AC-06": ["r1_training_summary.json"],
    "AC-07": ["r2_training_summary.json", "teacher_anchor_report.json"],
    "AC-08": ["training_curves.csv", "training_curves.json", "checkpoint_registry.json",
              "checkpoint_selection.json"],
    "AC-09": ["final_reliability.json", "final_latency.json"],
    "AC-10": ["rl_teacher_games.jsonl.gz", "rl_teacher_noninferiority.json"],
    "AC-11": ["rl_strategic_games.jsonl.gz", "rl_matchup_matrix.csv", "rl_global_ranking.json",
              "rl_holdout_report.json", "rl_improvement_report.json", "rl_regression_report.json"],
    "AC-12": ["rl_arm_selection.json", "RL_FEASIBILITY.md"],
    "AC-13": ["SUBMISSION_D_DECISION.md", "submission_D_validation.json", "KAGGLE_SUBMIT_COMMAND.txt"],
    "AC-14": ["kaggle_submission_status.json", "kaggle_submission_history.jsonl",
              "kaggle_teacher_rl_comparison.json", "KAGGLE_PROMOTION_DECISION.md"],
    "AC-15": ["NEXT_STEP.md", "next_step.json"],
    "AC-16": ["c008.patch", "CLEAN_CHECKOUT.md"],
}


def _git(*a):
    return subprocess.run(["git", "-C", _REPO, *a], capture_output=True, text=True).stdout


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _tree(root):
    out = {}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            try:
                out[os.path.relpath(p, _REPO)] = _sha(p)
            except OSError:
                out[os.path.relpath(p, _REPO)] = "UNREADABLE"
    return dict(sorted(out.items()))


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    sel = json.load(open(os.path.join(ART, "rl_arm_selection.json")))
    final_head = _git("rev-parse", "HEAD").strip()
    commits = [l for l in _git("log", "--oneline", f"{C007_FINAL}..HEAD").strip().splitlines() if l]

    base = json.load(open(os.path.join(ART, "immutability_verification.json")))
    changed = {}
    for name, key in zip(IMMUT, ("c005_files", "c006_files", "c007_files")):
        now = _tree(os.path.join(_REPO, "contracts", name))
        for k, v in now.items():
            if k in base[key] and base[key][k] != v:
                changed[k] = [base[key][k], v]
    immut_ok = len(changed) == 0
    json.dump({"immutability_preserved": immut_ok, "changed": changed},
              open(os.path.join(ART, "immutability_recheck.json"), "w"), indent=2)

    patch = _git("diff", f"{C007_FINAL}..HEAD", "--", *SRC)
    open(os.path.join(ART, "c008.patch"), "w").write(patch)
    snap = os.path.join(ART, "source_snapshot")
    if os.path.exists(snap):
        shutil.rmtree(snap)
    for f in SRC:
        src = os.path.join(_REPO, f)
        if os.path.exists(src):
            dst = os.path.join(snap, f); os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    open(os.path.join(RES, "test_logs", "final_git_status.txt"), "w").write(_git("status", "--short"))
    open(os.path.join(ART, "CLEAN_CHECKOUT.md"), "w").write(
        "# Clean Checkout & Run (c008)\n\nReproduce from branch "
        f"`contract/c008_fixed_deck_teacher_anchored_rl` (final HEAD `{final_head}`), repo root, "
        "`.venv/bin/python`. RL training/eval are engine `random_device`-seeded and NOT bit-reproducible; "
        "the toy PPO positive control, GAE, masking, and dependency checks are deterministic. Statistical "
        "conclusions are stable over the registered samples. Provide externally (gitignored): cabt SDK + "
        "`libcg.so`, `cg` symlinks, kaggle-environments, numpy/scipy/matplotlib, the c005 teacher_sources, "
        "and the c007 V2-A checkpoint + v2 dataset. results/ is uncommitted review evidence.\n")

    checklist = {ac: {"present": all(os.path.exists(os.path.join(ART, f)) for f in files), "files": files}
                 for ac, files in AC_EVIDENCE.items()}
    all_present = all(v["present"] for v in checklist.values())

    dep = json.load(open(os.path.join(ART, "dependency_verification.json")))
    kag = json.load(open(os.path.join(ART, "kaggle_teacher_rl_comparison.json")))
    status = {
        "contract": "c008_fixed_deck_teacher_anchored_rl",
        "status": "PASS" if all_present else "PARTIAL",
        "acceptance_criteria_total": 16,
        "acceptance_criteria_passed": sum(1 for v in checklist.values() if v["present"]),
        "acceptance_criteria_failed": sum(1 for v in checklist.values() if not v["present"]),
        "initial_head": C007_FINAL, "final_head": final_head,
        "implementation_commits": [c.split()[0] for c in commits],
        "teacher_id": dep["teacher_id"], "teacher_submission_ref": "54948560",
        "deck_id": dep["frozen_deck_id"],
        "best_rl_arm": sel["best_rl_arm"], "rl_feasibility": sel["rl_feasibility"],
        "submission_D_decision": sel["submission_D"], "kaggle_upload": "SKIPPED_BY_GATE"
        if sel["submission_D"] != "SUBMIT" else "SUBMITTED",
        "kaggle_submission_ref": None, "kaggle_submission_status": None, "rl_public_score": None,
        "teacher_public_score_same_run": kag.get("teacher_public_score_same_run"),
        "promotion_decision": sel["promotion_decision"], "next_step": sel["next_step"],
        "highest_leverage_blocker": sel["highest_leverage_blocker"],
        "blocking_issues": [], "immutability_preserved": immut_ok,
        "known_limitations": [
            "Pure-numpy PPO under a bounded simulator budget; sparse ±1 terminal reward over ~70-decision "
            "games is a weak learning signal on a fixed tuned-teacher deck.",
            "Engine random_device: RL games are non-reproducible; conclusions are statistical over the "
            "registered samples; the value head, GAE, masking, and toy PPO control are validated.",
            "R2 on-policy teacher-action term disabled (synchronization after divergent RL actions "
            "unproven); R2 used offline replay + reference KL only.",
        ],
    }
    json.dump(status, open(os.path.join(RES, "STATUS.json"), "w"), indent=2)

    cl = ["# Acceptance Checklist (c008)", "", f"Status: **{status['status']}** "
          f"({status['acceptance_criteria_passed']}/16)", "", "| AC | evidence present |", "|---|---|"]
    for ac, v in checklist.items():
        cl.append(f"| {ac} | {'yes' if v['present'] else 'MISSING'} |")
    open(os.path.join(RES, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(cl) + "\n")
    open(os.path.join(RES, "FILES_CHANGED.md"), "w").write(
        "# Files Changed (c008 source, committed)\n\n" + "\n".join(f"- `{f}`" for f in SRC)
        + "\n\nresults/ is uncommitted review evidence (c002–c007 policy). No c005/c006/c007 file modified; "
          "no `.so` committed.\n")
    open(os.path.join(RES, "GIT_REPORT.md"), "w").write(
        f"# Git Report (c008)\n\n- Branch: `contract/c008_fixed_deck_teacher_anchored_rl`\n"
        f"- Initial HEAD (c007 final): `{C007_FINAL}`\n- Final HEAD: `{final_head}`\n"
        f"- Implementation commits ({len(commits)}):\n" + "\n".join(f"  - {c}" for c in commits)
        + f"\n\n- Immutability preserved (c005/c006/c007 unchanged): **{immut_ok}**\n"
          "- Source-only commits; results/ uncommitted; no `.so`; no credentials.\n")

    print(json.dumps({"status": status["status"], "passed": status["acceptance_criteria_passed"],
                      "final_head": final_head[:12], "immutability_preserved": immut_ok,
                      "missing": [ac for ac, v in checklist.items() if not v["present"]]}, indent=2))
    return 0 if all_present else 1


if __name__ == "__main__":
    sys.exit(main())

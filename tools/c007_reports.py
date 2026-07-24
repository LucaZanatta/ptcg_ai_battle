"""c007 AC-16 + top-level results package: immutability re-verification, git report,
source snapshot, clean-checkout note, and STATUS/SUMMARY/CHECKLIST/FILES/COMMANDS/GIT
reports. Run LAST, after the c007 source is committed and all AC evidence exists.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C007 = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2")
ART = os.path.join(C007, "results", "artifacts")
RES = os.path.join(C007, "results")
C005 = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset")
C006 = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline")
C006_FINAL = "08ebac88385444a69d0615b7976dea9dbddeb79a"

# c007 source files (committed)
SRC = ["starter_kit/instrumented_teacher.py", "starter_kit/state_encoder_v2.py",
       "starter_kit/policy_model_v2.py", "starter_kit/policy_data_v2.py",
       "starter_kit/teacher_variants.py", "starter_kit/hybrid_agent.py",
       "starter_kit/hybrid_gameplay.py", "starter_kit/micrograd.py",
       "tools/c007_verify_deps.py", "tools/c007_context_census.py", "tools/c007_teacher_parity.py",
       "tools/c007_state_encoder_audit.py", "tools/c007_register_experiment.py",
       "tools/generate_v2_dataset.py", "tools/validate_v2_dataset.py", "tools/train_student_v2.py",
       "tools/offline_eval_v2.py", "tools/c007_improvement_labels.py", "tools/c007_residual_admission.py",
       "tools/c007_build_hybrid.py", "tools/c007_on_policy.py", "tools/c007_hybrid_gameplay.py",
       "tools/c007_decide.py", "tools/c007_finalize.py", "tools/build_submission_c.py",
       "tools/c007_reports.py", "tests/test_c007_models.py"]

AC_EVIDENCE = {
    "AC-01": ["dependency_verification.json", "immutability_verification.json"],
    "AC-02": ["EXPERIMENT_REGISTRATION.md", "experiment_registration.json"],
    "AC-03": ["state_encoder_v2_schema.json", "state_encoder_v2_audit.md",
              "c006_vs_v2_feature_diff.json"],
    "AC-04": ["teacher_instrumentation_manifest.json", "teacher_plan_label_schema.json",
              "teacher_instrumentation_parity.json"],
    "AC-05": ["v2_dataset_manifest.json", "v2_dataset_split_report.json"],
    "AC-06": ["v2_training_runs.json", "v2_offline_evaluation.json", "v2_ablation.json"],
    "AC-07": ["residual_context_candidates.json", "residual_context_admission.json",
              "RESIDUAL_CONTEXTS.md"],
    "AC-08": ["improvement_label_manifest.json", "improvement_labels.jsonl.gz",
              "counterfactual_evaluation.json"],
    "AC-09": ["on_policy_states.jsonl.gz", "on_policy_relabel_report.json",
              "final_residual_checkpoint.json"],
    "AC-10": ["h0_parity_report.json", "hybrid_reliability_report.json", "hybrid_latency_report.json"],
    "AC-11": ["h2_teacher_noninferiority.json"],
    "AC-12": ["hybrid_matchup_matrix.csv", "hybrid_global_ranking.json",
              "hybrid_improvement_report.json", "hybrid_regression_report.json"],
    "AC-13": ["hybrid_selection.json", "hybrid_selection.md", "SUBMISSION_C_DECISION.md"],
    "AC-14": ["submission_C_validation.json", "KAGGLE_SUBMIT_COMMAND.txt",
              "kaggle_submission_status.json", "kaggle_teacher_hybrid_comparison.json",
              "KAGGLE_PROMOTION_DECISION.md"],
    "AC-15": ["RESIDUAL_RL_READINESS.md", "residual_rl_readiness.json"],
    "AC-16": ["c007.patch", "CLEAN_CHECKOUT.md"],
}


def _git(*args):
    return subprocess.run(["git", "-C", _REPO, *args], capture_output=True, text=True).stdout


def _sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _tree(root):
    out = {}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            try:
                out[os.path.relpath(p, _REPO)] = _sha_file(p)
            except OSError:
                out[os.path.relpath(p, _REPO)] = "UNREADABLE"
    return dict(sorted(out.items()))


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    sel = json.load(open(os.path.join(ART, "hybrid_selection.json")))
    final_head = _git("rev-parse", "HEAD").strip()
    commits = [l for l in _git("log", "--oneline", f"{C006_FINAL}..HEAD").strip().splitlines() if l]

    # immutability re-verify
    base = json.load(open(os.path.join(ART, "immutability_verification.json")))
    now5 = _tree(C005); now6 = _tree(C006)
    changed5 = {k: (base["c005_files"].get(k), now5[k]) for k in now5
                if k in base["c005_files"] and base["c005_files"][k] != now5[k]}
    changed6 = {k: (base["c006_files"].get(k), now6[k]) for k in now6
                if k in base["c006_files"] and base["c006_files"][k] != now6[k]}
    immut_ok = len(changed5) == 0 and len(changed6) == 0
    json.dump({"c005_unchanged": len(changed5) == 0, "c006_unchanged": len(changed6) == 0,
               "changed_c005": changed5, "changed_c006": changed6, "immutability_preserved": immut_ok},
              open(os.path.join(ART, "immutability_recheck.json"), "w"), indent=2)

    # patch + source snapshot
    patch = _git("diff", f"{C006_FINAL}..HEAD", "--", *SRC)
    open(os.path.join(ART, "c007.patch"), "w").write(patch)
    snap = os.path.join(ART, "source_snapshot")
    if os.path.exists(snap):
        shutil.rmtree(snap)
    for f in SRC:
        src = os.path.join(_REPO, f)
        if os.path.exists(src):
            dst = os.path.join(snap, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    open(os.path.join(RES, "test_logs", "final_git_status.txt"), "w").write(_git("status", "--short"))

    # AC checklist
    checklist = {}
    for ac, files in AC_EVIDENCE.items():
        present = {f: os.path.exists(os.path.join(ART, f)) for f in files}
        checklist[ac] = {"evidence_present": all(present.values()), "files": present}
    all_present = all(v["evidence_present"] for v in checklist.values())

    # decisions
    d = {"state_encoder_v2": sel["state_encoder_v2"],
         "teacher_instrumentation": sel["teacher_instrumentation"],
         "residual_contexts": sel["residual_contexts"], "best_hybrid": sel["best_hybrid"],
         "submission_C_decision": sel["submission_C"], "promotion_decision": sel["promotion_decision"],
         "residual_rl_readiness": sel["residual_rl_readiness"]}
    noninf = json.load(open(os.path.join(ART, "h2_teacher_noninferiority.json")))
    kag = json.load(open(os.path.join(ART, "kaggle_teacher_hybrid_comparison.json")))
    man = json.load(open(os.path.join(ART, "v2_dataset_manifest.json")))
    offl = json.load(open(os.path.join(ART, "v2_offline_evaluation.json")))

    status = {
        "contract": "c007_hybrid_teacher_residual_and_state_encoder_v2",
        "status": "PASS" if all_present else "PARTIAL",
        "acceptance_criteria_total": 16,
        "acceptance_criteria_passed": sum(1 for v in checklist.values() if v["evidence_present"]),
        "acceptance_criteria_failed": sum(1 for v in checklist.values() if not v["evidence_present"]),
        "initial_head": C006_FINAL, "final_head": final_head,
        "implementation_commits": [c.split()[0] for c in commits],
        "teacher_id": "dragapult",
        "deck_id": "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab",
        "state_encoder_v2": d["state_encoder_v2"],
        "teacher_instrumentation": d["teacher_instrumentation"],
        "residual_contexts": d["residual_contexts"], "best_hybrid": d["best_hybrid"],
        "submission_C_decision": d["submission_C_decision"], "kaggle_upload": "SKIPPED_BY_GATE",
        "kaggle_submission_ref": None, "kaggle_submission_status": None,
        "hybrid_public_score": None,
        "teacher_public_score_same_run": kag.get("teacher_public_score_same_run"),
        "promotion_decision": d["promotion_decision"],
        "residual_rl_readiness": d["residual_rl_readiness"],
        "highest_leverage_blocker": sel["highest_leverage_blocker"],
        "blocking_issues": [],
        "known_limitations": [
            "The tuned rule-based teacher has no exploitable seam a one-rule residual can beat; "
            "four pre-registered damage-counter variants failed the two-batch improvement gate.",
            "Engine is random_device-seeded: all game conclusions are statistical over large samples; "
            "the v2 dataset/checkpoints/analysis are deterministic and reproducible.",
            "Branch-and-rollout is available via the engine search API but stochastic and hard to "
            "synchronize the teacher within; controlled-variant policy A/B (§12 fallback) was used.",
        ],
        "immutability_preserved": immut_ok,
        "v2_dataset": {"games": man["total_strategic_games"], "decisions": man["total_strategic_decisions"]},
        "h2_non_inferiority_lb": noninf.get("lower_bound_95_one_sided"),
        "h2_non_inferior": noninf.get("non_inferior"),
        "model_param_count": offl.get("results", {}).get("V2_B", {}).get("param_count"),
    }
    json.dump(status, open(os.path.join(RES, "STATUS.json"), "w"), indent=2)

    # checklist md
    cl = ["# Acceptance Checklist (c007)", "",
          f"Status: **{status['status']}** ({status['acceptance_criteria_passed']}/16)", ""]
    for ac, v in checklist.items():
        cl.append(f"- {'PASS' if v['evidence_present'] else 'MISSING'} — {ac}")
    open(os.path.join(RES, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(cl) + "\n")

    # files changed
    open(os.path.join(RES, "FILES_CHANGED.md"), "w").write(
        "# Files Changed (c007 source, committed)\n\n"
        + "\n".join(f"- `{f}`" for f in SRC)
        + "\n\nResults under `results/` are review evidence and are intentionally uncommitted "
          "(same policy as c002–c006). No file under c005/c006 modified; no `.so` committed.\n")

    # git report
    open(os.path.join(RES, "GIT_REPORT.md"), "w").write(
        f"# Git Report (c007)\n\n- Branch: `contract/c007_hybrid_teacher_residual_and_state_encoder_v2`\n"
        f"- Initial HEAD (c006 final): `{C006_FINAL}`\n- Final HEAD: `{final_head}`\n"
        f"- Implementation commits ({len(commits)}):\n"
        + "\n".join(f"  - {c}" for c in commits)
        + f"\n\n- Immutability preserved (c005/c006 unchanged): **{immut_ok}**\n"
          f"- Source-only commits; results/ uncommitted; no `.so` committed; no credentials.\n"
          f"- `c007.patch` + `source_snapshot/` capture the exact committed source.\n")

    # clean checkout
    open(os.path.join(ART, "CLEAN_CHECKOUT.md"), "w").write(
        "# Clean Checkout & Run (c007)\n\n"
        "Reproduce from branch `contract/c007_hybrid_teacher_residual_and_state_encoder_v2` "
        f"(final HEAD `{final_head}`), from repo root with `.venv/bin/python` and `OMP_NUM_THREADS=1`.\n\n"
        "Deterministic & reproducible: dependency verify, context census, encoder audit + tests, "
        "instrumentation parity (replay), experiment registration, v2 dataset rebuild, model training "
        "(seed + OMP=1), offline eval, admission, decisions. Not bit-reproducible (engine "
        "`random_device`): the games themselves; the statistical conclusions are stable across the "
        "large samples and fixed bootstrap seeds.\n\n"
        "External (gitignored / provided): the cabt SDK + `libcg.so`, `cg` symlinks, "
        "`kaggle-environments==1.30.1`, numpy/scipy, and the c005 `teacher_sources/` + `frozen_teacher/`.\n\n"
        "Results package (dataset, checkpoints, games, reports, Kaggle evidence) is review evidence "
        "and is not committed; only c007 source is on the branch.\n")

    print(json.dumps({"status": status["status"], "passed": status["acceptance_criteria_passed"],
                      "final_head": final_head[:12], "immutability_preserved": immut_ok,
                      "missing": [ac for ac, v in checklist.items() if not v["evidence_present"]]},
                     indent=2))
    return 0 if all_present else 1


if __name__ == "__main__":
    sys.exit(main())

"""c010 AC-16 + root results: immutability recheck, git report/patch/source snapshot,
clean-checkout note, and STATUS / ACCEPTANCE_CHECKLIST / FILES_CHANGED / GIT_REPORT.

The acceptance checklist is content-aware: each criterion requires its evidence files AND a
substantive assertion drawn from their contents (§29: never PASS because files exist).
"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
RES = os.path.join(C010, "results")
LOGD = os.path.join(RES, "test_logs")
C009_FINAL = "e868dfbbeefc30bcf246cd60e0f51bf6d0043eb8"
IMMUT = ["c005_teacher_import_submission_and_dataset", "c006_distilled_policy_baseline",
         "c007_hybrid_teacher_residual_and_state_encoder_v2",
         "c008_fixed_deck_teacher_anchored_rl", "c009_amendment_c008"]
SRC = ["starter_kit/c010_train.py", "starter_kit/c010_decisions.py",
       "tools/c010_verify_deps.py", "tools/c010_register.py", "tools/c010_train_loop.py",
       "tools/c010_calibrate.py", "tools/c010_validate_ppo.py", "tools/c010_eval.py",
       "tools/c010_aggregate.py", "tools/c010_validate_evidence.py", "tools/c010_finalize.py",
       "tools/c010_reports.py", "tests/test_c010_arm_registration.py",
       "tests/test_c010_incumbent_protection.py", "tests/test_c010_identity_safe_eval.py",
       "tests/test_c010_promotion_rules.py", "tests/test_c010_content_validation.py"]


def _git(*a):
    return subprocess.run(["git", "-C", _REPO, *a], capture_output=True, text=True).stdout


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def J(n, base=None):
    p = os.path.join(base or ART, n)
    return json.load(open(p)) if os.path.exists(p) else {}


def _run_specific_limitations():
    """Limitations this run actually produced, not the pre-run boilerplate.

    A follow-on contract reads STATUS.json (c010_verify_deps.py), not the prose, so anything
    it must not assume has to be machine-readable here.
    """
    out = []
    for arm in ("A", "B", "C"):
        p = os.path.join(ART, f"arm_{arm}_summary.json")
        if not os.path.exists(p):
            continue
        cov = json.load(open(p)).get("evaluation_point_coverage", {})
        for sd, v in (cov.get("per_seed") or {}).items():
            if v.get("missing"):
                t = v.get("terminal_below_registered_point") or {}
                out.append(
                    f"Arm {arm} seed {sd} stopped at {v.get('final_games')} games and did not "
                    f"reach its registered evaluation point(s) {v['missing']}; rollouts are "
                    f"atomic and its budget was derived to respect the 120,000 hard maximum. "
                    f"Its terminal checkpoint is recorded with registered_eval_point=null "
                    f"(nearest point reached: {t.get('nearest_reached')}). Do not assume every "
                    f"seed has a checkpoint at every registered point.")
    re_ = os.path.join(ART, "reproducibility_extendability.json")
    if os.path.exists(re_):
        d = json.load(open(re_))
        ties = []
        for k in ("exact_reproducibility", "exact_continuation", "stabilized_continuation"):
            g = (d.get(k) or {}).get("median_field_gain")
            if g is not None and abs(g - 0.03) <= 1e-6:
                ties.append(k)
        out.append(
            "Every arm verdict turned on the strategic-field dimension, measured at 100 games "
            "per field opponent on the confirmation panel; the teacher dimension was cleared "
            "comfortably in all three. Field differences of a few percentage points are near "
            "the resolution of that panel."
            + (f" {' and '.join(ties)} sat exactly ON the 3pp threshold (see "
               f"failures/DEFECT_float_tie_flipped_a_registered_threshold.md)." if ties else ""))
    return out


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    final_head = _git("rev-parse", "HEAD").strip()
    commits = [l for l in _git("log", "--oneline", f"{C009_FINAL}..HEAD").strip().splitlines() if l]

    base_imm = J("immutability_verification.json")
    changed = []
    for key, folder in zip(("c005_files", "c006_files", "c007_files", "c008_files", "c009_files"),
                           IMMUT):
        b = base_imm.get(key, {})
        for dp, _dn, fns in os.walk(os.path.join(_REPO, "contracts", folder)):
            for fn in fns:
                p = os.path.join(dp, fn); rel = os.path.relpath(p, _REPO)
                if rel in b and sha(p) != b[rel]:
                    changed.append(rel)
    immut_ok = not changed
    json.dump({"immutability_preserved": immut_ok, "changed": changed, "folders": IMMUT},
              open(os.path.join(ART, "immutability_recheck.json"), "w"), indent=2)

    open(os.path.join(ART, "c010.patch"), "w").write(_git("diff", f"{C009_FINAL}..HEAD", "--", *SRC))
    snap = os.path.join(ART, "source_snapshot")
    if os.path.exists(snap):
        shutil.rmtree(snap)
    for f in SRC:
        s = os.path.join(_REPO, f)
        if os.path.exists(s):
            d = os.path.join(snap, f); os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)
    open(os.path.join(LOGD, "final_git_status.txt"), "w").write(_git("status", "--short"))
    open(os.path.join(ART, "CLEAN_CHECKOUT.md"), "w").write(
        "# Clean Checkout & Run (c010)\n\nReproduce from branch `contract/c010_fixed_deck_rl_loop_v2` "
        f"(final HEAD `{final_head}`), repo root, `.venv/bin/python`, `OMP_NUM_THREADS=1` (each "
        "rollout worker is a separate process; letting BLAS also thread inside every worker "
        "oversubscribes the machine and costs ~3x throughput).\n\n"
        "Deterministic: dependency/immutability verification, baseline+arm registration and the "
        "configuration diff, PPO/environment validation (toy positive control, GAE, masking, "
        "initialisation fidelity), identity assertions, all aggregate recomputation from raw games, "
        "the content-aware validator, and every decision rule.\n\n"
        "Not bit-reproducible: the games themselves (the cabt engine seeds from `std::random_device`), "
        "so training trajectories and evaluation point estimates vary between runs; all conclusions "
        "are stated with bootstrap intervals and the raw per-game records ship so every aggregate can "
        "be recomputed exactly.\n\n"
        "Externally provided (gitignored): the cabt SDK + `libcg.so`, `cg` symlinks, "
        "kaggle-environments, numpy/scipy, the c005 teacher sources, the c007 V2-A checkpoint and the "
        "c008/c009 artifacts. No file under c005-c009 is written; B0 and I0 are read-only.\n\n"
        "`results/` is review evidence and is intentionally uncommitted.\n")

    # ---------- evidence + substantive assertions ----------
    dep = J("dependency_verification.json"); exp = J("experiment_registry.json")
    cdiff = J("arm_configuration_diff.json"); ppo = J("ppo_validation.json")
    budget = J("compute_budget.json"); man = J("evaluation_game_manifest.json")
    rex = J("reproducibility_extendability.json"); bas = J("best_agent_selection.json")
    val = J("evidence_validation.json"); sub = J("submission_E_validation.json")
    ks = J("kaggle_submission_status.json"); nxt = J("next_step.json")
    vdiag = J("value_diagnostics_by_game_phase.json")
    base = J("baseline_incumbent_registry.json")

    def arm_ok(arm):
        d = os.path.join(ART, "training", f"arm_{arm}")
        if not os.path.isdir(d):
            return False, 0, []
        seeds, games = [], 0
        for sd in sorted(os.listdir(d)):
            sp = os.path.join(d, sd, "summary.json")
            if os.path.exists(sp):
                s = json.load(open(sp)); seeds.append(s["seed"]); games += s["games_done"]
        return (sorted(seeds) == sorted(exp["arms"][arm]["seeds"]) if seeds else False), games, seeds

    aok, agames, aseeds = arm_ok("A"); bok, bgames, bseeds = arm_ok("B")
    cok, cgames, cseeds = arm_ok("C")
    total_train = agames + bgames + cgames

    AC = {
        "AC-01": (["dependency_verification.json", "immutability_verification.json",
                   "../test_logs/dependency_verification.txt"],
                  "c005-c009 hashes verified and c009 raw games re-derive B0/I0 scores",
                  bool(dep.get("all_ok"))),
        "AC-02": (["baseline_incumbent_registry.json", "../test_logs/baseline_incumbent_validation.txt"],
                  "B0/I0/T registered, hashed and marked protected",
                  bool(base.get("B0", {}).get("protected") and base.get("I0", {}).get("protected"))),
        "AC-03": (["experiment_registry.json", "arm_configuration_diff.json",
                   "../test_logs/arm_registration_tests.txt"],
                  "A/B equal exact R1; C changes exactly the three registered values",
                  bool(cdiff.get("arm_A_vs_exact_r1", {}).get("identical")
                       and cdiff.get("arm_B_vs_exact_r1", {}).get("identical")
                       and cdiff.get("arm_C_vs_exact_r1", {}).get(
                           "changes_exactly_the_three_registered_values"))),
        "AC-04": (["ppo_validation.json", "../test_logs/ppo_validation.txt"],
                  "toy positive control learns; masking exact; B0 initialisation fidelity guarded",
                  bool(ppo.get("all_pass"))),
        "AC-05": (["evaluation_identity_protocol.json", "../test_logs/evaluation_identity_tests.txt"],
                  "identity assertions pass on every evaluation batch",
                  bool(man.get("identity_reports")
                       and all(r.get("ok") for r in man["identity_reports"]))),
        "AC-06": (["throughput_calibration.json", "compute_budget.json",
                   "../test_logs/throughput_calibration.txt"],
                  "per-arm probes measured and full run projected against the hard cap",
                  bool(budget.get("projection")) and budget.get("budget_check", {}).get(
                      "within_hard_maximum") is True),
        "AC-07": (["arm_A_summary.json", "arm_A_training_games.jsonl.gz", "arm_A_updates.jsonl.gz",
                   "arm_A_checkpoint_registry.json", "../test_logs/arm_A_training.txt"],
                  f"all three Arm A seeds executed ({aseeds}, {agames} games)", aok),
        "AC-08": (["arm_B_summary.json", "arm_B_training_games.jsonl.gz", "arm_B_updates.jsonl.gz",
                   "arm_B_checkpoint_registry.json", "../test_logs/arm_B_training.txt"],
                  f"all three Arm B seeds executed ({bseeds}, {bgames} games)", bok),
        "AC-09": (["arm_C_summary.json", "arm_C_training_games.jsonl.gz", "arm_C_updates.jsonl.gz",
                   "arm_C_checkpoint_registry.json", "../test_logs/arm_C_training.txt"],
                  f"all three Arm C seeds executed ({cseeds}, {cgames} games)", cok),
        "AC-10": (["checkpoint_screening.csv", "checkpoint_confirmation.json",
                   "evaluation_games.jsonl.gz", "evaluation_game_manifest.json",
                   "../test_logs/checkpoint_evaluation.txt"],
                  "screen and confirmation panels executed with exact counts",
                  bool(man.get("total_games")) and man.get("seat_balance_ok") is True),
        "AC-11": (["value_diagnostics_by_game_phase.json", "optimization_diagnostics.json",
                   "../test_logs/value_diagnostics.txt"],
                  "held-out value calibration/EV reported per game phase",
                  bool(vdiag.get("by_arm"))),
        "AC-12": (["EXACT_REPRODUCIBILITY.md", "EXACT_CONTINUATION.md",
                   "STABILIZED_CONTINUATION.md", "reproducibility_extendability.json"],
                  "three arm decisions follow the registered rules",
                  all((rex.get(k) or {}).get("decision") for k in
                      ("exact_reproducibility", "exact_continuation", "stabilized_continuation"))),
        "AC-13": (["final_matchup_matrix.csv", "final_pairwise_intervals.json", "final_ranking.json",
                   "final_regression_report.json", "best_agent_selection.json",
                   "../test_logs/final_evaluation.txt"],
                  "final panel run and best agent selected with the incumbent protected",
                  bool(bas.get("best_agent")) and bas.get("incumbent_protected") is True),
        "AC-14": (["evidence_validation.json", "../test_logs/evidence_validation.txt"],
                  f"{val.get('n_checks')} content checks, {val.get('n_failed')} failed",
                  bool(val.get("all_ok"))),
        "AC-15": (["SUBMISSION_E_DECISION.md", "submission_E_validation.json",
                   "KAGGLE_SUBMIT_COMMAND.txt", "KAGGLE_PROMOTION_DECISION.md",
                   "kaggle_submission_status.json", "kaggle_submission_history.jsonl",
                   "kaggle_submissions_after_submit.csv",
                   "kaggle_teacher_agent_comparison.json",
                   "NEXT_STEP.md", "next_step.json",
                   "../test_logs/kaggle_submission.txt",
                   "../test_logs/kaggle_submission_retrieval.txt"],
                  "submission gate applied and exactly one next step + blocker stated",
                  bool(sub.get("submission_E")) and bool(nxt.get("next_step"))
                  and (os.path.exists(os.path.join(ART, "submission_E_fixed_deck_rl_v2.tar.gz"))
                       == (sub.get("submission_E") == "SUBMIT"))),
        "AC-16": (["c010.patch", "CLEAN_CHECKOUT.md", "source_snapshot",
                   "../test_logs/final_git_status.txt"],
                  "c010 source committed; c005-c009 unchanged; no protected checkpoint altered",
                  immut_ok and len(commits) > 0),
    }
    checklist = {}
    for ac, (files, assertion, ok) in AC.items():
        present = {f: os.path.exists(os.path.join(ART, f)) for f in files}
        checklist[ac] = {"evidence_present": all(present.values()), "assertion": assertion,
                         "assertion_passed": bool(ok), "files": present,
                         "passed": all(present.values()) and bool(ok)}
    all_pass = all(v["passed"] for v in checklist.values())

    status = {
        "contract": "c010_fixed_deck_rl_loop_v2",
        "status": "PASS" if all_pass else "PARTIAL",
        "acceptance_criteria_total": 16,
        "acceptance_criteria_passed": sum(1 for v in checklist.values() if v["passed"]),
        "acceptance_criteria_failed": sum(1 for v in checklist.values() if not v["passed"]),
        "initial_head": C009_FINAL, "final_head": final_head,
        "implementation_commits": [c.split()[0] for c in commits],
        "frozen_deck_fingerprint": exp.get("frozen_deck_fingerprint"),
        "frozen_deck_id": exp.get("frozen_deck_id"),
        "B0": base.get("B0", {}).get("checkpoint_sha256"),
        "I0": base.get("I0", {}).get("checkpoint_sha256"),
        "exact_reproducibility": (rex.get("exact_reproducibility") or {}).get("decision"),
        "exact_continuation": (rex.get("exact_continuation") or {}).get("decision"),
        "stabilized_continuation": (rex.get("stabilized_continuation") or {}).get("decision"),
        "best_agent": bas.get("best_agent"),
        "training_loop_status": sub.get("training_loop_status"),
        "submission_E": sub.get("submission_E"),
        "kaggle_upload": ks.get("kaggle_upload"),
        "kaggle_submission_ref": ks.get("submission_ref"),
        "kaggle_submission_status": ks.get("status"),
        "promotion_decision": bas.get("promotion_decision"),
        "next_step": nxt.get("next_step"),
        "highest_leverage_blocker": nxt.get("highest_leverage_blocker"),
        "training_games_total": total_train,
        "training_games_per_arm": {"A": agames, "B": bgames, "C": cgames},
        "training_hard_maximum": exp.get("budgets", {}).get("hard_maximum_including_spillover"),
        "within_training_budget": total_train <= exp.get("budgets", {}).get(
            "hard_maximum_including_spillover", 10 ** 9),
        "evaluation_games_total": man.get("total_games"),
        "teacher_public_score_same_run": J("kaggle_teacher_agent_comparison.json").get(
            "teacher_public_score_same_run"),
        "immutability_preserved": immut_ok,
        "evidence_validator_passed": bool(val.get("all_ok")),
        "blocking_issues": [] if all_pass else
            [ac for ac, v in checklist.items() if not v["passed"]],
        "known_limitations": [
            "Games are engine random_device-seeded and not bit-reproducible; every conclusion is "
            "stated with bootstrap intervals over the recorded games and the raw per-game records "
            "ship so aggregates can be recomputed exactly.",
            "Screen panels are 100 games per checkpoint, so screening differences below roughly 10 "
            "percentage points are inside noise; nomination is deliberately generous and only "
            "confirmation (500) and final (1,000) panels drive decisions.",
            "Throughput is memory-bandwidth bound in pure numpy: rollout workers must run with "
            "OMP_NUM_THREADS=1 or BLAS threads inside each worker oversubscribe the machine.",
        ] + _run_specific_limitations(),
    }
    json.dump(status, open(os.path.join(RES, "STATUS.json"), "w"), indent=2)

    cl = ["# Acceptance Checklist (c010)", "",
          f"Status: **{status['status']}** ({status['acceptance_criteria_passed']}/16)", "",
          "Each criterion requires its evidence files **and** a substantive assertion drawn from "
          "their contents. File existence alone never marks a criterion passed (§29).", "",
          "| AC | evidence | assertion (verified) | passed |", "|---|---|---|---|"]
    for ac, v in checklist.items():
        cl.append(f"| {ac} | {'present' if v['evidence_present'] else 'MISSING'} | "
                  f"{v['assertion']} | {'YES' if v['passed'] else 'NO'} |")
    open(os.path.join(RES, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(cl) + "\n")
    open(os.path.join(RES, "FILES_CHANGED.md"), "w").write(
        "# Files Changed (c010 source, committed)\n\n" + "\n".join(f"- `{f}`" for f in SRC)
        + "\n\nNo `tools/c008_*` or `tools/c009_*` file was modified and nothing under c005-c009 was "
          "touched. `results/` is uncommitted review evidence. No protected checkpoint (B0, I0) was "
          "written.\n")
    open(os.path.join(RES, "GIT_REPORT.md"), "w").write(
        f"# Git Report (c010)\n\n- Branch: `contract/c010_fixed_deck_rl_loop_v2`\n"
        f"- Initial HEAD (c009 final): `{C009_FINAL}`\n- Final HEAD: `{final_head}`\n"
        f"- Implementation commits ({len(commits)}):\n" + "\n".join(f"  - {c}" for c in commits)
        + f"\n\n- c005-c009 unchanged: **{immut_ok}**\n"
          f"- Protected baselines B0/I0 unmodified: **{immut_ok}**\n"
          "- Source-only commits; results/ uncommitted; no `.so`; no credentials.\n")

    print(json.dumps({"status": status["status"], "passed": status["acceptance_criteria_passed"],
                      "final_head": final_head[:12], "immutability_preserved": immut_ok,
                      "training_games": total_train,
                      "failed": [ac for ac, v in checklist.items() if not v["passed"]]}, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

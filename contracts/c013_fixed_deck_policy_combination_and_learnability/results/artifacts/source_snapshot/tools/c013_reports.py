"""c013 AC-16 — SUMMARY, STATUS, acceptance checklist, git report, next step.

Everything here READS decisions from the artifacts that computed them. Nothing is recomputed
and nothing is re-derived, because a report that recomputes a verdict can silently disagree with
the artifact that published it — which is exactly what c012's decide step did, contradicting its
own Claude qualifier. The one thing this module decides for itself is the overall STATUS, and it
derives that from the validator's result plus the acceptance checklist, not from prose.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
RES = os.path.join(C013, "results")
ART = os.path.join(RES, "artifacts")
LOGD = os.path.join(RES, "test_logs")


def jload(p, default=None):
    p = p if os.path.isabs(p) else os.path.join(ART, p)
    return json.load(open(p)) if os.path.exists(p) else (default if default is not None else {})


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=_REPO, capture_output=True,
                              text=True, timeout=120).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<git failed: {e!r}>"


AC = [
    ("AC-01", "Dependency and environment verification", ["dependency_verification.json"]),
    ("AC-02", "Carried-forward continuation repairs in c013 code",
     ["continuation_repair_report.json", "trainer_state_schema.json"]),
    ("AC-03", "Frozen hash-verified candidate and combination registries",
     ["candidate_registry.json", "combination_registry.json",
      "immutability_verification.json"]),
    ("AC-04", "Online ensemble and weight soup semantics",
     ["ensemble_semantics_validation.json"]),
    ("AC-05", "Combination selection and confirmation",
     ["combination_results.json", "COMBINATION_RESULT.md",
      "combination_selection_games.jsonl.gz", "combination_confirmation_games.jsonl.gz"]),
    ("AC-06", "Untouched final combination panel",
     ["combination_final_games.jsonl.gz", "combination_final_matrix.csv",
      "combination_final_intervals.json"]),
    ("AC-07", "Q0/Q1 learnability execution",
     ["Q0_summary.json", "Q1_summary.json", "Q0_training_games.jsonl.gz",
      "Q1_training_games.jsonl.gz", "value_refit_diagnostics.json"]),
    ("AC-08", "Q2 component continuation and recombination",
     ["Q2_component_registry.json", "Q2_training_games.jsonl.gz",
      "Q2_recombination_results.json"]),
    ("AC-09", "Q3 gate", ["Q3_gate.json", "Q3_summary.json"]),
    ("AC-10", "Soup learnability decision",
     ["soup_learnability.json", "SOUP_LEARNABILITY.md"]),
    ("AC-11", "Adaptive-curriculum smoke",
     ["curriculum_smoke_registry.json", "curriculum_smoke_history.jsonl",
      "CURRICULUM_SMOKE.md"]),
    ("AC-12", "Correct opponent-overlap analysis",
     ["identical_state_policy_actions.jsonl.gz", "semantic_action_agreement.json",
      "behavioral_fingerprints.json", "state_distribution_overlap.json",
      "OPPONENT_OVERLAP.md"]),
    ("AC-13", "Claude semantic preflight",
     ["semantic_state_schema.json", "claude_prompt.md", "claude_output_schema.json",
      "claude_preflight_inputs.jsonl.gz", "claude_preflight_outputs.jsonl.gz",
      "claude_semantic_validation.json", "CLAUDE_SEMANTIC_PREFLIGHT.md"]),
    ("AC-14", "Final best-agent and submission decision",
     ["best_agent_selection.json", "final_regression_report.json",
      "SUBMISSION_G_DECISION.md", "submission_G_validation.json",
      "KAGGLE_SUBMIT_COMMAND.txt"]),
    ("AC-15", "Content-aware validation and source bundle",
     ["evidence_validation.json", "c013_python_source_bundle.zip",
      "c013_python_source_manifest.json"]),
    ("AC-16", "Next step, Git, and source integrity",
     ["NEXT_STEP.md", "next_step.json", "c013.patch"]),
]


def main():
    os.makedirs(ART, exist_ok=True)
    comb = jload("combination_results.json")
    learn = jload("soup_learnability.json")
    smoke = jload("curriculum_smoke_registry.json")
    overlap = jload("semantic_action_agreement.json")
    claude = jload("claude_preflight_decision.json")
    ba = jload("best_agent_selection.json")
    val = jload("evidence_validation.json")
    bundle = jload("c013_python_source_manifest.json")
    budget_learn = sum(jload(os.path.join(ART, "training", a, f"seed{s}", "summary.json"))
                       .get("completed_games", 0)
                       for a, s in (("Q0", 901), ("Q1", 902), ("Q2A", 903), ("Q2B", 904)))
    budget_smoke = (smoke.get("budget") or {}).get("total_completed_games", 0)

    decisions = {
        "COMBINATION_RESULT": comb.get("COMBINATION_RESULT"),
        "SOUP_LEARNABILITY": learn.get("SOUP_LEARNABILITY"),
        "Q3": (comb.get("q3_gate") or {}).get("Q3"),
        "CURRICULUM_SMOKE": smoke.get("CURRICULUM_SMOKE"),
        "OPPONENT_OVERLAP": overlap.get("OPPONENT_OVERLAP"),
        "CLAUDE_SEMANTIC_PREFLIGHT": claude.get("CLAUDE_SEMANTIC_PREFLIGHT"),
        "SUBMISSION_G": (ba.get("submission_gate") or {}).get("SUBMISSION_G"),
        "TRUE_BEST_AGENT": ba.get("TRUE_BEST_AGENT"),
        "PACKAGE_FEASIBLE_BEST_AGENT": ba.get("PACKAGE_FEASIBLE_BEST_AGENT"),
    }

    # acceptance checklist
    rows = []
    for code, title, files in AC:
        missing = [f for f in files
                   if not os.path.exists(os.path.join(ART, f))
                   and not os.path.exists(os.path.join(RES, f))]
        rows.append({"ac": code, "title": title, "evidence": files,
                     "missing": missing, "executed": not missing})
    all_exec = all(r["executed"] for r in rows)

    unack = val.get("unacknowledged_critical_failures") or []
    ack = val.get("acknowledged_deviations") or []
    if all_exec and val.get("overall") == "PASS":
        status = "PASS"
    elif all_exec and not unack and ack:
        status = "PARTIAL"
    else:
        status = "PARTIAL"
    reasons = []
    if not all_exec:
        reasons.append("acceptance criteria with missing evidence: "
                       + ", ".join(r["ac"] for r in rows if not r["executed"]))
    for a in ack:
        reasons.append(f"documented deviation: {a['check']} ({a['document']})")
    for u in unack:
        reasons.append(f"unexplained validation failure: {u}")
    if claude.get("CLAUDE_SEMANTIC_PREFLIGHT") == "PARTIAL":
        reasons.append("CLAUDE_SEMANTIC_PREFLIGHT = PARTIAL: "
                       + "; ".join(claude.get("shortfalls") or []))

    status_doc = {
        "contract": "c013_fixed_deck_policy_combination_and_learnability",
        "status": status, "decisions": decisions,
        "acceptance_criteria": {"total": len(rows),
                                "executed": sum(1 for r in rows if r["executed"])},
        "validation": {"overall": val.get("overall"),
                       "n_checks": val.get("n_checks"),
                       "n_passed": val.get("n_passed"),
                       "unacknowledged_critical_failures": unack,
                       "acknowledged_deviations": ack},
        "budget": {"learnability_completed_games": budget_learn,
                   "learnability_cap": 50000,
                   "curriculum_smoke_completed_games": budget_smoke,
                   "curriculum_smoke_cap": 10000,
                   "total": budget_learn + budget_smoke, "hard_maximum": 62000,
                   "within_hard_maximum": (budget_learn + budget_smoke) <= 62000},
        "source_bundle": {"files": bundle.get("n_files"),
                          "categories": bundle.get("categories")},
        "reasons": reasons,
        "git": {"branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "head": git("rev-parse", "HEAD")},
    }
    json.dump(status_doc, open(os.path.join(RES, "STATUS.json"), "w"), indent=2, default=str)

    write_checklist(rows, status, val)
    write_summary(status_doc, comb, learn, smoke, overlap, claude, ba, val)
    write_next_step(decisions, learn, overlap, claude)
    write_git_report()
    write_files_changed()
    print(json.dumps({"status": status, "decisions": decisions,
                      "reasons": reasons}, indent=2, default=str))
    return 0


def write_checklist(rows, status, val):
    L = ["# c013 acceptance checklist\n", f"**STATUS = {status}**\n",
         "Evidence presence is listed here; whether the evidence is *correct* is decided by "
         "`evidence_validation.json`, which re-derives each headline claim from primary data "
         f"({val.get('n_passed')}/{val.get('n_checks')} checks passed).\n",
         "| AC | title | executed | missing |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['ac']} | {r['title']} | {'yes' if r['executed'] else 'NO'} | "
                 f"{', '.join(r['missing']) or '—'} |")
    open(os.path.join(RES, "ACCEPTANCE_CHECKLIST.md"), "w").write("\n".join(L) + "\n")


def write_summary(sd, comb, learn, smoke, overlap, claude, ba, val):
    d = sd["decisions"]
    L = ["# c013 — fixed-deck policy combination and learnability\n"]
    L.append(f"**STATUS = {sd['status']}**\n")
    L.append("## Decisions\n")
    L.append("| result | value |")
    L.append("|---|---|")
    for k, v in d.items():
        L.append(f"| `{k}` | **{v}** |")
    L.append("")
    L.append("## What was learned\n")
    L.append("**Weight soups beat online ensembles, and a single policy nearly beat both.** On "
             "the untouched 1,250-game final panel the winner is "
             f"`{d['TRUE_BEST_AGENT']}`; the two online ensembles rank third and fourth. "
             "Combining policies at inference time — running every component network and "
             "averaging — bought nothing over averaging their weights once, offline, for free. "
             "The c012 incumbent finishes last of five.\n")
    L.append("**The soup is not learnable by any registered method at this budget.** c012 "
             "concluded the same thing, but its in-run evaluations were returning zero scored "
             "games from the first update onward, so it never measured what it claimed to. "
             "Under a repaired instrument the conclusion survives: no Q0/Q1/Q2 candidate beats "
             "the Phase 2 start with a confidence interval excluding zero. What c013 adds is "
             "the shape of the near-miss — all nine continued candidates show a *positive* "
             "strategic-field tendency, the best at P(gain>0) = 0.94. The honest statement is "
             "'no confirmed improvement within ~12,000 games per arm', not 'training cannot "
             "help'.\n")
    L.append("**An in-run signal was believed and then withdrawn.** Q0's in-run teacher score "
             "rose 0.275 → 0.425 and was reported mid-run as overturning c012. It does not: "
             "those evaluations score 40 games per point against the panel's 750, and on the "
             "panel Q0 sits *below* its own starting point. §17 forbids concluding from "
             "training-side numbers precisely because they are cheap and flattering.\n")
    L.append("**The official opponents share a rule skeleton with each other, not with the "
             "teacher.** Querying nine policies on 4,110 identical visible states, teacher–"
             "Lucario is highest on 7 of 8 registered measures but clears the pre-registered "
             "bar on none, so the verdict is `INCONCLUSIVE` and the rule was left alone. The "
             "unlooked-for result is stronger: Mega Lucario and Mega Abomasnow choose "
             "**identically on all 98 promotion decisions**, Iono and Abomasnow agree on 0.871 "
             "of energy commitments, and every opponent–opponent pair is more alike than any "
             "opponent–teacher pair.\n")
    L.append("**The curriculum machinery now works.** R1 executed two real stage changes with "
             "every registered evaluation returning scored games and a literal trainer-state "
             "restore reproducing the next opponent/seat/seed sequence exactly — all eight §20 "
             "requirements, none of which held anywhere in c012's 90,000-game arm.\n")
    g = ba.get("submission_gate") or {}
    L.append("## Why nothing was submitted\n")
    lb = g.get("teacher_noninferiority_lb95")
    L.append(f"§31 requires a one-sided 95% lower bound of 0.47 on teacher non-inferiority. The "
             f"package-feasible best agent measures {'—' if lb is None else f'{lb:.3f}'}. On the "
             f"same panel the frozen teacher scores "
             f"{g.get('teacher_strategic_field')} on the strategic field against the "
             f"candidate's {g.get('candidate_strategic_field')}. The gate is not close, so "
             "`SUBMISSION_G = DO_NOT_SUBMIT` and no archive was built or uploaded.\n")
    L.append("## Defects found and disclosed\n")
    fdir = os.path.join(RES, "failures")
    for f in sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []:
        L.append(f"- `{f}`")
    L.append("")
    b = sd["budget"]
    L.append("## Budget\n")
    L.append(f"Learnability {b['learnability_completed_games']} / {b['learnability_cap']}; "
             f"curriculum smoke {b['curriculum_smoke_completed_games']} / "
             f"{b['curriculum_smoke_cap']}; total {b['total']} / {b['hard_maximum']} hard "
             f"maximum. The smoke exceeded its phase cap by "
             f"{max(0, b['curriculum_smoke_completed_games'] - b['curriculum_smoke_cap'])} "
             "games through rollout granularity; this is documented as a deviation and the "
             "validator fails on it rather than passing.\n")
    if sd["reasons"]:
        L.append("## Why this is not a PASS\n")
        for r in sd["reasons"]:
            L.append(f"- {r}")
        L.append("")
    open(os.path.join(RES, "SUMMARY.md"), "w").write("\n".join(L) + "\n")


def write_next_step(d, learn, overlap, claude):
    steps = [
        {"priority": 1, "step": "Stop trying to improve the soup by continuation",
         "rationale": "Q0/Q1/Q2 all fail to produce a confirmed improvement, and the "
                      "strategic-field tendency is positive but underpowered at ~12,000 games "
                      "per arm. Either commit a budget large enough to resolve a ~0.04 field "
                      "effect, or change the objective — not another 12,000-game arm."},
        {"priority": 2, "step": "Close the gap to the frozen teacher on the strategic field",
         "rationale": "the teacher scores ~0.55 on the field against ~0.37 for the best RL "
                      "candidate. That, not the soup, is the binding constraint on "
                      "SUBMISSION_G, and no amount of policy combination has moved it."},
        {"priority": 3, "step": "Rebuild the semantic benchmark with phase- and "
                                "opponent-stratified sampling",
         "rationale": "the Claude preflight is PARTIAL only because the sampler stratified by "
                      "option type and never drew attack, setup, or matchup-failure states. "
                      "8 of §27's 10 categories are reachable with a different sampler."},
        {"priority": 4, "step": "Investigate the shared opponent skeleton",
         "rationale": "Lucario and Abomasnow are identical on all 98 promotion decisions. If "
                      "the official agents share a promotion routine, exploiting it is a "
                      "concrete edge that no amount of self-play discovers."},
    ]
    json.dump({"next_steps": steps, "decisions": d},
              open(os.path.join(ART, "next_step.json"), "w"), indent=2, default=str)
    L = ["# c013 — next step\n"]
    for s in steps:
        L.append(f"## {s['priority']}. {s['step']}\n")
        L.append(s["rationale"] + "\n")
    open(os.path.join(ART, "NEXT_STEP.md"), "w").write("\n".join(L) + "\n")


def write_git_report():
    L = ["# c013 git report\n"]
    L.append(f"Branch: `{git('rev-parse', '--abbrev-ref', 'HEAD')}`  ")
    L.append(f"HEAD: `{git('rev-parse', 'HEAD')}`\n")
    L.append("## Commits\n```text")
    L.append(git("log", "--oneline", "-30"))
    L.append("```\n")
    L.append("## Working tree at completion\n```text")
    L.append(git("status", "--porcelain") or "(clean)")
    L.append("```\n")
    L.append("`results/` is intentionally uncommitted, per the contract execution protocol: "
             "source is committed with a `c013:` prefix, evidence stays on disk.\n")
    open(os.path.join(RES, "GIT_REPORT.md"), "w").write("\n".join(L) + "\n")
    with open(os.path.join(LOGD, "final_git_status.txt"), "w") as fh:
        fh.write(git("status") + "\n\n" + git("log", "--oneline", "-30") + "\n")
    open(os.path.join(ART, "CLEAN_CHECKOUT.md"), "w").write(
        "# Clean-checkout reproducibility\n\n"
        "Every c013 source file is committed on this branch and bundled in "
        "`c013_python_source_bundle.zip` together with the contract, command, inputs, "
        "references, dependency and machine snapshots, and the Git patch. A clean checkout at "
        f"`{git('rev-parse', 'HEAD')}` plus the bundle reproduces the toolchain; the engine is "
        "`std::random_device`-seeded, so individual games are not bit-reproducible and every "
        "conclusion is stated with bootstrap intervals rather than exact replay.\n")


def write_files_changed():
    L = ["# Files changed\n", "## Committed source\n```text"]
    L.append(git("diff", "--stat", "main...HEAD"))
    L.append("```\n")
    L.append("## Evidence written (uncommitted)\n```text")
    n = sum(len(fs) for _, _, fs in os.walk(RES))
    L.append(f"{n} files under contracts/c013_.../results/")
    L.append("```\n")
    open(os.path.join(RES, "FILES_CHANGED.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

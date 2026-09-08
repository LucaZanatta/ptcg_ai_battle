"""c018 §35 — conform the results tree to the layout the contract specifies.

The evidence all existed, but under an ad-hoc layout of my own. §35 gives an exact structure,
and the stated purpose of the archive is that it be "sufficient for an independent code and
evidence audit" — an auditor looking for `models/curriculum/` should not have to discover that
it lives in `checkpoints/`. A correct archive in the wrong shape is a findability defect, which
for an audit deliverable is a real one.

Files are HARD-LINKED into their contract-specified locations rather than moved or copied:
every tool that already writes and reads its own path keeps working, nothing is duplicated on
disk (these are hundreds of MB of checkpoints), and the two paths are provably the same bytes
because they are the same inode.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(_REPO, "contracts",
                    "c018_complete_integrated_search_learning_curriculum_campaign")
C18 = os.path.join(CDIR, "results")

# contract-required directories, including the ones that stay empty with a README saying why
DIRS = [
    "baseline", "configs", "integration", "git",
    "search/roots", "search/traces", "search/lifecycle", "search/determinizations",
    "search/latency", "search/fixtures", "search/raw_games",
    "trajectories/manifests", "trajectories/representative_samples", "trajectories/trusted",
    "trajectories/diagnostic", "trajectories/integrity",
    "models/distillation", "models/curriculum", "models/guided",
    "training/configs", "training/checkpoints", "training/optimizer_states", "training/logs",
    "training/raw_rollouts", "training/evaluations", "training/resume_probes",
]

# (source relative to results/, destination relative to results/)
LINKS = [
    ("artifacts/parent_resolution.json", "baseline/parent_resolution.json"),
    ("artifacts/immutability_baseline_pre_c018.json",
     "baseline/immutability_baseline_pre_c018.json"),
    ("artifacts/baseline_anchor.json", "baseline/baseline_anchor.json"),
    ("artifacts/thin_vertical.json", "integration/thin_vertical.json"),
    ("artifacts/defect_ranking.json", "integration/defect_ranking.json"),
    ("artifacts/export_round_trip.json", "integration/export_round_trip.json"),
    ("artifacts/node_budget_defect.json", "integration/node_budget_defect.json"),
    ("artifacts/lifecycle_extended.json", "search/lifecycle/lifecycle_extended.json"),
    ("artifacts/branch_proof.json", "search/traces/branch_proof.json"),
    ("artifacts/tactical_fixtures.json", "search/fixtures/tactical_fixtures.json"),
    ("artifacts/throughput.json", "search/latency/throughput.json"),
    ("artifacts/guided_latency.json", "search/latency/guided_latency.json"),
    ("artifacts/guidance_comparison.json", "models/guided/guidance_comparison.json"),
    ("artifacts/trajectory_integrity.json", "trajectories/integrity/trajectory_integrity.json"),
    ("artifacts/heldout_metrics.json", "training/evaluations/heldout_metrics.json"),
    ("artifacts/heldout_metrics_11k.json",
     "training/evaluations/heldout_metrics_11k_control.json"),
    ("artifacts/curriculum_audit.json", "training/evaluations/curriculum_audit.json"),
    ("artifacts/continuation_check.json", "training/resume_probes/continuation_check.json"),
    ("artifacts/evidence_validation.json", "artifacts/evidence_validation.json"),
    ("training/distillation_report.json", "models/distillation/distillation_report.json"),
    ("training/curriculum_report.json", "models/curriculum/curriculum_report.json"),
    ("training/m02_distilled_11k_report.json",
     "models/distillation/m02_distilled_11k_control_report.json"),
    ("training/m03_curriculum_40k_report.json",
     "models/curriculum/m03_curriculum_40k_fallback_report.json"),
]

EMPTY_NOTES = {
    "training/optimizer_states": (
        "# Optimizer states\n\nNot preserved. The PPO trainer creates its AdamW optimizer per "
        "run from `PPO_CFG` and does not checkpoint optimizer moments; P13's continuation check "
        "therefore verifies that a reloaded *model* checkpoint continues training and performs "
        "real updates, not that Adam moments round-trip. Recorded as a known limitation rather "
        "than left as an unexplained empty directory.\n"),
    "search/roots": (
        "# Search roots\n\nRoot observations are not stored separately: each root is identified "
        "inside the trajectory rows (`game_index`, `decision_index`, `context`, `n_options`) "
        "and the sampled full traces live in `search/traces/`. Storing every root observation "
        "for 42,857 searched decisions would add hundreds of MB of duplicated state for no "
        "audit value beyond what the traces already give.\n"),
}


def rel(p):
    return os.path.join(C18, p)


def link(src, dst):
    s, d = rel(src), rel(dst)
    if not os.path.exists(s) or os.path.abspath(s) == os.path.abspath(d):
        return None
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.exists(d):
        try:
            if os.path.samefile(s, d):
                return {"source": src, "dest": dst, "status": "already linked"}
        except OSError:
            pass
        os.remove(d)
    try:
        os.link(s, d)                 # same inode: provably identical bytes, no duplication
        return {"source": src, "dest": dst, "status": "hardlinked"}
    except OSError:
        shutil.copyfile(s, d)
        return {"source": src, "dest": dst, "status": "copied"}


def main():
    made = []
    for d in DIRS:
        os.makedirs(rel(d), exist_ok=True)
    for src, dst in LINKS:
        r = link(src, dst)
        if r:
            made.append(r)

    # glob-driven placements
    for p in glob.glob(rel("search/*_search_summary.json")):
        made.append(link(os.path.relpath(p, C18),
                         f"search/traces/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("trajectories/*_trajectories.jsonl.gz")):
        b = os.path.basename(p)
        sub = "trusted" if b.startswith(("scaled", "vertical")) else "diagnostic"
        made.append(link(os.path.relpath(p, C18), f"trajectories/{sub}/{b}") or {})
    for p in glob.glob(rel("trajectories/*_features.npz")):
        made.append(link(os.path.relpath(p, C18),
                         f"trajectories/trusted/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("rollouts/*_games.jsonl.gz")) + \
            glob.glob(rel("rollouts/*_updates.jsonl.gz")):
        made.append(link(os.path.relpath(p, C18),
                         f"training/raw_rollouts/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("checkpoints/m02_*")):
        made.append(link(os.path.relpath(p, C18),
                         f"models/distillation/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("checkpoints/m03_curriculum.*")) + \
            glob.glob(rel("checkpoints/m03_curriculum_40k.*")):
        made.append(link(os.path.relpath(p, C18),
                         f"models/curriculum/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("test_logs/*")):
        made.append(link(os.path.relpath(p, C18),
                         f"training/logs/{os.path.basename(p)}") or {})
    for p in glob.glob(rel("final_panel/*raw_games.jsonl.gz")):
        made.append(link(os.path.relpath(p, C18),
                         f"search/raw_games/{os.path.basename(p)}") or {})

    # trajectory schema, written from the generator's own constants
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c018_trajectories as TR
    schema = {
        "schema_version": TR.SCHEMA_VERSION,
        "split_by": "whole games (§17)",
        "fields": {
            "schema_version": "trajectory schema id",
            "search_version": "c018_search module version",
            "leaf_version": "heuristic leaf evaluator version",
            "game_index": "trajectory/game id", "decision_index": "decision id within the game",
            "opponent_id": "opponent identity", "seat": "seat (0/1)",
            "context": "engine SelectContext", "n_options": "size of the legal option set",
            "min_count": "select minCount", "max_count": "select maxCount",
            "legal_mask": "per-option legality mask, same length as n_options",
            "baseline_action": "the official baseline agent's action",
            "label_action": "the search-selected action",
            "candidate_scores": "per-candidate leaf values, depth and baseline flag",
            "determinization_archetype": "inferred opponent archetype used to predict hidden "
                                         "cards",
            "searched": "whether a real search ran for this decision",
            "trusted": "searched AND at least one real successor observed",
            "depth_max": "deepest real search_step chain reached",
            "distinct_successors": "distinct successor observations seen",
            "search_ms": "wall-clock for this decision's search",
            "reason": "fallback reason when not searched",
            "final_outcome": "terminal result of this game for this seat (1/0.5/0)",
            "game_completed": "whether the game reached a terminal state",
            "split": "train | validation | test, assigned by whole game",
        },
        "feature_file": "companion NPZ with encoder tensors and a trusted_rows index",
        "k_max": TR.KMAX,
        "note": ("aggregated action values across determinizations and a normalized policy "
                 "target with registered temperature are NOT produced: this planner runs one "
                 "determinization per root, so there is nothing to aggregate across and the "
                 "label is the search's argmax rather than a softened distribution. Recorded "
                 "as a deviation from §17 rather than emitted as a degenerate field."),
    }
    json.dump(schema, open(rel("trajectories/schema.json"), "w"), indent=2, default=str)

    for p in glob.glob(rel("search/*_search_summary.json")):
        d = json.load(open(p))
        b = os.path.basename(p)[:-len("_search_summary.json")]
        json.dump({"prefix": b, "games": d.get("games"),
                   "decisions": d.get("decisions"),
                   "trusted_decisions": d.get("trusted_decisions"),
                   "trajectory_file": d.get("trajectory_file"),
                   "trajectory_sha256": d.get("trajectory_sha256"),
                   "feature_file": d.get("feature_file"),
                   "config": d.get("config"),
                   "uses_c017_labels": d.get("uses_c017_labels")},
                  open(rel(f"trajectories/manifests/{b}_manifest.json"), "w"), indent=2,
                  default=str)
        det = (d.get("sample_traces") or [])[:40]
        json.dump({"prefix": b, "determinizations": [t.get("determinization") for t in det]},
                  open(rel(f"search/determinizations/{b}_determinizations.json"), "w"),
                  indent=2, default=str)
        json.dump({"prefix": b, "samples": det[:12]},
                  open(rel(f"trajectories/representative_samples/{b}_samples.json"), "w"),
                  indent=2, default=str)

    # configs, resolved from the code that actually ran
    import c018_search as S
    import c018_curriculum as CU
    json.dump({"search": dict(S.DEFAULT_CFG), "search_version": S.SEARCH_VERSION,
               "leaf_version": S.LEAF_VERSION},
              open(rel("configs/search_config.json"), "w"), indent=2, default=str)
    json.dump(CU.PPO_CFG, open(rel("configs/ppo_config.json"), "w"), indent=2, default=str)
    json.dump(CU.PPO_CFG, open(rel("training/configs/ppo_config.json"), "w"), indent=2,
              default=str)
    json.dump({"search": dict(S.DEFAULT_CFG)},
              open(rel("training/configs/search_config.json"), "w"), indent=2, default=str)

    # curriculum + mix history as JSONL, from the report's own per-block record
    cr = rel("training/curriculum_report.json")
    if os.path.exists(cr):
        c = json.load(open(cr))
        with open(rel("training/curriculum_history.jsonl"), "w") as fh:
            for h in c.get("history") or []:
                fh.write(json.dumps(h, default=str) + "\n")
        with open(rel("training/opponent_mix_history.jsonl"), "w") as fh:
            for h in c.get("history") or []:
                fh.write(json.dumps({"block": h["block"],
                                     "planned_fractions": h.get("planned_fractions"),
                                     "actual_fractions": h.get("actual_fractions"),
                                     "planned_self_play": h.get("planned_self_play")},
                                    default=str) + "\n")

    for p in glob.glob(rel("checkpoints/m03_curriculum_b*_current.npz")):
        made.append(link(os.path.relpath(p, C18),
                         f"training/checkpoints/{os.path.basename(p)}") or {})

    # git evidence
    import subprocess
    for name, args in (("log.txt", ["log", "--oneline", "d8a34b1..HEAD"]),
                       ("status.txt", ["status", "--porcelain"]),
                       ("head.txt", ["rev-parse", "HEAD"]),
                       ("branch.txt", ["rev-parse", "--abbrev-ref", "HEAD"])):
        out = subprocess.run(["git", *args], cwd=_REPO, capture_output=True,
                             text=True).stdout
        open(rel(f"git/{name}"), "w").write(out)

    for d, note in EMPTY_NOTES.items():
        if not [f for f in os.listdir(rel(d)) if f != "README.md"]:
            open(rel(os.path.join(d, "README.md")), "w").write(note)

    n = sum(1 for m in made if m and m.get("status") in ("hardlinked", "copied",
                                                         "already linked"))
    json.dump({"section": "§35", "directories_created": len(DIRS), "placements": n,
               "method": ("hard links, so a file's contract-specified path and its working "
                          "path are the same inode -- provably identical bytes, no "
                          "duplication of hundreds of MB of checkpoints"),
               "empty_directories_with_stated_reason": sorted(EMPTY_NOTES),
               "records": [m for m in made if m]},
              open(rel("artifacts/layout_conformance.json"), "w"), indent=2, default=str)
    print(json.dumps({"directories": len(DIRS), "placements": n,
                      "documented_empty": sorted(EMPTY_NOTES)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

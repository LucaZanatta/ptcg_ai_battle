"""c018 — assemble the results tree required by RESULTS_SCHEMA.md.

Source bundles, uncompressed inspection copies, milestone manifests M00..M05, hashes,
environment/dependency records, git patch, budget execution, and the final STATUS.

Everything is derived from what is actually on disk at build time. Where a required artifact is
missing the manifest records it as missing rather than omitting the row -- an absent line reads
as "not applicable", which is exactly how a skipped criterion gets counted as a pass.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

CDIR = os.path.join(_REPO, "contracts",
                    "c018_complete_integrated_search_learning_curriculum_campaign")
C18 = os.path.join(CDIR, "results")
SRC = os.path.join(C18, "source")
INSP = os.path.join(SRC, "inspection")
MILE = os.path.join(SRC, "milestones")

C018_TOOLS = ["c018_search.py", "c018_trajectories.py", "c018_distill.py",
              "c018_curriculum.py", "c018_guided.py", "c018_panel.py", "c018_package.py",
              "c018_validate.py", "c018_probes.py", "c018_probes_train.py",
              "c018_diagnostics.py", "c018_vertical.py", "c018_export_check.py",
              "c018_tree.py", "c018_submit.py", "c018_fixtures.py", "c018_metrics.py",
              "c018_curriculum_audit.py", "c018_stages.py", "c018_baseline_anchor.py",
              "c018_reports.py", "c018_repair_pass.py"]
C018_TESTS = ["tests/test_c018.py"]
SUPPORT = [("tools/c011_torch_model.py", "policy/value model (CUDA port)"),
           ("tools/c011_torch_ppo.py", "PPO trainer"),
           ("cg/rl_env.py", "PPO rollout (real simulator games)"),
           ("cg/rl_policy.py", "runtime numpy policy"),
           ("cg/state_encoder_v2.py", "featurizer"),
           ("cg/api.py", "official search API")]

ROLE = {
    "c018_search.py": "official search API adapter + context manager; determinization and "
                      "archetype classifier; candidate generator; beam planner; heuristic leaf "
                      "evaluator",
    "c018_trajectories.py": "trajectory schema, writer and feature export",
    "c018_distill.py": "supervised trainer (M02)",
    "c018_curriculum.py": "PPO curriculum scheduler (M03)",
    "c018_guided.py": "guided-search integration (M04)",
    "c018_panel.py": "identity-safe evaluator (P17)",
    "c018_package.py": "package builder and submission entrypoint",
    "c018_validate.py": "evidence validator (P90)",
    "c018_probes.py": "probes P02-P08",
    "c018_probes_train.py": "probes P09-P17, P30",
    "c018_diagnostics.py": "guidance/latency/continuation diagnostics (P13/P15/P16)",
    "c018_vertical.py": "thin end-to-end vertical (P30)",
    "c018_export_check.py": "torch->numpy export round-trip gate",
    "c018_tree.py": "results tree assembler",
    "c018_submit.py": "Kaggle upload and acceptance polling",
    "c018_fixtures.py": "tactical fixtures, per-decision branch proof, lifecycle, throughput "
                        "(P01/P02/P05/P06)",
    "c018_metrics.py": "held-out metric depth and trajectory integrity (P07/P08/P10)",
    "c018_curriculum_audit.py": "§26/§27 curriculum compliance audit",
    "c018_stages.py": "§29 stage registry with explicit non-production records",
    "c018_baseline_anchor.py": "AC-01 baseline package and accepted-reference verification",
    "c018_reports.py": "STATUS, README, SUMMARY and the §39 decision board",
    "c018_repair_pass.py": "§7 Pass B defect ranking and consolidated rerun record",
}


def primary_prefix(default="scaled"):
    """The trajectory set with the most TRUSTED decisions.

    Several prefixes coexist (smoke, vertical, budgetcheck, scaled, scaled2). Hardcoding one
    means a rerun at larger scale silently keeps reporting the smaller set, so the primary set
    is resolved from the evidence rather than named in code.
    """
    best, best_n = default, -1
    for p in glob.glob(os.path.join(C18, "search", "*_search_summary.json")):
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue
        n = d.get("trusted_decisions") or 0
        if n > best_n:
            best, best_n = os.path.basename(p)[:-len("_search_summary.json")], n
    return best


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True,
                          text=True).stdout.strip()


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else d


def entry(path, note=None):
    ap = path if os.path.isabs(path) else os.path.join(_REPO, path)
    if not os.path.exists(ap):
        return {"path": path, "present": False, "sha256": None, "bytes": None, "note": note}
    return {"path": os.path.relpath(ap, _REPO), "present": True, "sha256": sha_file(ap),
            "bytes": os.path.getsize(ap), "note": note}


# ------------------------------------------------------------------ bundles

def build_bundles():
    os.makedirs(SRC, exist_ok=True)
    skip_dirs = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}
    full = os.path.join(SRC, "complete_repository_source.zip")
    n_full = 0
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(_REPO):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            # results trees are evidence, not source, and would balloon the bundle
            if os.sep + "results" + os.sep in root + os.sep and "contracts" in root:
                continue
            for f in files:
                p = os.path.join(root, f)
                if os.path.getsize(p) > 40 << 20 or f.endswith((".so", ".pt", ".npz")):
                    continue
                z.write(p, os.path.relpath(p, _REPO))
                n_full += 1

    comp = os.path.join(SRC, "c018_competition_source_bundle.zip")
    n_comp = 0
    with zipfile.ZipFile(comp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for t in C018_TOOLS:
            p = os.path.join(_REPO, "tools", t)
            if os.path.exists(p):
                z.write(p, f"tools/{t}")
                n_comp += 1
        for rel, _ in SUPPORT:
            p = os.path.join(_REPO, rel)
            if os.path.exists(p):
                z.write(p, rel)
                n_comp += 1
        for rel in C018_TESTS:
            p = os.path.join(_REPO, rel)
            if os.path.exists(p):
                z.write(p, rel)
                n_comp += 1
        for f in ("CONTRACT.md", "PROBE_MATRIX.md", "RESULTS_SCHEMA.md",
                  "DECISION_RULES.md"):
            p = os.path.join(CDIR, f)
            if os.path.exists(p):
                z.write(p, f)
                n_comp += 1
        for p in glob.glob(os.path.join(C18, "packages", "*_manifest.json")):
            z.write(p, f"packages/{os.path.basename(p)}")
            n_comp += 1
    return {"complete_repository_source.zip": {**entry(full), "files": n_full},
            "c018_competition_source_bundle.zip": {**entry(comp), "files": n_comp}}


def build_inspection():
    os.makedirs(INSP, exist_ok=True)
    rows = []
    for t in C018_TOOLS:
        p = os.path.join(_REPO, "tools", t)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(INSP, t))
            rows.append({**entry(p), "role": ROLE.get(t)})
    for rel, role in SUPPORT:
        p = os.path.join(_REPO, rel)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(INSP, os.path.basename(rel)))
            rows.append({**entry(p), "role": role})
    # RESULTS_SCHEMA requires all c018-specific tests in inspection/
    for rel in C018_TESTS:
        p = os.path.join(_REPO, rel)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(INSP, os.path.basename(rel)))
            rows.append({**entry(p), "role": "c018 unit tests"})
    return rows


# ------------------------------------------------------------------ milestones

def milestone(mid, title, sources, configs, checkpoints, artifacts, command, extra=None):
    d = os.path.join(MILE, mid)
    os.makedirs(d, exist_ok=True)
    for s in sources:
        p = os.path.join(_REPO, s)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(d, os.path.basename(p)))
    deck = os.path.join(_REPO, "cg", "deck.csv")
    man = {"milestone": mid, "title": title,
           "git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}"),
           "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "sources": [entry(s) for s in sources],
           "configs": configs,
           "config_hash": hashlib.sha256(
               json.dumps(configs, sort_keys=True, default=str).encode()).hexdigest()[:32],
           "deck": entry("cg/deck.csv") if os.path.exists(deck) else None,
           "checkpoints": [entry(c) for c in checkpoints],
           "result_artifacts": [entry(x) for x in artifacts],
           "command": command}
    if extra:
        man.update(extra)
    json.dump(man, open(os.path.join(d, "manifest.json"), "w"), indent=2, default=str)
    return man


def build_milestones():
    import c018_search as S  # noqa: E402
    out = {}
    PFX = primary_prefix()
    ss = jload(f"search/{PFX}_search_summary.json") or {}
    dr = jload("training/distillation_report.json") or {}
    cr = jload("training/curriculum_report.json") or {}
    pk = sorted(glob.glob(os.path.join(C18, "packages", "*_manifest.json")))
    sub = jload("submissions/post_baseline_submission.json") or {}

    out["M00_parent"] = milestone(
        "M00_parent", "resolved c017 parent and immutable baseline",
        ["tools/c018_search.py"], {},
        [], [os.path.relpath(os.path.join(C18, "artifacts", "parent_resolution.json"), _REPO),
             os.path.relpath(os.path.join(C18, "artifacts",
                                          "immutability_baseline_pre_c018.json"), _REPO)],
        "git log / tools/c018_validate.py",
        {"parent_resolution": jload("artifacts/parent_resolution.json")})

    out["M01_real_search"] = milestone(
        "M01_real_search", "first trusted official-API multi-step planner",
        ["tools/c018_search.py", "tools/c018_trajectories.py"], S.DEFAULT_CFG, [],
        [os.path.relpath(os.path.join(C18, "search", f"{PFX}_search_summary.json"), _REPO),
         os.path.relpath(os.path.join(C18, "trajectories",
                                      f"{PFX}_trajectories.jsonl.gz"), _REPO),
         os.path.relpath(os.path.join(C18, "trajectories", f"{PFX}_features.npz"), _REPO)],
        f"python tools/c018_trajectories.py --games {ss.get('games')} --prefix {PFX}",
        {"real_search_counters": ss.get("real_search_counters"),
         "trusted_decisions": ss.get("trusted_decisions"),
         "trajectory_sha256": ss.get("trajectory_sha256")})

    out["M02_distilled"] = milestone(
        "M02_distilled", "best trusted search-distilled model",
        ["tools/c018_distill.py", "tools/c011_torch_model.py"],
        {"epochs": dr.get("epochs"), "batch_size": dr.get("batch_size"), "lr": dr.get("lr")},
        [os.path.join("contracts", os.path.relpath(
            os.path.join(C18, "checkpoints", "m02_distilled.pt"),
            os.path.join(_REPO, "contracts")))],
        [os.path.relpath(os.path.join(C18, "training", "distillation_report.json"), _REPO)],
        "python tools/c018_distill.py --prefix scaled --epochs 60 --tag m02_distilled",
        {"optimizer_steps": dr.get("optimizer_steps"),
         "checkpoint_sha256_before": dr.get("checkpoint_sha256_before"),
         "checkpoint_sha256_after": dr.get("checkpoint_sha256_after"),
         "held_out_test": dr.get("held_out_test"),
         "export_round_trip": jload("artifacts/export_round_trip.json")})

    out["M03_curriculum"] = milestone(
        "M03_curriculum", "best actual PPO curriculum checkpoint",
        ["tools/c018_curriculum.py", "tools/c011_torch_ppo.py", "cg/rl_env.py"],
        cr.get("ppo_cfg") or {},
        [os.path.relpath(os.path.join(C18, "checkpoints", "m03_curriculum.pt"), _REPO),
         os.path.relpath(os.path.join(C18, "checkpoints", "m03_curriculum.npz"), _REPO)],
        [os.path.relpath(os.path.join(C18, "training", "curriculum_report.json"), _REPO),
         os.path.relpath(os.path.join(C18, "rollouts",
                                      "m03_curriculum_games.jsonl.gz"), _REPO),
         os.path.relpath(os.path.join(C18, "rollouts",
                                      "m03_curriculum_updates.jsonl.gz"), _REPO)],
        "python tools/c018_curriculum.py --blocks 40 --games-per-block 1024 --nproc 10",
        {"actual_simulator_games": cr.get("actual_simulator_games"),
         "optimizer_steps": cr.get("optimizer_steps"),
         "distinct_checkpoint_hashes": cr.get("distinct_checkpoint_hashes"),
         "self_play_schedule": cr.get("self_play_schedule")})

    out["M04_guided_search"] = milestone(
        "M04_guided_search", "best trusted guided-search candidate",
        ["tools/c018_guided.py", "tools/c018_search.py"], S.DEFAULT_CFG,
        [os.path.relpath(os.path.join(C18, "checkpoints", "m03_curriculum.npz"), _REPO)],
        [os.path.relpath(os.path.join(C18, "artifacts", "guided_latency.json"), _REPO),
         os.path.relpath(os.path.join(C18, "artifacts", "guidance_comparison.json"), _REPO)],
        "python tools/c018_diagnostics.py",
        {"guided_latency": jload("artifacts/guided_latency.json"),
         "guidance_comparison": {k: v for k, v in
                                 (jload("artifacts/guidance_comparison.json") or {}).items()
                                 if k != "sample"}})

    out["M05_submitted"] = milestone(
        "M05_submitted", "exact source/config/checkpoint/package uploaded",
        ["tools/c018_package.py", "tools/c018_submit.py"], {},
        [], [os.path.relpath(p, _REPO) for p in pk]
        + [os.path.relpath(os.path.join(C18, "final_panel",
                                        "final_panel_results.json"), _REPO)],
        "python tools/c018_package.py && python tools/c018_submit.py",
        {"packages": [jload(p) and {k: jload(p)[k] for k in ("name", "sha256", "bytes")}
                      for p in pk],
         "submission": sub})
    return out


# ------------------------------------------------------------------ top level

def build_budget():
    PFX = primary_prefix()
    ss = jload(f"search/{PFX}_search_summary.json") or {}
    c = ss.get("real_search_counters") or {}
    dr = jload("training/distillation_report.json") or {}
    cr = jload("training/curriculum_report.json") or {}
    pm = jload("final_panel/panel_meta.json") or {}
    sub = jload("submissions/post_baseline_submission.json") or {}
    floors = [
        ("real search_begin roots >= 200", c.get("begin_ok") or 0, 200),
        ("real search_step calls >= 5000", c.get("step_ok") or 0, 5000),
        ("trusted search-labelled decisions >= 10000", ss.get("trusted_decisions") or 0, 10000),
        ("actual PPO curriculum games >= 20000", cr.get("actual_simulator_games") or 0, 20000),
        ("optimizer steps total >= 1000",
         (dr.get("optimizer_steps") or 0) + (cr.get("optimizer_steps") or 0), 1000),
        ("final-panel games >= 600", pm.get("scored_games") or 0, 600),
        ("accepted post-baseline submissions >= 1",
         1 if sub.get("submission_ref") else 0, 1),
    ]
    rows = [{"floor": n, "actual": a, "required": r, "met": a >= r} for n, a, r in floors]
    doc = {"floors": rows, "all_floors_met": all(r["met"] for r in rows),
           "missed": [r["floor"] for r in rows if not r["met"]],
           "targets": [
               {"target": "trusted search-labelled decisions 30,000-60,000",
                "actual": ss.get("trusted_decisions"),
                "in_band": 30000 <= (ss.get("trusted_decisions") or 0) <= 60000,
                "note": ("floor of 10,000 met; the band was not reached because scaling to "
                         "30,000 would have cost more than the remaining floors were worth "
                         "and forced M02 and M03 to be re-run on top")},
               {"target": "actual curriculum games 40,000-100,000",
                "actual": cr.get("actual_simulator_games"),
                "in_band": 40000 <= (cr.get("actual_simulator_games") or 0) <= 100000},
               {"target": "final-panel games 1,200-2,000",
                "actual": pm.get("scored_games"),
                "in_band": 1200 <= (pm.get("scored_games") or 0) <= 2000,
                "note": ("six §29 stages x 4 opponents x 100 games per pair exceeds the band; "
                         "recorded as exceeded rather than presented as inside it")}],
           "uploads_used": len(glob.glob(os.path.join(C18, "submissions", "*_upload.json"))),
           "uploads_allowed": 2}
    json.dump(doc, open(os.path.join(C18, "BUDGET_EXECUTION.json"), "w"), indent=2, default=str)
    return doc


def build_env():
    os.makedirs(SRC, exist_ok=True)
    import platform
    try:
        import torch
        cuda = {"torch": torch.__version__, "cuda_available": torch.cuda.is_available(),
                "cuda_version": torch.version.cuda,
                "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    except Exception as e:  # noqa: BLE001
        cuda = {"error": repr(e)}
    open(os.path.join(SRC, "environment.txt"), "w").write(
        f"python: {sys.version}\nplatform: {platform.platform()}\n"
        f"machine: {platform.machine()}\ncpu_count: {os.cpu_count()}\n"
        f"torch: {json.dumps(cuda, default=str)}\n"
        f"git_commit: {git('rev-parse', 'HEAD')}\n"
        f"git_branch: {git('rev-parse', '--abbrev-ref', 'HEAD')}\n")
    pip = subprocess.run([os.path.join(_REPO, ".venv", "bin", "pip"), "freeze"],
                         capture_output=True, text=True)
    open(os.path.join(SRC, "dependency_lock.txt"), "w").write(pip.stdout or pip.stderr)
    # the parent is resolved ONCE, in M00, and read back here -- two independent copies of the
    # same fact drift, and this one decides what the audit patch actually contains
    pr = jload("artifacts/parent_resolution.json", {}) or {}
    parent = pr.get("resolved_parent_commit") or "d8a34b1"
    open(os.path.join(SRC, "git_diff.patch"), "w").write(git("diff", parent, "HEAD") or "")
    return {**cuda, "parent_commit_used_for_patch": parent}


def build_hashes():
    lines = []
    for root, dirs, files in os.walk(C18):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            p = os.path.join(root, f)
            if os.path.getsize(p) > 512 << 20:
                continue
            lines.append(f"{sha_file(p)}  {os.path.relpath(p, C18)}")
    open(os.path.join(SRC, "hashes.sha256"), "w").write("\n".join(sorted(lines)) + "\n")
    return len(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bundles", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(SRC, exist_ok=True)
    print("[c018 tree] inspection")
    insp = build_inspection()
    print("[c018 tree] milestones")
    miles = build_milestones()
    print("[c018 tree] environment")
    env = build_env()
    print("[c018 tree] budget")
    budget = build_budget()
    bundles = {}
    if not a.skip_bundles:
        print("[c018 tree] bundles")
        bundles = build_bundles()
    print("[c018 tree] hashes")
    nh = build_hashes()

    man = {"contract": "c018", "git_commit": git("rev-parse", "HEAD"),
           "git_tree": git("rev-parse", "HEAD^{tree}"),
           "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "parent_commit": (jload("artifacts/parent_resolution.json", {}) or {}).get(
               "resolved_parent_commit", "d8a34b1"),
           "bundles": bundles, "inspection_files": insp,
           "milestones": {k: {"manifest": os.path.relpath(
               os.path.join(MILE, k, "manifest.json"), _REPO),
               "title": v["title"], "config_hash": v["config_hash"]}
               for k, v in miles.items()},
           "hashed_files": nh,
           "environment": env, "budget": budget}
    json.dump(man, open(os.path.join(SRC, "source_manifest.json"), "w"), indent=2, default=str)
    print(json.dumps({"bundles": {k: v.get("bytes") for k, v in bundles.items()},
                      "inspection_files": len(insp), "milestones": list(miles),
                      "hashed_files": nh,
                      "floors_met": budget["all_floors_met"],
                      "missed": budget["missed"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

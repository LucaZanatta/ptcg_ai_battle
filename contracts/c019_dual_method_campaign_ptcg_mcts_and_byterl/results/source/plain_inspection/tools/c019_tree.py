"""c019 — assemble the mandatory results/source tree (RESULTS_SCHEMA.md).

The stated purpose is a line-by-line implementation audit, so this favours plain readable copies
and complete manifests over compression. Directories that stay empty carry a README explaining
why: empty and unexplained reads as an oversight, and this contract's evidence has to survive
someone actively looking for gaps.
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
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

CDIR = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl")
C19 = os.path.join(CDIR, "results")
SRC = os.path.join(C19, "source")

C019_CG = ["c019_core.py", "c019_baseline.py", "c019_determinize.py", "c019_leaf.py",
           "c019_mcts.py", "c019_ismcts.py", "c019_byterl_encode.py", "c019_byterl_model.py",
           "c019_byterl_actor.py", "c019_vtrace.py", "c019_osfp.py", "c019_hybrid.py"]
C019_TOOLS = ["c019_sources.py", "c019_calibrate.py", "c019_probe_chance.py",
              "c019_probe_m01.py", "c019_mcts_run.py", "c019_byterl_train.py",
              "c019_panel.py", "c019_package.py", "c019_validate.py", "c019_tree.py",
              "c019_reports.py", "c019_submit.py", "c019_probes.py"]
C019_TESTS = ["test_c019_fixtures.py"]

ROLE = {
    "c019_core.py": "canonical option/observation interface, hidden-information guard",
    "c019_baseline.py": "branch-local baseline policy memory (§8.1)",
    "c019_determinize.py": "legal information-set determinization sampler (§8.2)",
    "c019_leaf.py": "PTCG heuristic leaf evaluator (§8.4)",
    "c019_mcts.py": "node/tree/PUCT/expansion/rollout/backup (§8.3)",
    "c019_ismcts.py": "multi-determinization agent and root aggregation (§8.2, M09)",
    "c019_byterl_encode.py": "visible token encoder (§9.2)",
    "c019_byterl_model.py": "recurrent masked policy/value, LSTM-256 (§9.2)",
    "c019_byterl_actor.py": "CPU actor and unroll schema (§9.3)",
    "c019_vtrace.py": "V-trace targets, UPGO, PPO-clipped objective (§9.3)",
    "c019_osfp.py": "OSFP Algorithm 1: H, payoff sampling, promotion (§9.4)",
    "c019_hybrid.py": "switchable priors/value/visit-target adapters (§10)",
    "c019_byterl_train.py": "actor-learner training loop (§9.3)",
    "c019_mcts_run.py": "scaled MCTS evaluation and evidence capture (§8.6)",
    "c019_panel.py": "frozen identity-safe common panel (§11)",
    "c019_package.py": "standalone package builders and clean-extraction validation (§13)",
    "c019_validate.py": "method-fidelity and evidence validator (F03)",
    "c019_submit.py": "gated Kaggle submission",
    "c019_probes.py": "probe directory writer",
}

EMPTY_NOTES = {
    "hybrid/packages": ("# Hybrid packages\n\nNone built. §10 caps hybrid work at 15% of the "
                        "campaign and states c019 does not require hybrid training or "
                        "submission; the adapters exist and are switchable, and no hybrid "
                        "candidate cleared a promotion gate.\n"),
    "mcts/trees": ("# Full tree dumps\n\nCompact node summaries and per-decision tree shapes are "
                   "in `sampled_full_traces/`. Serialising every node of every tree for 7,549 "
                   "searched decisions would add gigabytes duplicating what the shapes already "
                   "prove (depth, branching, visits, values).\n"),
}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True, text=True).stdout.strip()


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C19, p)
    return json.load(open(p)) if os.path.exists(p) else d


def entry(rel, note=None):
    ap = rel if os.path.isabs(rel) else os.path.join(_REPO, rel)
    if not os.path.exists(ap):
        return {"path": rel, "present": False, "note": note}
    return {"path": os.path.relpath(ap, _REPO), "present": True, "sha256": sha_file(ap),
            "bytes": os.path.getsize(ap), "note": note}


def build_inspection():
    rows = []
    for sub, files, base in (("cg", C019_CG, os.path.join(_REPO, "cg")),
                             ("tools", C019_TOOLS, os.path.join(_REPO, "tools")),
                             ("tests", C019_TESTS, os.path.join(_REPO, "tests"))):
        d = os.path.join(SRC, "plain_inspection", sub)
        os.makedirs(d, exist_ok=True)
        for f in files:
            p = os.path.join(base, f)
            if os.path.exists(p):
                shutil.copyfile(p, os.path.join(d, f))
                rows.append({**entry(os.path.relpath(p, _REPO)), "role": ROLE.get(f)})
    d = os.path.join(SRC, "plain_inspection", "packages_entrypoints")
    os.makedirs(d, exist_ok=True)
    for man in glob.glob(os.path.join(C19, "packages", "*", "manifest.json")):
        name = os.path.basename(os.path.dirname(man))
        arch = os.path.join(os.path.dirname(man),
                            json.load(open(man)).get("archive", ""))
        if os.path.exists(arch):
            import tarfile
            with tarfile.open(arch) as tar:
                for m in tar.getmembers():
                    if m.name == "main.py":
                        f = tar.extractfile(m)
                        open(os.path.join(d, f"{name}_main.py"), "wb").write(f.read())
                        rows.append({"path": f"packages/{name}/main.py", "present": True,
                                     "role": "package entrypoint"})
    return rows


def build_bundles():
    os.makedirs(SRC, exist_ok=True)
    skip = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}
    full = os.path.join(SRC, "complete_repository_source.zip")
    n = 0
    with zipfile.ZipFile(full, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(_REPO):
            dirs[:] = [d for d in dirs if d not in skip]
            if os.sep + "results" + os.sep in root + os.sep and "contracts" in root:
                continue
            for f in files:
                p = os.path.join(root, f)
                try:
                    if os.path.getsize(p) > 40 << 20 or f.endswith((".so", ".pt", ".npz",
                                                                    ".zip", ".z01", ".z02",
                                                                    ".z03", ".gz")):
                        continue
                    z.write(p, os.path.relpath(p, _REPO))
                    n += 1
                except OSError:
                    continue
    comp = os.path.join(SRC, "c019_competition_source_bundle.zip")
    m = 0
    with zipfile.ZipFile(comp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in C019_CG:
            p = os.path.join(_REPO, "cg", f)
            if os.path.exists(p):
                z.write(p, f"cg/{f}")
                m += 1
        for f in C019_TOOLS:
            p = os.path.join(_REPO, "tools", f)
            if os.path.exists(p):
                z.write(p, f"tools/{f}")
                m += 1
        for f in C019_TESTS:
            p = os.path.join(_REPO, "tests", f)
            if os.path.exists(p):
                z.write(p, f"tests/{f}")
                m += 1
        for f in ("CONTRACT.md", "METHOD_FIDELITY.md", "DECISION_RULES.md", "PROBE_MATRIX.md",
                  "RESULTS_SCHEMA.md", "IMPLEMENTATION_GUIDE.md"):
            p = os.path.join(CDIR, f)
            if os.path.exists(p):
                z.write(p, f)
                m += 1
        for f in ("references/SOURCE_REFERENCES.md", "references/LICENSE_AND_REUSE_POLICY.md"):
            p = os.path.join(CDIR, f)
            if os.path.exists(p):
                z.write(p, f)
                m += 1
        deck = os.path.join(_REPO, "contracts",
                            "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                            "results", "artifacts", "candidates", "official_mega_lucario",
                            "deck.csv")
        if os.path.exists(deck):
            z.write(deck, "deck/deck.csv")
            m += 1
        for p in glob.glob(os.path.join(C19, "packages", "*", "manifest.json")):
            z.write(p, f"packages/{os.path.basename(os.path.dirname(p))}_manifest.json")
            m += 1
        for p in glob.glob(os.path.join(C19, "common", "*.json")) + \
                glob.glob(os.path.join(C19, "common", "*.txt")):
            z.write(p, f"common/{os.path.basename(p)}")
            m += 1
    return {"complete_repository_source.zip": {**entry(full), "files": n},
            "c019_competition_source_bundle.zip": {**entry(comp), "files": m}}


def milestone(mid, title, sources, configs, artifacts, command, extra=None):
    d = os.path.join(SRC, "milestones", mid)
    os.makedirs(d, exist_ok=True)
    for s in sources:
        p = os.path.join(_REPO, s)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(d, os.path.basename(p)))
    man = {"milestone": mid, "title": title,
           "git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}"),
           "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "sources": [entry(s) for s in sources], "configs": configs,
           "config_hash": hashlib.sha256(
               json.dumps(configs, sort_keys=True, default=str).encode()).hexdigest()[:32],
           "result_artifacts": [entry(x) for x in artifacts], "command": command}
    if extra:
        man.update(extra)
    json.dump(man, open(os.path.join(d, "manifest.json"), "w"), indent=2, default=str)
    return man


def build_milestones():
    from cg import c019_mcts as M
    import importlib
    tr = importlib.import_module("c019_byterl_train") if os.path.exists(
        os.path.join(_REPO, "tools", "c019_byterl_train.py")) else None
    mcts_sum = jload("mcts/aggregate_stats/scaled_summary.json", {})
    by_sum = (jload("byterl/learner_logs/scaled_training_summary.json")
              or jload("byterl/learner_logs/training_summary.json", {}))
    out = {}
    out["M00_parent"] = milestone(
        "M00_parent", "resolved c018 parent and immutable start",
        [], {}, ["contracts/c019_dual_method_campaign_ptcg_mcts_and_byterl/results/git/"
                 "parent_resolution.md"],
        "git rev-parse / see results/git/parent_resolution.md",
        {"expected_parent": "4cbae35888b21cbfccb6ebf4f5f5bfc5e05bd757",
         "selected_parent": git("rev-list", "--max-parents=100", "-n", "1", "HEAD") or None,
         "initial_head": open(os.path.join(C19, "git", "initial_head.txt")).read().strip()
         if os.path.exists(os.path.join(C19, "git", "initial_head.txt")) else None})
    out["M01_shared_interface"] = milestone(
        "M01_shared_interface", "canonical option/observation interface and deck freeze",
        ["cg/c019_core.py", "cg/c019_baseline.py"], {},
        ["contracts/c019_dual_method_campaign_ptcg_mcts_and_byterl/results/common/"
         "deck_freeze.json"],
        "python tools/c019_probe_m01.py",
        {"m01_parity": jload("probes/M01_baseline_memory_parity/probe.json", {}).get("status")})
    out["M02_mcts_faithful"] = milestone(
        "M02_mcts_faithful", "method-faithful PTCG-ISMCTS",
        ["cg/c019_mcts.py", "cg/c019_ismcts.py", "cg/c019_determinize.py", "cg/c019_leaf.py"],
        dict(M.DEFAULT_CFG),
        ["contracts/c019_dual_method_campaign_ptcg_mcts_and_byterl/results/mcts/"
         "aggregate_stats/scaled_summary.json"],
        "python tools/c019_mcts_run.py --games 160 --sims 48 --determinizations 3",
        {"floors": mcts_sum.get("floors"), "fidelity": mcts_sum.get("fidelity_evidence")})
    out["M03_byterl_actor_learner"] = milestone(
        "M03_byterl_actor_learner", "ByteRL recurrent actor-learner",
        ["cg/c019_byterl_model.py", "cg/c019_byterl_encode.py", "cg/c019_byterl_actor.py",
         "cg/c019_vtrace.py"],
        (tr.HP if tr else {}),
        ["contracts/c019_dual_method_campaign_ptcg_mcts_and_byterl/results/byterl/"
         "learner_logs/scaled_training_summary.json"],
        "python tools/c019_byterl_train.py --learning-periods 8 --games-per-lp 20000",
        {"actual_games": (by_sum or {}).get("actual_games"),
         "optimizer_steps": (by_sum or {}).get("optimizer_steps")})
    out["M04_byterl_osfp"] = milestone(
        "M04_byterl_osfp", "OSFP historical pool and promotions",
        ["cg/c019_osfp.py"],
        {"p": 0.6, "xi": 0.55, "max_lp_without_add": 6},
        [], "see byterl/osfp/",
        {"historical_pool": (by_sum or {}).get("historical_pool"),
         "promotions": (by_sum or {}).get("promotions")})
    out["M05_hybrid_adapters"] = milestone(
        "M05_hybrid_adapters", "switchable hybrid adapters", ["cg/c019_hybrid.py"], {}, [],
        "adapters are constructor arguments defaulting to None",
        {"note": "§10 caps hybrid work; c019 does not require hybrid training or submission"})
    pkgs = sorted(glob.glob(os.path.join(C19, "packages", "*", "manifest.json")))
    out["M06_submitted_packages"] = milestone(
        "M06_submitted_packages", "packages and submission decisions",
        ["tools/c019_package.py", "tools/c019_submit.py"], {},
        [os.path.relpath(p, _REPO) for p in pkgs],
        "python tools/c019_package.py",
        {"packages": [{"name": json.load(open(p)).get("name"),
                       "sha256": json.load(open(p)).get("sha256"),
                       "clean_extraction_ok": (jload(
                           f"packages/{os.path.basename(os.path.dirname(p))}/"
                           "clean_validation.json", {}) or {}).get("clean_extraction_ok")}
                      for p in pkgs],
         "submission": jload("submissions/references.json")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bundles", action="store_true")
    a = ap.parse_args(argv)
    for d in ("method_fidelity", "common", "mcts/configs", "mcts/determinizations",
              "mcts/trees", "mcts/sampled_full_traces", "mcts/aggregate_stats", "mcts/parity",
              "mcts/latency", "mcts/raw_games", "mcts/evaluations", "mcts/packages",
              "mcts/submissions", "byterl/configs", "byterl/model_architecture",
              "byterl/actor_unrolls", "byterl/queue_stats", "byterl/learner_logs",
              "byterl/vtrace_upgo_fixtures", "byterl/osfp/payoff_tables",
              "byterl/osfp/historical_checkpoints", "byterl/checkpoints", "byterl/raw_games",
              "byterl/evaluations", "byterl/packages", "byterl/submissions",
              "hybrid/adapters", "hybrid/smoke_traces", "hybrid/comparisons", "hybrid/packages",
              "final_panel", "probes", "failures/exceptions", "failures/timeouts",
              "failures/invalid_determinizations", "failures/failed_unrolls",
              "packages/baseline", "submissions/responses", "source/plain_inspection",
              "source/milestones", "git"):
        os.makedirs(os.path.join(C19, d), exist_ok=True)

    insp = build_inspection()
    miles = build_milestones()

    # model architecture record (RESULTS_SCHEMA byterl/model_architecture)
    try:
        import torch
        from cg import c019_byterl_model as MM
        m = MM.PTCGByteRL()
        json.dump({"version": MM.MODEL_VERSION, "cfg": m.cfg,
                   "parameters": sum(p.numel() for p in m.parameters()),
                   "lstm_hidden": MM.LSTM_HIDDEN,
                   "modules": [f"{n}: {tuple(p.shape)}" for n, p in m.named_parameters()],
                   "repr": repr(m)[:8000]},
                  open(os.path.join(C19, "byterl", "model_architecture", "architecture.json"),
                       "w"), indent=2, default=str)
    except Exception:  # noqa: BLE001
        pass

    for rel, note in EMPTY_NOTES.items():
        d = os.path.join(C19, rel)
        os.makedirs(d, exist_ok=True)
        if not [f for f in os.listdir(d) if f != "README.md"]:
            open(os.path.join(d, "README.md"), "w").write(note)

    env = {}
    try:
        import platform
        import torch
        env = {"python": sys.version.split()[0], "platform": platform.platform(),
               "torch": torch.__version__, "cuda": torch.cuda.is_available(),
               "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    except Exception:  # noqa: BLE001
        pass
    open(os.path.join(SRC, "git_diff.patch"), "w").write(git("diff", "2197214", "HEAD") or "")
    for name, args in (("log.txt", ["log", "--oneline", "2197214..HEAD"]),
                       ("status.txt", ["status", "--porcelain"]),
                       ("final_head.txt", ["rev-parse", "HEAD"]),
                       ("branch.txt", ["rev-parse", "--abbrev-ref", "HEAD"])):
        open(os.path.join(C19, "git", name), "w").write(git(*args))

    bundles = {} if a.skip_bundles else build_bundles()

    lines = []
    for root, dirs, files in os.walk(C19):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > 512 << 20:
                    continue
                lines.append(f"{sha_file(p)}  {os.path.relpath(p, C19)}")
            except OSError:
                continue
    open(os.path.join(SRC, "hashes.sha256"), "w").write("\n".join(sorted(lines)) + "\n")

    man = {"contract": "c019", "git_commit": git("rev-parse", "HEAD"),
           "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "bundles": bundles, "inspection_files": insp,
           "milestones": {k: {"title": v["title"], "config_hash": v["config_hash"]}
                          for k, v in miles.items()},
           "hashed_files": len(lines), "environment": env}
    json.dump(man, open(os.path.join(SRC, "source_manifest.json"), "w"), indent=2, default=str)
    print(json.dumps({"inspection_files": len(insp), "milestones": list(miles),
                      "hashed_files": len(lines),
                      "bundles": {k: v.get("bytes") for k, v in bundles.items()}},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

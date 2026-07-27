"""c020 F06 / RESULTS_SCHEMA — complete source bundles, plain inspection copies, milestones.

`RESULTS_SCHEMA.md` is explicit that summaries without full code and raw evidence are
unacceptable, because the results will be audited line by line. This assembles the source half of
that: the whole repository tree, a focused c020 bundle sufficient to reproduce every corrected
block, plain (unzipped) inspection copies, milestone snapshots and hashes.
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
CDIR = os.path.join(_REPO, "contracts",
                    "c020_forced_method_correction_and_hybrid_integration_campaign")
C20 = os.path.join(CDIR, "results")
SRC = os.path.join(C20, "source")

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
             ".ipynb_checkpoints"}
SKIP_EXT = {".pyc", ".pyo", ".so.bak"}

MILESTONES = {
    "M00_parent": [],
    "M01_all_corrections_implemented": [
        "starter_kit/c020_infoset.py", "starter_kit/c020_baseline_memory.py",
        "starter_kit/c020_ismcts.py", "starter_kit/c020_tactical_leaf.py",
        "starter_kit/c020_override.py", "starter_kit/c020_determinize.py",
        "starter_kit/c020_cards.py", "starter_kit/c020_agent.py",
        "starter_kit/c020_byterl_encode.py", "starter_kit/c020_byterl_model.py",
        "starter_kit/c020_byterl_actor.py", "starter_kit/c020_vtrace.py",
        "starter_kit/c020_osfp.py", "starter_kit/c020_hybrid.py"],
    "M02_complete_smoke": ["tools/c020_mcts_run.py", "tools/c020_byterl_train.py",
                           "tools/c020_hybrid_run.py", "tools/c020_panel.py",
                           "tools/c020_package.py"],
    "M03_repair_pass": ["tools/c020_validate.py"],
    "M04_scaled_mcts": ["tools/c020_mcts_run.py"],
    "M05_scaled_byterl": ["tools/c020_byterl_train.py"],
    "M06_hybrid_H0_H4": ["tools/c020_hybrid_run.py", "tools/c020_admission.py"],
    "M07_submitted_packages": ["tools/c020_package.py", "tools/c020_submit.py"],
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def walk_repo():
    for root, dirs, files in os.walk(_REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXT:
                continue
            p = os.path.join(root, f)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            yield p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bundles", action="store_true")
    a = ap.parse_args(argv)

    for d in ("plain_inspection/cg", "plain_inspection/starter_kit", "plain_inspection/tools",
              "plain_inspection/tests", "plain_inspection/package_entrypoints", "milestones"):
        os.makedirs(os.path.join(SRC, d), exist_ok=True)

    # ---------------------------------------------------------------- plain inspection
    plain = {}
    for pattern, dest in (("starter_kit/c020_*.py", "starter_kit"),
                          ("starter_kit/c019_*.py", "cg"),
                          ("tools/c020_*.py", "tools"),
                          ("tools/c019_panel.py", "tools"),
                          ("tests/test_c020_*.py", "tests"),
                          ("tests/test_c019_*.py", "tests")):
        for p in sorted(glob.glob(os.path.join(_REPO, pattern))):
            dst = os.path.join(SRC, "plain_inspection", dest, os.path.basename(p))
            shutil.copyfile(p, dst)
            plain[os.path.relpath(dst, SRC)] = sha(dst)
    for p in sorted(glob.glob(os.path.join(C20, "packages", "*", "*", "main.py"))):
        name = os.path.basename(os.path.dirname(p))
        dst = os.path.join(SRC, "plain_inspection", "package_entrypoints", f"{name}_main.py")
        shutil.copyfile(p, dst)
        plain[os.path.relpath(dst, SRC)] = sha(dst)

    # ---------------------------------------------------------------- milestones
    ms = {}
    for name, files in MILESTONES.items():
        d = os.path.join(SRC, "milestones", name)
        os.makedirs(d, exist_ok=True)
        got = []
        for rel in files:
            p = os.path.join(_REPO, rel)
            if os.path.exists(p):
                dst = os.path.join(d, os.path.basename(rel))
                shutil.copyfile(p, dst)
                got.append({"file": rel, "sha256": sha(dst)})
        ms[name] = got
        if name == "M00_parent":
            open(os.path.join(d, "PARENT.txt"), "w").write(
                "a1d322e291e51b86aa308410b96a7b19748060f0\n"
                "contract/c019_dual_method_campaign_ptcg_mcts_and_byterl\n")

    # ---------------------------------------------------------------- git evidence
    os.makedirs(os.path.join(C20, "git"), exist_ok=True)
    for name, args in (("final_head.txt", ["rev-parse", "HEAD"]),
                       ("branch.txt", ["rev-parse", "--abbrev-ref", "HEAD"]),
                       ("status.txt", ["status", "--short"]),
                       ("log.txt", ["log", "--oneline", "-40"])):
        out = subprocess.run(["git", *args], cwd=_REPO, capture_output=True,
                             text=True).stdout
        open(os.path.join(C20, "git", name), "w").write(out)
    patch = subprocess.run(
        ["git", "diff", "a1d322e291e51b86aa308410b96a7b19748060f0", "HEAD", "--", ".",
         ":(exclude)*.gz", ":(exclude)*.pt", ":(exclude)*.zip"],
        cwd=_REPO, capture_output=True, text=True).stdout
    open(os.path.join(SRC, "git_diff.patch"), "w").write(patch)

    # ---------------------------------------------------------------- hashes
    hashes = {}
    n = 0
    with open(os.path.join(SRC, "hashes.sha256"), "w") as fh:
        for p in walk_repo():
            rel = os.path.relpath(p, _REPO)
            if rel.startswith("contracts/c020") and "/source/" in rel:
                continue
            try:
                h = sha(p)
            except OSError:
                continue
            fh.write(f"{h}  {rel}\n")
            n += 1
            if rel.startswith(("starter_kit/c020", "tools/c020", "tests/test_c020")):
                hashes[rel] = h

    bundles = {}
    if not a.skip_bundles:
        # complete repository source
        zp = os.path.join(SRC, "complete_repository_source.zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for p in walk_repo():
                rel = os.path.relpath(p, _REPO)
                if rel.startswith("contracts/c020") and "/source/" in rel:
                    continue
                if os.path.getsize(p) > 64 * 1024 * 1024:
                    continue
                z.write(p, rel)
        bundles["complete_repository_source.zip"] = os.path.getsize(zp)

        # focused c020 bundle: everything needed to reproduce the corrected blocks
        zp2 = os.path.join(SRC, "c020_competition_source_bundle.zip")
        with zipfile.ZipFile(zp2, "w", zipfile.ZIP_DEFLATED) as z:
            for pattern in ("starter_kit/c020_*.py", "starter_kit/c019_core.py",
                            "starter_kit/c019_baseline.py", "starter_kit/c019_determinize.py",
                            "starter_kit/c019_vtrace.py", "starter_kit/c019_ismcts.py",
                            "starter_kit/c019_mcts.py", "starter_kit/c019_leaf.py",
                            "starter_kit/c019_byterl_*.py", "starter_kit/c019_osfp.py",
                            "tools/c020_*.py", "tests/test_c020_*.py",
                            "cg/api.py", "cg/game.py", "cg/sim.py", "cg/utils.py",
                            "cg/__init__.py"):
                for p in glob.glob(os.path.join(_REPO, pattern)):
                    if os.path.isfile(p) and not os.path.islink(p):
                        z.write(p, os.path.relpath(p, _REPO))
            for rel in ("CONTRACT.md", "MANDATORY_CHANGES.md", "IMPLEMENTATION_GUIDE.md",
                        "DECISION_RULES.md", "PROBE_MATRIX.md", "RESULTS_SCHEMA.md",
                        "references/C019_AUDIT_FINDINGS.md"):
                p = os.path.join(CDIR, rel)
                if os.path.exists(p):
                    z.write(p, f"contract/{rel}")
            for rel in ("implementation/forced_change_map.md", "implementation/repair_pass.md",
                        "controls/control_manifest.json", "SUMMARY.md", "STATUS.json"):
                p = os.path.join(C20, rel)
                if os.path.exists(p):
                    z.write(p, f"results/{rel}")
            bd = os.path.join(
                _REPO, "contracts",
                "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                "results", "artifacts", "candidates", "official_mega_lucario")
            for root, _d, fs in os.walk(bd):
                for f in fs:
                    p = os.path.join(root, f)
                    z.write(p, f"deck_and_baseline/{os.path.relpath(p, bd)}")
        bundles["c020_competition_source_bundle.zip"] = os.path.getsize(zp2)
        for k in list(bundles):
            bundles[k] = {"bytes": bundles[k], "sha256": sha(os.path.join(SRC, k))}

    manifest = {
        "contract": "c020",
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                 capture_output=True, text=True).stdout.strip(),
        "hashed_files": n,
        "c020_source_hashes": hashes,
        "plain_inspection": plain,
        "milestones": {k: len(v) for k, v in ms.items()},
        "milestone_files": ms,
        "bundles": bundles,
        "patch_bytes": len(patch),
    }
    json.dump(manifest, open(os.path.join(SRC, "source_manifest.json"), "w"), indent=2)
    print(json.dumps({"hashed_files": n, "c020_modules": len(hashes),
                      "plain_inspection_files": len(plain),
                      "milestones": manifest["milestones"], "bundles": bundles,
                      "patch_bytes": len(patch)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

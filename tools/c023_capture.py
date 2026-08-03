"""c023 — capture exact source and Git evidence, and build the final results archive.

Everything a reviewer needs to reconstruct what actually ran: the commit, the working-tree state,
the diff, the log, a full source archive, a focused archive of only the files this contract
added or changed, the environment, and hashes for all of it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
SRC = os.path.join(OUT, "source")
GIT = os.path.join(OUT, "git")

# The files this contract authored. The focused archive holds exactly these.
C023_SOURCE = [
    "tools/c023_extract_kernels.py", "tools/c023_eval.py", "tools/c023_build_candidate.py",
    "tools/c023_identity.py", "tools/c023_deck_search.py", "tools/c023_matrix.py",
    "tools/c023_mine.py", "tools/c023_package.py", "tools/c023_history.py",
    "tools/c023_validate.py", "tools/c023_reports.py", "tools/c023_capture.py",
    "starter_kit/c023_players.py", "starter_kit/c023_wrapper_main.py",
    "starter_kit/c023_planner.py",
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git"] + list(args), cwd=_REPO,
                          capture_output=True, text=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", action="store_true", help="also build the results archive")
    a = ap.parse_args()

    os.makedirs(SRC, exist_ok=True)
    os.makedirs(GIT, exist_ok=True)

    # --- git evidence -----------------------------------------------------------------------
    open(os.path.join(GIT, "status.txt"), "w").write(git("status"))
    open(os.path.join(GIT, "status_porcelain.txt"), "w").write(git("status", "--porcelain"))
    open(os.path.join(GIT, "log.txt"), "w").write(git("log", "--oneline", "-40"))
    open(os.path.join(GIT, "log_full.txt"), "w").write(git("log", "-12", "--stat"))
    open(os.path.join(GIT, "diff_tracked.patch"), "w").write(git("diff"))
    open(os.path.join(GIT, "diff_staged.patch"), "w").write(git("diff", "--cached"))
    commit = git("rev-parse", "HEAD").strip()
    branch = git("branch", "--show-current").strip()
    base = git("merge-base", "HEAD", "main").strip() or ""
    if base:
        open(os.path.join(GIT, "diff_vs_main.patch"), "w").write(git("diff", base, "HEAD"))
        open(os.path.join(GIT, "files_changed_vs_main.txt"), "w").write(
            git("diff", "--stat", base, "HEAD"))

    # --- source archives --------------------------------------------------------------------
    focused = os.path.join(SRC, "c023_source.tar.gz")
    with tarfile.open(focused, "w:gz") as tf:
        for rel in C023_SOURCE:
            p = os.path.join(_REPO, rel)
            if os.path.exists(p):
                tf.add(p, arcname=rel)
        cdir = os.path.join(_REPO, "contracts", "c023_autonomous_meta_first_competition_sprint")
        for f in ("CONTRACT.md", "README.md", "CLAUDE_COMMAND.txt"):
            p = os.path.join(cdir, f)
            if os.path.exists(p):
                tf.add(p, arcname=os.path.join("contract", f))

    full = os.path.join(SRC, "repo_python_source.tar.gz")
    with tarfile.open(full, "w:gz") as tf:
        for root, dirs, files in os.walk(_REPO):
            dirs[:] = [d for d in dirs if d not in
                       {".git", ".venv", "__pycache__", "external_refs", "results", "contracts"}]
            for f in sorted(files):
                if f.endswith(".py"):
                    p = os.path.join(root, f)
                    tf.add(p, arcname=os.path.relpath(p, _REPO))

    manifest: Dict[str, Any] = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": {"commit": commit, "branch": branch, "merge_base_with_main": base,
                "dirty_tracked": bool(git("status", "--porcelain", "--untracked-files=no").strip())},
        "c023_source_files": [
            {"path": rel, "sha256": sha256_file(os.path.join(_REPO, rel)),
             "bytes": os.path.getsize(os.path.join(_REPO, rel))}
            for rel in C023_SOURCE if os.path.exists(os.path.join(_REPO, rel))],
        "archives": [
            {"path": os.path.relpath(focused, _REPO), "sha256": sha256_file(focused),
             "bytes": os.path.getsize(focused)},
            {"path": os.path.relpath(full, _REPO), "sha256": sha256_file(full),
             "bytes": os.path.getsize(full)},
        ],
        "environment": {
            "python": sys.version.split()[0],
            "platform": subprocess.run(["uname", "-a"], capture_output=True, text=True).stdout.strip(),
            "nproc": os.cpu_count(),
            "kaggle_environments": subprocess.run(
                [os.path.join(_REPO, ".venv", "bin", "python"), "-c",
                 "import kaggle_environments as k;print(k.version)"],
                capture_output=True, text=True).stdout.strip(),
            "libcg_sha256": sha256_file(os.path.join(_REPO, "starter_kit", "libcg.so")),
        },
    }
    with open(os.path.join(SRC, "SOURCE_MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(json.dumps({"commit": commit, "branch": branch,
                      "focused_archive_bytes": os.path.getsize(focused),
                      "full_archive_bytes": os.path.getsize(full),
                      "source_files": len(manifest["c023_source_files"])}, indent=2))

    if a.archive:
        arc = os.path.join(_REPO, "results",
                           "c023_autonomous_meta_first_competition_sprint_results.tar.gz")
        with tarfile.open(arc, "w:gz") as tf:
            tf.add(OUT, arcname="c023_results",
                   filter=lambda ti: None if "__pycache__" in ti.name else ti)
        print(json.dumps({"results_archive": os.path.relpath(arc, _REPO),
                          "sha256": sha256_file(arc), "bytes": os.path.getsize(arc)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

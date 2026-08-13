"""c024 — capture exact source and Git evidence, and build the final results archive.

Same shape as `tools/c023_capture.py`: hash every file this contract authored, record the commit
and the working-tree state, and build one archive of the results tree that can be handed over on
its own. Kept separate rather than folded into the c023 tool because c023's results are frozen
evidence for a closed contract and its file list must not change.

The one addition is `deployability`, and it exists because of D11. A source hash proves *what*
was written; it says nothing about whether the artifact built from it can start on the
competition's harness. Every package in the archive is therefore recorded with its
`raw_python_self_play` verdict alongside its sha256.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import tarfile
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_REPO, "results", "c024_final_sprint")

C024_SOURCE = [
    "tools/c024_extract_kernels.py", "tools/c024_prize_oracle.py", "tools/c024_handsize.py",
    "tools/c024_status.py", "tools/c024_capture.py",
    "starter_kit/c024_prizes.py", "starter_kit/c024_finish.py", "starter_kit/c024_alakazam.py",
    # Touched by this contract, not authored by it: the D11 fixes and the new package check.
    "tools/c023_package.py", "starter_kit/c023_wrapper_main.py", "starter_kit/c023_players.py",
    "tools/c023_build_candidate.py",
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
    ap.add_argument("--archive", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    gitdir = os.path.join(OUT, "git")
    os.makedirs(gitdir, exist_ok=True)

    sources = {}
    for rel in C024_SOURCE:
        p = os.path.join(_REPO, rel)
        if os.path.isfile(p):
            sources[rel] = {"sha256": sha256_file(p), "bytes": os.path.getsize(p)}

    # Deployability, per D11: a hash proves what was written, not that it can start.
    # Packages built before `raw_python_check` existed carry `valid: true` in their manifests and
    # are NOT known to be deployable -- c024_alakazam_v1 is exactly that: its manifest says valid,
    # and it died on Kaggle having played nothing. A status summary that reports the stored
    # `valid` alone would launder a known-bad artifact, so the two are reported separately and
    # the known-bad one is named.
    KNOWN_BAD = {"c024_alakazam_v1": "submitted as 55466460 and ERRORED on its validation "
                                     "episode (D11); manifest predates raw_python_check"}
    deployability = {}
    for m in sorted(glob.glob(os.path.join(
            _REPO, "results", "c023_autonomous_meta_first_competition_sprint",
            "final_packages", "*_manifest.json"))):
        d = json.load(open(m))
        v = d.get("clean_validation") or {}
        checks = v.get("checks") or {}
        name = os.path.basename(m).replace("_manifest.json", "")
        deployability[name] = {
            "archive_sha256": d.get("archive_sha256"),
            "valid": v.get("valid"),
            "raw_python_self_play": checks.get("raw_python_self_play"),
            "note": (KNOWN_BAD.get(name) if name in KNOWN_BAD else
                     (None if checks.get("raw_python_self_play")
                      else "manifest predates raw_python_check -- deployability UNVERIFIED, "
                           "not a claim that it works")),
            "deployable": (False if name in KNOWN_BAD
                           else checks.get("raw_python_self_play")),
        }

    with open(os.path.join(gitdir, "c024_diff.txt"), "w") as fh:
        fh.write(git("diff", "HEAD~12", "--stat"))
    with open(os.path.join(gitdir, "c024_log.txt"), "w") as fh:
        fh.write(git("log", "--oneline", "-25"))

    payload = {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": git("rev-parse", "HEAD").strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "dirty": bool(git("status", "--porcelain").strip()),
        "sources": sources,
        "deployability": deployability,
    }
    with open(os.path.join(OUT, "SOURCE_EVIDENCE.json"), "w") as fh:
        json.dump(payload, fh, indent=2)

    print(f"commit {payload['commit'][:12]} dirty={payload['dirty']}  "
          f"{len(sources)} source files hashed")
    for n, d in deployability.items():
        print(f"  package {n:32s} valid={d['valid']} raw_python={d['raw_python_self_play']} "
              f"deployable={d['deployable']}"
              + (f"  <- {d['note']}" if d.get("note") else ""))

    if a.archive:
        arc = os.path.join(_REPO, "results", "c024_final_sprint_results.tar.gz")
        with tarfile.open(arc, "w:gz") as tar:
            tar.add(OUT, arcname="c024_final_sprint")
        print(json.dumps({"results_archive": os.path.relpath(arc, _REPO),
                          "sha256": sha256_file(arc),
                          "bytes": os.path.getsize(arc)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

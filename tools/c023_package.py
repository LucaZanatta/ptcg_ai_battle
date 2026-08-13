"""c023 — build and validate a Kaggle submission package for a player.

A package is what the competition actually runs: a `.tar.gz` holding `main.py`, `deck.csv`, any
modules `main.py` imports, and the official `cg` SDK. c018/c019 established the shape and the
clean-validation step; this keeps both.

Validation is by *execution*, not by inspection. The archive is extracted to a scratch directory
with nothing else on the path, games are played out of that directory, and the package is only
recorded as valid if those games complete with zero errors, zero illegal selections and a decision
latency inside the self-imposed bound. A package that has only been listed has not been validated.

The frozen champion's package is written once and never overwritten: `--freeze` refuses to
replace an existing archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
PKG = os.path.join(OUT, "final_packages")
SDK = os.path.join(_REPO, "starter_kit")

# The SDK files the competition ships in `sample_submission/cg`.
SDK_FILES = ["api.py", "game.py", "sim.py", "utils.py", "libcg.so", "__init__.py"]

# Self-imposed, and labelled as such: the competition's published per-decision timeout is not
# machine-retrievable (the rules page is a client-rendered SPA; c005 recorded this).
LATENCY_BOUND_MS = 1000.0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(player_id: str, out_name: str, freeze: bool = False) -> Dict[str, Any]:
    from cg import c023_players as P
    d = P.resolve(player_id)
    os.makedirs(PKG, exist_ok=True)
    archive = os.path.join(PKG, out_name + ".tar.gz")
    if os.path.exists(archive) and freeze:
        raise FileExistsError(f"{archive} exists and --freeze forbids overwriting the frozen "
                              f"champion package")

    members: List[str] = []
    with tarfile.open(archive, "w:gz") as tf:
        for root, _dirs, files in os.walk(d):
            for f in sorted(files):
                if f.endswith(".pyc") or "__pycache__" in root:
                    continue
                full = os.path.join(root, f)
                arc = os.path.relpath(full, d)
                tf.add(full, arcname=arc)
                members.append(arc)
        for f in SDK_FILES:
            src = os.path.join(SDK, f)
            if os.path.exists(src):
                tf.add(src, arcname=os.path.join("cg", f))
                members.append(os.path.join("cg", f))
    return {"player_id": player_id, "archive": os.path.relpath(archive, _REPO),
            "archive_sha256": sha256_file(archive),
            "archive_bytes": os.path.getsize(archive),
            "members": sorted(members)}


def clean_validate(archive: str, games: int, opponents: List[str],
                   procs: int) -> Dict[str, Any]:
    """Extract to a scratch dir and play out of it, with the repo NOT on the agent's path."""
    tmp = tempfile.mkdtemp(prefix="c023_pkg_")
    ext = os.path.join(tmp, "agent")
    os.makedirs(ext, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        try:
            tf.extractall(ext, filter="data")
        except TypeError:
            tf.extractall(ext)
    required = ["main.py", "deck.csv", os.path.join("cg", "libcg.so")]
    missing = [r for r in required if not os.path.exists(os.path.join(ext, r))]
    if missing:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"valid": False, "reason": f"missing from archive: {missing}"}

    # Register the extracted copy as a temporary player and evaluate it with the normal harness,
    # so package games and campaign games are measured by the same code.
    agents_dir = os.path.join(OUT, "agents")
    link = os.path.join(agents_dir, "_pkgtest")
    os.makedirs(agents_dir, exist_ok=True)
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link) if os.path.islink(link) else shutil.rmtree(link)
    os.symlink(ext, link)
    try:
        sys.path.insert(0, os.path.join(_REPO, "tools"))
        import c023_eval as E
        jobs = E.build_jobs(["_pkgtest"], opponents, games, "package")
        results = E.run_jobs(jobs, procs)
        summ = E.summarize(results, games)["_pkgtest"]
        # Run it the way Kaggle will, BEFORE the extracted tree is deleted.
        raw = raw_python_check(ext)
    finally:
        if os.path.islink(link):
            os.remove(link)
        shutil.rmtree(tmp, ignore_errors=True)

    ok = (summ["errors"] == 0 and summ["completed_games"] == summ["requested_games"]
          and summ["latency_max_ms"] <= LATENCY_BOUND_MS
          and summ["per_seat"]["seat0_games"] > 0 and summ["per_seat"]["seat1_games"] > 0
          and raw["raw_python_self_play"])
    return {"valid": bool(ok), "summary": summ, "raw_python": raw,
            "latency_bound_ms": LATENCY_BOUND_MS,
            "latency_bound_is": "SELF-IMPOSED; the competition's published per-decision timeout "
                                "is not machine-retrievable (client-rendered rules page)",
            "checks": {
                "zero_errors": summ["errors"] == 0,
                "all_completed": summ["completed_games"] == summ["requested_games"],
                "max_latency_within_bound": summ["latency_max_ms"] <= LATENCY_BOUND_MS,
                "both_seats": summ["per_seat"]["seat0_games"] > 0 and summ["per_seat"]["seat1_games"] > 0,
                # The check that submission 55466460 needed and did not have.
                "raw_python_self_play": raw["raw_python_self_play"],
            }}


def raw_python_check(pkg_dir: str) -> dict:
    """Run the package the way the COMPETITION runs it: by file path, agent against itself.

    This is not a duplicate of the play validation above. That one imports `main.py` as a module,
    which is how this repository's harness loads a player -- and it is *not* how Kaggle loads one.
    `kaggle_environments.get_last_callable` reads the source and `exec`s it in a bare namespace
    with no `__file__`, then Kaggle's first act on a new submission is a VALIDATION episode of the
    agent against itself.

    c024 submission 55466460 passed every check in this file and then died on that validation
    episode with `Invalid raw Python: NameError("name '__file__' is not defined")`, having played
    no cards at all. Module-import validation cannot see that class of defect, and neither can a
    round-robin against other players. Both gaps are closed here.
    """
    import subprocess
    code = (
        "from kaggle_environments import make\n"
        "env = make('cabt', configuration={})\n"
        "env.run(['main.py', 'main.py'])\n"
        "last = env.steps[-1]\n"
        "print('STATUS', last[0]['status'], last[1]['status'], len(env.steps))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=pkg_dir, capture_output=True, text=True,
                       timeout=900)
    line = next((l for l in r.stdout.splitlines() if l.startswith("STATUS")), "")
    parts = line.split()
    ok = len(parts) == 4 and parts[1] == "DONE" and parts[2] == "DONE" and int(parts[3]) > 10
    err = ""
    if not ok:
        # The engine SDK logs ~35 INFO lines to stderr on import, so the last line is almost
        # never the exception. Keep the lines that look like a traceback's payload.
        lines = [l for l in (r.stderr or "").splitlines()
                 if l.strip() and "INFO:" not in l and not l.startswith(" ")]
        err = lines[-1][:300] if lines else ((r.stderr or r.stdout or "").strip()[-300:])
    return {"raw_python_self_play": ok, "steps": (int(parts[3]) if ok else None), "error": err}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--opponents", default="official_dragapult,official_iono,"
                                           "official_mega_abomasnow,pub_tetsutani_grimmsnarl")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 6))
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    man = build(a.player, a.name, a.freeze)
    val = clean_validate(os.path.join(_REPO, man["archive"]), a.games,
                         [x for x in a.opponents.split(",") if x], a.procs)
    man["clean_validation"] = val
    man["note"] = a.note
    man["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    man["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                       capture_output=True, text=True).stdout.strip()
    man["git_dirty"] = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                           cwd=_REPO, capture_output=True, text=True).stdout.strip())
    attribution = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint",
                               "agents", a.player, "ATTRIBUTION.txt")
    if os.path.exists(attribution):
        man["attribution"] = open(attribution).read()
    with open(os.path.join(PKG, a.name + "_manifest.json"), "w") as fh:
        json.dump(man, fh, indent=2)
    print(json.dumps({"archive": man["archive"], "sha256": man["archive_sha256"][:16],
                      "bytes": man["archive_bytes"], "valid": val["valid"],
                      "checks": val.get("checks")}, indent=2))
    return 0 if val["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

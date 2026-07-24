"""Reproducible acquisition of strategic teacher candidates (c005 Phase A).

- Official Kaggle sample kernels via `kaggle kernels output` (packaged
  submission.tar.gz = main.py + deck.csv + cg/) and `kaggle kernels pull`
  (notebook source). No credentials are read or written by this script.
- The public benchmark repo `wmh/ptcg-abc` via `git clone` pinned to a commit.
- SHA-256 for every acquired main.py / deck.csv; retrieval timestamps; reuse
  classification; and any failed attempts.

Raw third-party downloads land under the OUTPUT dir (kept in results/, NOT
committed). Writes source_evidence.json.

Usage (from repo root):
  .venv/bin/python tools/acquire_teachers.py \
      --out-dir contracts/c005_teacher_import_submission_and_dataset/results/artifacts/teacher_sources
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

OFFICIAL_KERNELS = {
    "dragapult": ("kiyotah/a-sample-rule-based-agent-dragapult-ex-deck", "Dragapult ex"),
    "mega_lucario": ("kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck", "Mega Lucario ex"),
    "mega_abomasnow": ("kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck", "Mega Abomasnow ex"),
    "iono": ("kiyotah/a-sample-rule-based-agent-iono-s-deck", "Iono's deck"),
}
BENCHMARK_REPO = "https://github.com/wmh/ptcg-abc"
KAGGLE = os.path.join(os.path.dirname(sys.executable), "kaggle")


def _sha(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def _run(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def acquire_official(cid, ref, archetype, out_dir, log):
    dst = os.path.join(out_dir, cid)
    os.makedirs(dst, exist_ok=True)
    entry = {"candidate_id": cid, "archetype": archetype, "source_type": "official_kaggle_sample",
             "source_reference": f"kaggle:{ref}", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
             "reuse_classification": "OFFICIAL_REUSABLE", "attribution": f"Official Kaggle sample kernel {ref} (Kiyota)",
             "submission_eligible": True, "commands": [], "failed": []}
    # kernel output (packaged submission)
    rc, out = _run([KAGGLE, "kernels", "output", ref, "-p", dst], timeout=120)
    log.append(f"$ kaggle kernels output {ref}\n(exit {rc})\n{out.strip()[:400]}\n")
    entry["commands"].append(f"kaggle kernels output {ref} -p {os.path.relpath(dst)}")
    tgz = os.path.join(dst, "submission.tar.gz")
    if rc != 0 or not os.path.isfile(tgz):
        entry["failed"].append({"step": "kernels_output", "exit": rc})
        return entry
    entry["submission_sha256"] = _sha(tgz)
    with tarfile.open(tgz) as tf:
        tf.extractall(dst)
    # kernel source notebook (provenance)
    rc2, out2 = _run([KAGGLE, "kernels", "pull", ref, "-p", os.path.join(dst, "src"), "-m"], timeout=90)
    log.append(f"$ kaggle kernels pull {ref} -m\n(exit {rc2})\n{out2.strip()[:200]}\n")
    entry["commands"].append(f"kaggle kernels pull {ref} -p {os.path.relpath(dst)}/src -m")
    main_py = os.path.join(dst, "main.py")
    deck = os.path.join(dst, "deck.csv")
    entry["agent"] = {"agent_id": cid, "agent_version": ref, "policy_type": "rule_based_strategic",
                      "source_files": [{"path": f"main.py", "sha256": _sha(main_py)}]}
    entry["deck_source"] = {"path": "deck.csv", "sha256": _sha(deck)}
    try:
        with open(deck) as fh:
            cards = [int(x) for x in fh if x.strip()]
        entry["deck_card_count"] = len(cards)
        entry["deck_distinct"] = len(set(cards))
    except Exception as exc:
        entry["failed"].append({"step": "deck_read", "error": str(exc)})
    entry["runnable_files"] = sorted(os.path.relpath(os.path.join(r, f), dst)
                                     for r, _d, fs in os.walk(dst) for f in fs
                                     if f in ("main.py", "deck.csv") or f.endswith(".so"))
    return entry


def acquire_benchmark(out_dir, log):
    dst = os.path.join(out_dir, "ptcg-abc")
    entry = {"candidate_id": "bellibolt", "archetype": "Bellibolt (public benchmark)",
             "source_type": "public_repository", "source_reference": BENCHMARK_REPO,
             "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
             "reuse_classification": "LOCAL_BENCHMARK_ONLY",
             "attribution": "wmh/ptcg-abc (public GitHub). No explicit license observed -> local benchmark only; NOT submission-eligible and NOT copied into training artifacts.",
             "submission_eligible": False, "commands": [], "failed": []}
    rc, out = _run(["git", "clone", "--depth", "1", BENCHMARK_REPO, dst], timeout=120)
    log.append(f"$ git clone --depth 1 {BENCHMARK_REPO}\n(exit {rc})\n{out.strip()[:300]}\n")
    entry["commands"].append(f"git clone --depth 1 {BENCHMARK_REPO}")
    if rc != 0:
        entry["failed"].append({"step": "git_clone", "exit": rc})
        return entry
    rc2, commit = _run(["git", "-C", dst, "rev-parse", "HEAD"])
    entry["source_version"] = commit.strip()
    rc3, lic = _run(["bash", "-lc", f"ls {dst} | grep -iE '^licen' || echo NONE"])
    entry["license_files"] = lic.strip()
    entry["agents_present"] = sorted(d for d in os.listdir(os.path.join(dst, "agents"))
                                     if os.path.isdir(os.path.join(dst, "agents", d))) if os.path.isdir(os.path.join(dst, "agents")) else []
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description="Acquire strategic teachers")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)
    log = [f"# Teacher acquisition — {datetime.now(timezone.utc).isoformat()}\n"]
    evidence = {"acquired_at_utc": datetime.now(timezone.utc).isoformat(),
                "official_candidates": [], "public_candidates": [], "notes": [
                    "No Kaggle credentials required for public kernel output/pull (anonymous read).",
                    "Official kiyotah samples are competition-provided baselines -> OFFICIAL_REUSABLE.",
                    "wmh/ptcg-abc has no explicit license -> LOCAL_BENCHMARK_ONLY (not submitted, not in training data)."]}
    for cid, (ref, arch) in OFFICIAL_KERNELS.items():
        evidence["official_candidates"].append(acquire_official(cid, ref, arch, args.out_dir, log))
    evidence["public_candidates"].append(acquire_benchmark(args.out_dir, log))

    with open(os.path.join(args.out_dir, "source_evidence.json"), "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)
    print("".join(log))
    ok = sum(1 for c in evidence["official_candidates"] if not c["failed"])
    print(f"official acquired: {ok}/{len(OFFICIAL_KERNELS)} | benchmark: "
          f"{'ok' if not evidence['public_candidates'][0]['failed'] else 'failed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

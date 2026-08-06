"""c013 §36 — identity-safe evaluation extended to ONLINE ENSEMBLE candidates.

Design note. The game loop, scoring convention, defect classification and latency accounting
all live in `cg.c009_eval.run_job`. Re-implementing them here for ensembles would risk the two
paths diverging, which would make ensemble scores incomparable with single-policy scores --
exactly the sort of silent inconsistency this project keeps paying for. So c013 REUSES c009's
worker unchanged and only supplies it with a different policy object:

  * every ensemble gets a MANIFEST file whose content is the combination mode plus the ordered
    component paths and hashes. The manifest is the ensemble's `checkpoint_path`, so c009's
    existing "re-hash the file you loaded" identity check applies verbatim;
  * before delegating, the worker independently re-hashes every COMPONENT on disk and refuses
    the job if any differs from the manifest, so a swapped or stale component fails identity
    just as a swapped checkpoint does for a single policy;
  * the built ensemble is inserted into c009's policy cache under the manifest path, so
    `_load_policy` returns it without c009 being modified in any way (§4).

c009/c011/c012 code is imported, never modified.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from cg import c009_eval as ce, c011_eval_core as cc  # noqa: E402

TEACHER_MAIN = cc.TEACHER_MAIN


def write_manifest(path: str, mode: str, component_ids: List[str],
                   component_paths: List[str], component_sha: List[str]) -> str:
    """Deterministic, hashable identity for an online ensemble."""
    doc = {"kind": "online_ensemble", "mode": mode,
           "components": [{"id": i, "path": p, "sha256": s}
                          for i, p, s in zip(component_ids, component_paths, component_sha)],
           "note": "Equal-weight combination. This manifest IS the ensemble's checkpoint for "
                   "identity purposes; the worker re-hashes it and every component it loads."}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    return path


def _defect_record(identity, defect, components=None):
    return {**identity, "outcome": None, "score": None, "terminal": False,
            "decision_count": 0, "fallback_count": 0, "invalid_action_count": 0,
            "exception_count": 0, "timeout_count": 0, "latency_p50_ms": None,
            "latency_p95_ms": None, "latency_p99_ms": None, "duration_seconds": 0.0,
            "verified_checkpoint_sha256": None, "deck_fingerprint": None,
            "defect": defect, "component_sha256": components}


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Ensembles are built and cached, then delegated to the unmodified c009 worker."""
    if job.get("candidate_kind") != "online_ensemble":
        return cc.run_job(job)

    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c013_ensemble_policy as ep

    man_path = os.path.join(_REPO, job["checkpoint_path"])
    identity = {k: job[k] for k in ce.IDENTITY_FIELDS}
    identity.update({"arm": job.get("arm"), "seed": job.get("seed"),
                     "candidate_kind": job["candidate_kind"]})
    got = None
    try:
        man = json.load(open(man_path))
        paths = [os.path.join(_REPO, c["path"]) for c in man["components"]]
        want = [c["sha256"] for c in man["components"]]
        got = [ce.sha256_file(p) for p in paths]
        if got != want:
            return _defect_record(identity, "ensemble_component_hash_mismatch", got)
        pol = ep.build(paths, man["mode"],
                       component_ids=[c["id"] for c in man["components"]],
                       component_sha256=got)
    except Exception as e:  # noqa: BLE001
        return _defect_record(identity, f"ensemble_build_failed:{type(e).__name__}:{e}", got)

    # hand the ensemble to c009's loader without modifying c009
    ce._POLICY_CACHE[("rl_ckpt", man_path)] = pol
    inner = dict(job)
    inner["candidate_kind"] = "rl_ckpt"
    rec = ce.run_job(inner)
    rec["candidate_kind"] = "online_ensemble"
    rec["component_sha256"] = got
    rec["ensemble_mode"] = man["mode"]
    return rec


def run_jobs(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    import multiprocessing as mp
    if nproc <= 1 or len(jobs) <= 1:
        return [run_job(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(run_job, jobs, chunksize=1))

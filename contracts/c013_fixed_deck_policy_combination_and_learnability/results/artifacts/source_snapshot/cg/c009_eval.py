"""c009 identity-safe evaluator core (repairs the c008 unordered-result identity defect).

Contract §8.2: every submitted job carries an immutable identity
(``job_id, candidate_id, checkpoint_sha256, opponent_id, seat, replicate, requested_seed``)
and **every worker result returns those same fields directly**. No post-hoc positional
reattachment is permitted anywhere in this module.

Defence in depth: the worker re-hashes the checkpoint file it actually loaded and returns
that hash, and it returns a fingerprint of the deck it actually played, so the orchestrator
can prove each game used the intended weights and the exact frozen deck.

Read-only with respect to c005–c008 (checkpoints are loaded, never written).
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                       "results", "artifacts", "teacher_sources")

# identity fields that MUST round-trip from job to result unchanged
IDENTITY_FIELDS = ("job_id", "candidate_id", "checkpoint_sha256", "opponent_id",
                   "seat", "replicate", "requested_seed", "phase")

_POLICY_CACHE: Dict[Tuple[str, str], Any] = {}
_SHA_CACHE: Dict[str, str] = {}


def sha256_file(path: str) -> str:
    if path in _SHA_CACHE:
        return _SHA_CACHE[path]
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    _SHA_CACHE[path] = h.hexdigest()
    return _SHA_CACHE[path]


def deck_fingerprint(deck: Iterable[int]) -> str:
    return hashlib.sha256(",".join(str(int(c)) for c in deck).encode()).hexdigest()


def make_job_id(candidate_id: str, opponent_id: str, seat: int, replicate: int, phase: str) -> str:
    return f"{phase}::{candidate_id}::{opponent_id}::s{seat}::r{replicate}"


def make_job(candidate: Dict[str, Any], opponent_id: str, seat: int, replicate: int,
             phase: str, requested_seed: int, deck: List[int]) -> Dict[str, Any]:
    return {
        "job_id": make_job_id(candidate["candidate_id"], opponent_id, seat, replicate, phase),
        "candidate_id": candidate["candidate_id"],
        "candidate_kind": candidate["kind"],
        "checkpoint_path": candidate["checkpoint_path"],
        "checkpoint_sha256": candidate["checkpoint_sha256"],
        "arm": candidate["arm"], "seed": candidate.get("seed"),
        "opponent_id": opponent_id, "seat": int(seat), "replicate": int(replicate),
        "requested_seed": int(requested_seed), "phase": phase,
        "deck": list(deck),
    }


# -------------------- policy / opponent construction --------------------

def _load_policy(kind: str, path: str):
    key = (kind, path)
    pol = _POLICY_CACHE.get(key)
    if pol is not None:
        return pol
    from cg.rl_policy import RLPolicy
    if kind == "rl_ckpt":
        pol = RLPolicy.load(path)
    elif kind == "v2a_init":
        # B0: the exact untouched c007 V2-A trunk, value head/STOP at their untrained init —
        # i.e. precisely the policy R1/R2 started from at game zero. Nothing is written.
        pol = RLPolicy(seed=0)
        pol.init_from_v2a(path)
    else:
        raise ValueError(f"unknown candidate kind {kind}")
    _POLICY_CACHE[key] = pol
    return pol


def _build_focus(job: Dict[str, Any], rng):
    kind = job["candidate_kind"]
    if kind == "frozen_teacher":
        from cg.teachers import make_fresh
        return make_fresh("dragapult", SOURCES), None
    from cg.rl_env import RLAgent
    pol = _load_policy(kind, os.path.join(_REPO, job["checkpoint_path"]))
    return RLAgent(pol, job["deck"], rng, collect=False, greedy=True), pol


def _build_opponent(opponent_id: str, deck: List[int]):
    if opponent_id == "__control__":
        from cg.control_agent import DetControl
        return DetControl(deck)
    from cg.teachers import make_fresh
    return make_fresh(opponent_id, SOURCES)


# -------------------- worker --------------------

def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Play one game. ALWAYS returns the job's identity fields verbatim, plus the hash of the
    checkpoint actually loaded and a fingerprint of the deck actually played."""
    identity = {k: job[k] for k in IDENTITY_FIELDS}
    identity.update({"arm": job["arm"], "seed": job["seed"],
                     "candidate_kind": job["candidate_kind"]})
    t0 = time.time()
    rec = {**identity, "outcome": None, "score": None, "terminal": False,
           "decision_count": 0, "fallback_count": 0, "invalid_action_count": 0,
           "exception_count": 0, "timeout_count": 0,
           "latency_p50_ms": None, "latency_p95_ms": None, "latency_p99_ms": None,
           "duration_seconds": 0.0, "verified_checkpoint_sha256": None,
           "deck_fingerprint": None, "defect": None}

    # verify the weights this worker will actually use
    if job["candidate_kind"] != "frozen_teacher":
        ap = os.path.join(_REPO, job["checkpoint_path"])
        try:
            rec["verified_checkpoint_sha256"] = sha256_file(ap)
        except OSError as e:  # noqa: BLE001
            rec["defect"] = f"checkpoint_unreadable:{e}"
            rec["duration_seconds"] = round(time.time() - t0, 3)
            return rec
        if rec["verified_checkpoint_sha256"] != job["checkpoint_sha256"]:
            rec["defect"] = "checkpoint_hash_mismatch"
            rec["duration_seconds"] = round(time.time() - t0, 3)
            return rec
    else:
        rec["verified_checkpoint_sha256"] = job["checkpoint_sha256"]

    rec["deck_fingerprint"] = deck_fingerprint(job["deck"])

    from kaggle_environments import make
    from cg.safe_policy import MalformedSelection, validate_selection
    rng = np.random.default_rng(job["requested_seed"])
    lat: List[int] = []
    invalid = [0]
    try:
        focus, _pol = _build_focus(job, rng)
        opp = _build_opponent(job["opponent_id"], job["deck"])
    except Exception as e:  # noqa: BLE001
        rec["defect"] = f"agent_build_failed:{type(e).__name__}:{e}"
        rec["exception_count"] = 1
        rec["duration_seconds"] = round(time.time() - t0, 3)
        return rec

    def focus_wrapped(obs):
        sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
        t = time.perf_counter_ns()
        res = focus(obs)
        dt = time.perf_counter_ns() - t
        if sel is not None:
            lat.append(dt)
            n = len(sel.get("option", []))
            try:
                validate_selection(list(res), n, sel.get("minCount"), sel.get("maxCount"))
            except MalformedSelection:
                invalid[0] += 1
        return res

    def opp_wrapped(obs):
        return opp(obs)

    players = [focus_wrapped, opp_wrapped] if job["seat"] == 0 else [opp_wrapped, focus_wrapped]
    env = None
    exc = None
    try:
        env = make("cabt")
        env.run(players)
    except Exception as e:  # noqa: BLE001
        exc = f"{type(e).__name__}:{e}"

    if lat:
        a = np.asarray(lat) / 1e6
        rec["latency_p50_ms"] = float(np.percentile(a, 50))
        rec["latency_p95_ms"] = float(np.percentile(a, 95))
        rec["latency_p99_ms"] = float(np.percentile(a, 99))
    rec["decision_count"] = int(getattr(focus, "n_decisions", len(lat)) or len(lat))
    rec["fallback_count"] = int(getattr(focus, "n_fallback", 0) or 0)
    rec["invalid_action_count"] = int(invalid[0])
    rec["duration_seconds"] = round(time.time() - t0, 3)

    if exc is not None or env is None:
        rec["exception_count"] = 1
        rec["defect"] = f"env_exception:{exc}"
        return rec
    last = env.steps[-1]
    statuses = [last[0]["status"], last[1]["status"]]
    rewards = [last[0].get("reward"), last[1].get("reward")]
    rec["timeout_count"] = int(sum(1 for s in statuses if s == "TIMEOUT"))
    if statuses != ["DONE", "DONE"]:
        rec["defect"] = f"non_terminal:{statuses}"
        return rec
    rec["terminal"] = True
    r_focus = rewards[job["seat"]]
    if rewards[0] == rewards[1]:
        rec["outcome"], rec["score"] = "draw", 0.5
    elif r_focus == 1:
        rec["outcome"], rec["score"] = "win", 1.0
    else:
        rec["outcome"], rec["score"] = "loss", 0.0
    return rec


def run_jobs(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    """Execute jobs. Results may arrive in ANY order — identity travels inside each result,
    so order is irrelevant by construction (this is the c008 repair)."""
    if nproc <= 1 or len(jobs) <= 1:
        return [run_job(j) for j in jobs]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(run_job, jobs, chunksize=1))


# -------------------- identity assertions (§8.3) --------------------

class IdentityError(AssertionError):
    pass


def assert_identity(jobs: List[Dict[str, Any]], results: List[Dict[str, Any]],
                    registry: Dict[str, Dict[str, Any]],
                    expected_deck_fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """All nine §8.3 assertions. Raises IdentityError on any violation; returns a report."""
    problems: List[str] = []
    jmap = {j["job_id"]: j for j in jobs}

    # 1. submitted job IDs unique
    if len(jmap) != len(jobs):
        problems.append(f"submitted job_ids not unique: {len(jobs)} jobs, {len(jmap)} unique")
    # 2. returned job IDs unique
    rids = [r.get("job_id") for r in results]
    if len(set(rids)) != len(rids):
        dup = [i for i, c in __import__("collections").Counter(rids).items() if c > 1]
        problems.append(f"returned job_ids not unique (duplicates: {dup[:5]})")
    # 3. submitted set == returned set
    missing = sorted(set(jmap) - set(rids))
    unexpected = sorted(set(rids) - set(jmap))
    if missing:
        problems.append(f"{len(missing)} submitted job_ids missing from results (e.g. {missing[:3]})")
    if unexpected:
        problems.append(f"{len(unexpected)} unexpected job_ids in results (e.g. {unexpected[:3]})")

    per_cell = __import__("collections").Counter()
    for r in results:
        j = jmap.get(r.get("job_id"))
        if j is None:
            continue
        # 4. candidate id known to the frozen registry
        if r["candidate_id"] not in registry:
            problems.append(f"{r['job_id']}: candidate_id {r['candidate_id']} not in registry")
        # 5. checkpoint hash matches registry AND what the worker actually loaded
        reg_sha = registry.get(r["candidate_id"], {}).get("checkpoint_sha256")
        if reg_sha is not None and r["checkpoint_sha256"] != reg_sha:
            problems.append(f"{r['job_id']}: checkpoint_sha256 != registry")
        if r.get("verified_checkpoint_sha256") != r["checkpoint_sha256"]:
            problems.append(f"{r['job_id']}: worker-verified checkpoint hash mismatch")
        # 6. every identity field round-trips from the submitted job
        for f in IDENTITY_FIELDS:
            if r.get(f) != j.get(f):
                problems.append(f"{r['job_id']}: identity field {f} changed "
                                f"({j.get(f)!r} -> {r.get(f)!r})")
        # deck actually played
        if expected_deck_fingerprint and r.get("deck_fingerprint") != expected_deck_fingerprint:
            problems.append(f"{r['job_id']}: deck fingerprint mismatch (not the frozen deck)")
        per_cell[(r["candidate_id"], r["opponent_id"], r["seat"])] += 1

    # 7. expected count per candidate/opponent/seat is exact
    exp_cell = __import__("collections").Counter(
        (j["candidate_id"], j["opponent_id"], j["seat"]) for j in jobs)
    for cell, n in exp_cell.items():
        if per_cell.get(cell, 0) != n:
            problems.append(f"count mismatch {cell}: expected {n}, got {per_cell.get(cell, 0)}")
    # 8. no unexpected candidates/opponents
    unexpected_cells = set(per_cell) - set(exp_cell)
    if unexpected_cells:
        problems.append(f"unexpected candidate/opponent/seat cells: {sorted(unexpected_cells)[:5]}")
    # 9. every game terminal or explicitly classified as a defect
    unclassified = [r["job_id"] for r in results if not r.get("terminal") and not r.get("defect")]
    if unclassified:
        problems.append(f"{len(unclassified)} games neither terminal nor defect-classified")

    report = {
        "n_jobs": len(jobs), "n_results": len(results),
        "unique_submitted": len(jmap), "unique_returned": len(set(rids)),
        "missing": len(missing), "unexpected": len(unexpected),
        "cells": len(exp_cell),
        "terminal": sum(1 for r in results if r.get("terminal")),
        "defects": sum(1 for r in results if r.get("defect")),
        "problems": problems, "ok": not problems,
    }
    if problems:
        raise IdentityError("identity assertions failed:\n  - " + "\n  - ".join(problems[:20]))
    return report

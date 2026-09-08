"""c023 — the campaign's one evaluation harness.

Every strength number in this contract comes from here, so that two numbers placed side by side
are never two different measuring sticks (the failure c022's final panel was built to avoid).

Design commitments, each answering a defect this repository has already paid for:

* **Identity travels with the job.** Every result carries back the job's own
  `job_id / candidate_id / opponent_id / seat / replicate`, plus the sha256 of the `main.py` and
  `deck.csv` that actually played. Nothing is ever re-attached by list position — that defect
  misattributed 19,542 records in c019 and corrupted 8 of 20 cells in c008.
* **Factory-wrapped closures.** `kaggle_environments` inspects the agent signature and passes
  `(observation, configuration)` to anything taking two parameters. Default-argument capture has
  silently killed three whole runs in this repo.
* **Seat balance by construction.** Replicates alternate seats, so a candidate's score is never a
  measurement of going first.
* **Errors are counted, not swallowed.** A game whose status is not DONE/DONE is recorded as an
  error and excluded from the score, and the counts are reported next to it.

The engine cannot be seeded (`libcg.so` seeds `std::mt19937` from `std::random_device`; c002
established this externally). So games are NOT paired on the deal — pairing here means matched
opponents, matched seats and matched counts, and the reports say so rather than implying a
common-random-numbers design that the engine refuses.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from typing import Any, Dict, Iterable, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

# One BLAS thread per worker. Unset, every worker opens a pool the width of the machine and the
# workers fight each other; this repository has paid for that mistake twice.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

OUT_ROOT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
RAW = os.path.join(OUT_ROOT, "raw_evaluations")

IDENTITY_FIELDS = ("job_id", "candidate_id", "opponent_id", "seat", "replicate", "phase")


def wilson(k: float, n: int, z: float = 1.96) -> List[Optional[float]]:
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


# --------------------------------------------------------------------------------------------
# worker
# --------------------------------------------------------------------------------------------

def _play(job: Dict[str, Any]) -> Dict[str, Any]:
    """Play exactly one game. Every engine import happens here so the parent stays clean."""
    sys.path.insert(0, _REPO)
    t0 = time.time()
    rec: Dict[str, Any] = {k: job[k] for k in IDENTITY_FIELDS}
    rec.update({"completed": False, "error": None, "score": None, "reward": None,
                "steps": None, "seconds": None})
    a = b = None
    try:
        from kaggle_environments import make
        from cg import c023_players as P

        cand = P.make_fresh(job["candidate_id"])
        opp = P.make_fresh(job["opponent_id"])
        rec["candidate_main_sha256"] = cand.main_sha256
        rec["candidate_deck_sha256"] = cand.deck_sha256
        rec["opponent_main_sha256"] = opp.main_sha256
        rec["opponent_deck_sha256"] = opp.deck_sha256
        a, b = cand, opp

        lat: List[float] = []
        trivial = [0]      # decisions where the action equals the mindless legal fallback
        ndec = [0]

        def _trivial_action(o):
            sel = o.get("select") if isinstance(o, dict) else getattr(o, "select", None)
            if not sel:
                return None
            opts = (sel.get("option") if isinstance(sel, dict) else getattr(sel, "option", None)) or []
            mx = int((sel.get("maxCount") if isinstance(sel, dict) else getattr(sel, "maxCount", 0)) or 0)
            return list(range(min(len(opts), mx)))

        def timed(player):
            def f(o):
                s = time.perf_counter()
                r = player(o)
                lat.append(time.perf_counter() - s)
                # Integrity probe: an agent whose module failed to load still returns legal
                # actions -- the first k option indices -- and looks like a weak player rather
                # than a broken one. Counting exact agreement with that fallback catches it.
                t = _trivial_action(o)
                if t is not None:
                    ndec[0] += 1
                    if list(r) == t:
                        trivial[0] += 1
                return r
            return f

        def plain(player):
            def f(o):
                return player(o)
            return f

        seat = int(job["seat"])          # 0 = candidate moves as player 0
        agents = [timed(cand), plain(opp)] if seat == 0 else [plain(opp), timed(cand)]

        env = make("cabt", configuration={})
        env.run(agents)
        last = env.steps[-1]
        st = [last[i]["status"] for i in (0, 1)]
        rew = [last[i]["reward"] for i in (0, 1)]
        rec["steps"] = len(env.steps)
        rec["statuses"] = st
        rec["rewards"] = rew
        if st[0] == "DONE" and st[1] == "DONE":
            r = rew[seat]
            rec["completed"] = True
            rec["reward"] = r
            rec["score"] = 1.0 if r == 1 else (0.5 if r == 0 else 0.0)
        else:
            rec["error"] = f"status={st}"
        if ndec[0]:
            rec["trivial_fallback_decisions"] = trivial[0]
            rec["scored_decisions"] = ndec[0]
        if lat:
            lat_sorted = sorted(lat)
            rec["decisions"] = len(lat)
            rec["latency_mean_ms"] = round(1000 * sum(lat) / len(lat), 4)
            rec["latency_p99_ms"] = round(1000 * lat_sorted[min(len(lat) - 1, int(0.99 * len(lat)))], 4)
            rec["latency_max_ms"] = round(1000 * lat_sorted[-1], 4)
    except Exception as exc:  # noqa: BLE001 - a worker must never take the pool down
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc()[-1500:]
    finally:
        for p in (a, b):
            if p is not None:
                try:
                    p.close()
                except Exception:
                    pass
    rec["seconds"] = round(time.time() - t0, 3)
    return rec


# --------------------------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------------------------

def build_jobs(candidates: List[str], opponents: List[str], games: int, phase: str,
               skip_self: bool = False) -> List[Dict[str, Any]]:
    """`games` per (candidate, opponent) ordered pair, seat-balanced."""
    jobs = []
    for c in candidates:
        for o in opponents:
            if skip_self and c == o:
                continue
            for r in range(games):
                seat = r % 2
                jobs.append({"job_id": f"{phase}::{c}::{o}::s{seat}::r{r}",
                             "candidate_id": c, "opponent_id": o, "seat": seat,
                             "replicate": r, "phase": phase})
    return jobs


def run_jobs(jobs: List[Dict[str, Any]], procs: int, chunk: int = 1,
             progress_every: int = 0, game_timeout: float = 600.0,
             worker=None) -> List[Dict[str, Any]]:
    """One game per forked child.

    A worker pool that plays many games per process cannot be used here. Several public agents
    call the engine's `search_begin` API and do not release every handle, and the engine's handle
    buffer has capacity 7: the eighth allocation in a process throws an *uncaught C++ exception*,
    `std::terminate` fires, and the worker dies by SIGABRT. `multiprocessing.Pool` then waits
    forever for a result that will never arrive — which is exactly how the first run of this
    harness hung with every worker at 0% CPU.

    Forking one child per game makes an engine abort a *recorded outcome* instead of a deadlock,
    and gives every game genuinely fresh engine and agent state. The parent pre-imports the heavy
    modules once, so a fork costs milliseconds rather than the ~3 s a spawn would.
    """
    import tempfile

    worker = worker or _play
    # Pre-import in the parent: children inherit these copy-on-write and start instantly.
    import kaggle_environments  # noqa: F401
    from cg import c023_players  # noqa: F401

    results: List[Dict[str, Any]] = []
    tmpdir = tempfile.mkdtemp(prefix="c023_eval_")
    running: Dict[int, Tuple[Dict[str, Any], str, float]] = {}
    queue = list(jobs)
    t0 = time.time()
    done = 0

    def launch(job: Dict[str, Any]) -> None:
        path = os.path.join(tmpdir, job["job_id"].replace("/", "_").replace(":", "-") + ".json")
        pid = os.fork()
        if pid == 0:  # child
            code = 0
            try:
                rec = worker(job)
                with open(path, "w") as fh:
                    json.dump(rec, fh)
            except BaseException:  # noqa: BLE001
                code = 1
            finally:
                os._exit(code)
        running[pid] = (job, path, time.time())

    while queue or running:
        while queue and len(running) < procs:
            launch(queue.pop())
        # Reap whatever finished; never block forever, so timeouts can be enforced.
        reaped = False
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            pid, status = 0, 0
        if pid and pid in running:
            reaped = True
            job, path, started = running.pop(pid)
            rec: Optional[Dict[str, Any]] = None
            if os.path.exists(path):
                try:
                    rec = json.load(open(path))
                except Exception:
                    rec = None
                os.unlink(path)
            if rec is None:
                rec = {k: job[k] for k in IDENTITY_FIELDS}
                sig = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
                rec.update({"completed": False, "score": None, "reward": None,
                            "seconds": round(time.time() - started, 3),
                            "error": f"engine_process_died signal={sig} status={status}",
                            "process_died": True})
            results.append(rec)
            done += 1
            if progress_every and done % progress_every == 0:
                el = time.time() - t0
                print(f"  {done}/{len(jobs)} games  {el:.0f}s  {done/max(el,1e-9):.1f} g/s",
                      flush=True)
        now = time.time()
        for pid, (job, path, started) in list(running.items()):
            if now - started > game_timeout:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
        if not reaped and running:
            time.sleep(0.005)

    try:
        os.rmdir(tmpdir)
    except OSError:
        pass

    # The invariant the c008/c019 defects broke: every job comes back exactly once, itself.
    got = sorted(r["job_id"] for r in results)
    want = sorted(j["job_id"] for j in jobs)
    assert got == want, f"job identity mismatch: {len(got)} results for {len(want)} jobs"
    return results


def summarize(results: List[Dict[str, Any]], requested: int) -> Dict[str, Any]:
    by_cand: Dict[str, Dict[str, Any]] = {}
    for r in results:
        c = r["candidate_id"]
        d = by_cand.setdefault(c, {"candidate_id": c, "opponents": {}, "seats": {0: [], 1: []},
                                   "errors": 0, "requested": 0, "completed": 0,
                                   "latency_max_ms": 0.0, "latency_p99_ms": 0.0,
                                   "seconds": 0.0, "decisions": 0,
                                   "trivial": 0, "scored_dec": 0, "died": 0})
        d["requested"] += 1
        d["seconds"] += r.get("seconds") or 0.0
        d["decisions"] += r.get("decisions") or 0
        d["trivial"] += r.get("trivial_fallback_decisions") or 0
        d["scored_dec"] += r.get("scored_decisions") or 0
        d["died"] += 1 if r.get("process_died") else 0
        d["latency_max_ms"] = max(d["latency_max_ms"], r.get("latency_max_ms") or 0.0)
        d["latency_p99_ms"] = max(d["latency_p99_ms"], r.get("latency_p99_ms") or 0.0)
        if not r["completed"]:
            d["errors"] += 1
            continue
        d["completed"] += 1
        d["opponents"].setdefault(r["opponent_id"], []).append(r["score"])
        d["seats"][int(r["seat"])].append(r["score"])

    out: Dict[str, Any] = {}
    for c, d in by_cand.items():
        opp_rates = {}
        for o, xs in sorted(d["opponents"].items()):
            opp_rates[o] = {"games": len(xs), "score_rate": round(sum(xs) / len(xs), 4),
                            "wilson95": wilson(sum(xs), len(xs))}
        allx = [x for xs in d["opponents"].values() for x in xs]
        # Field score = the MEAN OF PER-OPPONENT RATES, not the pooled rate: an unbalanced
        # opponent mix must not reweight the field.
        field = round(sum(v["score_rate"] for v in opp_rates.values()) / len(opp_rates), 4) if opp_rates else None
        off = {o: v for o, v in opp_rates.items() if o != c}
        field_off = round(sum(v["score_rate"] for v in off.values()) / len(off), 4) if off else None
        seat_rates = {s: (round(sum(xs) / len(xs), 4) if xs else None) for s, xs in d["seats"].items()}
        out[c] = {
            "candidate_id": c,
            "requested_games": d["requested"], "completed_games": d["completed"],
            "errors": d["errors"],
            "field_score": field,
            # Mirror matches are 0.5 by symmetry and only dilute a field score, so the
            # off-mirror mean is the number the promotion rules use.
            "field_score_off_mirror": field_off,
            "pooled_score_rate": round(sum(allx) / len(allx), 4) if allx else None,
            "pooled_wilson95": wilson(sum(allx), len(allx)) if allx else [None, None],
            "per_opponent": opp_rates,
            "per_seat": {"seat0": seat_rates[0], "seat1": seat_rates[1],
                         "seat0_games": len(d["seats"][0]), "seat1_games": len(d["seats"][1])},
            "latency_p99_ms": round(d["latency_p99_ms"], 4),
            "latency_max_ms": round(d["latency_max_ms"], 4),
            "mean_game_seconds": round(d["seconds"] / max(1, d["requested"]), 4),
            "decisions": d["decisions"],
            "engine_process_deaths": d["died"],
            "trivial_fallback_rate": (round(d["trivial"] / d["scored_dec"], 4)
                                      if d["scored_dec"] else None),
        }
    return out


def write_out(tag: str, jobs: List[Dict[str, Any]], results: List[Dict[str, Any]],
              summary: Dict[str, Any], meta: Dict[str, Any]) -> str:
    d = os.path.join(RAW, tag)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "games.jsonl"), "w") as fh:
        for r in sorted(results, key=lambda x: x["job_id"]):
            fh.write(json.dumps(r) + "\n")
    payload = {"tag": tag, "meta": meta, "requested_games": len(jobs),
               "completed_games": sum(1 for r in results if r["completed"]),
               "errors": sum(1 for r in results if not r["completed"]),
               "summary": summary}
    with open(os.path.join(d, "summary.json"), "w") as fh:
        json.dump(payload, fh, indent=2)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, help="comma-separated player ids")
    ap.add_argument("--opponents", required=True, help="comma-separated player ids")
    ap.add_argument("--games", type=int, default=100, help="games per ordered pair")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--phase", default="dev")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 4))
    ap.add_argument("--skip-self", action="store_true")
    ap.add_argument("--progress", type=int, default=200)
    a = ap.parse_args()

    cands = [x for x in a.candidates.split(",") if x]
    opps = [x for x in a.opponents.split(",") if x]
    jobs = build_jobs(cands, opps, a.games, a.phase, a.skip_self)
    print(f"[{a.tag}] {len(jobs)} games  {len(cands)} candidates x {len(opps)} opponents "
          f"x {a.games}  procs={a.procs}", flush=True)
    t0 = time.time()
    results = run_jobs(jobs, a.procs, progress_every=a.progress)
    el = time.time() - t0
    summary = summarize(results, a.games)
    meta = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": round(el, 1), "procs": a.procs, "phase": a.phase,
            "games_per_pair": a.games, "candidates": cands, "opponents": opps,
            "nproc_machine": os.cpu_count(), "loadavg": os.getloadavg()}
    d = write_out(a.tag, jobs, results, summary, meta)
    print(f"[{a.tag}] done in {el:.0f}s -> {d}", flush=True)
    for c, s in sorted(summary.items(), key=lambda kv: -(kv[1]["field_score"] or 0)):
        per = "  ".join(f"{o}={v['score_rate']:.3f}" for o, v in s["per_opponent"].items())
        print(f"  {c:34s} field={s['field_score']}  n={s['completed_games']}/{s['requested_games']} "
              f"err={s['errors']}  p99={s['latency_p99_ms']}ms | {per}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

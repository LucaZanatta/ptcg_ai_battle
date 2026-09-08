"""c004 competitive gauntlet: freeze candidates, smoke-gate, run the balanced
sequential round-robin, and capture schema-v2 lineage (gzip).

Writes (under --out-dir): candidate_manifest.json, candidate_admission.md,
candidate_freeze_hashes_before/after.json, candidate_smoke_report.json,
gauntlet_plan.json, gauntlet_games.jsonl.gz, pair_stopping_report.json,
reliability_report.json, latency_report.json, fallback_report.json,
run_metadata.json.

Engine RNG is not controlled (std::random_device); seeds/seat schedule are, and
the stochastic candidate is seeded per game.

Usage (from repo root):
  .venv/bin/python tools/run_gauntlet.py --base-seed 90210 --require-clean \
      --out-dir contracts/c004_competitive_baseline_gauntlet/results/artifacts
"""

import argparse
import gzip
import itertools
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.candidates import freeze_hashes, get_candidate_specs, make_agent
from cg.episode_capture import context_name, derive_seed
from cg.episode_schema import (
    classify_terminal, collect_engine_info, collect_environment, collect_git_info,
    final_state_terminal, implementation_sha256, sha256_bytes, source_files_lineage,
)
from cg.gauntlet_stats import seat_balanced_rate, stratified_bootstrap_ci
from cg.safe_policy import MalformedSelection, validate_selection

_IMPL_FILES = ["starter_kit/candidates.py", "starter_kit/gauntlet_stats.py",
               "starter_kit/episode_schema.py", "tools/run_gauntlet.py"]
_BOOT = 2000
_STOP_HI, _STOP_LO = 0.55, 0.45
_MAX_PER_SEAT = 100


class GzWriter:
    def __init__(self, path):
        self._fh = gzip.open(path, "wt", encoding="utf-8")
        self.n = 0

    def write(self, rec):
        self._fh.write(json.dumps(rec) + "\n")
        self.n += 1

    def flush(self):
        self._fh.flush()

    def close(self):
        self._fh.flush()
        self._fh.close()


def _winner_seat(rewards):
    r0, r1 = rewards
    if r0 == r1:
        return None
    return 0 if (r0 or 0) > (r1 or 0) else 1


def play_game(make, writer, *, run_id, game_id, phase, pair_id, seat_ids, seeds, seq, retries=2):
    """Play one game, capture lineage + decisions, return a structured result."""
    from cg.candidates import make_agent as _mk
    stats = {"calls": {0: 0, 1: 0}, "latency_ns": {0: [], 1: []},
             "invalid": {0: 0, 1: 0}, "fallback": {0: 0, 1: 0}, "didx": [0]}
    agents = {seat: _mk(cid, _REPO_ROOT, seed=seeds.get(seat)) for seat, cid in seat_ids.items()}
    deck_ids = {seat: agents[seat].configuration["deck_id"] for seat in (0, 1)}

    writer.write({"schema_version": 2, "record_type": "game_start", "run_id": run_id,
                  "game_id": game_id, "phase": phase, "pair_id": pair_id,
                  "seat_candidate_ids": {str(s): seat_ids[s] for s in (0, 1)},
                  "seat_deck_ids": {str(s): deck_ids[s] for s in (0, 1)},
                  "seed": {"seat0_seed": seeds.get(0), "seat1_seed": seeds.get(1),
                           "engine_rng_controlled": False}})

    def wrap(seat):
        agent = agents[seat]
        cid = seat_ids[seat]

        def wrapped(obs):
            select = obs["select"]
            t0 = time.perf_counter_ns()
            result = agent(obs)
            dt = time.perf_counter_ns() - t0
            stats["calls"][seat] += 1
            stats["latency_ns"][seat].append(dt)
            if select is None:
                return result
            prov = agent.classify_decision(obs, result)
            if prov["used_fallback"]:
                stats["fallback"][seat] += 1
            n = len(select.get("option", []))
            lo, mx = select.get("minCount"), select.get("maxCount")
            vstatus = "valid"
            try:
                validate_selection(list(result), n, lo, mx)
            except MalformedSelection as exc:
                vstatus = f"invalid: {exc}"
                stats["invalid"][seat] += 1
            writer.write({"schema_version": 2, "record_type": "decision", "run_id": run_id,
                          "game_id": game_id, "phase": phase, "seat": seat, "candidate_id": cid,
                          "decision_index": stats["didx"][0], "select_context": select.get("context"),
                          "context_name": context_name(select.get("context")), "min_count": lo,
                          "max_count": mx, "legal_option_count": n, "option": select.get("option"),
                          "selected_indices": list(result), "policy_latency_ns": dt,
                          "decision_source": prov["decision_source"], "used_fallback": prov["used_fallback"],
                          "fallback_reason": prov["fallback_reason"], "validation_status": vstatus})
            stats["didx"][0] += 1
            return result

        return wrapped

    exception = None
    env = None
    for _attempt in range(retries + 1):
        exception = None
        try:
            env = make("cabt")
            env.run([wrap(0), wrap(1)])
            break
        except Exception as exc:  # environment-level exception -> retry
            exception = repr(exc)
    t_dur = 0.0

    if exception is not None or env is None:
        statuses, rewards, err = ["ERROR", "ERROR"], [None, None], exception
        terminal = classify_terminal(statuses, rewards, exception=exception)
    else:
        statuses, rewards, err = final_state_terminal(env)
        terminal = classify_terminal(statuses, rewards, error=err)

    wseat = _winner_seat(rewards)
    winner_candidate = ("draw" if wseat is None else seat_ids[wseat]) if terminal["terminal_type"] != "environment_error" else "env_error"
    reliability = {}
    for seat in (0, 1):
        s = statuses[seat]
        reliability[str(seat)] = {
            "candidate_id": seat_ids[seat],
            "invalid_selections": stats["invalid"][seat],
            "agent_error": bool(s in ("ERROR", "INVALID")),
            "timeout": bool(s == "TIMEOUT"),
        }
    writer.write({"schema_version": 2, "record_type": "game_terminal", "run_id": run_id,
                  "game_id": game_id, "phase": phase, "pair_id": pair_id,
                  "seat_candidate_ids": {str(s): seat_ids[s] for s in (0, 1)},
                  **terminal, "winner_seat": wseat, "winner_candidate": winner_candidate,
                  "reliability": reliability, "env_exception": exception,
                  "decisions_by_seat": {str(s): stats["calls"][s] for s in (0, 1)},
                  "latency_ns_by_seat": {str(s): stats["latency_ns"][s] for s in (0, 1)},
                  "fallback_by_seat": {str(s): stats["fallback"][s] for s in (0, 1)}})
    writer.flush()
    return {"winner_seat": wseat, "winner_candidate": winner_candidate, "terminal_type": terminal["terminal_type"],
            "reliability": reliability, "stats": stats, "env_exception": exception,
            "completed": statuses == ["DONE", "DONE"]}


def a_result(res, a_seat):
    """A's game result (1 win / 0.5 draw / 0 loss) given which seat A occupied."""
    if res["winner_seat"] is None:
        return 0.5
    return 1.0 if res["winner_seat"] == a_seat else 0.0


def run(args):
    from kaggle_environments import make
    repo_root = _REPO_ROOT
    os.makedirs(args.out_dir, exist_ok=True)
    git = collect_git_info(repo_root)
    if args.require_clean and git.get("dirty"):
        print("REFUSING: dirty tracked tree; commit source before the gauntlet.", file=sys.stderr)
        return 2

    specs = get_candidate_specs(repo_root)
    runnable = [s for s in specs if s["runnable"]]
    created = datetime.now(timezone.utc).isoformat()
    run_id = "gauntlet_" + sha256_bytes(f"{git['commit']}|{created}|{args.base_seed}".encode())[:16]
    command = f".venv/bin/python tools/run_gauntlet.py --base-seed {args.base_seed} --out-dir {os.path.relpath(args.out_dir, repo_root)}"
    run_meta = {
        "schema_version": 2, "record_type": "run_metadata", "run_id": run_id, "created_at_utc": created,
        "git": git, "capture": {"implementation_sha256": implementation_sha256(_IMPL_FILES, repo_root),
                                 "implementation_source_files": source_files_lineage(_IMPL_FILES, repo_root),
                                 "command": command, "compression": "gzip"},
        "environment": collect_environment(),
        "engine": collect_engine_info(os.path.join(repo_root, "starter_kit", "libcg.so"), repo_root),
        "candidates": {s["candidate_id"]: {k: s[k] for k in ("candidate_id", "candidate_version",
                       "policy_type", "deterministic", "deck_name", "attribution", "agent_source",
                       "deck_source")} | {"deck_id": s["deck"]["deck_id"]} for s in runnable},
        "base_seed": args.base_seed,
    }
    # manifest + freeze-before
    json.dump({"run_id": run_id, "candidates": [
        {k: s[k] for k in ("candidate_id", "candidate_version", "policy_type", "deterministic",
                           "deck_name", "attribution", "runnable", "agent_source", "deck_source")}
        | {"deck": s["deck"]} for s in specs]},
        open(os.path.join(args.out_dir, "candidate_manifest.json"), "w"), indent=2)
    freeze_before = freeze_hashes(repo_root)
    json.dump(freeze_before, open(os.path.join(args.out_dir, "candidate_freeze_hashes_before.json"), "w"), indent=2)
    json.dump(run_meta, open(os.path.join(args.out_dir, "run_metadata.json"), "w"), indent=2)

    writer = GzWriter(os.path.join(args.out_dir, "gauntlet_games.jsonl.gz"))
    writer.write(run_meta)
    gseq = [0]

    def next_seed(seat_ids):
        # seed only stochastic candidates; unique per game/seat
        seeds = {}
        for seat, cid in seat_ids.items():
            spec = next(s for s in specs if s["candidate_id"] == cid)
            if not spec["deterministic"]:
                seeds[seat] = derive_seed(args.base_seed, gseq[0] * 2 + seat)
        return seeds

    # ---- Phase 2: smoke gate (10 games/candidate: 5 seat0, 5 seat1, >=2 opponents) ----
    smoke = {}
    cand_ids = [s["candidate_id"] for s in runnable]
    for cid in cand_ids:
        opponents = [o for o in cand_ids if o != cid][:2] or [cid]
        rows = {"seat0": [], "seat1": [], "reliability_defects": 0, "invalid": 0,
                "agent_errors": 0, "timeouts": 0, "latency_ns": [], "completed": 0, "games": 0}
        plan = ([(0, opponents[i % len(opponents)]) for i in range(5)]
                + [(1, opponents[i % len(opponents)]) for i in range(5)])
        for seat, opp in plan:
            gseq[0] += 1
            seat_ids = {seat: cid, 1 - seat: opp}
            res = play_game(make, writer, run_id=run_id, game_id=f"smoke-{cid}-{gseq[0]:04d}",
                            phase="smoke", pair_id=f"{cid}|{opp}", seat_ids=seat_ids,
                            seeds=next_seed(seat_ids), seq=gseq)
            rows["games"] += 1
            if res["completed"]:
                rows["completed"] += 1
            rows["latency_ns"].extend(res["stats"]["latency_ns"][seat])
            rel = res["reliability"][str(seat)]
            rows["invalid"] += rel["invalid_selections"]
            rows["agent_errors"] += int(rel["agent_error"])
            rows["timeouts"] += int(rel["timeout"])
            (rows["seat0"] if seat == 0 else rows["seat1"]).append(res["winner_seat"] == seat)
        rows["reliability_defects"] = rows["invalid"] + rows["agent_errors"] + rows["timeouts"]
        rows["passed"] = (rows["completed"] == rows["games"] and rows["reliability_defects"] == 0)
        smoke[cid] = rows

    admitted = [c for c in cand_ids if smoke[c]["passed"]]
    json.dump({"candidates": {c: {k: v for k, v in smoke[c].items() if k != "latency_ns"}
                              | {"latency_calls": len(smoke[c]["latency_ns"])} for c in smoke},
               "admitted": admitted},
              open(os.path.join(args.out_dir, "candidate_smoke_report.json"), "w"), indent=2)

    # ---- Phase 3: sequential balanced round-robin over admitted candidates ----
    plan_pairs = list(itertools.combinations(sorted(admitted), 2))
    stopping = []
    boot_rng = random.Random(args.base_seed ^ 0x5EED)
    for (A, B) in plan_pairs:
        a_seat0, a_seat1 = [], []  # A's results as seat0 / seat1
        pair_defects = {A: 0, B: 0}
        reason = None
        per_seat = 0
        while True:
            batch = 20 if per_seat == 0 else 10
            for _ in range(batch):  # A as seat 0
                gseq[0] += 1
                sids = {0: A, 1: B}
                res = play_game(make, writer, run_id=run_id, game_id=f"g-{A}-{B}-{gseq[0]:05d}",
                                phase="gauntlet", pair_id=f"{A}|{B}", seat_ids=sids,
                                seeds=next_seed(sids), seq=gseq)
                a_seat0.append(a_result(res, 0))
                for s in (0, 1):
                    r = res["reliability"][str(s)]
                    pair_defects[sids[s]] += r["invalid_selections"] + int(r["agent_error"]) + int(r["timeout"])
            for _ in range(batch):  # A as seat 1
                gseq[0] += 1
                sids = {0: B, 1: A}
                res = play_game(make, writer, run_id=run_id, game_id=f"g-{B}-{A}-{gseq[0]:05d}",
                                phase="gauntlet", pair_id=f"{A}|{B}", seat_ids=sids,
                                seeds=next_seed(sids), seq=gseq)
                a_seat1.append(a_result(res, 1))
                for s in (0, 1):
                    r = res["reliability"][str(s)]
                    pair_defects[sids[s]] += r["invalid_selections"] + int(r["agent_error"]) + int(r["timeout"])
            per_seat += batch
            lo, hi, point = stratified_bootstrap_ci(a_seat0, a_seat1, n_boot=_BOOT, rng=boot_rng)
            if lo > _STOP_HI:
                reason = "ci_above_0.55"
                break
            if hi < _STOP_LO:
                reason = "ci_below_0.45"
                break
            if per_seat >= _MAX_PER_SEAT:
                reason = "max_games_reached"
                break
        stopping.append({"pair": [A, B], "games_per_seat": per_seat, "total_games": per_seat * 2,
                         "a_seat0_rate": seat_balanced_rate(a_seat0, []),
                         "a_seat1_rate": seat_balanced_rate([], a_seat1),
                         "seat_balanced_a_rate": point, "ci95": [lo, hi], "stopping_reason": reason,
                         "reliability_defects": pair_defects, "interval_method": "stratified_percentile_bootstrap_2000"})

    writer.close()
    json.dump({"run_id": run_id, "admitted": admitted, "pairs": [list(p) for p in plan_pairs],
               "batching": {"initial_per_seat": 20, "extend_per_seat": 10, "max_per_seat": _MAX_PER_SEAT,
                            "stop_hi": _STOP_HI, "stop_lo": _STOP_LO, "bootstrap": _BOOT},
               "seat_orders": "both (A-seat0-vs-B and B-seat0-vs-A)"},
              open(os.path.join(args.out_dir, "gauntlet_plan.json"), "w"), indent=2)
    json.dump({"pairs": stopping}, open(os.path.join(args.out_dir, "pair_stopping_report.json"), "w"), indent=2)

    # freeze-after (must equal before)
    freeze_after = freeze_hashes(repo_root)
    json.dump(freeze_after, open(os.path.join(args.out_dir, "candidate_freeze_hashes_after.json"), "w"), indent=2)

    total_gauntlet = sum(p["total_games"] for p in stopping)
    total_smoke = sum(smoke[c]["games"] for c in smoke)
    summary = {"run_id": run_id, "admitted": admitted, "smoke_games": total_smoke,
               "gauntlet_games": total_gauntlet, "records_written": writer.n,
               "freeze_stable": freeze_before == freeze_after, "git_dirty": git.get("dirty")}
    print(json.dumps(summary, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="c004 competitive gauntlet")
    parser.add_argument("--base-seed", type=int, default=90210)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--require-clean", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

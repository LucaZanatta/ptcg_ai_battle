"""c005 strategic teacher gauntlet: freeze, smoke-gate, and run the balanced
sequential round-robin over LOADED strategic teachers (fresh instance per game
per seat), capturing schema-v2 lineage (gzip).

Reuses cg.gauntlet_stats (stratified-bootstrap stopping). Terminals are written
in the c004-compatible shape so tools/analyze_gauntlet-style aggregation applies.

Usage (from repo root):
  .venv/bin/python tools/run_strategic_gauntlet.py --base-seed 5150 --require-clean \
      --sources <teacher_sources> --out-dir <artifacts>
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

from cg.episode_capture import context_name
from cg.episode_schema import (
    classify_terminal, collect_engine_info, collect_environment, collect_git_info,
    final_state_terminal, implementation_sha256, sha256_bytes, source_files_lineage,
)
from cg.gauntlet_stats import seat_balanced_rate, stratified_bootstrap_ci
from cg.safe_policy import MalformedSelection, validate_selection
from cg.teachers import TEACHERS, agent_lineage, canonical_deck_record, freeze_hashes, make_fresh

_IMPL = ["starter_kit/teachers.py", "starter_kit/gauntlet_stats.py", "tools/run_strategic_gauntlet.py"]
_BOOT, _HI, _LO, _MAXPS = 2000, 0.55, 0.45, 100


class GzWriter:
    def __init__(self, path):
        self._fh = gzip.open(path, "wt", encoding="utf-8"); self.n = 0

    def write(self, r):
        self._fh.write(json.dumps(r) + "\n"); self.n += 1

    def flush(self):
        self._fh.flush()

    def close(self):
        self._fh.flush(); self._fh.close()


def _winner_seat(rewards):
    r0, r1 = rewards
    return None if r0 == r1 else (0 if (r0 or 0) > (r1 or 0) else 1)


def play_game(make, writer, sources, *, run_id, game_id, phase, pair_id, seat_ids):
    """Fresh teacher instances per seat; capture light decisions + terminal."""
    agents = {s: make_fresh(cid, sources) for s, cid in seat_ids.items()}
    deck_ids = {s: canonical_deck_record(seat_ids[s], sources, _REPO_ROOT)["deck_id"] for s in (0, 1)}
    stats = {"calls": {0: 0, 1: 0}, "lat": {0: [], 1: []}, "invalid": {0: 0, 1: 0},
             "fallback": {0: 0, 1: 0}, "didx": [0], "ctx": {0: {}, 1: {}}}
    writer.write({"schema_version": 2, "record_type": "game_start", "run_id": run_id, "game_id": game_id,
                  "phase": phase, "pair_id": pair_id,
                  "seat_candidate_ids": {str(s): seat_ids[s] for s in (0, 1)},
                  "seat_deck_ids": {str(s): deck_ids[s] for s in (0, 1)},
                  "seed": {"engine_rng_controlled": False}})

    def wrap(seat):
        ag = agents[seat]; cid = seat_ids[seat]

        def w(obs):
            sel = obs["select"]
            t0 = time.perf_counter_ns()
            res = ag(obs)
            dt = time.perf_counter_ns() - t0
            stats["calls"][seat] += 1; stats["lat"][seat].append(dt)
            if sel is None:
                return res
            prov = ag.classify_decision(obs, res)
            if prov["used_fallback"]:
                stats["fallback"][seat] += 1
            n = len(sel.get("option", [])); lo, mx = sel.get("minCount"), sel.get("maxCount")
            vst = "valid"
            try:
                validate_selection(list(res), n, lo, mx)
            except MalformedSelection as e:
                vst = f"invalid: {e}"; stats["invalid"][seat] += 1
            cv = sel.get("context")
            stats["ctx"][seat][cv] = stats["ctx"][seat].get(cv, 0) + 1
            writer.write({"schema_version": 2, "record_type": "decision", "run_id": run_id,
                          "game_id": game_id, "phase": phase, "seat": seat, "candidate_id": cid,
                          "decision_index": stats["didx"][0], "select_context": cv,
                          "context_name": context_name(cv), "min_count": lo, "max_count": mx,
                          "legal_option_count": n, "option_types": [o.get("type") for o in sel.get("option", [])],
                          "selected_indices": list(res), "policy_latency_ns": dt,
                          "decision_source": prov["decision_source"], "used_fallback": prov["used_fallback"],
                          "validation_status": vst})
            stats["didx"][0] += 1
            return res
        return w

    exc = None; env = None
    try:
        env = make("cabt"); env.run([wrap(0), wrap(1)])
    except Exception as e:  # pragma: no cover
        exc = repr(e)
    if exc is not None or env is None:
        statuses, rewards, err = ["ERROR", "ERROR"], [None, None], exc
        term = classify_terminal(statuses, rewards, exception=exc)
    else:
        statuses, rewards, err = final_state_terminal(env)
        term = classify_terminal(statuses, rewards, error=err)
    wseat = _winner_seat(rewards)
    winner = "draw" if wseat is None else seat_ids[wseat]
    rel = {str(s): {"candidate_id": seat_ids[s], "invalid_selections": stats["invalid"][s],
                    "agent_error": bool(statuses[s] in ("ERROR", "INVALID")),
                    "timeout": bool(statuses[s] == "TIMEOUT")} for s in (0, 1)}
    writer.write({"schema_version": 2, "record_type": "game_terminal", "run_id": run_id, "game_id": game_id,
                  "phase": phase, "pair_id": pair_id,
                  "seat_candidate_ids": {str(s): seat_ids[s] for s in (0, 1)}, **term,
                  "winner_seat": wseat, "winner_candidate": winner, "reliability": rel,
                  "env_exception": exc, "decisions_by_seat": {str(s): stats["calls"][s] for s in (0, 1)},
                  "latency_ns_by_seat": {str(s): stats["lat"][s] for s in (0, 1)},
                  "fallback_by_seat": {str(s): stats["fallback"][s] for s in (0, 1)},
                  "context_counts_by_seat": {str(s): {str(k): v for k, v in stats["ctx"][s].items()} for s in (0, 1)},
                  "game_length_steps": (len(env.steps) if env is not None else None)})
    writer.flush()
    return {"winner_seat": wseat, "winner_candidate": winner, "reliability": rel,
            "completed": statuses == ["DONE", "DONE"], "calls": stats["calls"]}


def a_result(res, a_seat):
    if res["winner_seat"] is None:
        return 0.5
    return 1.0 if res["winner_seat"] == a_seat else 0.0


def run(args):
    from kaggle_environments import make
    os.makedirs(args.out_dir, exist_ok=True)
    git = collect_git_info(_REPO_ROOT)
    if args.require_clean and git.get("dirty"):
        print("REFUSING: dirty tracked tree.", file=sys.stderr); return 2
    teacher_ids = list(TEACHERS)
    created = datetime.now(timezone.utc).isoformat()
    run_id = "strat_" + sha256_bytes(f"{git['commit']}|{created}|{args.base_seed}".encode())[:16]
    run_meta = {"schema_version": 2, "record_type": "run_metadata", "run_id": run_id, "created_at_utc": created,
                "git": git, "capture": {"implementation_sha256": implementation_sha256(_IMPL, _REPO_ROOT),
                                        "implementation_source_files": source_files_lineage(_IMPL, _REPO_ROOT),
                                        "command": f".venv/bin/python tools/run_strategic_gauntlet.py --base-seed {args.base_seed}",
                                        "compression": "gzip"},
                "environment": collect_environment(),
                "engine": collect_engine_info(os.path.join(_REPO_ROOT, "starter_kit", "libcg.so"), _REPO_ROOT),
                "teachers": {c: {**{k: TEACHERS[c][k] for k in ("display_name", "archetype", "policy_type",
                             "reuse_classification", "submission_eligible", "source_reference")},
                             "agent": agent_lineage(c, args.sources, _REPO_ROOT),
                             "deck": canonical_deck_record(c, args.sources, _REPO_ROOT)} for c in teacher_ids},
                "base_seed": args.base_seed}
    json.dump(run_meta, open(os.path.join(args.out_dir, "strategic_run_metadata.json"), "w"), indent=2)
    fz_before = freeze_hashes(args.sources, _REPO_ROOT)
    json.dump(fz_before, open(os.path.join(args.out_dir, "candidate_freeze_before.json"), "w"), indent=2)

    writer = GzWriter(os.path.join(args.out_dir, "strategic_gauntlet_games.jsonl.gz"))
    writer.write(run_meta)

    # smoke gate
    smoke = {}
    for cid in teacher_ids:
        opps = [o for o in teacher_ids if o != cid][:2]
        rows = {"seat0": 0, "seat1": 0, "games": 0, "completed": 0, "invalid": 0,
                "agent_errors": 0, "timeouts": 0, "latency_ns": 0}
        plan = [(0, opps[i % len(opps)]) for i in range(10)] + [(1, opps[i % len(opps)]) for i in range(10)]
        for seat, opp in plan:
            res = play_game(make, writer, args.sources, run_id=run_id,
                            game_id=f"smoke-{cid}-{rows['games']:03d}", phase="smoke",
                            pair_id=f"{cid}|{opp}", seat_ids={seat: cid, 1 - seat: opp})
            rows["games"] += 1
            rows["completed"] += int(res["completed"])
            r = res["reliability"][str(seat)]
            rows["invalid"] += r["invalid_selections"]; rows["agent_errors"] += int(r["agent_error"])
            rows["timeouts"] += int(r["timeout"]); rows["latency_ns"] += res["calls"][seat]
        rows["defects"] = rows["invalid"] + rows["agent_errors"] + rows["timeouts"]
        rows["passed"] = rows["completed"] == rows["games"] and rows["defects"] == 0
        smoke[cid] = rows
    admitted = [c for c in teacher_ids if smoke[c]["passed"]]
    json.dump({"candidates": smoke, "admitted": admitted},
              open(os.path.join(args.out_dir, "strategic_smoke_report.json"), "w"), indent=2)

    # sequential balanced round-robin over admitted
    boot_rng = random.Random(args.base_seed ^ 0x1234)
    stopping = []
    for (A, B) in itertools.combinations(sorted(admitted), 2):
        a0, a1 = [], []; ps = 0; reason = None
        while True:
            batch = 20 if ps == 0 else 10
            for _ in range(batch):
                res = play_game(make, writer, args.sources, run_id=run_id,
                                game_id=f"g-{A}-{B}-{len(a0)+len(a1):05d}", phase="gauntlet",
                                pair_id=f"{A}|{B}", seat_ids={0: A, 1: B})
                a0.append(a_result(res, 0))
            for _ in range(batch):
                res = play_game(make, writer, args.sources, run_id=run_id,
                                game_id=f"g-{B}-{A}-{len(a0)+len(a1):05d}", phase="gauntlet",
                                pair_id=f"{A}|{B}", seat_ids={0: B, 1: A})
                a1.append(a_result(res, 1))
            ps += batch
            lo, hi, point = stratified_bootstrap_ci(a0, a1, n_boot=_BOOT, rng=boot_rng)
            if lo > _HI:
                reason = "ci_above_0.55"; break
            if hi < _LO:
                reason = "ci_below_0.45"; break
            if ps >= _MAXPS:
                reason = "max_games_reached"; break
        stopping.append({"pair": [A, B], "games_per_seat": ps, "total_games": ps * 2,
                         "seat_balanced_a_rate": point, "ci95": [lo, hi], "stopping_reason": reason,
                         "interval_method": "stratified_percentile_bootstrap_2000"})
    writer.close()
    json.dump({"run_id": run_id, "admitted": admitted, "pairs": [s["pair"] for s in stopping],
               "batching": {"initial_per_seat": 20, "extend_per_seat": 10, "max_per_seat": _MAXPS}},
              open(os.path.join(args.out_dir, "strategic_gauntlet_plan.json"), "w"), indent=2)
    json.dump({"pairs": stopping}, open(os.path.join(args.out_dir, "strategic_pair_stopping.json"), "w"), indent=2)
    fz_after = freeze_hashes(args.sources, _REPO_ROOT)
    json.dump(fz_after, open(os.path.join(args.out_dir, "candidate_freeze_after.json"), "w"), indent=2)

    summ = {"run_id": run_id, "admitted": admitted,
            "smoke_games": sum(smoke[c]["games"] for c in smoke),
            "gauntlet_games": sum(s["total_games"] for s in stopping),
            "records": writer.n, "freeze_stable": fz_before == fz_after, "git_dirty": git.get("dirty")}
    print(json.dumps(summ, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--base-seed", type=int, default=5150)
    p.add_argument("--sources", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--require-clean", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

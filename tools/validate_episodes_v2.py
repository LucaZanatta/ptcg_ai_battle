"""Streaming validator + semantic replay for schema-v2 episode captures.

Works on .jsonl and .jsonl.gz (streaming; no full-file load). Performs:
- structural/ordering validation (run_metadata -> game_start -> contiguous
  decisions -> game_terminal); unique record_ids within the run;
- cross-field validation (§7.9): top-level select_context/min/max/option-count
  agree with observation.select; selected indices satisfy bounds and refer to
  available options; terminal decision counts match observed decisions;
- **true semantic replay** (§7.8/AC-04): for each safe-agent decision, convert
  the serialized observation via to_observation_class AND invoke the actual safe
  agent on it, comparing the returned indices to the recorded action;
- context and latency reports.

Emits JSON reports and exits nonzero on any validation failure or replay mismatch.

Usage (from repo root):
  .venv/bin/python tools/validate_episodes_v2.py <episodes.jsonl|.gz> \
     --validation-report ... --semantic-report ... --context-report ... --latency-report ...
"""

import argparse
import json
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.api import SelectContext, to_observation_class
from cg.episode_compat import read_records
from cg.replay_registry import (
    OK as REPLAY_OK, STOCHASTIC as REPLAY_STOCHASTIC, build_registry, resolve as replay_resolve,
)

_RUN_META_REQUIRED = ["run_id", "created_at_utc", "git", "capture", "environment",
                      "engine", "agents", "decks"]
_AGENT_LINEAGE_REQUIRED = ["agent_id", "agent_version", "policy_type", "source_files",
                           "configuration"]


def _pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return round(s[0], 6)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(s[int(k)], 6)
    return round(s[lo] * (hi - k) + s[hi] * (k - lo), 6)


def _ctx_name(v):
    try:
        return SelectContext(v).name
    except (ValueError, TypeError):
        return f"UNKNOWN_{v}"


def validate(path, run_semantic=True, registry=None):
    if registry is None:
        registry = build_registry(_REPO_ROOT)
    errors = []
    seen_ids = set()
    open_game = None
    run_id = None
    run_meta_seen = False
    run_agents = {}
    decisions = 0
    terminals = []
    terminal_types = {}
    replay = {"checked": 0, "convert_ok": 0, "matches": 0, "mismatches": [],
              "stochastic_skipped": 0, "unavailable": 0}
    per_ctx = {}
    all_latency_ms = []
    seat_counts = {}

    def err(line_no, msg):
        errors.append({"line": line_no, "message": msg})

    for line_no, ver, rec in read_records(path):
        rt = rec.get("record_type")
        rid = rec.get("record_id")
        if rid is not None:
            if rid in seen_ids:
                err(line_no, f"duplicate record_id {rid}")
            seen_ids.add(rid)

        if rt == "run_metadata":
            run_meta_seen = True
            run_id = rec.get("run_id")
            for f in _RUN_META_REQUIRED:
                if not rec.get(f):
                    err(line_no, f"run_metadata missing/empty field: {f}")
            run_agents = rec.get("agents") or {}
            for aid, lin in run_agents.items():
                missing = [k for k in _AGENT_LINEAGE_REQUIRED if k not in (lin or {})]
                if missing:
                    err(line_no, f"agent '{aid}' lineage missing fields: {missing}")
            continue

        if rt == "game_start":
            if open_game is not None:
                err(line_no, f"game_start while game {open_game['game_id']} open")
            if "game_seed" in rec:
                err(line_no, "schema-v2 game_start must not contain ambiguous game_seed")
            if not rec.get("seed") or rec["seed"].get("engine_rng_controlled") is not False:
                err(line_no, "game_start seed block missing or engine_rng_controlled != false")
            # every seat's agent must have serialized lineage in run_metadata.agents
            for seat, aid in (rec.get("seat_agent_ids") or {}).items():
                if run_agents and aid not in run_agents:
                    err(line_no, f"seat {seat} agent_id '{aid}' has no lineage in run_metadata.agents")
            open_game = {"game_id": rec.get("game_id"), "next": 0, "by_player": {}, "line": line_no}
            continue

        if rt == "decision":
            decisions += 1
            if "game_seed" in rec:
                err(line_no, "schema-v2 decision must not contain ambiguous game_seed")
            if open_game is None:
                err(line_no, "decision outside any game")
                continue
            if rec.get("decision_index") != open_game["next"]:
                err(line_no, f"decision_index {rec.get('decision_index')} != {open_game['next']}")
            open_game["next"] += 1
            p = rec.get("player_index")
            open_game["by_player"][p] = open_game["by_player"].get(p, 0) + 1
            # provenance presence
            for f in ("decision_source", "used_fallback", "fallback_reason", "agent_id"):
                if f not in rec:
                    err(line_no, f"decision missing provenance field {f}")
            # cross-field vs observation.select
            obs = rec.get("observation") or {}
            sel = obs.get("select")
            if not isinstance(sel, dict):
                err(line_no, "decision observation.select missing")
            else:
                if rec.get("select_context") != sel.get("context"):
                    err(line_no, "select_context != observation.select.context")
                if rec.get("min_count") != sel.get("minCount") or rec.get("max_count") != sel.get("maxCount"):
                    err(line_no, "min/max_count != observation.select bounds")
                if rec.get("legal_option_count") != len(sel.get("option") or []):
                    err(line_no, "legal_option_count != len(observation.select.option)")
                if rec.get("legal_option_metadata") != sel.get("option"):
                    # c004 amendment #2: duplicated metadata must equal the source
                    err(line_no, "legal_option_metadata != observation.select.option")
                n = len(sel.get("option") or [])
                lo, hi = sel.get("minCount"), sel.get("maxCount")
                seli = rec.get("selected_indices") or []
                if len(set(seli)) != len(seli):
                    err(line_no, "duplicate selected_indices")
                if not (lo <= len(seli) <= hi):
                    err(line_no, f"selection count {len(seli)} outside [{lo},{hi}]")
                for i in seli:
                    if not (isinstance(i, int) and 0 <= i < n):
                        err(line_no, f"selected index {i} out of range/option [0,{n})")
            # context + latency accumulation
            cv = rec.get("select_context")
            seat = rec.get("seat")
            seat_counts[seat] = seat_counts.get(seat, 0) + 1
            st = per_ctx.setdefault(cv, {"count": 0, "by_seat": {}, "fallback": 0,
                                         "invalid": 0, "lat_ms": []})
            st["count"] += 1
            st["by_seat"][seat] = st["by_seat"].get(seat, 0) + 1
            if rec.get("used_fallback"):
                st["fallback"] += 1
            if not str(rec.get("validation_status", "valid")).startswith("valid"):
                st["invalid"] += 1
            lat = rec.get("policy_latency_ns")
            if isinstance(lat, (int, float)):
                st["lat_ms"].append(lat / 1e6)
                all_latency_ms.append(lat / 1e6)
            # semantic replay — c004 amendment #3: verify recorded agent identity,
            # version and source hashes against the current registry BEFORE invoking.
            if run_semantic and rec.get("agent_id"):
                status, fn = replay_resolve(registry, rec["agent_id"], run_agents.get(rec["agent_id"]))
                if status == REPLAY_STOCHASTIC:
                    replay["stochastic_skipped"] += 1
                elif status != REPLAY_OK:
                    replay["unavailable"] += 1  # hash mismatch / unregistered -> not invoked
                else:
                    replay["checked"] += 1
                    try:
                        to_observation_class(obs)  # conversion test (§7.8 step 3)
                        replay["convert_ok"] += 1
                    except Exception as exc:
                        err(line_no, f"to_observation_class failed: {exc!r}")
                        replay["mismatches"].append({"line": line_no, "reason": "convert_failed"})
                        continue
                    try:
                        got = fn(obs)  # ACTUAL invocation of the verified current agent
                    except Exception as exc:
                        err(line_no, f"agent invocation failed: {exc!r}")
                        replay["mismatches"].append({"line": line_no, "reason": "invoke_failed"})
                        continue
                    if got == rec.get("selected_indices"):
                        replay["matches"] += 1
                    else:
                        replay["mismatches"].append({
                            "line": line_no, "run_id": rec.get("run_id"), "game_id": rec.get("game_id"),
                            "decision_index": rec.get("decision_index"), "context": _ctx_name(cv),
                            "record_id": rec.get("record_id"), "recorded": rec.get("selected_indices"),
                            "replayed": got})
                        err(line_no, "semantic replay mismatch")
            continue

        if rt == "game_terminal":
            if open_game is None:
                err(line_no, "game_terminal with no open game")
                continue
            declared = {int(k): v for k, v in (rec.get("decisions_by_player") or {}).items()}
            if declared != open_game["by_player"]:
                err(line_no, f"terminal decisions_by_player {declared} != observed {open_game['by_player']}")
            tt = rec.get("terminal_type")
            if not tt:
                err(line_no, "game_terminal missing terminal_type")
            terminal_types[tt] = terminal_types.get(tt, 0) + 1
            terminals.append({"game_id": rec.get("game_id"), "terminal_type": tt,
                              "winner": rec.get("winner")})
            open_game = None
            continue

        err(line_no, f"unknown record_type {rt!r}")

    if open_game is not None:
        err(open_game["line"], f"game {open_game['game_id']} never terminated")
    if not run_meta_seen:
        err(0, "no run_metadata record found")

    valid = len(errors) == 0
    replay_ok = (replay["checked"] > 0 and len(replay["mismatches"]) == 0
                 and replay["matches"] == replay["checked"])
    return {
        "validation": {
            "path": path, "run_id": run_id, "games": len(terminals), "decisions": decisions,
            "terminals": len(terminals), "terminal_types": terminal_types,
            "unique_record_ids": len(seen_ids), "error_count": len(errors),
            "errors": errors[:200], "valid": valid,
        },
        "semantic": {
            "safe_decisions_checked": replay["checked"], "convert_ok": replay["convert_ok"],
            "matches": replay["matches"], "mismatch_count": len(replay["mismatches"]),
            "stochastic_skipped": replay["stochastic_skipped"], "replay_unavailable": replay["unavailable"],
            "mismatches": replay["mismatches"][:50], "all_reproduced": replay_ok,
            "method": "registry-verified (agent_id+version+source-hash) then to_observation_class(obs) + agent(obs); serialized observation, not duplicated bounds",
        },
        "context": _context_report(per_ctx, seat_counts, decisions),
        "latency": {
            "count": len(all_latency_ms),
            "overall_ms": {"p50": _pct(all_latency_ms, 50), "p95": _pct(all_latency_ms, 95),
                           "p99": _pct(all_latency_ms, 99),
                           "max": (round(max(all_latency_ms), 6) if all_latency_ms else None)},
            "per_context_ms": {_ctx_name(cv): {"count": len(st["lat_ms"]),
                                               "p50": _pct(st["lat_ms"], 50), "p95": _pct(st["lat_ms"], 95),
                                               "p99": _pct(st["lat_ms"], 99),
                                               "max": (round(max(st["lat_ms"]), 6) if st["lat_ms"] else None)}
                               for cv, st in sorted(per_ctx.items(), key=lambda x: (x[0] is None, x[0]))},
        },
        "ok": valid and replay_ok,
    }


def _context_report(per_ctx, seat_counts, total_decisions):
    members = list(SelectContext)
    observed = set(per_ctx)
    rows = []
    for c in members:
        v = int(c)
        st = per_ctx.get(v)
        rows.append(_row(c.name, v, st, v in observed, True))
    for v in sorted(x for x in observed if x not in {int(c) for c in members}):
        rows.append(_row(_ctx_name(v), v, per_ctx[v], True, False))
    return {
        "enum_contexts_total": len(members),
        "runtime_contexts_observed": len(observed & {int(c) for c in members}),
        "total_decisions": total_decisions,
        "decisions_by_seat": {str(k): v for k, v in sorted(seat_counts.items(), key=lambda x: (x[0] is None, x[0]))},
        "contexts": rows,
        "not_observed": [c.name for c in members if int(c) not in observed],
    }


def _row(name, value, st, observed, in_enum):
    if st:
        return {"name": name, "value": value, "in_enum": in_enum, "observed": observed,
                "observed_count": st["count"],
                "by_seat": {str(k): v for k, v in st["by_seat"].items()},
                "fallback_count": st["fallback"], "invalid_count": st["invalid"]}
    return {"name": name, "value": value, "in_enum": in_enum, "observed": False,
            "observed_count": 0, "by_seat": {}, "fallback_count": 0, "invalid_count": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate schema-v2 episodes")
    parser.add_argument("path")
    parser.add_argument("--no-semantic", action="store_true")
    parser.add_argument("--validation-report", default=None)
    parser.add_argument("--semantic-report", default=None)
    parser.add_argument("--context-report", default=None)
    parser.add_argument("--latency-report", default=None)
    args = parser.parse_args(argv)

    result = validate(args.path, run_semantic=not args.no_semantic)

    def dump(obj, p):
        if p:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=2)

    dump(result["validation"], args.validation_report)
    dump(result["semantic"], args.semantic_report)
    dump(result["context"], args.context_report)
    dump(result["latency"], args.latency_report)

    v, s = result["validation"], result["semantic"]
    print(f"file: {os.path.relpath(args.path, _REPO_ROOT) if args.path.startswith(_REPO_ROOT) else args.path}")
    print(f"games={v['games']} decisions={v['decisions']} errors={v['error_count']} "
          f"terminal_types={v['terminal_types']}")
    print(f"semantic replay: {s['matches']}/{s['safe_decisions_checked']} safe decisions "
          f"reproduced (convert_ok={s['convert_ok']}, mismatches={s['mismatch_count']})")
    for e in v["errors"][:10]:
        print(f"  line {e['line']}: {e['message']}")
    print("RESULT:", "PASS" if result["ok"] else "FAIL")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

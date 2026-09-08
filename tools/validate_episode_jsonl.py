"""Streaming loader/validator for captured episode JSONL (schema version 1).

Validates, without loading the whole file into memory:
- schema version and required fields per record type;
- game/decision ordering (game_start -> contiguous decisions -> game_terminal);
- selected indices against recorded legal bounds (distinct, in range, count in
  [min_count, max_count]);
- terminal per-player decision counts against actually-seen decisions;
- record-level policy determinism: safe-agent (used_fallback) selections equal
  the deterministic recomputation from recorded bounds.

Reports malformed records with 1-based line numbers, prints a human summary and
(optionally) a JSON summary, and exits nonzero on any validation failure.

Usage (from repo root):
  .venv/bin/python tools/validate_episode_jsonl.py <episodes.jsonl>
  .venv/bin/python tools/validate_episode_jsonl.py <episodes.jsonl> --json out.json
"""

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.safe_policy import select_indices  # noqa: E402

SCHEMA_VERSION = 1
_REQUIRED = {
    "game_start": ["schema_version", "record_type", "game_id", "cohort", "game_seed",
                   "agents_by_seat", "decks_by_seat"],
    "decision": ["schema_version", "record_type", "game_id", "decision_index", "player_index",
                 "seat", "game_seed", "agent_name", "context_name", "context_value",
                 "legal_option_count", "min_count", "max_count", "selected_indices",
                 "policy_latency_ns", "used_fallback", "validation_status", "observation"],
    "game_terminal": ["schema_version", "record_type", "game_id", "winner", "terminal_reason",
                      "decisions_by_player", "invalid_selection_count"],
}


def validate_stream(path):
    errors = []          # (line_no, message)
    games = 0
    decisions = 0
    terminals = 0
    open_game = None     # dict for the currently open game

    def err(line_no, msg):
        errors.append((line_no, msg))

    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as exc:
                err(line_no, f"malformed JSON: {exc}")
                continue
            rtype = rec.get("record_type")
            if rtype not in _REQUIRED:
                err(line_no, f"unknown record_type: {rtype!r}")
                continue
            missing = [f for f in _REQUIRED[rtype] if f not in rec]
            if missing:
                err(line_no, f"{rtype} missing fields: {missing}")
                continue
            if rec.get("schema_version") != SCHEMA_VERSION:
                err(line_no, f"schema_version {rec.get('schema_version')!r} != {SCHEMA_VERSION}")

            if rtype == "game_start":
                if open_game is not None:
                    err(line_no, f"game_start for {rec['game_id']} while game "
                                 f"{open_game['game_id']} still open")
                open_game = {"game_id": rec["game_id"], "next_index": 0,
                             "by_player": {}, "start_line": line_no}
                games += 1
            elif rtype == "decision":
                decisions += 1
                if open_game is None:
                    err(line_no, "decision outside any game (no preceding game_start)")
                    continue
                if rec["game_id"] != open_game["game_id"]:
                    err(line_no, f"decision game_id {rec['game_id']} != open "
                                 f"{open_game['game_id']}")
                if rec["decision_index"] != open_game["next_index"]:
                    err(line_no, f"decision_index {rec['decision_index']} != expected "
                                 f"{open_game['next_index']}")
                open_game["next_index"] += 1
                p = rec["player_index"]
                open_game["by_player"][p] = open_game["by_player"].get(p, 0) + 1
                # bounds
                n = rec["legal_option_count"]
                lo, hi = rec["min_count"], rec["max_count"]
                sel = rec["selected_indices"]
                if not isinstance(sel, list):
                    err(line_no, "selected_indices not a list")
                else:
                    if len(set(sel)) != len(sel):
                        err(line_no, f"duplicate selected_indices: {sel}")
                    if not (lo <= len(sel) <= hi):
                        err(line_no, f"selection count {len(sel)} outside [{lo},{hi}]")
                    for i in sel:
                        if not (isinstance(i, int) and 0 <= i < n):
                            err(line_no, f"selected index {i} out of range [0,{n})")
                    # record-level policy determinism for safe-agent decisions
                    if rec.get("used_fallback"):
                        expected = select_indices(n, lo, hi)
                        if sel != expected:
                            err(line_no, f"safe decision {sel} != deterministic {expected}")
            elif rtype == "game_terminal":
                terminals += 1
                if open_game is None:
                    err(line_no, "game_terminal with no open game")
                    continue
                if rec["game_id"] != open_game["game_id"]:
                    err(line_no, f"terminal game_id {rec['game_id']} != open "
                                 f"{open_game['game_id']}")
                declared = {int(k): v for k, v in rec["decisions_by_player"].items()}
                seen = open_game["by_player"]
                if declared != seen:
                    err(line_no, f"terminal decisions_by_player {declared} != seen {seen}")
                open_game = None

    if open_game is not None:
        err(open_game["start_line"], f"game {open_game['game_id']} never terminated")

    return {
        "path": os.path.relpath(path, _REPO_ROOT),
        "games": games,
        "decisions": decisions,
        "terminals": terminals,
        "error_count": len(errors),
        "errors": [{"line": ln, "message": m} for ln, m in errors[:200]],
        "valid": len(errors) == 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate episode JSONL")
    parser.add_argument("path")
    parser.add_argument("--json", default=None, help="write JSON summary to this path")
    args = parser.parse_args(argv)

    result = validate_stream(args.path)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

    print(f"file: {result['path']}")
    print(f"games={result['games']} decisions={result['decisions']} "
          f"terminals={result['terminals']} errors={result['error_count']}")
    for e in result["errors"][:20]:
        print(f"  line {e['line']}: {e['message']}")
    print("RESULT:", "PASS" if result["valid"] else "FAIL")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""c005 Phase E: streaming validation of the model-ready teacher dataset (AC-11).

Streams train/validation/test .jsonl.gz, checks required model-input+label fields,
deterministic unique example_ids, no game-id leakage across splits, no corrupt
records, and reports context/action distributions + entropy. Exits nonzero on
any validation failure.

Usage: .venv/bin/python tools/validate_teacher_dataset.py --dir <teacher_dataset> [--json out.json]
"""

import argparse
import gzip
import json
import math
import os
import sys

_REQUIRED = ["example_id", "game_id", "split", "teacher_id", "teacher_deck_id", "opponent_id",
             "seat", "select_context", "observation", "legal_options", "legal_option_count",
             "teacher_action_indices", "terminal_outcome", "decision_latency_ms", "importance_class"]
_SPLITS = ("train", "validation", "test")


def _entropy(counter):
    tot = sum(counter.values())
    return round(-sum((n / tot) * math.log2(n / tot) for n in counter.values() if n), 4) if tot else 0.0


def validate(directory):
    errors = []
    ids = set()
    game_split = {}
    ctx_counts, sel_counts = {}, {}
    per_split = {s: {"records": 0, "games": set()} for s in _SPLITS}
    total = 0
    corrupt = 0
    for s in _SPLITS:
        path = os.path.join(directory, f"{s}.jsonl.gz")
        if not os.path.isfile(path):
            errors.append(f"missing split file {s}.jsonl.gz")
            continue
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as e:
                    corrupt += 1
                    errors.append(f"{s}:{lineno} corrupt JSON: {e}")
                    continue
                total += 1
                per_split[s]["records"] += 1
                miss = [f for f in _REQUIRED if f not in rec]
                if miss:
                    errors.append(f"{s}:{lineno} missing fields {miss}")
                    continue
                if rec["split"] != s:
                    errors.append(f"{s}:{lineno} split field {rec['split']} != {s}")
                eid = rec["example_id"]
                if eid in ids:
                    errors.append(f"{s}:{lineno} duplicate example_id {eid}")
                ids.add(eid)
                gid = rec["game_id"]
                per_split[s]["games"].add(gid)
                if gid in game_split and game_split[gid] != s:
                    errors.append(f"leakage: game {gid} in {game_split[gid]} and {s}")
                game_split[gid] = s
                # label sanity: indices within option range
                n = rec["legal_option_count"]
                for i in rec["teacher_action_indices"]:
                    if not (isinstance(i, int) and 0 <= i < n):
                        errors.append(f"{s}:{lineno} action index {i} out of range [0,{n})")
                if not isinstance(rec["observation"], dict) or "select" not in rec["observation"]:
                    errors.append(f"{s}:{lineno} observation missing select")
                ctx_counts[rec["select_context"]] = ctx_counts.get(rec["select_context"], 0) + 1
                key = rec["teacher_action_indices"][0] if rec["teacher_action_indices"] else -1
                sel_counts[key] = sel_counts.get(key, 0) + 1

    result = {
        "directory": os.path.relpath(directory) if directory.startswith(os.getcwd()) else directory,
        "total_records": total, "unique_example_ids": len(ids), "corrupt_records": corrupt,
        "records_by_split": {s: per_split[s]["records"] for s in _SPLITS},
        "games_by_split": {s: len(per_split[s]["games"]) for s in _SPLITS},
        "leakage_detected": any("leakage" in e for e in errors),
        "context_distribution": {str(k): v for k, v in sorted(ctx_counts.items(), key=lambda x: -x[1])},
        "selected_index_entropy": _entropy(sel_counts),
        "error_count": len(errors), "errors": errors[:100],
        "valid": len(errors) == 0,
    }
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--json", default=None)
    a = p.parse_args(argv)
    r = validate(a.dir)
    if a.json:
        json.dump(r, open(a.json, "w"), indent=2)
    print(f"records={r['total_records']} unique_ids={r['unique_example_ids']} "
          f"corrupt={r['corrupt_records']} leakage={r['leakage_detected']} errors={r['error_count']}")
    print("by_split records:", r["records_by_split"], "games:", r["games_by_split"])
    for e in r["errors"][:10]:
        print("  ", e)
    print("RESULT:", "PASS" if r["valid"] else "FAIL")
    return 0 if r["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

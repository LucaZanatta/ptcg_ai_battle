"""Mine concrete tactical-failure examples for the primary baseline (AC-09).

The primary baseline uses a deterministic 'first maxCount options' policy. In the
MAIN decision context the engine offers several action OptionTypes (PLAY, ATTACH,
EVOLVE, ABILITY, RETREAT, ATTACK, END, ...). Because the policy always takes the
first option, it frequently DECLINES a legally-available ATTACK — often ending
the turn or attaching energy instead of attacking. Each such decision is a
concrete, decodable tactical failure ("a legal ATTACK existed and was not taken").

Reads gauntlet_games.jsonl.gz decision records for the target candidate; writes
tactical_failure_examples.jsonl and prints counts.

Usage (from repo root):
  .venv/bin/python tools/mine_tactical_failures.py --in-dir <artifacts> \
      --out contracts/.../results/artifacts/tactical_failure_examples.jsonl --candidate det_starter
"""

import argparse
import gzip
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.api import OptionType, SelectContext

_ATTACK = int(OptionType.ATTACK)
_END = int(OptionType.END)
_MAIN = int(SelectContext.MAIN)
_NAMES = {int(o): o.name for o in OptionType}


def mine(in_dir, out_path, candidate, max_examples=200):
    path = os.path.join(in_dir, "gauntlet_games.jsonl.gz")
    total_main = 0
    attack_available_not_taken = 0
    end_with_attack_available = 0
    examples = []
    with gzip.open(path, "rt", encoding="utf-8") as fh, \
            open(out_path, "w", encoding="utf-8") as out:
        for line in fh:
            r = json.loads(line)
            if r.get("record_type") != "decision" or r.get("candidate_id") != candidate:
                continue
            if r.get("select_context") != _MAIN:
                continue
            total_main += 1
            opts = r.get("option") or []
            sel = r.get("selected_indices") or []
            types = [o.get("type") for o in opts]
            attack_idx = [i for i, t in enumerate(types) if t == _ATTACK]
            if not attack_idx:
                continue
            chose_attack = any(sel and s in attack_idx for s in sel)
            if chose_attack:
                continue
            attack_available_not_taken += 1
            opt0_type = types[0] if types else None
            ended = opt0_type == _END
            if ended:
                end_with_attack_available += 1
            if len(examples) < max_examples:
                ex = {
                    "game_id": r.get("game_id"), "phase": r.get("phase"),
                    "candidate_id": candidate, "decision_index": r.get("decision_index"),
                    "context": "MAIN", "num_options": len(opts),
                    "selected_indices": sel,
                    "selected_option_types": [_NAMES.get(types[i], types[i]) for i in sel if i < len(types)],
                    "attack_option_indices": attack_idx,
                    "available_option_types": [_NAMES.get(t, t) for t in types],
                    "failure": ("ended_turn_with_attack_available" if ended
                                else "declined_available_attack"),
                }
                examples.append(ex)
                out.write(json.dumps(ex) + "\n")
    summary = {
        "candidate": candidate,
        "main_decisions": total_main,
        "attack_available_not_taken": attack_available_not_taken,
        "end_turn_with_attack_available": end_with_attack_available,
        "examples_written": len(examples),
        "out": os.path.relpath(out_path, _REPO_ROOT),
    }
    print(json.dumps(summary, indent=2))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mine tactical failures")
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate", default="det_starter")
    parser.add_argument("--max-examples", type=int, default=200)
    args = parser.parse_args(argv)
    mine(args.in_dir, args.out, args.candidate, args.max_examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""c007 AC-05 validation: verify the generated v2 dataset is schema-complete, ordered,
leak-free, and carries populated privileged plan labels. Writes v2_dataset_validation.txt.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")

REQUIRED = ["example_id", "game_id", "split", "decision_index", "turn_index", "step_index",
            "teacher_seat", "teacher_id", "teacher_deck_id", "opponent_id", "select_context",
            "min_count", "max_count", "legal_option_count", "previous_context",
            "previous_teacher_action_indices", "observation", "legal_options",
            "teacher_action_indices", "terminal_outcome", "decision_latency_ms", "plan_labels"]
PLAN_REQUIRED = ["plan_a_attack", "plan_a_counter", "plan_b_counter", "use_support",
                 "bench_attacker", "scores", "select_context"]


def _eid(tid, gid, didx):
    return hashlib.sha256(f"{tid}|{gid}|{didx}".encode()).hexdigest()[:24]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=os.path.join(C007_ART, "v2_dataset"))
    p.add_argument("--log", default=os.path.join(os.path.dirname(C007_ART), "test_logs",
                                                 "v2_dataset_validation.txt"))
    a = p.parse_args(argv)
    checks = []

    def rec(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    games = {}
    game_split = {}
    missing_field = 0
    plan_populated = 0
    plan_total = 0
    bad_eid = 0
    n = 0
    outcome_present = 0
    for sp in ("train", "validation", "test"):
        path = os.path.join(a.data_dir, f"{sp}.jsonl.gz")
        with gzip.open(path, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                n += 1
                for f in REQUIRED:
                    if f not in r:
                        missing_field += 1
                        break
                games.setdefault(r["game_id"], []).append(r["decision_index"])
                game_split.setdefault(r["game_id"], set()).add(sp)
                if _eid(r["teacher_id"], r["game_id"], r["decision_index"]) != r["example_id"]:
                    bad_eid += 1
                pl = r.get("plan_labels") or {}
                plan_total += 1
                if all(k in pl for k in PLAN_REQUIRED):
                    plan_populated += 1
                if r.get("terminal_outcome") is not None:
                    outcome_present += 1

    # contiguity per game
    noncontig = 0
    for gid, idxs in games.items():
        if sorted(idxs) != list(range(len(idxs))):
            noncontig += 1
    leak = {g: sorted(s) for g, s in game_split.items() if len(s) > 1}

    man = json.load(open(os.path.join(C007_ART, "v2_dataset_manifest.json")))
    tot_games = man["total_strategic_games"]; tot_dec = man["total_strategic_decisions"]

    rec("all_required_fields_present", missing_field == 0, f"missing in {missing_field} records")
    rec("example_ids_recoverable", bad_eid == 0, f"{bad_eid} mismatches")
    rec("decision_indices_contiguous", noncontig == 0, f"{noncontig} games noncontiguous")
    rec("no_game_in_multiple_splits", len(leak) == 0, str(leak)[:200])
    rec("plan_labels_populated", plan_populated == plan_total,
        f"{plan_populated}/{plan_total}")
    rec("terminal_outcome_present", outcome_present == n, f"{outcome_present}/{n}")
    rec("min_600_games", tot_games >= 600, f"{tot_games} games")
    rec("min_50000_decisions", tot_dec >= 50000, f"{tot_dec} decisions")
    rec("decisions_match_manifest", n == tot_dec, f"scanned {n} vs manifest {tot_dec}")

    all_ok = all(c[1] for c in checks)
    lines = ["c007 AC-05 v2 dataset validation", "=" * 50,
             f"scanned {n} decisions over {len(games)} games",
             f"strategic: {tot_games} games / {tot_dec} decisions; control: "
             f"{man['control_games']} games / {man['control_decisions']} decisions", ""]
    for name, ok, detail in checks:
        lines.append(f"  [{'OK ' if ok else 'FAIL'}] {name}  {detail}")
    lines.append("")
    lines.append(f"ALL_OK = {all_ok}")
    txt = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    open(a.log, "w").write(txt)
    print(txt)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

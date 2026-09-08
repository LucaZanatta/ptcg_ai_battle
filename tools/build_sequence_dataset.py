"""c006 AC-02: rebuild ORDERED sequence-preserving records from the c005
model-ready capture, restoring the decision-ordering fields that the c005
records dropped, WITHOUT regenerating games (so c005 split membership is
preserved exactly; the engine is non-reproducible so re-running would move games).

For each game the sequential ``decision_index`` is recovered losslessly from the
c005 ``example_id`` (= sha256(teacher_id|game_id|decision_index)[:24]); ordering
is cross-checked against the engine ``observation.step`` counter. Real turn/step
identifiers are taken from the observation (``current.turn`` / ``step``). Adds
per-record ``previous_context`` and ``previous_teacher_action_indices`` (the S2
explicit-history inputs), resets at game start.

Outputs (under results/artifacts):
  sequence_dataset/{train,validation,test}.jsonl.gz
  sequence_dataset/sequence_index.json    game_id -> ordered example_ids (+ split)
  sequence_dataset_manifest.json
"""

import argparse
import gzip
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                  "results", "artifacts", "teacher_dataset")


def _eid(tid, gid, didx):
    return hashlib.sha256(f"{tid}|{gid}|{didx}".encode()).hexdigest()[:24]


def _recover_order(records):
    """Return records sorted by recovered decision_index (0..n-1)."""
    tid = records[0]["teacher_id"]
    gid = records[0]["game_id"]
    by_eid = {r["example_id"]: r for r in records}
    ordered = [None] * len(records)
    for didx in range(len(records) + 8):
        e = _eid(tid, gid, didx)
        if e in by_eid:
            if didx >= len(records):
                raise ValueError(f"decision_index {didx} exceeds game size for {gid}")
            ordered[didx] = by_eid[e]
    if any(r is None for r in ordered):
        raise ValueError(f"could not recover a contiguous ordering for game {gid}")
    return ordered


def _turn_step(rec):
    obs = rec["observation"]
    cur = obs.get("current") or {}
    return cur.get("turn"), obs.get("step")


def run(args):
    out_dir = os.path.join(args.out_dir, "sequence_dataset")
    os.makedirs(out_dir, exist_ok=True)

    # load c005 records grouped by game, remembering original split
    games = {}          # gid -> list of records
    game_split = {}     # gid -> split
    for sp in ("train", "validation", "test"):
        with gzip.open(os.path.join(DS, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
                game_split[r["game_id"]] = sp

    writers = {sp: gzip.open(os.path.join(out_dir, f"{sp}.jsonl.gz"), "wt", encoding="utf-8")
               for sp in ("train", "validation", "test")}
    seq_index = {}
    counts = {sp: {"games": 0, "decisions": 0} for sp in writers}
    problems = []
    step_monotonic_violations = 0
    turn_nondecreasing_violations = 0

    for gid, recs in sorted(games.items()):
        sp = game_split[gid]
        ordered = _recover_order(recs)
        prev_step = None
        prev_turn = None
        prev_ctx = None
        prev_action = []
        eids = []
        for didx, r in enumerate(ordered):
            turn, step = _turn_step(r)
            if prev_step is not None and step is not None and step < prev_step:
                step_monotonic_violations += 1
            if prev_turn is not None and turn is not None and turn < prev_turn:
                turn_nondecreasing_violations += 1
            out = {
                "example_id": r["example_id"],
                "game_id": gid,
                "split": sp,
                "decision_index": didx,
                "turn_index": turn,
                "step_index": step,
                "teacher_seat": r["seat"],
                "teacher_id": r["teacher_id"],
                "teacher_deck_id": r["teacher_deck_id"],
                "opponent_id": r["opponent_id"],
                "select_context": r["select_context"],
                "min_count": r["min_count"],
                "max_count": r["max_count"],
                "legal_option_count": r["legal_option_count"],
                "previous_context": prev_ctx,
                "previous_teacher_action_indices": prev_action,
                "observation": r["observation"],
                "legal_options": r["legal_options"],
                "teacher_action_indices": r["teacher_action_indices"],
                "terminal_outcome": r["terminal_outcome"],
                "decision_latency_ms": r.get("decision_latency_ms"),
            }
            writers[sp].write(json.dumps(out) + "\n")
            eids.append(r["example_id"])
            prev_step, prev_turn = step, turn
            prev_ctx = r["select_context"]
            prev_action = list(r["teacher_action_indices"])
        seq_index[gid] = {"split": sp, "n_decisions": len(ordered), "example_ids": eids}
        counts[sp]["games"] += 1
        counts[sp]["decisions"] += len(ordered)

    for w in writers.values():
        w.close()
    json.dump(seq_index, open(os.path.join(out_dir, "sequence_index.json"), "w"))

    # verify split membership unchanged vs c005 splits.json
    c005_splits = json.load(open(os.path.join(DS, "splits.json")))
    membership_ok = all(counts[sp]["games"] == c005_splits["games"][sp]
                        and counts[sp]["decisions"] == c005_splits["decisions"][sp]
                        for sp in counts)

    manifest = {
        "contract": "c006_distilled_policy_baseline",
        "source": "c005 teacher_dataset (model-ready records, ordering restored)",
        "regenerated_games": False,
        "ordering_method": "decision_index recovered from c005 example_id hash; "
                           "cross-checked against observation.step; turn_index=current.turn, "
                           "step_index=observation.step (real engine fields, no derivation needed)",
        "counts": counts,
        "total_games": sum(counts[s]["games"] for s in counts),
        "total_decisions": sum(counts[s]["decisions"] for s in counts),
        "split_membership_preserved": membership_ok,
        "step_monotonic_violations": step_monotonic_violations,
        "turn_nondecreasing_violations": turn_nondecreasing_violations,
        "no_sequence_crosses_game_boundary": True,
        "hidden_state_reset": "per game (sequence_index groups by game_id)",
        "file_sha256": {sp: hashlib.sha256(open(os.path.join(out_dir, f"{sp}.jsonl.gz"), "rb").read()).hexdigest()
                        for sp in ("train", "validation", "test")},
    }
    json.dump(manifest, open(os.path.join(args.out_dir, "sequence_dataset_manifest.json"), "w"), indent=2)

    ok = (membership_ok and step_monotonic_violations == 0 and not problems)
    print(json.dumps({"counts": counts, "split_membership_preserved": membership_ok,
                      "step_monotonic_violations": step_monotonic_violations,
                      "turn_nondecreasing_violations": turn_nondecreasing_violations,
                      "all_ok": ok}, indent=2))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

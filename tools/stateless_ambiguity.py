"""c006 AC-03: stateless-ambiguity diagnostic.

Quantifies how often a stateless policy is fundamentally unable to reproduce the
teacher because the visible (normalized) observation + legal options are
equivalent yet the teacher's action differs across game histories. Computed on
TRAIN+VALIDATION only (the test split stays sealed until final offline eval).

Two hashes (see cg.obs_norm, documented there):
  - EXACT : canonical (strategic state, legal options) match byte-for-byte.
  - NEAR  : coarse board/context/option-shape bucket.

For each bucket with >1 distinct teacher action we record a conflict. The
empirical upper bound on stateless EXACT agreement is the fraction of decisions a
Bayes-optimal stateless policy (predict the per-bucket majority action) would
match: sum(max_action_count per exact bucket) / total.
"""

import argparse
import collections
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.obs_norm import action_key, exact_hash, near_hash


def _load(seq_dir, splits):
    for sp in splits:
        with gzip.open(os.path.join(seq_dir, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                yield json.loads(line)


def run(args):
    seq_dir = os.path.join(args.in_dir, "sequence_dataset")
    splits = ("train", "validation")  # test sealed

    exact = collections.defaultdict(collections.Counter)   # hash -> action_key -> count
    exact_ctx = {}                                          # hash -> context
    exact_members = collections.defaultdict(list)          # hash -> list(record refs)
    near = collections.defaultdict(collections.Counter)
    near_ctx = {}
    near_members = collections.defaultdict(list)
    total = 0

    for r in _load(seq_dir, splits):
        total += 1
        ak = action_key(r["legal_options"], r["teacher_action_indices"])
        eh = exact_hash(r["observation"], r["legal_options"])
        nh = near_hash(r["observation"], r["legal_options"])
        exact[eh][ak] += 1
        exact_ctx[eh] = r["select_context"]
        exact_members[eh].append((r["example_id"], r["game_id"], r["select_context"],
                                  r["teacher_action_indices"], ak))
        near[nh][ak] += 1
        near_ctx[nh] = r["select_context"]
        near_members[nh].append((r["example_id"], r["game_id"], r["select_context"],
                                 r["teacher_action_indices"]))

    # exact-equivalence stats
    exact_conflict_buckets = 0
    exact_conflict_records = 0
    majority_correct = 0
    ctx_conflicts = collections.Counter()
    for h, actions in exact.items():
        n = sum(actions.values())
        majority_correct += max(actions.values())
        if len(actions) > 1:
            exact_conflict_buckets += 1
            exact_conflict_records += n
            ctx_conflicts[exact_ctx[h]] += n
    upper_bound_exact_agreement = majority_correct / total if total else 1.0

    # near-equivalence stats
    near_conflict_buckets = 0
    near_conflict_records = 0
    near_majority = 0
    for h, actions in near.items():
        n = sum(actions.values())
        near_majority += max(actions.values())
        if len(actions) > 1:
            near_conflict_buckets += 1
            near_conflict_records += n
    upper_bound_near_agreement = near_majority / total if total else 1.0

    report = {
        "contract": "c006_distilled_policy_baseline",
        "computed_on_splits": list(splits),
        "test_split_touched": False,
        "total_decisions": total,
        "distinct_exact_states": len(exact),
        "exact_ambiguity": {
            "conflicting_buckets": exact_conflict_buckets,
            "conflicting_records": exact_conflict_records,
            "conflicting_record_fraction": round(exact_conflict_records / total, 6) if total else 0.0,
            "empirical_upper_bound_stateless_exact_agreement": round(upper_bound_exact_agreement, 6),
            "note": "Exact = byte-identical canonical (strategic state, legal options); "
                    "serial/step/clock removed. This bound IS treated as exact because "
                    "the equivalence is exact under the documented normalization.",
        },
        "near_ambiguity": {
            "documented_hash": "cg.obs_norm.near_hash (context + option-type multiset + "
                               "active/bench/hand id multisets + prize counts + turn + remainDamageCounter)",
            "distinct_near_buckets": len(near),
            "conflicting_buckets": near_conflict_buckets,
            "conflicting_records": near_conflict_records,
            "conflicting_record_fraction": round(near_conflict_records / total, 6) if total else 0.0,
            "empirical_upper_bound_under_near_hash": round(upper_bound_near_agreement, 6),
        },
        "contexts_most_affected_exact": [
            {"context": c, "conflicting_records": n} for c, n in ctx_conflicts.most_common(12)
        ],
    }

    os.makedirs(args.out_dir, exist_ok=True)
    json.dump(report, open(os.path.join(args.out_dir, "stateless_ambiguity_report.json"), "w"), indent=2)

    # examples: up to N largest exact-conflict buckets, showing the differing actions
    conflict_buckets = sorted(
        ((h, exact[h]) for h in exact if len(exact[h]) > 1),
        key=lambda kv: -sum(kv[1].values()))
    near_conflict_list = sorted(
        ((h, near[h]) for h in near if len(near[h]) > 1),
        key=lambda kv: -sum(kv[1].values()))
    with open(os.path.join(args.out_dir, "stateless_ambiguity_examples.jsonl"), "w") as fh:
        for h, actions in conflict_buckets[:args.examples]:
            members = exact_members[h]
            fh.write(json.dumps({
                "ambiguity_type": "exact",
                "exact_state_hash": h,
                "select_context": exact_ctx[h],
                "bucket_size": sum(actions.values()),
                "distinct_actions": len(actions),
                "action_distribution": [{"count": c} for c in sorted(actions.values(), reverse=True)],
                "example_members": [
                    {"example_id": m[0], "game_id": m[1], "context": m[2],
                     "teacher_action_indices": m[3]} for m in members[:6]
                ],
            }) + "\n")
        for h, actions in near_conflict_list[:args.examples]:
            members = near_members[h]
            fh.write(json.dumps({
                "ambiguity_type": "near",
                "near_state_hash": h,
                "select_context": near_ctx[h],
                "bucket_size": sum(actions.values()),
                "distinct_actions": len(actions),
                "action_distribution": [{"count": c} for c in sorted(actions.values(), reverse=True)],
                "example_members": [
                    {"example_id": m[0], "game_id": m[1], "context": m[2],
                     "teacher_action_indices": m[3]} for m in members[:6]
                ],
            }) + "\n")

    print(json.dumps({
        "total_decisions": total,
        "distinct_exact_states": len(exact),
        "exact_conflict_records": exact_conflict_records,
        "upper_bound_stateless_exact_agreement": round(upper_bound_exact_agreement, 4),
        "near_conflict_records": near_conflict_records,
        "upper_bound_under_near_hash": round(upper_bound_near_agreement, 4),
        "top_contexts": ctx_conflicts.most_common(6),
    }, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--examples", type=int, default=200)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

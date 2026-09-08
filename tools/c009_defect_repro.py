"""c009 AC-02: independently reproduce and quantify the c008 evaluation identity defect.

Three independent lines of evidence:

  1. DETERMINISTIC SYNTHETIC — a fixed permutation of completion order; the c008 pattern
     (positional ``zip`` after unordered results) mislabels; the c009 protocol (identity
     carried in the result) does not.
  2. REAL MULTIPROCESSING — a spawn Pool with ``imap_unordered`` and a deterministic delay
     schedule that forces completion order != submission order; same comparison.
  3. FORENSIC — the shipped c008 artifacts themselves: per-(arm,opponent) game counts must
     be exactly 80 but are 77/78/82/83 at arm-block boundaries, plus seat imbalance in the
     same cells. This is direct proof the shipped aggregates are corrupted.

Read-only with respect to c008.
"""

import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl",
                        "results", "artifacts")

# job order used by c008 strategic(): arm-major, then opponent, then seat, then replicate
ARMS = ["teacher", "R0", "R1", "R2"]
OPPS = ["mega_lucario", "iono", "mega_abomasnow", "dragapult", "__control__"]
PER_COMBO = 40


def _mp_worker(job):
    """Deterministic delay so completion order provably differs from submission order:
    jobs whose index is in the last fifth of a block sleep longer (mirrors long games at a
    block tail), so they finish after jobs from the following block."""
    idx = job["idx"]
    time.sleep(0.02 if (idx % 20) >= 16 else 0.001)
    # a correct worker RETURNS its identity; it never relies on ordering
    return {"idx": idx, "true_arm": job["arm"], "opp": job["opp"], "seat": job["seat"]}


def synthetic_repro():
    """Fixed permutation, no concurrency: isolates the logic error from timing."""
    jobs = []
    for arm in ARMS:
        for opp in OPPS:
            for seat in (0, 1):
                for r in range(4):  # small but structurally identical
                    jobs.append({"idx": len(jobs), "arm": arm, "opp": opp, "seat": seat,
                                 "replicate": r})
    n = len(jobs)
    block = len(OPPS) * 2 * 4                    # jobs per arm block
    # Deterministic completion order reproducing the REAL signature: the last two jobs of
    # each arm block finish AFTER the first two jobs of the next arm block (long games at a
    # block tail get overtaken). Reordering must CROSS an arm boundary to mislabel — an
    # in-block permutation alone leaves positional labels accidentally correct.
    order = list(range(n))
    for b in range(block, n, block):
        order[b - 2:b + 2] = order[b:b + 2] + order[b - 2:b]
    results = [{"idx": jobs[i]["idx"], "true_arm": jobs[i]["arm"], "opp": jobs[i]["opp"],
                "seat": jobs[i]["seat"]} for i in order]

    # --- c008 pattern: positional reattachment ---
    c008 = [dict(r) for r in results]
    for j, r in zip(jobs, c008):
        r["arm"] = j["arm"]
    c008_bad = sum(1 for r in c008 if r["arm"] != r["true_arm"])

    # --- c009 protocol: identity travels with the result ---
    c009 = [dict(r) for r in results]
    for r in c009:
        r["arm"] = r["true_arm"]
    c009_bad = sum(1 for r in c009 if r["arm"] != r["true_arm"])

    return {"jobs": n, "completion_order_differs": order != list(range(n)),
            "permutation": "last 2 jobs of each arm block complete after the first 2 of the next",
            "c008_pattern_mislabeled": c008_bad,
            "c008_pattern_mislabel_rate": round(c008_bad / n, 4),
            "c009_protocol_mislabeled": c009_bad,
            "note": "reordering must cross an arm-block boundary to mislabel; a purely "
                    "within-block permutation leaves positional labels accidentally correct, "
                    "which is why c008's corruption is concentrated at block boundaries",
            "defect_reproduced": c008_bad > 0 and c009_bad == 0}


def multiprocessing_repro(nproc=8):
    """Real spawn Pool + imap_unordered; deterministic delays force reordering."""
    jobs = []
    for arm in ARMS:
        for opp in OPPS:
            for seat in (0, 1):
                for _r in range(2):
                    jobs.append({"idx": len(jobs), "arm": arm, "opp": opp, "seat": seat})
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=nproc) as pool:
        results = list(pool.imap_unordered(_mp_worker, jobs, chunksize=1))
    submitted_order = [j["idx"] for j in jobs]
    completion_order = [r["idx"] for r in results]
    # c008 pattern
    c008 = [dict(r) for r in results]
    for j, r in zip(jobs, c008):
        r["arm"] = j["arm"]
    c008_bad = sum(1 for r in c008 if r["arm"] != r["true_arm"])
    # c009 protocol
    c009_bad = sum(1 for r in results if r["true_arm"] != jobs[r["idx"]]["arm"])
    return {"jobs": len(jobs), "nproc": nproc,
            "completion_order_differs_from_submission": completion_order != submitted_order,
            "first_10_submitted": submitted_order[:10], "first_10_completed": completion_order[:10],
            "c008_pattern_mislabeled": c008_bad,
            "c008_pattern_mislabel_rate": round(c008_bad / len(jobs), 4),
            "c009_protocol_mislabeled": c009_bad,
            "defect_reproduced": c008_bad > 0 and c009_bad == 0}


def forensic_c008():
    """The shipped c008 artifacts prove corruption on their own."""
    path = os.path.join(C008_ART, "rl_strategic_games.jsonl.gz")
    rows = [json.loads(l) for l in gzip.open(path, "rt")]
    cell = Counter((r["arm"], r["opp"]) for r in rows)
    seat = Counter((r["arm"], r["opp"], r["seat"]) for r in rows)
    expected = PER_COMBO * 2
    bad_cells = {f"{a}|{o}": n for (a, o), n in sorted(cell.items()) if n != expected}
    seat_imbalanced = {f"{a}|{o}": [seat.get((a, o, 0), 0), seat.get((a, o, 1), 0)]
                       for (a, o) in sorted(cell)
                       if seat.get((a, o, 0), 0) != seat.get((a, o, 1), 0)}
    # minimum provably-mislabeled games = sum of positive deviations
    min_mislabeled = sum(max(0, n - expected) for n in cell.values())
    # which opponents are affected (block boundaries)
    affected_opps = sorted({o for (a, o), n in cell.items() if n != expected})
    per_arm = Counter(r["arm"] for r in rows)
    return {
        "raw_rows": len(rows), "expected_per_cell": expected,
        "per_arm_totals": dict(per_arm),
        "cells_with_wrong_count": bad_cells,
        "n_cells_wrong": len(bad_cells),
        "seat_imbalanced_cells": seat_imbalanced,
        "min_provably_mislabeled_games": min_mislabeled,
        "affected_opponents": affected_opps,
        "boundary_signature": ("wrong counts occur only at arm-block boundaries "
                               "(first opponent 'mega_lucario' and last opponent '__control__' "
                               "of each 400-job arm block), the exact signature of positional "
                               "reattachment after unordered completion"),
        "corruption_confirmed": len(bad_cells) > 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)

    syn = synthetic_repro()
    mpr = multiprocessing_repro()
    fx = forensic_c008()
    out = {
        "contract": "c009",
        "defect": "c008 evaluator assigned arm labels positionally (zip) over results returned "
                  "by multiprocessing imap_unordered, which yields COMPLETION order, not "
                  "submission order.",
        "defective_code": {
            "file": "tools/c008_final_eval.py", "function": "strategic()",
            "pattern": "res = _run(...)  # imap_unordered\\nfor j, r in zip(jobs, res): r['arm'] = j['arm']",
            "note": "the c008 source comment ('attach arm label (imap loses it otherwise)') shows the "
                    "label was known to be lost and was then re-attached by position — the error.",
        },
        "scope": {
            "affected": ["strategic field aggregates", "held-out Mega Abomasnow report",
                         "matchup matrix", "global ranking/mean-vs-field",
                         "improvement report", "regression report", "best-arm conclusion"],
            "not_affected_by_this_defect": [
                "teacher non-inferiority (each candidate ran in its own pool call and all "
                "aggregate fields came from worker-returned values)",
                "reliability (per-candidate pool call; count/sum aggregates only)",
                "training curves and checkpoint selection (no multiprocessing relabeling)"],
        },
        "synthetic_reproduction": syn,
        "multiprocessing_reproduction": mpr,
        "forensic_c008_artifacts": fx,
        "reproduced": bool(syn["defect_reproduced"] and mpr["defect_reproduced"]
                           and fx["corruption_confirmed"]),
    }
    json.dump(out, open(os.path.join(a.out_dir, "c008_defect_reproduction.json"), "w"), indent=2)

    lines = ["c009 AC-02 — c008 identity-defect reproduction", "=" * 60,
             "1) SYNTHETIC (deterministic permutation):",
             f"   jobs={syn['jobs']} c008-pattern mislabeled={syn['c008_pattern_mislabeled']} "
             f"({syn['c008_pattern_mislabel_rate']*100:.1f}%)  c009-protocol mislabeled={syn['c009_protocol_mislabeled']}",
             f"   reproduced={syn['defect_reproduced']}", "",
             "2) REAL MULTIPROCESSING (spawn + imap_unordered, deterministic delays):",
             f"   jobs={mpr['jobs']} completion order differs={mpr['completion_order_differs_from_submission']}",
             f"   submitted[:10]={mpr['first_10_submitted']}",
             f"   completed[:10]={mpr['first_10_completed']}",
             f"   c008-pattern mislabeled={mpr['c008_pattern_mislabeled']} "
             f"({mpr['c008_pattern_mislabel_rate']*100:.1f}%)  c009-protocol mislabeled={mpr['c009_protocol_mislabeled']}",
             f"   reproduced={mpr['defect_reproduced']}", "",
             "3) FORENSIC (shipped c008 artifacts):",
             f"   raw rows={fx['raw_rows']} expected per (arm,opponent) cell={fx['expected_per_cell']}",
             f"   cells with wrong count={fx['n_cells_wrong']} -> {fx['cells_with_wrong_count']}",
             f"   seat-imbalanced cells={len(fx['seat_imbalanced_cells'])} -> {fx['seat_imbalanced_cells']}",
             f"   minimum provably mislabeled games={fx['min_provably_mislabeled_games']}",
             f"   affected opponents={fx['affected_opponents']}",
             f"   corruption confirmed={fx['corruption_confirmed']}", "",
             f"DEFECT REPRODUCED = {out['reproduced']}"]
    open(a.log, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if out["reproduced"] else 1


if __name__ == "__main__":
    sys.exit(main())

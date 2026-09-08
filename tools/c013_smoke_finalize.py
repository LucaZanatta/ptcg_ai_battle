"""c013 §19 — backfill the game-5,000 evaluation the smoke runs exited before reaching.

§19 requires evaluations at 0, 2,500 and 5,000. In `c013_curriculum_smoke.py` the evaluation
block lived inside `while completed < max_games`, so a run whose final rollout carried it past
5,000 left the loop before evaluating that point. Both arms therefore recorded two evaluations
instead of three.

The loop is fixed for future runs. For the two runs already completed, the missing evaluation is
performed HERE, on each arm's **final checkpoint** — the same policy the loop would have
evaluated, at the same registered point. Nothing is retrained and no training game is spent; the
budget is untouched. What differs from a clean run is only WHEN the evaluation was issued, and
each backfilled record carries `backfilled: true` plus the reason so the evidence never implies
it was produced inline.

Re-running the two arms under the fixed loop was the alternative. It would have cost a further
~10,000 completed games and taken the curriculum smoke to ~20,000 against a registered maximum
of 10,000 — spending a doubled compute ceiling to make a timestamp tidier.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_curriculum_smoke as cs  # noqa: E402
import c013_common as K  # noqa: E402
from cg import teachers as T, c009_eval as ce  # noqa: E402

ART = cs.ART


def finalize(arm: str, seed: int, nproc: int = 16) -> dict:
    outdir = os.path.join(ART, "training", arm, f"seed{seed}")
    spath = os.path.join(outdir, "summary.json")
    summ = json.load(open(spath))
    done = {e.get("registered_point") for e in summ["evaluations"]}
    missing = [p for p in cs.EVAL_POINTS
               if p not in done and summ["completed_games"] >= p]
    if not missing:
        return {"arm": arm, "status": "already_complete",
                "n_evaluations": len(summ["evaluations"])}

    reg = json.load(open(os.path.join(outdir, "checkpoint_registry.json")))
    final = reg[max(reg, key=lambda x: int(x))]
    ckpt = os.path.join(_REPO, final["checkpoint_path"])
    deck = T.read_deck("dragapult", ce.SOURCES)
    rng = np.random.default_rng(seed + 90000)

    pool = mp.get_context("spawn").Pool(processes=nproc)
    try:
        for pt in missing:
            ev = cs.panel(pool, ckpt, deck, rng, f"{arm}{seed}_backfill_pt{pt}")
            best = {"teacher": max((e.get("teacher") or 0) for e in summ["evaluations"]),
                    "field": max((e.get("field") or 0) for e in summ["evaluations"])}
            adv, g = cs.gates(ev, best)
            ev.update({"arm": arm, "seed": seed, "registered_point": pt,
                       "completed_games": summ["completed_games"],
                       "stage": summ["final_stage"], "gates": g, "advance": adv,
                       "backfilled": True,
                       "backfill_reason": "the budget loop exited before evaluating this "
                                          "registered point; evaluated here on the final "
                                          "checkpoint, no training games spent",
                       "checkpoint_path": final["checkpoint_path"]})
            summ["evaluations"].append(ev)
    finally:
        pool.close()
        pool.join()

    summ["evaluations"].sort(key=lambda e: e["registered_point"])
    summ["n_evaluations"] = len(summ["evaluations"])
    m = summ.setdefault("machinery", {})
    m["nonzero_evaluations"] = [e["scored"] > 0 for e in summ["evaluations"]]
    m["backfilled_evaluations"] = [e["registered_point"] for e in summ["evaluations"]
                                   if e.get("backfilled")]
    summ["registered_evaluation_points_covered"] = sorted(
        {e["registered_point"] for e in summ["evaluations"]})
    json.dump(summ, open(spath, "w"), indent=2, default=str)
    return {"arm": arm, "status": "backfilled", "points": missing,
            "n_evaluations": summ["n_evaluations"],
            "all_nonzero": all(m["nonzero_evaluations"])}


def main():
    out = [finalize(a, s) for a, s in (("R0", 1001), ("R1", 1002))]
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

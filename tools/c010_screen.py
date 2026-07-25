"""c010 AC-10: apply the registered §17 nomination rule and record the confirmation panel.

Stage `nominate` walks each branch (arm, seed) in training order and applies
cg.c010_decisions.nominate against the running branch best -- the rule is applied
prospectively, in checkpoint order, exactly as §17 states, so a later checkpoint can never
retroactively change whether an earlier one was nominated. Nomination is not promotion; it
only buys a 500-game confirmation panel.

Stage `confirm` records the confirmation-panel outcome for every nominated checkpoint,
including the ones whose screen result did not survive the larger panel.
"""

import argparse
import csv
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from cg import c010_decisions as D  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")

FIELDS = ["candidate_id", "arm", "seed", "training_games", "registered_eval_point",
          "teacher_score", "teacher_one_sided_lb95", "strategic_field_score",
          "promotion_composite", "composite_ci95_lo", "composite_ci95_hi", "games",
          "defects", "invalid", "nominated", "nomination_reasons"]


def J(n, default=None):
    p = os.path.join(ART, n)
    return json.load(open(p)) if os.path.exists(p) else (default if default is not None else {})


def branch_order(reg, screen):
    """(arm, seed) -> candidate ids ordered by training games. Baselines are not branches."""
    branches = {}
    for cid, meta in reg.items():
        if cid in ("B0_v2a", "I0_incumbent", "T_teacher") or cid not in screen:
            continue
        branches.setdefault((meta["arm"], meta["seed"]), []).append(cid)
    for k in branches:
        branches[k].sort(key=lambda c: reg[c]["training_games"])
    return branches


def stage_nominate():
    reg = J("evaluation_candidate_registry.json")
    screen = J("panel_screen_summaries.json")
    branches = branch_order(reg, screen)

    rows, nominated = [], []
    for (arm, seed), cids in sorted(branches.items()):
        branch_best = None
        for i, cid in enumerate(cids):
            s = screen[cid]
            dec = D.nominate(s, branch_best, is_final_checkpoint=(i == len(cids) - 1))
            if dec["nominated"]:
                nominated.append(cid)
            ci = s.get("composite_ci95") or [None, None]
            rows.append({
                "candidate_id": cid, "arm": arm, "seed": seed,
                "training_games": reg[cid]["training_games"],
                "registered_eval_point": reg[cid].get("registered_eval_point"),
                "teacher_score": s.get("teacher_score"),
                "teacher_one_sided_lb95": s.get("teacher_one_sided_lb95"),
                "strategic_field_score": s.get("strategic_field_score"),
                "promotion_composite": s.get("promotion_composite"),
                "composite_ci95_lo": ci[0], "composite_ci95_hi": ci[1],
                "games": s["reliability"]["games"], "defects": s["reliability"]["defects"],
                "invalid": s["reliability"]["invalid"],
                "nominated": dec["nominated"],
                "nomination_reasons": "; ".join(dec["reasons"]),
            })
            # running branch best is updated by composite, prospectively
            if branch_best is None or (
                    s.get("promotion_composite") is not None
                    and branch_best.get("promotion_composite") is not None
                    and s["promotion_composite"] > branch_best["promotion_composite"]):
                branch_best = s

    for cid in ("B0_v2a", "I0_incumbent"):
        if cid in screen:
            s = screen[cid]
            ci = s.get("composite_ci95") or [None, None]
            rows.append({
                "candidate_id": cid, "arm": reg[cid]["arm"], "seed": reg[cid]["seed"],
                "training_games": reg[cid].get("training_games"),
                "registered_eval_point": None,
                "teacher_score": s.get("teacher_score"),
                "teacher_one_sided_lb95": s.get("teacher_one_sided_lb95"),
                "strategic_field_score": s.get("strategic_field_score"),
                "promotion_composite": s.get("promotion_composite"),
                "composite_ci95_lo": ci[0], "composite_ci95_hi": ci[1],
                "games": s["reliability"]["games"], "defects": s["reliability"]["defects"],
                "invalid": s["reliability"]["invalid"],
                "nominated": False,
                "nomination_reasons": "baseline/incumbent reference, not a branch candidate",
            })

    with open(os.path.join(ART, "checkpoint_screening.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (str(r["arm"]), str(r["seed"]),
                                             r["training_games"] or 0)):
            w.writerow(r)

    json.dump({"rule": "§17: composite exceeds branch best, or teacher +>=3pp, or field "
                       "+>=4pp, or branch final registered checkpoint. Applied prospectively "
                       "in checkpoint order; nomination is not promotion.",
               "branches": {f"{a}_{s}": c for (a, s), c in sorted(branches.items())},
               "nominated": nominated, "n_nominated": len(nominated),
               "n_screened": len(rows)},
              open(os.path.join(ART, "screening_nominations.json"), "w"), indent=2)

    with open(os.path.join(LOGD, "checkpoint_screening.txt"), "w") as fh:
        fh.write(f"c010 AC-10 screening: {len(rows)} rows, {len(nominated)} nominated\n")
        for r in sorted(rows, key=lambda r: -(r["promotion_composite"] or -9)):
            fh.write(f"  {r['candidate_id']:20s} comp={r['promotion_composite']} "
                     f"teacher={r['teacher_score']} field={r['strategic_field_score']} "
                     f"{'NOMINATED' if r['nominated'] else ''} {r['nomination_reasons']}\n")
    print(json.dumps({"screened": len(rows), "nominated": nominated}, indent=2))
    return nominated


def stage_confirm():
    reg = J("evaluation_candidate_registry.json")
    conf = J("panel_confirmation_summaries.json")
    screen = J("panel_screen_summaries.json")
    noms = J("screening_nominations.json").get("nominated", [])
    out = {}
    for cid in noms:
        if cid not in conf:
            out[cid] = {"confirmed": False, "note": "confirmation panel not run"}
            continue
        c, s = conf[cid], screen.get(cid, {})
        out[cid] = {
            "arm": reg[cid]["arm"], "seed": reg[cid]["seed"],
            "training_games": reg[cid]["training_games"],
            "screen": {"teacher": s.get("teacher_score"),
                       "field": s.get("strategic_field_score"),
                       "composite": s.get("promotion_composite")},
            "confirmation": {"teacher": c.get("teacher_score"),
                             "teacher_lb95": c.get("teacher_one_sided_lb95"),
                             "field": c.get("strategic_field_score"),
                             "composite": c.get("promotion_composite"),
                             "composite_ci95": c.get("composite_ci95"),
                             "games": c["reliability"]["games"]},
            "screen_survived_confirmation": (
                c.get("promotion_composite") is not None and s.get("promotion_composite") is not None
                and c["promotion_composite"] >= s["promotion_composite"] - 0.05),
            "reliability": c["reliability"],
        }
    i0 = conf.get("I0_incumbent") or screen.get("I0_incumbent") or {}
    json.dump({"note": "Confirmation is a 500-game panel on every §17 nomination. A nomination "
                       "that does not survive is retained here as evidence, not deleted.",
               "incumbent_reference": {"teacher": i0.get("teacher_score"),
                                       "field": i0.get("strategic_field_score"),
                                       "composite": i0.get("promotion_composite"),
                                       "panel": i0.get("panel")},
               "n_nominated": len(noms), "n_confirmed_panels": sum(1 for v in out.values()
                                                                   if "confirmation" in v),
               "candidates": out},
              open(os.path.join(ART, "checkpoint_confirmation.json"), "w"), indent=2)
    print(json.dumps({"nominated": len(noms),
                      "with_confirmation_panel": sum(1 for v in out.values()
                                                     if "confirmation" in v)}, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, choices=["nominate", "confirm"])
    a = p.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    if a.stage == "nominate":
        stage_nominate()
    else:
        stage_confirm()
    return 0


if __name__ == "__main__":
    sys.exit(main())

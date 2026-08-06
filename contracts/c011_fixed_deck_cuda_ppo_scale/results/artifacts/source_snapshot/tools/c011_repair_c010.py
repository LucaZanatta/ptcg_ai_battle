"""c011 §7 Phase 0: repair the remaining c010 checkpoint/decision evidence gaps.

Three separable jobs:

  §7.1  Enumerate EVERY saved c010 checkpoint and apply the four registered promising
        conditions programmatically, from c010's own screening CSV and registries. The
        contract's example IDs ("C_511 around 15k", ...) are deliberately NOT used -- §7.1
        says not to rely on them -- so the enumeration cannot silently miss a checkpoint
        whose name does not match an expectation.

  §7.2  Emit the job list for the same-panel frozen-teacher baseline.

  §7.3  Select the repaired incumbent from all CORRECTLY confirmed candidates by the
        registered ordering, and freeze + hash it.

The stage is split so the (slow) confirmation panels run between `--stage enumerate` and
`--stage select`.
"""

import argparse
import csv
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c009_eval as ce  # noqa: E402

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
C010A = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts")
ART = os.path.join(C011, "results", "artifacts")
LOGD = os.path.join(C011, "results", "test_logs")

# §7.1 promising conditions
T_MIN = 0.27
F_MIN = 0.33
COMPOSITE_WITHIN = 0.03
LATE_FRACTION = 0.75


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def branch_budgets(rows):
    """Actual final training-game count per (arm, seed) branch.

    Deliberately computed from the observed maximum training_games rather than from a
    registered budget: c010 Arm C seeds landed at 20,292 / 20,220 / 19,952, and seed 533's
    terminal checkpoint carries registered_eval_point = null. Keying anything on the
    registered point would drop exactly that checkpoint.
    """
    b = {}
    for r in rows:
        key = (r["arm"], r["seed"])
        g = int(r["training_games"] or 0)
        b[key] = max(b.get(key, 0), g)
    return b


def stage_enumerate():
    rows = list(csv.DictReader(open(os.path.join(C010A, "checkpoint_screening.csv"))))
    rows = [r for r in rows if r["candidate_id"] not in ("B0_v2a", "I0_incumbent")]
    conf = json.load(open(os.path.join(C010A, "checkpoint_confirmation.json")))
    already_confirmed = {k for k, v in conf["candidates"].items() if "confirmation" in v}
    budgets = branch_budgets(rows)
    best_screen_composite = max((f(r["promotion_composite"]) or -9) for r in rows)

    out = []
    for r in rows:
        cid = r["candidate_id"]
        t, fld = f(r["teacher_score"]), f(r["strategic_field_score"])
        comp = f(r["promotion_composite"])
        games = int(r["training_games"] or 0)
        budget = budgets[(r["arm"], r["seed"])]
        defects = int(r["defects"] or 0) + int(r["invalid"] or 0)
        late = budget > 0 and games >= LATE_FRACTION * budget
        cond = {
            "teacher_screen_ge_0.27": bool(t is not None and t >= T_MIN),
            "field_screen_ge_0.33": bool(fld is not None and fld >= F_MIN),
            "composite_within_0.03_of_best_screen": bool(
                comp is not None and comp >= best_screen_composite - COMPOSITE_WITHIN),
            "late_checkpoint_no_defect": bool(late and defects == 0),
        }
        promising = any(cond.values())
        out.append({
            "candidate_id": cid, "arm": r["arm"], "seed": int(r["seed"]),
            "training_games": games, "branch_final_games": budget,
            "fraction_of_branch": round(games / budget, 4) if budget else None,
            "registered_eval_point": r["registered_eval_point"] or None,
            "screen": {"teacher": t, "field": fld, "composite": comp,
                       "defects": defects},
            "conditions": cond, "promising": promising,
            "already_confirmed_in_c010": cid in already_confirmed,
            "needs_c011_confirmation": bool(promising and cid not in already_confirmed),
        })

    need = [o["candidate_id"] for o in out if o["needs_c011_confirmation"]]
    doc = {
        "rule": "§7.1 — a saved c010 checkpoint must receive a c011 confirmation panel when "
                "ANY of: teacher screen >= 0.27; field screen >= 0.33; promotion composite "
                "within 0.03 of c010's best screen; late checkpoint at >= 75% of its branch's "
                "ACTUAL final game count with no reliability defect.",
        "note": "Enumerated programmatically from c010's screening CSV and registries. The "
                "contract's approximate example IDs are not used (§7.1). Branch budgets are "
                "the observed final game counts, so seed 533's terminal checkpoint "
                "(registered_eval_point = null, 19,952 games) is included rather than "
                "filtered out.",
        "c010_best_screen_composite": best_screen_composite,
        "n_checkpoints_enumerated": len(out),
        "n_promising": sum(1 for o in out if o["promising"]),
        "n_already_confirmed_in_c010": sum(1 for o in out if o["already_confirmed_in_c010"]),
        "n_needing_c011_confirmation": len(need),
        "needs_confirmation": need,
        "checkpoints": out,
    }
    os.makedirs(ART, exist_ok=True)
    json.dump(doc, open(os.path.join(ART, "c010_checkpoint_reconfirmation.json"), "w"), indent=2)
    os.makedirs(LOGD, exist_ok=True)
    with open(os.path.join(LOGD, "c010_repair.txt"), "w") as fh:
        fh.write(f"c010 checkpoint enumeration: {len(out)} saved checkpoints, "
                 f"{doc['n_promising']} promising, {len(need)} need a c011 confirmation panel\n")
        for o in sorted(out, key=lambda x: -(x["screen"]["composite"] or -9)):
            fl = "".join(k[0].upper() if v else "." for k, v in o["conditions"].items())
            fh.write(f"  {o['candidate_id']:18s} g={o['training_games']:6d} "
                     f"({o['fraction_of_branch']:.2f} of branch) t={o['screen']['teacher']} "
                     f"f={o['screen']['field']} c={o['screen']['composite']} "
                     f"[{fl}] promising={o['promising']} "
                     f"c010conf={o['already_confirmed_in_c010']} "
                     f"need={o['needs_c011_confirmation']}\n")
    print(json.dumps({k: doc[k] for k in
                      ("n_checkpoints_enumerated", "n_promising",
                       "n_already_confirmed_in_c010", "n_needing_c011_confirmation",
                       "needs_confirmation")}, indent=2))
    return need


def stage_select(nproc=12):
    """§7.3 — repaired incumbent from every CORRECTLY confirmed candidate."""
    import numpy as np
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    import c011_eval as ev

    # §7.3 considers ALL correctly confirmed c010 candidates, so c010's own confirmation
    # games are pooled with c011's. c010 files are read, never written (§4). c011 only ran
    # confirmation panels for candidates c010 had NOT confirmed, so job_ids cannot collide.
    import gzip
    games = ev.load_existing()
    c010_games = os.path.join(C010A, "evaluation_games.jsonl.gz")
    n_c010 = 0
    if os.path.exists(c010_games):
        seen = {g["job_id"] for g in games}
        for line in gzip.open(c010_games, "rt"):
            g = json.loads(line)
            if g["job_id"] not in seen:
                games.append(g); n_c010 += 1
    reg = ev.build_candidate_registry()
    rng = np.random.default_rng(20260725)
    cands = {}
    # Confirmation-panel evidence only: every candidate is then judged on an equal 500-game
    # footing. Pooling c010's final panels would give five candidates 1,500 games and the
    # rest 500 in the same ranking.
    for cid in reg:
        if cid in ("T_teacher",):
            continue
        s, _ = ev.summarize(games, cid, {"confirmation"}, rng)
        if s and s["promotion_composite"] is not None and s["reliability"]["games"] >= 500:
            cands[cid] = s
    if not cands:
        print(json.dumps({"error": "no confirmed candidates"}))
        return 1

    def key(cid):
        s = cands[cid]
        po = s["per_opponent"]
        worst = min((po[o]["point"] for o in ev.ALL_OPPS if o in po), default=0.0)
        rel = s["reliability"]
        rel_ok = (rel["defects"] == 0 and rel["invalid"] == 0 and rel["exceptions"] == 0
                  and rel["timeouts"] == 0)
        return (s["teacher_score"] or 0, s["strategic_field_score"] or 0,
                po.get("mega_abomasnow", {}).get("point") or 0, worst, 1 if rel_ok else 0,
                -(s["latency_p99_max_ms"] or 0), -(reg[cid].get("training_games") or 0))

    ranked = sorted(cands, key=key, reverse=True)
    best = ranked[0]
    meta = reg[best]
    path = os.path.join(_REPO, meta["checkpoint_path"])
    on_disk = ce.sha256_file(path)
    assert on_disk == meta["checkpoint_sha256"], (
        f"incumbent hash drift: {on_disk} != {meta['checkpoint_sha256']}")

    doc = {
        "rule": "§7.3 ordering — teacher head-to-head, strategic field, held-out Abomasnow, "
                "worst-matchup risk, reliability, latency, then earlier training games.",
        "n_confirmed_candidates_considered": len(cands),
        "evidence": {"panel": "confirmation (500 games) for every candidate, equal footing",
                     "c011_confirmation_games": len(ev.load_existing()),
                     "c010_confirmation_games_pooled": n_c010},
        "incumbent_id": best,
        "checkpoint_path": meta["checkpoint_path"],
        "checkpoint_sha256": on_disk,
        "hash_verified_on_disk": True,
        "source_contract": meta.get("source_contract", "c010"),
        "training_games": meta.get("training_games"),
        "protected": True,
        "note": "Frozen before any CUDA training. Permanently protected (§15): a newer "
                "checkpoint never replaces it automatically.",
        "scores": {k: {"teacher": cands[k]["teacher_score"],
                       "field": cands[k]["strategic_field_score"],
                       "composite": cands[k]["promotion_composite"],
                       "abomasnow": cands[k]["per_opponent"].get("mega_abomasnow", {}).get("point"),
                       "games": cands[k]["reliability"]["games"]}
                   for k in ranked},
        "ranking": ranked,
    }
    json.dump(doc, open(os.path.join(ART, "c010_repaired_incumbent.json"), "w"), indent=2)
    with open(os.path.join(LOGD, "c010_repair.txt"), "a") as fh:
        fh.write(f"\n§7.3 repaired incumbent = {best} "
                 f"(teacher {cands[best]['teacher_score']}, "
                 f"field {cands[best]['strategic_field_score']}, sha {on_disk[:12]})\n")
        for c in ranked[:12]:
            s = cands[c]
            fh.write(f"  {c:20s} t={s['teacher_score']:.4f} f={s['strategic_field_score']:.4f} "
                     f"comp={s['promotion_composite']:.4f} n={s['reliability']['games']}\n")
    print(json.dumps({"incumbent_id": best, "sha256": on_disk,
                      "teacher": cands[best]["teacher_score"],
                      "field": cands[best]["strategic_field_score"],
                      "composite": cands[best]["promotion_composite"],
                      "considered": len(cands)}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, choices=["enumerate", "select"])
    p.add_argument("--nproc", type=int, default=12)
    a = p.parse_args(argv)
    if a.stage == "enumerate":
        stage_enumerate()
        return 0
    return stage_select(a.nproc)


if __name__ == "__main__":
    sys.exit(main())

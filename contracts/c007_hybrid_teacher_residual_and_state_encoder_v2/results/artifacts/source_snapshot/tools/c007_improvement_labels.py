"""c007 AC-08: outcome-backed improvement labels via controlled policy variants (§12).

1. Build the registered damage-counter variants (V_plan_a, V_greedy) from the frozen
   teacher (one-semantic-rule changes).
2. Balanced full-game A/B: each arm (teacher, each variant) vs the strategic field, both
   seats; bootstrap the DIFFERENCE in seat-balanced global strength.
3. Positive-label gate (POLICY-LEVEL, not per-state): a variant is admitted only if its
   global-strength improvement 90% bootstrap lower bound > 0 with zero reliability defects
   and a real behavioral difference in-context.
4. For an admitted variant, emit residual improvement labels = the variant's action at the
   admitted-context decisions where it differs from the teacher (target 2,000). If none
   qualifies, emit an honest empty label set.

The engine is random_device-seeded, so improvement is a policy-level global claim; per-state
counterfactual labels are never fabricated.
"""

import argparse
import gzip
import json
import multiprocessing as mp
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402

C005_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                            "results", "artifacts", "teacher_sources")
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
VARIANTS_ROOT = os.path.join(C007_ART, "teacher_variants")
V2_DATA = os.path.join(C007_ART, "v2_dataset")
STRATEGIC = ["mega_lucario", "mega_abomasnow", "iono", "dragapult"]
ADMIT_CONTEXT = "DAMAGE_COUNTER_ANY"


def _build_arm(spec):
    from cg.teachers import make_fresh as teacher_fresh
    from cg.teacher_variants import load_variant
    if spec[0] == "teacher":
        return teacher_fresh("dragapult", C005_SOURCES)
    if spec[0] == "variant":
        return load_variant(spec[1], VARIANTS_ROOT)
    raise ValueError(spec)


def _play(job):
    from kaggle_environments import make
    from cg.teachers import make_fresh as teacher_fresh
    from cg.safe_policy import MalformedSelection, validate_selection
    arm = _build_arm(job["arm"])
    opp = teacher_fresh(job["opp"], C005_SOURCES)
    seat = job["seat"]
    inv = [0]

    def make_arm_wrap():
        def w(obs):
            sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
            res = arm(obs)
            if sel is not None:
                n = len(sel.get("option", []))
                try:
                    validate_selection(list(res), n, sel.get("minCount"), sel.get("maxCount"))
                except MalformedSelection:
                    inv[0] += 1
            return res
        return w

    def make_opp_wrap():
        def w(obs):
            return opp(obs)
        return w

    players = [make_arm_wrap(), make_opp_wrap()] if seat == 0 else [make_opp_wrap(), make_arm_wrap()]
    exc = None; env = None
    try:
        env = make("cabt"); env.run(players)
    except Exception as e:  # noqa: BLE001
        exc = repr(e)
    if env is None:
        return {**job, "score": None, "invalid": inv[0], "exc": exc, "completed": False}
    last = env.steps[-1]
    st = [last[0]["status"], last[1]["status"]]
    rw = [last[0].get("reward"), last[1].get("reward")]
    if st != ["DONE", "DONE"]:
        return {**job, "score": None, "invalid": inv[0], "exc": exc, "completed": False}
    r = rw[seat]
    score = 0.5 if rw[0] == rw[1] else (1.0 if r == 1 else 0.0)
    return {"arm": job["arm"], "opp": job["opp"], "seat": seat, "score": score,
            "invalid": inv[0], "exc": None, "completed": True}


def _seat_balanced_mvf(games):
    """seat-balanced mean-vs-field: avg over opponents of 0.5*(mean seat0 + mean seat1)."""
    by = {}
    for g in games:
        by.setdefault((g["opp"], g["seat"]), []).append(g["score"])
    opps = sorted(set(o for o, _ in by))
    vals = []
    for o in opps:
        s0 = by.get((o, 0), []); s1 = by.get((o, 1), [])
        m0 = np.mean(s0) if s0 else np.nan; m1 = np.mean(s1) if s1 else np.nan
        vals.append(np.nanmean([m0, m1]))
    return float(np.nanmean(vals))


def _bootstrap_mvf(games, n_boot, rng):
    by = {}
    for g in games:
        by.setdefault((g["opp"], g["seat"]), []).append(g["score"])
    keys = sorted(by)
    arrs = {k: np.asarray(by[k]) for k in keys}
    opps = sorted(set(o for o, _ in keys))
    out = np.empty(n_boot)
    for b in range(n_boot):
        vals = []
        for o in opps:
            ms = []
            for seat in (0, 1):
                a = arrs.get((o, seat))
                if a is not None and len(a):
                    ms.append(a[rng.integers(0, len(a), len(a))].mean())
            if ms:
                vals.append(np.mean(ms))
        out[b] = np.mean(vals)
    return out


def run_ab(arms, games_per_combo, nproc, n_boot=4000):
    jobs = []
    for arm in arms:
        for opp in STRATEGIC:
            for seat in (0, 1):
                for _ in range(games_per_combo):
                    jobs.append({"arm": arm, "opp": opp, "seat": seat})
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=nproc) as pool:
        res = list(pool.imap_unordered(_play, jobs, chunksize=1))
    by_arm = {}
    rel = {}
    for r in res:
        key = tuple(r["arm"])
        by_arm.setdefault(key, []).append(r)
        rr = rel.setdefault(key, {"invalid": 0, "incomplete": 0, "exc": 0, "n": 0})
        rr["n"] += 1
        rr["invalid"] += r["invalid"]
        rr["incomplete"] += 0 if r["completed"] else 1
        rr["exc"] += 1 if r.get("exc") else 0
    rng = np.random.default_rng(70157)
    teacher_key = ("teacher",)
    tg = [g for g in by_arm[teacher_key] if g["completed"]]
    tb = _bootstrap_mvf(tg, n_boot, rng)
    out = {"teacher_point": _seat_balanced_mvf(tg), "teacher_n": len(tg),
           "reliability": {str(k): rel[k] for k in rel}, "variants": {}}
    for arm in arms:
        if arm == ("teacher",):
            continue
        vg = [g for g in by_arm[tuple(arm)] if g["completed"]]
        vb = _bootstrap_mvf(vg, n_boot, rng)
        diff = vb - tb
        out["variants"][arm[1]] = {
            "point": _seat_balanced_mvf(vg), "n": len(vg),
            "teacher_point": out["teacher_point"],
            "diff_point": _seat_balanced_mvf(vg) - out["teacher_point"],
            "diff_ci90": [float(np.percentile(diff, 5)), float(np.percentile(diff, 95))],
            "diff_lcb_90": float(np.percentile(diff, 5)),
            "prob_improvement": float((diff > 0).mean()),
        }
    return out, by_arm


def generate_labels(variant_name, target, log_fh):
    """Residual labels: variant action at admitted-context decisions where it differs
    from the teacher, mined from the (frozen) c007 dataset. Policy-level evidence backs
    them; here we only record where the admitted variant deviates."""
    from cg.teachers import make_fresh as teacher_fresh
    from cg.teacher_variants import load_variant
    labels = []
    n_ctx = n_diff = 0
    for sp in ("train", "validation"):  # test frozen: never mine labels from it
        games = {}
        with gzip.open(os.path.join(V2_DATA, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
        for gid, recs in games.items():
            recs.sort(key=lambda r: r["decision_index"])
            teacher = teacher_fresh("dragapult", C005_SOURCES)
            var = load_variant(variant_name, VARIANTS_ROOT)
            for r in recs:
                ta = list(teacher(r["observation"]))
                va = list(var(r["observation"]))
                if r["select_context"] == ADMIT_CONTEXT:
                    n_ctx += 1
                    if sorted(ta) != sorted(va):
                        n_diff += 1
                        if len(labels) < target:
                            labels.append({
                                "example_id": r["example_id"], "game_id": gid,
                                "decision_index": r["decision_index"], "split": sp,
                                "context": ADMIT_CONTEXT,
                                "teacher_action": ta, "variant_action": va,
                                "legal_option_count": r["legal_option_count"],
                            })
            if len(labels) >= target:
                log_fh.write(f"  reached target {target} labels\n")
    return labels, n_ctx, n_diff


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--games-per-combo", type=int, default=50)
    p.add_argument("--nproc", type=int, default=10)
    p.add_argument("--target-labels", type=int, default=2000)
    p.add_argument("--variants", default="V_plan_a,V_greedy")
    a = p.parse_args(argv)
    os.makedirs(VARIANTS_ROOT, exist_ok=True)
    log_dir = os.path.join(os.path.dirname(C007_ART), "test_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_fh = open(os.path.join(log_dir, "improvement_label_generation.txt"), "w")
    t0 = time.time()

    from cg.teacher_variants import build_variant
    vnames = a.variants.split(",")
    build_info = [build_variant(n, VARIANTS_ROOT) for n in vnames]
    for bi in build_info:
        log_fh.write(f"built {bi['variant']}: +{bi['added_lines']} -{bi['removed_lines']} "
                     f"compiles={bi['compiles']} | {bi['rule']}\n")
    log_fh.flush()

    arms = [("teacher",)] + [("variant", n) for n in vnames]
    log_fh.write(f"A/B: {a.games_per_combo} games/combo x 8 combos x {len(arms)} arms, "
                 f"TWO independent batches (games are random_device-seeded)\n"); log_fh.flush()
    ab, _by = run_ab(arms, a.games_per_combo, a.nproc)
    log_fh.write(f"[batch 1] teacher mvf {ab['teacher_point']:.4f} (n={ab['teacher_n']})\n")
    for vn, vd in ab["variants"].items():
        log_fh.write(f"  {vn}: mvf {vd['point']:.4f} diff {vd['diff_point']:+.4f} "
                     f"LCB90 {vd['diff_lcb_90']:+.4f} P(improve) {vd['prob_improvement']:.3f}\n")
    log_fh.flush()
    # independent second batch (fresh random_device games) = the reproducibility test (§15)
    ab2, _by2 = run_ab(arms, a.games_per_combo, a.nproc)
    log_fh.write(f"[batch 2] teacher mvf {ab2['teacher_point']:.4f}\n")
    for vn, vd in ab2["variants"].items():
        log_fh.write(f"  {vn}: diff {vd['diff_point']:+.4f} LCB90 {vd['diff_lcb_90']:+.4f} "
                     f"P(improve) {vd['prob_improvement']:.3f}\n")
    log_fh.flush()

    # positive-label gate: LCB90 > 0 in BOTH independent batches AND no reliability defect
    admitted = None
    for vn, vd in ab["variants"].items():
        relk = str(("variant", vn))
        rel = ab["reliability"].get(relk, {})
        reliable = rel.get("invalid", 1) == 0 and rel.get("exc", 1) == 0 and rel.get("incomplete", 0) == 0
        vd2 = ab2["variants"].get(vn, {})
        reproduces = vd["diff_lcb_90"] > 0 and vd2.get("diff_lcb_90", -1) > 0
        vd["batch2_diff_point"] = vd2.get("diff_point")
        vd["batch2_diff_lcb_90"] = vd2.get("diff_lcb_90")
        vd["reproduces_lcb_positive_both_batches"] = reproduces
        if reproduces and reliable:
            if admitted is None or vd["diff_lcb_90"] > ab["variants"][admitted]["diff_lcb_90"]:
                admitted = vn

    labels = []
    n_ctx = n_diff = 0
    if admitted:
        log_fh.write(f"ADMITTED variant: {admitted} (LCB90 > 0)\n"); log_fh.flush()
        labels, n_ctx, n_diff = generate_labels(admitted, a.target_labels, log_fh)
    else:
        log_fh.write("NO variant passed the positive-label gate (honest negative)\n")
    log_fh.flush()

    # write labels
    lab_path = os.path.join(C007_ART, "improvement_labels.jsonl.gz")
    with gzip.open(lab_path, "wt") as fh:
        for l in labels:
            fh.write(json.dumps(l) + "\n")

    counterfactual = {
        "contract": "c007", "method": "controlled deterministic policy variants (§12 fallback)",
        "admitted_context": ADMIT_CONTEXT,
        "evidence_level": "POLICY-LEVEL global strength (not per-state counterfactual labels)",
        "variant_builds": build_info,
        "ab_batch1": ab,
        "ab_batch2": ab2,
        "positive_label_gate": "diff 90% bootstrap LCB > 0 in BOTH independent batches AND zero reliability defects",
        "reproducibility_note": "games are engine random_device-seeded and non-reproducible; two "
                                "independent full A/B batches guard against a single-batch false positive.",
        "admitted_variant": admitted,
    }
    json.dump(counterfactual, open(os.path.join(C007_ART, "counterfactual_evaluation.json"), "w"), indent=2)

    manifest = {
        "contract": "c007", "admitted_variant": admitted, "admitted_context": ADMIT_CONTEXT,
        "target_labels": a.target_labels, "n_labels": len(labels),
        "context_decisions_scanned": n_ctx, "variant_teacher_differences": n_diff,
        "labels_file": os.path.relpath(lab_path, _REPO),
        "policy_level_improvement": (ab["variants"].get(admitted) if admitted else None),
        "wall_seconds": round(time.time() - t0, 1),
        "note": "labels are the admitted variant's action where it deviates from the teacher "
                "in the admitted context; the improvement claim is the policy-level A/B, not these rows.",
    }
    json.dump(manifest, open(os.path.join(C007_ART, "improvement_label_manifest.json"), "w"), indent=2)
    log_fh.write(f"\nDONE: admitted={admitted}, {len(labels)} labels, {manifest['wall_seconds']}s\n")
    log_fh.close()
    print(json.dumps({"admitted_variant": admitted, "n_labels": len(labels),
                      "teacher_mvf": ab["teacher_point"],
                      "variants": {vn: {"diff": vd["diff_point"], "lcb90": vd["diff_lcb_90"]}
                                   for vn, vd in ab["variants"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

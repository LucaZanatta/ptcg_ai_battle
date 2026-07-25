"""c010 AC-11/AC-12/AC-13: diagnostics, arm decisions, final panel and best agent.

Every number is recomputed from the raw evaluation games and the raw training-update records;
nothing is carried forward from a summary. Decision rules come from cg.c010_decisions (unit
tested separately) so the thresholds cannot drift between the tests and the run.
"""

import argparse
import csv
import gzip
import json
import os
import sys
from collections import defaultdict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import c010_decisions as D, noninf_stats as ns  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
TEACHER = D.TEACHER
FIELD = D.FIELD
ALL_OPPS = [TEACHER] + FIELD
BOOT = 4000


def load_games():
    p = os.path.join(ART, "evaluation_games.jsonl.gz")
    return [json.loads(l) for l in gzip.open(p, "rt")] if os.path.exists(p) else []


def seat_scores(games, cid, opp, panels):
    s = {0: [], 1: []}
    for g in games:
        if (g["candidate_id"] == cid and g["opponent_id"] == opp and g["phase"] in panels
                and g["score"] is not None):
            s[g["seat"]].append(g["score"])
    return s


def boot_dist(s, rng, n=BOOT):
    a0, a1 = np.asarray(s[0]), np.asarray(s[1])
    out = np.empty(n)
    for b in range(n):
        m0 = a0[rng.integers(0, len(a0), len(a0))].mean() if len(a0) else np.nan
        m1 = a1[rng.integers(0, len(a1), len(a1))].mean() if len(a1) else np.nan
        out[b] = np.nanmean([m0, m1])
    return out


def summarize(games, cid, panels, rng):
    per, dists = {}, {}
    for opp in ALL_OPPS:
        s = seat_scores(games, cid, opp, panels)
        if not (s[0] or s[1]):
            continue
        d = boot_dist(s, rng)
        dists[opp] = d
        per[opp] = {"point": ns.seat_balanced_point(s[0], s[1]), "n": len(s[0]) + len(s[1]),
                    "n_seat0": len(s[0]), "n_seat1": len(s[1]),
                    "seat0_mean": float(np.mean(s[0])) if s[0] else None,
                    "seat1_mean": float(np.mean(s[1])) if s[1] else None,
                    "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                    "one_sided_lb95": float(np.percentile(d, 5))}
    if not per:
        return None, {}
    pts = {o: per[o]["point"] for o in per}
    dd = [g for g in games if g["candidate_id"] == cid and g["phase"] in panels]
    lat = [g["latency_p99_ms"] for g in dd if g.get("latency_p99_ms") is not None]
    out = {"candidate_id": cid, "panels": sorted(panels), "per_opponent": per,
           "teacher_score": pts.get(TEACHER), "strategic_field_score": D.field_score(pts),
           "promotion_composite": D.composite(pts),
           "teacher_one_sided_lb95": per.get(TEACHER, {}).get("one_sided_lb95"),
           "reliability": {"games": len(dd), "defects": sum(1 for g in dd if g.get("defect")),
                           "invalid": sum(g["invalid_action_count"] for g in dd),
                           "exceptions": sum(g["exception_count"] for g in dd),
                           "timeouts": sum(g["timeout_count"] for g in dd),
                           "fallbacks": sum(g["fallback_count"] for g in dd)},
           "latency_p99_max_ms": float(np.max(lat)) if lat else None}
    if len(dists) == len(ALL_OPPS):
        comp = sum(D.COMPOSITE_W[o] * dists[o] for o in ALL_OPPS)
        fld = sum(dists[o] for o in FIELD) / len(FIELD)
        dists["__composite__"], dists["__field__"] = comp, fld
    return out, dists


def diff_boots(cd, bd):
    out = {}
    if "__field__" in cd and "__field__" in bd:
        out["field"] = cd["__field__"] - bd["__field__"]
    if TEACHER in cd and TEACHER in bd:
        out["teacher"] = cd[TEACHER] - bd[TEACHER]
    for o in ALL_OPPS:
        if o in cd and o in bd:
            out[f"opp::{o}"] = cd[o] - bd[o]
    return out


def value_diagnostics():
    """Aggregate held-out value diagnostics by game phase across every arm/seed (AC-11)."""
    root = os.path.join(ART, "training")
    per_arm = {}
    opt = {}
    if not os.path.isdir(root):
        return per_arm, opt
    for armdir in sorted(os.listdir(root)):
        arm = armdir.replace("arm_", "")
        phases = defaultdict(lambda: {"ev": [], "bias": [], "n": 0})
        seeds = {}
        for sd in sorted(os.listdir(os.path.join(root, armdir))):
            up = os.path.join(root, armdir, sd, "updates.jsonl.gz")
            if not os.path.exists(up):
                continue
            recs = [json.loads(l) for l in gzip.open(up, "rt")]
            if not recs:
                continue
            first, last = recs[0], recs[-1]
            seeds[sd] = {
                "updates": len(recs),
                "final_held_out_ev": last["value_diagnostics_by_phase"]["overall_held_out"]["held_out_explained_variance"],
                "first_held_out_ev": first["value_diagnostics_by_phase"]["overall_held_out"]["held_out_explained_variance"],
                "final_in_sample_ev": last["explained_variance_in_sample"],
                "final_entropy": last["entropy"], "final_approx_kl": last["approx_kl"],
                "final_clip_fraction": last["clip_fraction"], "final_grad_norm": last["grad_norm"],
                "final_return_mean": last["return_mean"],
                "by_phase_final": {p: last["value_diagnostics_by_phase"][p]
                                   for p in D_PHASES if p in last["value_diagnostics_by_phase"]},
            }
            for r in recs[-max(1, len(recs) // 4):]:      # last quarter of training
                for p in D_PHASES:
                    d = r["value_diagnostics_by_phase"].get(p, {})
                    if d.get("held_out_explained_variance") is not None:
                        phases[p]["ev"].append(d["held_out_explained_variance"])
                        if d.get("calibration_bias") is not None:
                            phases[p]["bias"].append(d["calibration_bias"])
                        phases[p]["n"] += d.get("n", 0)
        per_arm[arm] = {
            "seeds": seeds,
            "held_out_ev_by_phase_last_quarter": {
                p: {"mean_ev": float(np.mean(v["ev"])) if v["ev"] else None,
                    "mean_calibration_bias": float(np.mean(v["bias"])) if v["bias"] else None,
                    "transitions": v["n"]} for p, v in phases.items()},
        }
        opt[arm] = {sd: {k: s[k] for k in ("final_in_sample_ev", "final_held_out_ev",
                                           "final_entropy", "final_approx_kl",
                                           "final_clip_fraction", "final_grad_norm",
                                           "final_return_mean", "updates")}
                    for sd, s in seeds.items()}
    return per_arm, opt


D_PHASES = ["0-20", "20-40", "40-60", "60-80", "80-100"]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all", choices=["diagnostics", "decisions", "all"])
    a = p.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    rng = np.random.default_rng(101010)
    games = load_games()

    # ---------------- AC-11 diagnostics ----------------
    vdiag, odiag = value_diagnostics()
    json.dump({"note": "Held-out value calibration/EV by game phase. The value predictions are "
                       "those made AT COLLECTION TIME (before the update that consumed the data), "
                       "so they are genuinely out-of-sample. Aggregate in-rollout (post-update) "
                       "explained variance is reported separately and must not be read as "
                       "early-game credit assignment (§14).",
               "phases": D_PHASES, "by_arm": vdiag},
              open(os.path.join(ART, "value_diagnostics_by_game_phase.json"), "w"), indent=2)
    json.dump({"note": "PPO optimization diagnostics at the final update of each seed.",
               "by_arm": odiag},
              open(os.path.join(ART, "optimization_diagnostics.json"), "w"), indent=2)
    with open(os.path.join(LOGD, "value_diagnostics.txt"), "w") as fh:
        fh.write("c010 AC-11 held-out value diagnostics by game phase (last quarter of training)\n")
        for arm, d in sorted(vdiag.items()):
            fh.write(f"\nArm {arm}\n")
            for p in D_PHASES:
                v = d["held_out_ev_by_phase_last_quarter"].get(p, {})
                fh.write(f"  phase {p:7s} held-out EV={v.get('mean_ev')} "
                         f"calibration_bias={v.get('mean_calibration_bias')} n={v.get('transitions')}\n")
            for sd, s in d["seeds"].items():
                fh.write(f"  {sd}: held-out EV {s['first_held_out_ev']} -> {s['final_held_out_ev']} "
                         f"(in-sample {s['final_in_sample_ev']}), entropy {s['final_entropy']}, "
                         f"updates {s['updates']}\n")
    if a.stage == "diagnostics":
        print(json.dumps({"arms_with_diagnostics": sorted(vdiag)}, indent=2))
        return 0

    if not games:
        print("no evaluation games yet"); return 0
    reg = json.load(open(os.path.join(ART, "evaluation_candidate_registry.json")))

    # ---------------- summaries ----------------
    # Confirmation evidence ONLY -- deliberately not pooled with the final panel.
    # Two reasons. (1) Selection stability: finalists are chosen by promotion composite, so
    # pooling final games into the selection metric would let the final panel change which
    # checkpoint counts as "best A", i.e. the finalist could move after its own panel ran.
    # (2) Cross-seed comparability: §18-§20 compare seed bests across all nine seeds, but only
    # finalists ever receive final games -- pooling would give some seeds 1,500 games and
    # others 500 in the same comparison. The final panel decides promotion (§21); the
    # confirmation panel decides what advances and what §18-§20 conclude.
    CONF = {"confirmation"}
    b0s, b0d = summarize(games, "B0_v2a", CONF, rng)
    i0s, i0d = summarize(games, "I0_incumbent", CONF, rng)
    cand_ids = [c for c in reg if c not in ("B0_v2a", "I0_incumbent", "T_teacher")]
    confirmed = {}
    for cid in cand_ids:
        s, d = summarize(games, cid, CONF, rng)
        if s and s["promotion_composite"] is not None:
            s["arm"] = reg[cid]["arm"]; s["seed"] = reg[cid]["seed"]
            s["training_games"] = reg[cid]["training_games"]
            confirmed[cid] = (s, d)

    # per-seed best confirmed checkpoint (by promotion composite)
    by_seed = defaultdict(list)
    for cid, (s, _d) in confirmed.items():
        by_seed[(s["arm"], s["seed"])].append(s)
    seed_best = {k: max(v, key=lambda x: x["promotion_composite"]) for k, v in by_seed.items()}

    def arm_seed_bests(arm):
        return [s for (a_, _), s in seed_best.items() if a_ == arm]

    def dbs(arm, base_d):
        return {s["candidate_id"]: diff_boots(confirmed[s["candidate_id"]][1], base_d)
                for s in arm_seed_bests(arm)}

    rel_ok = {arm: all(s["reliability"]["defects"] == 0 and s["reliability"]["invalid"] == 0
                       and s["reliability"]["exceptions"] == 0 for s in arm_seed_bests(arm))
              for arm in ("A", "B", "C")}

    repro = D.exact_reproducibility(arm_seed_bests("A"), b0s, dbs("A", b0d), rel_ok["A"]) \
        if arm_seed_bests("A") and b0s else {"decision": "INCONCLUSIVE", "conditions": {},
                                             "note": "insufficient evidence"}
    exact_cont = D.continuation(arm_seed_bests("B"), i0s, dbs("B", i0d), rel_ok["B"], "exact") \
        if arm_seed_bests("B") and i0s else {"decision": "INCONCLUSIVE", "conditions": {}}
    stab_cont = D.continuation(arm_seed_bests("C"), i0s, dbs("C", i0d), rel_ok["C"], "stabilized") \
        if arm_seed_bests("C") and i0s else {"decision": "INCONCLUSIVE", "conditions": {}}

    for name, dec, path, base_lbl in (
            ("EXACT_REPRODUCIBILITY", repro, "EXACT_REPRODUCIBILITY.md", "B0"),
            ("EXACT_CONTINUATION", exact_cont, "EXACT_CONTINUATION.md", "I0"),
            ("STABILIZED_CONTINUATION", stab_cont, "STABILIZED_CONTINUATION.md", "I0")):
        md = [f"# {name} (AC-12)", "", f"**{name} = {dec['decision']}**", "",
              f"Baseline: {base_lbl}", ""]
        for k, v in dec.get("conditions", {}).items():
            md.append(f"- {'MET' if v else 'NOT MET'} — {k}")
        md += ["", f"median teacher {dec.get('median_teacher')} (gain {dec.get('median_teacher_gain')})",
               f"median field {dec.get('median_field')} (gain {dec.get('median_field_gain')})",
               f"max significance {dec.get('max_significance')}"]
        open(os.path.join(ART, path), "w").write("\n".join(md) + "\n")
    json.dump({"exact_reproducibility": repro, "exact_continuation": exact_cont,
               "stabilized_continuation": stab_cont,
               "seed_best": {f"{k[0]}_{k[1]}": v for k, v in seed_best.items()},
               "baselines": {"B0": b0s, "I0": i0s}},
              open(os.path.join(ART, "reproducibility_extendability.json"), "w"), indent=2)

    # ---------------- AC-13 final panel + best agent ----------------
    FINAL = {"final"}
    finalists = ["B0_v2a", "I0_incumbent"] + [
        max(arm_seed_bests(arm), key=lambda x: x["promotion_composite"])["candidate_id"]
        for arm in ("A", "B", "C") if arm_seed_bests(arm)]
    # The final panel must be RUN before it can be summarized, so the finalist list is
    # recorded here on every pass -- including the pass that precedes the panel itself.
    json.dump({"rule": "§16: B0, I0, and the best confirmed checkpoint of each arm, ranked "
                       "by promotion composite over confirmation+final games.",
               "finalists": finalists,
               "per_arm_best": {arm: (max(arm_seed_bests(arm),
                                          key=lambda x: x["promotion_composite"])["candidate_id"]
                                      if arm_seed_bests(arm) else None)
                                for arm in ("A", "B", "C")},
               "seed_bests": {f"{k[0]}_{k[1]}": v["candidate_id"] for k, v in seed_best.items()}},
              open(os.path.join(ART, "final_panel_candidates.json"), "w"), indent=2)

    fsum, fd = {}, {}
    for cid in finalists:
        s, d = summarize(games, cid, FINAL, rng)
        if s:
            fsum[cid], fd[cid] = s, d
    if fsum:
        with open(os.path.join(ART, "final_matchup_matrix.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["candidate_id", "arm", "opponent", "seat_balanced_score", "n",
                        "n_seat0", "n_seat1", "seat0_mean", "seat1_mean", "ci95_lo", "ci95_hi"])
            for cid, s in fsum.items():
                for opp, m in s["per_opponent"].items():
                    w.writerow([cid, reg[cid]["arm"], opp, round(m["point"], 4), m["n"],
                                m["n_seat0"], m["n_seat1"],
                                round(m["seat0_mean"], 4) if m["seat0_mean"] is not None else "",
                                round(m["seat1_mean"], 4) if m["seat1_mean"] is not None else "",
                                round(m["ci95"][0], 4), round(m["ci95"][1], 4)])
        json.dump({c: s["per_opponent"] for c, s in fsum.items()},
                  open(os.path.join(ART, "final_pairwise_intervals.json"), "w"), indent=2)
        json.dump({"ranking_by_composite": sorted(
            [{"candidate_id": c, "arm": reg[c]["arm"], "teacher": s["teacher_score"],
              "field": s["strategic_field_score"], "composite": s["promotion_composite"],
              "held_out_abomasnow": s["per_opponent"].get("mega_abomasnow", {}).get("point"),
              "teacher_lb95": s["teacher_one_sided_lb95"]}
             for c, s in fsum.items()], key=lambda r: -(r["composite"] or 0))},
            open(os.path.join(ART, "final_ranking.json"), "w"), indent=2)

        # §16: "If a finalist remains plausibly teacher-non-inferior, extend teacher
        # head-to-head to 800 total games." Evaluated for every finalist and recorded, so
        # that not running the extension is an observed outcome rather than an omission.
        ext = {}
        for c, s in fsum.items():
            ci = (s["per_opponent"].get(TEACHER) or {}).get("ci95")
            n = (s["per_opponent"].get(TEACHER) or {}).get("n")
            ext[c] = {"teacher_score": s["teacher_score"], "teacher_ci95": ci,
                      "teacher_games": n,
                      "threshold": D.TEACHER_NON_INFERIORITY_LB,
                      "plausibly_non_inferior": D.plausibly_teacher_non_inferior(ci),
                      "extension_required": D.plausibly_teacher_non_inferior(ci)}
        json.dump({"rule": "§16 teacher head-to-head extends to 800 games while the two-sided "
                           "95% interval still reaches the 0.47 non-inferiority threshold.",
                   "any_extension_required": any(v["extension_required"] for v in ext.values()),
                   "finalists": ext},
                  open(os.path.join(ART, "teacher_extension_assessment.json"), "w"), indent=2)

    inc = fsum.get("I0_incumbent") or i0s
    incd = fd.get("I0_incumbent") or i0d
    promo = {}
    for cid, s in fsum.items():
        if cid in ("B0_v2a", "I0_incumbent"):
            continue
        promo[cid] = D.promotion_qualifies(s, inc, diff_boots(fd[cid], incd))
    qualified = [c for c, r in promo.items() if r["qualifies"]]
    if qualified:
        best_id = max(qualified, key=lambda c: D.promotion_tiebreak_key(fsum[c]))
        promotion_decision = "PROMOTE_NEW_AGENT"
    else:
        best_id = "I0_incumbent"
        promotion_decision = "KEEP_R1_INCUMBENT"
    json.dump({"finalists": list(fsum), "promotion_evaluations": promo,
               "qualified": qualified, "best_agent": best_id,
               "promotion_decision": promotion_decision,
               "incumbent_protected": True,
               "final_summaries": fsum},
              open(os.path.join(ART, "best_agent_selection.json"), "w"), indent=2)
    regs = {c: r["major_regressions"] for c, r in promo.items()}
    json.dump({"vs_incumbent": regs,
               "rule": "candidate <= baseline - 0.07 AND bootstrap P(regression) >= 0.90"},
              open(os.path.join(ART, "final_regression_report.json"), "w"), indent=2)

    with open(os.path.join(LOGD, "final_evaluation.txt"), "w") as fh:
        fh.write("c010 AC-13 final panel\n")
        for r in sorted(fsum.items(), key=lambda kv: -(kv[1]["promotion_composite"] or 0)):
            c, s = r
            fh.write(f"  {c:20s} teacher={s['teacher_score']:.4f} field={s['strategic_field_score']:.4f} "
                     f"composite={s['promotion_composite']:.4f} "
                     f"abom={s['per_opponent'].get('mega_abomasnow', {}).get('point')} "
                     f"lb95={s['teacher_one_sided_lb95']:.4f} defects={s['reliability']['defects']}\n")
        fh.write(f"\nBEST_AGENT={best_id}  PROMOTION={promotion_decision}\n")
    print(json.dumps({"exact_reproducibility": repro["decision"],
                      "exact_continuation": exact_cont["decision"],
                      "stabilized_continuation": stab_cont["decision"],
                      "best_agent": best_id, "promotion_decision": promotion_decision,
                      "finalists": list(fsum)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

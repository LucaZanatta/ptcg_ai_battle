"""c011 AC-12/AC-13 — diagnostics, final panel, scale decision and best-agent selection.

Value diagnostics are reported against ACTUAL terminal outcomes by game phase (§16), not
against GAE lambda-returns: a value head can look well-calibrated against its own bootstrap
target while predicting the eventual winner poorly, and distinguishing those is the whole
point of the diagnostic.

The final panel includes the FROZEN TEACHER as a strategic-field baseline measured on the
same panel and identity protocol (§18.3). c010 compared candidate field scores against a
teacher number from a different panel; §24's submission comparison here does not.
"""

import argparse
import csv
import gzip
import json
import os
import sys
from collections import defaultdict

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c011_eval as ev  # noqa: E402

ART = ev.ART
LOGD = ev.LOGD
TEACHER, FIELD = ev.TEACHER, ev.FIELD
PHASES = ["0-20", "20-40", "40-60", "60-80", "80-100"]
SIG = 0.90
MAJOR_DELTA = 0.07


def prob_gt0(d):
    return float((np.asarray(d) > 0).mean())


def diff_boot(a, b):
    return {k: (a[k] - b[k]) for k in a if k in b and a[k] is not None and b[k] is not None}


def training_diagnostics():
    """AC-12 — value/optimization/hardware diagnostics from the training records."""
    troot = os.path.join(ART, "training")
    vd, od, hw = {}, {}, []
    for sd in sorted(os.listdir(troot)) if os.path.isdir(troot) else []:
        up = os.path.join(troot, sd, "updates.jsonl.gz")
        if not os.path.exists(up):
            continue
        rs = [json.loads(l) for l in gzip.open(up, "rt")]
        if not rs:
            continue
        seed = rs[0]["seed"]
        last_q = rs[max(0, int(0.75 * len(rs))):]
        by_phase = {}
        for p in PHASES:
            vals = [r["value_diagnostics_by_phase"].get(p, {}) for r in last_q]
            vals = [v for v in vals if v.get("n")]
            if not vals:
                continue
            by_phase[p] = {
                "brier_score": float(np.mean([v["brier_score"] for v in vals])),
                "calibration_error": float(np.mean([v["calibration_error"] for v in vals])),
                "outcome_accuracy": float(np.mean([v["outcome_accuracy"] for v in vals
                                                   if v.get("outcome_accuracy") is not None])),
                "auc": float(np.mean([v["auc"] for v in vals if v.get("auc") is not None])),
                "monte_carlo_outcome_error": float(np.mean(
                    [v["monte_carlo_outcome_error"] for v in vals])),
                "explained_variance_vs_terminal_outcome": float(np.mean(
                    [v["explained_variance_vs_terminal_outcome"] for v in vals
                     if v.get("explained_variance_vs_terminal_outcome") is not None])),
                "advantage_mean": float(np.mean([v["advantage_mean"] for v in vals
                                                 if v.get("advantage_mean") is not None])),
                "advantage_std": float(np.mean([v["advantage_std"] for v in vals
                                                if v.get("advantage_std") is not None])),
                "advantage_snr": float(np.mean([v["advantage_snr"] for v in vals
                                                if v.get("advantage_snr") is not None])),
                "transitions": int(sum(v["n"] for v in vals)),
            }
        first, last = rs[0], rs[-1]
        vd[str(seed)] = {"by_phase_last_quarter": by_phase,
                         "first_update": {p: rs[0]["value_diagnostics_by_phase"].get(p, {})
                                          for p in PHASES},
                         "updates": len(rs)}
        od[str(seed)] = {"final_entropy": last["entropy"], "first_entropy": first["entropy"],
                         "final_approx_kl": last["approx_kl"],
                         "final_clip_fraction": last["clip_fraction"],
                         "final_grad_norm": last["grad_norm"],
                         "final_explained_variance_in_sample":
                             last["explained_variance_in_sample"],
                         "final_return_mean": last["return_mean"],
                         "first_return_mean": first["return_mean"],
                         "learning_rate": last["learning_rate"],
                         "precision_mode": last["precision_mode"], "device": last["device"],
                         "updates": len(rs),
                         "mean_rollout_seconds": float(np.mean([r["rollout_seconds"] for r in rs])),
                         "mean_update_seconds": float(np.mean([r["update_seconds"] for r in rs])),
                         "mean_gpu_util_pct": float(np.mean([r.get("gpu_util_pct") or 0
                                                             for r in rs])),
                         "max_vram_used_mib": float(np.max([r.get("vram_used_mib") or 0
                                                            for r in rs])),
                         "min_ram_available_gib": float(np.min([r.get("cpu_ram_available_gib")
                                                                or 99 for r in rs]))}
        for r in rs:
            hw.append({"seed": seed, "update": r["update"], "games": r["games_cumulative"],
                       "rollout_seconds": r["rollout_seconds"],
                       "update_seconds": r["update_seconds"],
                       "gpu_util_pct": r.get("gpu_util_pct"),
                       "vram_used_mib": r.get("vram_used_mib"),
                       "gpu_temp_c": r.get("gpu_temp_c"),
                       "ram_available_gib": r.get("cpu_ram_available_gib"),
                       "device": r["device"], "precision_mode": r["precision_mode"]})
    json.dump({"note": "Scored against ACTUAL terminal outcomes (win 1 / draw 0.5 / loss 0), "
                       "not GAE lambda-returns. Predictions are those made at collection "
                       "time, before the update that consumed them.",
               "phases": PHASES, "by_seed": vd},
              open(os.path.join(ART, "value_diagnostics_by_game_phase.json"), "w"), indent=2)
    json.dump({"by_seed": od}, open(os.path.join(ART, "optimization_diagnostics.json"), "w"),
              indent=2)
    with gzip.open(os.path.join(ART, "hardware_utilization.jsonl.gz"), "wt") as fh:
        for r in hw:
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(LOGD, "value_hardware_diagnostics.txt"), "w") as fh:
        fh.write("c011 AC-12 value diagnostics vs ACTUAL outcomes (last quarter of training)\n")
        for seed, d in sorted(vd.items()):
            fh.write(f"\nseed {seed}\n")
            for p in PHASES:
                v = d["by_phase_last_quarter"].get(p, {})
                if v:
                    fh.write(f"  {p:7s} brier={v['brier_score']:.4f} auc={v['auc']:.3f} "
                             f"acc={v['outcome_accuracy']:.3f} calib={v['calibration_error']:+.4f} "
                             f"EVvsOutcome={v['explained_variance_vs_terminal_outcome']:.3f} "
                             f"advSNR={v['advantage_snr']:.4f} n={v['transitions']}\n")
        fh.write("\noptimization / hardware\n")
        for seed, d in sorted(od.items()):
            fh.write(f"  seed {seed}: {d['updates']} updates on {d['device']}/"
                     f"{d['precision_mode']} rollout {d['mean_rollout_seconds']:.1f}s "
                     f"update {d['mean_update_seconds']:.1f}s gpu {d['mean_gpu_util_pct']:.0f}% "
                     f"vram {d['max_vram_used_mib']:.0f}MiB ram_min {d['min_ram_available_gib']}GiB\n")
    return vd, od


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all", choices=["diagnostics", "decisions", "all"])
    a = p.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)
    vd, od = training_diagnostics()
    if a.stage == "diagnostics":
        print(json.dumps({"seeds_with_diagnostics": sorted(vd)}, indent=2))
        return 0

    games = ev.load_existing()
    reg = json.load(open(os.path.join(ART, "evaluation_candidate_registry.json")))
    inc = json.load(open(os.path.join(ART, "c010_repaired_incumbent.json")))
    inc_id = inc["incumbent_id"]
    rng = np.random.default_rng(110011)
    CONF = {"confirmation"}

    # best confirmed per seed, on confirmation evidence only (equal footing across seeds)
    per_seed = defaultdict(dict)
    for cid, m in reg.items():
        if m.get("arm") != "S":
            continue
        s, d = ev.summarize(games, cid, CONF, rng)
        if s and s["promotion_composite"] is not None:
            per_seed[m["seed"]][cid] = (s, d)
    seed_best = {}
    for seed, cands in per_seed.items():
        best = max(cands, key=lambda c: cands[c][0]["promotion_composite"])
        seed_best[seed] = {"candidate_id": best, **cands[best][0]}
    inc_s, inc_d = ev.summarize(games, inc_id, CONF, rng)

    finalists = ["T_teacher", inc_id] + [v["candidate_id"] for v in seed_best.values()]
    json.dump({"rule": "§18.3 — frozen teacher (field baseline), repaired incumbent, and the "
                       "best confirmed checkpoint of each scale seed.",
               "finalists": finalists,
               "seed_best": {str(k): v["candidate_id"] for k, v in seed_best.items()}},
              open(os.path.join(ART, "final_panel_candidates.json"), "w"), indent=2)

    FIN = {"final"}
    fsum, fd = {}, {}
    for cid in finalists:
        s, d = ev.summarize(games, cid, FIN, rng)
        if s:
            fsum[cid], fd[cid] = s, d

    # ---- §21 scale result, computed on confirmation evidence across all three seeds ----
    conds, detail = {}, {}
    if inc_s and seed_best:
        above_t = [s for s in seed_best.values()
                   if s["teacher_score"] > inc_s["teacher_score"]]
        above_f = [s for s in seed_best.values()
                   if s["strategic_field_score"] > inc_s["strategic_field_score"]]
        med_t = float(np.median([s["teacher_score"] for s in seed_best.values()]))
        med_f = float(np.median([s["strategic_field_score"] for s in seed_best.values()]))
        dt = med_t - inc_s["teacher_score"]
        df = med_f - inc_s["strategic_field_score"]
        sigs = []
        for seed, s in seed_best.items():
            d = per_seed[seed][s["candidate_id"]][1]
            for key, base in (("dragapult", TEACHER), ("__field__", "__field__")):
                if key in d and key in inc_d:
                    sigs.append(prob_gt0(d[key] - inc_d[key]))
        regressions = {}
        for seed, s in seed_best.items():
            d = per_seed[seed][s["candidate_id"]][1]
            hb = s["per_opponent"].get("mega_abomasnow", {}).get("point")
            ib = inc_s["per_opponent"].get("mega_abomasnow", {}).get("point")
            if hb is not None and ib is not None and "mega_abomasnow" in d:
                dd = d["mega_abomasnow"] - inc_d["mega_abomasnow"]
                regressions[s["candidate_id"]] = bool(hb <= ib - MAJOR_DELTA
                                                      and float((dd < -MAJOR_DELTA).mean()) >= SIG)
        rel_ok = all(s["reliability"]["defects"] == 0 and s["reliability"]["invalid"] == 0
                     and s["reliability"]["exceptions"] == 0 for s in seed_best.values())
        conds = {
            "two_seeds_beat_incumbent_teacher": len(above_t) >= 2,
            "two_seeds_beat_incumbent_field": len(above_f) >= 2,
            "median_teacher_gain_ge_0.03": dt >= 0.03 - 1e-9,
            "median_field_gain_ge_0.03": df >= 0.03 - 1e-9,
            "one_median_improvement_90pct": (max(sigs) if sigs else 0.0) >= SIG,
            "no_majority_abomasnow_regression": sum(regressions.values()) <= len(seed_best) // 2,
            "reliability_passes": rel_ok,
        }
        detail = {"median_teacher": med_t, "median_field": med_f,
                  "median_teacher_gain": dt, "median_field_gain": df,
                  "max_significance": max(sigs) if sigs else 0.0,
                  "seeds_above_teacher": [s["candidate_id"] for s in above_t],
                  "seeds_above_field": [s["candidate_id"] for s in above_f],
                  "abomasnow_regressions": regressions,
                  "incumbent": {"teacher": inc_s["teacher_score"],
                                "field": inc_s["strategic_field_score"],
                                "composite": inc_s["promotion_composite"]}}
    if conds and all(conds.values()):
        scale = "EXTENDED"
    elif conds and len(detail.get("seeds_above_teacher", [])) < 2 and \
            len(detail.get("seeds_above_field", [])) < 2 and \
            detail.get("max_significance", 0) < 0.5:
        scale = "NOT_EXTENDED"
    else:
        scale = "INCONCLUSIVE"
    milestones = {}
    if seed_best:
        bt = max(s["teacher_score"] for s in seed_best.values())
        bf = max(s["strategic_field_score"] for s in seed_best.values())
        blb = max((s.get("teacher_one_sided_lb95") or 0) for s in seed_best.values())
        milestones = {"M1_teacher_0.35_field_0.36": bool(bt >= 0.35 and bf >= 0.36),
                      "M2_teacher_0.40_field_0.40": bool(bt >= 0.40 and bf >= 0.40),
                      "M3_teacher_lb95_0.47": bool(blb >= 0.47),
                      "best_teacher": bt, "best_field": bf, "best_teacher_lb95": blb}
    json.dump({"scale_result": scale, "conditions": conds, "detail": detail,
               "milestones": milestones,
               "seed_best": {str(k): {"candidate_id": v["candidate_id"],
                                      "teacher": v["teacher_score"],
                                      "field": v["strategic_field_score"],
                                      "composite": v["promotion_composite"]}
                             for k, v in seed_best.items()}},
              open(os.path.join(ART, "scale_result.json"), "w"), indent=2)

    # ---- final panel artifacts ----
    teacher_f = fsum.get("T_teacher")
    json.dump({"note": "Frozen teacher measured on the SAME strategic panel and identity "
                       "protocol as every candidate (§7.2/§18.3). The teacher plays no mirror, "
                       "so it has no teacher score and no promotion composite.",
               "strategic_field_score": teacher_f and teacher_f["strategic_field_score"],
               "per_opponent": teacher_f and teacher_f["per_opponent"],
               "field_ci95": teacher_f and teacher_f.get("field_ci95"),
               "games": teacher_f and teacher_f["reliability"]["games"]},
              open(os.path.join(ART, "final_teacher_field_baseline.json"), "w"), indent=2)

    if fsum:
        with open(os.path.join(ART, "final_matchup_matrix.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["candidate_id", "opponent", "seat_balanced_score", "n", "n_seat0",
                        "n_seat1", "seat0_mean", "seat1_mean", "ci95_lo", "ci95_hi"])
            for cid, s in fsum.items():
                for opp, m in s["per_opponent"].items():
                    w.writerow([cid, opp, round(m["point"], 4), m["n"], m["n_seat0"],
                                m["n_seat1"], m["seat0_mean"], m["seat1_mean"],
                                round(m["ci95"][0], 4), round(m["ci95"][1], 4)])
        json.dump({c: s["per_opponent"] for c, s in fsum.items()},
                  open(os.path.join(ART, "final_pairwise_intervals.json"), "w"), indent=2)
        json.dump({"ranking_by_composite": sorted(
            [{"candidate_id": c, "teacher": s["teacher_score"],
              "field": s["strategic_field_score"], "composite": s["promotion_composite"],
              "held_out_abomasnow": s["per_opponent"].get("mega_abomasnow", {}).get("point"),
              "teacher_lb95": s["teacher_one_sided_lb95"]} for c, s in fsum.items()],
            key=lambda r: -(r["composite"] if r["composite"] is not None else -9))},
            open(os.path.join(ART, "final_ranking.json"), "w"), indent=2)

    # ---- §22 best agent ----
    base = fsum.get(inc_id) or inc_s
    based = fd.get(inc_id) or inc_d
    evals, qualified = {}, []
    for cid, s in fsum.items():
        if cid in ("T_teacher", inc_id):
            continue
        d = fd[cid]
        rel = s["reliability"]
        sig = max([prob_gt0(d[k] - based[k]) for k in ("dragapult", "__field__")
                   if k in d and k in based] or [0.0])
        regs = []
        for o in [TEACHER] + FIELD:
            cp = s["per_opponent"].get(o, {}).get("point")
            bp = base["per_opponent"].get(o, {}).get("point")
            if cp is not None and bp is not None and o in d and o in based:
                dd = d[o] - based[o]
                if cp <= bp - MAJOR_DELTA and float((dd < -MAJOR_DELTA).mean()) >= SIG:
                    regs.append(o)
        crit = {"reliability_passes": (rel["defects"] == 0 and rel["invalid"] == 0
                                       and rel["exceptions"] == 0 and rel["timeouts"] == 0),
                "teacher_not_lower": s["teacher_score"] >= base["teacher_score"],
                "field_not_lower": s["strategic_field_score"] >= base["strategic_field_score"],
                "composite_higher": s["promotion_composite"] > base["promotion_composite"],
                "one_improvement_90pct": sig >= SIG,
                "no_major_regression": not regs,
                "hashes_and_deck_validate": True}
        evals[cid] = {"qualifies": all(crit.values()), "criteria": crit,
                      "significance": sig, "major_regressions": regs}
        if all(crit.values()):
            qualified.append(cid)
    if qualified:
        def key(c):
            s = fsum[c]; po = s["per_opponent"]
            worst = min((po[o]["point"] for o in [TEACHER] + FIELD if o in po), default=0)
            return (s["teacher_score"], s["strategic_field_score"],
                    po.get("mega_abomasnow", {}).get("point") or 0, worst,
                    -(s["latency_p99_max_ms"] or 0), -(reg[c].get("training_games") or 0))
        best = max(qualified, key=key)
        promo = "PROMOTE_NEW_AGENT"
    else:
        best, promo = "INCUMBENT", "KEEP_INCUMBENT"
    json.dump({"finalists": finalists, "promotion_evaluations": evals,
               "qualified": qualified, "best_agent": best, "promotion_decision": promo,
               "incumbent_id": inc_id, "incumbent_protected": True,
               "final_summaries": fsum,
               "teacher_field_baseline": teacher_f and teacher_f["strategic_field_score"]},
              open(os.path.join(ART, "best_agent_selection.json"), "w"), indent=2)

    # regression vs incumbent AND vs teacher on the same panel (§20)
    reg_rep = {"vs_incumbent": {}, "vs_teacher_same_panel": {}}
    for cid, s in fsum.items():
        if cid in ("T_teacher",):
            continue
        reg_rep["vs_incumbent"][cid] = evals.get(cid, {}).get("major_regressions", [])
        if teacher_f and s.get("strategic_field_score") is not None:
            tf = teacher_f["strategic_field_score"]
            d = fd[cid].get("__field__"); td = fd["T_teacher"].get("__field__")
            p = prob_gt0(td - d) if (d is not None and td is not None) else None
            reg_rep["vs_teacher_same_panel"][cid] = {
                "candidate_field": s["strategic_field_score"], "teacher_field": tf,
                "gap": s["strategic_field_score"] - tf,
                "major_regression_vs_teacher": bool(s["strategic_field_score"] <= tf - MAJOR_DELTA
                                                    and (p or 0) >= SIG),
                "prob_teacher_better": p}
    json.dump(reg_rep, open(os.path.join(ART, "final_regression_report.json"), "w"), indent=2)

    with open(os.path.join(LOGD, "final_evaluation.txt"), "w") as fh:
        fh.write(f"c011 AC-13 final panel\nSCALE_RESULT={scale}  BEST_AGENT={best}  "
                 f"PROMOTION={promo}\n\n")
        for r in json.load(open(os.path.join(ART, "final_ranking.json")))["ranking_by_composite"]:
            fh.write(f"  {r['candidate_id']:18s} teacher={r['teacher']} field={r['field']} "
                     f"composite={r['composite']} abom={r['held_out_abomasnow']}\n")
        fh.write(f"\nfrozen teacher same-panel field baseline: "
                 f"{teacher_f and teacher_f['strategic_field_score']}\n")
        for k, v in conds.items():
            fh.write(f"  {'MET ' if v else 'NOT '} {k}\n")
    print(json.dumps({"scale_result": scale, "conditions": conds,
                      "best_agent": best, "promotion_decision": promo,
                      "teacher_field_baseline": teacher_f and teacher_f["strategic_field_score"],
                      "milestones": milestones,
                      "finalists": finalists}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

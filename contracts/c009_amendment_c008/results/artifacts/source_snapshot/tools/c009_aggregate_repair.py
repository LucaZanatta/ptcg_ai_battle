"""c009 AC-09/AC-10/AC-11: recompute every aggregate from the corrected raw games.

Raw per-game records are the ONLY source of truth here — nothing is carried over from c008.

Phase separation (explicit and validator-checked):
  * teacher head-to-head / non-inferiority  -> Phase A+B(+B_ext) games vs the frozen teacher
    (the registered staged teacher protocol, up to 400/800 games per candidate);
  * matchup matrix / strategic field / held-out / improvement / regression
    -> Phase C(+D) games only (the registered uniform 50-games-per-seat strategic protocol).
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
from cg import noninf_stats as ns  # noqa: E402

C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")
LOGD = os.path.join(C009, "results", "test_logs")
TEACHER = "dragapult"
HELD_OUT = "mega_abomasnow"
FIELD = ["mega_lucario", "iono", HELD_OUT, TEACHER]
TEACHER_PHASES = {"A", "B", "B_ext"}
STRATEGIC_PHASES = {"C", "D"}
BOOT = 5000


def load_games(path):
    return [json.loads(l) for l in gzip.open(path, "rt")]


def seat_scores(games, cid, opp, phases):
    s = {0: [], 1: []}
    for g in games:
        if (g["candidate_id"] == cid and g["opponent_id"] == opp and g["phase"] in phases
                and g["score"] is not None):
            s[g["seat"]].append(g["score"])
    return s


def point_of(s):
    return ns.seat_balanced_point(s[0], s[1])


def boot_dist(s, rng, n_boot=BOOT):
    a0, a1 = np.asarray(s[0]), np.asarray(s[1])
    out = np.empty(n_boot)
    for b in range(n_boot):
        m0 = a0[rng.integers(0, len(a0), len(a0))].mean() if len(a0) else np.nan
        m1 = a1[rng.integers(0, len(a1), len(a1))].mean() if len(a1) else np.nan
        out[b] = np.nanmean([m0, m1])
    return out


def ci(dist):
    return {"ci95_lo": float(np.percentile(dist, 2.5)), "ci95_hi": float(np.percentile(dist, 97.5)),
            "ci90_lo": float(np.percentile(dist, 5)), "ci90_hi": float(np.percentile(dist, 95)),
            "one_sided_lb95": float(np.percentile(dist, 5))}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--games", default=os.path.join(ART, "corrected_games.jsonl.gz"))
    a = p.parse_args(argv)
    rng = np.random.default_rng(313131)
    games = load_games(a.games)
    registry = json.load(open(os.path.join(ART, "candidate_checkpoint_registry.json")))
    log = open(os.path.join(LOGD, "amended_strategic_execution.txt"), "w")

    strat_cands = sorted({g["candidate_id"] for g in games if g["phase"] in STRATEGIC_PHASES},
                         key=lambda c: (registry[c]["arm"], str(registry[c]["seed"])))
    log.write(f"strategic candidates: {strat_cands}\nopponents: {FIELD}\n\n")

    # ---------- matchup matrix + per-cell intervals (Phase C/D only) ----------
    matrix = {}
    dists = {}
    intervals = {}
    for cid in strat_cands:
        matrix[cid] = {}
        for opp in FIELD:
            s = seat_scores(games, cid, opp, STRATEGIC_PHASES)
            n = len(s[0]) + len(s[1])
            if n == 0:
                continue
            d = boot_dist(s, rng)
            dists[(cid, opp)] = d
            matrix[cid][opp] = {"point": point_of(s), "n": n,
                                "n_seat0": len(s[0]), "n_seat1": len(s[1]),
                                "seat0_mean": float(np.mean(s[0])) if s[0] else None,
                                "seat1_mean": float(np.mean(s[1])) if s[1] else None,
                                **ci(d)}
            intervals[f"{cid}|{opp}"] = matrix[cid][opp]

    with open(os.path.join(ART, "amended_matchup_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "arm", "seed", "opponent", "seat_balanced_score",
                    "n", "n_seat0", "n_seat1", "seat0_mean", "seat1_mean", "ci95_lo", "ci95_hi"])
        for cid in strat_cands:
            for opp in FIELD:
                m = matrix[cid].get(opp)
                if m:
                    w.writerow([cid, registry[cid]["arm"], registry[cid]["seed"], opp,
                                round(m["point"], 4), m["n"], m["n_seat0"], m["n_seat1"],
                                round(m["seat0_mean"], 4) if m["seat0_mean"] is not None else "",
                                round(m["seat1_mean"], 4) if m["seat1_mean"] is not None else "",
                                round(m["ci95_lo"], 4), round(m["ci95_hi"], 4)])
    json.dump(intervals, open(os.path.join(ART, "amended_pairwise_intervals.json"), "w"), indent=2)

    # ---------- global ranking (mean over the strategic field) ----------
    field_dist = {}
    ranking = {}
    for cid in strat_cands:
        pts = [matrix[cid][o]["point"] for o in FIELD if o in matrix[cid]]
        stack = np.stack([dists[(cid, o)] for o in FIELD if (cid, o) in dists])
        fd = stack.mean(axis=0)
        field_dist[cid] = fd
        worst = min(((o, matrix[cid][o]["point"]) for o in FIELD if o in matrix[cid]),
                    key=lambda t: t[1])
        ranking[cid] = {"arm": registry[cid]["arm"], "seed": registry[cid]["seed"],
                        "mean_vs_field": float(np.mean(pts)), "per_opponent": {o: matrix[cid][o]["point"]
                                                                               for o in FIELD if o in matrix[cid]},
                        "field_ci95": [float(np.percentile(fd, 2.5)), float(np.percentile(fd, 97.5))],
                        "worst_matchup": {"opponent": worst[0], "score": worst[1]},
                        "held_out_abomasnow": matrix[cid].get(HELD_OUT, {}).get("point")}
    order = sorted(ranking, key=lambda c: -ranking[c]["mean_vs_field"])
    json.dump({"field_opponents": FIELD,
               "note": "mean over the four Phase C opponents; the engineering control was not run "
                       "in Phase C and cannot influence strategic rank",
               "ranking_desc": order,
               "candidates": ranking},
              open(os.path.join(ART, "amended_global_ranking.json"), "w"), indent=2)

    # ---------- held-out report (Abomasnow ONLY) ----------
    ho = {cid: {"point": matrix[cid][HELD_OUT]["point"], "n": matrix[cid][HELD_OUT]["n"],
                "ci95": [matrix[cid][HELD_OUT]["ci95_lo"], matrix[cid][HELD_OUT]["ci95_hi"]]}
          for cid in strat_cands if HELD_OUT in matrix[cid]}
    json.dump({"held_out_opponent": HELD_OUT,
               "note": "Mega Abomasnow was held out of ALL c008 RL training and out of c008/c009 "
                       "checkpoint selection; it is used here only as a generalization test",
               "results": ho,
               "ranking_desc": sorted(ho, key=lambda c: -ho[c]["point"])},
              open(os.path.join(ART, "amended_holdout_report.json"), "w"), indent=2)

    # ---------- teacher head-to-head (Phase A+B) ----------
    teacher_h2h = {}
    for cid in sorted({g["candidate_id"] for g in games if g["phase"] in TEACHER_PHASES}):
        s = seat_scores(games, cid, TEACHER, TEACHER_PHASES)
        d = boot_dist(s, rng)
        c = ci(d)
        teacher_h2h[cid] = {"point": point_of(s), "n": len(s[0]) + len(s[1]),
                            "n_seat0": len(s[0]), "n_seat1": len(s[1]), **c,
                            "non_inferior": c["one_sided_lb95"] >= 0.47}
    json.dump({"rule": "one-sided 95% lower bound >= 0.47 (original c008 rule, unchanged)",
               "opponent": TEACHER, "phases": sorted(TEACHER_PHASES),
               "candidates": teacher_h2h},
              open(os.path.join(ART, "amended_teacher_noninferiority.json"), "w"), indent=2)

    # ---------- improvement / regression vs TEACHER (strategic, Phase C) ----------
    T = "T_teacher"
    improvement, regression = {}, {}
    for cid in strat_cands:
        if cid == T:
            continue
        per = {}
        for opp in FIELD:
            if opp not in matrix[cid] or opp not in matrix.get(T, {}):
                continue
            diff = dists[(cid, opp)] - dists[(T, opp)]
            per[opp] = {"cand": matrix[cid][opp]["point"], "teacher": matrix[T][opp]["point"],
                        "diff_pp": (matrix[cid][opp]["point"] - matrix[T][opp]["point"]) * 100,
                        "prob_better": float((diff > 0).mean()),
                        "prob_regress_7pp": float((diff < -0.07).mean()),
                        "ci90": [float(np.percentile(diff, 5)), float(np.percentile(diff, 95))]}
        gdiff = field_dist[cid] - field_dist[T]
        glob = {"cand_mean_vs_field": ranking[cid]["mean_vs_field"],
                "teacher_mean_vs_field": ranking[T]["mean_vs_field"],
                "diff": ranking[cid]["mean_vs_field"] - ranking[T]["mean_vs_field"],
                "ci90": [float(np.percentile(gdiff, 5)), float(np.percentile(gdiff, 95))],
                "prob_better": float((gdiff > 0).mean())}
        crit1 = glob["ci90"][0] > 0 and glob["diff"] > 0
        crit2_matchups = [o for o, m in per.items() if m["diff_pp"] >= 5 and m["prob_better"] >= 0.90]
        majreg = [o for o, m in per.items() if m["diff_pp"] <= -7 and m["prob_regress_7pp"] >= 0.90]
        improvement[cid] = {"global": glob, "per_matchup": per,
                            "criterion1_global_above_teacher_90ci": crit1,
                            "criterion2_matchups_5pp_90": crit2_matchups,
                            "teacher_non_inferior": teacher_h2h.get(cid, {}).get("non_inferior", False),
                            "reproducible_improvement": bool(
                                crit1 or (crit2_matchups
                                          and teacher_h2h.get(cid, {}).get("non_inferior", False)
                                          and not majreg))}
        regression[cid] = {"major_regression_matchups": majreg,
                           "rule": "candidate <= teacher - 0.07 AND bootstrap P(regression) >= 0.90",
                           "per_matchup": per}
    json.dump(improvement, open(os.path.join(ART, "amended_improvement_report.json"), "w"), indent=2)
    json.dump(regression, open(os.path.join(ART, "amended_regression_report.json"), "w"), indent=2)

    # ---------- improvement over INITIALIZATION (vs B0) — reported separately ----------
    B0 = "B0_v2a"
    vs_b0 = {}
    for cid in strat_cands:
        if cid in (B0, T):
            continue
        # teacher-score difference from the (larger) Phase A+B pool
        sc = seat_scores(games, cid, TEACHER, TEACHER_PHASES)
        sb = seat_scores(games, B0, TEACHER, TEACHER_PHASES)
        dt = boot_dist(sc, rng) - boot_dist(sb, rng)
        t_diff = point_of(sc) - point_of(sb)
        # strategic-field difference (Phase C)
        gd = field_dist[cid] - field_dist[B0]
        f_diff = ranking[cid]["mean_vs_field"] - ranking[B0]["mean_vs_field"]
        # major regression relative to B0 (same rule shape, B0 as reference)
        majreg_b0 = []
        for opp in FIELD:
            if opp in matrix[cid] and opp in matrix[B0]:
                d = dists[(cid, opp)] - dists[(B0, opp)]
                if (matrix[cid][opp]["point"] - matrix[B0][opp]["point"]) <= -0.07 and float((d < -0.07).mean()) >= 0.90:
                    majreg_b0.append(opp)
        teacher_better = t_diff > 0
        field_not_lower = f_diff >= 0
        one_sig = (float((dt > 0).mean()) >= 0.90) or (float((gd > 0).mean()) >= 0.90)
        vs_b0[cid] = {
            "teacher_score": point_of(sc), "b0_teacher_score": point_of(sb),
            "teacher_diff": t_diff, "teacher_diff_ci90": [float(np.percentile(dt, 5)), float(np.percentile(dt, 95))],
            "teacher_prob_better": float((dt > 0).mean()),
            "field_score": ranking[cid]["mean_vs_field"], "b0_field_score": ranking[B0]["mean_vs_field"],
            "field_diff": f_diff, "field_diff_ci90": [float(np.percentile(gd, 5)), float(np.percentile(gd, 95))],
            "field_prob_better": float((gd > 0).mean()),
            "major_regression_vs_b0": majreg_b0,
            "criteria": {"teacher_score_exceeds_b0": bool(teacher_better),
                         "strategic_field_not_lower": bool(field_not_lower),
                         "one_difference_90pct_above_zero": bool(one_sig),
                         "no_major_regression_vs_b0": not majreg_b0},
            "beats_b0": bool(teacher_better and field_not_lower and one_sig and not majreg_b0),
        }
    json.dump({"rule": "§11.2 — an RL checkpoint beats B0 only when its teacher score exceeds B0's "
                       "AND its strategic-field score is not lower AND at least one of those "
                       "differences has 90% bootstrap probability above zero AND no major "
                       "regression vs B0",
               "b0_candidate": B0, "candidates": vs_b0},
              open(os.path.join(ART, "rl_vs_initialization.json"), "w"), indent=2)

    # ---------- log ----------
    log.write("MATCHUP MATRIX (Phase C, seat-balanced)\n")
    hdr = f"{'candidate':12s}" + "".join(f"{o:>16s}" for o in FIELD) + f"{'field':>10s}"
    log.write(hdr + "\n" + "-" * len(hdr) + "\n")
    for cid in order:
        row = f"{cid:12s}" + "".join(
            f"{matrix[cid][o]['point']:16.3f}" if o in matrix[cid] else f"{'-':>16s}" for o in FIELD)
        log.write(row + f"{ranking[cid]['mean_vs_field']:10.3f}\n")
    log.write("\nTEACHER HEAD-TO-HEAD (Phase A+B)\n")
    for cid, d in sorted(teacher_h2h.items(), key=lambda kv: -kv[1]["point"]):
        log.write(f"  {cid:12s} point={d['point']:.4f} lb95={d['one_sided_lb95']:.4f} "
                  f"n={d['n']} non_inferior={d['non_inferior']}\n")
    log.write("\nHELD-OUT (Mega Abomasnow)\n")
    for cid, d in sorted(ho.items(), key=lambda kv: -kv[1]["point"]):
        log.write(f"  {cid:12s} point={d['point']:.4f} n={d['n']}\n")
    log.write("\nIMPROVEMENT OVER INITIALIZATION (vs B0)\n")
    for cid, d in vs_b0.items():
        log.write(f"  {cid:12s} teacher {d['b0_teacher_score']:.3f}->{d['teacher_score']:.3f} "
                  f"(P={d['teacher_prob_better']:.2f}) field {d['b0_field_score']:.3f}->"
                  f"{d['field_score']:.3f} (P={d['field_prob_better']:.2f}) beats_b0={d['beats_b0']}\n")
    log.close()

    print(json.dumps({
        "field_ranking": [(c, round(ranking[c]["mean_vs_field"], 4)) for c in order],
        "teacher_h2h": {c: [round(d["point"], 4), round(d["one_sided_lb95"], 4), d["non_inferior"]]
                        for c, d in teacher_h2h.items()},
        "held_out": {c: round(d["point"], 4) for c, d in ho.items()},
        "beats_b0": {c: d["beats_b0"] for c, d in vs_b0.items()},
        "reproducible_improvement_vs_teacher": {c: d["reproducible_improvement"]
                                                for c, d in improvement.items()},
        "major_regressions_vs_teacher": {c: d["major_regression_matchups"]
                                         for c, d in regression.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

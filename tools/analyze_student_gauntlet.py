"""c006 AC-10 analysis: reduce captured strategic-gauntlet games to ranking,
pairwise intervals, worst matchups, seat effects, Bradley-Terry, and the
student-vs-teacher regression report. Reads the terminals gz (no game re-run).
"""

import argparse
import collections
import csv
import gzip
import json
import os
import random
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.gauntlet_stats import bradley_terry, stratified_bootstrap_ci

FIELD = ["mega_lucario", "mega_abomasnow", "iono", "mirror"]
EVALUATED = ["teacher", "S1", "S2", "control"]


def _a_score(term, a_seat):
    ws = term["winner_seat"]
    return 0.5 if ws is None else (1.0 if ws == a_seat else 0.0)


def load_matchups(gz_path):
    """(label, opp) -> {'s0': [...], 's1': [...]} of the evaluated agent's scores."""
    mm = collections.defaultdict(lambda: {"s0": [], "s1": []})
    seat_effect = collections.defaultdict(lambda: {"s0": [], "s1": []})
    with gzip.open(gz_path, "rt") as fh:
        for line in fh:
            t = json.loads(line)
            if t.get("record_type") != "game_terminal":
                continue
            label, opp = t["pair_id"].split("|")
            a_seat = 0 if "-s0-" in t["game_id"] else 1
            sc = _a_score(t, a_seat)
            key = "s0" if a_seat == 0 else "s1"
            mm[(label, opp)][key].append(sc)
            seat_effect[label][key].append(sc)
    return mm, seat_effect


def analyze_from_gz(gz_path, out_dir, log_path=None):
    mm, seat_effect = load_matchups(gz_path)
    boot = random.Random(4242)
    matrix = {}
    for label in EVALUATED:
        matrix[label] = {}
        for opp in FIELD:
            m = mm.get((label, opp), {"s0": [], "s1": []})
            lo, hi, point = stratified_bootstrap_ci(m["s0"], m["s1"], n_boot=2000, rng=boot)
            matrix[label][opp] = {"seat_balanced": point, "ci95": [lo, hi],
                                  "n": len(m["s0"]) + len(m["s1"]),
                                  "seat0_mean": float(np.mean(m["s0"])) if m["s0"] else None,
                                  "seat1_mean": float(np.mean(m["s1"])) if m["s1"] else None}

    ranking = []
    for label in EVALUATED:
        vs = [matrix[label][o]["seat_balanced"] for o in FIELD]
        ranking.append({"agent": label, "mean_seat_balanced_vs_field": float(np.mean(vs)),
                        "per_opponent": {o: matrix[label][o]["seat_balanced"] for o in FIELD}})
    ranking.sort(key=lambda r: -r["mean_seat_balanced_vs_field"])

    # Bradley-Terry over evaluated + strategic opponents (exclude mirror self-games)
    cands = set()
    bt_wins = collections.defaultdict(float)
    bt_games = collections.defaultdict(float)
    for (label, opp), m in mm.items():
        if opp == "mirror":
            continue
        allsc = m["s0"] + m["s1"]
        if not allsc:
            continue
        cands.add(label); cands.add(opp)
        bt_wins[(label, opp)] += sum(allsc)
        bt_wins[(opp, label)] += (len(allsc) - sum(allsc))
        bt_games[(label, opp)] += len(allsc)
        bt_games[(opp, label)] += len(allsc)
    bt = bradley_terry(sorted(cands), dict(bt_wins), dict(bt_games), pseudocount=1.0)

    worst = {}
    for label in ("teacher", "S1", "S2"):
        ws = min(FIELD, key=lambda o: matrix[label][o]["seat_balanced"])
        worst[label] = {"opponent": ws, "seat_balanced": matrix[label][ws]["seat_balanced"],
                        "ci95": matrix[label][ws]["ci95"]}

    regression = []
    for label in ("S1", "S2"):
        for opp in FIELD:
            s_all = mm[(label, opp)]["s0"] + mm[(label, opp)]["s1"]
            t_all = mm[("teacher", opp)]["s0"] + mm[("teacher", opp)]["s1"]
            delta = np.mean(s_all) - np.mean(t_all)
            rng = np.random.default_rng(abs(hash((label, opp))) % (2**32))
            prob = np.mean([
                (rng.choice(s_all, len(s_all)).mean() - rng.choice(t_all, len(t_all)).mean()) <= -0.10
                for _ in range(2000)])
            regression.append({"student": label, "opponent": opp,
                               "student_seat_balanced": float(np.mean(s_all)),
                               "teacher_seat_balanced": float(np.mean(t_all)),
                               "delta_pp": float(delta * 100), "prob_regression": float(prob),
                               "major_regression": bool(delta <= -0.10 and prob >= 0.90)})

    seat = {label: {"seat0_mean": float(np.mean(v["s0"])) if v["s0"] else None,
                    "seat1_mean": float(np.mean(v["s1"])) if v["s1"] else None,
                    "seat_effect": (float(np.mean(v["s0"]) - np.mean(v["s1"])) if v["s0"] and v["s1"] else None)}
            for label, v in seat_effect.items()}

    control_mean = next(r["mean_seat_balanced_vs_field"] for r in ranking if r["agent"] == "control")
    students_beat_control = {s: next(r["mean_seat_balanced_vs_field"] for r in ranking if r["agent"] == s) > control_mean
                             for s in ("S1", "S2")}

    os.makedirs(out_dir, exist_ok=True)
    json.dump({"contract": "c006", "ranking": ranking, "bradley_terry": bt, "seat_effects": seat,
               "control_mean_vs_field": control_mean, "students_beat_control": students_beat_control},
              open(os.path.join(out_dir, "student_global_ranking.json"), "w"), indent=2)
    json.dump({"worst_matchups": worst}, open(os.path.join(out_dir, "student_worst_matchups.json"), "w"), indent=2)
    json.dump({"regressions": regression,
               "major_regressions": [r for r in regression if r["major_regression"]],
               "rule": "major regression iff student seat-balanced >=10pp below teacher vs same opponent "
                       "AND bootstrap P(regression>=10pp) >= 0.90"},
              open(os.path.join(out_dir, "student_regression_report.json"), "w"), indent=2)
    with open(os.path.join(out_dir, "student_matchup_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["agent"] + FIELD + ["mean_vs_field"])
        for label in EVALUATED:
            row = [label] + [round(matrix[label][o]["seat_balanced"], 4) for o in FIELD]
            row.append(round(float(np.mean([matrix[label][o]["seat_balanced"] for o in FIELD])), 4))
            w.writerow(row)
    result = {"ranking": ranking, "worst": worst, "regression": regression, "bt": bt,
              "matrix": matrix, "students_beat_control": students_beat_control,
              "control_mean_vs_field": control_mean}
    log = ["=== strategic gauntlet (analysis) ==="]
    for r in ranking:
        log.append(f"  {r['agent']:8s}: mean_vs_field={r['mean_seat_balanced_vs_field']:.3f} "
                   + " ".join(f"{o}={r['per_opponent'][o]:.2f}" for o in FIELD))
    log.append(f"students_beat_control: {students_beat_control} (control={control_mean:.3f})")
    log.append("worst: " + json.dumps(worst))
    majors = [r for r in regression if r["major_regression"]]
    log.append(f"major_regressions: {len(majors)} " + json.dumps(majors))
    result["log_text"] = "\n".join(log)
    if log_path:
        open(log_path, "w").write(result["log_text"] + "\n")
    return result


def run(args):
    res = analyze_from_gz(args.gz, args.out_dir, args.log)
    print(res["log_text"])
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--gz", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

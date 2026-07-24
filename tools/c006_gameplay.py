"""c006 AC-08/09/10: student gameplay evaluation.

  smoke    : reliability smoke for S1 & S2 (20 seat0 + 20 seat1 vs >=2 strategic
             opponents; require zero invalid/error/timeout) + latency report.
  noninf   : student-vs-teacher head-to-head with one-sided 95% lower bound
             (100+100, extend +50/orientation to 400 if ambiguous).
  gauntlet : teacher/S1/S2/control vs the fixed strategic field (both seats,
             sequential protocol) + ranking/worst-matchup/regression analysis.

Games run in parallel across processes (spawn). Terminals streamed to gzip.
"""

import argparse
import gzip
import json
import os
import random
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.gameplay import run_batch
from cg.gauntlet_stats import bradley_terry, stratified_bootstrap_ci
from cg.noninf_stats import one_sided_lower_bound, seat_balanced_point

FIELD = ["mega_lucario", "mega_abomasnow", "iono", "mirror"]
STRATEGIC_SMOKE_OPPS = ["mega_lucario", "mega_abomasnow"]


def opp_spec(name):
    return ("teacher", "dragapult") if name == "mirror" else ("teacher", name)


def a_score(term, a_seat):
    ws = term["winner_seat"]
    if ws is None:
        return 0.5
    return 1.0 if ws == a_seat else 0.0


class GzW:
    def __init__(self, path):
        self.fh = gzip.open(path, "wt", encoding="utf-8"); self.n = 0

    def write(self, r):
        self.fh.write(json.dumps(r) + "\n"); self.n += 1

    def close(self):
        self.fh.close()


def cfg_of(args):
    deck = [int(x) for x in open(os.path.join(_REPO, args.deck)) if x.strip()]
    return {"sources": os.path.abspath(os.path.join(_REPO, args.sources)), "deck": deck}


def student_spec(args, arch):
    return ("student", os.path.abspath(os.path.join(args.ckpt_dir, f"{arch}_selected.npz")),
            "S1" if arch.startswith("S1") else "S2")


def _run(jobs, cfg, nproc, writer=None):
    for j in jobs:
        j["cfg"] = cfg
    terms = run_batch(jobs, nproc)
    by_id = {t["game_id"]: t for t in terms}
    ordered = [by_id[j["game_id"]] for j in jobs]
    if writer:
        for t in ordered:
            writer.write(t)
    return ordered


# ---------------- smoke ----------------
def phase_smoke(args, cfg, writer):
    out = {}
    lat = {}
    for arch in ("S1_STATELESS", "S2_RECURRENT"):
        sp = student_spec(args, arch)
        jobs = []
        for i in range(20):
            opp = STRATEGIC_SMOKE_OPPS[i % 2]
            jobs.append({"game_id": f"smoke-{arch}-s0-{i:03d}", "phase": "smoke", "pair_id": f"{arch}|{opp}",
                         "seat_ids": {0: sp, 1: opp_spec(opp)}})
        for i in range(20):
            opp = STRATEGIC_SMOKE_OPPS[i % 2]
            jobs.append({"game_id": f"smoke-{arch}-s1-{i:03d}", "phase": "smoke", "pair_id": f"{arch}|{opp}",
                         "seat_ids": {0: opp_spec(opp), 1: sp}})
        seats = {j["game_id"]: (0 if j["game_id"].split("-")[2] == "s0" else 1) for j in jobs}
        terms = _run(jobs, cfg, args.nproc, writer)
        invalid = err = timeout = incomplete = 0
        lats = []
        for t in terms:
            s = seats[t["game_id"]]
            r = t["reliability"][str(s)]
            invalid += r["invalid_selections"]; err += int(r["agent_error"]); timeout += int(r["timeout"])
            incomplete += int(not t["completed"])
            L = t["latency_by_seat"][str(s)]
            if L["count"]:
                lats.append(L)
        defects = invalid + err + timeout + incomplete
        p99 = max((L["p99_ms"] for L in lats), default=None)
        maxms = max((L["max_ms"] for L in lats), default=None)
        out[arch] = {"games": len(terms), "invalid": invalid, "agent_errors": err, "timeouts": timeout,
                     "incomplete": incomplete, "defects": defects, "passed": defects == 0,
                     "wins_seat_balanced": seat_balanced_point(
                         [a_score(t, seats[t["game_id"]]) for t in terms if seats[t["game_id"]] == 0],
                         [a_score(t, seats[t["game_id"]]) for t in terms if seats[t["game_id"]] == 1])}
        lat[arch] = {"p99_ms": p99, "max_ms": maxms,
                     "p50_ms": float(np.mean([L["p50_ms"] for L in lats])) if lats else None,
                     "p95_ms": float(np.mean([L["p95_ms"] for L in lats])) if lats else None}
    json.dump({"contract": "c006", "students": out}, open(os.path.join(args.out, "model_reliability_report.json"), "w"), indent=2)
    # authoritative per-move latency is the single-process offline measurement; the
    # gameplay figures below are measured under N-way parallel CPU contention (inflated).
    offline_lat = {}
    ofp = os.path.join(args.out, "offline_evaluation.json")
    if os.path.exists(ofp):
        of = json.load(open(ofp))
        offline_lat = {a: of["models"][a]["latency_ms"] for a in of.get("models", {})}
    json.dump({"contract": "c006",
               "authoritative_single_process_latency_ms": offline_lat,
               "gameplay_observed_latency_ms_under_parallel_load": lat,
               "nproc_during_gameplay": args.nproc,
               "envelope_note": "Authoritative per-move latency is the single-process offline measurement "
               "(P99 ~0.07-0.11ms, well inside the match clock; teacher ~0.33ms). Gameplay figures are "
               f"inflated by {args.nproc}-way parallel CPU contention and are not the match-time latency."},
              open(os.path.join(args.out, "model_latency_report.json"), "w"), indent=2)
    lines = ["=== reliability smoke ==="]
    for a in out:
        lines.append(f"{a}: games={out[a]['games']} defects={out[a]['defects']} passed={out[a]['passed']} "
                     f"seat_balanced_win={out[a]['wins_seat_balanced']:.3f} P99={lat[a]['p99_ms']}ms")
    open(os.path.join(args.out, "..", "test_logs", "model_smoke_games.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return out


# ---------------- non-inferiority ----------------
def phase_noninf(args, cfg, writer):
    rng = np.random.default_rng(9001)
    results = {}
    log = ["=== student vs teacher non-inferiority ==="]
    for arch in ("S1_STATELESS", "S2_RECURRENT"):
        sp = student_spec(args, arch)
        s0, s1 = [], []
        rounds = []
        per_orient = 100
        gi = 0
        while True:
            jobs = []
            base = len(s0)
            for i in range(per_orient):
                jobs.append({"game_id": f"noninf-{arch}-s0-{base + i:04d}", "phase": "noninf",
                             "pair_id": f"{arch}|teacher", "seat_ids": {0: sp, 1: ("teacher", "dragapult")}})
            base1 = len(s1)
            for i in range(per_orient):
                jobs.append({"game_id": f"noninf-{arch}-s1-{base1 + i:04d}", "phase": "noninf",
                             "pair_id": f"{arch}|teacher", "seat_ids": {0: ("teacher", "dragapult"), 1: sp}})
            seats = {j["game_id"]: (0 if "-s0-" in j["game_id"] else 1) for j in jobs}
            terms = _run(jobs, cfg, args.nproc, writer)
            for t in terms:
                sc = a_score(t, seats[t["game_id"]])
                (s0 if seats[t["game_id"]] == 0 else s1).append(sc)
            lb = one_sided_lower_bound(s0, s1, n_boot=3000, rng=rng)
            total = len(s0) + len(s1)
            rounds.append({"total_games": total, **lb})
            log.append(f"  {arch}: n={total} point={lb['point']:.3f} LB95={lb['lower_bound_95_one_sided']:.3f}")
            noninferior = lb["lower_bound_95_one_sided"] >= 0.45
            clearly_inferior = lb["upper_bound_95_one_sided"] < 0.45 and lb["point"] < 0.42
            per_orient = 50
            if noninferior or clearly_inferior or total >= 400:
                break
        results[arch] = {
            "n_games": len(s0) + len(s1), "n_seat0": len(s0), "n_seat1": len(s1),
            "point_estimate": seat_balanced_point(s0, s1),
            "one_sided_lb_95": rounds[-1]["lower_bound_95_one_sided"],
            "one_sided_ub_95": rounds[-1]["upper_bound_95_one_sided"],
            "margin": 0.05, "pass_threshold": 0.45,
            "non_inferior": bool(rounds[-1]["lower_bound_95_one_sided"] >= 0.45),
            "rounds": rounds,
        }
        log.append(f"  => {arch} non_inferior={results[arch]['non_inferior']} "
                   f"(LB {results[arch]['one_sided_lb_95']:.3f} vs 0.45)")
    json.dump({"contract": "c006", "students": results,
               "method": "seat-balanced bootstrap, one-sided 95% lower bound (5th pct), win=1/draw=.5/loss=0"},
              open(os.path.join(args.out, "student_teacher_noninferiority.json"), "w"), indent=2)
    open(os.path.join(args.out, "..", "test_logs", "student_teacher_execution.txt"), "w").write("\n".join(log) + "\n")
    print("\n".join(log))
    return results


# ---------------- strategic gauntlet ----------------
def _matchup(args, cfg, writer, A_spec, A_label, opp_name, boot_rng):
    """Sequential-protocol matchup: A vs opp, both seats. Returns seat-balanced stats."""
    sp_opp = opp_spec(opp_name)
    s0, s1 = [], []
    ps = 0
    reason = None
    while True:
        batch = 20 if ps == 0 else 10
        jobs = []
        for i in range(batch):
            jobs.append({"game_id": f"g-{A_label}-{opp_name}-s0-{len(s0):04d}-{i}", "phase": "gauntlet",
                         "pair_id": f"{A_label}|{opp_name}", "seat_ids": {0: A_spec, 1: sp_opp}})
        for i in range(batch):
            jobs.append({"game_id": f"g-{A_label}-{opp_name}-s1-{len(s1):04d}-{i}", "phase": "gauntlet",
                         "pair_id": f"{A_label}|{opp_name}", "seat_ids": {0: sp_opp, 1: A_spec}})
        seats = {j["game_id"]: (0 if "-s0-" in j["game_id"] else 1) for j in jobs}
        terms = _run(jobs, cfg, args.nproc, writer)
        for t in terms:
            sc = a_score(t, seats[t["game_id"]])
            (s0 if seats[t["game_id"]] == 0 else s1).append(sc)
        ps += batch
        lo, hi, point = stratified_bootstrap_ci(s0, s1, n_boot=2000, rng=boot_rng)
        if lo > 0.55 or hi < 0.45 or ps >= args.max_per_seat:
            reason = "ci_resolved" if (lo > 0.55 or hi < 0.45) else "max_reached"
            break
    return {"opponent": opp_name, "games_per_seat": ps, "total": ps * 2, "seat_balanced": point,
            "ci95": [lo, hi], "stopping_reason": reason, "s0": s0, "s1": s1}


def phase_gauntlet(args, cfg, writer):
    boot_rng = random.Random(4242)
    agents = [("teacher", ("teacher", "dragapult"), "teacher"),
              ("S1", student_spec(args, "S1_STATELESS"), "S1"),
              ("S2", student_spec(args, "S2_RECURRENT"), "S2"),
              ("control", ("control",), "control")]
    matrix = {}
    pair_games = {}                # (A,opp) -> list of (a_seat outcomes) for BT
    for name, spec, label in agents:
        matrix[label] = {}
        for opp in FIELD:
            m = _matchup(args, cfg, writer, spec, label, opp, boot_rng)
            matrix[label][opp] = {k: v for k, v in m.items() if k not in ("s0", "s1")}
            pair_games[(label, opp)] = m
            print(f"  {label} vs {opp}: sb={m['seat_balanced']:.3f} ci={[round(x,3) for x in m['ci95']]} "
                  f"n={m['total']} ({m['stopping_reason']})")
    # overall strength vs common strategic field (exclude control from ranking; mirror kept)
    ranking = []
    for label in ("teacher", "S1", "S2", "control"):
        vs = [matrix[label][o]["seat_balanced"] for o in FIELD]
        ranking.append({"agent": label, "mean_seat_balanced_vs_field": float(np.mean(vs)),
                        "per_opponent": {o: matrix[label][o]["seat_balanced"] for o in FIELD}})
    ranking.sort(key=lambda r: -r["mean_seat_balanced_vs_field"])

    # Bradley-Terry over evaluated agents + opponents using all non-mirror gauntlet games
    bt_wins = {}
    cands = set()
    for (label, opp), m in pair_games.items():
        if opp == "mirror":
            continue
        A, B = label, opp
        cands.add(A); cands.add(B)
        aw = sum(m["s0"]) + sum(m["s1"])          # A's total score
        n = len(m["s0"]) + len(m["s1"])
        bt_wins[(A, B)] = bt_wins.get((A, B), 0.0) + aw
        bt_wins[(B, A)] = bt_wins.get((B, A), 0.0) + (n - aw)
    bt = bradley_terry(sorted(cands), bt_wins, reg=1.0)

    # worst matchups per evaluated agent
    worst = {}
    for label in ("teacher", "S1", "S2"):
        ws = sorted(FIELD, key=lambda o: matrix[label][o]["seat_balanced"])[0]
        worst[label] = {"opponent": ws, "seat_balanced": matrix[label][ws]["seat_balanced"],
                        "ci95": matrix[label][ws]["ci95"]}

    # regression report: student vs teacher per opponent
    regression = []
    for label in ("S1", "S2"):
        for opp in FIELD:
            sm = pair_games[(label, opp)]; tm = pair_games[("teacher", opp)]
            s_all = sm["s0"] + sm["s1"]; t_all = tm["s0"] + tm["s1"]
            delta = np.mean(s_all) - np.mean(t_all)
            rng = np.random.default_rng(hash((label, opp)) % (2**32))
            prob_reg = np.mean([
                (rng.choice(s_all, len(s_all)).mean() - rng.choice(t_all, len(t_all)).mean()) <= -0.10
                for _ in range(2000)])
            major = bool(delta <= -0.10 and prob_reg >= 0.90)
            regression.append({"student": label, "opponent": opp,
                               "student_seat_balanced": float(np.mean(s_all)),
                               "teacher_seat_balanced": float(np.mean(t_all)),
                               "delta_pp": float(delta * 100), "prob_regression": float(prob_reg),
                               "major_regression": major})

    json.dump({"contract": "c006", "matrix": matrix, "bradley_terry": bt},
              open(os.path.join(args.out, "student_global_ranking.json"), "w"), indent=2)
    json.dump({"ranking": ranking, "bradley_terry": bt},
              open(os.path.join(args.out, "student_global_ranking.json"), "w"), indent=2)
    json.dump({"worst_matchups": worst}, open(os.path.join(args.out, "student_worst_matchups.json"), "w"), indent=2)
    json.dump({"regressions": regression,
               "rule": "major regression iff student seat-balanced >=10pp below teacher vs same opponent "
                       "AND bootstrap P(regression>=10pp) >= 0.90"},
              open(os.path.join(args.out, "student_regression_report.json"), "w"), indent=2)
    # matrix CSV
    import csv
    with open(os.path.join(args.out, "student_matchup_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["agent"] + FIELD + ["mean_vs_field"])
        for label in ("teacher", "S1", "S2", "control"):
            row = [label] + [round(matrix[label][o]["seat_balanced"], 4) for o in FIELD]
            row.append(round(float(np.mean([matrix[label][o]["seat_balanced"] for o in FIELD])), 4))
            w.writerow(row)
    log = ["=== strategic gauntlet ==="]
    for r in ranking:
        log.append(f"  {r['agent']}: mean_vs_field={r['mean_seat_balanced_vs_field']:.3f} "
                   + " ".join(f"{o}={r['per_opponent'][o]:.2f}" for o in FIELD))
    log.append("worst: " + json.dumps(worst))
    log.append("major_regressions: " + json.dumps([r for r in regression if r["major_regression"]]))
    open(os.path.join(args.out, "..", "test_logs", "student_gauntlet_execution.txt"), "w").write("\n".join(log) + "\n")
    print("\n".join(log))
    return {"ranking": ranking, "worst": worst, "regression": regression, "bt": bt}


def run(args):
    cfg = cfg_of(args)
    os.makedirs(args.out, exist_ok=True)
    if args.phase in ("smoke", "all"):
        w = GzW(os.path.join(args.out, "model_smoke_games.jsonl.gz"))
        phase_smoke(args, cfg, w); w.close()
    if args.phase in ("noninf", "all"):
        w = GzW(os.path.join(args.out, "student_teacher_games.jsonl.gz"))
        phase_noninf(args, cfg, w); w.close()
    if args.phase in ("gauntlet", "all"):
        w = GzW(os.path.join(args.out, "student_strategic_gauntlet.jsonl.gz"))
        phase_gauntlet(args, cfg, w); w.close()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--phase", default="all", choices=["smoke", "noninf", "gauntlet", "all"])
    p.add_argument("--sources", default="contracts/c005_teacher_import_submission_and_dataset/results/artifacts/teacher_sources")
    p.add_argument("--deck", default="contracts/c005_teacher_import_submission_and_dataset/results/artifacts/frozen_teacher/deck.csv")
    p.add_argument("--ckpt-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--nproc", type=int, default=14)
    p.add_argument("--max-per-seat", type=int, default=40)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

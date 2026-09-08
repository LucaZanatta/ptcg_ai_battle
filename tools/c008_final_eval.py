"""c008 AC-09/10/11: final local evaluation of the frozen teacher T and each surviving RL
candidate (greedy inference, exact frozen deck).

  reliability  40 games/seat vs >=3 strategic opponents; zero invalid/exception/timeout; latency.
  teacher      head-to-head 200/seat (400) extend to 800; one-sided 95% LB >= 0.47.
  strategic    T + candidates vs Lucario / Iono / held-out Mega Abomasnow / Dragapult mirror;
               control reported separately; matchup matrix, ranking, improvement, regression.

The held-out Abomasnow is used ONLY here (never in training/selection).
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
from cg import noninf_stats as ns  # noqa: E402

SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                       "results", "artifacts", "teacher_sources")
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")
STRATEGIC = ["mega_lucario", "iono", "mega_abomasnow", "dragapult"]   # last = mirror; abomasnow held-out
RELIABILITY_OPPS = ["mega_lucario", "iono", "mega_abomasnow"]


def _build_focus(spec, deck, rng):
    from cg.teachers import make_fresh
    if spec[0] == "teacher":
        return make_fresh("dragapult", SOURCES)
    if spec[0] == "rl":
        from cg.rl_policy import RLPolicy
        from cg.rl_env import RLAgent
        pol = _CACHE.get(spec[1]) or RLPolicy.load(spec[1])
        _CACHE[spec[1]] = pol
        return RLAgent(pol, deck, rng, collect=False, greedy=True)
    raise ValueError(spec)


def _build_opp(opp, deck):
    from cg.teachers import make_fresh
    if opp == "__control__":
        from cg.control_agent import DetControl
        return DetControl(deck)
    return make_fresh(opp, SOURCES)


_CACHE = {}


def _play(job):
    from kaggle_environments import make
    from cg.teachers import make_fresh
    from cg.safe_policy import MalformedSelection, validate_selection
    deck = make_fresh("dragapult", SOURCES).deck
    rng = np.random.default_rng(job["rng_seed"])
    focus = _build_focus(job["focus"], deck, rng)
    opp = _build_opp(job["opp"], deck)
    seat = job["seat"]
    lat = []; inv = [0]

    def wrap_focus(o):
        sel = o.get("select") if isinstance(o, dict) else getattr(o, "select", None)
        t0 = time.perf_counter_ns()
        res = focus(o)
        dt = time.perf_counter_ns() - t0
        if sel is not None:
            lat.append(dt)
            n = len(sel.get("option", []))
            try:
                validate_selection(list(res), n, sel.get("minCount"), sel.get("maxCount"))
            except MalformedSelection:
                inv[0] += 1
        return res

    def wrap_opp(o):
        return opp(o)

    players = [wrap_focus, wrap_opp] if seat == 0 else [wrap_opp, wrap_focus]
    exc = None; env = None
    try:
        env = make("cabt"); env.run(players)
    except Exception as e:  # noqa: BLE001
        exc = repr(e)
    if env is None:
        return {**{k: job[k] for k in ("opp", "seat")}, "score": None, "completed": False,
                "invalid": inv[0], "exc": exc, "lat_ns": lat,
                "fallback": getattr(focus, "n_fallback", 0), "ordered": getattr(focus, "n_ordered", 0)}
    last = env.steps[-1]
    st = [last[0]["status"], last[1]["status"]]
    rw = [last[0].get("reward"), last[1].get("reward")]
    completed = st == ["DONE", "DONE"]
    score = None
    if completed:
        r = rw[seat]
        score = 0.5 if rw[0] == rw[1] else (1.0 if r == 1 else 0.0)
    return {"opp": job["opp"], "seat": seat, "score": score if completed else None,
            "completed": completed, "invalid": inv[0], "exc": exc, "lat_ns": lat,
            "fallback": getattr(focus, "n_fallback", 0), "ordered": getattr(focus, "n_ordered", 0)}


def _run(jobs, nproc):
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(nproc, len(jobs))) as pool:
        return list(pool.imap_unordered(_play, jobs, chunksize=1))


def _lat_summary(ns_list):
    if not ns_list:
        return {"p50": None, "p95": None, "p99": None, "max": None}
    a = np.array(ns_list) / 1e6
    return {"p50_ms": float(np.percentile(a, 50)), "p95_ms": float(np.percentile(a, 95)),
            "p99_ms": float(np.percentile(a, 99)), "max_ms": float(a.max())}


def reliability(candidates, per_seat, nproc):
    out = {}
    for name, focus in candidates.items():
        if name == "teacher":
            continue
        jobs = []
        for opp in RELIABILITY_OPPS:
            for seat in (0, 1):
                for _ in range(per_seat):
                    jobs.append({"focus": focus, "opp": opp, "seat": seat,
                                 "rng_seed": int(np.random.default_rng([hash(name) % (1 << 30), len(jobs)]).integers(0, 1 << 30))})
        res = _run(jobs, nproc)
        lat = [x for r in res for x in r["lat_ns"]]
        out[name] = {"games": len(res), "invalid": sum(r["invalid"] for r in res),
                     "exceptions": sum(1 for r in res if r["exc"]),
                     "incomplete": sum(1 for r in res if not r["completed"]),
                     "fallback": sum(r["fallback"] for r in res),
                     "ordered": sum(r["ordered"] for r in res),
                     "latency": _lat_summary(lat),
                     "zero_defects": (sum(r["invalid"] for r in res) == 0
                                      and sum(1 for r in res if r["exc"]) == 0
                                      and sum(1 for r in res if not r["completed"]) == 0
                                      and sum(r["ordered"] for r in res) == 0)}
    return out


def teacher_noninf(candidates, per_seat, nproc):
    out = {}
    rng = np.random.default_rng(80808)
    for name, focus in candidates.items():
        if name == "teacher":
            continue
        jobs = []
        for seat in (0, 1):
            for _ in range(per_seat):
                jobs.append({"focus": focus, "opp": "dragapult", "seat": seat,
                             "rng_seed": int(rng.integers(0, 1 << 30))})
        res = _run(jobs, nproc)
        s0 = [r["score"] for r in res if r["seat"] == 0 and r["score"] is not None]
        s1 = [r["score"] for r in res if r["seat"] == 1 and r["score"] is not None]
        lb = ns.one_sided_lower_bound(s0, s1, n_boot=5000, rng=rng)
        out[name] = {"n_games": len(res), "n_seat0": len(s0), "n_seat1": len(s1), **lb,
                     "non_inferior": lb["lower_bound_95_one_sided"] >= 0.47,
                     "invalid": sum(r["invalid"] for r in res),
                     "completed": sum(1 for r in res if r["completed"]),
                     "games": [{"seat": r["seat"], "score": r["score"], "opp": "dragapult"} for r in res]}
    return out


def strategic(candidates, per_combo, nproc):
    jobs = []
    for name, focus in candidates.items():
        for opp in STRATEGIC + ["__control__"]:
            for seat in (0, 1):
                for _ in range(per_combo):
                    jobs.append({"focus": focus, "opp": opp, "seat": seat, "arm": name,
                                 "rng_seed": int(np.random.default_rng([len(jobs), 7]).integers(0, 1 << 30))})
    # attach arm label (imap loses it otherwise -> encode via focus/opp/seat mapping)
    res = _run([{k: j[k] for k in ("focus", "opp", "seat", "rng_seed")} for j in jobs], nproc)
    for j, r in zip(jobs, res):
        r["arm"] = j["arm"]
    return res


def analyze_strategic(res, candidates):
    arms = list(candidates.keys())
    by = {a: {} for a in arms}
    for r in res:
        if r["score"] is None:
            continue
        by[r["arm"]].setdefault((r["opp"], r["seat"]), []).append(r["score"])
    matrix = {}; mvf = {}; holdout = {}
    for a in arms:
        matrix[a] = {}
        strat_pts = []
        for opp in STRATEGIC + ["__control__"]:
            s0 = by[a].get((opp, 0), []); s1 = by[a].get((opp, 1), [])
            pt = ns.seat_balanced_point(s0, s1) if (s0 or s1) else None
            matrix[a][opp] = {"point": pt, "n": len(s0) + len(s1)}
            if opp not in ("__control__",):
                strat_pts.append(pt)
        mvf[a] = float(np.mean([p for p in strat_pts if p is not None])) if strat_pts else None
        holdout[a] = matrix[a].get("mega_abomasnow")
    # per-matchup improvement/regression vs teacher (bootstrap)
    rng = np.random.default_rng(80808)
    per_matchup = {}
    for a in arms:
        if a == "teacher":
            continue
        per_matchup[a] = {}
        for opp in STRATEGIC:
            t = {s: by["teacher"].get((opp, s), []) for s in (0, 1)}
            c = {s: by[a].get((opp, s), []) for s in (0, 1)}
            boot = np.empty(5000)
            for b in range(5000):
                def rs(d):
                    v = []
                    for s in (0, 1):
                        arr = np.asarray(d[s])
                        if len(arr):
                            v.append(arr[rng.integers(0, len(arr), len(arr))].mean())
                    return np.mean(v) if v else np.nan
                boot[b] = rs(c) - rs(t)
            diff = (ns.seat_balanced_point(c[0], c[1]) - ns.seat_balanced_point(t[0], t[1]))
            per_matchup[a][opp] = {"cand_point": ns.seat_balanced_point(c[0], c[1]),
                                   "teacher_point": ns.seat_balanced_point(t[0], t[1]),
                                   "diff_pp": diff * 100, "prob_better": float((boot > 0).mean()),
                                   "prob_regress_7pp": float((boot < -0.07).mean()),
                                   "ci90": [float(np.percentile(boot, 5)), float(np.percentile(boot, 95))]}
    return {"matchup": matrix, "mean_vs_field_excl_control": mvf, "holdout_abomasnow": holdout,
            "per_matchup_vs_teacher": per_matchup,
            "control_reported_separately": {a: matrix[a].get("__control__") for a in arms}}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True, help='JSON {"R0":ckpt,"R1":ckpt,"R2":ckpt} (survivors)')
    p.add_argument("--nproc", type=int, default=14)
    p.add_argument("--rel-per-seat", type=int, default=40)
    p.add_argument("--noninf-per-seat", type=int, default=200)
    p.add_argument("--strat-per-combo", type=int, default=40)
    a = p.parse_args(argv)
    cand_ck = json.loads(a.candidates)
    candidates = {"teacher": ("teacher",)}
    for arm, ck in cand_ck.items():
        if ck:
            candidates[arm] = ("rl", ck)
    log_dir = os.path.join(os.path.dirname(C008_ART), "test_logs")
    t0 = time.time()

    rel = reliability(candidates, a.rel_per_seat, a.nproc)
    json.dump(rel, open(os.path.join(C008_ART, "final_reliability.json"), "w"), indent=2)
    json.dump({k: rel[k]["latency"] for k in rel}, open(os.path.join(C008_ART, "final_latency.json"), "w"), indent=2)
    open(os.path.join(log_dir, "final_smoke_games.txt"), "w").write(json.dumps(rel, indent=2) + "\n")

    noninf = teacher_noninf(candidates, a.noninf_per_seat, a.nproc)
    games = []
    for name, d in noninf.items():
        for g in d.pop("games"):
            g["candidate"] = name; games.append(g)
    with gzip.open(os.path.join(C008_ART, "rl_teacher_games.jsonl.gz"), "wt") as fh:
        for g in games:
            fh.write(json.dumps(g) + "\n")
    json.dump(noninf, open(os.path.join(C008_ART, "rl_teacher_noninferiority.json"), "w"), indent=2)
    open(os.path.join(log_dir, "rl_teacher_execution.txt"), "w").write(json.dumps(noninf, indent=2) + "\n")

    sres = strategic(candidates, a.strat_per_combo, a.nproc)
    with gzip.open(os.path.join(C008_ART, "rl_strategic_games.jsonl.gz"), "wt") as fh:
        for r in sres:
            fh.write(json.dumps({k: r[k] for k in ("arm", "opp", "seat", "score", "completed")}) + "\n")
    an = analyze_strategic(sres, candidates)
    json.dump({"mean_vs_field": an["mean_vs_field_excl_control"], "matchup": an["matchup"],
               "control_reported_separately": an["control_reported_separately"]},
              open(os.path.join(C008_ART, "rl_global_ranking.json"), "w"), indent=2)
    json.dump({"holdout_abomasnow": an["holdout_abomasnow"],
               "note": "Mega Abomasnow held out from training/selection; used only here"},
              open(os.path.join(C008_ART, "rl_holdout_report.json"), "w"), indent=2)
    # improvement + regression
    improvement = {}; regression = {}
    for arm, mm in an["per_matchup_vs_teacher"].items():
        imp = [o for o, m in mm.items() if m["diff_pp"] >= 5 and m["prob_better"] >= 0.90]
        glob = an["mean_vs_field_excl_control"].get(arm)
        gt = an["mean_vs_field_excl_control"].get("teacher")
        improvement[arm] = {"matchups_5pp_90": imp, "mean_vs_field": glob, "teacher_mean_vs_field": gt,
                            "global_better": (glob is not None and gt is not None and glob > gt),
                            "per_matchup": mm}
        regression[arm] = {"major_regression_matchups": [o for o, m in mm.items() if m["prob_regress_7pp"] >= 0.90],
                           "per_matchup": mm}
    json.dump(improvement, open(os.path.join(C008_ART, "rl_improvement_report.json"), "w"), indent=2)
    json.dump(regression, open(os.path.join(C008_ART, "rl_regression_report.json"), "w"), indent=2)
    import csv
    with open(os.path.join(C008_ART, "rl_matchup_matrix.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["arm", "opponent", "seat_balanced_score", "n"])
        for arm, mm in an["matchup"].items():
            for opp, v in mm.items():
                w.writerow([arm, opp, round(v["point"], 4) if v["point"] is not None else "", v["n"]])
    open(os.path.join(log_dir, "rl_strategic_execution.txt"), "w").write(json.dumps(an, indent=2, default=str) + "\n")

    summary = {"reliability": {k: rel[k]["zero_defects"] for k in rel},
               "non_inferior": {k: noninf[k]["non_inferior"] for k in noninf},
               "non_inf_lb": {k: noninf[k]["lower_bound_95_one_sided"] for k in noninf},
               "mean_vs_field": an["mean_vs_field_excl_control"],
               "improvement": {k: improvement[k]["matchups_5pp_90"] or improvement[k]["global_better"] for k in improvement},
               "regression": {k: regression[k]["major_regression_matchups"] for k in regression},
               "holdout": an["holdout_abomasnow"], "wall_seconds": round(time.time() - t0, 1)}
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

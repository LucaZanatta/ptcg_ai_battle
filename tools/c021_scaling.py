"""c021 M16/M17 — worker-throughput scaling, and the search-vs-no-search ablation."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
PY = os.path.join(_REPO, ".venv", "bin", "python")

def run(tag, extra, games, nproc):
    cmd = [PY, "-u", os.path.join(_REPO, "tools", "c021_mcgs_run.py"),
           "--games", str(games), "--nproc", str(nproc),
           "--first-move-seconds", "0.9", "--continuing-move-seconds", "0.7",
           "--match-clock-seconds", "90", "--game-timeout-seconds", "300",
           "--tag", tag] + extra
    t0 = time.time()
    subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=7200)
    p = os.path.join(C21, "mcgs", "evaluations", f"{tag}_summary.json")
    d = json.load(open(p)) if os.path.exists(p) else {}
    return d, round(time.time() - t0, 1)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaling", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    a = ap.parse_args(argv)

    if a.scaling:
        # M16: identical work at 1/2/4/8/12 workers. Each run is measured ALONE.
        ms = []
        # 20 and 24 added deliberately: M16 is the mandated scaling probe AND the calibration
        # for how many workers the other latency-bounded runs may safely use. On a 24-core box
        # with torch.set_num_threads(1) per worker, workers <= cores should mean no
        # oversubscription and a FLAT sims_per_decision -- but that is a hypothesis, and the
        # whole point of this probe is to test it rather than assume it. The high-worker points
        # are the cheap ones.
        for n in (1, 2, 4, 8, 12, 20, 24):
            # 12 games per point let game-length variance swamp the contention signal: the
            # first run gave sims/decision of 73 / 1003 / 566 at 4 / 8 / 12 workers, which is
            # noise, not scaling. Same game COUNT at every point, more of them.
            d, wall = run(f"scale_w{n}", [], games=36, nproc=n)
            ms.append({"workers": n, "games": d.get("games"), "completed": d.get("completed"),
                       "wall_clock_s": wall,
                       "games_per_minute": round(60.0 * (d.get("completed") or 0) / max(wall, 1), 2),
                       "sims_per_decision": d.get("sims_per_decision"),
                       "field_score": d.get("field_score")})
            print(json.dumps(ms[-1]), flush=True)
        base = next((m["games_per_minute"] for m in ms if m["workers"] == 1), None)
        s1 = next((m["sims_per_decision"] for m in ms if m["workers"] == 1), None)
        for m in ms:
            m["speedup_vs_1_worker"] = (round(m["games_per_minute"] / base, 2)
                                        if base else None)
            # THE contention test: this must stay ~flat. If it falls as workers are added, the
            # per-decision wall-clock budget is being eaten and every field score at that worker
            # count is biased downward.
            m["sims_per_decision_vs_1_worker"] = (round(m["sims_per_decision"] / s1, 3)
                                                  if s1 else None)
        os.makedirs(os.path.join(C21, "hardware"), exist_ok=True)
        json.dump({"measurements": ms,
                   "note": ("Each point measured ALONE on an otherwise idle machine, with "
                            "torch.set_num_threads(1) per worker. sims_per_decision is the "
                            "quantity that must stay FLAT across worker counts: if it falls as "
                            "workers are added, the per-decision wall-clock budget is being eaten "
                            "by contention, which is the artifact that inverted a c019 ranking.")},
                  open(os.path.join(C21, "hardware", "mcgs_worker_scaling.json"), "w"), indent=2)
        print("wrote hardware/mcgs_worker_scaling.json")

    if a.ablation:
        # M17: identical everything except that the control never searches.
        srch, w1 = run("ablation_search", [], games=40, nproc=12)
        nos, w2 = run("ablation_nosearch", ["--match-clock-seconds", "0.0001"], games=40, nproc=12)
        def band(d):
            import math
            k = (d.get("field_score") or 0) * (d.get("completed") or 0); n = d.get("completed") or 0
            if not n: return [0, 1]
            p = k/n; z = 1.96; den = 1+z*z/n; c = p+z*z/(2*n)
            m = z*math.sqrt(max(p*(1-p)/n + z*z/(4*n*n), 0))
            return [round((c-m)/den, 4), round((c+m)/den, 4)]
        out = {
            "search": {"field_score": srch.get("field_score"), "completed": srch.get("completed"),
                       "sims_per_decision": srch.get("sims_per_decision"),
                       "wilson95": band(srch), "wall_clock_s": w1},
            "no_search": {"field_score": nos.get("field_score"), "completed": nos.get("completed"),
                          "searched_decisions": nos.get("searched_decisions"),
                          "match_clock_exhausted_decisions":
                              nos.get("match_clock_exhausted_decisions"),
                          "wilson95": band(nos), "wall_clock_s": w2},
            "delta": round((srch.get("field_score") or 0) - (nos.get("field_score") or 0), 4),
            "interpretation": ("The no-search control plays the same agent with the match clock "
                               "set to zero, so it never searches and takes END_TURN when "
                               "available. A positive delta means executed search actions helped; "
                               "a negative one means they HURT, which is the question "
                               "DECISION_RULES 5 requires answered explicitly. Read it against "
                               "the measured reproducibility bound, not against zero."),
        }
        os.makedirs(os.path.join(C21, "mcgs", "comparisons"), exist_ok=True)
        json.dump(out, open(os.path.join(C21, "mcgs", "comparisons",
                                         "decision_value_ablation.json"), "w"), indent=2)
        print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

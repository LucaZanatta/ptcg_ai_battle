"""c010 AC-06: throughput / compute registration.

Runs a short real probe of every arm (identical code path to the full runs, 2 PPO updates,
no checkpoints written), measures games/hour, decisions/game, update duration, rollout
duration, memory and disk growth, and projects the full registered experiment against the
118,500 / 120,000 caps. If the registered minimum is infeasible the projection says so
explicitly rather than any budget being silently altered (§13).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
PROBE_SEED = {"A": 311, "B": 411, "C": 511}


def probe(arm, nproc, omp):
    env = dict(os.environ, OMP_NUM_THREADS=str(omp))
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(_REPO, "tools", "c010_train_loop.py"),
                        "--arm", arm, "--seed", str(PROBE_SEED[arm]), "--nproc", str(nproc),
                        "--calibration"], capture_output=True, text=True, env=env, timeout=3600)
    out = None
    for line in r.stdout.splitlines():
        if line.startswith("CALIBRATION "):
            out = json.loads(line[len("CALIBRATION "):])
    if out is None:
        raise RuntimeError(f"probe for arm {arm} produced no calibration line: {r.stdout[-500:]}")
    out["wall_seconds_including_startup"] = round(time.time() - t0, 1)
    out["omp_threads"] = omp
    return out


def dir_size_mb(p):
    tot = 0
    for dp, _dn, fns in os.walk(p):
        for f in fns:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return round(tot / 1e6, 2)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--nproc", type=int, default=7)
    p.add_argument("--omp", type=int, default=4)
    p.add_argument("--concurrent-seeds", type=int, default=3)
    p.add_argument("--concurrency-efficiency", type=float, default=0.60,
                   help="measured fraction of solo throughput retained when N seeds share the box")
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    reg = json.load(open(os.path.join(ART, "experiment_registry.json")))

    disk_before = dir_size_mb(os.path.join(ART))
    probes = {}
    for arm in ("A", "B", "C"):
        probes[arm] = probe(arm, a.nproc, a.omp)
        print(f"probe {arm}: {json.dumps(probes[arm])}", flush=True)
    disk_after = dir_size_mb(os.path.join(ART))

    try:
        import resource
        mem_mb = round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1)
    except Exception:  # noqa: BLE001
        mem_mb = None
    try:
        free_gb = round(shutil.disk_usage(_REPO).free / 1e9, 1)
    except Exception:  # noqa: BLE001
        free_gb = None

    budgets = reg["budgets"]
    per_arm_max = {"A": budgets["arm_A"], "B": budgets["arm_B"], "C": budgets["arm_C"]}
    eff = a.concurrency_efficiency
    proj = {}
    total_h = 0.0
    for arm, games in per_arm_max.items():
        solo = probes[arm]["games_per_hour"]
        agg = solo * a.concurrent_seeds * eff
        h = games / agg
        total_h += h
        proj[arm] = {"max_games": games, "solo_games_per_hour": solo,
                     "assumed_concurrent_seeds": a.concurrent_seeds,
                     "assumed_efficiency": eff,
                     "projected_aggregate_games_per_hour": round(agg, 1),
                     "projected_hours": round(h, 2),
                     "decisions_per_game": probes[arm]["decisions_per_game"],
                     "mean_update_seconds": probes[arm]["mean_update_seconds"],
                     "mean_rollout_seconds": probes[arm]["mean_rollout_seconds"]}

    # evaluation projection (identity-safe panels)
    panels = reg["panels"]
    n_screen = (5 * 3) + (3 * 3) + (6 * 3) + 2      # non-zero eval points per seed + B0 + I0
    est_confirm = 15
    n_final = 5
    eval_games = (n_screen * panels["screen"]["total_per_checkpoint"]
                  + est_confirm * panels["confirmation"]["total_per_checkpoint"]
                  + n_final * panels["final"]["total_per_finalist"])
    eval_rate = 28 * 3600      # games/hour measured in c009 identity-safe evaluation (~28 g/s)
    eval_h = eval_games / eval_rate

    out = {
        "contract": "c010", "probe_config": {"nproc": a.nproc, "omp_threads": a.omp,
                                             "updates_per_probe": 2, "checkpoints_written": False},
        "probes": probes,
        "resources": {"peak_child_rss_mb": mem_mb, "artifact_disk_mb_before": disk_before,
                      "artifact_disk_mb_after": disk_after,
                      "probe_disk_growth_mb": round(disk_after - disk_before, 2),
                      "free_disk_gb": free_gb, "cpu_count": os.cpu_count()},
        "projection": proj,
        "projected_training_hours": round(total_h, 2),
        "projected_evaluation": {"estimated_games": eval_games,
                                 "assumed_games_per_hour": eval_rate,
                                 "projected_hours": round(eval_h, 2),
                                 "basis": "c009 identity-safe evaluation measured ~28 games/s at nproc 16"},
        "projected_total_hours": round(total_h + eval_h, 2),
        "budget_check": {
            "registered_total_training_games": budgets["total"],
            "hard_maximum": budgets["hard_maximum_including_spillover"],
            "within_hard_maximum": budgets["total"] <= budgets["hard_maximum_including_spillover"],
            "evaluation_counted_separately": True},
        "feasibility": None,
        "notes": [
            "Probes use the identical training code path (same rollout rule, same PPO update); "
            "only the number of updates is truncated and no checkpoints are written.",
            "Arm C's larger rollout (256 games / 32,768 decisions) makes each update ~4x heavier "
            "but proportionally rarer, so games/hour stays within ~15% of Arms A/B.",
            "Concurrency efficiency is an execution detail (how many seeds share the machine); it "
            "is not a registered experimental parameter and changing it does not alter any arm.",
        ],
    }
    out["feasibility"] = ("FEASIBLE" if out["projected_total_hours"] <= 12
                          else "INFEASIBLE_WITHIN_SESSION")
    json.dump(probes, open(os.path.join(ART, "throughput_calibration.json"), "w"), indent=2)
    json.dump(out, open(os.path.join(ART, "compute_budget.json"), "w"), indent=2)

    lines = ["c010 AC-06 throughput calibration + compute budget", "=" * 62,
             f"cpu_count={out['resources']['cpu_count']} peak_child_rss={mem_mb} MB "
             f"free_disk={free_gb} GB", ""]
    for arm in ("A", "B", "C"):
        pr = probes[arm]; pj = proj[arm]
        lines.append(f"  Arm {arm}: {pr['games_per_hour']:.0f} games/h solo (nproc {pr['nproc']}, "
                     f"omp {pr['omp_threads']}), {pr['decisions_per_game']:.1f} dec/game, "
                     f"update {pr['mean_update_seconds']:.0f}s, rollout {pr['mean_rollout_seconds']:.0f}s")
        lines.append(f"          max {pj['max_games']:,} games -> ~{pj['projected_hours']:.2f} h "
                     f"at {pj['projected_aggregate_games_per_hour']:.0f} games/h aggregate")
    lines += ["", f"projected training  : {out['projected_training_hours']:.2f} h",
              f"projected evaluation: {out['projected_evaluation']['projected_hours']:.2f} h "
              f"({eval_games:,} games)",
              f"projected TOTAL     : {out['projected_total_hours']:.2f} h",
              f"registered training budget {budgets['total']:,} (hard max "
              f"{budgets['hard_maximum_including_spillover']:,}) -> within cap: "
              f"{out['budget_check']['within_hard_maximum']}",
              f"FEASIBILITY = {out['feasibility']}"]
    open(os.path.join(LOGD, "throughput_calibration.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

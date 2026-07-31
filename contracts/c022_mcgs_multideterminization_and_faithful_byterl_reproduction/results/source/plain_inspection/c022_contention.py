"""c022 — measure whether concurrent load taints a simulation-budgeted MCGS arm.

`CONTRACT.md §5`: "MCGS gets exclusive CPU during decisive scaling and final panels. ByteRL may
run concurrently only when CPU contention is measured and shown not to taint timing/evaluation."

**Why c022 can ask this question at all, and c021 could not.** c021's arms were WALL-CLOCK
budgeted: each decision got 0.9 s, so contention converted directly into fewer simulations, and
its own M16 measured `sims_per_decision` collapsing to 8% of the single-worker value at 24
workers with nothing in the field score to reveal it. c021's answer had to be "run alone at
nproc 12".

c022's arms are SIMULATION-COUNT budgeted. A decision runs its 256 simulations however long that
takes. Contention should therefore change wall clock and nothing else — but "should" is how
c021's artifact happened, so this measures it.

Three quantities decide the answer, and only the first is the one people check:

1. `sims_per_decision` — must be EXACTLY the configured budget under load. If it is, the search
   itself is untainted, because the number of simulations is the whole causal quantity.
2. `decision_deadline_stops` — the per-decision wall ceiling is a safety stop. Under enough load
   a decision could hit it, at which point the budget was NOT delivered and the arm is tainted
   after all. This is the failure mode a naive check misses.
3. `abandoned` + `unscored` — games are cut by a wall-clock guard derived from the arm's cost.
   Slower games mean more cuts, and cut games leave the field score, so the surviving subsample
   changes. This is the failure mode that would silently move a field score.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
OUT = os.path.join(C22, "hardware")


def run_arm(tag, nproc, games, sims, k, outdir, timeout):
    cmd = [sys.executable, os.path.join(_REPO, "tools", "c022_mcgs_run.py"),
           "--tag", tag, "--k", str(k), "--protocol", "fixed_total", "--sims", str(sims),
           "--games", str(games), "--nproc", str(nproc), "--decision-budget", "260",
           "--arm-timeout", str(timeout), "--out", outdir]
    t0 = time.time()
    subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=timeout + 120)
    p = os.path.join(outdir, f"{tag}_summary.json")
    if not os.path.isfile(p):
        return {"tag": tag, "error": "no summary written", "wall_s": round(time.time() - t0, 1)}
    with open(p) as fh:
        s = json.load(fh)
    return {
        "tag": tag, "nproc": nproc, "games": games,
        "sims_per_decision_configured": sims,
        "sims_per_decision_measured": s.get("sims_per_decision"),
        "budget_delivered": s.get("budget_delivered"),
        "decision_deadline_stops": s.get("decision_deadline_stops"),
        "completed": s.get("completed"), "abandoned": s.get("abandoned"),
        "unscored": s.get("unscored"),
        "excluded_fraction": s.get("excluded_fraction"),
        "all_games_accounted": s.get("all_games_accounted"),
        "searched_decisions": s.get("searched_decisions"),
        "field_score": s.get("field_score"),
        "wall_clock_s": s.get("wall_clock_s"),
        "games_per_minute": round(60.0 * s.get("completed", 0)
                                  / max(1e-9, s.get("wall_clock_s", 1)), 2),
    }


def load_snapshot():
    try:
        with open("/proc/loadavg") as fh:
            la = fh.read().split()[:3]
    except Exception:  # noqa: BLE001
        la = None
    n = 0
    try:
        out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
        n = sum(1 for l in out.splitlines() if "python" in l)
    except Exception:  # noqa: BLE001
        pass
    return {"loadavg": la, "python_processes": n, "cpu_count": os.cpu_count()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nprocs", default="12,22")
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--scratch", default=os.path.join(
        "/tmp/claude-1000/-home-luca-kaggle-ptcg-ai-battle",
        "3e28ed63-1041-4fe7-81fb-48ae9cc70346", "scratchpad", "contention"))
    ap.add_argument("--out", default=os.path.join(OUT, "contention_tests.json"))
    a = ap.parse_args(argv)

    os.makedirs(a.scratch, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for np_ in [int(x) for x in a.nprocs.split(",")]:
        before = load_snapshot()
        r = run_arm(f"cont_np{np_}", np_, a.games, a.sims, a.k, a.scratch, a.timeout)
        r["load_before"] = before
        r["load_after"] = load_snapshot()
        rows.append(r)
        print(json.dumps({k: r.get(k) for k in
                          ("tag", "nproc", "sims_per_decision_measured", "budget_delivered",
                           "decision_deadline_stops", "completed", "abandoned", "unscored",
                           "wall_clock_s", "games_per_minute")}), flush=True)

    good = [r for r in rows if "error" not in r]
    budget_held = all(
        r["sims_per_decision_measured"] is not None
        and abs(r["sims_per_decision_measured"] - a.sims) <= 1.0 for r in good)
    no_stops = all((r["decision_deadline_stops"] or 0) == 0 for r in good)
    excl = [r["excluded_fraction"] or 0.0 for r in good]
    excl_spread = (max(excl) - min(excl)) if excl else None

    verdict = {
        "simulation_budget_held_under_every_concurrency": budget_held,
        "no_decision_hit_the_wall_ceiling": no_stops,
        "exclusion_rate_spread": round(excl_spread, 4) if excl_spread is not None else None,
        "exclusion_spread_acceptable": (excl_spread is not None and excl_spread <= 0.10),
    }
    verdict["safe_to_run_concurrent_load"] = bool(
        budget_held and no_stops and verdict["exclusion_spread_acceptable"])
    verdict["reading"] = (
        "A simulation-budgeted arm delivers the same number of simulations however contended the "
        "machine is; contention shows up as wall clock. That holds only while no decision hits "
        "the per-decision wall ceiling and no extra games are cut by the per-game guard -- both "
        "of which are checked here, because either would silently change the population the "
        "field score is computed over."
        if verdict["safe_to_run_concurrent_load"] else
        "At least one arm did NOT deliver its simulation budget, hit the wall ceiling, or "
        "excluded a materially different fraction of its games. Concurrent load taints the "
        "evaluation and CONTRACT.md §5 forbids it.")

    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "question": "does concurrent CPU load taint a SIMULATION-BUDGETED MCGS arm?",
           "why_c021_could_not_ask_this": "c021's arms were wall-clock budgeted, so contention "
                                          "converted directly into fewer simulations; its M16 "
                                          "measured sims_per_decision falling to 8% of the "
                                          "single-worker value at 24 workers, invisible in the "
                                          "field score.",
           "protocol": {"games": a.games, "simulations_per_decision": a.sims, "k": a.k,
                        "nprocs": a.nprocs},
           "measurements": rows, "verdict": verdict}
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(verdict, indent=1))
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

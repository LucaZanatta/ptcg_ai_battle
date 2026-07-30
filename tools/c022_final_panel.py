"""c022 — the final panel: registered candidates and the frozen bar, on ONE panel.

`DECISION_RULES §2` makes `MCGS_COMPETITIVE=PASS` require a candidate that "credibly beats the
strongest frozen local champion on the broad panel". The two numbers that invite comparison do
not live on the same panel:

    BASELINE_OFFICIAL_MEGA_LUCARIO   0.5837   on the c020 panel
    paired_k8 (corrected MCGS)       0.1650   on the c022 four-opponent panel

Putting those side by side would be the position-pairing defect family in a new costume: two
numbers that look comparable and are not. So this runs every candidate AND the frozen bar over
the SAME opponents, the same game count, the same seats and the same seeds, and reports the
comparison only from that.

**Why this panel is count-budgeted rather than deploy-budgeted.** A time-budgeted panel is
latency-sensitive and must run alone, which under the current schedule would mean not running it
at all. Count-budgeting makes it contention-tolerant — an arm gets slower, never weaker — at the
cost of not measuring deployment strength. That cost is paid separately and honestly: the M12
deploy arms DO run alone under c021's 90 s clock, and the report cites them for the deployment
question rather than pretending this panel answers it.

**Power, stated before the run.** The candidate and the bar are ~42 points apart on their own
panels. At 60 games a Wilson interval spans roughly 12 points at these rates, so a gap of that
size is resolvable many times over and a larger panel would buy precision the conclusion does not
need. If the observed gap turns out to be small, the report says the panel is underpowered for it
rather than reporting a coin flip as a finding.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")
OUT = os.path.join(MC, "final_panel")

OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _play(job: Dict[str, Any]) -> Dict[str, Any]:
    """One game. Imports live inside the worker so the parent never loads the engine."""
    sys.path.insert(0, _REPO)
    import numpy as np
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c021_byterl_deck as DK

    kind = job["candidate"]
    seat = int(job["seat"])
    opp = T.make_fresh(job["opponent"], ce.SOURCES)

    if kind == "baseline":
        # The frozen bar plays through the same harness as everything else. `make_fresh` is used
        # for BOTH sides so that a candidate is never advantaged by a different construction path.
        me = T.make_fresh(job["baseline_agent"], ce.SOURCES)
        report = {}
    else:
        from cg import c022_mcgs_agent as AG
        pool = DK.CardPool.from_archetypes([job["deck_archetype"]])
        deck = DK.greedy_reference_deck(pool)
        agent = AG.MultiDetMCGSAgent(deck=deck, cfg=job["cfg"], seed=int(job["seed"]))

        def me(o):
            return agent.act(o)
        report = None

    t0 = time.time()
    env = make("cabt")
    agents = [me, opp] if seat == 0 else [opp, me]
    status, reward = None, None
    try:
        env.run(agents)
        last = env.steps[-1]
        status = [s.status for s in last]
        if status == ["DONE", "DONE"]:
            rw = [s.reward for s in last]
            if rw[seat] is not None and rw[1 - seat] is not None:
                reward = (1.0 if rw[seat] > rw[1 - seat]
                          else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        return {**{k: job[k] for k in ("candidate", "opponent", "seat", "game_id")},
                "error": f"{type(e).__name__}: {e}"[:200], "seconds": round(time.time() - t0, 1)}

    row = {k: job[k] for k in ("candidate", "opponent", "seat", "game_id")}
    row.update({"status": status, "score": reward, "seconds": round(time.time() - t0, 1)})
    if report is None:
        r = agent.report()
        row["searched_decisions"] = r.get("searched_decisions")
        row["sims_per_decision"] = r.get("sims_per_decision")
    return row


def summarise(rows: List[Dict[str, Any]], tag: str) -> Dict[str, Any]:
    mine = [r for r in rows if r["candidate"] == tag]
    scored = [r for r in mine if r.get("score") is not None]
    errored = [r for r in mine if r.get("error")]
    unscored = [r for r in mine if not r.get("error") and r.get("score") is None]
    total = sum(r["score"] for r in scored)
    n = len(scored)
    per_opp = {}
    for o in OPPONENTS:
        sel = [r for r in scored if r["opponent"] == o]
        if sel:
            per_opp[o] = {"games": len(sel),
                          "rate": round(sum(r["score"] for r in sel) / len(sel), 4)}
    return {
        "candidate": tag, "games": len(mine), "scored": n,
        "errored": len(errored), "unscored": len(unscored),
        "field_score": round(total / n, 4) if n else None,
        "wilson95": wilson(total, n),
        "per_opponent": per_opp,
        "mean_seconds": round(sum(r.get("seconds", 0) for r in mine) / max(1, len(mine)), 1),
        "note": ("field_score is over SCORED games only; errored and unscored games are "
                 "excluded rather than counted as losses"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60, help="per candidate, across the panel")
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--seed", type=int, default=515151)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--sims", type=int, default=12, help="per world (fixed_per_world)")
    ap.add_argument("--decision-budget", type=int, default=50)
    ap.add_argument("--deck-archetype", default="mega_lucario")
    ap.add_argument("--baseline-agent", default="mega_lucario")
    ap.add_argument("--out", default=os.path.join(OUT, "panel.json"))
    a = ap.parse_args(argv)

    import multiprocessing as mp
    from cg import c022_mcgs_agent as AG

    def cfg(k: int) -> Dict[str, Any]:
        return {**AG.REFERENCE_CFG, "k_worlds": k, "budget_protocol": "fixed_per_world",
                "simulations_per_decision": a.sims, "graph_reuse": False,
                "match_clock_seconds": 0.0, "decision_seconds_cap": 0.0,
                "decision_wall_ceiling_seconds": 300.0,
                "decision_budget": a.decision_budget}

    candidates = {
        f"mcgs_k{a.k}": {"kind": "mcgs", "cfg": cfg(a.k)},
        "mcgs_k1": {"kind": "mcgs", "cfg": cfg(1)},
        "baseline": {"kind": "baseline"},
    }

    jobs = []
    for tag, spec in candidates.items():
        for i in range(a.games):
            jobs.append({
                "candidate": tag, "game_id": f"{tag}:g{i}",
                "opponent": OPPONENTS[i % len(OPPONENTS)],
                # Seats and opponents are assigned from the game INDEX, identically for every
                # candidate, so candidate A and candidate B face the same schedule. The engine
                # still redraws the shuffle -- NOISE_FLOOR_ACCIDENTAL_REPLICATION.md -- so this
                # pairs the schedule, not the games, and the report says so.
                "seat": i % 2,
                "seed": a.seed * 1000003 + i,
                "deck_archetype": a.deck_archetype,
                "baseline_agent": a.baseline_agent,
                "cfg": spec.get("cfg"),
            })

    print(f"[panel] {len(candidates)} candidates x {a.games} games = {len(jobs)} games, "
          f"nproc {a.nproc}", flush=True)
    t0 = time.time()
    with mp.Pool(a.nproc) as pool:
        rows = pool.map(_play, jobs)
    elapsed = time.time() - t0

    summaries = {t: summarise(rows, t) for t in candidates}
    base = summaries["baseline"]
    best_tag = max((t for t in candidates if t != "baseline"),
                   key=lambda t: (summaries[t]["field_score"] or -1))
    best = summaries[best_tag]

    sep = None
    if best["wilson95"][0] is not None and base["wilson95"][0] is not None:
        sep = bool(best["wilson95"][0] > base["wilson95"][1])
    delta = None
    if best["field_score"] is not None and base["field_score"] is not None:
        delta = round(100 * (best["field_score"] - base["field_score"]), 2)

    report = {
        "panel": OPPONENTS,
        "games_per_candidate": a.games,
        "elapsed_s": round(elapsed, 1),
        "budget": {"protocol": "fixed_per_world", "simulations_per_world": a.sims,
                   "k": a.k, "decision_budget": a.decision_budget},
        "why_count_budgeted": (
            "a time-budgeted panel is latency-sensitive and must run alone; count-budgeting "
            "makes it contention-tolerant, at the cost of not measuring DEPLOYMENT strength. "
            "That question is answered by the M12 deploy arms, which do run alone under c021's "
            "90 s clock."),
        "summaries": summaries,
        "champion_comparison": {
            "bar": "BASELINE_OFFICIAL_MEGA_LUCARIO, re-run here on this panel",
            "bar_field_score": base["field_score"],
            "bar_wilson95": base["wilson95"],
            "best_candidate": best_tag,
            "candidate_field_score": best["field_score"],
            "candidate_wilson95": best["wilson95"],
            "delta_pp": delta,
            "intervals_separate_in_candidate_favour": sep,
            "credible_improvement": bool(sep and (delta or 0) > 0),
            "note": ("the c020 figure of 0.5837 is NOT used as the bar: it was measured on a "
                     "different panel. The bar here is the same agent re-run over these "
                     "opponents, seats and game count."),
        },
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(os.path.dirname(a.out), "panel_games.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    for t, s in summaries.items():
        print(f"  {t:12s} field={s['field_score']} {s['wilson95']} "
              f"scored={s['scored']}/{s['games']} per_opp={s['per_opponent']}")
    c = report["champion_comparison"]
    print(f"  -> {c['best_candidate']} {c['candidate_field_score']} vs bar "
          f"{c['bar_field_score']}: delta {c['delta_pp']} pp, "
          f"credible_improvement={c['credible_improvement']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

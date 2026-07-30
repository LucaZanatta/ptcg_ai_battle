"""c022 — run one MCGS arm against the frozen four-archetype panel.

One arm = one (K, protocol, simulations) triple. Games run in separate processes so a stalled
game cannot take the arm with it, and results are drained as they arrive.

Two things c021 got wrong here and this runner does not:

**The queue is drained while children are alive.** c021's parent read child results only after
`join()`, so children blocking on a full pipe were recorded as abandoned. Twelve games that
"abandoned" at 154 s completed in 45 s once the drain was fixed. This runner drains continuously.

**Latency is not the budget.** Arms are budgeted by simulation count, so worker contention makes
a run slower but never weaker. c021's own M16 measurement found `sims_per_decision` collapsing to
8% of its single-worker value at 24 workers with nothing in the field score to reveal it. That
failure mode cannot occur here — but `sims_per_decision` is still reported per arm, because a
budget that is not being delivered must be visible.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _one_game(job: Dict[str, Any], cfg: Dict[str, Any], seed: int, q):
    """Play ONE game in its own process."""
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)          # mandatory: one BLAS thread per worker
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce, c019_determinize as D19
    from cg import c022_mcgs_agent as AG

    deck = D19.archetype_decks()["mega_lucario"]
    provider, arm = None, None
    if job.get("transfer_arm"):
        from cg import c021_transfer as TR
        arm = TR.arm_config(job["transfer_arm"])
        ck = job.get("byterl_checkpoint")
        if ck and any(arm.values()):
            provider = TR.ByteRLPriorProvider(ck)
    # Each game gets its own world base seed, so two games never search identical worlds; paired
    # arms reuse the SAME seed for the same game_id, which is what makes them paired.
    gcfg = dict(cfg)
    gcfg["world_base_seed"] = int(job["world_base_seed"])
    ag = AG.MultiDetMCGSAgent(deck, gcfg, seed=seed, prior_provider=provider, transfer_arm=arm)

    opp = T.make_fresh(job["opponent"], ce.SOURCES)
    seat = int(job["seat"])

    def mk(a):
        def f(o):
            return a.act(o)
        return f

    def mo(o):
        def f(x):
            return o(x)
        return f

    agents = [mk(ag), mo(opp)] if seat == 0 else [mo(opp), mk(ag)]
    t0 = time.time()
    completed, score = False, None
    statuses, rewards, n_steps = None, None, 0
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        # Record WHY a game did not score. The first version stored only completed/score, so a
        # game that ran to the end of env.run without both seats DONE fell into neither the
        # completed bucket nor the abandoned bucket -- 10 of 60 in the first arm, 17%, silently
        # excluded from the field score with no category naming them. An unscored game is a real
        # outcome and must be counted as one.
        statuses = [s.status for s in last]
        rewards = [s.reward for s in last]
        n_steps = len(env.steps)
        if statuses == ["DONE", "DONE"] and rewards[seat] is not None:
            completed = True
            score = (1.0 if rewards[seat] > rewards[1 - seat]
                     else (0.5 if rewards[seat] == rewards[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        q.put({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200],
               "seconds": round(time.time() - t0, 2)})
        return

    # Staple the realised outcome onto every calibration row. A predicted probability with no
    # realised outcome cannot be calibrated against anything.
    cal = ag.calibration
    for row in cal:
        row["realised"] = score
        row["game_id"] = job["game_id"]
        row["opponent"] = job["opponent"]
    q.put({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
           "completed": completed, "score": score,
           "statuses": statuses, "rewards": rewards, "env_steps": n_steps,
           "agent_exceptions": len(ag.exceptions),
           "seconds": round(time.time() - t0, 2),
           "report": ag.report(),
           "calibration": cal,
           "traces": ag.traces[:2],
           "exceptions": ag.exceptions[:2]})


def run_arm(a) -> Dict[str, Any]:
    cfg = {
        "branch": a.branch,
        "k_worlds": a.k,
        "budget_protocol": a.protocol,
        "simulations_per_decision": a.sims,
        "aggregation_rule": a.aggregation,
        "graph_reuse": bool(a.graph_reuse),
        "match_clock_seconds": float(a.match_clock),
        "decision_seconds_cap": float(a.decision_cap),
        "decision_wall_ceiling_seconds": float(a.wall_ceiling),
        "decision_budget": int(a.decision_budget),
    }
    # 0 means "keep the source value already in REFERENCE_CFG". Only the deploy arm overrides.
    if float(getattr(a, "first_move_seconds", 0.0)) > 0:
        cfg["first_move_seconds"] = float(a.first_move_seconds)
    if float(getattr(a, "continuing_move_seconds", 0.0)) > 0:
        cfg["continuing_move_seconds"] = float(a.continuing_move_seconds)
    jobs = [{"game_id": f"{a.tag}:g{i}",
             "opponent": OPPONENTS[i % len(OPPONENTS)],
             "seat": i % 2,
             # Paired across arms: game i always gets world base seed derived from i alone, so
             # arm A and arm B searching game i search the SAME hidden worlds.
             "world_base_seed": a.seed * 1000003 + i,
             "transfer_arm": a.transfer_arm,
             "byterl_checkpoint": a.byterl_checkpoint}
            for i in range(a.games)]

    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    results: List[Dict[str, Any]] = []
    running: Dict[str, Any] = {}
    pending = list(jobs)
    # The agent seed must depend ONLY on the job index. Deriving it from `len(results) +
    # len(running)` -- which the first version did -- makes it depend on completion TIMING, so
    # re-running the identical command gives different agent RNG streams and the arm is not
    # reproducible. Worlds were unaffected (they come from world_base_seed), but the
    # out-of-budget fallback and every agent-side tie-break were, which is enough to break
    # M13's matched seeds and F03's requirement that reported numbers recompute from raw data.
    for i, j in enumerate(jobs):
        j["agent_seed"] = a.seed + i
    t0 = time.time()
    deadline = t0 + a.arm_timeout

    while (pending or running) and time.time() < deadline:
        while pending and len(running) < a.nproc:
            job = pending.pop(0)
            p = ctx.Process(target=_one_game, args=(job, cfg, job["agent_seed"], q))
            p.start()
            running[job["game_id"]] = (p, job, time.time())
        # Drain CONTINUOUSLY. Reading only after join() is what made c021 record live children
        # as abandoned.
        drained = 0
        while True:
            try:
                results.append(q.get(timeout=0.25))
                drained += 1
            except Exception:  # noqa: BLE001
                break
        for gid, (p, job, started) in list(running.items()):
            if not p.is_alive():
                p.join(timeout=1)
                del running[gid]
            elif time.time() - started > a.game_timeout:
                p.terminate()
                p.join(timeout=5)
                del running[gid]
                results.append({"game_id": gid, "opponent": job["opponent"],
                                "completed": False, "score": None,
                                "abandoned": True,
                                "seconds": round(time.time() - started, 1)})
    for gid, (p, job, started) in list(running.items()):
        p.terminate()
        p.join(timeout=5)
        results.append({"game_id": gid, "opponent": job.get("opponent"),
                        "completed": False, "score": None, "abandoned": True,
                        "arm_timeout": True})
    while True:
        try:
            results.append(q.get(timeout=0.5))
        except Exception:  # noqa: BLE001
            break

    # A terminated game can appear TWICE: once as the abandoned marker written when the process
    # was killed, and once as a real result the child had already put on the queue before dying.
    # Counting both would make `games_accounted` exceed `games` and would let an abandoned
    # marker shadow a genuine score. Deduplicate by game_id, preferring the real result.
    by_id = {}
    duplicates = 0
    for r in results:
        gid = r.get("game_id")
        if gid is None:
            continue
        prev = by_id.get(gid)
        if prev is None:
            by_id[gid] = r
            continue
        duplicates += 1
        if prev.get("abandoned") and not r.get("abandoned"):
            by_id[gid] = r
    results = list(by_id.values())

    # ---------------------------------------------------------------- aggregate
    os.makedirs(a.out, exist_ok=True)
    scored = [r for r in results if r.get("completed") and r.get("score") is not None]
    abandoned = [r for r in results if r.get("abandoned")]
    errored = [r for r in results if r.get("error")]
    # Every game must land in exactly one bucket, and the buckets must sum to `games`. A game
    # that finishes env.run without both seats DONE is UNSCORED -- a real outcome, not an
    # absence -- and its terminal statuses are recorded so the category is diagnosable rather
    # than merely counted.
    unscored = [r for r in results
                if not r.get("completed") and not r.get("abandoned") and not r.get("error")]
    status_hist = collections.Counter(
        "|".join(map(str, r.get("statuses") or [])) for r in unscored)
    wins = sum(r["score"] for r in scored)
    n = len(scored)

    agg_stats: Dict[str, Any] = collections.defaultdict(float)
    for r in results:
        for k, v in (r.get("report") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                agg_stats[k] += v

    per_opp = collections.defaultdict(lambda: [0, 0.0])
    for r in scored:
        per_opp[r["opponent"]][0] += 1
        per_opp[r["opponent"]][1] += r["score"]

    cal_rows = [row for r in results for row in (r.get("calibration") or [])]
    with open(os.path.join(a.out, f"{a.tag}_calibration.jsonl"), "w") as fh:
        for row in cal_rows:
            fh.write(json.dumps(row) + "\n")
    with open(os.path.join(a.out, f"{a.tag}_games.jsonl"), "w") as fh:
        for r in results:
            fh.write(json.dumps({k: r.get(k) for k in
                                 ("game_id", "opponent", "seat", "completed", "score",
                                  "seconds", "abandoned", "error", "statuses", "rewards",
                                  "env_steps", "agent_exceptions")}) + "\n")
    with open(os.path.join(a.out, f"{a.tag}_traces.jsonl"), "w") as fh:
        for r in results:
            for t in (r.get("traces") or []):
                fh.write(json.dumps({"game_id": r.get("game_id"), **t}) + "\n")

    sd = max(1.0, agg_stats.get("searched_decisions", 0.0))
    summary = {
        "tag": a.tag, "branch": a.branch, "config": cfg,
        "seed": a.seed, "nproc": a.nproc,
        "games": a.games, "completed": n,
        "abandoned": len(abandoned), "errored": len(errored),
        "unscored": len(unscored),
        "unscored_status_histogram": dict(status_hist),
        "unscored_mean_seconds": round(
            sum(float(r.get("seconds") or 0) for r in unscored) / len(unscored), 1)
        if unscored else None,
        "games_accounted": len(scored) + len(abandoned) + len(errored) + len(unscored),
        "duplicate_records_collapsed": duplicates,
        "all_games_accounted": (len(scored) + len(abandoned) + len(errored)
                                + len(unscored)) == a.games,
        "effective_n_note": "field_score is computed over `completed` only. abandoned, errored "
                            "and unscored games are excluded, so `completed` is the effective "
                            "sample size and the Wilson interval is computed on it.",
        "abandoned_note": "games exceeding the per-game wall clock; EXCLUDED from the field "
                          "score rather than scored as losses",
        "field_score": round(wins / n, 4) if n else None,
        "wilson95": wilson(round(wins), n) if n else [None, None],
        # The field score is computed over COMPLETED games only. Every excluded game is a game
        # whose outcome is unknown, so the honest reading is an interval: best case they were
        # all wins, worst case all losses. Reporting only the point estimate would let an arm
        # look better the more games it failed to score.
        "field_score_bounds_if_unscored_counted": [
            round(wins / (n + len(abandoned) + len(unscored)), 4)
            if (n + len(abandoned) + len(unscored)) else None,
            round((wins + len(abandoned) + len(unscored))
                  / (n + len(abandoned) + len(unscored)), 4)
            if (n + len(abandoned) + len(unscored)) else None],
        "excluded_fraction": round(
            (len(abandoned) + len(unscored) + len(errored)) / max(1, a.games), 4),
        "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4)}
                         for k, v in sorted(per_opp.items()) if v[0]},
        "wall_clock_s": round(time.time() - t0, 1),
        "searched_decisions": int(agg_stats.get("searched_decisions", 0)),
        "total_simulations": int(agg_stats.get("searches", 0)),
        "sims_per_decision": round(agg_stats.get("searches", 0.0) / sd, 1),
        "mean_k_used": round(agg_stats.get("k_used_total", 0.0) / sd, 3),
        "world_errors": int(agg_stats.get("world_errors", 0)),
        "decision_deadline_stops": int(agg_stats.get("decision_deadline_stops", 0)),
        "match_clock_exhausted_decisions": int(
            agg_stats.get("match_clock_exhausted_decisions", 0)),
        "decision_budget": int(a.decision_budget),
        "derived_game_timeout_s": round(float(a.game_timeout), 1),
        "game_timeout_basis": getattr(a, "game_timeout_basis", "unknown"),
        "effective_seconds_per_simulation": round(
            a.seconds_per_simulation * (1.0 + a.k_overhead * (a.k - 1)), 5),
        "decision_budget_exhausted_decisions": int(
            agg_stats.get("decision_budget_exhausted_decisions", 0)),
        "decisions_total": int(agg_stats.get("decisions", 0)),
        "signature_mismatches": int(agg_stats.get("signature_mismatches", 0)),
        "opponent_flag_conflicts": int(agg_stats.get("opponent_flag_conflicts", 0)),
        "multiselect_decisions": int(agg_stats.get("multiselect_decisions", 0)),
        "obliged_decisions": int(agg_stats.get("obliged_decisions", 0)),
        "mixed_terminal_scale_decisions": int(
            agg_stats.get("mixed_terminal_scale_decisions", 0)),
        "aggregate_empty_decisions": int(agg_stats.get("aggregate_empty_decisions", 0)),
        "term_root_win": int(agg_stats.get("term_root_win", 0)),
        "term_root_loss": int(agg_stats.get("term_root_loss", 0)),
        "term_undecided": int(agg_stats.get("term_undecided", 0)),
        "finalised": int(agg_stats.get("finalised", 0)),
        "terminal_leaves": int(agg_stats.get("terminal_leaves", 0)),
        "lethal_bonus": int(agg_stats.get("lethal_bonus", 0)),
        "step_errors": int(agg_stats.get("step_errors", 0)),
        "begin_errors": int(agg_stats.get("begin_errors", 0)),
        "transposition_merges": int(agg_stats.get("transposition_merges", 0)),
        "dummy_edges": int(agg_stats.get("dummy_edges", 0)),
        "chance_nodes_created": int(agg_stats.get("chance_nodes_created", 0)),
        "manual_coin_node_ucb_selected": int(
            agg_stats.get("manual_coin_node_ucb_selected", 0)),
        "calibration_rows": len(cal_rows),
        "budget_delivered": bool(agg_stats.get("decision_deadline_stops", 0) == 0),
    }
    if a.protocol == "source_time":
        # A MEAN is the wrong statistic for a timed arm and is actively misleading here. The
        # first probe reported 82,540 simulations per decision; the MEDIAN was 610, and two
        # decisions out of 57 accounted for 99.2% of every simulation the arm ran. Those two are
        # decisions where the tree reached an already-decided line and the rollouts became
        # essentially free, so the arm spent minutes re-confirming a result it already had.
        #
        # Reporting the mean would have said "the source's schedule buys 860x the search of the
        # causal sweeps". The median says 6.4x. Only one of those is a fact about the schedule.
        sims_sorted = sorted(int(r.get("simulations") or 0) for r in cal_rows
                             if r.get("simulations"))
        if sims_sorted:
            def _q(f):
                return sims_sorted[int(f * (len(sims_sorted) - 1))]
            summary["sims_per_decision_distribution"] = {
                "n": len(sims_sorted), "min": sims_sorted[0], "p25": _q(0.25),
                "median": _q(0.5), "p75": _q(0.75), "p90": _q(0.9), "max": sims_sorted[-1],
                "mean": round(sum(sims_sorted) / len(sims_sorted), 1),
                "share_of_all_simulations_in_top_3_decisions": round(
                    sum(sims_sorted[-3:]) / max(1, sum(sims_sorted)), 4),
                "why": ("the mean is dominated by decisions whose search collapsed onto an "
                        "already-decided line; the median is what the schedule buys"),
            }
        # In this protocol the simulation count is the OUTCOME, so `budget_delivered` -- which
        # asks whether the configured count was reached -- has no meaning and would report
        # vacuously true. Replace it with the question that does have meaning: did the arm
        # actually search on the source's schedule, or did a stray count/ceiling bind first?
        #
        # `--sims 0` is the sentinel for "no count is being requested". If a protocol typo ever
        # sends a count-budgeted arm down this path, sims_per_decision collapses to that count
        # and this flag goes false instead of the arm looking like it executed.
        sd_reported = summary["sims_per_decision"]
        summary["budget_delivered"] = bool(sd_reported > max(4.0, 4.0 * float(a.sims)))
        summary["source_time_note"] = (
            "simulations are a MEASUREMENT here, not a budget; `budget_delivered` asserts the "
            "wall schedule bound rather than a count or the safety ceiling")
        summary["schedule_seconds"] = {
            "first_move": float(a.first_move_seconds or 15.0),
            "continuing": float(a.continuing_move_seconds or 10.0),
            "decision_wall_ceiling": float(a.wall_ceiling),
        }
    with open(os.path.join(a.out, f"{a.tag}_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--branch", default="MCGS_2019_PTCG_MULTI_DET_REFERENCE")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--protocol", default="fixed_total",
                    choices=["fixed_total", "fixed_per_world", "source_time"],
                    help="source_time is the M11 arm ONLY: search runs to the source's 15 s / "
                         "10 s wall schedule and the simulation count becomes a measurement. "
                         "A4 forbids it in any causal K comparison.")
    ap.add_argument("--sims", type=int, default=512)
    ap.add_argument("--aggregation", default="source_sum",
                    choices=["source_sum", "visit_sum", "robust_lcb"])
    ap.add_argument("--graph-reuse", type=int, default=0)
    ap.add_argument("--match-clock", type=float, default=0.0)
    ap.add_argument("--decision-cap", type=float, default=0.0)
    ap.add_argument("--wall-ceiling", type=float, default=120.0)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nproc", type=int, default=12)
    ap.add_argument("--seed", type=int, default=90210)
    ap.add_argument("--game-timeout", type=float, default=0.0,
                    help="absolute per-game wall clock. 0 = derive it from the arm's "
                         "per-decision simulation cost so every K is cut at the same DECISION, "
                         "not at the same second")
    ap.add_argument("--decision-budget", type=int, default=260,
                    help="how many searched decisions a game is allowed before it is cut. This, "
                         "not wall clock, is what must be equal across K.")
    ap.add_argument("--seconds-per-simulation", type=float, default=0.1224,
                    help="measured cost of one MCGS simulation at K=1, under load. Used with "
                         "--k-overhead to convert the decision budget into a wall-clock guard. "
                         "Over-estimating is safe: the guard is a backstop, and the decision "
                         "budget is the real cut.")
    ap.add_argument("--k-overhead", type=float, default=0.34,
                    help="fractional extra cost per ADDITIONAL world, at equal total "
                         "simulations. Measured 0.34: ft_k1 ran at 122.4 ms/simulation/worker "
                         "and ft_k2 at 164.0, with an identical 192-simulation budget. Opening "
                         "K sessions per decision is not free.")
    ap.add_argument("--game-timeout-base", type=float, default=0.0,
                    help="per-game wall guard at K=1 in seconds, scaled by --k-overhead for "
                         "higher K. When > 0 this REPLACES the search-cost derivation. Set it "
                         "from MEASURED completed-game duration: abandonment here is dominated "
                         "by non-terminating games, which consume whatever guard they are "
                         "given, while normal games finish far inside it.")
    # The source's schedule is 15 s / 10 s (SearchConfig.cs). The c021 DEPLOYMENT arm scaled it
    # to 0.9 s / 0.7 s under a 90 s cumulative match clock -- those are not invented numbers,
    # they are read off the frozen C021_MCGS_K1_CONTROL config. Exposed as flags so the M11
    # reference arm and the M12 deploy arm can differ in exactly this and nothing else.
    ap.add_argument("--first-move-seconds", type=float, default=0.0,
                    help="0 = the source value (15 s). The deploy arm passes c021's 0.9.")
    ap.add_argument("--continuing-move-seconds", type=float, default=0.0,
                    help="0 = the source value (10 s). The deploy arm passes c021's 0.7.")
    ap.add_argument("--arm-timeout", type=float, default=14400.0)
    ap.add_argument("--transfer-arm", default=None)
    ap.add_argument("--byterl-checkpoint", default=None)
    ap.add_argument("--out", default=os.path.join(MC, "k_sweeps"))
    a = ap.parse_args(argv)

    # A per-game WALL CLOCK cuts high-K arms earlier in DECISION space than low-K arms, because
    # a K=8 decision costs 8x a K=1 decision under fixed_per_world. Abandoned games are excluded
    # from the field score, so the surviving subsample would be systematically shorter at high K
    # and "K=8 is worse" would be indistinguishable from "K=8 dropped its long games".
    #
    # The guard is therefore derived from the arm's own per-decision cost, so every K is cut at
    # roughly the same decision number. `abandoned` is reported per arm regardless, and an arm
    # whose abandonment differs materially from its K=1 control has no valid causal claim.
    total_sims = a.sims if a.protocol == "fixed_total" else a.sims * a.k
    # The guard must be K-AWARE. ft_k1 and ft_k2 ran the identical 192-simulation budget and
    # cost 122.4 and 164.0 ms per simulation per worker -- opening K sessions per decision, each
    # with its own world sample, root construction, transposition table and teardown, is a real
    # per-decision cost that grows with K and is invisible to a simulation count.
    #
    # A guard derived from a K-independent cost therefore under-provisions high-K arms, cuts
    # more of their long games, and -- because excluded games leave the field score -- scores
    # them on a shorter population. That is exactly the confound the decision budget was
    # introduced to remove (D08), returning through the guard.
    k_factor = 1.0 + a.k_overhead * (a.k - 1)
    eff_sec_per_sim = a.seconds_per_simulation * k_factor
    basis = "search_cost_estimate"
    if a.game_timeout <= 0:
        if a.game_timeout_base > 0:
            # Derived from MEASURED completed-game duration, not from search cost.
            #
            # ft_k1 completed 29 games at a mean of 148.7 s and a MAXIMUM of 275 s, while its
            # three abandoned games each ran to exactly 1881.9 s -- the guard, to a tenth of a
            # second. Those are not slow games. They are games that do not terminate, and they
            # will consume whatever guard they are given.
            #
            # Two consequences. First, abandonment here measures the STALEMATE RATE, which is a
            # property of the game and not of K, so it does not confound the K comparison the
            # way a cost-driven cut would. Second, the guard IS the arm's wall time, because an
            # arm cannot finish until its stalemates time out -- so sizing the guard to the
            # search budget bought nothing but a longer arm.
            a.game_timeout = max(300.0, a.game_timeout_base * k_factor)
            basis = "measured_completed_game_duration"
        else:
            a.game_timeout = max(
                300.0, a.decision_budget * total_sims * eff_sec_per_sim * 1.6)
    a.derived_game_timeout = True
    a.game_timeout_basis = basis
    print(f"[arm {a.tag}] K={a.k} protocol={a.protocol} total_sims/decision={total_sims} "
          f"eff_ms/sim={eff_sec_per_sim*1000:.0f} k_factor={k_factor:.2f} "
          f"-> game_timeout={a.game_timeout:.0f}s ({basis})", flush=True)
    s = run_arm(a)
    print(json.dumps({k: s[k] for k in
                      ("tag", "games", "completed", "abandoned", "field_score", "wilson95",
                       "sims_per_decision", "mean_k_used", "total_simulations",
                       "budget_delivered", "match_clock_exhausted_decisions",
                       "decision_budget_exhausted_decisions", "searched_decisions",
                       "unscored", "unscored_status_histogram", "all_games_accounted",
                       "signature_mismatches", "mixed_terminal_scale_decisions",
                       "world_errors", "wall_clock_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

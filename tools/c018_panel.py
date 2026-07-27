"""c018 M05 / P17 — frozen final gameplay panel.

Identity-safe by construction: every raw game row carries its own `candidate_id`,
`opponent_id`, `seat` and `seed`, and aggregates are recomputed from those rows. Worker results
are NEVER positionally zipped back onto the job list -- that is how a panel silently attributes
one agent's wins to another.

Every candidate faces the SAME opponents at the SAME seeds and seats. The pairing schedule is
built once, up front, so a candidate added later cannot get an easier draw.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
PANEL = os.path.join(C18, "final_panel")
OPPONENTS = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - m) / d, 4), round((c + m) / d, 4))


def build_agent(cid, deck, seed):
    """Every candidate is constructed here, so the panel controls identity rather than
    inheriting whatever a caller happened to pass."""
    from cg import teachers as T, c009_eval as ce
    import c018_search as S
    rng = np.random.default_rng(seed)

    if cid == "official_mega_lucario":
        # wrapped in a plain function on purpose: kaggle_environments errors out the seat when
        # handed the teacher callable directly, which silently zeroed this candidate's games
        official = T.make_fresh("mega_lucario", ce.SOURCES)
        return (lambda o: official(o)), None

    base = T.make_fresh("mega_lucario", ce.SOURCES)
    stats = S.new_stats()
    guide = None
    if cid in ("m04_guided_search", "m03_curriculum_policy"):
        import c018_guided as G
        guide = G.Guide(os.path.join(C18, "checkpoints", "m03_curriculum.npz"))

    if cid == "m03_curriculum_policy":
        # the learned policy playing directly, no search -- isolates what training alone bought
        pol = guide.pol

        def play(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            try:
                order = guide.order(obs, len(sel["option"]))
                lo = int(sel.get("minCount") or 1)
                hi = int(sel.get("maxCount") or 1)
                n = max(lo, min(hi, 1))
                act = sorted(order[:n])
                from cg.safe_policy import validate_selection
                validate_selection(list(act), len(sel["option"]), sel["minCount"],
                                   sel["maxCount"])
                return act
            except Exception:  # noqa: BLE001
                return base(obs)
        return play, stats

    def play(obs):
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            return base(obs)
        stats["decisions"] += 1
        b = base(obs)
        r = S.plan(obs, b, deck, rng, S.DEFAULT_CFG, stats, None, guide=guide)
        a = r["action"]
        try:
            from cg.safe_policy import validate_selection
            validate_selection(list(a), len(sel["option"]), sel["minCount"], sel["maxCount"])
        except Exception:  # noqa: BLE001
            stats["invalid_search_action"] += 1
            a = list(b)
        return a
    return play, stats


def play_one(job):
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    deck = T.read_deck("mega_lucario", ce.SOURCES)
    me, stats = build_agent(job["candidate_id"], deck, job["seed"])
    opp = T.make_fresh(job["opponent_id"], ce.SOURCES)
    seat = job["seat"]
    agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
    row = dict(job)
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        st = [s.status for s in last]
        rw = [s.reward for s in last]
        row["statuses"] = st
        row["completed"] = st == ["DONE", "DONE"]
        if row["completed"] and rw[seat] is not None and rw[1 - seat] is not None:
            row["score"] = (1.0 if rw[seat] > rw[1 - seat] else
                            0.5 if rw[seat] == rw[1 - seat] else 0.0)
        else:
            row["score"] = None
    except Exception as e:  # noqa: BLE001
        row["statuses"] = ["ERROR", "ERROR"]
        row["completed"] = False
        row["score"] = None
        row["exception"] = f"{type(e).__name__}: {e}"
    if stats is not None:
        row["search_stats"] = {k: (round(v, 2) if isinstance(v, float) else v)
                               for k, v in stats.items()}
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="official_mega_lucario,m01_heuristic_search,"
                                            "m04_guided_search,m03_curriculum_policy")
    ap.add_argument("--games-per-pair", type=int, default=40)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1805)
    a = ap.parse_args(argv)
    cands = [c for c in a.candidates.split(",") if c]

    os.makedirs(PANEL, exist_ok=True)
    # One schedule, built before any game runs: identical opponents, seeds and seats for all.
    jobs = []
    for oi, opp in enumerate(OPPONENTS):
        for g in range(a.games_per_pair):
            seed = a.seed + oi * 10007 + g
            for c in cands:
                jobs.append({"candidate_id": c, "opponent_id": opp, "seat": g % 2,
                             "seed": seed, "pair_index": g})
    print(f"[c018 panel] {len(jobs)} games: {len(cands)} candidates x {len(OPPONENTS)} "
          f"opponents x {a.games_per_pair}", flush=True)

    t0 = time.time()
    rows = []
    if a.nproc > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.nproc) as pool:
            for i, r in enumerate(pool.imap_unordered(play_one, jobs, chunksize=2)):
                rows.append(r)
                if (i + 1) % 100 == 0:
                    print(f"[c018 panel] {i+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
    else:
        for j in jobs:
            rows.append(play_one(j))

    raw = os.path.join(PANEL, "raw_games.jsonl.gz")
    with gzip.open(raw, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")

    # aggregate ONLY from the identity fields on each row
    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in rows:
        if r.get("score") is None:
            continue
        agg[(r["candidate_id"], r["opponent_id"])][0] += 1
        agg[(r["candidate_id"], r["opponent_id"])][1] += r["score"]
    results = []
    for c in cands:
        row = {"candidate_id": c}
        tot_n = tot_s = 0
        worst = (2.0, None)
        for o in OPPONENTS:
            n, s = agg[(c, o)]
            row[f"{o}_games"] = n
            row[f"{o}_rate"] = round(s / n, 4) if n else None
            if n:
                lo, hi = wilson(s, n)
                row[f"{o}_ci"] = [lo, hi]
                if s / n < worst[0]:
                    worst = (s / n, o)
            tot_n += n
            tot_s += s
        row["games"] = tot_n
        row["overall_rate"] = round(tot_s / tot_n, 4) if tot_n else None
        row["overall_ci"] = list(wilson(tot_s, tot_n)) if tot_n else None
        row["worst_matchup"] = worst[1]
        row["worst_matchup_rate"] = round(worst[0], 4) if worst[1] else None
        results.append(row)
    # lexicographic: overall first, worst matchup as the tie-break -- a candidate that is
    # merely average everywhere beats one that is excellent except against a real archetype
    results.sort(key=lambda r: (-(r["overall_rate"] or 0), -(r["worst_matchup_rate"] or 0)))

    h = hashlib.sha256()
    with open(raw, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    json.dump(results, open(os.path.join(PANEL, "final_panel_results.json"), "w"), indent=2,
              default=str)
    meta = {"probe_id": "P17", "candidates": cands, "opponents": OPPONENTS,
            "games_per_pair": a.games_per_pair, "planned_games": len(jobs),
            "played_games": len(rows),
            "scored_games": sum(1 for r in rows if r.get("score") is not None),
            "incomplete_games": sum(1 for r in rows if not r.get("completed")),
            "seed_base": a.seed, "identical_seeds_and_seats_across_candidates": True,
            "raw_file": os.path.relpath(raw, C18), "raw_sha256": h.hexdigest(),
            "wall_clock_s": round(time.time() - t0, 1),
            "ranking_rule": "overall_rate desc, then worst_matchup_rate desc (pre-registered)"}
    json.dump(meta, open(os.path.join(PANEL, "panel_meta.json"), "w"), indent=2, default=str)
    print(json.dumps(meta, indent=2, default=str))
    for r in results:
        print(f"  {r['candidate_id']:26s} n={r['games']:4d} overall={r['overall_rate']} "
              f"ci={r['overall_ci']} worst={r['worst_matchup']}@{r['worst_matchup_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

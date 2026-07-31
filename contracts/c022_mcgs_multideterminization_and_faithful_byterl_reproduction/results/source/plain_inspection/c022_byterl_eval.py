"""c022 — evaluate a ByteRL checkpoint against the frozen external panel.

`TRAINING_AND_EVALUATION §3` requires, at fixed sample milestones, a frozen checkpoint evaluated
against the same registered external field with paired seeds, tracking external win rate and
confidence interval, per-matchup results, entropy and action diversity, deck legality and
diversity, and held-out value calibration.

`§3` also says: "Internal self-play or historical-policy win rate may not be the sole
continuation criterion." That is why this exists as a separate tool reading a frozen checkpoint,
rather than as a number the training loop reports about itself. The training loop's `win_rate` is
measured on the very games that produced the gradient; this is not.

Value calibration is measured here too, because `B23` asks for it against the right comparators:
a CONSTANT predictor at the observed base rate, and the outcome itself. A value head that cannot
beat a constant has learned nothing about which positions are good, however small its MSE looks.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import multiprocessing as mp
import os
import statistics
import sys
import time
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
BY = os.path.join(C22, "byterl")
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _one_game(job, q):
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_actor as ACT
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=0)
    ck = job.get("checkpoint")
    loaded = False
    if ck and os.path.isfile(ck):
        net.load_state_dict(torch.load(ck, map_location="cpu", weights_only=False))
        loaded = True
    net.eval()

    rng = np.random.default_rng(job["seed"])
    fixed = None if job["learn_construction"] else DK.greedy_reference_deck(pool)
    runner = ACT.EpisodeRunner(net, pool, rng, job["learn_construction"], fixed,
                               unroll_length=32, temperature=job.get("temperature", 1.0))
    deck, deck_legal = runner.build_deck()
    opp = T.make_fresh(job["opponent"], ce.SOURCES)
    seat = int(job["seat"])

    def me(o):
        return runner.act(o)

    def them(o):
        return opp(o)

    agents = [me, them] if seat == 0 else [them, me]
    t0 = time.time()
    completed, score, statuses = False, None, None
    try:
        env = make("cabt")
        env.run(agents)
        last = env.steps[-1]
        statuses = [s.status for s in last]
        rw = [s.reward for s in last]
        if statuses == ["DONE", "DONE"] and rw[seat] is not None:
            completed = True
            score = (1.0 if rw[seat] > rw[1 - seat]
                     else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
    except Exception as e:  # noqa: BLE001
        q.put({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:180]})
        return

    # value predictions, paired with the realised outcome, for B23
    vals = [s.value for s in runner.steps if s.stage == EN.STAGE_BATTLE]
    ents = []
    for s in runner.steps:
        toks = s.seq.get("tokens") or []
        if toks:
            ents.append(len(toks))
    q.put({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
           "completed": completed, "score": score, "statuses": statuses,
           "checkpoint_loaded": loaded,
           "deck_legal": bool(deck_legal), "deck": sorted(deck),
           "n_construction": runner.n_construction, "n_battle": runner.n_battle,
           "illegal_sequences": runner.illegal_sequences,
           "mean_value": round(statistics.fmean(vals), 6) if vals else None,
           "values": [round(v, 5) for v in vals[:400]],
           "mean_tokens_per_decision": round(statistics.fmean(ents), 3) if ents else None,
           "seconds": round(time.time() - t0, 2)})


def evaluate(checkpoint, games, nproc, seed, learn_construction, tag, out_dir,
             temperature=1.0, timeout=900.0):
    jobs = [{"game_id": f"{tag}:g{i}", "opponent": OPPONENTS[i % len(OPPONENTS)],
             "seat": i % 2, "seed": seed * 1000003 + i, "checkpoint": checkpoint,
             "learn_construction": bool(learn_construction), "temperature": temperature}
            for i in range(games)]
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    results, running, pending = [], {}, list(jobs)
    t0 = time.time()
    while (pending or running) and time.time() - t0 < timeout:
        while pending and len(running) < nproc:
            j = pending.pop(0)
            p = ctx.Process(target=_one_game, args=(j, q))
            p.start()
            running[j["game_id"]] = (p, time.time())
        while True:
            try:
                results.append(q.get(timeout=0.25))
            except Exception:  # noqa: BLE001
                break
        for gid, (p, st) in list(running.items()):
            if not p.is_alive():
                p.join(timeout=1)
                del running[gid]
    for gid, (p, st) in list(running.items()):
        p.terminate()
        p.join(timeout=3)
    while True:
        try:
            results.append(q.get(timeout=0.5))
        except Exception:  # noqa: BLE001
            break
    by_id = {}
    for r in results:
        by_id.setdefault(r.get("game_id"), r)
    results = list(by_id.values())

    scored = [r for r in results if r.get("completed") and r.get("score") is not None]
    n = len(scored)
    wins = sum(r["score"] for r in scored)
    per_opp = collections.defaultdict(lambda: [0, 0.0])
    for r in scored:
        per_opp[r["opponent"]][0] += 1
        per_opp[r["opponent"]][1] += r["score"]

    # ---- B23 value calibration, against the comparators that make it meaningful
    pairs = [(v, r["score"]) for r in scored for v in (r.get("values") or [])]
    vcal = {"n": len(pairs)}
    if pairs:
        preds = [p for p, _ in pairs]
        ys = [y for _, y in pairs]
        base = statistics.fmean(ys)
        mse = statistics.fmean((p - y) ** 2 for p, y in pairs)
        mse_const = statistics.fmean((base - y) ** 2 for y in ys)
        mp_, my = statistics.fmean(preds), base
        sp = statistics.pstdev(preds) or 1e-9
        sy = statistics.pstdev(ys) or 1e-9
        corr = statistics.fmean((p - mp_) * (y - my) for p, y in pairs) / (sp * sy)
        vcal.update({
            "mean_prediction": round(mp_, 5),
            "observed_base_rate": round(base, 5),
            "mse": round(mse, 6),
            "mse_constant_baseline": round(mse_const, 6),
            "skill_vs_constant": round(1 - mse / mse_const, 4) if mse_const > 0 else None,
            "beats_constant_predictor": bool(mse < mse_const),
            "pearson_correlation_with_outcome": round(corr, 4),
            "note": "B23: a value head that cannot beat a CONSTANT predictor at the observed "
                    "base rate has learned nothing about which positions are good, however "
                    "small its MSE looks in absolute terms.",
        })

    decks = [tuple(r["deck"]) for r in results if r.get("deck")]
    legal = [r for r in results if r.get("deck_legal")]
    summary = {
        "tag": tag, "checkpoint": checkpoint,
        "checkpoint_loaded": all(r.get("checkpoint_loaded") for r in results) if results
                             else None,
        "arm": "END_TO_END" if learn_construction else "FIXED_DECK",
        "games": games, "completed": n,
        "errored": sum(1 for r in results if r.get("error")),
        "unscored": sum(1 for r in results
                        if not r.get("completed") and not r.get("error")),
        "field_score": round(wins / n, 4) if n else None,
        "wilson95": wilson(wins, n) if n else [None, None],
        "per_opponent": {k: {"games": v[0], "rate": round(v[1] / v[0], 4)}
                         for k, v in sorted(per_opp.items()) if v[0]},
        "deck_legal_rate": round(len(legal) / max(1, len(results)), 4),
        "distinct_decks": len(set(decks)),
        "deck_diversity": round(len(set(decks)) / max(1, len(decks)), 4),
        "illegal_sequences": sum(r.get("illegal_sequences", 0) or 0 for r in results),
        "mean_tokens_per_decision": round(statistics.fmean(
            [r["mean_tokens_per_decision"] for r in results
             if r.get("mean_tokens_per_decision")]), 3)
        if any(r.get("mean_tokens_per_decision") for r in results) else None,
        "value_calibration": vcal,
        "seed": seed, "temperature": temperature,
        "wall_clock_s": round(time.time() - t0, 1),
        "panel": OPPONENTS,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{tag}_eval.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    with open(os.path.join(out_dir, f"{tag}_games.jsonl"), "w") as fh:
        for r in results:
            fh.write(json.dumps({k: r.get(k) for k in
                                 ("game_id", "opponent", "seat", "completed", "score",
                                  "statuses", "deck_legal", "n_battle", "n_construction",
                                  "error")}) + "\n")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None,
                    help="omit to evaluate FRESH RANDOM WEIGHTS -- the floor every learning "
                         "claim is measured against")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--games", type=int, default=128)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--seed", type=int, default=777001)
    ap.add_argument("--learn-construction", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--out", default=os.path.join(BY, "external_evaluations"))
    a = ap.parse_args(argv)

    s = evaluate(a.checkpoint, a.games, a.nproc, a.seed, a.learn_construction,
                 a.tag, a.out, a.temperature, a.timeout)
    print(json.dumps({k: s[k] for k in
                      ("tag", "arm", "games", "completed", "field_score", "wilson95",
                       "per_opponent", "deck_legal_rate", "distinct_decks",
                       "illegal_sequences", "checkpoint_loaded", "wall_clock_s")}, indent=1))
    print("value:", json.dumps(s["value_calibration"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

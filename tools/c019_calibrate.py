"""c019 — actor throughput calibration and B01 mask verification.

The ByteRL floors (60,000 actual games, 20,000 optimizer steps, >=5 OSFP learning periods) are
wall-clock bound, and `inputs/PROJECT_GROUND_TRUTH.md` warns explicitly that c018's ~39,000
games/hour does not transfer to a recurrent actor-learner. Measuring games/hour for ONE actor
now — while unroll length, actor count and batch size are still design choices — is worth more
than discovering the shortfall after the learner is written.

Also verifies B01 on live decisions: unavailable options carry exactly zero probability, legal
options sum to one, and the sampled index maps back to the correct canonical option.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import sys
import time

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")


def _play(args):
    """One self-play game driven by the untrained recurrent policy on CPU."""
    seed, n_games, check_mask = args
    torch.set_num_threads(1)          # actors are many and small; threads would oversubscribe
    from kaggle_environments import make
    from cg import api as A, teachers as T, c009_eval as ce
    from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M

    model = M.new_model(seed=1901)
    model.eval()
    gen = torch.Generator().manual_seed(seed)
    opp_ids = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]

    out = {"games": 0, "completed": 0, "decisions": 0, "seconds": 0.0,
           "mask_checked": 0, "mask_violations": 0, "index_map_violations": 0,
           "truncated_option_sets": 0, "encode_failures": 0, "per_game_s": []}
    t_all = time.time()
    for g in range(n_games):
        base = T.make_fresh("mega_lucario", ce.SOURCES)
        opp = T.make_fresh(opp_ids[g % len(opp_ids)], ce.SOURCES)
        state = [None]
        t0 = time.time()

        def me(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            try:
                o = A.to_observation_class(obs)
                f = E.encode(o)
            except Exception:  # noqa: BLE001
                out["encode_failures"] += 1
                return base(obs)
            out["truncated_option_sets"] += int(f["options_truncated"] > 0)
            idx, prob, logits, val, state[0] = model.act(f, state[0], generator=gen)
            out["decisions"] += 1

            if check_mask and out["mask_checked"] < 400:
                b = M.to_torch(f)
                p = M.masked_probs(logits[None, :], b["opt_mask"])[0].detach().numpy()
                k = min(int(f["n_options"]), E.N_OPT)
                out["mask_checked"] += 1
                legal_sum = float(p[:k].sum()) if k else 0.0
                illegal_sum = float(p[k:].sum()) if k < E.N_OPT else 0.0
                if k and (abs(legal_sum - 1.0) > 1e-4 or illegal_sum != 0.0):
                    out["mask_violations"] += 1
                # the sampled index must address the canonical option at that position
                opts = K.canonical_options(sel)
                if idx >= len(opts) or opts[idx].option_index != idx:
                    out["index_map_violations"] += 1

            sel_opts = K.canonical_options(sel)
            if idx < len(sel_opts):
                try:
                    return K.to_select_payload([sel_opts[idx]], sel)
                except Exception:  # noqa: BLE001
                    pass
            return base(obs)

        seat = g % 2
        agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            out["completed"] += int([s.status for s in last] == ["DONE", "DONE"])
        except Exception:  # noqa: BLE001
            pass
        out["games"] += 1
        out["per_game_s"].append(round(time.time() - t0, 3))
    out["seconds"] = round(time.time() - t_all, 2)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-per-actor", type=int, default=6)
    ap.add_argument("--actor-counts", default="1,4,8,10")
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(C19, "byterl", "configs"), exist_ok=True)

    results = {}
    for n_actors in [int(x) for x in a.actor_counts.split(",")]:
        jobs = [(2000 + i, a.games_per_actor, i == 0) for i in range(n_actors)]
        t0 = time.time()
        if n_actors == 1:
            res = [_play(jobs[0])]
        else:
            with mp.get_context("spawn").Pool(n_actors) as pool:
                res = pool.map(_play, jobs)
        wall = time.time() - t0
        games = sum(r["games"] for r in res)
        dec = sum(r["decisions"] for r in res)
        per = [x for r in res for x in r["per_game_s"]]
        results[n_actors] = {
            "actors": n_actors, "games": games, "completed": sum(r["completed"] for r in res),
            "decisions": dec, "wall_clock_s": round(wall, 2),
            "games_per_hour": round(games / wall * 3600, 1),
            "decisions_per_game": round(dec / max(1, games), 1),
            "median_game_s": round(statistics.median(per), 3) if per else None,
            "encode_failures": sum(r["encode_failures"] for r in res),
            "mask_checked": sum(r["mask_checked"] for r in res),
            "mask_violations": sum(r["mask_violations"] for r in res),
            "index_map_violations": sum(r["index_map_violations"] for r in res),
            "truncated_option_sets": sum(r["truncated_option_sets"] for r in res),
        }
        r = results[n_actors]
        print(f"  actors={n_actors:2d} games/h={r['games_per_hour']:>9,.0f} "
              f"median_game={r['median_game_s']}s dec/game={r['decisions_per_game']} "
              f"mask_viol={r['mask_violations']} idx_viol={r['index_map_violations']}",
              flush=True)

    best = max(results.values(), key=lambda r: r["games_per_hour"])
    gph = best["games_per_hour"]
    doc = {
        "probe": "c019_actor_calibration",
        "purpose": ("measure recurrent-actor throughput before the learner is written, because "
                    "the ByteRL floors are wall-clock bound and c018's feedforward rate does "
                    "not transfer"),
        "scaling": results,
        "best": best,
        "floor_projection": {
            "floor_games": 60000,
            "hours_for_floor_at_best": round(60000 / max(1.0, gph), 2),
            "target_games_low": 120000,
            "hours_for_target_low": round(120000 / max(1.0, gph), 2),
        },
        "b01_mask": {
            "checked": sum(r["mask_checked"] for r in results.values()),
            "violations": sum(r["mask_violations"] for r in results.values()),
            "index_map_violations": sum(r["index_map_violations"] for r in results.values()),
            "verdict": ("PASS" if not sum(r["mask_violations"] + r["index_map_violations"]
                                          for r in results.values()) else "FAIL"),
        },
    }
    json.dump(doc, open(os.path.join(C19, "byterl", "configs",
                                     "actor_calibration.json"), "w"), indent=2, default=str)
    print(json.dumps({"best_actors": best["actors"], "games_per_hour": gph,
                      "hours_for_60k_floor": doc["floor_projection"]
                      ["hours_for_floor_at_best"],
                      "b01": doc["b01_mask"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

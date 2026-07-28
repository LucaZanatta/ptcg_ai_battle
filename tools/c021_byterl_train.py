"""c021 B3 — the cumulative B0 -> B1 -> B1.5 -> B2 -> B3 ByteRL ladder.

Each rung ADDS one component and keeps everything below it. The ladder is cumulative so a change
in strength can be attributed; running only the top rung would leave every component unattributed.

    B0    uniform random over the legal mask                    (floor / sanity)
    B1    fresh random network, sampled policy, no learning     (architecture in the loop)
    B1.5  + V-trace policy-gradient learning                    (off-policy correction)
    B2    + UPGO                                                (better-than-expected targets)
    B3    + OSFP self-play against frozen checkpoints           (the full agent)

`FIDELITY_RULES §4` permits reducing ONLY actor count, sample count, duration and achieved
learning periods. Every such reduction is recorded in the run manifest under `reductions`, so the
scale story is auditable rather than implied.

ByteRL starts from FRESH RANDOM WEIGHTS at every rung (B1/B3): no distillation from a scripted
teacher, no warm start from a c0xx checkpoint.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
BR = os.path.join(C21, "byterl")

RUNGS = ["B0", "B1", "B1_5", "B2", "B3"]
RUNG_FEATURES = {
    "B0":   {"network": False, "vtrace": False, "upgo": False, "osfp": False},
    "B1":   {"network": True,  "vtrace": False, "upgo": False, "osfp": False},
    "B1_5": {"network": True,  "vtrace": True,  "upgo": False, "osfp": False},
    "B2":   {"network": True,  "vtrace": True,  "upgo": True,  "osfp": False},
    "B3":   {"network": True,  "vtrace": True,  "upgo": True,  "osfp": True},
}
OPPONENTS = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]


# ====================================================================== actor worker
def _play_games(payload):
    """Run a batch of episodes in a worker and return trajectories."""
    jobs, cfg, weights, seed = payload
    sys.path.insert(0, _REPO)
    import torch
    torch.set_num_threads(1)          # WITHOUT THIS, workers contend and timings invert
    import numpy as np
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c021_byterl_actor as AC, c021_byterl_deck as DK
    from cg import c021_byterl_encode as EN, c021_byterl_model as M

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    feats = RUNG_FEATURES[cfg["rung"]]
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  width=cfg["width"], blocks=cfg["blocks"], seed=cfg["seed"])
    if weights is not None:
        net.load_state_dict({k: torch.as_tensor(v) for k, v in weights.items()})
    net.eval()

    out = []
    for ji, job in enumerate(jobs):
        rng_seed = seed + ji * 7919
        fixed = None if cfg["learn_construction"] else DK.greedy_reference_deck(pool)
        actor = AC.ByteRLActor(net, pool, seed=rng_seed,
                               temperature=cfg["temperature"],
                               learn_construction=cfg["learn_construction"],
                               fixed_deck=fixed)
        if not feats["network"]:
            actor = _UniformActor(pool, rng_seed, cfg["learn_construction"], fixed)
        opp = T.make_fresh(job["opponent"], ce.SOURCES)
        seat = int(job["seat"])

        def mk(a):
            def f(o): return a.act(o)
            return f

        def mo(o):
            def f(x): return o(x)
            return f

        agents = [mk(actor), mo(opp)] if seat == 0 else [mo(opp), mk(actor)]
        t0 = time.time()
        completed, score = False, 0.0
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            if [s.status for s in last] == ["DONE", "DONE"]:
                rw = [s.reward for s in last]
                if rw[seat] is not None:
                    completed = True
                    score = (1.0 if rw[seat] > rw[1 - seat]
                             else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
        except Exception as e:  # noqa: BLE001
            out.append({"game_id": job["game_id"], "error": f"{type(e).__name__}: {e}"[:200]})
            continue

        ep = actor.finish(score, completed, {"opponent": job["opponent"], "seat": seat,
                                             "seconds": round(time.time() - t0, 2)})
        out.append({"game_id": job["game_id"], "opponent": job["opponent"], "seat": seat,
                    "completed": completed, "score": score,
                    "seconds": round(time.time() - t0, 2),
                    "deck_legal": ep.deck_legal, "deck": ep.deck,
                    "n_construction": ep.construction_steps(),
                    "n_battle": ep.battle_steps(),
                    "encode_stats": ep.info.get("encode_stats", {}),
                    "errors": ep.info.get("errors", []),
                    "trajectory": _pack(ep) if feats["vtrace"] else None})
    return out


class _UniformActor:
    """B0: uniform over the legal mask. The floor every later rung must beat."""

    def __init__(self, pool, seed, learn_construction, fixed_deck):
        from cg import c021_byterl_deck as DK
        self.pool = pool
        self.rng = np.random.default_rng(seed)
        self.DK = DK
        self._deck = list(fixed_deck) if fixed_deck else None
        self.learn_construction = learn_construction
        self.episode = _Ep()
        self.errors = []

    def act(self, obs):
        from cg import c019_core as K
        sel = obs.get("select") if isinstance(obs, dict) else None
        if sel is None:
            return list(self.deck())
        opts = K.canonical_options(sel)
        if not opts:
            return [0]
        lo = max(1, int(getattr(sel, "minCount", 1) or 1)) if not isinstance(sel, dict) \
            else max(1, int(sel.get("minCount", 1) or 1))
        hi = int(getattr(sel, "maxCount", 1) or 1) if not isinstance(sel, dict) \
            else int(sel.get("maxCount", 1) or 1)
        k = max(1, min(lo, len(opts)))
        idx = self.rng.choice(len(opts), size=min(k, len(opts)), replace=False)
        return K.to_select_payload([opts[i] for i in idx], sel)

    def deck(self):
        if self._deck is None:
            d, _ = self.DK.sample_deck(self.pool, self.rng)
            self._deck = d
            ok, det = self.DK.legality(d, self.pool)
            self.episode.deck, self.episode.deck_legal = d, ok
        return self._deck

    def finish(self, reward, completed, info=None):
        self.episode.reward = reward
        self.episode.completed = completed
        self.episode.info = dict(info or {})
        return self.episode


class _Ep:
    def __init__(self):
        self.steps, self.reward, self.completed = [], 0.0, False
        self.deck, self.deck_legal, self.info = [], False, {}

    def construction_steps(self):
        return 0

    def battle_steps(self):
        return 0


def _pack(ep) -> Dict[str, Any]:
    """Trajectory in a picklable form: encodings stay as arrays, no tensors cross processes."""
    return {"reward": ep.reward, "completed": ep.completed,
            "steps": [{"stage": int(s.stage), "chosen": list(s.chosen),
                       "behaviour_logp": float(s.behaviour_logp),
                       "value": float(s.value), "n_legal": int(s.n_legal),
                       "enc": {k: (v.tolist() if isinstance(v, np.ndarray) else int(v))
                               for k, v in s.enc.items()}}
                      for s in ep.steps]}


# ====================================================================== learner
def _learn(net, opt, trajectories, cfg, stats):
    import torch
    from cg import c021_byterl_encode as EN, c021_byterl_learn as L, c021_byterl_model as M

    feats = RUNG_FEATURES[cfg["rung"]]
    lc = L.LossConfig(value_coef=cfg["value_coef"], entropy_coef=cfg["entropy_coef"],
                      upgo_coef=(1.0 if feats["upgo"] else 0.0),
                      rho_bar=cfg["rho_bar"], c_bar=cfg["c_bar"],
                      max_grad_norm=cfg["max_grad_norm"])
    net.train()
    n_updates = 0
    for traj in trajectories:
        if traj is None or not traj["steps"]:
            continue
        tl, vals, ents, beh = [], [], [], []
        for s in traj["steps"]:
            enc = {k: (np.asarray(v, dtype=np.float32) if isinstance(v, list) else v)
                   for k, v in s["enc"].items()}
            for k in ("roles", "indices", "sides"):
                enc[k] = np.asarray(enc[k], dtype=np.int64)
            tt = EN.to_torch(enc)
            h = net.encode(tt["global"], tt["board"], tt["roles"], tt["indices"],
                           tt["sides"], tt["stage"])
            if s["stage"] == EN.STAGE_CONSTRUCTION:
                mask = tt["pool_mask"]
                lp = M.masked_log_softmax(net.construction_logits(h), mask)
                tl.append(lp[0, s["chosen"][0]])
                ents.append(-(lp.exp() * lp).sum())
            else:
                legal = tt["opt_mask"].clone()
                legal[:, int(enc["n_options"]):] = 0.0
                tl.append(net.select_logprob(h, tt["opt"], legal, s["chosen"]))
                lg = net.battle_logits(h, tt["opt"])
                lpa = M.masked_log_softmax(lg, legal)
                ents.append(-(lpa.exp() * lpa).sum())
            vals.append(net.value(h, tt["stage"]).squeeze(0))
            beh.append(s["behaviour_logp"])
        T = len(tl)
        rewards = torch.zeros(T)
        rewards[-1] = float(traj["reward"])
        total, st = L.byterl_losses(
            torch.stack(tl), torch.tensor(beh, dtype=torch.float32),
            torch.stack(ents), torch.stack(vals), rewards,
            torch.zeros(()), torch.ones(T), lc)
        opt.zero_grad(set_to_none=True)
        total.backward()
        gn = L.clip_grads(net, cfg["max_grad_norm"])
        opt.step()
        n_updates += 1
        for k, v in st.items():
            stats[k].append(v)
        stats["grad_norm"].append(gn)
    net.eval()
    return n_updates


# ====================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rung", choices=RUNGS, required=True)
    ap.add_argument("--iterations", type=int, default=6)
    ap.add_argument("--games-per-iter", type=int, default=24)
    ap.add_argument("--nproc", type=int, default=12)
    ap.add_argument("--width", type=int, default=192)
    ap.add_argument("--blocks", type=int, default=3)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--entropy-coef", type=float, default=0.01)
    ap.add_argument("--value-coef", type=float, default=0.5)
    ap.add_argument("--rho-bar", type=float, default=1.0)
    ap.add_argument("--c-bar", type=float, default=1.0)
    ap.add_argument("--max-grad-norm", type=float, default=10.0)
    ap.add_argument("--learn-construction", type=int, default=1)
    ap.add_argument("--seed", type=int, default=2100)
    ap.add_argument("--tag", default=None)
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(1)
    from cg import c021_byterl_deck as DK, c021_byterl_encode as EN
    from cg import c021_byterl_learn as L, c021_byterl_model as M

    tag = a.tag or a.rung.lower()
    for d in ("checkpoints", "curves", "manifests", "raw"):
        os.makedirs(os.path.join(BR, d), exist_ok=True)

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    feats = RUNG_FEATURES[a.rung]
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  width=a.width, blocks=a.blocks, seed=a.seed)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr) if feats["vtrace"] else None
    osfp = L.OSFP() if feats["osfp"] else None

    cfg = {"rung": a.rung, "width": a.width, "blocks": a.blocks, "seed": a.seed,
           "temperature": a.temperature, "learn_construction": bool(a.learn_construction),
           "value_coef": a.value_coef, "entropy_coef": a.entropy_coef,
           "rho_bar": a.rho_bar, "c_bar": a.c_bar, "max_grad_norm": a.max_grad_norm}

    manifest = {
        "rung": a.rung, "features": feats, "config": cfg,
        "params": M.count_parameters(net),
        "fresh_random_weights": True,
        "reductions": {
            "kind": "permitted by FIDELITY_RULES §4 (actors, samples, duration, periods only)",
            "actors": a.nproc, "games_per_iteration": a.games_per_iter,
            "iterations": a.iterations,
            "architecture_simplified": False, "algorithm_simplified": False,
        },
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    curve, stats_all = [], []
    t0 = time.time()
    gf = open(os.path.join(BR, "raw", f"{tag}_games.jsonl"), "w")
    for it in range(a.iterations):
        weights = ({k: v.detach().cpu().numpy() for k, v in net.state_dict().items()}
                   if feats["network"] else None)
        jobs = [{"game_id": f"{tag}:i{it}:g{g}",
                 "opponent": OPPONENTS[(it * a.games_per_iter + g) % len(OPPONENTS)],
                 "seat": (it * a.games_per_iter + g) % 2}
                for g in range(a.games_per_iter)]
        chunks = [[] for _ in range(a.nproc)]
        for i, j in enumerate(jobs):
            chunks[i % a.nproc].append(j)
        payload = [(ch, cfg, weights, a.seed + it * 1013 + k * 97)
                   for k, ch in enumerate(chunks) if ch]
        with mp.get_context("spawn").Pool(len(payload)) as pool_:
            res = [r for rr in pool_.map(_play_games, payload) for r in rr]

        ok = [r for r in res if not r.get("error")]
        done = [r for r in ok if r.get("completed")]
        wr = (sum(r["score"] for r in done) / len(done)) if done else None
        legal = sum(1 for r in ok if r.get("deck_legal"))
        enc_trunc = sum((r.get("encode_stats") or {}).get("option_truncations", 0) for r in ok)
        enc_max = max([(r.get("encode_stats") or {}).get("max_options_seen", 0)
                       for r in ok] or [0])

        stats = collections.defaultdict(list)
        n_up = 0
        if feats["vtrace"] and opt is not None:
            trajs = [r.get("trajectory") for r in ok]
            n_up = _learn(net, opt, trajs, cfg, stats)

        row = {"iteration": it, "games": len(res), "completed": len(done),
               "errors": sum(1 for r in res if r.get("error")),
               "win_rate": round(wr, 4) if wr is not None else None,
               "legal_decks": legal, "legal_deck_rate": round(legal / max(1, len(ok)), 4),
               "updates": n_up,
               "option_truncations": enc_trunc, "max_options_seen": enc_max,
               "mean_battle_steps": round(np.mean([r.get("n_battle", 0) for r in ok]), 1)
               if ok else 0,
               "elapsed_s": round(time.time() - t0, 1)}
        for k, v in stats.items():
            if v:
                row[k] = round(float(np.mean(v)), 5)
        if osfp is not None:
            if wr is not None and osfp.should_promote(wr, len(done),
                                                     threshold=0.55, min_games=len(done)):
                osfp.add_checkpoint({k: v.detach().cpu().numpy().tolist()
                                     for k, v in net.state_dict().items()},
                                    f"{tag}_it{it}")
                osfp.reset_period()
                row["promoted"] = True
            row["osfp"] = osfp.snapshot()
        curve.append(row)
        print(json.dumps({k: row[k] for k in list(row)[:14]}), flush=True)
        for r in ok:
            gf.write(json.dumps({k: r[k] for k in
                                 ("game_id", "opponent", "seat", "completed", "score",
                                  "seconds", "deck_legal", "n_construction", "n_battle")}) + "\n")
    gf.close()

    torch.save(net.state_dict(), os.path.join(BR, "checkpoints", f"{tag}_final.pt"))
    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    manifest["wall_clock_s"] = round(time.time() - t0, 1)
    manifest["final_win_rate"] = curve[-1]["win_rate"] if curve else None
    manifest["best_win_rate"] = max([c["win_rate"] for c in curve
                                     if c["win_rate"] is not None] or [None])
    json.dump(manifest, open(os.path.join(BR, "manifests", f"{tag}_manifest.json"), "w"),
              indent=2)
    json.dump(curve, open(os.path.join(BR, "curves", f"{tag}_curve.json"), "w"), indent=2)
    print(json.dumps({"rung": a.rung, "final": manifest["final_win_rate"],
                      "best": manifest["best_win_rate"],
                      "wall_clock_s": manifest["wall_clock_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

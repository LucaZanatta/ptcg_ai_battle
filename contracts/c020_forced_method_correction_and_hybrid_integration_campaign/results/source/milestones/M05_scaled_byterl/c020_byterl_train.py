"""c020 B4/B5/B6/B7/B8 — corrected ByteRL training.

Fresh random weights and a fresh optimizer (B8): c019's checkpoint cannot initialize this model
because the observation, action and recurrent semantics all changed, and `CONTRACT §2` forbids it
regardless.

The learner replays each unroll FROM THE STORED h0/c0 and asserts it reproduced the actor's
context fingerprints before computing any ratio. A mismatch raises and the batch is dropped to
`failures/recurrent_mismatches/` rather than being trained on — c019's silent reset (audit #10/#11)
is precisely the failure this refuses to repeat.

Each learning period ends with the sequence `MANDATORY_CHANGES B6` requires: freeze the exact
checkpoint, evaluate THAT checkpoint against the historical population with fixed seeds, populate
a PERIOD-LOCAL payoff row from those games only, and promote from that evidence.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
BY = os.path.join(C20, "byterl")

HP = {
    "lstm_hidden": 256, "gamma": 1.0, "learning_rate": 7e-5, "entropy_coef": 0.01,
    "value_coef": 0.5, "upgo_coef": 1.0, "sample_reuse": 2, "unroll_length": 16,
    "minibatch_unrolls": 8, "queue_capacity": 8192, "grad_clip": 10.0,
    "ppo_eps": 0.2, "rho_clip": [0.001, 1.007],
    "p_current_self_play": 0.6, "xi_promotion": 0.55, "max_lp_without_add": 6,
    "source": "arXiv 2303.05197 Table III/IV; unchanged from c019 registration",
}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ------------------------------------------------------------------ actor process

def _actor(payload):
    """One worker: play a list of jobs and return trajectories. Jobs carry their own game_id."""
    snap, version, jobs, deck, seed = payload
    torch.set_num_threads(1)
    sys.path.insert(0, _REPO)
    from kaggle_environments import make
    from cg import c020_byterl_model as M, c020_byterl_actor as AC

    model = M.PTCGByteRL()
    model.load_state_dict(torch.load(snap, map_location="cpu")["state_dict"])
    model.eval()

    opp_models: Dict[str, Any] = {}
    out = []
    for ji, job in enumerate(jobs):
        gid = job["game_id"]
        t0 = time.time()
        me = AC.ByteRLActor(model, deck, version=version, seed=seed + ji)
        # OPPONENT: current self-play uses the same weights but its OWN actor (independent
        # recurrent state); historical uses a frozen checkpoint loaded once per worker.
        if job["kind"] == "HISTORICAL_PAYOFF_SAMPLE":
            p = job["path"]
            if p not in opp_models:
                om = M.PTCGByteRL()
                om.load_state_dict(torch.load(p, map_location="cpu")["state_dict"])
                om.eval()
                opp_models[p] = om
            opp_actor = AC.ByteRLActor(opp_models[p], deck, version=-1, seed=seed + 5000 + ji)
        else:
            opp_actor = AC.ByteRLActor(model, deck, version=version, seed=seed + 9000 + ji)

        seat = int(job["seat"])

        # FACTORY closures: kaggle_environments passes (observation, configuration) to any
        # two-parameter callable, so default-arg capture silently breaks the agent.
        def make_play(actor):
            def play(obs):
                return actor.act(obs)
            return play

        agents = ([make_play(me), make_play(opp_actor)] if seat == 0
                  else [make_play(opp_actor), make_play(me)])
        completed, result = False, 0.0
        try:
            env = make("cabt")
            env.run(agents)
            last = env.steps[-1]
            if [s.status for s in last] == ["DONE", "DONE"]:
                rw = [s.reward for s in last]
                if rw[seat] is not None and rw[1 - seat] is not None:
                    completed = True
                    result = (1.0 if rw[seat] > rw[1 - seat]
                              else (0.0 if rw[seat] == rw[1 - seat] else -1.0))
        except Exception:  # noqa: BLE001
            completed = False
        me.finish(result)
        urs = me.unrolls(length=HP["unroll_length"]) if completed else []
        for u in urs:
            u.game_id, u.seat, u.opponent_kind = gid, seat, job["kind"]
        ms = [r.to_json() for r in me.multiselect if r.k > 1][:40]
        out.append({
            "game_id": gid, "job": job, "seat": seat, "completed": completed,
            "result_pm_one": result, "decisions": me.decision,
            "unrolls": urs, "seconds": round(time.time() - t0, 3),
            "multiselect_records": ms,
            "multiselect_count": sum(1 for r in me.multiselect if r.k > 1),
            "any_multiselect_context": sum(1 for r in me.multiselect if r.max_count > 1),
        })
    return out


# ------------------------------------------------------------------ learner

def learn(model, opt, unrolls, device, fail_dir) -> Optional[Dict[str, Any]]:
    """One optimizer step over a minibatch of unrolls, replayed from the STORED state."""
    from cg import c020_byterl_model as M, c020_vtrace as VT, c020_byterl_actor as AC

    tot_pg = tot_up = tot_v = tot_e = 0.0
    n = 0
    metrics = collections.defaultdict(float)
    opt.zero_grad(set_to_none=True)

    for u in unrolls:
        if not u.steps:
            continue
        h = torch.as_tensor(u.h0, device=device).unsqueeze(0)
        c = torch.as_tensor(u.c0, device=device).unsqueeze(0)
        state = (h, c)
        tgt_logp, vals, ents, ctx_seen = [], [], [], []
        for s in u.steps:
            b = M.to_torch(s.obs_features, device=device)
            lp, v, state, ent = model.joint_logp_of(b, s.selected, state)
            tgt_logp.append(lp[0])
            vals.append(v[0])
            ents.append(ent[0])
            ctx_seen.append(s.context_fingerprint)
        # B5/audit #11: refuse to train when the replay context differs from the actor's
        try:
            VT.assert_same_context([s.context_fingerprint for s in u.steps], ctx_seen)
        except VT.RecurrentContextMismatch as e:
            os.makedirs(fail_dir, exist_ok=True)
            with open(os.path.join(fail_dir, "mismatches.jsonl"), "a") as f:
                f.write(json.dumps({"game_id": u.game_id, "error": str(e)}) + "\n")
            continue

        t = torch.stack(tgt_logp)
        b_lp = torch.as_tensor([s.joint_logp for s in u.steps], device=device,
                               dtype=t.dtype)
        vv = torch.stack(vals)
        ee = torch.stack(ents)
        rew = torch.as_tensor([s.reward for s in u.steps], device=device, dtype=t.dtype)
        disc = torch.as_tensor([0.0 if s.done else HP["gamma"] for s in u.steps],
                               device=device, dtype=t.dtype)
        boot = torch.as_tensor(u.bootstrap_value, device=device, dtype=t.dtype)
        L = VT.losses(t, b_lp, vv, boot, rew, disc, ee,
                      vf_coef=HP["value_coef"], ent_coef=HP["entropy_coef"],
                      upgo_coef=HP["upgo_coef"])
        (L["total"] / max(1, len(unrolls))).backward()
        tot_pg += float(L["policy_vtrace"].item())
        tot_up += float(L["upgo"].item())
        tot_v += float(L["value"].item())
        tot_e += float(L["entropy"].item())
        for k in ("vs_mean", "vs_absmax", "rho_mean", "rho_clipped_frac"):
            if k in L:
                metrics[k] += float(L[k].item() if hasattr(L[k], "item") else L[k])
        n += 1

    if n == 0:
        return None
    gn = torch.nn.utils.clip_grad_norm_(model.parameters(), HP["grad_clip"])
    if not torch.isfinite(gn):
        opt.zero_grad(set_to_none=True)
        return {"skipped": True, "reason": "nonfinite_grad"}
    opt.step()
    return {"skipped": False, "policy_vtrace": tot_pg / n, "upgo": tot_up / n,
            "value": tot_v / n, "entropy": tot_e / n, "grad_norm": float(gn),
            **{k: v / n for k, v in metrics.items()}, "unrolls": n}


# ------------------------------------------------------------------ frozen evaluation

def evaluate_frozen(snap_path: str, population, deck, lp: int, games: int, actors: int,
                    seed: int, tag: str) -> Tuple[Any, List[Dict[str, Any]]]:
    """B6: play `games` against EACH historical model using ONE frozen checkpoint."""
    from cg import c020_osfp as O
    payoff = O.PeriodLocalPayoff(lp=lp, size=len(population.models))
    sha = _sha(snap_path)
    if not population.models:
        return payoff, []
    per = max(O.MIN_GAMES_PER_HISTORICAL, games // max(1, len(population.models)))
    jobs = []
    for i, m in enumerate(population.models):
        for g in range(per):
            jobs.append({"kind": "HISTORICAL_PAYOFF_SAMPLE", "index": i, "path": m.path,
                         "seat": g % 2,
                         "game_id": f"{tag}:eval:lp{lp}:h{i}:g{g}"})
    chunks = [[] for _ in range(actors)]
    for i, j in enumerate(jobs):
        chunks[i % actors].append(j)
    payload = [(snap_path, -1, ch, deck, seed + k) for k, ch in enumerate(chunks) if ch]
    rows = []
    with mp.get_context("spawn").Pool(len(payload)) as pool:
        for res in pool.map(_actor, payload):
            for r in res:
                if r["completed"]:
                    payoff.record(int(r["job"]["index"]), r["result_pm_one"],
                                  r["game_id"], sha)
                rows.append({"game_id": r["game_id"], "index": r["job"]["index"],
                             "seat": r["seat"], "completed": r["completed"],
                             "result_pm_one": r["result_pm_one"],
                             "frozen_checkpoint_sha256": sha})
    return payoff, rows


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--learning-periods", type=int, default=8)
    ap.add_argument("--games-per-lp", type=int, default=14000)
    ap.add_argument("--games-per-round", type=int, default=480)
    ap.add_argument("--actors", type=int, default=10)
    ap.add_argument("--eval-games", type=int, default=120)
    ap.add_argument("--tag", default="c020")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args(argv)

    from cg import c020_byterl_model as M, c020_osfp as O, c019_determinize as D19

    for d in ("configs", "schema", "model_architecture", "actor_unrolls", "recurrent_states",
              "multiselect_records", "learner_logs", "checkpoints", "raw_games", "evaluations",
              "osfp/period_local_GC", "osfp/payoff_tables", "osfp/frozen_evaluations",
              "osfp/opponent_mixtures", "osfp/historical_checkpoints"):
        os.makedirs(os.path.join(BY, d), exist_ok=True)
    ck_dir = os.path.join(BY, "checkpoints", a.tag)
    hist_dir = os.path.join(BY, "osfp", "historical_checkpoints", a.tag)
    os.makedirs(ck_dir, exist_ok=True)
    fail_dir = os.path.join(C20, "failures", "recurrent_mismatches")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(a.seed)
    model = M.PTCGByteRL(lstm_hidden=HP["lstm_hidden"]).to(device)   # B8: FRESH RANDOM
    init_sha = hashlib.sha256(
        b"".join(p.detach().cpu().numpy().tobytes() for p in model.parameters())).hexdigest()
    opt = torch.optim.Adam(model.parameters(), lr=HP["learning_rate"])
    deck = D19.archetype_decks()["mega_lucario"]
    rng = np.random.default_rng(a.seed)
    population = O.HistoricalPopulation(hist_dir, rng, HP["p_current_self_play"])

    json.dump({**HP, "device": device, "initialized_from": "FRESH_RANDOM",
               "init_param_sha256": init_sha, "tag": a.tag, "seed": a.seed,
               "learning_periods": a.learning_periods, "games_per_lp": a.games_per_lp},
              open(os.path.join(BY, "configs", f"{a.tag}_config.json"), "w"), indent=2)
    json.dump(M.architecture_report(model),
              open(os.path.join(BY, "model_architecture", f"{a.tag}_architecture.json"), "w"),
              indent=2)
    from cg import c020_byterl_encode as E
    json.dump(E.schema(), open(os.path.join(BY, "schema", f"{a.tag}_encoder_schema.json"), "w"),
              indent=2)

    games_log = gzip.open(os.path.join(BY, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    loss_log = gzip.open(os.path.join(BY, "learner_logs", f"{a.tag}_losses.jsonl.gz"), "wt")
    unroll_log = gzip.open(os.path.join(BY, "actor_unrolls", f"{a.tag}_unrolls.jsonl.gz"), "wt")
    ms_log = gzip.open(os.path.join(BY, "multiselect_records", f"{a.tag}_multiselect.jsonl.gz"),
                       "wt")
    lp_log = open(os.path.join(BY, "osfp", f"{a.tag}_learning_periods.jsonl"), "w")
    promo_log = open(os.path.join(BY, "osfp", "promotion_history.jsonl"), "a")
    mix_log = open(os.path.join(BY, "osfp", "opponent_mixtures", f"{a.tag}_mixtures.jsonl"), "w")

    version = 0
    total_games = 0
    total_steps = 0
    lps_without_add = 0
    t_start = time.time()
    counters = collections.Counter()

    for lp in range(a.learning_periods):
        # B6: period-local accumulators, allocated FRESH
        lp_stats = collections.Counter()
        played = 0
        while played < a.games_per_lp:
            n = min(a.games_per_round, a.games_per_lp - played)
            snap = os.path.join(ck_dir, f"{a.tag}_v{version:06d}.pt")
            torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                        "version": version, "cfg": model.cfg, "lp": lp}, snap)

            jobs = []
            for gi in range(n):
                rec = population.sample_opponent(lp)
                job = dict(rec)
                job.update({"seat": gi % 2,
                            "game_id": f"{a.tag}:lp{lp}:v{version}:g{total_games + gi}"})
                jobs.append(job)
            chunks = [[] for _ in range(a.actors)]
            for i, j in enumerate(jobs):
                chunks[i % a.actors].append(j)
            payload = [(snap, version, ch, deck, int(rng.integers(0, 1 << 30)))
                       for ch in chunks if ch]
            with mp.get_context("spawn").Pool(len(payload)) as pool:
                results = [r for res in pool.map(_actor, payload) for r in res]

            # pair by game_id, never by list position
            by_id = {r["game_id"]: r for r in results}
            all_unrolls = []
            for job in jobs:
                r = by_id.get(job["game_id"])
                if r is None:
                    continue
                games_log.write(json.dumps({
                    "game_id": r["game_id"], "lp": lp, "behavior_version": version,
                    "seat": r["seat"], "opponent_kind": job["kind"],
                    "opponent_index": job.get("index"),
                    "decisions": r["decisions"], "completed": r["completed"],
                    "result_pm_one": r["result_pm_one"], "seconds": r["seconds"],
                    "multiselect_count": r["multiselect_count"],
                    "multiselect_contexts": r["any_multiselect_context"]}) + "\n")
                counters["games"] += 1
                counters["completed"] += int(r["completed"])
                counters["multiselect_decisions"] += r["multiselect_count"]
                counters["multiselect_contexts"] += r["any_multiselect_context"]
                lp_stats[job["kind"]] += 1
                for rec in r["multiselect_records"][:4]:
                    if counters["ms_logged"] < 20000:
                        ms_log.write(json.dumps({"game_id": r["game_id"], **rec}) + "\n")
                        counters["ms_logged"] += 1
                for u in r["unrolls"]:
                    all_unrolls.append(u)
                    if counters["unrolls_logged"] < 20000:
                        unroll_log.write(json.dumps(u.to_json()) + "\n")
                        counters["unrolls_logged"] += 1
                        counters["midgame_unrolls"] += 0 if u.episode_start else 1
                        if not u.episode_start and not u.to_json()["h0_is_zero"]:
                            counters["midgame_with_state"] += 1

            played += n
            total_games += n

            # learner: sample_reuse passes over the collected unrolls
            if all_unrolls:
                nb = max(1, int(len(all_unrolls) * HP["sample_reuse"]
                                / max(1, HP["minibatch_unrolls"])))
                for _ in range(nb):
                    idx = rng.integers(0, len(all_unrolls),
                                       size=min(HP["minibatch_unrolls"], len(all_unrolls)))
                    mb = [all_unrolls[int(i)] for i in idx]
                    out = learn(model, opt, mb, device, fail_dir)
                    if out is None:
                        continue
                    version += 1
                    total_steps += 1
                    out.update({"lp": lp, "version": version})
                    loss_log.write(json.dumps(out) + "\n")
            print(f"  [lp {lp}] games={played}/{a.games_per_lp} v={version} "
                  f"steps={total_steps} {int(time.time()-t_start)}s", flush=True)
            games_log.flush(); loss_log.flush(); unroll_log.flush(); ms_log.flush()

        # ---------------------------------------------------------- period end (B6)
        frozen = os.path.join(ck_dir, f"{a.tag}_frozen_lp{lp:03d}_v{version:06d}.pt")
        torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                    "version": version, "cfg": model.cfg, "lp": lp}, frozen)
        frozen_sha = _sha(frozen)

        payoff, eval_rows = evaluate_frozen(frozen, population, deck, lp, a.eval_games,
                                            a.actors, a.seed + lp * 977, a.tag)
        json.dump(payoff.to_json(),
                  open(os.path.join(BY, "osfp", "period_local_GC",
                                    f"{a.tag}_lp{lp:03d}_GC.json"), "w"), indent=2)
        with open(os.path.join(BY, "osfp", "frozen_evaluations",
                               f"{a.tag}_lp{lp:03d}_games.jsonl"), "w") as f:
            for r in eval_rows:
                f.write(json.dumps(r) + "\n")

        decision = decide = None
        from cg import c020_osfp as O2
        decision = O2.decide_promotion(payoff, lps_without_add, HP["xi_promotion"],
                                       O2.MIN_GAMES_PER_HISTORICAL, HP["max_lp_without_add"])
        added = None
        if decision.get("add"):
            added = population.add(frozen, version, lp, decision["reason"],
                                   payoff.to_json(), payoff.evaluation_ids[:64])
            lps_without_add = 0
            decision["added"] = added.to_json()
        else:
            lps_without_add += 1
        mixture = population.set_mixture_from_payoff(payoff)

        promo_log.write(json.dumps({"tag": a.tag, "lp": lp, "version": version,
                                    "frozen_checkpoint_sha256": frozen_sha,
                                    **{k: v for k, v in decision.items()
                                       if k != "added"},
                                    "added": decision.get("added")}) + "\n")
        promo_log.flush()
        mix_log.write(json.dumps({"lp": lp, "mixture": [round(float(x), 6) for x in mixture],
                                  "population": len(population.models),
                                  "derived_from": "period_local_payoff_table"}) + "\n")
        mix_log.flush()
        lp_log.write(json.dumps({
            "lp": lp, "games": played, "optimizer_steps": total_steps, "version": version,
            "frozen_checkpoint": os.path.basename(frozen),
            "frozen_checkpoint_sha256": frozen_sha,
            "payoff": payoff.to_json(), "promotion": decision,
            "opponent_mix": dict(lp_stats),
            "population_after": len(population.models)}) + "\n")
        lp_log.flush()
        print(f"[LP {lp}] games={played} steps={total_steps} promo={decision['reason']} "
              f"|H|={len(population.models)} eval_games={sum(payoff.C)}", flush=True)

    final = os.path.join(ck_dir, f"{a.tag}_final_v{version:06d}.pt")
    torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                "version": version, "cfg": model.cfg, "lp": a.learning_periods - 1}, final)

    summary = {
        "tag": a.tag, "device": device, "initialized_from": "FRESH_RANDOM",
        "init_param_sha256": init_sha,
        "learning_periods": a.learning_periods, "actual_games": counters["games"],
        "completed_games": counters["completed"], "optimizer_steps": total_steps,
        "multiselect_decisions": counters["multiselect_decisions"],
        "multiselect_contexts_seen": counters["multiselect_contexts"],
        "midgame_unrolls_logged": counters["midgame_unrolls"],
        "midgame_unrolls_with_state": counters["midgame_with_state"],
        "historical_pool": len(population.models),
        "immutability": population.verify_all(),
        "population": population.to_json(),
        "final_checkpoint": os.path.basename(final),
        "final_checkpoint_sha256": _sha(final),
        "hyperparameters": HP,
        "seconds": round(time.time() - t_start, 1),
    }
    json.dump(summary, open(os.path.join(BY, "learner_logs",
                                         f"{a.tag}_training_summary.json"), "w"), indent=2)
    for f in (games_log, loss_log, unroll_log, ms_log, lp_log, promo_log, mix_log):
        f.close()
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("population", "hyperparameters")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

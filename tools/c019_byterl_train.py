"""c019 Branch B — ByteRL actor-learner with OSFP (§9.3, §9.4).

CPU actors generate real simulator games against opponents SAMPLED by OSFP; a bounded FIFO queue
feeds a CUDA learner that applies V-trace + UPGO + PPO-clipped losses with sample reuse 2.

Single-machine adaptation, recorded rather than hidden: the source trains on 24 V100s and 5,856
CPU cores with fully asynchronous actors. Here actors run in rounds against a snapshot of the
learner, which makes the system *near*-on-policy — staleness is measured per unroll and reported
rather than assumed to be zero.

Every training claim needs actual completed games, nonzero optimizer steps, finite losses,
gradient evidence and changed checkpoint hashes. All five are recorded per learning period.
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
from typing import Any, Dict, List, Optional

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
BY = os.path.join(C19, "byterl")
BY_DIR = BY

# Registered source hyperparameters (arXiv 2303.05197 Table III). Only batch/actor count are
# calibrated for this machine; every other value is the source value.
HP = {
    "gamma": 1.0, "learning_rate": 7e-5, "entropy_weight": 0.01,
    "policy_vtrace_weight": 1.0, "upgo_weight": 1.0, "value_weight": 1.0,
    "ppo_clip_epsilon": 0.2, "vtrace_c_lower": 0.001, "vtrace_c_upper": 1.007,
    "vtrace_rho_lower": 0.001, "vtrace_rho_upper": 1.007, "sample_reuse": 2,
    "lstm_hidden": 256, "max_grad_norm": 5.0,
    "unroll_length": 32, "minibatch_unrolls": 8, "queue_capacity": 8192,
    "source": "arXiv 2303.05197 Table III",
    "calibrated_for_this_machine": ["minibatch_unrolls", "actors", "games_per_round"],
}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _actor(args):
    """One CPU actor: play games against the OSFP-sampled opponents it was given."""
    (ckpt_path, version, jobs, deck, seed) = args
    torch.set_num_threads(1)
    from cg import teachers as T, c009_eval as ce
    from cg import c019_byterl_model as M, c019_byterl_actor as AC

    model = M.PTCGByteRL()
    model.load_state_dict(torch.load(ckpt_path, map_location="cpu")["state_dict"])
    model.eval()

    # kaggle_environments inspects the agent signature and passes (observation, configuration)
    # to any callable that accepts two arguments. Capturing state via DEFAULT ARGUMENTS
    # therefore binds `configuration` over the captured value -- which silently replaced the
    # model with a config Struct and errored every opponent seat. Agent callables must take
    # exactly one parameter.
    def make_model_agent(m, d):
        def agent(obs):
            return _self_play_action(m, obs, d)
        return agent

    def make_teacher_agent(t):
        def agent(obs):
            return t(obs)
        return agent

    hist_cache: Dict[str, Any] = {}
    out = []
    for j, job in enumerate(jobs):
        kind = job["kind"]
        if kind == "CURRENT_SELF_PLAY":
            opp_agent = make_model_agent(model, deck)
            opp_id = f"current_v{version}"
        elif kind == "HISTORICAL_PAYOFF_SAMPLE":
            p = job["path"]
            if p not in hist_cache:
                hm = M.PTCGByteRL()
                hm.load_state_dict(torch.load(p, map_location="cpu")["state_dict"])
                hm.eval()
                hist_cache[p] = hm
            opp_agent = make_model_agent(hist_cache[p], deck)
            opp_id = os.path.basename(p)
        else:
            opp_agent = make_teacher_agent(T.make_fresh(job["teacher"], ce.SOURCES))
            opp_id = job["teacher"]
        reset_opponent_state()
        tr = AC.play_game(model, opp_agent, deck, job["seat"], job["game_id"], version,
                          kind, opp_id, seed + j)
        out.append(tr)
    return out


_OPP_STATE: Dict[int, Any] = {}


def reset_opponent_state():
    """B02: the opponent's recurrent state resets at each game boundary, like the learner's."""
    _OPP_STATE.clear()


def _self_play_action(model, obs, deck=None):
    """Opponent policy driven by a ByteRL checkpoint, with its own recurrent state."""
    from cg import api as A
    from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M
    sel = obs.get("select") if isinstance(obs, dict) else None
    if sel is None:
        return list(deck) if deck else []
    key = id(model)
    st = _OPP_STATE.get(key)
    try:
        o = A.to_observation_class(obs)
        f = E.encode(o)
    except Exception:  # noqa: BLE001
        return []
    b = M.to_torch(f)
    with torch.no_grad():
        logits, _v, nxt = model.forward(b, st)
        probs = M.masked_probs(logits, b["opt_mask"])[0]
    _OPP_STATE[key] = (nxt[0].detach(), nxt[1].detach())
    k = min(int(f["n_options"]), E.N_OPT)
    if k <= 0:
        return []
    lo = int(sel.get("minCount") or 0)
    hi = int(sel.get("maxCount") or 1)
    n_pick = max(1, min(lo if lo > 0 else 1, hi if hi > 0 else 1, k))
    p = probs[:k]
    s = float(p.sum())
    if s <= 0:
        picks = list(range(n_pick))
    else:
        picks = torch.multinomial(p / p.sum(), n_pick, replacement=False).tolist()
    opts = K.canonical_options(sel)
    try:
        chosen = [opts[i] for i in sorted(picks) if i < len(opts)]
        if chosen:
            return K.to_select_payload(chosen, sel)
    except Exception:  # noqa: BLE001
        pass
    return sorted(set(min(int(i), max(0, len(opts) - 1)) for i in picks))


def learner_update(model, opt, batch, device, stats) -> Dict[str, float]:
    """One optimizer step over a minibatch of unrolls: V-trace + UPGO + value + entropy."""
    from cg import c019_byterl_encode as E, c019_byterl_model as M
    from cg import c019_vtrace as V

    B = len(batch)
    T = batch[0]["mask"].shape[0]
    feats = {k: torch.as_tensor(
        np.stack([b["feats"][k] for b in batch]),                      # [B,T,...]
        dtype=(torch.long if k in E.LONG_KEYS else torch.float32), device=device)
        for k in E.TENSOR_KEYS}

    act = torch.as_tensor(np.stack([b["action_index"] for b in batch]), device=device)
    beh_logp = torch.as_tensor(np.stack([b["behavior_logp"] for b in batch]),
                               dtype=torch.float32, device=device)
    reward = torch.as_tensor(np.stack([b["reward"] for b in batch]),
                             dtype=torch.float32, device=device)
    discount = torch.as_tensor(np.stack([b["discount"] for b in batch]),
                               dtype=torch.float32, device=device)
    mask = torch.as_tensor(np.stack([b["mask"] for b in batch]),
                           dtype=torch.float32, device=device)

    # recurrent forward through the unroll, carrying LSTM state across atomic decisions
    h = torch.zeros(B, HP["lstm_hidden"], device=device)
    c = torch.zeros(B, HP["lstm_hidden"], device=device)
    logps, values, entropies = [], [], []
    for t in range(T):
        step = {k: feats[k][:, t] for k in E.TENSOR_KEYS}
        logits, value, (h, c) = model.forward(step, (h, c))
        logp_all = torch.log_softmax(
            logits.masked_fill(step["opt_mask"] == 0, -1e9), dim=-1)
        logps.append(logp_all.gather(1, act[:, t:t + 1]).squeeze(1))
        p = torch.softmax(logits.masked_fill(step["opt_mask"] == 0, -1e9), dim=-1)
        entropies.append(-(p * logp_all.clamp(min=-30)).sum(-1))
        values.append(value)

    tgt_logp = torch.stack(logps, dim=0)              # [T,B]
    val = torch.stack(values, dim=0)
    ent = torch.stack(entropies, dim=0)
    bl = beh_logp.transpose(0, 1)
    rw = reward.transpose(0, 1)
    dc = discount.transpose(0, 1)
    mk = mask.transpose(0, 1)

    boot = torch.zeros(B, device=device)
    out = V.losses(tgt_logp, bl, val, boot, rw, dc, ent * mk,
                   weights={"policy": HP["policy_vtrace_weight"],
                            "upgo": HP["upgo_weight"], "value": HP["value_weight"],
                            "entropy": HP["entropy_weight"]})
    loss = out["total"]
    if not torch.isfinite(loss):
        stats["nonfinite_losses"] += 1
        return {"skipped": True}
    opt.zero_grad(set_to_none=True)
    loss.backward()
    gn = float(torch.nn.utils.clip_grad_norm_(model.parameters(), HP["max_grad_norm"]))
    if not np.isfinite(gn):
        stats["nonfinite_grads"] += 1
        opt.zero_grad(set_to_none=True)
        return {"skipped": True}
    opt.step()
    stats["optimizer_steps"] += 1
    return {"skipped": False, "total": float(loss), "policy_vtrace": float(out["policy_vtrace"]),
            "upgo": float(out["upgo"]), "value": float(out["value"]),
            "entropy": float(out["entropy"]), "grad_norm": gn,
            "vs_mean": float(out["vs_mean"]), "vs_absmax": float(out["vs_absmax"]),
            "rho_mean": float(out["rho_mean"]),
            "rho_clipped_frac": float(out["rho_clipped_frac"]),
            "upgo_adv_absmean": float(out["upgo_adv_absmean"])}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--learning-periods", type=int, default=6)
    ap.add_argument("--games-per-lp", type=int, default=1024)
    ap.add_argument("--actors", type=int, default=12)
    ap.add_argument("--games-per-round", type=int, default=96)
    # OSFP Algorithm 1 draws opponents from self-play or H only. A fixed scripted-teacher
    # slice would be a predetermined schedule -- exactly what CONTRACT §16 forbids -- so the
    # default is 0.0 and teachers appear only in evaluation, never in the training mixture.
    ap.add_argument("--teacher-fraction", type=float, default=0.0)
    ap.add_argument("--tag", default="byterl")
    ap.add_argument("--seed", type=int, default=1902)
    a = ap.parse_args(argv)

    from cg import teachers as T, c009_eval as ce
    from cg import c019_byterl_model as M, c019_byterl_actor as AC
    from cg import c019_osfp as O

    for d in ("configs", "learner_logs", "checkpoints", "actor_unrolls", "queue_stats",
              "osfp/payoff_tables", "osfp/historical_checkpoints", "raw_games"):
        os.makedirs(os.path.join(BY, d), exist_ok=True)

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    deck = T.read_deck("mega_lucario", ce.SOURCES)
    rng = np.random.default_rng(a.seed)

    model = M.new_model(seed=a.seed, device=dev)          # §9.1 fresh random weights
    opt = torch.optim.Adam(model.parameters(), lr=HP["learning_rate"])
    ckpt_dir = os.path.join(BY, "checkpoints", a.tag)
    os.makedirs(ckpt_dir, exist_ok=True)
    # per-tag pool: a smoke run must not collide with, or contaminate, a scaled run
    hist_dir = os.path.join(BY, "osfp", "historical_checkpoints", a.tag)
    osfp = O.OSFPScheduler(hist_dir, rng)

    json.dump({**HP, "actors": a.actors, "games_per_lp": a.games_per_lp,
               "learning_periods": a.learning_periods,
               "teacher_fraction": a.teacher_fraction,
               "osfp": {"p_current_self_play": O.P_CURRENT_SELF_PLAY,
                        "xi": O.XI_PROMOTION, "max_lp_without_add": O.MAX_LP_WITHOUT_ADD,
                        "min_games_per_historical": O.MIN_GAMES_PER_HISTORICAL,
                        "sampler": "registered hardness x uncertainty (see c019_osfp)"},
               "single_machine_adaptation": (
                   "actors run in rounds against a learner snapshot rather than fully "
                   "asynchronously; staleness is measured per unroll and reported")},
              open(os.path.join(BY, "configs", f"{a.tag}_config.json"), "w"), indent=2)

    queue = collections.deque(maxlen=HP["queue_capacity"])
    stats = collections.Counter()
    version = 0
    lp_log = open(os.path.join(BY, "osfp", f"{a.tag}_learning_periods.jsonl"), "w")
    opp_log = gzip.open(os.path.join(BY, "osfp", f"{a.tag}_opponent_samples.jsonl.gz"), "wt")
    promo_log = open(os.path.join(BY, "osfp", f"{a.tag}_promotion_history.jsonl"), "w")
    loss_log = gzip.open(os.path.join(BY, "learner_logs", f"{a.tag}_losses.jsonl.gz"), "wt")
    games_log = gzip.open(os.path.join(BY, "raw_games", f"{a.tag}_games.jsonl.gz"), "wt")
    teachers = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]

    t_start = time.time()
    total_games = 0
    for lp in range(a.learning_periods):
        lp_t0 = time.time()
        played = 0
        lp_stats = collections.Counter()
        before_hash = hashlib.sha256(
            b"".join(p.detach().cpu().numpy().tobytes()
                     for p in model.parameters())).hexdigest()

        while played < a.games_per_lp:
            n = min(a.games_per_round, a.games_per_lp - played)
            snap = os.path.join(ckpt_dir, f"{a.tag}_v{version:04d}.pt")
            torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                        "version": version, "cfg": model.cfg}, snap)

            jobs = []
            for gi in range(n):
                if rng.random() < a.teacher_fraction:
                    # a fixed slice against scripted teachers keeps a stable external anchor;
                    # it is NOT part of OSFP and is excluded from G/C
                    job = {"kind": "TEACHER", "teacher": teachers[gi % len(teachers)]}
                    opp_rec = {"lp": lp, "kind": "TEACHER", "teacher": job["teacher"]}
                else:
                    opp_rec = osfp.sample_opponent()
                    job = dict(opp_rec)
                job.update({"seat": gi % 2,
                            "game_id": f"{a.tag}:lp{lp}:v{version}:g{total_games + gi}"})
                jobs.append((job, opp_rec))

            chunks = [[] for _ in range(a.actors)]
            for i, (job, _) in enumerate(jobs):
                chunks[i % a.actors].append(job)
            payload = [(snap, version, ch, deck, int(rng.integers(0, 1 << 30)))
                       for ch in chunks if ch]
            with mp.get_context("spawn").Pool(len(payload)) as pool:
                results = pool.map(_actor, payload)
            trajs = [t for r in results for t in r]

            # Pair by game_id, NEVER by list position. `jobs` is in sampling order but `trajs`
            # is concatenated in ACTOR order after round-robin chunking, so `zip(jobs, trajs)`
            # attributes each result to a different game's opponent -- an identity bug that
            # silently corrupts G/C. See failures/DEFECT_osfp_payoff_attribution_misaligned.md.
            by_id = {t.game_id: t for t in trajs}
            if len(by_id) != len(trajs):
                raise RuntimeError(f"duplicate game_id in round: {len(trajs)} trajectories, "
                                   f"{len(by_id)} unique ids")
            missing = [j["game_id"] for j, _ in jobs if j["game_id"] not in by_id]
            if missing:
                raise RuntimeError(f"{len(missing)} jobs returned no trajectory, "
                                   f"first={missing[0]}")

            for job, opp_rec in jobs:
                tr = by_id[job["game_id"]]
                if tr.opponent_kind != opp_rec["kind"]:
                    raise RuntimeError(f"opponent identity mismatch on {tr.game_id}: "
                                       f"sampled {opp_rec['kind']} but actor played "
                                       f"{tr.opponent_kind}")
                if opp_rec.get("kind") == "HISTORICAL_PAYOFF_SAMPLE" and tr.completed:
                    osfp.record_result(opp_rec, tr.result_pm_one)
                opp_log.write(json.dumps({**opp_rec, "game_id": tr.game_id,
                                          "result": tr.result_pm_one,
                                          "completed": tr.completed}) + "\n")
                games_log.write(json.dumps({
                    "game_id": tr.game_id, "lp": lp, "behavior_version": tr.behavior_version,
                    "seat": tr.seat, "opponent_kind": tr.opponent_kind,
                    "opponent_id": tr.opponent_id, "steps": len(tr.steps),
                    "result_pm_one": tr.result_pm_one, "completed": tr.completed,
                    "seconds": round(tr.seconds, 3)}) + "\n")
                lp_stats["games"] += 1
                lp_stats["completed"] += int(tr.completed)
                lp_stats[f"opp:{tr.opponent_kind}"] += 1

            unrolls = AC.unroll_batches(trajs, HP["unroll_length"])
            queue.extend(unrolls)
            stats["unrolls_enqueued"] += len(unrolls)
            played += n
            total_games += n

            # Sample reuse 2 means each COLLECTED sample is consumed twice on average, so the
            # number of minibatches scales with how much new experience arrived. Doing a fixed
            # two minibatches per round would have given each sample well under one use.
            n_batches = max(1, int(round(len(unrolls) * HP["sample_reuse"]
                                         / HP["minibatch_unrolls"])))
            for _ in range(n_batches):
                if len(queue) < HP["minibatch_unrolls"]:
                    break
                idx = rng.choice(len(queue), size=HP["minibatch_unrolls"], replace=False)
                batch = [queue[int(i)] for i in idx]
                stale = [version - b["behavior_version"] for b in batch]
                d = learner_update(model, opt, batch, dev, stats)
                if not d.get("skipped"):
                    version += 1
                    d.update({"lp": lp, "version": version, "queue_len": len(queue),
                              "staleness_mean": float(np.mean(stale)),
                              "staleness_max": int(np.max(stale)),
                              "games_so_far": total_games})
                    loss_log.write(json.dumps(d) + "\n")
                    lp_stats["optimizer_steps"] += 1
            loss_log.flush()
            opp_log.flush()
            games_log.flush()
            print(f"  [lp {lp}] games={played}/{a.games_per_lp} v={version} "
                  f"queue={len(queue)} steps={stats['optimizer_steps']} "
                  f"{time.time() - lp_t0:.0f}s", flush=True)

        after_hash = hashlib.sha256(
            b"".join(p.detach().cpu().numpy().tobytes()
                     for p in model.parameters())).hexdigest()
        learner_path = os.path.join(ckpt_dir, f"{a.tag}_lp{lp:03d}_end.pt")
        torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                    "version": version, "cfg": model.cfg, "lp": lp}, learner_path)

        decision = osfp.end_learning_period(learner_path, version)
        promo_log.write(json.dumps(decision) + "\n")
        promo_log.flush()
        json.dump(osfp.payoff_table(),
                  open(os.path.join(BY, "osfp", "payoff_tables",
                                    f"{a.tag}_payoff_lp{lp:03d}.json"), "w"), indent=2, default=str)
        rec = {"lp": lp, "games": lp_stats["games"], "completed": lp_stats["completed"],
               "optimizer_steps": lp_stats["optimizer_steps"],
               "learner_version": version,
               "checkpoint_before": before_hash, "checkpoint_after": after_hash,
               "weights_changed": before_hash != after_hash,
               "promotion": decision,
               "historical_pool_size": len(osfp.H),
               "observed_self_play_fraction": osfp.observed_self_play_fraction(),
               "opponent_mix": {k: v for k, v in lp_stats.items() if k.startswith("opp:")},
               "seconds": round(time.time() - lp_t0, 1)}
        lp_log.write(json.dumps(rec, default=str) + "\n")
        lp_log.flush()
        print(f"[LP {lp}] games={rec['games']} steps={rec['optimizer_steps']} "
              f"promo={decision['reason']} |H|={len(osfp.H)} "
              f"selfplay={rec['observed_self_play_fraction']} "
              f"moved={rec['weights_changed']}", flush=True)

    for f in (lp_log, opp_log, promo_log, loss_log, games_log):
        f.close()
    final = os.path.join(ckpt_dir, f"{a.tag}_final.pt")
    torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                "version": version, "cfg": model.cfg}, final)
    summary = {
        "tag": a.tag, "device": dev, "hyperparameters": HP,
        "learning_periods": a.learning_periods, "actual_games": total_games,
        "optimizer_steps": stats["optimizer_steps"],
        "nonfinite_losses": stats["nonfinite_losses"],
        "nonfinite_grads": stats["nonfinite_grads"],
        "unrolls_enqueued": stats["unrolls_enqueued"],
        "historical_pool": len(osfp.H),
        "promotions": osfp.promotions,
        "immutability": osfp.verify_immutability(),
        "observed_self_play_fraction": osfp.observed_self_play_fraction(),
        "final_checkpoint": final, "final_sha256": sha_file(final),
        "wall_clock_s": round(time.time() - t_start, 1),
        "initialized_from": "FRESH_RANDOM (§9.1); not a c018 checkpoint",
    }
    json.dump(summary, open(os.path.join(BY, "learner_logs", f"{a.tag}_training_summary.json"), "w"),
              indent=2, default=str)
    print(json.dumps({k: summary[k] for k in
                      ("actual_games", "optimizer_steps", "historical_pool",
                       "observed_self_play_fraction", "wall_clock_s")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

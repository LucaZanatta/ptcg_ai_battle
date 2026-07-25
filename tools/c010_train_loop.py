"""c010 AC-07/08/09: execute one registered arm+seed of the fixed-deck RL loop v2.

Arm A  from B0 (untouched V2-A), exact c008 R1 recipe, <=12,000 games.
Arm B  from I0 (protected c009 incumbent), exact c008 R1 recipe, <=7,500 additional games.
Arm C  from I0, identical to exact R1 except learning rate 3e-5, rollout target 256 completed
       games, and minimum 32,768 trainable decisions per update.

Preserves one compact record per training game, one record per PPO update, value diagnostics
by game phase (held-out), branch checkpoint lineage, lagged self-play snapshot identities, and
the registered screening evaluations. B0/I0 are read-only and can never be overwritten.
"""

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import c010_train as ct, ppo as ppo_mod, rl_policy as rlp  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
TEACHER = "dragapult"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def opponent_distribution(has_lagged):
    """Exact c008 R1 population (§8); before lagged snapshots the 15% is redistributed
    proportionally across teacher / Lucario / Iono."""
    if has_lagged:
        return [(("teacher", TEACHER), 0.35), (("teacher", "mega_lucario"), 0.20),
                (("teacher", "iono"), 0.20), ("__lagged__", 0.15), (("control",), 0.10)]
    return [(("teacher", TEACHER), 0.35 + 0.15 * 0.35 / 0.75),
            (("teacher", "mega_lucario"), 0.20 + 0.15 * 0.20 / 0.75),
            (("teacher", "iono"), 0.20 + 0.15 * 0.20 / 0.75), (("control",), 0.10)]


def load_initialization(init, init_path, seed):
    """Load a protected baseline into a trainable RLPolicy.

    B0 is a c007 ModelV2 checkpoint (bare keys) and MUST be loaded through
    ``init_from_v2a`` — ``RLPolicy.load`` would silently keep random weights because the key
    prefixes and meta layout differ, which would turn Arm A into random-initialized RL (§4
    prohibits that). I0 is a genuine RLPolicy checkpoint and loads directly. This mirrors the
    exact c008 R1 procedure: ``RLPolicy(seed=training_seed).init_from_v2a(V2A)``.
    """
    if init["kind"] == "rl_ckpt_from_v2a":
        pol = rlp.RLPolicy(seed=seed)
        pol.init_from_v2a(init_path)
        return pol, "RLPolicy(seed).init_from_v2a  [exact c008 R1 procedure]"
    return rlp.RLPolicy.load(init_path), "RLPolicy.load"


def verify_initialization(pol, init, init_path):
    """Prove the trainable policy really carries the baseline's weights (guards the silent
    no-op load class of failure)."""
    raw = np.load(init_path)
    prefix = "" if init["kind"] == "rl_ckpt_from_v2a" else "trunk::"
    checked = 0
    for name in ("sem", "ctx", "score2", "emb", "glob"):
        key = prefix + name
        if key in raw.files and name in pol.trunk.p:
            assert np.allclose(pol.trunk.p[name].data, raw[key]), \
                f"initialisation fidelity FAILED: {name} does not match {init['candidate_id']}"
            checked += 1
    assert checked >= 3, f"initialisation fidelity check covered only {checked} tensors"
    return checked


def sample_opponent(rng, lagged):
    dist = opponent_distribution(bool(lagged))
    specs = [d[0] for d in dist]
    probs = np.array([d[1] for d in dist], dtype=float); probs /= probs.sum()
    choice = specs[int(rng.choice(len(specs), p=probs))]
    if choice == "__lagged__":
        ck = lagged[int(rng.integers(0, len(lagged)))]
        return ("lagged", ck, int(rng.integers(0, 1 << 30)))
    return choice


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True, choices=["A", "B", "C"])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--nproc", type=int, default=7)
    p.add_argument("--max-games", type=int, default=None)
    p.add_argument("--calibration", action="store_true",
                   help="short throughput probe: 2 updates, no eval, writes nothing permanent")
    a = p.parse_args(argv)

    reg = json.load(open(os.path.join(ART, "experiment_registry.json")))
    arm_cfg = reg["arms"][a.arm]
    ppo_cfg = dict(arm_cfg["ppo"])
    base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
    init = base[arm_cfg["initialization"]]
    budget = a.max_games or arm_cfg["max_games_per_seed"]
    eval_points = arm_cfg["evaluation_points"]

    outdir = os.path.join(ART, "training", f"arm_{a.arm}", f"seed{a.seed}")
    ckdir = os.path.join(outdir, "checkpoints")
    os.makedirs(ckdir, exist_ok=True)
    log = open(os.path.join(outdir, "train.log"), "w")

    def emit(m):
        log.write(m + "\n"); log.flush(); print(m, flush=True)

    # ---- initialise from the protected baseline (read-only) ----
    init_path = os.path.join(_REPO, init["checkpoint_path"])
    assert sha_file(init_path) == init["checkpoint_sha256"], "initialisation checkpoint hash mismatch"
    pol, init_method = load_initialization(init, init_path, a.seed)
    verify_initialization(pol, init, init_path)   # hard guard: weights really came from the file
    emit(f"[{a.arm} s{a.seed}] initialised from {init['candidate_id']} "
         f"({init['checkpoint_sha256'][:12]}) @ {init.get('training_games')} prior games "
         f"via {init_method} [weight fidelity verified]")

    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ct.SOURCES).deck
    deck_fp = ct.deck_fingerprint(deck) if hasattr(ct, "deck_fingerprint") else \
        hashlib.sha256(",".join(str(c) for c in deck).encode()).hexdigest()
    assert deck_fp == reg["frozen_deck_fingerprint"], "deck is not the exact frozen deck"

    opt = ppo_mod.AdamW(pol.params(), lr=ppo_cfg["learning_rate"], wd=ppo_cfg["weight_decay"])
    rng = np.random.default_rng(a.seed)
    cur_ckpt = os.path.join(outdir, "cur.npz")
    version = 0
    games_done = 0
    updates = 0
    lagged = []
    last_lag = 0
    game_records = []
    update_records = []
    checkpoints = {}
    stop_reason = None
    next_eval = 0
    t_start = time.time()
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=a.nproc)
    max_updates = 2 if a.calibration else 10 ** 9
    try:
        while games_done < budget and stop_reason is None and updates < max_updates:
            frac = games_done / budget
            ent_coef = ppo_cfg["entropy_coef_start"] + \
                (ppo_cfg["entropy_coef_end"] - ppo_cfg["entropy_coef_start"]) * frac
            pol.save(cur_ckpt); version += 1
            cur_sha = sha_file(cur_ckpt)
            _ = ct._SHA.pop(cur_ckpt, None)  # force re-hash next save

            games, n_dec, n_games = [], 0, 0
            t_roll = time.time()
            while n_games < ppo_cfg["rollout_game_target"] or n_dec < ppo_cfg["min_trainable_decisions"]:
                batch = []
                for _ in range(a.nproc):
                    batch.append({"policy_ckpt": cur_ckpt, "policy_version": version,
                                  "policy_sha256": cur_sha, "arm": a.arm, "seed": a.seed,
                                  "game_index": games_done + n_games + len(batch),
                                  "opponent": sample_opponent(rng, lagged),
                                  "seat": int(rng.integers(0, 2)),
                                  "rng_seed": int(rng.integers(0, 1 << 30)), "deck": deck})
                out = pool.map(ct.play_training_game, batch)
                for r in out:
                    game_records.append(r["meta"])
                    if r["meta"]["terminal"] and r["transitions"]:
                        games.append(r["transitions"]); n_dec += len(r["transitions"]); n_games += 1
                if n_games > 3 * ppo_cfg["rollout_game_target"]:
                    break
            roll_s = time.time() - t_roll
            games_done += n_games

            # value diagnostics BEFORE the update (collection-time predictions are held-out)
            ppo_mod.compute_gae(games, ppo_cfg["gamma"], ppo_cfg["gae_lambda"])
            vdiag = ct.value_diagnostics_by_phase(games)

            t_up = time.time()
            cfg = {"gamma": ppo_cfg["gamma"], "lam": ppo_cfg["gae_lambda"], "clip": ppo_cfg["clip"],
                   "vf_coef": ppo_cfg["value_coef"], "max_grad_norm": ppo_cfg["max_grad_norm"],
                   "epochs": ppo_cfg["epochs"], "minibatch": ppo_cfg["minibatch"]}
            diag = ppo_mod.ppo_update(pol, games, cfg, opt, ent_coef, rng=rng)
            up_s = time.time() - t_up
            updates += 1

            recent = game_records[-(n_games + a.nproc * 4):]
            opp_dist = Counter(g["opponent_id"] for g in recent)
            seat_dist = Counter(g["seat"] for g in recent)
            rec = {"arm": a.arm, "seed": a.seed, "update": updates, "games_cumulative": games_done,
                   "games_this_update": n_games, "decisions": diag["n_decisions"],
                   "policy_loss": diag["policy_loss"], "value_loss": diag["value_loss"],
                   "entropy": diag["entropy"], "approx_kl": diag["approx_kl"],
                   "clip_fraction": diag["clip_frac"], "explained_variance_in_sample":
                       diag["explained_variance"], "grad_norm": diag["grad_norm"],
                   "learning_rate": ppo_cfg["learning_rate"], "entropy_coef": ent_coef,
                   "return_mean": diag["return_mean"],
                   "opponent_distribution": dict(opp_dist), "seat_distribution": dict(seat_dist),
                   "value_diagnostics_by_phase": vdiag,
                   "rollout_seconds": round(roll_s, 1), "update_seconds": round(up_s, 1),
                   "elapsed_seconds": round(time.time() - t_start, 1)}
            update_records.append(rec)
            emit(f"[{a.arm} s{a.seed}] g={games_done} upd={updates} ret={diag['return_mean']:+.3f} "
                 f"evIS={diag['explained_variance']:.2f} evHO={vdiag['overall_held_out']['held_out_explained_variance']:.2f} "
                 f"ent={diag['entropy']:.3f} kl={diag['approx_kl']:.4f} clip={diag['clip_frac']:.3f} "
                 f"gn={diag['grad_norm']:.2f} roll={roll_s:.0f}s up={up_s:.0f}s")

            if not np.isfinite(diag["policy_loss"]) or not np.isfinite(diag["value_loss"]):
                stop_reason = "catastrophic_nonfinite_loss"
            if sum(g["invalid_actions"] for g in recent) > 0:
                stop_reason = stop_reason or "reliability_failure_invalid_actions"

            if games_done >= 5000 and games_done - last_lag >= 5000 and not a.calibration:
                lp = os.path.join(ckdir, f"lagged_g{games_done}.npz")
                pol.save(lp); lagged.append(lp); lagged = lagged[-3:]; last_lag = games_done
                emit(f"  lagged snapshot @ {games_done} -> {os.path.basename(lp)} "
                     f"({sha_file(lp)[:12]}), pool={len(lagged)}")

            while (not a.calibration and next_eval < len(eval_points)
                   and games_done >= eval_points[next_eval]):
                pt = eval_points[next_eval]; next_eval += 1
                if pt == 0:
                    continue
                cp = os.path.join(ckdir, f"ckpt_g{games_done}.npz")
                pol.save(cp)
                checkpoints[str(games_done)] = {
                    "checkpoint_path": os.path.relpath(cp, _REPO), "sha256": sha_file(cp),
                    "training_games": games_done, "registered_eval_point": pt,
                    "arm": a.arm, "seed": a.seed, "updates": updates,
                    "parent": init["candidate_id"] if not checkpoints else
                              sorted(checkpoints, key=lambda k: int(k))[-1]}
                emit(f"  checkpoint @ {games_done} (eval point {pt}) -> {os.path.basename(cp)} "
                     f"{sha_file(cp)[:12]}")
    finally:
        pool.close(); pool.join()
    if stop_reason is None:
        stop_reason = "budget_reached" if games_done >= budget else "calibration_probe"

    if a.calibration:
        el = time.time() - t_start
        out = {"arm": a.arm, "seed": a.seed, "updates": updates, "games": games_done,
               "elapsed_seconds": round(el, 1), "games_per_hour": round(3600 * games_done / el, 1),
               "decisions_per_game": round(sum(u["decisions"] for u in update_records)
                                           / max(1, games_done), 2),
               "mean_update_seconds": round(float(np.mean([u["update_seconds"] for u in update_records])), 1),
               "mean_rollout_seconds": round(float(np.mean([u["rollout_seconds"] for u in update_records])), 1),
               "nproc": a.nproc}
        print("CALIBRATION " + json.dumps(out))
        log.close()
        return 0

    with gzip.open(os.path.join(outdir, "training_games.jsonl.gz"), "wt") as fh:
        for g in game_records:
            fh.write(json.dumps(g) + "\n")
    with gzip.open(os.path.join(outdir, "updates.jsonl.gz"), "wt") as fh:
        for u in update_records:
            fh.write(json.dumps(u) + "\n")
    json.dump(checkpoints, open(os.path.join(outdir, "checkpoint_registry.json"), "w"), indent=2)
    el = time.time() - t_start
    summary = {
        "arm": a.arm, "seed": a.seed, "initialization": init["candidate_id"],
        "initialization_sha256": init["checkpoint_sha256"],
        "games_done": games_done, "budget": budget, "updates": updates,
        "trainable_decisions": int(sum(u["decisions"] for u in update_records)),
        "stop_reason": stop_reason, "elapsed_seconds": round(el, 1),
        "games_per_hour": round(3600 * games_done / el, 1),
        "checkpoints": checkpoints, "lagged_snapshots": [os.path.relpath(l, _REPO) for l in lagged],
        "opponent_distribution": dict(Counter(g["opponent_id"] for g in game_records)),
        "seat_distribution": dict(Counter(g["seat"] for g in game_records)),
        "reliability": {"invalid_actions": int(sum(g["invalid_actions"] for g in game_records)),
                        "exceptions": int(sum(g["exceptions"] for g in game_records)),
                        "timeouts": int(sum(g["timeouts"] for g in game_records)),
                        "ordered_blocks": int(sum(g["ordered_blocks"] for g in game_records)),
                        "fallbacks": int(sum(g["fallbacks"] for g in game_records)),
                        "non_terminal": int(sum(1 for g in game_records if not g["terminal"]))},
        "ppo_config": ppo_cfg,
    }
    json.dump(summary, open(os.path.join(outdir, "summary.json"), "w"), indent=2)
    emit(f"DONE {a.arm} s{a.seed}: {games_done} games, {updates} updates, stop={stop_reason}, "
         f"{summary['games_per_hour']:.0f} games/h")
    log.close()
    print(json.dumps({k: summary[k] for k in ("arm", "seed", "games_done", "updates",
                                              "stop_reason", "games_per_hour")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

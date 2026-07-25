"""c011 §12-§16 — scale training on the CUDA backend from the repaired incumbent.

Structure (§9): CPU simulator workers produce identity-preserving NumPy trajectory records;
those are batched to tensors; PPO/value optimisation runs on CUDA; weights are exported back
to the runtime NPZ format so evaluation goes through the established custom action stack.

The learning algorithm is c010 Arm C unchanged (§12) — only the backend and the horizon
differ. The opponent population is c010's exactly (§13).

Two things c010 could not do:
  * every registered checkpoint also writes FULL trainer state (weights, AdamW moments,
    schedules, all four RNG streams, opponent-sampler state, lagged registry), so future
    continuation is literal rather than a warm restart;
  * value diagnostics are computed against ACTUAL terminal outcomes (Brier, calibration
    error, AUC, Monte-Carlo outcome error, EV-vs-outcome, advantage SNR) by game phase,
    rather than only against GAE lambda-returns (§16).

This seed is itself a warm restart: it starts from a c010 checkpoint, which has no trainer
state to restore. That is stated in the summary rather than glossed.
"""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import c010_train as ct, c009_eval as ce, ppo as legacy_ppo, rl_policy as rlp  # noqa: E402
import c011_torch_model as tm  # noqa: E402
import c011_torch_ppo as tp  # noqa: E402
import c011_trainer_state as tstate  # noqa: E402

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts")
TEACHER = "dragapult"

PPO_CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50,
           "max_grad_norm": 0.50, "epochs": 4, "minibatch": 256,
           "learning_rate": 3e-5, "weight_decay": 1e-5,
           "rollout_game_target": 256, "min_trainable_decisions": 32768,
           "entropy_coef_start": 0.006, "entropy_coef_end": 0.002}
EVAL_POINTS = [0, 5000, 10000, 15000, 20000, 30000, 40000]
PHASES = ["0-20", "20-40", "40-60", "60-80", "80-100"]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def opponent_distribution(has_lagged):
    """§13, identical to c010: before lagged self-play the 15% is redistributed
    proportionally across teacher / Lucario / Iono."""
    if has_lagged:
        return [(("teacher", TEACHER), 0.35), (("teacher", "mega_lucario"), 0.20),
                (("teacher", "iono"), 0.20), ("__lagged__", 0.15), (("control",), 0.10)]
    return [(("teacher", TEACHER), 0.35 + 0.15 * 0.35 / 0.75),
            (("teacher", "mega_lucario"), 0.20 + 0.15 * 0.20 / 0.75),
            (("teacher", "iono"), 0.20 + 0.15 * 0.20 / 0.75), (("control",), 0.10)]


def sample_opponent(rng, lagged):
    dist = opponent_distribution(bool(lagged))
    specs = [d[0] for d in dist]
    probs = np.array([d[1] for d in dist], dtype=float); probs /= probs.sum()
    choice = specs[int(rng.choice(len(specs), p=probs))]
    if choice == "__lagged__":
        ck = lagged[int(rng.integers(0, len(lagged)))]
        return ("lagged", ck, int(rng.integers(0, 1 << 30)))
    return choice


def gpu_stats():
    try:
        r = subprocess.run(["nvidia-smi",
                            "--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True,
                           timeout=20)
        u, used, free, temp = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"gpu_util_pct": float(u), "vram_used_mib": float(used),
                "vram_free_mib": float(free), "gpu_temp_c": float(temp)}
    except Exception:  # noqa: BLE001
        return {}


def ram_available_gib():
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable"):
                return round(int(ln.split()[1]) / 1048576, 2)
    except OSError:
        pass
    return None


# ---------------- §16 value diagnostics against ACTUAL outcomes ----------------

def value_diagnostics(games):
    """Per game phase, scored against the terminal outcome the game actually reached.

    c010 reported explained variance against GAE lambda-returns, which is a self-consistency
    measure: a value head can look calibrated against its own bootstrap while predicting the
    eventual WINNER poorly. Here the target is the realised terminal outcome mapped to
    {loss 0, draw 0.5, win 1}, so Brier/AUC/calibration mean what they normally mean.
    """
    buckets = {p: {"pred": [], "out": [], "adv": []} for p in PHASES}
    for tr in games:
        if not tr:
            continue
        final_r = float(tr[-1].get("reward", 0.0))
        outcome = 0.5 * (final_r + 1.0)          # -1/0/+1 -> 0/0.5/1
        n = len(tr)
        for i, t in enumerate(tr):
            frac = (i + 1) / n
            idx = min(int(frac * 5), 4)
            b = buckets[PHASES[idx]]
            b["pred"].append(0.5 * (float(t["value"]) + 1.0))   # value in [-1,1] -> [0,1]
            b["out"].append(outcome)
            if "advantage" in t:
                b["adv"].append(float(t["advantage"]))
    out = {}
    for p, b in buckets.items():
        if not b["pred"]:
            out[p] = {"n": 0}
            continue
        pred = np.clip(np.asarray(b["pred"]), 0.0, 1.0)
        y = np.asarray(b["out"])
        brier = float(np.mean((pred - y) ** 2))
        calib = float(np.mean(pred) - np.mean(y))
        # decisive games only for accuracy/AUC (a draw has no correct label)
        dec = y != 0.5
        acc = auc = None
        if dec.sum() > 0:
            yb = (y[dec] > 0.5).astype(float)
            pb = pred[dec]
            acc = float(np.mean((pb > 0.5).astype(float) == yb))
            if 0 < yb.sum() < len(yb):
                order = np.argsort(pb)
                ranks = np.empty(len(pb)); ranks[order] = np.arange(1, len(pb) + 1)
                n1 = yb.sum(); n0 = len(yb) - n1
                auc = float((ranks[yb == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
        var = float(np.var(y))
        ev = float(1.0 - np.var(y - pred) / var) if var > 1e-12 else None
        adv = np.asarray(b["adv"]) if b["adv"] else np.array([])
        out[p] = {"n": int(len(pred)),
                  "brier_score": brier,
                  "calibration_error": calib,
                  "mean_abs_calibration_error": float(np.mean(np.abs(pred - y))),
                  "outcome_accuracy": acc, "auc": auc,
                  "monte_carlo_outcome_error": float(np.mean(np.abs(pred - y))),
                  "explained_variance_vs_terminal_outcome": ev,
                  "advantage_mean": float(adv.mean()) if adv.size else None,
                  "advantage_std": float(adv.std()) if adv.size else None,
                  "advantage_snr": (float(abs(adv.mean()) / (adv.std() + 1e-12))
                                    if adv.size else None)}
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--nproc", type=int, default=16)
    p.add_argument("--max-games", type=int, default=40000)
    p.add_argument("--device", default="cuda")
    p.add_argument("--smoke", type=int, default=0, help="smoke run: stop after N games")
    a = p.parse_args(argv)

    torch.set_num_threads(max(1, min(8, os.cpu_count() // 3)))
    device = a.device if (a.device == "cpu" or torch.cuda.is_available()) else "cpu"
    dtype = torch.float32

    inc = json.load(open(os.path.join(ART, "c010_repaired_incumbent.json")))
    init_path = os.path.join(_REPO, inc["checkpoint_path"])
    assert sha_file(init_path) == inc["checkpoint_sha256"], "incumbent hash drift"

    outdir = os.path.join(ART, "training", f"seed{a.seed}")
    ckdir = os.path.join(outdir, "checkpoints")
    os.makedirs(ckdir, exist_ok=True)
    log = open(os.path.join(outdir, "train.log"), "w")

    def emit(msg):
        print(msg, flush=True); log.write(msg + "\n"); log.flush()

    # ---- initialise from the repaired incumbent; verify weights actually landed ----
    legacy = rlp.RLPolicy.load(init_path)
    model = tm.TorchPolicy(legacy.trunk.cfg, dtype=dtype,
                           device=device).load_legacy_state(legacy.state_dict())
    raw = np.load(init_path)
    with torch.no_grad():
        chk = 0
        for name in ("sem", "ctx", "score2", "glob"):
            W = raw[f"trunk::{name}"]
            got = getattr(model, name).weight.detach().cpu().double().numpy().T
            assert np.allclose(got, W, atol=1e-6), f"init fidelity FAILED for {name}"
            chk += 1
    emit(f"[S s{a.seed}] initialised from {inc['incumbent_id']} ({inc['checkpoint_sha256'][:12]}) "
         f"on {device}/{dtype} [weight fidelity verified on {chk} tensors] "
         f"-- WARM RESTART: the c010 checkpoint carries no trainer state to restore")

    opt = tp.make_optimizer(model, PPO_CFG["learning_rate"], PPO_CFG["weight_decay"])
    st = tstate.TrainerState(seed=a.seed, games_done=0, updates=0)
    st.seed_all()
    rng = np.random.default_rng(a.seed)

    budget = a.smoke or a.max_games
    games_done = updates = 0
    next_eval = 0
    lagged, last_lag = [], 0
    game_records, update_records = [], []
    checkpoints = {}
    cur_ckpt = os.path.join(outdir, "cur.npz")
    stop_reason = None
    t_start = time.time()
    deck = None
    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ce.SOURCES).deck

    def export_npz(path):
        sd = model.export_legacy_state()
        meta = np.array([legacy.trunk.cfg[k] for k in
                         ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH", "CTX", "OH", "OH2",
                          "SH")] + [a.seed], dtype=np.int64)
        np.savez(path, __meta__=meta, **sd)
        return path

    import multiprocessing as mp
    ctx_mp = mp.get_context("spawn")
    pool = ctx_mp.Pool(processes=a.nproc)
    try:
        while games_done < budget and stop_reason is None:
            frac = games_done / max(budget, 1)
            ent_coef = (PPO_CFG["entropy_coef_start"]
                        + (PPO_CFG["entropy_coef_end"] - PPO_CFG["entropy_coef_start"]) * frac)
            export_npz(cur_ckpt)
            cur_sha = sha_file(cur_ckpt)
            ct._SHA.pop(cur_ckpt, None)
            trainer_state_id = f"S{a.seed}-u{updates}-{cur_sha[:12]}"

            games, n_dec, n_games = [], 0, 0
            t_roll = time.time()
            ram_min = ram_available_gib() or 99
            while n_games < PPO_CFG["rollout_game_target"] or n_dec < PPO_CFG["min_trainable_decisions"]:
                batch = []
                for _ in range(a.nproc):
                    batch.append({"policy_ckpt": cur_ckpt, "policy_version": updates + 1,
                                  "policy_sha256": cur_sha, "arm": "S", "seed": a.seed,
                                  "game_index": games_done + n_games + len(batch),
                                  "opponent": sample_opponent(rng, lagged),
                                  "seat": int(rng.integers(0, 2)),
                                  "rng_seed": int(rng.integers(0, 1 << 30)), "deck": deck})
                out = pool.map(ct.play_training_game, batch)
                for r in out:
                    m = dict(r["meta"]); m["trainer_state_id"] = trainer_state_id
                    game_records.append(m)
                    if m["terminal"] and r["transitions"]:
                        games.append(r["transitions"]); n_dec += len(r["transitions"])
                        n_games += 1
                ram_min = min(ram_min, ram_available_gib() or 99)
                if n_games > 3 * PPO_CFG["rollout_game_target"]:
                    break
            roll_s = time.time() - t_roll
            games_done += n_games

            # GAE first so advantages exist for the diagnostics, then diagnostics BEFORE the
            # update (collection-time predictions are genuinely out of sample)
            flat = legacy_ppo.compute_gae(games, PPO_CFG["gamma"], PPO_CFG["lam"])
            vdiag = value_diagnostics(games)

            t_up = time.time()
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            diag = tp.ppo_update_torch(model, games, PPO_CFG, opt, ent_coef,
                                       rng=rng, device=device, flat=flat)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            up_s = time.time() - t_up
            updates += 1
            st.updates = updates; st.games_done = games_done

            recent = game_records[-(n_games + a.nproc * 4):]
            g = gpu_stats()
            rec = {"seed": a.seed, "update": updates, "games_cumulative": games_done,
                   "games_this_update": n_games, "decisions": diag["n_decisions"],
                   "policy_loss": diag["policy_loss"], "value_loss": diag["value_loss"],
                   "entropy": diag["entropy"], "approx_kl": diag["approx_kl"],
                   "clip_fraction": diag["clip_frac"],
                   "explained_variance_in_sample": diag["explained_variance"],
                   "grad_norm": diag["grad_norm"],
                   "learning_rate": PPO_CFG["learning_rate"], "entropy_coef": ent_coef,
                   "return_mean": diag["return_mean"],
                   "precision_mode": "FP32_CUDA" if device.startswith("cuda") else "FP32_CPU",
                   "device": device,
                   "rollout_seconds": round(roll_s, 1), "update_seconds": round(up_s, 1),
                   "cpu_ram_available_gib": ram_min,
                   **g,
                   "opponent_distribution": dict(Counter(x["opponent_id"] for x in recent)),
                   "seat_distribution": dict(Counter(x["seat"] for x in recent)),
                   "value_diagnostics_by_phase": vdiag,
                   "policy_checkpoint_sha256": cur_sha,
                   "trainer_state_id": trainer_state_id,
                   "elapsed_seconds": round(time.time() - t_start, 1)}
            update_records.append(rec)
            with open(os.path.join(outdir, "updates.partial.jsonl"), "a") as pf:
                pf.write(json.dumps(rec) + "\n")
            v0 = vdiag.get("0-20", {})
            emit(f"[S s{a.seed}] g={games_done} upd={updates} ret={diag['return_mean']:+.3f} "
                 f"ev={diag['explained_variance']:.2f} brier0={v0.get('brier_score', 0):.3f} "
                 f"auc0={(v0.get('auc') or 0):.2f} ent={diag['entropy']:.3f} "
                 f"kl={diag['approx_kl']:.4f} clip={diag['clip_frac']:.3f} "
                 f"gn={diag['grad_norm']:.2f} roll={roll_s:.0f}s up={up_s:.1f}s "
                 f"gpu={g.get('gpu_util_pct')}%")

            if not np.isfinite(diag["policy_loss"]) or not np.isfinite(diag["value_loss"]):
                stop_reason = "catastrophic_nonfinite_loss"
            if sum(x["invalid_actions"] for x in recent) > 0:
                stop_reason = stop_reason or "reliability_failure_invalid_actions"

            if games_done >= 5000 and games_done - last_lag >= 5000:
                lp = os.path.join(ckdir, f"lagged_g{games_done}.npz")
                export_npz(lp); lagged.append(lp); lagged = lagged[-3:]; last_lag = games_done
                st.lagged = [{"path": os.path.relpath(x, _REPO), "sha256": sha_file(x)}
                             for x in lagged]
                emit(f"  lagged snapshot @ {games_done} -> {os.path.basename(lp)}")

            # registered evaluation checkpoints + FULL trainer state
            while next_eval < len(EVAL_POINTS) and games_done >= EVAL_POINTS[next_eval]:
                pt = EVAL_POINTS[next_eval]; next_eval += 1
                if pt == 0:
                    continue
                cp = os.path.join(ckdir, f"ckpt_g{games_done}.npz")
                export_npz(cp)
                tsp = os.path.join(ckdir, f"trainer_g{games_done}.pt")
                st.opponent_sampler_state = {"counts": dict(Counter(
                    x["opponent_id"] for x in game_records))}
                st.trainer_state_id = trainer_state_id
                st.save(tsp, model, opt, entropy_coef=ent_coef,
                        lr=PPO_CFG["learning_rate"])
                checkpoints[str(games_done)] = {
                    "checkpoint_path": os.path.relpath(cp, _REPO), "sha256": sha_file(cp),
                    "trainer_state_path": os.path.relpath(tsp, _REPO),
                    "trainer_state_sha256": sha_file(tsp),
                    "trainer_state_id": trainer_state_id,
                    "training_games": games_done, "registered_eval_point": pt,
                    "seed": a.seed, "updates": updates,
                    "parent": inc["incumbent_id"] if not checkpoints else
                              sorted(checkpoints, key=lambda k: int(k))[-1]}
                emit(f"  checkpoint @ {games_done} (eval point {pt}) + full trainer state")
        # terminal checkpoint when the last registered point was not reached
        if next_eval < len(EVAL_POINTS) and games_done > 0 and str(games_done) not in checkpoints:
            cp = os.path.join(ckdir, f"ckpt_g{games_done}_terminal.npz")
            export_npz(cp)
            tsp = os.path.join(ckdir, f"trainer_g{games_done}_terminal.pt")
            st.save(tsp, model, opt, entropy_coef=ent_coef, lr=PPO_CFG["learning_rate"])
            reached = [p for p in EVAL_POINTS if p <= games_done]
            checkpoints[str(games_done)] = {
                "checkpoint_path": os.path.relpath(cp, _REPO), "sha256": sha_file(cp),
                "trainer_state_path": os.path.relpath(tsp, _REPO),
                "trainer_state_sha256": sha_file(tsp),
                "trainer_state_id": trainer_state_id,
                "training_games": games_done, "registered_eval_point": None,
                "terminal_below_registered_point": True,
                "unreached_registered_point": EVAL_POINTS[next_eval],
                "nearest_registered_point_reached": reached[-1] if reached else 0,
                "seed": a.seed, "updates": updates,
                "parent": sorted(checkpoints, key=lambda k: int(k))[-1] if checkpoints
                          else inc["incumbent_id"]}
            emit(f"  TERMINAL checkpoint @ {games_done} (point {EVAL_POINTS[next_eval]} NOT reached)")
    finally:
        pool.close(); pool.join()

    stop_reason = stop_reason or ("smoke_complete" if a.smoke else "budget_reached")
    with gzip.open(os.path.join(outdir, "training_games.jsonl.gz"), "wt") as fh:
        for m in game_records:
            fh.write(json.dumps(m) + "\n")
    with gzip.open(os.path.join(outdir, "updates.jsonl.gz"), "wt") as fh:
        for r in update_records:
            fh.write(json.dumps(r) + "\n")
    json.dump(checkpoints, open(os.path.join(outdir, "checkpoint_registry.json"), "w"), indent=2)
    el = time.time() - t_start
    summary = {
        "seed": a.seed, "initialization": inc["incumbent_id"],
        "initialization_sha256": inc["checkpoint_sha256"],
        "continuation_kind": "warm_restart",
        "continuation_note": "The c010 incumbent stores policy weights only, so optimizer "
                             "moments, schedules, RNG streams and the opponent sampler start "
                             "fresh. Every c011 checkpoint from update 1 onward carries full "
                             "trainer state, so the NEXT continuation can be literal.",
        "games_done": games_done, "budget": budget, "updates": updates,
        "trainable_decisions": sum(r["decisions"] for r in update_records),
        "stop_reason": stop_reason, "elapsed_seconds": round(el, 1),
        "games_per_hour": round(3600 * games_done / el, 1) if el > 0 else None,
        "device": device, "precision_mode": "FP32_CUDA" if device.startswith("cuda") else "FP32_CPU",
        "workers": a.nproc,
        "checkpoints": checkpoints,
        "lagged_snapshots": [os.path.relpath(x, _REPO) for x in lagged],
        "opponent_distribution": dict(Counter(m["opponent_id"] for m in game_records)),
        "seat_distribution": dict(Counter(m["seat"] for m in game_records)),
        "reliability": {"invalid_actions": sum(m["invalid_actions"] for m in game_records),
                        "exceptions": sum(m["exceptions"] for m in game_records),
                        "timeouts": sum(m["timeouts"] for m in game_records),
                        "fallbacks": sum(m["fallbacks"] for m in game_records),
                        "ordered_blocks": sum(m["ordered_blocks"] for m in game_records)},
    }
    json.dump(summary, open(os.path.join(outdir, "summary.json"), "w"), indent=2)
    emit(f"[S s{a.seed}] DONE games={games_done} updates={updates} stop={stop_reason} "
         f"{summary['games_per_hour']} g/h")
    log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

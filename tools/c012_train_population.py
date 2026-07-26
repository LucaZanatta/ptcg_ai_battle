"""c012 §21-§25 — P0 control and P1 adaptive elite self-play, on the c011 CUDA PPO backend.

Three c011 defects are repaired here, and they are the reason this is a new trainer rather
than a flag on the old one:

  §7  ONE `numpy.random.Generator` drives opponent draws, seats, per-game seeds AND the PPO
      minibatch permutation, and it is saved/restored through `rng.bit_generator.state`.
      c011 saved the legacy global RNG, which the trainer never sampled from.

  §8  The budget counts COMPLETED games, including games that contained only forced
      decisions. c011 counted trainable games and silently excluded those. All three
      counters are tracked separately.

  §9  Registered evaluations run DURING training and can stop a branch early. c011 evaluated
      only after training finished, so its early-stopping rules could never fire.

The learning algorithm is c011's, unchanged (§21). The only new training variable is the
opponent curriculum (§2), which is read from a hash-locked registry and verified at startup
so the lock is mechanical rather than a promise (§20).
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

from cg import c010_train as ct, c009_eval as ce, c011_eval_core as cc  # noqa: E402
import c011_torch_model as tm  # noqa: E402
import c011_torch_ppo as tp  # noqa: E402
import c012_ppo as cp  # noqa: E402
import c012_trainer_state as tstate  # noqa: E402

C012 = os.path.join(_REPO, "contracts",
                    "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART = os.path.join(C012, "results", "artifacts")
TEACHER = "dragapult"

PPO_CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50,
           "max_grad_norm": 0.50, "epochs": 4, "minibatch": 256,
           "learning_rate": 3e-5, "weight_decay": 1e-5,
           "rollout_game_target": 256, "min_trainable_decisions": 32768,
           "entropy_coef_start": 0.006, "entropy_coef_end": 0.002}
EVAL_POINTS = [0, 5000, 10000, 15000, 20000, 25000, 30000]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


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


def ram_gib():
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable"):
                return round(int(ln.split()[1]) / 1048576, 2)
    except OSError:
        pass
    return None


# ---------------- opponent sampling ----------------

def resolve_mixture(curr, arm, stage, lagged, elite_pool):
    """Category probabilities for this arm/stage, from the locked registry (§23/§25).

    Mass is only ever reallocated among registered categories. Before lagged snapshots
    exist, the lagged share is redistributed proportionally across teacher/Lucario/Iono,
    exactly as c011 did.
    """
    base = dict(curr["arms"][arm]["stages"][stage]["mixture"])
    if not elite_pool:
        base.pop("elite", None)
    if not lagged:
        lag = base.pop("lagged", 0.0)
        keys = ["teacher", "mega_lucario", "iono"]
        tot = sum(base[k] for k in keys)
        for k in keys:
            base[k] += lag * base[k] / tot
    s = sum(base.values())
    return {k: v / s for k, v in base.items()}


def sample_opponent(rng, mixture, lagged, elite_pool, elite_weights=None):
    """Draw one opponent. Every draw consumes the single active Generator (§7)."""
    cats = sorted(mixture)
    probs = np.array([mixture[c] for c in cats], dtype=float)
    probs /= probs.sum()
    cat = cats[int(rng.choice(len(cats), p=probs))]
    if cat == "control":
        return ("control",), "control", "__control__", mixture[cat]
    if cat == "lagged":
        ck = lagged[int(rng.integers(0, len(lagged)))]
        return (("lagged", ck, int(rng.integers(0, 1 << 30))), "lagged",
                f"lagged::{os.path.basename(ck)}", mixture[cat])
    if cat == "elite":
        # §25 informative-band preference, implemented as sampling weights over the pool
        w = np.array([(elite_weights or {}).get(e["id"], 1.0) for e in elite_pool], dtype=float)
        w = w / w.sum() if w.sum() > 0 else np.ones(len(elite_pool)) / len(elite_pool)
        e = elite_pool[int(rng.choice(len(elite_pool), p=w))]
        return (("lagged", os.path.join(_REPO, e["checkpoint_path"]),
                 int(rng.integers(0, 1 << 30))), "elite", e["id"], mixture[cat])
    return ("teacher", cat), "teacher", cat, mixture[cat]


# ---------------- in-run evaluation (§9) ----------------

def run_screen(pool, model, export_fn, cur_ckpt, cur_sha, deck, panel, rng, registry_extra):
    """Screen panel executed DURING training through the training pool.

    Returns per-opponent seat-balanced scores. Jobs carry the c009 identity fields and the
    worker re-hashes what it loaded, so in-run evaluation is identity-safe like every other
    panel (§50).
    """
    from cg import noninf_stats as ns
    cand = {"candidate_id": f"INRUN::{cur_sha[:12]}", "kind": "rl_ckpt", "arm": "INRUN",
            "seed": None, "checkpoint_path": os.path.relpath(cur_ckpt, _REPO),
            "checkpoint_sha256": cur_sha}
    jobs = []
    for opp, per_seat in panel.items():
        for seat in (0, 1):
            for r in range(per_seat):
                jobs.append(ce.make_job(cand, opp, seat, r, "inrun_screen",
                                        requested_seed=int(rng.integers(0, 1 << 30)), deck=deck))
    if not jobs:
        return {}, []
    res = pool.map(cc.run_job, jobs)
    per = {}
    for opp in panel:
        s = {0: [], 1: []}
        for g in res:
            if g["opponent_id"] == opp and g["score"] is not None:
                s[g["seat"]].append(g["score"])
        if s[0] or s[1]:
            per[opp] = ns.seat_balanced_point(s[0], s[1])
    return per, res


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True, choices=["P0", "P1"])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--nproc", type=int, default=16)
    p.add_argument("--max-games", type=int, default=30000)
    p.add_argument("--device", default="cuda")
    p.add_argument("--smoke", type=int, default=0)
    a = p.parse_args(argv)

    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 12) // 3)))
    device = a.device if (a.device == "cpu" or torch.cuda.is_available()) else "cpu"
    dtype = torch.float32

    # ---- locked curriculum registry, verified by hash at startup (§20) ----
    creg_p = os.path.join(ART, "curriculum_registry.json")
    csha_p = os.path.join(ART, "curriculum_registry.sha256")
    curr = json.load(open(creg_p))
    want = open(csha_p).read().split()[0]
    got = sha_file(creg_p)
    assert got == want, (f"curriculum registry hash mismatch: {got} != {want}. The registry is "
                         f"locked before the first Phase 2 game (§20) and may not change.")

    inc = json.load(open(os.path.join(ART, "frozen_incumbent_registry.json")))
    init_path = os.path.join(_REPO, inc["TRAINING_INCUMBENT"]["checkpoint_path"])
    assert sha_file(init_path) == inc["TRAINING_INCUMBENT"]["checkpoint_sha256"], "incumbent drift"
    elite_pool = json.load(open(os.path.join(ART, "elite_pool_registry.json")))["elite_pool"] \
        if a.arm == "P1" else []
    for e in elite_pool:
        assert sha_file(os.path.join(_REPO, e["checkpoint_path"])) == e["sha256"], \
            f"elite pool member {e['id']} hash drift"

    outdir = os.path.join(ART, "training", a.arm, f"seed{a.seed}")
    ckdir = os.path.join(outdir, "checkpoints")
    os.makedirs(ckdir, exist_ok=True)
    log = open(os.path.join(outdir, "train.log"), "w")

    def emit(m):
        print(m, flush=True); log.write(m + "\n"); log.flush()

    from cg import rl_policy as rlp
    from cg.teachers import make_fresh
    legacy = rlp.RLPolicy.load(init_path)
    model = tm.TorchPolicy(legacy.trunk.cfg, dtype=dtype,
                           device=device).load_legacy_state(legacy.state_dict())
    raw = np.load(init_path)
    for name in ("sem", "ctx", "score2", "glob"):
        got_w = getattr(model, name).weight.detach().cpu().double().numpy().T
        assert np.allclose(got_w, raw[f"trunk::{name}"], atol=1e-6), f"init fidelity {name}"
    opt = tp.make_optimizer(model, PPO_CFG["learning_rate"], PPO_CFG["weight_decay"])

    # §7: THE Generator. Everything stochastic in this run draws from it.
    rng = tstate.TrainerState.new_rng(a.seed)
    st = tstate.TrainerState(seed=a.seed, entropy_schedule={
        "start": PPO_CFG["entropy_coef_start"], "end": PPO_CFG["entropy_coef_end"],
        "kind": "linear_in_completed_games"})

    deck = make_fresh(TEACHER, ce.SOURCES).deck
    budget = a.smoke or a.max_games
    stage = 0
    stop_reason = None
    completed = trainable_games = trainable_dec = updates = 0
    next_eval = 0
    lagged, last_lag = [], 0
    game_records, update_records, curr_history, inrun_evals = [], [], [], []
    checkpoints = {}
    cur_ckpt = os.path.join(outdir, "cur.npz")
    branch_best = {"composite": None, "teacher": None, "field": None, "ckpt": None}
    no_improve = 0
    t0 = time.time()
    panel = curr["screen_panel"]

    def export(path):
        sd = model.export_legacy_state()
        meta = np.array([legacy.trunk.cfg[k] for k in
                         ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH", "CTX", "OH", "OH2",
                          "SH")] + [a.seed], dtype=np.int64)
        np.savez(path, __meta__=meta, **sd)
        return path

    emit(f"[{a.arm} s{a.seed}] init from {inc['TRAINING_INCUMBENT']['candidate_id']} "
         f"({inc['TRAINING_INCUMBENT']['checkpoint_sha256'][:12]}) on {device} | "
         f"curriculum {curr['registry_id']} sha {want[:12]} | elite pool {len(elite_pool)}")

    import multiprocessing as mp
    pool = mp.get_context("spawn").Pool(processes=a.nproc)
    try:
        while completed < budget and stop_reason is None:
            frac = completed / max(budget, 1)
            ent_coef = (PPO_CFG["entropy_coef_start"]
                        + (PPO_CFG["entropy_coef_end"] - PPO_CFG["entropy_coef_start"]) * frac)
            st.entropy_schedule["fraction"] = frac
            export(cur_ckpt)
            cur_sha = sha_file(cur_ckpt)
            ct._SHA.pop(cur_ckpt, None)
            tsid = f"{a.arm}{a.seed}-u{updates}-{cur_sha[:12]}"
            mixture = resolve_mixture(curr, a.arm, stage, lagged, elite_pool)

            # ---- registered evaluation points, DURING training (§9/§21 game-zero) ----
            while next_eval < len(EVAL_POINTS) and completed >= EVAL_POINTS[next_eval]:
                pt = EVAL_POINTS[next_eval]; next_eval += 1
                pts, raw_games = run_screen(pool, model, export, cur_ckpt, cur_sha, deck,
                                            panel, rng, None)
                fld = [pts[o] for o in ("mega_lucario", "iono", "mega_abomasnow") if o in pts]
                ev = {"arm": a.arm, "seed": a.seed, "registered_point": pt,
                      "completed_games": completed, "updates": updates,
                      "checkpoint_sha256": cur_sha, "trainer_state_id": tsid,
                      "per_opponent": pts,
                      "teacher": pts.get(TEACHER),
                      "field": float(np.mean(fld)) if len(fld) == 3 else None,
                      "n_games": len(raw_games),
                      "defects": sum(1 for g in raw_games if g.get("defect")),
                      "timestamp": time.time()}
                ev["composite"] = (0.40 * (ev["teacher"] or 0) + 0.25 * (ev["field"] or 0)) \
                    if ev["teacher"] is not None else None
                inrun_evals.append(ev)
                emit(f"  [eval @ {completed} pt={pt}] teacher={ev['teacher']} "
                     f"field={ev['field']} n={ev['n_games']}")
                if pt > 0:
                    cpp = os.path.join(ckdir, f"ckpt_g{completed}.npz")
                    export(cpp)
                    tsp = os.path.join(ckdir, f"trainer_g{completed}.pt")
                    st.completed_games = completed
                    st.games_with_trainable_decisions = trainable_games
                    st.trainable_decisions = trainable_dec
                    st.updates = updates; st.trainer_state_id = tsid
                    st.lagged = [{"path": os.path.relpath(x, _REPO), "sha256": sha_file(x)}
                                 for x in lagged]
                    st.curriculum_state = {"stage": stage, "mixture": mixture}
                    st.branch_checkpoints = dict(checkpoints)
                    st.save(tsp, model, opt, rng, PPO_CFG["learning_rate"], ent_coef)
                    checkpoints[str(completed)] = {
                        "checkpoint_path": os.path.relpath(cpp, _REPO), "sha256": sha_file(cpp),
                        "trainer_state_path": os.path.relpath(tsp, _REPO),
                        "trainer_state_sha256": sha_file(tsp), "trainer_state_id": tsid,
                        "training_games": completed, "registered_eval_point": pt,
                        "arm": a.arm, "seed": a.seed, "updates": updates,
                        "curriculum_stage": stage,
                        "inrun_eval": {"teacher": ev["teacher"], "field": ev["field"]}}
                    # ---- early stopping / curriculum gates on REAL evaluation ----
                    improved = (branch_best["composite"] is None
                                or (ev["composite"] or -9) > branch_best["composite"] + 0.02)
                    if improved:
                        branch_best = {"composite": ev["composite"], "teacher": ev["teacher"],
                                       "field": ev["field"], "ckpt": str(completed)}
                        no_improve = 0
                    else:
                        no_improve += 1
                    if completed >= 10000 and no_improve >= 3:
                        stop_reason = "confirmed_plateau_three_consecutive_evaluations"
                    if (completed >= 10000 and branch_best["teacher"] is not None
                            and ev["teacher"] is not None
                            and ev["teacher"] <= branch_best["teacher"] - 0.07
                            and (ev["field"] or 0) <= (branch_best["field"] or 0) - 0.07):
                        stop_reason = "confirmed_severe_regression"
                    if a.arm == "P1":
                        stage, note = advance_curriculum(curr, stage, ev, branch_best)
                        if note:
                            curr_history.append({"completed_games": completed, "stage": stage,
                                                 "mixture": resolve_mixture(curr, a.arm, stage,
                                                                            lagged, elite_pool),
                                                 "reason": note, "eval": ev})
                            emit(f"  [curriculum] stage -> {stage}: {note}")
            if stop_reason:
                break

            # ---- rollout ----
            games, n_dec, n_trainable, n_completed = [], 0, 0, 0
            t_roll = time.time()
            opp_counts, prob_log = Counter(), {}
            while n_completed < PPO_CFG["rollout_game_target"] or n_dec < PPO_CFG["min_trainable_decisions"]:
                batch = []
                for _ in range(a.nproc):
                    spec, cat, oid, prob = sample_opponent(rng, mixture, lagged, elite_pool)
                    prob_log[oid] = prob
                    batch.append({"policy_ckpt": cur_ckpt, "policy_version": updates + 1,
                                  "policy_sha256": cur_sha, "arm": a.arm, "seed": a.seed,
                                  "game_index": completed + n_completed + len(batch),
                                  "opponent": spec, "seat": int(rng.integers(0, 2)),
                                  "rng_seed": int(rng.integers(0, 1 << 30)), "deck": deck,
                                  "_cat": cat, "_oid": oid})
                cats = {j["game_index"]: (j["_cat"], j["_oid"]) for j in batch}
                for j in batch:
                    j.pop("_cat"); j.pop("_oid")
                out = pool.map(ct.play_training_game, batch)
                for r in out:
                    m = dict(r["meta"])
                    cat, oid = cats.get(m["game_index"], ("?", m.get("opponent_id")))
                    m.update({"trainer_state_id": tsid, "opponent_category": cat,
                              "sampling_probability": prob_log.get(oid),
                              "curriculum_stage": stage,
                              "completed_game": bool(m["terminal"])})
                    game_records.append(m)
                    opp_counts[m["opponent_id"]] += 1
                    if m["terminal"]:
                        n_completed += 1                       # §8: every completed game
                        if r["transitions"]:
                            games.append(r["transitions"])
                            n_dec += len(r["transitions"]); n_trainable += 1
                if n_completed > 3 * PPO_CFG["rollout_game_target"]:
                    break
            roll_s = time.time() - t_roll
            completed += n_completed
            trainable_games += n_trainable
            trainable_dec += n_dec

            t_up = time.time()
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            diag = cp.ppo_update(model, games, PPO_CFG, opt, ent_coef, rng, device=device)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            up_s = time.time() - t_up
            updates += 1

            g = gpu_stats()
            rec = {"arm": a.arm, "seed": a.seed, "update": updates,
                   "completed_games": completed,
                   "games_with_trainable_decisions": trainable_games,
                   "trainable_decisions": trainable_dec,
                   "completed_this_update": n_completed,
                   "trainable_this_update": n_trainable, "decisions": diag["n_decisions"],
                   "policy_loss": diag["policy_loss"], "value_loss": diag["value_loss"],
                   "entropy": diag["entropy"], "approx_kl": diag["approx_kl"],
                   "clip_fraction": diag["clip_frac"],
                   "explained_variance": diag["explained_variance"],
                   "grad_norm": diag["grad_norm"], "learning_rate": PPO_CFG["learning_rate"],
                   "entropy_coef": ent_coef, "return_mean": diag["return_mean"],
                   "curriculum_stage": stage, "opponent_probabilities": mixture,
                   "realized_opponent_counts": dict(opp_counts),
                   "seat_distribution": dict(Counter(
                       x["seat"] for x in game_records[-(n_completed + a.nproc * 4):])),
                   "rollout_seconds": round(roll_s, 1), "update_seconds": round(up_s, 1),
                   "orders_digest": diag.get("orders_digest"),
                   "trainer_state_id": tsid, "device": device, "precision_mode": "FP32_CUDA",
                   "cpu_ram_available_gib": ram_gib(), **g,
                   "elapsed_seconds": round(time.time() - t0, 1)}
            update_records.append(rec)
            with open(os.path.join(outdir, "updates.partial.jsonl"), "a") as pf:
                pf.write(json.dumps(rec) + "\n")
            emit(f"[{a.arm} s{a.seed}] c={completed} tr={trainable_games} upd={updates} "
                 f"ret={diag['return_mean']:+.3f} ev={diag['explained_variance']:.2f} "
                 f"ent={diag['entropy']:.3f} kl={diag['approx_kl']:.4f} st={stage} "
                 f"roll={roll_s:.0f}s up={up_s:.1f}s gpu={g.get('gpu_util_pct')}%")

            if not np.isfinite(diag["policy_loss"]) or not np.isfinite(diag["value_loss"]):
                stop_reason = "catastrophic_nonfinite_loss"
            if sum(x["invalid_actions"] for x in
                   game_records[-(n_completed + a.nproc * 4):]) > 0:
                stop_reason = stop_reason or "reliability_failure_invalid_actions"

            if completed >= 5000 and completed - last_lag >= 5000:
                lp = os.path.join(ckdir, f"lagged_g{completed}.npz")
                export(lp); lagged.append(lp); lagged = lagged[-3:]; last_lag = completed
                emit(f"  lagged snapshot @ {completed}")
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
    with open(os.path.join(outdir, "inrun_evaluations.jsonl"), "w") as fh:
        for e in inrun_evals:
            fh.write(json.dumps(e) + "\n")
    if a.arm == "P1":
        with open(os.path.join(outdir, "curriculum_history.jsonl"), "w") as fh:
            for h in curr_history:
                fh.write(json.dumps(h) + "\n")
    el = time.time() - t0
    summary = {
        "arm": a.arm, "seed": a.seed,
        "initialization": inc["TRAINING_INCUMBENT"]["candidate_id"],
        "initialization_sha256": inc["TRAINING_INCUMBENT"]["checkpoint_sha256"],
        "curriculum_registry_id": curr["registry_id"], "curriculum_registry_sha256": want,
        "completed_games": completed,
        "games_with_trainable_decisions": trainable_games,
        "trainable_decisions": trainable_dec,
        "budget_completed_games": budget, "updates": updates, "stop_reason": stop_reason,
        "final_curriculum_stage": stage, "curriculum_changes": len(curr_history),
        "elapsed_seconds": round(el, 1),
        "completed_games_per_hour": round(3600 * completed / el, 1) if el > 0 else None,
        "device": "cuda", "precision_mode": "FP32_CUDA", "workers": a.nproc,
        "checkpoints": checkpoints, "branch_best": branch_best,
        "n_inrun_evaluations": len(inrun_evals),
        "lagged_snapshots": [os.path.relpath(x, _REPO) for x in lagged],
        "opponent_distribution": dict(Counter(m["opponent_id"] for m in game_records)),
        "opponent_category_distribution": dict(Counter(m["opponent_category"]
                                                       for m in game_records)),
        "seat_distribution": dict(Counter(m["seat"] for m in game_records)),
        "reliability": {"invalid_actions": sum(m["invalid_actions"] for m in game_records),
                        "exceptions": sum(m["exceptions"] for m in game_records),
                        "timeouts": sum(m["timeouts"] for m in game_records),
                        "fallbacks": sum(m["fallbacks"] for m in game_records)},
    }
    json.dump(summary, open(os.path.join(outdir, "summary.json"), "w"), indent=2)
    emit(f"[{a.arm} s{a.seed}] DONE completed={completed} trainable={trainable_games} "
         f"upd={updates} stop={stop_reason} {summary['completed_games_per_hour']} g/h")
    log.close()
    return 0


def advance_curriculum(curr, stage, ev, branch_best):
    """§24 gates. Advance only on a registered evaluation that shows preserved teacher score
    and no Iono/Abomasnow regression; never merely because game count increased."""
    stages = curr["arms"]["P1"]["stages"]
    if stage + 1 >= len(stages):
        return stage, None
    t, f = ev.get("teacher"), ev.get("field")
    if t is None or f is None:
        return stage, None
    po = ev.get("per_opponent", {})
    bt = branch_best.get("teacher")
    if bt is not None and t < bt - 1e-9:
        return stage, None
    g = curr["arms"]["P1"]["advance_gates"]
    if po.get("iono", 1.0) < g["min_iono"] or po.get("mega_abomasnow", 1.0) < g["min_abomasnow"]:
        return stage, None
    return stage + 1, (f"teacher {t:.3f} preserved vs branch best {bt}, iono "
                       f"{po.get('iono')} and abomasnow {po.get('mega_abomasnow')} above gate")


if __name__ == "__main__":
    sys.exit(main())

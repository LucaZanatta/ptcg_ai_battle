"""c008 AC-05/06/07: train one RL arm+seed under the registered protocol.

Arms: R0 (random init), R1 (V2-A init), R2 (V2-A init + decaying teacher-replay + frozen-
reference KL). On-policy PPO with the registered hyperparameters, opponent population, seat
balance, lagged self-play, screening cadence, early-stop gates, and validation-only
checkpoint selection (held-out Abomasnow never used here). Screening games are evaluation
and do NOT consume the training-game budget. All training evidence is preserved.
"""

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import rl_policy as rlp, rl_env, ppo as ppo_mod, policy_data_v2 as pd  # noqa: E402
from cg import noninf_stats as ns  # noqa: E402

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
V2A = os.path.join(C007_ART, "checkpoints", "V2_A_selected.npz")
SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                       "results", "artifacts", "teacher_sources")

PPO_CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50, "max_grad_norm": 0.50,
           "epochs": 4, "target_games": 128, "min_decisions": 8192, "minibatch": 512,
           "replay_mb": 256, "ent_start": 0.010, "ent_end": 0.002, "wd": 1e-5}
LR = {"R0": 3e-4, "R1": 1e-4, "R2": 1e-4}
BUDGET = {"R0": 10000, "R1": 30000, "R2": 50000}
STRAT_SCREEN = [("teacher", "dragapult"), ("teacher", "mega_lucario"), ("teacher", "iono")]
SCREEN_LABEL = {"dragapult": "teacher", "mega_lucario": "lucario", "iono": "iono"}


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _replay_coef(frac):
    if frac < 0.20:
        return 0.50
    if frac < 0.50:
        return 0.50 + (0.15 - 0.50) * (frac - 0.20) / 0.30
    if frac < 0.80:
        return 0.15 + (0.05 - 0.15) * (frac - 0.50) / 0.30
    return 0.05


def _kl_coef(frac):
    if frac < 0.20:
        return 0.05
    if frac < 0.60:
        return 0.05 + (0.01 - 0.05) * (frac - 0.20) / 0.40
    return 0.01


def _opp_dist(has_lagged):
    if has_lagged:
        return [(("teacher", "dragapult"), 0.35), (("teacher", "mega_lucario"), 0.20),
                (("teacher", "iono"), 0.20), ("__lagged__", 0.15), (("control",), 0.10)]
    # redistribute 15% across teacher/lucario/iono proportionally (base 0.75)
    return [(("teacher", "dragapult"), 0.35 + 0.15 * 0.35 / 0.75),
            (("teacher", "mega_lucario"), 0.20 + 0.15 * 0.20 / 0.75),
            (("teacher", "iono"), 0.20 + 0.15 * 0.20 / 0.75), (("control",), 0.10)]


def _sample_opp(rng, lagged_ckpts):
    dist = _opp_dist(bool(lagged_ckpts))
    specs = [d[0] for d in dist]; probs = np.array([d[1] for d in dist]); probs /= probs.sum()
    choice = specs[rng.choice(len(specs), p=probs)]
    if choice == "__lagged__":
        ck = lagged_ckpts[rng.integers(0, len(lagged_ckpts))]
        return ("lagged", ck, int(rng.integers(0, 1 << 30)))
    return choice


def screening_eval(cur_ckpt, version, deck, pool, rng, per_seat_strat=20, per_seat_ctrl=10):
    """Greedy eval of the frozen checkpoint vs strategic opponents + control (separate).
    Returns per-opponent seat-balanced score + the registered validation blend."""
    jobs = []
    gid = 0
    for opp in STRAT_SCREEN:
        for seat in (0, 1):
            for _ in range(per_seat_strat):
                jobs.append({"policy_ckpt": cur_ckpt, "policy_version": version, "seat": seat,
                             "rng_seed": int(rng.integers(0, 1 << 30)), "deck": deck,
                             "opponent": opp, "collect": False, "greedy": True})
                gid += 1
    for seat in (0, 1):
        for _ in range(per_seat_ctrl):
            jobs.append({"policy_ckpt": cur_ckpt, "policy_version": version, "seat": seat,
                         "rng_seed": int(rng.integers(0, 1 << 30)), "deck": deck,
                         "opponent": ("control",), "collect": False, "greedy": True})
    res = pool.map(rl_env.play_game, jobs) if pool else [rl_env.play_game(j) for j in jobs]
    by = {}
    defects = {"invalid": 0, "exception": 0, "fallback": 0, "ordered": 0, "incomplete": 0}
    for r in res:
        defects["exception"] += r["n_exception"]; defects["fallback"] += r["n_fallback"]
        defects["ordered"] += r["n_ordered"]
        if not r["completed"]:
            defects["incomplete"] += 1; continue
        by.setdefault((r["opponent"], r["seat"]), []).append(r["score"])
    scores = {}
    for label_key, label in [("dragapult", "teacher"), ("mega_lucario", "lucario"),
                             ("iono", "iono"), ("control", "control")]:
        s0 = by.get((label_key, 0), []); s1 = by.get((label_key, 1), [])
        scores[label] = ns.seat_balanced_point(s0, s1) if (s0 or s1) else None
    blend = (0.40 * (scores["teacher"] or 0) + 0.25 * (scores["lucario"] or 0)
             + 0.25 * (scores["iono"] or 0) + 0.10 * (scores["control"] or 0))
    return {"scores": scores, "validation_blend": blend, "defects": defects,
            "n_games": len(res)}


def early_stop(arm, games, screen_hist):
    """Return (stop, reason) per §13.2/§13.3. screen_hist = list of dicts with games/blend/scores."""
    last = screen_hist[-1]; sc = last["scores"]
    strat = np.mean([sc["lucario"] or 0, sc["iono"] or 0])
    if arm == "R0":
        if games >= 2500 and (sc["control"] or 0) < 0.60 and _at(screen_hist, 2500):
            return True, "R0_control_below_0.60_at_2500"
        if games >= 5000 and (sc["teacher"] or 0) < 0.15 and (sc["lucario"] or 0) < 0.25 and (sc["iono"] or 0) < 0.25:
            return True, "R0_weak_vs_all_at_5000"
        if len(screen_hist) >= 3:
            imp = last["validation_blend"] - screen_hist[-3]["validation_blend"]
            if imp <= 0.02 and games > 2500:
                return True, "R0_no_improvement_gt_2pp_two_evals"
    else:  # R1 / R2
        if 9000 <= games and (sc["teacher"] or 0) < 0.20 and strat < 0.30 and _near(screen_hist, 10000):
            return True, f"{arm}_reject_at_10000"
        if 19000 <= games and (sc["teacher"] or 0) < 0.35 and strat < 0.40 and _near(screen_hist, 20000):
            return True, f"{arm}_reject_at_20000"
        if games > 20000 and len(screen_hist) >= 4:
            imps = [screen_hist[-1]["validation_blend"] - screen_hist[-2]["validation_blend"],
                    screen_hist[-2]["validation_blend"] - screen_hist[-3]["validation_blend"],
                    screen_hist[-3]["validation_blend"] - screen_hist[-4]["validation_blend"]]
            if all(i <= 0.015 for i in imps):
                return True, f"{arm}_no_improvement_gt_1.5pp_three_evals"
    return False, None


def _at(hist, g):
    return any(abs(h["games"] - g) < 800 for h in hist)


def _near(hist, g):
    return any(abs(h["games"] - g) < 3000 for h in hist)


def screening_points(budget):
    pts = [1000, 2500, 5000]
    g = 10000
    while g <= budget:
        pts.append(g); g += 5000
    return pts


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True, choices=["R0", "R1", "R2"])
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--nproc", type=int, default=18)
    p.add_argument("--max-games", type=int, default=None)
    a = p.parse_args(argv)
    import multiprocessing as mp
    arm, seed = a.arm, a.seed
    budget = a.max_games or BUDGET[arm]
    sdir = os.path.join(a.out_dir, arm, f"seed{seed}")
    ckdir = os.path.join(sdir, "checkpoints"); os.makedirs(ckdir, exist_ok=True)
    logf = open(os.path.join(sdir, "train.log"), "w")

    def log(msg):
        logf.write(msg + "\n"); logf.flush()

    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", SOURCES).deck

    # init policy
    pol = rlp.RLPolicy(seed=seed)
    if arm in ("R1", "R2"):
        pol.init_from_v2a(V2A)
    ref_pol = None; replay_pool = None
    if arm == "R2":
        ref_pol = rlp.RLPolicy(seed=seed); ref_pol.init_from_v2a(V2A)  # frozen initial V2-A
        recs = []
        for line in gzip.open(os.path.join(C007_ART, "v2_dataset", "train.jsonl.gz"), "rt"):
            recs.append(json.loads(line))
        replay_pool = [t for d in pd.featurize_split(recs) if (t := rlp.to_rl_transition(d))]
        log(f"R2 replay pool: {len(replay_pool)} teacher decisions (c007 train split only)")

    opt = ppo_mod.AdamW(pol.params(), lr=LR[arm], wd=PPO_CFG["wd"])
    rng = np.random.default_rng(seed)
    cur_ckpt = os.path.join(sdir, "cur.npz")
    version = 0
    games_done = 0
    updates = 0
    lagged_ckpts = []
    screen_hist = []
    checkpoints = {}
    curves = []
    stop_reason = None
    screen_pts = screening_points(budget)
    next_screen = 0
    last_lagged_at = 0
    t_start = time.time()
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=a.nproc)
    try:
        while games_done < budget and stop_reason is None:
            frac = games_done / budget
            ent_coef = PPO_CFG["ent_start"] + (PPO_CFG["ent_end"] - PPO_CFG["ent_start"]) * frac
            rcoef = _replay_coef(frac) if arm == "R2" else 0.0
            kcoef = _kl_coef(frac) if arm == "R2" else 0.0
            # ---- rollout ----
            pol.save(cur_ckpt); version += 1
            games = []; n_dec = 0; n_games = 0; rel = {"exc": 0, "fb": 0, "ord": 0, "inc": 0}
            t_roll = time.time()
            while n_games < PPO_CFG["target_games"] or n_dec < PPO_CFG["min_decisions"]:
                batch = []
                for _ in range(a.nproc):
                    opp = _sample_opp(rng, lagged_ckpts)
                    batch.append({"policy_ckpt": cur_ckpt, "policy_version": version,
                                  "seat": int(rng.integers(0, 2)), "rng_seed": int(rng.integers(0, 1 << 30)),
                                  "deck": deck, "opponent": opp, "collect": True, "greedy": False})
                res = pool.map(rl_env.play_game, batch)
                for r in res:
                    rel["exc"] += r["n_exception"]; rel["fb"] += r["n_fallback"]; rel["ord"] += r["n_ordered"]
                    if r["completed"] and r["transitions"]:
                        games.append(r["transitions"]); n_dec += len(r["transitions"]); n_games += 1
                    elif not r["completed"]:
                        rel["inc"] += 1
                if n_games >= 400:  # safety
                    break
            roll_s = time.time() - t_roll
            games_done += n_games
            # ---- PPO update ----
            t_up = time.time()
            diag = ppo_mod.ppo_update(pol, games, PPO_CFG, opt, ent_coef, ref_policy=ref_pol,
                                      replay_pool=replay_pool, replay_coef=rcoef, kl_coef=kcoef, rng=rng)
            up_s = time.time() - t_up
            updates += 1
            # catastrophic checks
            if not np.isfinite(diag.get("policy_loss", 0.0)) or not np.isfinite(diag.get("value_loss", 0.0)):
                stop_reason = "catastrophic_nonfinite_loss"
            if rel["exc"] > 0:
                stop_reason = stop_reason or "catastrophic_exception"
            row = {"games": games_done, "updates": updates, "decisions": diag["n_decisions"],
                   "return_mean": diag["return_mean"], "policy_loss": diag["policy_loss"],
                   "value_loss": diag["value_loss"], "entropy": diag["entropy"],
                   "approx_kl": diag["approx_kl"], "clip_frac": diag["clip_frac"],
                   "grad_norm": diag["grad_norm"], "explained_variance": diag["explained_variance"],
                   "replay_loss": diag["replay_loss"], "ref_kl": diag["ref_kl"],
                   "entropy_coef": ent_coef, "replay_coef": rcoef, "kl_coef": kcoef,
                   "rollout_s": round(roll_s, 1), "update_s": round(up_s, 1),
                   "games_per_s": round(n_games / (roll_s + up_s + 1e-9), 2)}
            curves.append(row)
            log(f"[{arm} s{seed}] g={games_done} upd={updates} ret={diag['return_mean']:.3f} "
                f"ev={diag['explained_variance']:.2f} ent={diag['entropy']:.3f} kl={diag['approx_kl']:.4f} "
                f"clip={diag['clip_frac']:.3f} gn={diag['grad_norm']:.2f} roll={roll_s:.0f}s up={up_s:.0f}s")
            # ---- lagged self-play snapshot ----
            if games_done >= 5000 and games_done - last_lagged_at >= 5000:
                lck = os.path.join(ckdir, f"lagged_g{games_done}.npz"); pol.save(lck)
                lagged_ckpts.append(lck); lagged_ckpts = lagged_ckpts[-3:]; last_lagged_at = games_done
                log(f"  lagged snapshot @ {games_done} (keep {len(lagged_ckpts)})")
            # ---- screening eval ----
            while next_screen < len(screen_pts) and games_done >= screen_pts[next_screen]:
                pt = screen_pts[next_screen]; next_screen += 1
                ck = os.path.join(ckdir, f"ckpt_g{games_done}.npz"); pol.save(ck); version += 1
                sev = screening_eval(ck, version, deck, pool, rng)
                sev["games"] = games_done; sev["screen_point"] = pt
                sev["checkpoint"] = os.path.relpath(ck, _REPO); sev["sha256"] = _sha(ck)
                screen_hist.append(sev)
                checkpoints[games_done] = {"checkpoint": sev["checkpoint"], "sha256": sev["sha256"],
                                           "validation_blend": sev["validation_blend"],
                                           "scores": sev["scores"], "defects": sev["defects"]}
                log(f"  SCREEN @ {games_done}: blend={sev['validation_blend']:.3f} "
                    f"T={sev['scores']['teacher']} L={sev['scores']['lucario']} I={sev['scores']['iono']} "
                    f"C={sev['scores']['control']} defects={sev['defects']}")
                stop, reason = early_stop(arm, games_done, screen_hist)
                if stop:
                    stop_reason = reason; break
            with open(os.path.join(sdir, "screening.jsonl"), "w") as fh:
                for s in screen_hist:
                    fh.write(json.dumps(s) + "\n")
    finally:
        pool.close(); pool.join()
    if stop_reason is None:
        stop_reason = "budget_reached"

    # checkpoint selection (validation blend; ties -> lower worst-strategic, earlier)
    best = None
    for s in screen_hist:
        worst = min([s["scores"]["teacher"] or 0, s["scores"]["lucario"] or 0, s["scores"]["iono"] or 0])
        key = (s["validation_blend"], worst, -s["games"])
        if best is None or key > best[0]:
            best = (key, s)
    # write evidence
    with open(os.path.join(sdir, "curves.csv"), "w", newline="") as fh:
        if curves:
            w = csv.DictWriter(fh, fieldnames=list(curves[0].keys())); w.writeheader(); w.writerows(curves)
    json.dump(curves, open(os.path.join(sdir, "curves.json"), "w"), indent=1)
    summary = {
        "arm": arm, "seed": seed, "games_done": games_done, "updates": updates,
        "decisions_total": int(sum(c["decisions"] for c in curves)),
        "budget": budget, "stop_reason": stop_reason,
        "lr": LR[arm], "wall_seconds": round(time.time() - t_start, 1),
        "screening_points_evaluated": [s["games"] for s in screen_hist],
        "selected_checkpoint": (best[1]["checkpoint"] if best else None),
        "selected_games": (best[1]["games"] if best else None),
        "selected_validation_blend": (best[1]["validation_blend"] if best else None),
        "selected_scores": (best[1]["scores"] if best else None),
        "final_validation_blend": (screen_hist[-1]["validation_blend"] if screen_hist else None),
        "learning_curve_blend": [(s["games"], round(s["validation_blend"], 4)) for s in screen_hist],
        "throughput_games_per_s": round(games_done / (time.time() - t_start), 2),
        "lagged_snapshots": len(lagged_ckpts),
        "reliability_during_training": {"exceptions": rel["exc"] if 'rel' in dir() else 0},
    }
    json.dump(summary, open(os.path.join(sdir, "summary.json"), "w"), indent=2)
    log(f"DONE {arm} s{seed}: {games_done} games, stop={stop_reason}, "
        f"selected {summary['selected_checkpoint']} blend {summary['selected_validation_blend']}")
    logf.close()
    print(json.dumps({k: summary[k] for k in ("arm", "seed", "games_done", "stop_reason",
          "selected_validation_blend", "selected_games", "throughput_games_per_s", "wall_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

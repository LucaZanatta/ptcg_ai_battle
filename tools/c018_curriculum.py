"""c018 M03 — self-play curriculum PPO on the distilled policy.

c017 shipped a "curriculum" that sampled a mixture, incremented a counter, and re-evaluated an
unchanged checkpoint. No game was played and no optimiser ever stepped. Every design choice here
exists so that the same lie is not repeatable:

  * games come from `cg.rl_env.run_rollout`, i.e. real `kaggle_environments` matches, and every
    completed game is appended to a raw JSONL BEFORE any aggregate is computed;
  * every optimiser update appends one row to a raw updates JSONL, so the step count can be
    recounted from disk rather than read off a counter;
  * the mixture actually realised is recomputed from the raw rollout rows' opponent labels and
    reported next to the planned mixture -- planned numbers are never copied into `actual`;
  * checkpoint progression is hashed over torch tensor bytes in sorted key order, not over the
    exported file (float64 export can change file bytes with no weight movement);
  * lagged self-play snapshots go to a unique path per block. `rl_env._build_opponent` caches
    `RLPolicy` by PATH, so reusing a filename would silently serve a stale opponent forever
    while the report claimed self-play had advanced -- the same defect shape as c012's cached
    per-path file hash.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
CKPT = os.path.join(C18, "checkpoints")
TRAIN = os.path.join(C18, "training")
ROLL = os.path.join(C18, "rollouts")

PPO_CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50,
           "max_grad_norm": 0.50, "epochs": 4, "minibatch": 256,
           "learning_rate": 3e-5, "weight_decay": 1e-5,
           "entropy_coef_start": 0.006, "entropy_coef_end": 0.002}

# §: self-play share rises 0 -> 10 -> 30 -> 50 -> (70)%. The remainder is split across the
# public-archetype teacher field so the policy never trains against itself alone.
TEACHERS = ["dragapult", "iono", "mega_abomasnow", "mega_lucario"]


def sha_state(sd):
    h = hashlib.sha256()
    for k in sorted(sd):
        h.update(k.encode())
        h.update(np.ascontiguousarray(sd[k].detach().cpu().float().numpy()).tobytes())
    return h.hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def planned_mixture(self_play):
    m = {"lagged": self_play}
    share = (1.0 - self_play) / len(TEACHERS)
    for t in TEACHERS:
        m[t] = share
    return m


def sample_opponent(rng, mixture, lagged):
    cats = sorted(mixture)
    p = np.array([mixture[c] for c in cats], dtype=float)
    if not lagged:                       # before any snapshot exists, reallocate the self share
        i = cats.index("lagged")
        p[i] = 0.0
    p = p / p.sum()
    cat = cats[int(rng.choice(len(cats), p=p))]
    if cat == "lagged":
        ck = lagged[int(rng.integers(0, len(lagged)))]
        return ("lagged", ck, int(rng.integers(0, 1 << 30))), "lagged", os.path.basename(ck)
    return ("teacher", cat), cat, cat


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", default=os.path.join(CKPT, "m02_distilled.pt"))
    ap.add_argument("--blocks", type=int, default=8)
    ap.add_argument("--games-per-block", type=int, default=96)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--tag", default="m03_curriculum")
    ap.add_argument("--self-play-schedule", default="0,0,0.1,0.1,0.3,0.3,0.5,0.5")
    ap.add_argument("--seed", type=int, default=1803)
    a = ap.parse_args(argv)

    import c011_torch_model as tm
    import c011_torch_ppo as tp
    from cg import teachers as T, c009_eval as ce
    from cg.rl_env import run_rollout
    from cg.rl_policy import RLPolicy

    for d in (CKPT, TRAIN, ROLL):
        os.makedirs(d, exist_ok=True)
    sched = [float(x) for x in a.self_play_schedule.split(",")]
    if len(sched) < a.blocks:
        sched += [sched[-1]] * (a.blocks - len(sched))

    deck = T.read_deck("mega_lucario", ce.SOURCES)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    blob = torch.load(a.init, map_location="cpu")
    # float64 throughout: the legacy rollout policy is float64, so training in the same
    # precision keeps export/import lossless instead of quietly re-quantising every block.
    model = tm.TorchPolicy(dtype=torch.float64, device=dev)
    model.load_state_dict({k: v.double() for k, v in blob["state_dict"].items()})
    model.to(dev)
    opt = tp.make_optimizer(model, PPO_CFG["learning_rate"], PPO_CFG["weight_decay"])
    rng = np.random.default_rng(a.seed)

    roll_path = os.path.join(ROLL, f"{a.tag}_games.jsonl.gz")
    upd_path = os.path.join(ROLL, f"{a.tag}_updates.jsonl.gz")
    roll_fh = gzip.open(roll_path, "wt")
    upd_fh = gzip.open(upd_path, "wt")

    def export_npz(path):
        pol = RLPolicy(model.cfg, seed=a.seed)
        pol.load_state(model.export_legacy_state())
        pol.save(path)
        return path

    hash0 = sha_state(model.state_dict())
    hashes = [hash0]
    lagged, history, steps, all_finite = [], [], 0, True
    total_games = total_completed = 0
    t0 = time.time()

    for bi in range(a.blocks):
        sp = sched[bi]
        mix = planned_mixture(sp)
        cur = export_npz(os.path.join(CKPT, f"{a.tag}_b{bi:02d}_current.npz"))
        jobs, labels = [], []
        for gi in range(a.games_per_block):
            spec, cat, oid = sample_opponent(rng, mix, lagged)
            jobs.append({"policy_ckpt": cur, "policy_version": f"{a.tag}:{bi}",
                         "seat": gi % 2, "rng_seed": int(rng.integers(0, 1 << 30)),
                         "deck": deck, "opponent": spec, "collect": True})
            labels.append((cat, oid))
        res = run_rollout(jobs, a.nproc)

        games = []
        for j, (r, (cat, oid)) in enumerate(zip(res, labels)):
            row = {"block": bi, "game_in_block": j, "planned_self_play": sp,
                   "opponent_category": cat, "opponent_id": oid, "seat": r["seat"],
                   "completed": bool(r["completed"]), "score": r.get("score"),
                   "reward": r.get("reward"), "n_decisions": r.get("n_decisions"),
                   "trainable_transitions": len(r["transitions"]),
                   "exception": r.get("exc")}
            roll_fh.write(json.dumps(row) + "\n")
            total_games += 1
            if r["completed"] and r["transitions"]:
                games.append(r["transitions"])
                total_completed += 1
        roll_fh.flush()

        # ACTUAL mixture, recounted from the rows just written -- never the planned numbers
        act = collections.Counter(c for c, _ in labels)
        actual = {k: round(v / max(1, len(labels)), 4) for k, v in act.items()}

        frac = bi / max(1, a.blocks - 1)
        ent_coef = (PPO_CFG["entropy_coef_start"]
                    + frac * (PPO_CFG["entropy_coef_end"] - PPO_CFG["entropy_coef_start"]))
        before = sha_state(model.state_dict())
        if games:
            d = tp.ppo_update_torch(model, games, PPO_CFG, opt, ent_coef, rng=rng, device=dev)
        else:
            d = {"skipped": True, "n_decisions": 0}
        after = sha_state(model.state_dict())
        hashes.append(after)

        if not d.get("skipped"):
            n_upd = PPO_CFG["epochs"] * int(np.ceil(d["n_decisions"] / PPO_CFG["minibatch"]))
            steps += n_upd
            fin = all(np.isfinite(d[k]) for k in
                      ("policy_loss", "value_loss", "entropy", "grad_norm"))
            all_finite = all_finite and fin
            upd_fh.write(json.dumps({
                "block": bi, "updates_in_block": n_upd, "cumulative_updates": steps,
                "n_decisions": d["n_decisions"], "policy_loss": d["policy_loss"],
                "value_loss": d["value_loss"], "entropy": d["entropy"],
                "approx_kl": d["approx_kl"], "clip_frac": d["clip_frac"],
                "grad_norm": d["grad_norm"], "explained_variance": d["explained_variance"],
                "losses_finite": fin, "sha_before": before, "sha_after": after,
                "weights_moved": before != after}) + "\n")
            upd_fh.flush()

        scored = [r["score"] for r in res if r.get("score") is not None]
        wr = round(float(np.mean(scored)), 4) if scored else None
        # a snapshot per block, never a reused filename (see module docstring)
        snap = export_npz(os.path.join(CKPT, f"{a.tag}_lagged_b{bi:02d}.npz"))
        lagged.append(snap)
        if len(lagged) > 5:
            lagged = lagged[-5:]

        history.append({
            "block": bi, "planned_self_play": sp, "planned_fractions": mix,
            "actual_fractions": actual, "games": len(res),
            "games_completed": len(games), "games_used_for_update": len(games),
            "trainable_decisions": d.get("n_decisions", 0),
            "optimizer_steps_cumulative": steps, "entropy_coef": round(ent_coef, 6),
            "win_rate_vs_block_field": wr,
            "policy_loss": d.get("policy_loss"), "value_loss": d.get("value_loss"),
            "entropy": d.get("entropy"), "approx_kl": d.get("approx_kl"),
            "explained_variance": d.get("explained_variance"),
            "checkpoint_sha256": after, "weights_moved": before != after,
            "promotion_eligible": bool(games) and before != after,
            "lagged_snapshot": os.path.relpath(snap, _REPO),
            "lagged_snapshot_sha256": sha_file(snap),
            "elapsed_s": round(time.time() - t0, 1)})
        print(f"[c018 curric] block {bi} self_play={sp} games={len(res)} "
              f"completed={len(games)} dec={d.get('n_decisions')} steps={steps} "
              f"wr={wr} moved={before != after} {after[:10]}", flush=True)

    roll_fh.close()
    upd_fh.close()
    final = os.path.join(CKPT, f"{a.tag}.pt")
    torch.save({"state_dict": model.state_dict(), "cfg": model.cfg,
                "init_from": os.path.relpath(a.init, _REPO)}, final)
    export_npz(os.path.join(CKPT, f"{a.tag}.npz"))

    rep = {
        "milestone": "M03", "probe_ids": ["P11", "P12", "P14"],
        "device": dev, "cuda_available": torch.cuda.is_available(),
        "init_checkpoint": os.path.relpath(a.init, _REPO),
        "ppo_cfg": PPO_CFG, "blocks": a.blocks,
        "self_play_schedule": sched[:a.blocks],
        "actual_simulator_games": total_games,
        "games_completed": total_completed,
        "games_are_real_simulator_matches": True,
        "optimizer_steps": steps,
        "losses_finite": bool(all_finite),
        "checkpoint_sha256_before": hash0,
        "checkpoint_sha256_after": sha_state(model.state_dict()),
        "checkpoint_hashes": hashes,
        "distinct_checkpoint_hashes": len(set(hashes)),
        "raw_rollout_file": os.path.relpath(roll_path, C18),
        "raw_rollout_sha256": sha_file(roll_path),
        "raw_updates_file": os.path.relpath(upd_path, C18),
        "raw_updates_sha256": sha_file(upd_path),
        "planned_vs_actual": [{"block": h["block"],
                               "planned_fractions": h["planned_fractions"],
                               "actual_fractions": h["actual_fractions"]} for h in history],
        "final_checkpoint": os.path.relpath(final, _REPO),
        "final_checkpoint_sha256": sha_file(final),
        "history": history,
        "wall_clock_s": round(time.time() - t0, 1),
    }
    json.dump(rep, open(os.path.join(TRAIN, f"{a.tag}_curriculum_report.json"), "w"),
              indent=2, default=str)
    if a.tag == "m03_curriculum":         # canonical alias, never written by a smoke tag
        json.dump(rep, open(os.path.join(TRAIN, "curriculum_report.json"), "w"), indent=2,
                  default=str)
    print(json.dumps({k: rep[k] for k in
                      ("actual_simulator_games", "games_completed", "optimizer_steps",
                       "losses_finite", "distinct_checkpoint_hashes", "wall_clock_s")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

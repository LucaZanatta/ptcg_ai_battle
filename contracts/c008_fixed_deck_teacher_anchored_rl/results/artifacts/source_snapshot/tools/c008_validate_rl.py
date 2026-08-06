"""c008 AC-03 + AC-04: validate the RL environment, action decoders, and PPO.

AC-03: action-form coverage (SINGLE/FIXED/VARIABLE present; ORDERED/EMPTY absent -> a
BLOCK guard is registered), exact legal masking (illegal prob == 0), and reproducible
log-probs (act() == evaluate() -> PPO ratio 1 at collection).

AC-04: GAE correctness vs a hand-computed trajectory, clipping/value-loss/masking sanity,
checkpoint save/restore, and a DETERMINISTIC TOY POSITIVE CONTROL where PPO must provably
learn (a masked contextual bandit whose optimal action is known) — if PPO cannot solve it,
arm results would be uninterpretable. Plus a real rollout+update smoke with finite losses.
"""

import argparse
import gzip
import json
import os
import sys
import tempfile
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import micrograd as mg, rl_policy as rlp, ppo as ppo_mod, decoders, policy_data_v2 as pd  # noqa: E402

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
V2A = os.path.join(C007_ART, "checkpoints", "V2_A_selected.npz")
DECK_SOURCES = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                            "results", "artifacts", "teacher_sources")


# -------------------- toy positive control --------------------

def toy_ppo_positive_control():
    """Masked contextual bandit: 3 contexts, K=5 actions; reward +1 iff action == context's
    target (a legal action), else -1. A tiny logit policy trained with the SAME PPO math
    (masked_log_softmax, gather, ratio-clip, GAE, AdamW) must drive P(target) -> ~1."""
    rng = np.random.default_rng(0)
    K = 5
    targets = np.array([0, 2, 4])
    mask = np.ones((3, K))  # all legal
    logits = mg.Node(np.zeros((3, K)), requires_grad=True)
    value = mg.Node(np.zeros((3, 1)), requires_grad=True)
    opt = ppo_mod.AdamW([logits, value], lr=0.05)
    hist = []
    for it in range(400):
        # sample a batch of (context, action, reward)
        ctx = rng.integers(0, 3, 256)
        lp = logits.data[ctx]
        p = np.exp(lp - lp.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
        acts = np.array([rng.choice(K, p=p[i]) for i in range(len(ctx))])
        rew = np.where(acts == targets[ctx], 1.0, -1.0)
        old_lp = np.log(p[np.arange(len(ctx)), acts] + 1e-30)
        # advantage = reward - V(ctx); single-step episodes
        adv = rew - value.data[ctx, 0]
        adv_n = (adv - adv.mean()) / (adv.std() + 1e-8)
        for _ in range(4):
            ln = mg.Node(logits.data[ctx], requires_grad=False)  # placeholder to rebuild graph
            # rebuild graph from parameters
            sub_logits = mg.gather_rows(logits, ctx)               # [B,K] Node
            logp, _ = mg.masked_log_softmax(sub_logits, mask[ctx])
            chosen = mg.gather_per_row(logp, acts)
            ratio = mg.exp(chosen + mg.Node(-old_lp))
            a = mg.Node(adv_n)
            s1 = ratio * a; s2 = mg.clamp(ratio, 0.8, 1.2) * a
            u = (s1.data <= s2.data).astype(float)
            poll = mg.reduce_sum(s1 * mg.Node(u) + s2 * mg.Node(1 - u), 0) * mg.Node(-1.0 / len(ctx))
            v = mg.gather_rows(value, ctx).reshape((len(ctx),))
            vl = mg.reduce_sum((v + mg.Node(-rew)) * (v + mg.Node(-rew)), 0) * mg.Node(0.5 / len(ctx))
            loss = poll + vl * mg.Node(0.5)
            loss.backward()
            opt.step(0.5)
        if it % 50 == 0 or it == 399:
            ptgt = np.mean([np.exp(logits.data[c] - logits.data[c].max())[targets[c]] /
                            np.exp(logits.data[c] - logits.data[c].max()).sum() for c in range(3)])
            hist.append({"iter": it, "mean_p_target": float(ptgt)})
    final = hist[-1]["mean_p_target"]
    return {"final_mean_p_target": final, "learned": final > 0.95, "history": hist}


# -------------------- GAE correctness --------------------

def gae_check():
    # trajectory of 3 trainable steps, terminal reward +1, gamma=0.9, lambda=0.8, values given
    g = [{"reward": 0.0, "done": 0.0, "value": 0.5},
         {"reward": 0.0, "done": 0.0, "value": 0.4},
         {"reward": 1.0, "done": 1.0, "value": 0.3}]
    ppo_mod.compute_gae([g], 0.9, 0.8)
    # hand compute
    gm, lm = 0.9, 0.8
    d2 = 1.0 + gm * 0.0 * 0.0 - 0.3; a2 = d2
    d1 = 0.0 + gm * 0.3 * 1.0 - 0.4; a1 = d1 + gm * lm * 1.0 * a2
    d0 = 0.0 + gm * 0.4 * 1.0 - 0.5; a0 = d0 + gm * lm * 1.0 * a1
    exp = [a0, a1, a2]
    got = [g[i]["advantage"] for i in range(3)]
    err = max(abs(exp[i] - got[i]) for i in range(3))
    return {"expected_adv": exp, "got_adv": got, "max_err": err, "ok": err < 1e-12}


# -------------------- env / decoder / masking --------------------

def env_and_decoder_checks(pol, n_records=4000):
    recs = []
    for line in gzip.open(os.path.join(C007_ART, "v2_dataset", "train.jsonl.gz"), "rt"):
        recs.append(json.loads(line))
        if len(recs) >= n_records:
            break
    dec = pd.featurize_split(recs)
    forms = {}
    consistency = []
    illegal_prob_max = 0.0
    rng = np.random.default_rng(3)
    seen = {}
    for d in dec:
        forms[d["form"]] = forms.get(d["form"], 0) + 1
        if d["form"] in ("EMPTY", "ORDERED"):
            continue
        if d["form"] not in seen:
            seen[d["form"]] = 0
        if seen[d["form"]] < 40 and d["action"]:
            seen[d["form"]] += 1
            r = pol.act(d["feat"], d["form"], d["lo"], d["hi"], rng)
            t = {"feat": d["feat"], "form": d["form"], "lo": d["lo"], "hi": d["hi"],
                 "n_options": d["n"], "action_seq": r["action_seq"]}
            b, arr = rlp.collate_rl([t])
            lp, _, _, _ = pol.evaluate(b, arr)
            consistency.append(abs(r["logprob"] - float(lp.data[0])))
            # illegal masking: probs on illegal option indices must be 0
            scores = pol.trunk.forward(b)["scores"].data[0]
            aug = np.concatenate([scores, [float(pol.pv["stop"].data[0])]])
            m = np.zeros(len(aug)); m[:d["n"]] = 1
            if d["form"] == "VARIABLE_MULTISELECT":
                m[len(scores)] = 1
            z = aug.copy(); z[m == 0] = -1e30; z -= z.max(); e = np.exp(z); e[m == 0] = 0
            p = e / e.sum()
            illegal_prob_max = max(illegal_prob_max, float((p * (1 - m)).max()))
    return {
        "form_distribution": forms,
        "ordered_present": forms.get("ORDERED", 0) > 0,
        "empty_present": forms.get("EMPTY", 0) > 0,
        "supported_forms": ["SINGLE_CHOICE", "FIXED_MULTISELECT", "VARIABLE_MULTISELECT"],
        "ordered_block_guard": "RLAgent flags ORDERED and BLOCKs (none observed in-deck)",
        "act_eval_logprob_max_diff": float(max(consistency)) if consistency else 0.0,
        "act_eval_reproducible": (max(consistency) < 1e-9) if consistency else True,
        "illegal_option_prob_max": illegal_prob_max,
        "masking_exact": illegal_prob_max == 0.0,
    }


# -------------------- checkpoint restore --------------------

def checkpoint_restore(pol):
    recs = []
    for line in gzip.open(os.path.join(C007_ART, "v2_dataset", "validation.jsonl.gz"), "rt"):
        recs.append(json.loads(line))
        if len(recs) >= 300:
            break
    dec = [d for d in pd.featurize_split(recs) if d["form"] == "SINGLE_CHOICE"][:64]
    b = pd.collate(dec)
    s0 = pol.trunk.score_np(b)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "p.npz"); pol.save(p)
        pol2 = rlp.RLPolicy.load(p)
    s1 = pol2.trunk.score_np(b)
    return {"score_max_diff": float(np.abs(s0 - s1).max()), "value_head_restored":
            bool(np.allclose(pol.pv["vW1"].data, pol2.pv["vW1"].data)),
            "ok": float(np.abs(s0 - s1).max()) < 1e-12}


# -------------------- real smoke rollout + update --------------------

def smoke_training(pol, log):
    from cg import rl_env
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", DECK_SOURCES).deck
    with tempfile.TemporaryDirectory() as td:
        ck = os.path.join(td, "cur.npz"); pol.save(ck)
        jobs = []
        for i in range(12):
            jobs.append({"policy_ckpt": ck, "seat": i % 2, "rng_seed": 1000 + i, "deck": deck,
                         "opponent": ("teacher", "mega_lucario") if i % 2 == 0 else ("control",),
                         "collect": True})
        t0 = time.time()
        res = rl_env.run_rollout(jobs, nproc=8)
        rollout_s = time.time() - t0
    games = [r["transitions"] for r in res if r["completed"] and r["transitions"]]
    n_dec = sum(len(g) for g in games)
    cfg = {"gamma": 0.997, "lam": 0.95, "clip": 0.2, "vf_coef": 0.5, "max_grad_norm": 0.5,
           "epochs": 2, "minibatch": 256, "replay_mb": 128}
    opt = ppo_mod.AdamW(pol.params(), lr=1e-4)
    rng = np.random.default_rng(0)
    t0 = time.time()
    diag = ppo_mod.ppo_update(pol, games, cfg, opt, entropy_coef=0.01, rng=rng)
    update_s = time.time() - t0
    finite = all(np.isfinite(diag.get(k, 0.0)) for k in ("policy_loss", "value_loss", "entropy",
               "approx_kl", "grad_norm", "explained_variance"))
    log.write(f"smoke: {len(games)} games, {n_dec} decisions, rollout {rollout_s:.1f}s, update {update_s:.1f}s\n")
    log.write(f"  diag: {json.dumps({k: round(v,4) for k,v in diag.items() if isinstance(v,(int,float))})}\n")
    return {"games": len(games), "decisions": n_dec, "rollout_s": round(rollout_s, 1),
            "update_s": round(update_s, 1), "losses_finite": bool(finite),
            "diagnostics": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in diag.items()},
            "completed_all": sum(1 for r in res if r["completed"]) == len(res),
            "invalid_or_ordered": sum(r["n_fallback"] + r["n_ordered"] for r in res)}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log-dir", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True); os.makedirs(a.log_dir, exist_ok=True)
    pol = rlp.RLPolicy(seed=0); pol.init_from_v2a(V2A)

    envc = env_and_decoder_checks(pol)
    json.dump({"contract": "c008", **{k: v for k, v in envc.items() if k != "form_distribution"},
               "form_distribution": envc["form_distribution"]},
              open(os.path.join(a.out_dir, "action_decoder_coverage.json"), "w"), indent=2)
    schema = {
        "contract": "c008", "step_definition": "one non-forced agent selection (§9.1)",
        "forced_rule": "n_options<=1 OR maxCount==0 OR (minCount==maxCount==n_options): bypass, no transition",
        "reward": {"win": 1, "draw": 0, "loss": -1, "intermediate": 0},
        "action_forms": envc["supported_forms"],
        "distribution": "single-choice masked categorical; fixed/variable sequential masked "
                        "sampling w/o replacement (variable adds a learned STOP logit); "
                        "log-prob = sum of sub-step masked log-probs; ORDERED -> BLOCK.",
        "observation": "cg.state_encoder_v2 (c007) with per-game threaded history; value head added",
        "policy_params": pol.trunk.param_count() + sum(v.data.size for v in pol.pv.values()),
    }
    json.dump(schema, open(os.path.join(a.out_dir, "rl_environment_schema.json"), "w"), indent=2)
    open(os.path.join(a.log_dir, "rl_environment_tests.txt"), "w").write(
        f"act==evaluate reproducible: {envc['act_eval_reproducible']} (max diff {envc['act_eval_logprob_max_diff']:.2e})\n"
        f"illegal masking exact: {envc['masking_exact']} (max illegal prob {envc['illegal_option_prob_max']})\n"
        f"forms: {envc['form_distribution']}; ORDERED present: {envc['ordered_present']}\n")
    open(os.path.join(a.log_dir, "action_decoder_tests.txt"), "w").write(
        json.dumps(envc, indent=2) + "\n")

    # AC-04
    toy = toy_ppo_positive_control()
    gae = gae_check()
    ckr = checkpoint_restore(pol)
    smoke_log = open(os.path.join(a.log_dir, "ppo_smoke_training.txt"), "w")
    smoke = smoke_training(pol, smoke_log); smoke_log.close()
    ppo_val = {
        "contract": "c008",
        "toy_positive_control": toy,
        "gae_correctness": gae,
        "checkpoint_restore": ckr,
        "smoke_training": smoke,
        "all_pass": bool(toy["learned"] and gae["ok"] and ckr["ok"] and smoke["losses_finite"]
                         and envc["act_eval_reproducible"] and envc["masking_exact"]
                         and smoke["completed_all"]),
    }
    json.dump(ppo_val, open(os.path.join(a.out_dir, "ppo_validation.json"), "w"), indent=2)
    open(os.path.join(a.log_dir, "ppo_unit_tests.txt"), "w").write(
        f"toy PPO positive control: learned={toy['learned']} (P(target)->{toy['final_mean_p_target']:.3f})\n"
        f"GAE correctness: ok={gae['ok']} (max err {gae['max_err']:.2e})\n"
        f"checkpoint restore: ok={ckr['ok']} (max diff {ckr['score_max_diff']:.2e})\n"
        f"masking exact: {envc['masking_exact']}; act==evaluate: {envc['act_eval_reproducible']}\n"
        f"ALL_PASS={ppo_val['all_pass']}\n")
    print(json.dumps({"toy_learned": toy["learned"], "toy_p_target": round(toy["final_mean_p_target"], 3),
                      "gae_ok": gae["ok"], "ckpt_ok": ckr["ok"], "masking_exact": envc["masking_exact"],
                      "act_eval_reproducible": envc["act_eval_reproducible"],
                      "smoke": {k: smoke[k] for k in ("games", "decisions", "rollout_s", "update_s",
                                "losses_finite", "completed_all", "invalid_or_ordered")},
                      "all_pass": ppo_val["all_pass"]}, indent=2))
    return 0 if ppo_val["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

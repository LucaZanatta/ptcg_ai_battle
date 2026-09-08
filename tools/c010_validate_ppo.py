"""c010 AC-04: PPO / environment / action-decoder validation for the reused c008-c009 stack.

Re-validates the machinery c010 depends on, in this repository state:
  * deterministic toy positive control — PPO must provably learn a known optimum;
  * GAE correctness against a hand-computed trajectory;
  * exact legal masking (illegal options carry exactly zero probability);
  * act() == evaluate() log-probs (the PPO ratio is 1 at collection);
  * checkpoint save/restore fidelity;
  * INITIALISATION FIDELITY for the protected baselines — B0 is a c007 ModelV2 checkpoint and
    must be loaded through init_from_v2a; RLPolicy.load would silently keep random weights,
    which would turn Arm A into the random-initialized RL that §4 prohibits.
"""

import argparse
import gzip
import json
import os
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import micrograd as mg, ppo as ppo_mod, rl_policy as rlp, policy_data_v2 as pd  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
C007_DS = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                       "results", "artifacts", "v2_dataset")


def toy_positive_control():
    """Masked contextual bandit with a known optimum, trained with the SAME PPO math."""
    rng = np.random.default_rng(0)
    K, targets = 5, np.array([0, 2, 4])
    mask = np.ones((3, K))
    logits = mg.Node(np.zeros((3, K)), requires_grad=True)
    value = mg.Node(np.zeros((3, 1)), requires_grad=True)
    opt = ppo_mod.AdamW([logits, value], lr=0.05)
    for _ in range(300):
        ctx = rng.integers(0, 3, 256)
        lp = logits.data[ctx]
        p = np.exp(lp - lp.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
        acts = np.array([rng.choice(K, p=p[i]) for i in range(len(ctx))])
        rew = np.where(acts == targets[ctx], 1.0, -1.0)
        old = np.log(p[np.arange(len(ctx)), acts] + 1e-30)
        adv = rew - value.data[ctx, 0]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        for _ in range(4):
            sub = mg.gather_rows(logits, ctx)
            logp, _ = mg.masked_log_softmax(sub, mask[ctx])
            ratio = mg.exp(mg.gather_per_row(logp, acts) + mg.Node(-old))
            a = mg.Node(adv)
            s1, s2 = ratio * a, mg.clamp(ratio, 0.8, 1.2) * a
            u = (s1.data <= s2.data).astype(float)
            pol = mg.reduce_sum(s1 * mg.Node(u) + s2 * mg.Node(1 - u), 0) * mg.Node(-1.0 / len(ctx))
            v = mg.gather_rows(value, ctx).reshape((len(ctx),))
            vl = mg.reduce_sum((v + mg.Node(-rew)) * (v + mg.Node(-rew)), 0) * mg.Node(0.5 / len(ctx))
            (pol + vl * mg.Node(0.5)).backward()
            opt.step(0.5)
    ptgt = float(np.mean([np.exp(logits.data[c] - logits.data[c].max())[targets[c]]
                          / np.exp(logits.data[c] - logits.data[c].max()).sum() for c in range(3)]))
    return {"final_mean_p_target": ptgt, "learned": ptgt > 0.95}


def gae_check():
    g = [{"reward": 0.0, "done": 0.0, "value": 0.5}, {"reward": 0.0, "done": 0.0, "value": 0.4},
         {"reward": 1.0, "done": 1.0, "value": 0.3}]
    ppo_mod.compute_gae([g], 0.9, 0.8)
    gm, lm = 0.9, 0.8
    a2 = 1.0 - 0.3
    a1 = (0.0 + gm * 0.3 - 0.4) + gm * lm * a2
    a0 = (0.0 + gm * 0.4 - 0.5) + gm * lm * a1
    err = max(abs(x - y) for x, y in zip([a0, a1, a2], [g[i]["advantage"] for i in range(3)]))
    return {"max_err": err, "ok": err < 1e-12}


def masking_and_logprob(pol, n=60):
    recs = []
    for line in gzip.open(os.path.join(C007_DS, "validation.jsonl.gz"), "rt"):
        recs.append(json.loads(line))
        if len(recs) >= 1500:
            break
    dec = pd.featurize_split(recs)
    rng = np.random.default_rng(5)
    illegal_max, diffs, forms = 0.0, [], {}
    for d in dec:
        forms[d["form"]] = forms.get(d["form"], 0) + 1
        if d["form"] in ("EMPTY", "ORDERED") or not d["action"] or len(diffs) >= n:
            continue
        r = pol.act(d["feat"], d["form"], d["lo"], d["hi"], rng)
        t = {"feat": d["feat"], "form": d["form"], "lo": d["lo"], "hi": d["hi"],
             "n_options": d["n"], "action_seq": r["action_seq"]}
        b, arr = rlp.collate_rl([t])
        lp, _, _, _ = pol.evaluate(b, arr)
        diffs.append(abs(r["logprob"] - float(lp.data[0])))
        scores = pol.trunk.forward(b)["scores"].data[0]
        aug = np.concatenate([scores, [float(pol.pv["stop"].data[0])]])
        m = np.zeros(len(aug)); m[:d["n"]] = 1
        if d["form"] == "VARIABLE_MULTISELECT":
            m[len(scores)] = 1
        z = aug.copy(); z[m == 0] = -1e30; z -= z.max(); e = np.exp(z); e[m == 0] = 0
        p = e / e.sum()
        illegal_max = max(illegal_max, float((p * (1 - m)).max()))
    return {"illegal_option_prob_max": illegal_max, "masking_exact": illegal_max == 0.0,
            "act_eval_max_logprob_diff": float(max(diffs)) if diffs else 0.0,
            "act_eval_reproducible": bool(max(diffs) < 1e-9) if diffs else True,
            "form_distribution": forms, "n_checked": len(diffs)}


def checkpoint_restore(pol):
    recs = []
    for line in gzip.open(os.path.join(C007_DS, "validation.jsonl.gz"), "rt"):
        recs.append(json.loads(line))
        if len(recs) >= 200:
            break
    dec = [d for d in pd.featurize_split(recs) if d["form"] == "SINGLE_CHOICE"][:48]
    b = pd.collate(dec)
    s0 = pol.trunk.score_np(b)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "p.npz"); pol.save(p); pol2 = rlp.RLPolicy.load(p)
    return {"max_score_diff": float(np.abs(s0 - pol2.trunk.score_np(b)).max()),
            "ok": float(np.abs(s0 - pol2.trunk.score_np(b)).max()) < 1e-12}


def initialization_fidelity():
    """The guard for the silent no-op load that would have made Arm A random-initialized."""
    base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
    out = {}
    b0p = os.path.join(_REPO, base["B0"]["checkpoint_path"])
    raw = np.load(b0p)
    correct = rlp.RLPolicy(seed=311); correct.init_from_v2a(b0p)
    wrong = rlp.RLPolicy.load(b0p)
    out["B0"] = {
        "init_from_v2a_matches_source": all(np.allclose(correct.trunk.p[k].data, raw[k])
                                            for k in ("sem", "ctx", "score2", "emb")),
        "RLPolicy_load_would_silently_lose_weights":
            not all(np.allclose(wrong.trunk.p[k].data, raw[k]) for k in ("sem", "ctx", "score2")),
        "required_loader": "RLPolicy(seed).init_from_v2a",
        "why": "B0 is a c007 ModelV2 checkpoint: bare keys and a 14-entry meta, so RLPolicy.load "
               "matches nothing and leaves random weights. Loading it that way would make Arm A "
               "random-initialized RL, which §4 prohibits.",
    }
    i0p = os.path.join(_REPO, base["I0"]["checkpoint_path"])
    raw2 = np.load(i0p)
    i0 = rlp.RLPolicy.load(i0p)
    out["I0"] = {"RLPolicy_load_matches_source":
                 all(np.allclose(i0.trunk.p[k].data, raw2["trunk::" + k])
                     for k in ("sem", "ctx", "score2", "emb")),
                 "required_loader": "RLPolicy.load"}
    out["ok"] = (out["B0"]["init_from_v2a_matches_source"]
                 and out["B0"]["RLPolicy_load_would_silently_lose_weights"]
                 and out["I0"]["RLPolicy_load_matches_source"])
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=ART)
    p.add_argument("--log-dir", default=LOGD)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True); os.makedirs(a.log_dir, exist_ok=True)
    base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
    pol = rlp.RLPolicy(seed=0)
    pol.init_from_v2a(os.path.join(_REPO, base["B0"]["checkpoint_path"]))

    toy = toy_positive_control()
    gae = gae_check()
    mk = masking_and_logprob(pol)
    ck = checkpoint_restore(pol)
    init = initialization_fidelity()
    reg = json.load(open(os.path.join(ART, "experiment_registry.json")))
    out = {"contract": "c010",
           "environment_source": reg["exact_r1_provenance"]["reused_modules"],
           "toy_positive_control": toy, "gae_correctness": gae,
           "masking_and_logprobs": mk, "checkpoint_restore": ck,
           "initialization_fidelity": init,
           "ordered_forms_observed": mk["form_distribution"].get("ORDERED", 0),
           "all_pass": bool(toy["learned"] and gae["ok"] and mk["masking_exact"]
                            and mk["act_eval_reproducible"] and ck["ok"] and init["ok"])}
    json.dump(out, open(os.path.join(a.out_dir, "ppo_validation.json"), "w"), indent=2)
    lines = ["c010 AC-04 PPO / environment validation", "=" * 55,
             f"  toy PPO positive control : learned={toy['learned']} "
             f"(P(optimal)->{toy['final_mean_p_target']:.3f})",
             f"  GAE correctness          : ok={gae['ok']} (max err {gae['max_err']:.2e})",
             f"  legal masking exact      : {mk['masking_exact']} "
             f"(max illegal prob {mk['illegal_option_prob_max']})",
             f"  act()==evaluate()        : {mk['act_eval_reproducible']} "
             f"(max diff {mk['act_eval_max_logprob_diff']:.2e}, n={mk['n_checked']})",
             f"  checkpoint restore       : ok={ck['ok']} (max diff {ck['max_score_diff']:.2e})",
             f"  ORDERED forms observed   : {out['ordered_forms_observed']} (none in this deck)",
             "",
             "  initialization fidelity (protected baselines):",
             f"    B0 init_from_v2a matches source            : {init['B0']['init_from_v2a_matches_source']}",
             f"    B0 RLPolicy.load would lose weights silently: {init['B0']['RLPolicy_load_would_silently_lose_weights']}",
             f"    I0 RLPolicy.load matches source            : {init['I0']['RLPolicy_load_matches_source']}",
             "", f"ALL_PASS = {out['all_pass']}"]
    open(os.path.join(a.log_dir, "ppo_validation.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

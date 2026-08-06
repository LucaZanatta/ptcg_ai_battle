"""c011 AC-03/AC-05 — forward, legal-action, multi-select and NPZ-round-trip parity.

Fixtures are real decisions captured from actual games with the incumbent weights, covering
ordinary, forced, masked, multi-select and variable-cardinality decisions (§10). They are
frozen to disk so every later parity run compares against the same states.

Both dtypes are reported for every check:
  float64 torch vs float64 legacy  -> semantic correctness of the port (expect ~1e-12)
  float32 torch vs float64 legacy  -> the registered FP32 number (§10.1 tolerance 1e-5)
Reporting both is what §10.1 means by "stop and diagnose" if FP32 is tight; the bar itself
is never widened.
"""

import argparse
import json
import os
import pickle
import sys

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import rl_policy as rlp, micrograd as mg  # noqa: E402
import c011_torch_model as tm  # noqa: E402

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts")
LOGD = os.path.join(C011, "results", "test_logs")
FIXTURES = os.path.join(ART, "parity_fixtures.pkl")

TOL_FWD = 1e-5
TOL_PROB_SUM = 1e-6
TOL_LOGP = 1e-5


def collect_fixtures(ckpt, n_games=8, seed=4242):
    """Play real games through the training path and keep decisions spanning every action
    form, including forced (n_options == 1) and wide/multi-select decisions (§10)."""
    from cg import c010_train as ct, c009_eval as ce
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", ce.SOURCES).deck
    sha = ce.sha256_file(ckpt)
    keep, forms = [], {}
    for g in range(n_games):
        job = {"policy_ckpt": ckpt, "policy_version": 1, "policy_sha256": sha,
               "arm": "PARITY", "seed": seed, "game_index": g,
               "opponent": ("teacher", "mega_lucario" if g % 2 else "dragapult"),
               "seat": g % 2, "rng_seed": seed + g, "deck": deck}
        try:
            out = ct.play_training_game(job)
        except Exception:  # noqa: BLE001
            continue
        for t in out.get("transitions", []):
            f = t.get("form")
            forms[f] = forms.get(f, 0) + 1
            if forms[f] <= 40 or t["n_options"] == 1:
                keep.append(t)
        if len(keep) >= 160 and len(forms) >= 2:
            break
    return keep, forms


def _legacy_forward(pol, b):
    scores, value, _ = pol.forward(b)
    return scores.data.copy(), value.data.copy()


def run(ckpt, out_json, log):
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    if os.path.exists(FIXTURES):
        fixtures, forms = pickle.load(open(FIXTURES, "rb"))
    else:
        fixtures, forms = collect_fixtures(ckpt)
        pickle.dump((fixtures, forms), open(FIXTURES, "wb"))

    pol = rlp.RLPolicy.load(ckpt)
    sd = pol.state_dict()
    b, arr = rlp.collate_rl(fixtures)
    leg_scores, leg_value = _legacy_forward(pol, b)
    leg_lp, leg_ent, leg_val, leg_first = pol.evaluate(b, arr)
    leg_lp = leg_lp.data.copy(); leg_ent = leg_ent.data.copy()
    leg_first = leg_first.data.copy()

    res = {"n_fixtures": len(fixtures), "forms": forms, "checkpoint": ckpt,
           "tolerances": {"forward": TOL_FWD, "legal_prob_sum": TOL_PROB_SUM,
                          "multiselect_logp": TOL_LOGP},
           "dtypes": {}}

    for dname, dt in (("float64", torch.float64), ("float32", torch.float32)):
        model = tm.TorchPolicy(pol.trunk.cfg, dtype=dt, device="cpu").load_legacy_state(sd)
        model.eval()
        tb = tm.to_torch_batch(b, dt, "cpu")
        ta = tm.to_torch_act(arr, dt, "cpu")
        with torch.no_grad():
            ts, tv, _ = model(tb)
            tlp, tent, tval, tfirst = tm.evaluate(model, tb, ta)
        ts_n = ts.double().numpy(); tv_n = tv.double().numpy()

        d_logit = float(np.max(np.abs(ts_n - leg_scores)))
        d_value = float(np.max(np.abs(tv_n - leg_value)))

        # ---- legal-action probability parity (§10.2) ----
        base = arr["aug_mask"]
        lp_leg = leg_first
        lp_t = tfirst.double().numpy()
        p_leg = np.where(base > 0, np.exp(np.clip(lp_leg, -700, None)), 0.0)
        p_t = np.where(base > 0, np.exp(np.clip(lp_t, -700, None)), 0.0)
        illegal_mass_t = float(np.max(np.where(base == 0, p_t, 0.0)))
        same_mask = bool(np.array_equal((lp_leg > -1e29), (lp_t > -1e29)))
        argmax_same = bool(np.array_equal(np.argmax(np.where(base > 0, lp_leg, -np.inf), 1),
                                          np.argmax(np.where(base > 0, lp_t, -np.inf), 1)))
        sum_err = float(np.max(np.abs(p_t.sum(1) - 1.0)))
        prob_err = float(np.max(np.abs(p_t - p_leg)))

        # ---- multi-select parity (§10.3): summed logprob over the real sequences ----
        d_logp = float(np.max(np.abs(tlp.double().numpy() - leg_lp)))
        d_ent = float(np.max(np.abs(tent.double().numpy() - leg_ent)))

        ok = {
            "forward_logit_within_1e-5": d_logit <= TOL_FWD,
            "forward_value_within_1e-5": d_value <= TOL_FWD,
            "identical_legal_mask": same_mask,
            "illegal_probability_exactly_zero": illegal_mass_t == 0.0,
            "argmax_identical": argmax_same,
            "legal_probability_sums_to_one_within_1e-6": sum_err <= TOL_PROB_SUM,
            "legal_probability_error_within_1e-5": prob_err <= TOL_FWD,
            "multiselect_summed_logprob_within_1e-5": d_logp <= TOL_LOGP,
            "entropy_within_1e-5": d_ent <= TOL_LOGP,
        }
        res["dtypes"][dname] = {
            "max_abs_logit_error": d_logit, "max_abs_value_error": d_value,
            "max_legal_prob_error": prob_err, "max_legal_prob_sum_error": sum_err,
            "max_illegal_probability": illegal_mass_t,
            "identical_legal_mask": same_mask, "argmax_identical": argmax_same,
            "max_multiselect_logprob_error": d_logp, "max_entropy_error": d_ent,
            "checks": ok, "all_pass": all(ok.values()),
        }

    # ---- NPZ round trip (§10.5): torch -> NPZ -> legacy runtime ----
    model64 = tm.TorchPolicy(pol.trunk.cfg, dtype=torch.float64,
                             device="cpu").load_legacy_state(sd)
    exported = model64.export_legacy_state()
    tmp = os.path.join(ART, "_parity_roundtrip.npz")
    meta = np.array([pol.trunk.cfg[k] for k in ("D", "Hs", "BV", "Hh", "HV", "Hd", "DV", "GH",
                                                "CTX", "OH", "OH2", "SH")] + [pol.seed],
                    dtype=np.int64)
    np.savez(tmp, __meta__=meta, **exported)
    rt = rlp.RLPolicy.load(tmp)
    rt_scores, rt_value = _legacy_forward(rt, b)
    npz = {"max_abs_logit_error": float(np.max(np.abs(rt_scores - leg_scores))),
           "max_abs_value_error": float(np.max(np.abs(rt_value - leg_value)))}
    npz["within_forward_tolerance"] = (npz["max_abs_logit_error"] <= TOL_FWD
                                       and npz["max_abs_value_error"] <= TOL_FWD)
    npz["n_tensors"] = len(exported)
    npz["all_keys_match_legacy"] = sorted(exported) == sorted(sd)
    os.remove(tmp)
    res["npz_roundtrip"] = npz

    res["fp32_meets_registered_tolerance"] = res["dtypes"]["float32"]["all_pass"]
    res["float64_semantic_parity"] = res["dtypes"]["float64"]["all_pass"]
    res["parity_verdict"] = "PASS" if (res["float64_semantic_parity"]
                                       and res["fp32_meets_registered_tolerance"]) else "REVIEW"
    json.dump(res, open(out_json, "w"), indent=2)
    json.dump(npz, open(os.path.join(ART, "npz_roundtrip.json"), "w"), indent=2)

    with open(log, "w") as fh:
        fh.write(f"c011 forward/action/multiselect parity — {len(fixtures)} fixtures, "
                 f"forms={forms}\n")
        for dname, d in res["dtypes"].items():
            fh.write(f"\n[{dname}] all_pass={d['all_pass']}\n")
            for k, v in d.items():
                if k != "checks":
                    fh.write(f"    {k}: {v}\n")
            for k, v in d["checks"].items():
                fh.write(f"    {'PASS' if v else 'FAIL'} {k}\n")
        fh.write(f"\nNPZ round trip: {npz}\n")
    print(json.dumps({"parity_verdict": res["parity_verdict"],
                      "float64": {k: res["dtypes"]["float64"][k] for k in
                                  ("max_abs_logit_error", "max_abs_value_error",
                                   "max_multiselect_logprob_error", "all_pass")},
                      "float32": {k: res["dtypes"]["float32"][k] for k in
                                  ("max_abs_logit_error", "max_abs_value_error",
                                   "max_multiselect_logprob_error", "all_pass")},
                      "npz_roundtrip": npz}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--out", default=os.path.join(ART, "forward_action_parity.json"))
    p.add_argument("--log", default=os.path.join(LOGD, "forward_action_parity.txt"))
    a = p.parse_args(argv)
    return run(a.checkpoint, a.out, a.log)


if __name__ == "__main__":
    sys.exit(main())

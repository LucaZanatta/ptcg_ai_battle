"""c011 AC-04/AC-05 — PPO fixed-batch parity and full trainer-state round trip.

§10.4 compares one registered PPO update computed by the legacy NumPy/micrograd path and by
the PyTorch path on the SAME frozen trajectory batch, with the SAME minibatch permutation.
The permutation is not merely re-seeded: legacy shuffles a persistent array once per epoch,
so the torch side consumes the identical sequence produced by an identically-seeded
Generator. Advantages/returns come from the legacy GAE on the legacy records, so any
difference is attributable to the update, not to data preparation.

Reported for both dtypes. float64 isolates algorithmic identity from precision; float32 is
the configuration training will actually use.

§10.6 saves and restores policy weights, AdamW state, optimizer step, LR/entropy schedule
state, game/update counters, Python/NumPy/torch-CPU/torch-CUDA RNGs, the opponent-sampler
state and the lagged-snapshot registry, then requires the NEXT update to match an
uninterrupted control within the PPO tolerances.
"""

import argparse
import json
import os
import pickle
import random
import sys

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import ppo as legacy_ppo, rl_policy as rlp  # noqa: E402
import c011_torch_model as tm  # noqa: E402
import c011_torch_ppo as tp  # noqa: E402
import c011_trainer_state as ts  # noqa: E402

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts")
LOGD = os.path.join(C011, "results", "test_logs")
BATCH = os.path.join(ART, "ppo_parity_batch.pkl")

TOL = 1e-4
COS_MIN = 0.999

CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50, "max_grad_norm": 0.50,
       "epochs": 4, "minibatch": 256}
LR = 3e-5
WD = 1e-5
ENT = 0.004


def collect_batch(ckpt, n_games=10, seed=90210):
    from cg import c010_train as ct, c009_eval as ce
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", ce.SOURCES).deck
    sha = ce.sha256_file(ckpt)
    games = []
    for g in range(n_games):
        job = {"policy_ckpt": ckpt, "policy_version": 1, "policy_sha256": sha,
               "arm": "PARITY", "seed": seed, "game_index": g,
               "opponent": ("teacher", "mega_lucario" if g % 2 else "dragapult"),
               "seat": g % 2, "rng_seed": seed + g, "deck": deck}
        try:
            out = ct.play_training_game(job)
        except Exception:  # noqa: BLE001
            continue
        if out["meta"]["terminal"] and out["transitions"]:
            games.append(out["transitions"])
    return games


# legacy <-> torch parameter mapping (legacy stores [fan_in,fan_out]; nn.Linear [fan_out,fan_in])
PAIRS = [(f"trunk::{n}", n, True) for n in tm.TorchPolicy._TRUNK] + \
        [(f"trunk::{n}_b", n, False) for n in tm.TorchPolicy._TRUNK] + \
        [("pv::vW1", "vW1", True), ("pv::vb1", "vW1", False),
         ("pv::vW2", "vW2", True), ("pv::vb2", "vW2", False)]


def torch_tensor_for(model, attr, is_weight):
    mod = getattr(model, attr)
    return (mod.weight if is_weight else mod.bias)


def cosine(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def run_parity(ckpt):
    det = tm.enable_determinism()
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    if os.path.exists(BATCH):
        games = pickle.load(open(BATCH, "rb"))
    else:
        games = collect_batch(ckpt)
        pickle.dump(games, open(BATCH, "wb"))
    n_dec = sum(len(g) for g in games)

    # ---------- legacy update ----------
    legacy_pol = rlp.RLPolicy.load(ckpt)
    before_legacy = {k: v.copy() for k, v in legacy_pol.state_dict().items()}
    opt = legacy_ppo.AdamW(legacy_pol.params(), lr=LR, wd=WD)
    leg_diag = legacy_ppo.ppo_update(legacy_pol, games, CFG, opt, ENT,
                                     rng=np.random.default_rng(7))
    after_legacy = legacy_pol.state_dict()
    delta_legacy = {k: after_legacy[k] - before_legacy[k] for k in after_legacy}

    # the identical permutation sequence legacy consumed
    flat_n = leg_diag["n_decisions"]
    orders = tp.precompute_order(flat_n, CFG["epochs"], np.random.default_rng(7))

    out = {"n_games": len(games), "n_decisions": n_dec, "checkpoint": ckpt,
           "tolerances": {"loss": TOL, "cosine": COS_MIN}, "determinism": det,
           "legacy": leg_diag, "dtypes": {}}

    for dname, dt in (("float64", torch.float64), ("float32", torch.float32)):
        model = tm.TorchPolicy(legacy_pol.trunk.cfg, dtype=dt,
                               device="cpu").load_legacy_state(before_legacy)
        before_t = {a: torch_tensor_for(model, a, w).detach().double().cpu().numpy().copy()
                    for _lk, a, w in PAIRS for _ in [0]}
        before_t = {}
        for lk, attr, isw in PAIRS:
            before_t[lk] = torch_tensor_for(model, attr, isw).detach().double().cpu().numpy().copy()
        before_emb = model.emb.detach().double().cpu().numpy().copy()
        before_stop = model.stop.detach().double().cpu().numpy().copy()

        topt = tp.make_optimizer(model, LR, WD)
        t_diag = tp.ppo_update_torch(model, games, CFG, topt, ENT, orders=orders, device="cpu")

        deltas = {}
        for lk, attr, isw in PAIRS:
            now = torch_tensor_for(model, attr, isw).detach().double().cpu().numpy()
            d = now - before_t[lk]
            deltas[lk] = d.T if isw else d          # back to legacy [fan_in,fan_out]
        deltas["trunk::emb"] = model.emb.detach().double().cpu().numpy() - before_emb
        deltas["pv::stop"] = model.stop.detach().double().cpu().numpy() - before_stop

        cos = {}
        for k, dl in delta_legacy.items():
            if k not in deltas:
                continue
            cos[k] = cosine(dl, deltas[k])
        worst = min(cos.values()) if cos else 0.0
        worst_name = min(cos, key=cos.get) if cos else None

        errs = {m: abs(float(t_diag[m]) - float(leg_diag[m]))
                for m in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_frac")}
        finite = all(np.isfinite(list(t_diag[m] for m in errs)))
        checks = {
            "policy_loss_within_1e-4": errs["policy_loss"] <= TOL,
            "value_loss_within_1e-4": errs["value_loss"] <= TOL,
            "entropy_within_1e-4": errs["entropy"] <= TOL,
            "approx_kl_within_1e-4": errs["approx_kl"] <= TOL,
            "clip_fraction_within_1e-4": errs["clip_frac"] <= TOL,
            "every_tensor_update_cosine_ge_0.999": worst >= COS_MIN,
            "no_nan_or_inf": bool(finite),
            "same_decision_count": t_diag["n_decisions"] == leg_diag["n_decisions"],
        }
        out["dtypes"][dname] = {"torch": {k: t_diag[k] for k in
                                          ("policy_loss", "value_loss", "entropy", "approx_kl",
                                           "clip_frac", "grad_norm", "explained_variance",
                                           "n_decisions")},
                                "abs_errors": errs,
                                "min_update_cosine": worst,
                                "min_cosine_tensor": worst_name,
                                "n_tensors_compared": len(cos),
                                "checks": checks, "all_pass": all(checks.values())}
    out["parity_verdict"] = "PASS" if all(v["all_pass"] for v in out["dtypes"].values()) else "FAIL"
    json.dump(out, open(os.path.join(ART, "ppo_update_parity.json"), "w"), indent=2)
    with open(os.path.join(LOGD, "ppo_update_parity.txt"), "w") as fh:
        fh.write(f"c011 AC-04 PPO fixed-batch parity — {len(games)} games, {n_dec} decisions, "
                 f"identical minibatch permutation\n")
        fh.write(f"legacy: {json.dumps({k: leg_diag[k] for k in ('policy_loss','value_loss','entropy','approx_kl','clip_frac')})}\n")
        for d, v in out["dtypes"].items():
            fh.write(f"\n[{d}] all_pass={v['all_pass']} min_cosine={v['min_update_cosine']:.9f} "
                     f"({v['min_cosine_tensor']}, {v['n_tensors_compared']} tensors)\n")
            for k, e in v["abs_errors"].items():
                fh.write(f"    |{k} error| = {e:.3e}\n")
            for k, ok in v["checks"].items():
                fh.write(f"    {'PASS' if ok else 'FAIL'} {k}\n")
    print(json.dumps({"verdict": out["parity_verdict"],
                      **{d: {"all_pass": v["all_pass"],
                             "min_cosine": v["min_update_cosine"],
                             "max_loss_err": max(v["abs_errors"].values())}
                         for d, v in out["dtypes"].items()}}, indent=2))
    return out["parity_verdict"] == "PASS"


def run_trainer_state(ckpt):
    """§10.6 — save/restore everything, then the next update must match an uninterrupted run."""
    det = tm.enable_determinism()
    games = pickle.load(open(BATCH, "rb"))
    legacy_pol = rlp.RLPolicy.load(ckpt)
    sd = legacy_pol.state_dict()
    cfgm = legacy_pol.trunk.cfg
    dt = torch.float32
    results = {}

    def fresh():
        m = tm.TorchPolicy(cfgm, dtype=dt, device="cpu").load_legacy_state(sd)
        o = tp.make_optimizer(m, LR, WD)
        return m, o

    # control: two consecutive updates, uninterrupted
    m1, o1 = fresh()
    st = ts.TrainerState(seed=611, games_done=0, updates=0)
    st.seed_all()
    orders1 = tp.precompute_order(sum(len(g) for g in games), CFG["epochs"],
                                  np.random.default_rng(11))
    tp.ppo_update_torch(m1, games, CFG, o1, ENT, orders=orders1, device="cpu")
    st.updates = 1
    orders2 = tp.precompute_order(sum(len(g) for g in games), CFG["epochs"],
                                  np.random.default_rng(12))
    ctrl = tp.ppo_update_torch(m1, games, CFG, o1, ENT, orders=orders2, device="cpu")

    # interrupted: identical first update, save, restore into a NEW process-local object, resume
    m2, o2 = fresh()
    st2 = ts.TrainerState(seed=611, games_done=0, updates=0)
    st2.seed_all()
    tp.ppo_update_torch(m2, games, CFG, o2, ENT, orders=orders1, device="cpu")
    st2.updates = 1
    st2.games_done = 448
    st2.lagged = [{"path": "x/lagged_g5000.npz", "sha256": "a" * 64}]
    st2.opponent_sampler_state = {"counts": {"dragapult": 10, "iono": 4}}
    path = os.path.join(ART, "_trainer_state_roundtrip.pt")
    st2.save(path, m2, o2, entropy_coef=ENT, lr=LR)
    pre_save_w = {k: v.detach().double().cpu().numpy().copy()
                  for k, v in m2.state_dict().items()}
    pre_save_opt = {i: {k: (v.detach().double().cpu().numpy().copy()
                            if torch.is_tensor(v) else v)
                        for k, v in st_.items()}
                    for i, st_ in o2.state_dict()["state"].items()}

    m3 = tm.TorchPolicy(cfgm, dtype=dt, device="cpu")
    o3 = tp.make_optimizer(m3, LR, WD)
    st3 = ts.TrainerState.load(path, m3, o3, device="cpu")
    post_w = {k: v.detach().double().cpu().numpy() for k, v in m3.state_dict().items()}
    roundtrip_w = max(float(np.max(np.abs(pre_save_w[k] - post_w[k]))) for k in pre_save_w)
    post_opt = {i: {k: (v.detach().double().cpu().numpy() if torch.is_tensor(v) else v)
                    for k, v in st_.items()}
                for i, st_ in o3.state_dict()["state"].items()}
    roundtrip_opt = 0.0
    for i in pre_save_opt:
        for k, v in pre_save_opt[i].items():
            if isinstance(v, np.ndarray):
                roundtrip_opt = max(roundtrip_opt,
                                    float(np.max(np.abs(v - post_opt[i][k]))))
    resumed = tp.ppo_update_torch(m3, games, CFG, o3, ENT, orders=orders2, device="cpu")

    errs = {m: abs(float(resumed[m]) - float(ctrl[m]))
            for m in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_frac")}
    w1 = {k: v.detach().double().cpu().numpy() for k, v in m1.state_dict().items()}
    w3 = {k: v.detach().double().cpu().numpy() for k, v in m3.state_dict().items()}
    max_w = max(float(np.max(np.abs(w1[k] - w3[k]))) for k in w1)

    fields = ts.TrainerState.REQUIRED_FIELDS
    saved = torch.load(path, map_location="cpu", weights_only=False)
    checks = {
        "all_required_fields_saved": all(f in saved for f in fields),
        "weights_survive_save_restore_exactly": roundtrip_w == 0.0,
        "adamw_moments_survive_save_restore_exactly": roundtrip_opt == 0.0,
        "optimizer_step_restored": st3.updates == st2.updates,
        "games_done_restored": st3.games_done == st2.games_done,
        "lagged_registry_restored": st3.lagged == st2.lagged,
        "opponent_sampler_restored": st3.opponent_sampler_state == st2.opponent_sampler_state,
        "resumed_update_matches_control": all(e <= TOL for e in errs.values()),
    }
    results = {"required_fields": list(fields), "abs_errors_vs_uninterrupted_control": errs,
               "determinism": det,
               "max_roundtrip_weight_difference": roundtrip_w,
               "max_roundtrip_adamw_moment_difference": roundtrip_opt,
               "max_weight_difference_control_vs_resumed": max_w,
               "checks": checks, "all_pass": all(checks.values()),
               "note": "The resumed update is compared against an UNINTERRUPTED control that "
                       "ran the same two updates in one process; matching within the PPO "
                       "tolerances is what makes future continuation literal rather than a "
                       "warm restart (§14)."}
    json.dump(results, open(os.path.join(ART, "trainer_state_roundtrip.json"), "w"), indent=2)
    os.remove(path)
    with open(os.path.join(LOGD, "roundtrip_tests.txt"), "a") as fh:
        fh.write("\nc011 AC-05 trainer-state round trip\n")
        for k, v in checks.items():
            fh.write(f"    {'PASS' if v else 'FAIL'} {k}\n")
        fh.write(f"    max weight diff after restore: {max_w}\n")
        fh.write(f"    resumed-vs-control errors: {json.dumps(errs)}\n")
    print(json.dumps({"trainer_state_all_pass": results["all_pass"],
                      "roundtrip_weight_diff": roundtrip_w,
                      "roundtrip_adamw_diff": roundtrip_opt,
                      "control_vs_resumed_weight_diff": max_w,
                      "errors": errs}, indent=2))
    return results["all_pass"]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--stage", default="all", choices=["parity", "state", "all"])
    a = p.parse_args(argv)
    ok = True
    if a.stage in ("parity", "all"):
        ok &= run_parity(a.checkpoint)
    if a.stage in ("state", "all"):
        ok &= run_trainer_state(a.checkpoint)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

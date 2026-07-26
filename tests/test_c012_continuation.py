"""c012 §7 — TRUE continuation test.

The protocol §7 specifies: run N updates, save, continue M; separately restore after N and
continue the same M; then verify matching opponent draws, seats, requested seeds, minibatch
permutations, losses and parameters.

Crucially this test does NOT supply precomputed minibatch orders (§7 calls such a test
insufficient). Every stochastic quantity -- opponent category, seat, per-game seed, and the
PPO permutation -- is drawn from the one active Generator, so a broken RNG restore shows up
as diverging draws rather than being masked by a pinned permutation.

The PPO update itself runs on a small frozen trajectory batch so the test is fast and
deterministic; what is under test is the RNG/state plumbing, not the simulator.
"""

import json
import os
import pickle
import sys
import tempfile
import unittest

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c011_torch_model as tm  # noqa: E402
import c011_torch_ppo as tp  # noqa: E402
import c012_ppo as cp  # noqa: E402
import c012_trainer_state as ts  # noqa: E402
import c012_train_population as trainpop  # noqa: E402

BATCH = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale", "results",
                     "artifacts", "ppo_parity_batch.pkl")
CFG = {"gamma": 0.997, "lam": 0.95, "clip": 0.20, "vf_coef": 0.50, "max_grad_norm": 0.50,
       "epochs": 2, "minibatch": 256}
MIX = {"teacher": 0.35, "mega_lucario": 0.20, "iono": 0.20, "control": 0.10, "elite": 0.15}
ELITE = [{"id": "E1", "checkpoint_path": "a.npz"}, {"id": "E2", "checkpoint_path": "b.npz"}]
TOL = 1e-6


def _fixtures():
    return pickle.load(open(BATCH, "rb"))


def _model():
    from cg import rl_policy as rlp
    ck = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale", "results",
                      "artifacts", "training", "seed611", "checkpoints", "ckpt_g5440.npz")
    pol = rlp.RLPolicy.load(ck)
    m = tm.TorchPolicy(pol.trunk.cfg, dtype=torch.float32,
                       device="cpu").load_legacy_state(pol.state_dict())
    return m, tp.make_optimizer(m, 3e-5, 1e-5)


def _step(model, opt, rng, games, n):
    """One 'training step': draw opponents/seats/seeds like the trainer, then one PPO update
    whose permutation also comes from `rng`."""
    trace = []
    for _ in range(n):
        draws = []
        for _ in range(6):
            spec, cat, oid, prob = trainpop.sample_opponent(rng, MIX, [], ELITE)
            draws.append((cat, oid, int(rng.integers(0, 2)), int(rng.integers(0, 1 << 30))))
        d = cp.ppo_update(model, games, CFG, opt, 0.004, rng, device="cpu")
        trace.append({"draws": draws, "orders": d["orders_first8"],
                      "policy_loss": d["policy_loss"], "value_loss": d["value_loss"],
                      "entropy": d["entropy"], "approx_kl": d["approx_kl"]})
    return trace


@unittest.skipUnless(os.path.exists(BATCH), "c011 parity batch unavailable")
class TrueContinuation(unittest.TestCase):
    def test_restored_run_matches_uninterrupted_run(self):
        tm.enable_determinism()
        games = _fixtures()
        N, M = 2, 2

        # --- uninterrupted: N then M ---
        m1, o1 = _model()
        r1 = ts.TrainerState.new_rng(711)
        _step(m1, o1, r1, games, N)
        control = _step(m1, o1, r1, games, M)
        w1 = {k: v.detach().double().cpu().numpy().copy() for k, v in m1.state_dict().items()}

        # --- interrupted: N, save, restore into fresh objects, then the same M ---
        m2, o2 = _model()
        r2 = ts.TrainerState.new_rng(711)
        _step(m2, o2, r2, games, N)
        st = ts.TrainerState(seed=711, completed_games=100, updates=N)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "state.pt")
            st.save(p, m2, o2, r2, 3e-5, 0.004)
            m3, o3 = _model()
            st3, r3 = ts.TrainerState.load(p, m3, o3, device="cpu")
        resumed = _step(m3, o3, r3, games, M)
        w3 = {k: v.detach().double().cpu().numpy() for k, v in m3.state_dict().items()}

        # §7's six required equalities
        self.assertEqual([t["draws"] for t in control], [t["draws"] for t in resumed],
                         "opponent draws / seats / requested seeds diverged")
        self.assertEqual([t["orders"] for t in control], [t["orders"] for t in resumed],
                         "minibatch permutations diverged")
        for a, b in zip(control, resumed):
            for k in ("policy_loss", "value_loss", "entropy", "approx_kl"):
                self.assertAlmostEqual(a[k], b[k], delta=1e-4, msg=k)
        self.assertLessEqual(max(float(np.max(np.abs(w1[k] - w3[k]))) for k in w1), TOL,
                             "parameters diverged after restore")

    def test_state_blob_contains_every_required_field(self):
        m, o = _model()
        r = ts.TrainerState.new_rng(1)
        st = ts.TrainerState(seed=1)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.pt")
            st.save(p, m, o, r, 3e-5, 0.004)
            blob = torch.load(p, map_location="cpu", weights_only=False)
        for f in ts.REQUIRED_FIELDS:
            self.assertIn(f, blob, f)
        self.assertEqual(blob["numpy_generator_type"], "PCG64")

    def test_a_broken_rng_restore_would_be_caught(self):
        """Negative control: if the Generator is NOT restored, draws must diverge -- proving
        the test has power and is not vacuously passing."""
        games = _fixtures()
        m1, o1 = _model()
        r1 = ts.TrainerState.new_rng(711)
        _step(m1, o1, r1, games, 1)
        good = _step(m1, o1, r1, games, 1)

        m2, o2 = _model()
        r2 = ts.TrainerState.new_rng(711)
        _step(m2, o2, r2, games, 1)
        r_broken = ts.TrainerState.new_rng(711)      # re-seeded, i.e. NOT restored
        bad = _step(m2, o2, r_broken, games, 1)
        self.assertNotEqual([t["draws"] for t in good], [t["draws"] for t in bad])


if __name__ == "__main__":
    unittest.main()

"""c010 AC-02: B0 and I0 are protected, load with full fidelity, and can never be silently
replaced or corrupted.

The central regression test here is the initialisation-fidelity guard: B0 is a c007 ModelV2
checkpoint, so ``RLPolicy.load`` matches none of its keys and silently leaves random weights.
Loading B0 that way would make Arm A random-initialized RL, which §4 prohibits.
"""

import hashlib
import json
import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from cg.rl_policy import RLPolicy  # noqa: E402

ART = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts")
C009_REG = os.path.join(_REPO, "contracts", "c009_amendment_c008", "results", "artifacts",
                        "candidate_checkpoint_registry.json")
IMMUTABLE_PREFIXES = tuple(f"contracts/{d}" for d in (
    "c005_teacher_import_submission_and_dataset", "c006_distilled_policy_baseline",
    "c007_hybrid_teacher_residual_and_state_encoder_v2", "c008_fixed_deck_teacher_anchored_rl",
    "c009_amendment_c008"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class IncumbentProtection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
        cls.c009 = json.load(open(C009_REG))
        cls.b0p = os.path.join(_REPO, cls.base["B0"]["checkpoint_path"])
        cls.i0p = os.path.join(_REPO, cls.base["I0"]["checkpoint_path"])

    def test_b0_and_i0_marked_protected(self):
        self.assertTrue(self.base["B0"]["protected"])
        self.assertTrue(self.base["I0"]["protected"])

    def test_hashes_match_disk(self):
        self.assertEqual(sha(self.b0p), self.base["B0"]["checkpoint_sha256"])
        self.assertEqual(sha(self.i0p), self.base["I0"]["checkpoint_sha256"])

    def test_hashes_match_c009_registry(self):
        self.assertEqual(self.base["B0"]["checkpoint_sha256"],
                         self.c009["B0_v2a"]["checkpoint_sha256"])
        self.assertEqual(self.base["I0"]["checkpoint_sha256"],
                         self.c009["R1_101"]["checkpoint_sha256"])

    def test_i0_is_the_c009_resolved_incumbent(self):
        self.assertEqual(self.base["I0"]["candidate_id"], "R1_101")
        self.assertEqual(self.base["I0"]["training_games"], 10040)

    def test_baselines_live_under_immutable_contracts(self):
        for p in (self.base["B0"]["checkpoint_path"], self.base["I0"]["checkpoint_path"]):
            self.assertTrue(p.startswith(IMMUTABLE_PREFIXES), p)

    # ---- initialisation fidelity (the guard) ----
    def test_b0_requires_init_from_v2a(self):
        raw = np.load(self.b0p)
        good = RLPolicy(seed=311); good.init_from_v2a(self.b0p)
        for k in ("sem", "ctx", "score2", "emb"):
            self.assertTrue(np.allclose(good.trunk.p[k].data, raw[k]),
                            f"init_from_v2a failed to load {k}")

    def test_rlpolicy_load_on_b0_would_silently_lose_weights(self):
        """Documents the trap: RLPolicy.load(B0) raises nothing but loads nothing."""
        raw = np.load(self.b0p)
        wrong = RLPolicy.load(self.b0p)
        mismatched = [k for k in ("sem", "ctx", "score2")
                      if not np.allclose(wrong.trunk.p[k].data, raw[k])]
        self.assertEqual(len(mismatched), 3,
                         "RLPolicy.load unexpectedly reproduced B0; the guard would be moot")

    def test_i0_loads_with_rlpolicy_load(self):
        raw = np.load(self.i0p)
        pol = RLPolicy.load(self.i0p)
        for k in ("sem", "ctx", "score2", "emb"):
            self.assertTrue(np.allclose(pol.trunk.p[k].data, raw["trunk::" + k]), k)

    def test_training_loop_dispatches_on_registry_kind(self):
        from importlib.machinery import SourceFileLoader
        m = SourceFileLoader("c010_train_loop", os.path.join(_REPO, "tools", "c010_train_loop.py")).load_module()
        polB0, how = m.load_initialization(
            {"kind": "rl_ckpt_from_v2a", "candidate_id": "B0_v2a"}, self.b0p, 311)
        self.assertIn("init_from_v2a", how)
        raw = np.load(self.b0p)
        self.assertTrue(np.allclose(polB0.trunk.p["sem"].data, raw["sem"]))
        m.verify_initialization(polB0, {"kind": "rl_ckpt_from_v2a", "candidate_id": "B0_v2a"}, self.b0p)
        polI0, how2 = m.load_initialization(
            {"kind": "rl_ckpt", "candidate_id": "R1_101"}, self.i0p, 411)
        self.assertEqual(how2, "RLPolicy.load")
        m.verify_initialization(polI0, {"kind": "rl_ckpt", "candidate_id": "R1_101"}, self.i0p)

    def test_verify_initialization_rejects_wrong_weights(self):
        from importlib.machinery import SourceFileLoader
        m = SourceFileLoader("c010_train_loop2", os.path.join(_REPO, "tools", "c010_train_loop.py")).load_module()
        bad = RLPolicy.load(self.b0p)          # the silent-no-op load
        with self.assertRaises(AssertionError):
            m.verify_initialization(bad, {"kind": "rl_ckpt_from_v2a", "candidate_id": "B0_v2a"},
                                    self.b0p)

    # ---- outputs never touch protected territory ----
    def test_training_outputs_are_written_under_c010_only(self):
        reg = json.load(open(os.path.join(ART, "experiment_registry.json")))
        self.assertIn("c010", os.path.relpath(ART, _REPO))
        for arm in reg["arms"]:
            out = os.path.join(ART, "training", f"arm_{arm}")
            self.assertFalse(os.path.relpath(out, _REPO).startswith(IMMUTABLE_PREFIXES))


if __name__ == "__main__":
    unittest.main()

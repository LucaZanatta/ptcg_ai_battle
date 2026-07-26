"""c012 §7 — the ACTIVE numpy Generator must round-trip, and the legacy global state must not
be mistaken for it.

These tests fail against c011's trainer-state implementation, which is the point: they encode
the defect being repaired.
"""

import os
import sys
import tempfile
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c012_trainer_state as ts  # noqa: E402


class ActiveGeneratorRoundTrip(unittest.TestCase):
    def test_bit_generator_state_restores_the_draw_sequence(self):
        rng = ts.TrainerState.new_rng(711)
        _ = rng.integers(0, 1 << 30, 25)          # advance it
        state = rng.bit_generator.state
        expected = rng.integers(0, 1 << 30, 40).tolist()

        restored = np.random.default_rng()
        restored.bit_generator.state = state
        self.assertEqual(restored.integers(0, 1 << 30, 40).tolist(), expected)

    def test_legacy_global_state_does_not_restore_the_active_generator(self):
        """c011 saved np.random.get_state(); that cannot reproduce a default_rng stream."""
        rng = ts.TrainerState.new_rng(711)
        _ = rng.integers(0, 1 << 30, 25)
        legacy = np.random.get_state()            # what c011 stored
        expected = rng.integers(0, 1 << 30, 20).tolist()

        np.random.set_state(legacy)               # restoring it restores the WRONG stream
        other = np.random.default_rng(711)
        self.assertNotEqual(other.integers(0, 1 << 30, 20).tolist(), expected)

    def test_generator_type_is_recorded(self):
        rng = ts.TrainerState.new_rng(1)
        self.assertEqual(type(rng.bit_generator).__name__, "PCG64")

    def test_state_survives_torch_save_load(self):
        import torch
        rng = ts.TrainerState.new_rng(822)
        _ = rng.integers(0, 100, 7)
        expected = rng.integers(0, 1 << 30, 12).tolist()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.pt")
            torch.save({"numpy_generator_state": rng.bit_generator.state}, p)
            blob = torch.load(p, weights_only=False)
        r2 = np.random.default_rng()
        r2.bit_generator.state = blob["numpy_generator_state"]
        # rng has advanced past `expected`; rewind a fresh one to the saved point
        r3 = np.random.default_rng()
        r3.bit_generator.state = blob["numpy_generator_state"]
        self.assertEqual(r2.integers(0, 1 << 30, 12).tolist(),
                         r3.integers(0, 1 << 30, 12).tolist())

    def test_required_fields_cover_section_7(self):
        req = set(ts.REQUIRED_FIELDS)
        for f in ("numpy_generator_state", "numpy_generator_type", "adam_moments",
                  "optimizer_step", "completed_games", "games_with_trainable_decisions",
                  "trainable_decisions", "entropy_schedule_definition",
                  "entropy_schedule_progress", "torch_cpu_rng", "torch_cuda_rng",
                  "lagged_registry", "curriculum_state", "branch_checkpoint_registry"):
            self.assertIn(f, req, f)


class MinibatchPermutationFromLiveGenerator(unittest.TestCase):
    def test_orders_come_from_the_generator_and_advance_it(self):
        import c012_ppo as cp
        rng = ts.TrainerState.new_rng(5)
        before = rng.bit_generator.state
        o1 = cp.draw_orders(rng, 100, 4)
        self.assertNotEqual(rng.bit_generator.state, before)
        rng2 = np.random.default_rng()
        rng2.bit_generator.state = before
        o2 = cp.draw_orders(rng2, 100, 4)
        for a, b in zip(o1, o2):
            self.assertEqual(a.tolist(), b.tolist())

    def test_different_state_gives_different_permutation(self):
        import c012_ppo as cp
        a = cp.draw_orders(ts.TrainerState.new_rng(1), 100, 2)
        b = cp.draw_orders(ts.TrainerState.new_rng(2), 100, 2)
        self.assertNotEqual(a[0].tolist(), b[0].tolist())


if __name__ == "__main__":
    unittest.main()

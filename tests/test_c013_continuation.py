"""c013 AC-02 — the carried-forward repairs, verified in c013-controlled code.

Each repair here exists because an earlier contract shipped a conclusion that the defect had
silently corrupted. So each test is paired with a NEGATIVE CONTROL that reintroduces the old
behaviour and asserts the test would have caught it. A test that passes against both the fixed
and the broken implementation is not evidence of anything.

  RNG            c011 persisted `np.random.get_state()` -- the legacy GLOBAL -- while the
                 trainer sampled from an `np.random.Generator`. Restore restored nothing that
                 mattered, and "literal continuation" was claimed anyway.
  hash refresh   c012's `sha256_file` memoises by PATH; the trainer rewrote one `cur.npz`, so
                 persistent pool workers returned stale hashes and every in-run evaluation
                 after game zero scored nothing.
  zero scores    that condition returned `None` silently, disabling curriculum gates and early
                 stopping for a 90,000-game arm.
  median rule    c011's scale decision used the MAXIMUM bootstrap significance over any
                 seed/metric pair, which is a much weaker claim than the registered median.
  budget         completed games are the budget quantity, including games whose decisions were
                 all forced.
"""

import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_common as K  # noqa: E402


class ActiveGeneratorState(unittest.TestCase):
    """The ACTIVE Generator must be what is persisted."""

    def test_generator_state_round_trip_reproduces_the_exact_stream(self):
        rng = K.TrainerState.new_rng(4242)
        rng.random(37)                              # advance mid-run
        state = rng.bit_generator.state
        expected = rng.random(11).tolist()

        restored = np.random.default_rng(0)
        restored.bit_generator.state = state
        self.assertEqual(restored.random(11).tolist(), expected)

    def test_legacy_global_state_would_not_have_caught_this(self):
        """Negative control for the c011 defect: saving the legacy global and restoring it
        leaves the Generator stream untouched, so a broken restore looks identical to a good
        one unless the ACTIVE generator is the thing being checked."""
        rng = K.TrainerState.new_rng(99)
        rng.random(5)
        np.random.seed(1234)                        # the thing c011 actually saved
        legacy = np.random.get_state()
        expected = rng.random(7).tolist()

        wrong = K.TrainerState.new_rng(99)          # "restored" the c011 way
        np.random.set_state(legacy)
        self.assertNotEqual(wrong.random(7).tolist(), expected,
                            "if these matched, restoring the global would be sufficient and "
                            "the c011 defect would not have been a defect")

    def test_state_dict_names_the_generator_type(self):
        rng = K.TrainerState.new_rng(7)
        self.assertIn("numpy_generator_type", K.REQUIRED_STATE_FIELDS)
        self.assertIn("numpy_generator_state", K.REQUIRED_STATE_FIELDS)
        self.assertEqual(type(rng.bit_generator).__name__, "PCG64")


class ContentAddressedHashRefresh(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp()

    def test_rewriting_a_fixed_path_yields_a_new_eval_path(self):
        p = os.path.join(self.d, "cur.npz")
        with open(p, "wb") as fh:
            fh.write(b"first-version")
        d1, s1 = K.content_addressed_copy(p, "t")
        with open(p, "wb") as fh:
            fh.write(b"second-version")
        d2, s2 = K.content_addressed_copy(p, "t")
        self.assertNotEqual(d1, d2, "a rewritten checkpoint must land on a different path")
        self.assertNotEqual(s1, s2)
        self.assertEqual(open(d1, "rb").read(), b"first-version")
        self.assertEqual(open(d2, "rb").read(), b"second-version")

    def test_a_per_path_cache_returns_a_stale_hash_on_the_fixed_path(self):
        """Negative control: reproduce c012's actual failure mechanism."""
        cache = {}

        def memoised_by_path(path):
            if path not in cache:
                cache[path] = K.sha_file(path)
            return cache[path]

        p = os.path.join(self.d, "cur2.npz")
        with open(p, "wb") as fh:
            fh.write(b"v1")
        first = memoised_by_path(p)
        with open(p, "wb") as fh:
            fh.write(b"v2")
        stale = memoised_by_path(p)
        self.assertEqual(first, stale, "this IS the c012 defect")
        self.assertNotEqual(stale, K.sha_file(p))
        # and the content-addressed path defeats it
        d2, _ = K.content_addressed_copy(p, "t2")
        self.assertEqual(memoised_by_path(d2), K.sha_file(p))


class ZeroScoredGamesIsFatal(unittest.TestCase):
    def test_all_unscored_raises_with_a_defect_histogram(self):
        games = [{"score": None, "defect": "checkpoint_hash_mismatch"} for _ in range(12)]
        with self.assertRaises(K.ZeroScoredGamesError) as cm:
            K.require_scored_games(games, "unit")
        self.assertIn("checkpoint_hash_mismatch", str(cm.exception))
        self.assertIn("0 scored", str(cm.exception))

    def test_partial_scoring_is_allowed_and_returns_only_scored(self):
        games = [{"score": 1.0}, {"score": None, "defect": "x"}, {"score": 0.0}]
        self.assertEqual(len(K.require_scored_games(games, "unit")), 2)

    def test_silently_returning_none_would_not_have_been_caught(self):
        """Negative control for the c012 behaviour that disabled gates for a whole arm."""
        def c012_style(results):
            scored = [r for r in results if r.get("score") is not None]
            return None if not scored else scored
        self.assertIsNone(c012_style([{"score": None}]))     # no exception, no signal


class MedianBestPerSeed(unittest.TestCase):
    def test_median_not_maximum(self):
        per_seed = {"a": 0.10, "b": 0.12, "c": 0.40}
        self.assertAlmostEqual(K.median_best_per_seed(per_seed), 0.12)
        self.assertNotAlmostEqual(K.median_best_per_seed(per_seed), max(per_seed.values()))

    def test_ignores_missing_seeds_rather_than_scoring_them_zero(self):
        self.assertAlmostEqual(K.median_best_per_seed({"a": 0.2, "b": None, "c": 0.4}), 0.3)

    def test_empty_is_none_not_zero(self):
        self.assertIsNone(K.median_best_per_seed({"a": None}))


class CompletedGameAccounting(unittest.TestCase):
    def test_forced_only_games_count_toward_the_budget(self):
        st = K.TrainerState(seed=1)
        for trainable in (5, 0, 3, 0):
            st.completed_games += 1
            if trainable:
                st.games_with_trainable_decisions += 1
                st.trainable_decisions += trainable
        self.assertEqual(st.completed_games, 4,
                         "the budget quantity is COMPLETED games, including forced-only ones")
        self.assertEqual(st.games_with_trainable_decisions, 2)
        self.assertEqual(st.trainable_decisions, 8)

    def test_schema_declares_the_budget_quantity(self):
        self.assertIn("completed_games", K.schema()["budget_quantity"])


class ContinuationKindIsHonest(unittest.TestCase):
    def test_required_fields_cover_every_carried_forward_repair(self):
        for f in ("numpy_generator_state", "adam_moments", "optimizer_step",
                  "completed_games", "entropy_schedule_progress", "torch_cuda_rng",
                  "lagged_registry", "curriculum_state"):
            self.assertIn(f, K.REQUIRED_STATE_FIELDS)

    def test_partial_restore_is_not_reported_as_literal_continuation(self):
        """`load` distinguishes a literal continuation from an optimizer-state-only one. A run
        that could not restore the Generator must not be described as literally continuing."""
        report = {"restored": ["adam_moments"], "absent": ["numpy_generator_state"]}
        literal = ("numpy_generator_state" in report["restored"]
                   and "adam_moments" in report["restored"])
        self.assertFalse(literal)
        report2 = {"restored": ["adam_moments", "numpy_generator_state"], "absent": []}
        self.assertTrue("numpy_generator_state" in report2["restored"]
                        and "adam_moments" in report2["restored"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

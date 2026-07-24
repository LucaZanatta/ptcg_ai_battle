"""AC-06 statistical analysis correctness (stdlib unittest)."""

import os
import random
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.gauntlet_stats import (
    bootstrap_ranking, bradley_terry, seat_balanced_rate, stratified_bootstrap_ci, wilson_interval,
)


class TestWilson(unittest.TestCase):
    def test_center_and_bounds(self):
        lo, hi, p = wilson_interval(5, 10)
        self.assertAlmostEqual(p, 0.5)
        self.assertTrue(0 <= lo < p < hi <= 1)

    def test_zero_n(self):
        lo, hi, p = wilson_interval(0, 0)
        self.assertEqual((lo, hi, p), (0.0, 1.0, 0.5))


class TestSeatBalanced(unittest.TestCase):
    def test_equal_weight(self):
        # seat0 win rate 0.8, seat1 win rate 0.4 -> balanced 0.6 regardless of n.
        self.assertAlmostEqual(seat_balanced_rate([1, 1, 1, 1, 0], [1, 1, 0, 0, 0]), 0.6)

    def test_draws_half(self):
        self.assertAlmostEqual(seat_balanced_rate([0.5, 0.5], [0.5, 0.5]), 0.5)


class TestBootstrapCI(unittest.TestCase):
    def test_point_and_bracket(self):
        rng = random.Random(1)
        seat0 = [1] * 8 + [0] * 2   # 0.8
        seat1 = [1] * 6 + [0] * 4   # 0.6
        lo, hi, point = stratified_bootstrap_ci(seat0, seat1, n_boot=2000, rng=rng)
        self.assertAlmostEqual(point, 0.7)
        self.assertLessEqual(lo, point)
        self.assertGreaterEqual(hi, point)

    def test_total_domination_ci_high(self):
        rng = random.Random(2)
        lo, hi, point = stratified_bootstrap_ci([1] * 20, [1] * 20, n_boot=2000, rng=rng)
        self.assertEqual(point, 1.0)
        self.assertGreater(lo, 0.55)


class TestBradleyTerry(unittest.TestCase):
    def test_finite_under_total_domination(self):
        # A beats B 20-0: without regularization strength -> inf. Must stay finite.
        cands = ["A", "B"]
        s = bradley_terry(cands, {("A", "B"): 20.0, ("B", "A"): 0.0},
                          {("A", "B"): 20.0}, pseudocount=1.0)
        self.assertTrue(all(math_isfinite(v) and v > 0 for v in s.values()))
        self.assertGreater(s["A"], s["B"])

    def test_ordering_three(self):
        cands = ["A", "B", "C"]
        pw = {("A", "B"): 15, ("B", "A"): 5, ("A", "C"): 18, ("C", "A"): 2,
              ("B", "C"): 13, ("C", "B"): 7}
        pg = {("A", "B"): 20, ("A", "C"): 20, ("B", "C"): 20}
        s = bradley_terry(cands, pw, pg)
        self.assertGreater(s["A"], s["B"])
        self.assertGreater(s["B"], s["C"])


class TestBootstrapRanking(unittest.TestCase):
    def test_frequencies_and_leader(self):
        rng = random.Random(3)
        games = ([{"a": "A", "b": "B", "a_result": 1} for _ in range(18)]
                 + [{"a": "A", "b": "B", "a_result": 0} for _ in range(2)])
        out = bootstrap_ranking(["A", "B"], games, n_boot=500, rng=rng)
        for c in ("A", "B"):
            total = sum(out[c]["rank_frequency"].values())
            self.assertAlmostEqual(total, 1.0, places=6)
        self.assertGreater(out["A"]["rank_frequency"]["1"], 0.9)


def math_isfinite(x):
    import math
    return math.isfinite(x)


if __name__ == "__main__":
    unittest.main()

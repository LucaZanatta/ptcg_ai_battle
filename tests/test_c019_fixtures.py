"""c019 numerical fixtures — M04, M05, B04, B05, B10.

These pin the semantics the live logs must later match. Each one is cheap and each one targets a
claim that is easy to assert and hard to verify from aggregate counters:

  * M04 — PUCT selection matches hand-calculated arithmetic, and `c_puct` actually changes the
    chosen child. c018's `beam_width` was configured and had no runtime effect.
  * M05 — backup updates visits and values with the correct zero-sum sign.
  * B04 — the torch V-trace path matches an independent NumPy reference.
  * B05 — UPGO matches a hand-calculated recursion and produces nonzero gradients.
  * B10 — OSFP promotion covers performance promotion, no promotion, and FORCED_MAX_LP.
"""

from __future__ import annotations

import math
import os
import sys
import unittest

import numpy as np
import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import c019_mcts as M  # noqa: E402
from cg import c019_vtrace as V  # noqa: E402


def _node(visits, value_sum, prior, key):
    n = M.MCTSNode(search_id=0, obs=None, obs_hash="h", det_id="d", memory=None)
    n.visits = visits
    n.value_sum = value_sum
    n.prior = prior
    return n


class TestPUCT(unittest.TestCase):
    """M04 — selection arithmetic and c_puct sensitivity."""

    def _parent(self):
        p = M.MCTSNode(search_id=0, obs=None, obs_hash="p", det_id="d", memory=None)
        p.visits = 25
        # child A: strong Q, weak prior, many visits | child B: weak Q, strong prior, few visits
        p.children = {("A",): _node(20, 12.0, 0.20, "A"),
                      ("B",): _node(4, 0.4, 0.70, "B")}
        return p

    def test_scores_match_hand_calculation(self):
        p = self._parent()
        c_puct = 1.5
        sqrt_n = math.sqrt(25)
        expect_a = 12.0 / 20 + c_puct * 0.20 * sqrt_n / (1 + 20)
        expect_b = 0.4 / 4 + c_puct * 0.70 * sqrt_n / (1 + 4)
        got = M.puct_scores(p, c_puct)
        self.assertAlmostEqual(got[("A",)], expect_a, places=12)
        self.assertAlmostEqual(got[("B",)], expect_b, places=12)

    def test_c_puct_changes_the_selected_child(self):
        """A configured constant that cannot change behaviour is not a real parameter."""
        p = self._parent()
        low = M.select_child(p, 0.01)
        high = M.select_child(p, 10.0)
        self.assertIs(low, p.children[("A",)])    # exploitation picks the strong Q
        self.assertIs(high, p.children[("B",)])   # exploration picks the strong prior
        self.assertIsNot(low, high)

    def test_progressive_widening_grows_with_visits_and_exposes_more_actions(self):
        p = M.MCTSNode(search_id=0, obs=None, obs_hash="p", det_id="d", memory=None)
        p.unexpanded = [None] * 10
        cfg = dict(M.DEFAULT_CFG)
        p.visits = 1
        a1 = M.allowed_children(p, cfg)
        p.visits = 100
        a100 = M.allowed_children(p, cfg)
        self.assertGreater(a100, a1)
        self.assertLessEqual(a100, p.n_legal())
        self.assertGreaterEqual(a1, 1)


class TestBackupSign(unittest.TestCase):
    """M05 — a known two-ply zero-sum fixture."""

    def test_backup_updates_visits_and_signed_values(self):
        root = M.MCTSNode(search_id=0, obs=None, obs_hash="r", det_id="d", memory=None,
                          player_sign=1, depth=0)
        child = M.MCTSNode(search_id=1, obs=None, obs_hash="c", det_id="d", memory=None,
                           parent=root, player_sign=-1, depth=1)
        root.children[("a",)] = child
        path = [root, child]
        value = 0.75
        for v in reversed(path):
            v.visits += 1
            v.value_sum += value * v.player_sign
        self.assertEqual(root.visits, 1)
        self.assertEqual(child.visits, 1)
        self.assertAlmostEqual(root.value_sum, 0.75)
        self.assertAlmostEqual(child.value_sum, -0.75)
        self.assertAlmostEqual(root.q, 0.75)
        self.assertAlmostEqual(child.q, -0.75)

    def test_repeated_backup_averages(self):
        n = M.MCTSNode(search_id=0, obs=None, obs_hash="n", det_id="d", memory=None)
        for v in (1.0, 0.0, -1.0, 0.5):
            n.visits += 1
            n.value_sum += v * n.player_sign
        self.assertEqual(n.visits, 4)
        self.assertAlmostEqual(n.q, 0.125)


class TestVTrace(unittest.TestCase):
    """B04 — torch path must equal an independent NumPy reference."""

    def _traj(self, T=6, seed=0):
        rng = np.random.default_rng(seed)
        beh = np.log(rng.uniform(0.1, 0.9, T))
        tgt = np.log(rng.uniform(0.1, 0.9, T))
        val = rng.normal(0, 0.5, T)
        rew = np.zeros(T)
        rew[-1] = 1.0                       # terminal-reward game, as in PTCG
        disc = np.full(T, V.GAMMA)
        disc[-1] = 0.0                      # no bootstrap past the terminal step
        return beh, tgt, val, rew, disc

    def test_torch_matches_numpy_reference(self):
        beh, tgt, val, rew, disc = self._traj()
        ref = V.vtrace_reference(beh, tgt, val, 0.0, rew, disc)
        t = V.vtrace_torch(*[torch.tensor(x, dtype=torch.float64)[:, None]
                             for x in (beh, tgt, val)],
                           torch.zeros(1, dtype=torch.float64),
                           torch.tensor(rew, dtype=torch.float64)[:, None],
                           torch.tensor(disc, dtype=torch.float64)[:, None])
        np.testing.assert_allclose(t["vs"][:, 0].numpy(), ref["vs"], rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(t["pg_advantage"][:, 0].numpy(), ref["pg_advantage"],
                                   rtol=1e-10, atol=1e-12)

    def test_clipping_bounds_are_the_registered_source_values(self):
        self.assertEqual((V.C_LOWER, V.C_UPPER), (0.001, 1.007))
        self.assertEqual((V.RHO_LOWER, V.RHO_UPPER), (0.001, 1.007))
        self.assertEqual(V.GAMMA, 1.0)
        self.assertEqual(V.PPO_CLIP_EPS, 0.2)

    def test_on_policy_vtrace_reduces_to_td_lambda_style_target(self):
        """With pi == mu and discount 1, rho = c = 1 and vs telescopes to the return."""
        T = 4
        lp = np.log(np.full(T, 0.5))
        val = np.zeros(T)
        rew = np.array([0.0, 0.0, 0.0, 1.0])
        disc = np.array([1.0, 1.0, 1.0, 0.0])
        ref = V.vtrace_reference(lp, lp, val, 0.0, rew, disc)
        np.testing.assert_allclose(ref["vs"], np.array([1.0, 1.0, 1.0, 1.0]), atol=1e-12)

    def test_is_not_gae(self):
        """A GAE-shaped computation would ignore importance ratios entirely."""
        beh, tgt, val, rew, disc = self._traj(seed=3)
        same = V.vtrace_reference(beh, beh, val, 0.0, rew, disc)
        diff = V.vtrace_reference(beh, tgt, val, 0.0, rew, disc)
        self.assertFalse(np.allclose(same["vs"], diff["vs"]),
                         "targets must depend on pi/mu; identical results would mean the "
                         "importance ratio is unused, i.e. this is not V-trace")


class TestUPGO(unittest.TestCase):
    """B05 — hand-calculated recursion and nonzero gradient contribution."""

    def test_matches_hand_calculation(self):
        # V = [0.0, 0.5], r = [0, 1], gamma = 1, bootstrap 0
        # t=1: q = 1 + 0*0 = 1 >= V[1]=0.5 -> G[1] = 1 + 0*0 = 1
        # t=0: q = 0 + 1*V[1] = 0.5 >= V[0]=0.0 -> G[0] = 0 + 1*G[1] = 1
        val = np.array([0.0, 0.5])
        rew = np.array([0.0, 1.0])
        disc = np.array([1.0, 0.0])
        out = V.upgo_reference(np.zeros(2), val, 0.0, rew, disc)
        np.testing.assert_allclose(out["returns"], np.array([1.0, 1.0]), atol=1e-12)
        np.testing.assert_allclose(out["advantage"], np.array([1.0, 0.5]), atol=1e-12)

    def test_torch_matches_reference(self):
        rng = np.random.default_rng(7)
        T = 5
        val = rng.normal(0, 0.4, T)
        rew = np.zeros(T)
        rew[-1] = -1.0
        disc = np.full(T, 1.0)
        disc[-1] = 0.0
        ref = V.upgo_reference(np.zeros(T), val, 0.0, rew, disc)
        t = V.upgo_torch(torch.tensor(val)[:, None], torch.zeros(1, dtype=torch.float64),
                         torch.tensor(rew)[:, None], torch.tensor(disc)[:, None])
        np.testing.assert_allclose(t["returns"][:, 0].numpy(), ref["returns"], atol=1e-12)

    def test_upgo_produces_nonzero_gradient(self):
        """METHOD_FIDELITY forbids aliasing UPGO to zero or to the V-trace loss."""
        T = 4
        beh = torch.log(torch.full((T, 1), 0.5, dtype=torch.float64))
        logits = torch.zeros(T, 1, dtype=torch.float64, requires_grad=True)
        tgt = torch.log_softmax(torch.stack([logits, -logits], dim=-1), dim=-1)[..., 0]
        val = torch.tensor([[0.0], [0.1], [0.2], [0.3]], dtype=torch.float64)
        rew = torch.tensor([[0.0], [0.0], [0.0], [1.0]], dtype=torch.float64)
        disc = torch.tensor([[1.0], [1.0], [1.0], [0.0]], dtype=torch.float64)
        ug = V.upgo_torch(val, torch.zeros(1, dtype=torch.float64), rew, disc)
        loss = V.ppo_clipped_policy_loss(tgt, beh, ug["advantage"])
        loss.backward()
        self.assertIsNotNone(logits.grad)
        self.assertGreater(float(logits.grad.abs().sum()), 0.0)

    def test_upgo_differs_from_vtrace_advantage(self):
        rng = np.random.default_rng(11)
        T = 6
        beh = np.log(rng.uniform(0.2, 0.8, T))
        tgt = np.log(rng.uniform(0.2, 0.8, T))
        val = rng.normal(0, 0.5, T)
        rew = np.zeros(T)
        rew[-1] = 1.0
        disc = np.full(T, 1.0)
        disc[-1] = 0.0
        vt = V.vtrace_reference(beh, tgt, val, 0.0, rew, disc)
        ug = V.upgo_reference(tgt, val, 0.0, rew, disc)
        self.assertFalse(np.allclose(vt["pg_advantage"], ug["advantage"]),
                         "UPGO aliased to the V-trace advantage would be a fake auxiliary loss")


class TestOSFPPromotion(unittest.TestCase):
    """B10 — performance promotion, no promotion, and FORCED_MAX_LP."""

    def setUp(self):
        from cg import c019_osfp as O
        self.O = O

    def test_performance_promotion(self):
        d = self.O.promotion_decision(G=[8.0, 9.0], C=[10, 10], xi=0.55,
                                      min_games=5, lps_without_add=0, max_lp=6)
        self.assertTrue(d["add"])
        self.assertEqual(d["reason"], "PERFORMANCE")

    def test_no_promotion_when_below_threshold(self):
        d = self.O.promotion_decision(G=[0.0, 9.0], C=[10, 10], xi=0.55,
                                      min_games=5, lps_without_add=0, max_lp=6)
        self.assertFalse(d["add"])
        self.assertEqual(d["reason"], "NO_PROMOTION")

    def test_no_promotion_when_insufficiently_sampled(self):
        """A single lucky game must not promote a checkpoint."""
        d = self.O.promotion_decision(G=[1.0], C=[1], xi=0.55, min_games=5,
                                      lps_without_add=0, max_lp=6)
        self.assertFalse(d["add"])
        self.assertEqual(d["reason"], "NO_PROMOTION")

    def test_xi_is_compared_against_a_win_rate_not_a_mean_payoff(self):
        """The discriminating case, and the one the earlier tests were too extreme to catch.

        `G/C` is a mean payoff in [-1, 1]; xi = 0.55 is a win rate. A 60% win rate is a mean
        payoff of 0.2, so comparing 0.2 against 0.55 refuses a promotion the method requires.
        Every earlier case here used |G/C| >= 0.8, where both conventions agree.
        """
        # 6 wins, 4 losses on each opponent -> win rate 0.60 > xi, mean payoff 0.20 < xi
        d = self.O.promotion_decision(G=[2.0, 2.0], C=[10, 10], xi=0.55, min_games=5,
                                      lps_without_add=0, max_lp=6)
        self.assertEqual(d["reason"], "PERFORMANCE")
        self.assertTrue(d["add"])
        self.assertAlmostEqual(d["winrates"][0], 0.60, places=9)
        self.assertAlmostEqual(d["mean_payoffs"][0], 0.20, places=9)

    def test_win_rates_are_reported_on_the_unit_interval(self):
        for G, C in ([[-10.0], [10]], [[0.0], [10]], [[10.0], [10]]):
            d = self.O.promotion_decision(G=G, C=C, xi=0.55, min_games=5,
                                          lps_without_add=0, max_lp=6)
            self.assertGreaterEqual(d["winrates"][0], 0.0)
            self.assertLessEqual(d["winrates"][0], 1.0)

    def test_a_losing_record_never_promotes_even_at_the_boundary(self):
        # win rate 0.55 exactly -- strictly-greater is required, so this must NOT promote
        d = self.O.promotion_decision(G=[1.0], C=[10], xi=0.55, min_games=5,
                                      lps_without_add=0, max_lp=6)
        self.assertAlmostEqual(d["winrates"][0], 0.55, places=9)
        self.assertEqual(d["reason"], "NO_PROMOTION")

    def test_forced_add_after_max_lp(self):
        d = self.O.promotion_decision(G=[0.0], C=[10], xi=0.55, min_games=5,
                                      lps_without_add=7, max_lp=6)
        self.assertTrue(d["add"])
        self.assertEqual(d["reason"], "FORCED_MAX_LP")

    def test_forced_add_fires_exactly_at_max_lp(self):
        """`c = 6` means at most 6 learning periods may pass without an addition.

        Off by one here is not cosmetic: it decides whether a campaign configured for N
        learning periods ever produces a second historical checkpoint at all.
        """
        at = self.O.promotion_decision(G=[0.0], C=[10], xi=0.55, min_games=5,
                                       lps_without_add=6, max_lp=6)
        self.assertEqual(at["reason"], "FORCED_MAX_LP")
        before = self.O.promotion_decision(G=[0.0], C=[10], xi=0.55, min_games=5,
                                           lps_without_add=5, max_lp=6)
        self.assertEqual(before["reason"], "NO_PROMOTION")

    def test_forced_add_is_never_labelled_performance(self):
        d = self.O.promotion_decision(G=[-9.0], C=[10], xi=0.55, min_games=5,
                                      lps_without_add=99, max_lp=6)
        self.assertEqual(d["reason"], "FORCED_MAX_LP")
        self.assertNotEqual(d["reason"], "PERFORMANCE")

    def test_empty_history_promotes_the_first_checkpoint(self):
        d = self.O.promotion_decision(G=[], C=[], xi=0.55, min_games=5,
                                      lps_without_add=0, max_lp=6)
        self.assertTrue(d["add"])
        self.assertEqual(d["reason"], "FIRST_HISTORICAL")

    def test_payoff_sampler_prefers_harder_and_less_sampled_opponents(self):
        probs = self.O.sample_probabilities(G=[9.0, -9.0], C=[10, 10])
        self.assertEqual(len(probs), 2)
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        self.assertGreater(probs[1], probs[0])   # we lose to #1 -> it is harder -> sample more
        p2 = self.O.sample_probabilities(G=[0.0, 0.0], C=[100, 2])
        self.assertGreater(p2[1], p2[0])         # less sampled -> more uncertain -> sample more


if __name__ == "__main__":
    unittest.main()

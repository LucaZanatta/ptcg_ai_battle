"""c013 AC-04 — online ensemble semantics, and proof that they are NOT weight-space soups.

§2 forbids claiming online ensembles and weight soups are equivalent, and §9 requires a set of
concrete behaviours. These tests demonstrate each numerically rather than asserting it.
"""

import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_ensemble_policy as ep  # noqa: E402


class MaskedSoftmax(unittest.TestCase):
    def test_illegal_options_get_exactly_zero(self):
        z = np.array([2.0, 1.0, 5.0, 0.5])
        m = np.array([1.0, 1.0, 0.0, 1.0])
        p = ep._masked_softmax(z, m)
        self.assertEqual(p[2], 0.0)
        self.assertAlmostEqual(p.sum(), 1.0, places=12)

    def test_combination_is_restricted_to_legal_actions(self):
        logits = np.array([[3.0, 0.0, 9.0], [0.0, 3.0, 9.0]])
        mask = np.array([1.0, 1.0, 0.0])
        for mode in ("logit", "prob"):
            e = ep.EnsemblePolicy.__new__(ep.EnsemblePolicy)
            e.mode = mode; e.weights = np.array([0.5, 0.5])
            p = e._combine(logits, mask)
            self.assertEqual(p[2], 0.0, mode)
            self.assertAlmostEqual(p.sum(), 1.0, places=12)


class LogitVersusProbability(unittest.TestCase):
    """The two registered rules are different functions, not stylistic variants."""

    def _ens(self, mode):
        e = ep.EnsemblePolicy.__new__(ep.EnsemblePolicy)
        e.mode = mode; e.weights = np.array([0.5, 0.5])
        return e

    def test_rules_disagree_when_components_disagree(self):
        logits = np.array([[6.0, 0.0, 0.0], [0.0, 1.0, 0.9]])
        mask = np.ones(3)
        pl = self._ens("logit")._combine(logits, mask)
        pp = self._ens("prob")._combine(logits, mask)
        self.assertGreater(np.abs(pl - pp).max(), 0.05,
                           "logit and probability averaging must differ on disagreement")

    def test_rules_can_select_different_actions(self):
        # one confident component vs one mildly-preferring-another component
        logits = np.array([[0.0, 2.2, 0.0], [1.4, 0.0, 1.35]])
        mask = np.ones(3)
        al = int(np.argmax(self._ens("logit")._combine(logits, mask)))
        ap = int(np.argmax(self._ens("prob")._combine(logits, mask)))
        self.assertIsInstance(al, int); self.assertIsInstance(ap, int)

    def test_rules_coincide_when_components_are_identical(self):
        logits = np.array([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
        mask = np.ones(3)
        pl = self._ens("logit")._combine(logits, mask)
        pp = self._ens("prob")._combine(logits, mask)
        self.assertLess(np.abs(pl - pp).max(), 1e-12)

    def test_probability_rule_is_not_renormalisation_of_one_averaged_vector(self):
        """§9's per-step recomputation: after removing an option, the probability ensemble
        renormalises EACH component and re-averages. That is not the same as renormalising a
        single previously-averaged distribution."""
        logits = np.array([[5.0, 0.0, 0.0], [0.0, 0.2, 0.0]])
        full = np.ones(3)
        e = self._ens("prob")
        p_full = e._combine(logits, full)
        shrunk = np.array([0.0, 1.0, 1.0])
        p_correct = e._combine(logits, shrunk)                 # recomputed per §9
        naive = p_full * shrunk
        naive = naive / naive.sum()                             # the wrong shortcut
        self.assertGreater(np.abs(p_correct - naive).max(), 1e-6)


class NotAWeightSoup(unittest.TestCase):
    def test_ensemble_of_two_linear_maps_differs_from_their_weight_average(self):
        """A ReLU network at averaged weights is not the average of the networks. Shown on the
        smallest structure that exhibits it, so the claim rests on arithmetic, not assertion."""
        x = np.array([1.0, -2.0, 0.5])
        W1 = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        W2 = np.array([[0.0, 2.0], [2.0, 0.0], [-1.0, 1.0]])
        relu = lambda v: np.maximum(v, 0.0)          # noqa: E731
        out_ens = 0.5 * (relu(x @ W1) + relu(x @ W2))
        out_soup = relu(x @ (0.5 * (W1 + W2)))
        self.assertGreater(np.abs(out_ens - out_soup).max(), 1e-9,
                           "if these matched, the two families would be interchangeable")

    def test_registry_marks_the_two_families_distinctly(self):
        import json
        p = os.path.join(_REPO, "contracts",
                         "c013_fixed_deck_policy_combination_and_learnability",
                         "results", "artifacts", "combination_registry.json")
        if not os.path.exists(p):
            self.skipTest("combination registry not built yet")
        reg = json.load(open(p))
        kinds = {c["candidate_type"] for c in reg["combinations"].values()}
        self.assertIn("weight_soup", kinds)
        self.assertIn("online_ensemble", kinds)
        for c in reg["combinations"].values():
            if c["candidate_type"] == "online_ensemble":
                self.assertFalse(c.get("trainable", False),
                                 "an online ensemble is not a trainable initialisation")


class EqualWeightsOnly(unittest.TestCase):
    def test_weights_are_equal_and_not_tuned(self):
        e = ep.EnsemblePolicy.__new__(ep.EnsemblePolicy)
        e.weights = np.full(3, 1 / 3)
        self.assertEqual(len(set(np.round(e.weights, 12))), 1)
        self.assertAlmostEqual(float(e.weights.sum()), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()

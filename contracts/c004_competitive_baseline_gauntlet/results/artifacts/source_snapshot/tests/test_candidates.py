"""Candidate registry/adapter/freeze tests (stdlib unittest)."""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.candidates import freeze_hashes, get_candidate_specs, make_agent
from cg.safe_policy import validate_selection


def _obs(n, lo, hi):
    return {"select": {"option": [{"type": 1, "index": i} for i in range(n)],
                       "minCount": lo, "maxCount": hi, "context": 0}, "logs": [], "current": None}


class TestCandidateRegistry(unittest.TestCase):
    def test_four_candidates_runnable(self):
        specs = get_candidate_specs(_REPO_ROOT)
        self.assertEqual(len(specs), 4)
        self.assertTrue(all(s["runnable"] for s in specs))
        ids = {s["candidate_id"] for s in specs}
        self.assertEqual(ids, {"det_starter", "det_cabt", "random_starter", "random_cabt"})

    def test_deterministic_pair_shares_source_differs_deck(self):
        specs = {s["candidate_id"]: s for s in get_candidate_specs(_REPO_ROOT)}
        # same agent source hash, different deck id (the material axis).
        self.assertEqual(specs["det_starter"]["adapter_source_sha256"],
                         specs["det_cabt"]["adapter_source_sha256"])
        self.assertNotEqual(specs["det_starter"]["deck"]["deck_id"],
                            specs["det_cabt"]["deck"]["deck_id"])

    def test_decks_are_60_cards(self):
        for s in get_candidate_specs(_REPO_ROOT):
            self.assertEqual(s["deck"]["card_count"], 60)


class TestAdapters(unittest.TestCase):
    def test_deterministic_returns_first_maxcount(self):
        agent = make_agent("det_starter", _REPO_ROOT)
        self.assertEqual(agent(_obs(5, 1, 2)), [0, 1])
        # deck selection returns the 60-card deck
        deck = agent({"select": None, "logs": [], "current": None})
        self.assertEqual(len(deck), 60)

    def test_random_is_legal_and_seeded(self):
        a1 = make_agent("random_starter", _REPO_ROOT, seed=42)
        a2 = make_agent("random_starter", _REPO_ROOT, seed=42)
        r1 = a1(_obs(6, 1, 2))
        r2 = a2(_obs(6, 1, 2))
        self.assertEqual(r1, r2)  # same seed -> reproducible
        self.assertTrue(validate_selection(r1, 6, 1, 2))

    def test_classify_decision_by_policy(self):
        det = make_agent("det_cabt", _REPO_ROOT)
        rnd = make_agent("random_cabt", _REPO_ROOT, seed=1)
        self.assertEqual(det.classify_decision(_obs(3, 1, 1), [0])["decision_source"], "fallback")
        self.assertEqual(rnd.classify_decision(_obs(3, 1, 1), [0])["decision_source"], "random_baseline")


class TestFreeze(unittest.TestCase):
    def test_freeze_stable(self):
        self.assertEqual(freeze_hashes(_REPO_ROOT), freeze_hashes(_REPO_ROOT))
        fh = freeze_hashes(_REPO_ROOT)
        self.assertEqual(set(fh), {"det_starter", "det_cabt", "random_starter", "random_cabt"})
        for c in fh.values():
            self.assertIsNotNone(c["deck_id"])
            self.assertIsNotNone(c["agent_source_sha256"])


if __name__ == "__main__":
    unittest.main()

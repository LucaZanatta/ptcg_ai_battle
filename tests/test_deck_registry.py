"""AC-02: canonical deck registry — order-independent identity (stdlib unittest)."""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_schema import canonical_deck


class TestCanonicalDeck(unittest.TestCase):
    def test_order_independent_same_id(self):
        a = canonical_deck([1, 1, 2, 3])
        b = canonical_deck([3, 2, 1, 1])
        self.assertEqual(a["deck_id"], b["deck_id"])
        self.assertEqual(a["cards"], b["cards"])

    def test_one_card_change_different_id(self):
        a = canonical_deck([1, 1, 2, 3])
        b = canonical_deck([1, 1, 2, 4])
        self.assertNotEqual(a["deck_id"], b["deck_id"])

    def test_duplicate_lines_aggregate(self):
        d = canonical_deck([5, 5, 5, 5, 7])
        cards = {c["card_id"]: c["count"] for c in d["cards"]}
        self.assertEqual(cards, {5: 4, 7: 1})
        self.assertEqual(d["card_count"], 5)
        self.assertEqual(d["distinct_cards"], 2)

    def test_cards_sorted_by_id(self):
        d = canonical_deck([9, 2, 5, 2])
        ids = [c["card_id"] for c in d["cards"]]
        self.assertEqual(ids, sorted(ids))

    def test_total_count_validated(self):
        d = canonical_deck([1] * 60)
        self.assertEqual(d["card_count"], 60)
        self.assertEqual(sum(c["count"] for c in d["cards"]), 60)

    def test_deck_id_format(self):
        d = canonical_deck([1, 2, 3])
        self.assertTrue(d["deck_id"].startswith("sha256:"))

    def test_source_recorded(self):
        d = canonical_deck([1, 2, 3], source_path=os.path.join(_REPO_ROOT, "starter_kit", "deck.csv"),
                            repo_root=_REPO_ROOT)
        self.assertIsNotNone(d["source"])
        self.assertEqual(d["source"]["path"], os.path.join("starter_kit", "deck.csv"))
        self.assertIsNotNone(d["source"]["sha256"])


if __name__ == "__main__":
    unittest.main()

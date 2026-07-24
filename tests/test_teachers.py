"""Teacher loader tests (stdlib unittest).

These exercise the real acquired teacher sources under the c005 results/ (which
are NOT committed); the tests skip when the sources are absent (e.g. a clean
checkout before acquisition).
"""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.safe_policy import validate_selection
from cg.teachers import (
    TEACHERS, canonical_deck_record, freeze_hashes, make_fresh, read_deck,
)

_SOURCES = os.path.join(_REPO_ROOT, "contracts", "c005_teacher_import_submission_and_dataset",
                        "results", "artifacts", "teacher_sources")


def _have_sources():
    return all(os.path.isfile(os.path.join(_SOURCES, TEACHERS[c]["dir"], "main.py")) for c in TEACHERS)


@unittest.skipUnless(_have_sources(), "teacher sources not acquired")
class TestTeacherLoader(unittest.TestCase):
    def test_all_teachers_load_and_have_60_card_decks(self):
        for cid in TEACHERS:
            deck = read_deck(cid, _SOURCES)
            self.assertEqual(len(deck), 60, cid)
        rec = {c: canonical_deck_record(c, _SOURCES, _REPO_ROOT)["deck_id"] for c in TEACHERS}
        self.assertEqual(len(set(rec.values())), len(TEACHERS), "decks must be distinct archetypes")

    def test_fresh_instance_returns_own_deck(self):
        t = make_fresh("dragapult", _SOURCES)
        deck = t({"select": None, "logs": [], "current": None})
        self.assertEqual(len(deck), 60)
        self.assertEqual(sorted(deck), sorted(read_deck("dragapult", _SOURCES)))

    def test_two_teachers_isolated(self):
        a = make_fresh("dragapult", _SOURCES)
        b = make_fresh("mega_lucario", _SOURCES)
        da = a({"select": None, "logs": [], "current": None})
        db = b({"select": None, "logs": [], "current": None})
        self.assertNotEqual(sorted(set(da)), sorted(set(db)))  # own decks, not shared

    def test_teacher_produces_legal_selection(self):
        t = make_fresh("iono", _SOURCES)
        obs = {"select": {"option": [{"type": 1, "index": i} for i in range(4)],
                          "minCount": 1, "maxCount": 1, "context": 0}, "logs": [], "current": None}
        result = t(obs)
        self.assertTrue(validate_selection(result, 4, 1, 1))

    def test_classify_decision_is_rule(self):
        t = make_fresh("mega_lucario", _SOURCES)
        self.assertEqual(t.classify_decision({}, [0])["decision_source"], "rule")

    def test_freeze_stable(self):
        self.assertEqual(freeze_hashes(_SOURCES, _REPO_ROOT), freeze_hashes(_SOURCES, _REPO_ROOT))


if __name__ == "__main__":
    unittest.main()

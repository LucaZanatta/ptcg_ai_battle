"""Standard-library unit + property-style tests for cg.safe_policy.

Run: .venv/bin/python -m unittest tests.test_safe_policy -v

Covers deterministic selection, bound validation, deck parsing, and
selector-compatibility across every real ``SelectContext`` enum member. All
imports use the ``cg`` package (symlink to ``starter_kit``) to avoid loading the
engine twice under a single interpreter.
"""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.safe_policy import (  # noqa: E402
    DECK_SIZE,
    MalformedDeck,
    MalformedSelection,
    default_deck_path,
    load_deck,
    parse_deck,
    select_for,
    select_indices,
    validate_bounds,
    validate_selection,
)
from cg.api import SelectContext  # noqa: E402


class _FakeSelect:
    """Minimal duck-typed stand-in for a cabt SelectData object."""

    def __init__(self, num_options, min_count, max_count, context=None):
        self.option = list(range(num_options))
        self.minCount = min_count
        self.maxCount = max_count
        self.context = context


class TestSelectIndices(unittest.TestCase):
    def test_zero_options_zero_counts(self):
        self.assertEqual(select_indices(0, 0, 0), [])

    def test_one_option_one_selection(self):
        self.assertEqual(select_indices(1, 1, 1), [0])

    def test_many_options_one_selection(self):
        self.assertEqual(select_indices(5, 1, 1), [0])

    def test_many_options_multi_selection(self):
        self.assertEqual(select_indices(5, 2, 3), [0, 1, 2])

    def test_min_zero_max_positive(self):
        self.assertEqual(select_indices(5, 0, 2), [0, 1])

    def test_deterministic_repeated(self):
        first = select_indices(7, 1, 4)
        for _ in range(1000):
            self.assertEqual(select_indices(7, 1, 4), first)

    def test_no_duplicates_and_in_range(self):
        # Property-style sweep over all valid (n, lo, hi) up to a small bound.
        for n in range(0, 12):
            for hi in range(0, n + 1):
                for lo in range(0, hi + 1):
                    result = select_indices(n, lo, hi)
                    self.assertEqual(len(set(result)), len(result), (n, lo, hi))
                    self.assertEqual(len(result), hi, (n, lo, hi))
                    self.assertTrue(all(0 <= i < n for i in result), (n, lo, hi))
                    # Cross-check via the independent validator.
                    self.assertTrue(validate_selection(result, n, lo, hi))

    def test_negative_counts_raise(self):
        with self.assertRaises(MalformedSelection):
            select_indices(5, -1, 2)
        with self.assertRaises(MalformedSelection):
            select_indices(5, 0, -1)
        with self.assertRaises(MalformedSelection):
            select_indices(-1, 0, 0)

    def test_min_gt_max_raises(self):
        with self.assertRaises(MalformedSelection):
            select_indices(5, 3, 2)

    def test_max_gt_options_raises(self):
        with self.assertRaises(MalformedSelection):
            select_indices(3, 1, 4)

    def test_non_integer_counts_raise(self):
        with self.assertRaises(MalformedSelection):
            select_indices(5, 1, 2.0)
        with self.assertRaises(MalformedSelection):
            select_indices(5, True, 2)  # bool rejected
        with self.assertRaises(MalformedSelection):
            select_indices("5", 1, 2)


class TestValidateBoundsAndSelection(unittest.TestCase):
    def test_validate_bounds_ok(self):
        self.assertEqual(validate_bounds(5, 1, 3), (5, 1, 3))

    def test_valid_selection_ok(self):
        self.assertTrue(validate_selection([0, 1, 2], 5, 2, 3))

    def test_duplicates_raise(self):
        with self.assertRaises(MalformedSelection):
            validate_selection([0, 0], 5, 1, 3)

    def test_out_of_range_raise(self):
        with self.assertRaises(MalformedSelection):
            validate_selection([5], 5, 1, 1)
        with self.assertRaises(MalformedSelection):
            validate_selection([-1], 5, 1, 1)

    def test_count_out_of_bounds_raise(self):
        with self.assertRaises(MalformedSelection):
            validate_selection([0, 1, 2, 3], 5, 1, 3)  # too many
        with self.assertRaises(MalformedSelection):
            validate_selection([], 5, 1, 3)  # too few

    def test_non_list_raises(self):
        with self.assertRaises(MalformedSelection):
            validate_selection((0, 1), 5, 1, 3)


class TestSelectFor(unittest.TestCase):
    def test_select_for_duck_typed(self):
        sel = _FakeSelect(num_options=5, min_count=1, max_count=2)
        self.assertEqual(select_for(sel), [0, 1])

    def test_select_for_zero(self):
        sel = _FakeSelect(num_options=0, min_count=0, max_count=0)
        self.assertEqual(select_for(sel), [])


class TestDeck(unittest.TestCase):
    def test_parse_deck_success(self):
        text = "\n".join(str(i) for i in range(DECK_SIZE))
        self.assertEqual(parse_deck(text), list(range(DECK_SIZE)))

    def test_parse_deck_ignores_blank_lines(self):
        lines = [str(i) for i in range(DECK_SIZE)]
        text = "\n\n".join(lines) + "\n\n"  # extra blank lines interspersed/trailing
        self.assertEqual(parse_deck(text), list(range(DECK_SIZE)))

    def test_parse_deck_wrong_length_raises(self):
        with self.assertRaises(MalformedDeck):
            parse_deck("\n".join(str(i) for i in range(DECK_SIZE - 1)))
        with self.assertRaises(MalformedDeck):
            parse_deck("\n".join(str(i) for i in range(DECK_SIZE + 1)))

    def test_parse_deck_malformed_id_raises(self):
        lines = [str(i) for i in range(DECK_SIZE)]
        lines[7] = "not_a_number"
        with self.assertRaises(MalformedDeck):
            parse_deck("\n".join(lines))

    def test_load_real_deck_is_valid(self):
        deck = load_deck()
        self.assertEqual(len(deck), DECK_SIZE)
        self.assertTrue(all(isinstance(c, int) for c in deck))
        # module-relative resolution (derived from __file__), and the file exists.
        dp = default_deck_path()
        self.assertTrue(dp.endswith("deck.csv"), dp)
        self.assertTrue(os.path.exists(dp), dp)


class TestSelectContextCoverage(unittest.TestCase):
    """AC-02: every real SelectContext enum member is selector-compatible.

    Proves that context identity never alters or breaks deterministic legal
    index generation for valid synthetic bounds. This is enum-level selector
    coverage, NOT runtime-observed context coverage.
    """

    def test_all_contexts_compatible(self):
        members = list(SelectContext)
        self.assertGreaterEqual(len(members), 49)
        n, lo, hi = 4, 1, 2
        context_free = select_indices(n, lo, hi)
        covered = 0
        for ctx in members:
            sel = _FakeSelect(num_options=n, min_count=lo, max_count=hi, context=ctx)
            result = select_for(sel)
            self.assertEqual(result, context_free, f"context {ctx.name} altered selection")
            self.assertTrue(validate_selection(result, n, lo, hi), ctx.name)
            covered += 1
        # No file writes (c002 §5.4: side-effect-free unit tests).
        self.assertEqual(covered, len(members))


if __name__ == "__main__":
    unittest.main()

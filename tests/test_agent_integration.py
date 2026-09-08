"""Entrypoint / deck / harness integration tests for the safe agent.

Run: .venv/bin/python -m unittest tests.test_agent_integration -v

Does not run a large benchmark; the smoke test plays a single game per seat.
All imports use the ``cg`` package (symlink to ``starter_kit``).
"""

import os
import random
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.main import agent  # noqa: E402
from cg.safe_policy import DECK_SIZE, MalformedDeck, load_deck  # noqa: E402

# Minimal deck-selection observation (select is None during deck selection).
_DECK_SELECT_OBS = {"select": None, "logs": [], "current": None}


def _write_temp_deck(text):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


class TestDeckSelection(unittest.TestCase):
    def test_deck_selection_deterministic_60(self):
        first = agent(dict(_DECK_SELECT_OBS))
        second = agent(dict(_DECK_SELECT_OBS))
        self.assertEqual(len(first), DECK_SIZE)
        self.assertTrue(all(isinstance(c, int) for c in first))
        self.assertEqual(first, second, "deck selection must be deterministic")

    def test_invalid_deck_length_rejected(self):
        path = _write_temp_deck("\n".join(str(i) for i in range(DECK_SIZE - 1)))
        try:
            with self.assertRaises(MalformedDeck):
                load_deck(path)
        finally:
            os.unlink(path)

    def test_malformed_card_id_rejected(self):
        lines = [str(i) for i in range(DECK_SIZE)]
        lines[3] = "not_an_int"
        path = _write_temp_deck("\n".join(lines))
        try:
            with self.assertRaises(MalformedDeck):
                load_deck(path)
        finally:
            os.unlink(path)

    def test_deck_validation_summary(self):
        """Deck determinism + rejection, assertions only (c002 §5.4: no file writes)."""
        deck = agent(dict(_DECK_SELECT_OBS))
        repeat = agent(dict(_DECK_SELECT_OBS))
        self.assertEqual(len(deck), DECK_SIZE)
        self.assertTrue(all(isinstance(c, int) for c in deck))
        self.assertEqual(deck, repeat)

        bad_len = _write_temp_deck("\n".join(str(i) for i in range(DECK_SIZE - 1)))
        bad_id_lines = [str(i) for i in range(DECK_SIZE)]
        bad_id_lines[3] = "not_an_int"
        bad_id = _write_temp_deck("\n".join(bad_id_lines))
        try:
            with self.assertRaises(MalformedDeck):
                load_deck(bad_len)
            with self.assertRaises(MalformedDeck):
                load_deck(bad_id)
        finally:
            os.unlink(bad_len)
            os.unlink(bad_id)


class TestHarnessSmoke(unittest.TestCase):
    """AC-07: the entrypoint runs through the verified cabt harness in both seats."""

    def test_agent_runs_as_both_players(self):
        from kaggle_environments import make

        deck = load_deck()
        rng = random.Random(20240101)

        def random_opponent(obs):
            select = obs["select"]
            if select is None:
                return deck
            return rng.sample(range(len(select["option"])), select["maxCount"])

        for seat in (0, 1):
            env = make("cabt", configuration={"decks": [deck, deck]})
            players = [agent, random_opponent] if seat == 0 else [random_opponent, agent]
            env.run(players)
            last = env.steps[-1]
            self.assertEqual(last[0]["status"], "DONE", f"seat={seat}: player0 not DONE")
            self.assertEqual(last[1]["status"], "DONE", f"seat={seat}: player1 not DONE")


if __name__ == "__main__":
    unittest.main()

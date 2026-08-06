"""AC-06: terminal classification from FINAL state (stdlib unittest, synthetic)."""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_schema import classify_terminal


class TestTerminalClassification(unittest.TestCase):
    def test_normal_win_seat0(self):
        t = classify_terminal(["DONE", "DONE"], [1, -1])
        self.assertEqual(t["terminal_type"], "normal_win")
        self.assertEqual(t["winner"], 0)
        self.assertEqual(t["loser"], 1)
        self.assertFalse(t["draw"])

    def test_normal_win_seat1(self):
        t = classify_terminal(["DONE", "DONE"], [-1, 1])
        self.assertEqual(t["terminal_type"], "normal_win")
        self.assertEqual(t["winner"], 1)

    def test_draw(self):
        t = classify_terminal(["DONE", "DONE"], [0, 0])
        self.assertEqual(t["terminal_type"], "draw")
        self.assertTrue(t["draw"])
        self.assertIsNone(t["winner"])

    def test_agent_error_from_invalid(self):
        t = classify_terminal(["INVALID", "DONE"], [-1, 1], error="Player 0 illegal selection")
        self.assertEqual(t["terminal_type"], "agent_error")
        self.assertEqual(t["error_player"], 0)
        self.assertEqual(t["error"], "Player 0 illegal selection")

    def test_agent_error_from_error_status(self):
        t = classify_terminal(["DONE", "ERROR"], [1, -1])
        self.assertEqual(t["terminal_type"], "agent_error")
        self.assertEqual(t["error_player"], 1)

    def test_timeout(self):
        t = classify_terminal(["TIMEOUT", "DONE"], [-1, 1])
        self.assertEqual(t["terminal_type"], "timeout")
        self.assertEqual(t["timeout_player"], 0)

    def test_environment_error_from_exception(self):
        t = classify_terminal(["ERROR", "ERROR"], [None, None], exception="RuntimeError(boom)")
        self.assertEqual(t["terminal_type"], "environment_error")
        self.assertEqual(t["error"], "RuntimeError(boom)")

    def test_unknown_when_not_terminal(self):
        t = classify_terminal(["ACTIVE", "INACTIVE"], [None, None])
        self.assertEqual(t["terminal_type"], "unknown")


if __name__ == "__main__":
    unittest.main()

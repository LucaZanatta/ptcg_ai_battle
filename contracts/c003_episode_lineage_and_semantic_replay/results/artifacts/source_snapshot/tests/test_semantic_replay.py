"""AC-04: true semantic replay + cross-field validation (stdlib unittest).

Uses synthetic schema-v2 records: the validator reconstructs each safe-agent
observation via to_observation_class and invokes the real safe agent, comparing
to the recorded action. Corrupt fixtures prove cross-field checks fail.
"""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import tools.validate_episodes_v2 as v2
from tests._v2_helpers import (
    decision_record, game_start_record, run_metadata_record, terminal_record,
)


def _write(records, path):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _dataset(decision, decisions_by_player=None):
    return [
        run_metadata_record(),
        game_start_record(),
        decision,
        terminal_record(decisions_by_player=decisions_by_player or {"0": 1}),
    ]


class TestSemanticReplay(unittest.TestCase):
    def test_safe_decision_reproduces(self):
        # selected = list(range(maxCount)) -> the safe agent must reproduce it.
        dec = decision_record(4, 1, 2, 0, [0, 1])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertTrue(res["ok"], res["validation"]["errors"])
            sem = res["semantic"]
            self.assertEqual(sem["safe_decisions_checked"], 1)
            self.assertEqual(sem["convert_ok"], 1)
            self.assertEqual(sem["matches"], 1)
            self.assertTrue(sem["all_reproduced"])

    def test_replay_mismatch_detected(self):
        # Recorded action disagrees with what the safe agent would produce.
        dec = decision_record(4, 1, 2, 0, [2, 3])  # safe agent would return [0,1]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertFalse(res["ok"])
            self.assertGreaterEqual(res["semantic"]["mismatch_count"], 1)

    def test_cross_field_context_mismatch(self):
        dec = decision_record(4, 1, 2, 0, [0, 1], corrupt={"select_context": 999})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertFalse(res["ok"])
            self.assertTrue(any("select_context" in e["message"]
                                for e in res["validation"]["errors"]))

    def test_cross_field_bounds_mismatch(self):
        dec = decision_record(4, 1, 2, 0, [0, 1], corrupt={"max_count": 99})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertFalse(res["ok"])
            self.assertTrue(any("min/max_count" in e["message"]
                                for e in res["validation"]["errors"]))

    def test_out_of_range_selected_index(self):
        dec = decision_record(4, 1, 1, 0, [7], corrupt={"legal_option_count": 4})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertFalse(res["ok"])
            self.assertTrue(any("out of range" in e["message"]
                                for e in res["validation"]["errors"]))

    def test_duplicate_record_id_detected(self):
        dec = decision_record(4, 1, 2, 0, [0, 1], seq=1)  # collides with game_start seq=1
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            _write(_dataset(dec), path)
            res = v2.validate(path)
            self.assertFalse(res["ok"])
            self.assertTrue(any("duplicate record_id" in e["message"]
                                for e in res["validation"]["errors"]))


if __name__ == "__main__":
    unittest.main()

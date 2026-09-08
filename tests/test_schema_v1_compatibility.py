"""AC-07: schema-v1 compatibility without invented provenance (stdlib unittest)."""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_compat import (
    LEGACY_UNAVAILABLE, UnsupportedSchemaVersion, legacy_availability, read_records,
    summarize_file,
)

_C002 = os.path.join(_REPO_ROOT, "contracts", "c002_reproducible_episode_capture",
                     "results", "artifacts", "episodes", "episodes.jsonl")


def _v1_fixture():
    """Minimal schema-v1 records shaped like c002 output."""
    return [
        {"schema_version": 1, "record_type": "game_start", "game_id": "g", "game_seed": 123,
         "cohort": "c", "agents_by_seat": {"0": "safe_agent"}, "decks_by_seat": {"0": "deck60_x"}},
        {"schema_version": 1, "record_type": "decision", "game_id": "g", "decision_index": 0,
         "player_index": 0, "seat": 0, "game_seed": 123, "agent_name": "safe_agent",
         "deck_identifier": "deck60_x", "timestamp_monotonic_ns": 1, "observation": {"select": None},
         "context_name": "MAIN", "context_value": 0, "legal_option_count": 1, "min_count": 1,
         "max_count": 1, "selected_indices": [0], "policy_latency_ns": 5, "used_fallback": True,
         "validation_status": "valid"},
        {"schema_version": 1, "record_type": "game_terminal", "game_id": "g", "game_seed": 123,
         "winner": 0, "decisions_by_player": {"0": 1}},
    ]


class TestSchemaV1Compatibility(unittest.TestCase):
    def _write(self, records, path):
        with open(path, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")

    def test_reads_v1_fixture_as_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "v1.jsonl")
            self._write(_v1_fixture(), path)
            summ = summarize_file(path)
            self.assertEqual(summ["detected_schema"], 1)
            self.assertGreater(len(summ["v2_only_fields_legacy_unavailable"]), 0)
            # v2-only provenance is marked unavailable, not invented.
            self.assertIn("decision_source", summ["v2_only_fields_legacy_unavailable"])

    def test_legacy_availability_marks_missing_fields(self):
        v1_decision = _v1_fixture()[1]
        avail = legacy_availability(v1_decision)
        self.assertEqual(avail.get("decision_source"), LEGACY_UNAVAILABLE)
        self.assertEqual(avail.get("run_id"), LEGACY_UNAVAILABLE)
        # v1 used_fallback exists but is surfaced as untrusted (identity-based).
        self.assertEqual(avail.get("used_fallback"), "legacy_present_untrusted")

    def test_unsupported_version_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "future.jsonl")
            self._write([{"schema_version": 99, "record_type": "decision"}], path)
            with self.assertRaises(UnsupportedSchemaVersion):
                list(read_records(path))

    def test_real_c002_file_detected_as_v1_if_present(self):
        if not os.path.isfile(_C002):
            self.skipTest("c002 v1 dataset not present")
        # Only read the head to stay fast; detection is per-record.
        n = 0
        for _ln, ver, _rec in read_records(_C002):
            self.assertEqual(ver, 1)
            n += 1
            if n >= 50:
                break
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()

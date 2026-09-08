"""Tests for versioned episode capture, serialization, and validation (stdlib).

Run: .venv/bin/python -m unittest tests.test_episode_capture -v

Covers §8 categories 5-13: seed derivation, decision/terminal serialization,
JSONL round-trip, malformed-JSON detection, out-of-bounds detection, ordering
detection, no writes to historical contract folders, and unchanged safe behavior.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_capture import (  # noqa: E402
    GameRecorder, JsonlWriter, SCHEMA_VERSION, derive_seed, deck_identifier,
    make_capturing_agent, normalize_observation,
)
from cg.safe_policy import select_indices  # noqa: E402
from cg.main import agent as safe_agent  # noqa: E402
import tools.validate_episode_jsonl as vej  # noqa: E402


def _decision_obs(num_options, min_count, max_count, context):
    return {
        "select": {
            "option": [{"type": 1, "index": i} for i in range(num_options)],
            "minCount": min_count, "maxCount": max_count, "context": context,
        },
        "logs": [], "current": None,
    }


class TestSeedDerivation(unittest.TestCase):
    def test_stable_and_distinct(self):
        self.assertEqual(derive_seed(777, 3), derive_seed(777, 3))
        self.assertNotEqual(derive_seed(777, 3), derive_seed(777, 4))
        self.assertNotEqual(derive_seed(1, 0), derive_seed(2, 0))
        seeds = [derive_seed(777, i) for i in range(60)]
        self.assertEqual(len(set(seeds)), 60, "seeds must be unique across games")
        self.assertTrue(all(0 <= s < 2 ** 63 for s in seeds))


class TestNormalizeObservation(unittest.TestCase):
    def test_json_safe_and_records_omitted(self):
        norm, omitted = normalize_observation({"a": 1, "b": {"c": [1, 2, 3]}, "d": {1, 2}})
        json.dumps(norm)  # must not raise
        self.assertIn("obs.d", omitted)
        self.assertEqual(norm["b"]["c"], [1, 2, 3])
        self.assertIsNone(norm["d"])


class TestSerialization(unittest.TestCase):
    def _capture_one_game(self, path):
        writer = JsonlWriter(path)
        rec = GameRecorder(writer, game_id="g0", cohort="unit", game_seed=derive_seed(5, 0),
                           safe_seat=0, agents_by_seat={0: "safe_agent", 1: "safe_agent"},
                           decks_by_seat={0: "deckX", 1: "deckX"})
        rec.write_start()
        obs = _decision_obs(3, 1, 2, context=8)  # DISCARD
        rec.record_decision(agent_name="safe_agent", player_index=0, seat=0, is_safe_agent=True,
                            obs=obs, result=select_indices(3, 1, 2), latency_ns=1234, decision_ts_ns=999)
        rec.record_decision(agent_name="safe_agent", player_index=1, seat=1, is_safe_agent=True,
                            obs=_decision_obs(2, 1, 1, context=0), result=[0],
                            latency_ns=99, decision_ts_ns=1000)
        rec.write_terminal(winner=0, terminal_reason="normal", duration_s=0.01,
                           error_status=None, statuses=["DONE", "DONE"], rewards=[1, -1])
        writer.close()
        return rec

    def test_decision_and_terminal_serialization(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "g.jsonl")
            self._capture_one_game(path)
            records = [json.loads(l) for l in open(path, encoding="utf-8")]
            self.assertEqual(records[0]["record_type"], "game_start")
            dec = records[1]
            self.assertEqual(dec["record_type"], "decision")
            self.assertEqual(dec["schema_version"], SCHEMA_VERSION)
            self.assertEqual(dec["selected_indices"], [0, 1])
            self.assertEqual(dec["context_name"], "DISCARD")
            self.assertEqual(dec["min_count"], 1)
            self.assertEqual(dec["max_count"], 2)
            self.assertTrue(dec["used_fallback"])
            self.assertEqual(dec["validation_status"], "valid")
            term = records[-1]
            self.assertEqual(term["record_type"], "game_terminal")
            self.assertEqual(term["decisions_by_player"], {"0": 1, "1": 1})
            self.assertEqual(term["invalid_selection_count"], 0)
            self.assertEqual(term["winner"], 0)

    def test_jsonl_roundtrip_valid(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "g.jsonl")
            self._capture_one_game(path)
            result = vej.validate_stream(path)
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["games"], 1)
            self.assertEqual(result["decisions"], 2)


class TestValidatorDetection(unittest.TestCase):
    def test_malformed_json_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{ not valid json\n')
            result = vej.validate_stream(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("malformed JSON" in e["message"] for e in result["errors"]))

    def test_out_of_bounds_index_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "oob.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                start = {"schema_version": 1, "record_type": "game_start", "game_id": "g",
                         "cohort": "u", "game_seed": 1, "agents_by_seat": {}, "decks_by_seat": {}}
                dec = {"schema_version": 1, "record_type": "decision", "game_id": "g",
                       "decision_index": 0, "player_index": 0, "seat": 0, "game_seed": 1,
                       "agent_name": "safe_agent", "context_name": "MAIN", "context_value": 0,
                       "legal_option_count": 3, "min_count": 1, "max_count": 1,
                       "selected_indices": [5], "policy_latency_ns": 1, "used_fallback": False,
                       "validation_status": "valid", "observation": {}}
                fh.write(json.dumps(start) + "\n" + json.dumps(dec) + "\n")
            result = vej.validate_stream(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("out of range" in e["message"] for e in result["errors"]))

    def test_inconsistent_ordering_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "ord.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                start = {"schema_version": 1, "record_type": "game_start", "game_id": "g",
                         "cohort": "u", "game_seed": 1, "agents_by_seat": {}, "decks_by_seat": {}}
                dec = {"schema_version": 1, "record_type": "decision", "game_id": "g",
                       "decision_index": 3, "player_index": 0, "seat": 0, "game_seed": 1,
                       "agent_name": "safe_agent", "context_name": "MAIN", "context_value": 0,
                       "legal_option_count": 3, "min_count": 1, "max_count": 1,
                       "selected_indices": [0], "policy_latency_ns": 1, "used_fallback": True,
                       "validation_status": "valid", "observation": {}}
                fh.write(json.dumps(start) + "\n" + json.dumps(dec) + "\n")
            result = vej.validate_stream(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("decision_index" in e["message"] for e in result["errors"]))


def _hash_tree(root):
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            fp = os.path.join(dirpath, f)
            with open(fp, "rb") as fh:
                out[os.path.relpath(fp, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


class TestNoContractResultWrites(unittest.TestCase):
    def test_capture_does_not_touch_historical_results(self):
        targets = [os.path.join(_REPO_ROOT, "contracts", c, "results")
                   for c in ("c000_repository_audit_and_baseline",
                             "c001_deterministic_safe_agent_core")]
        targets = [t for t in targets if os.path.isdir(t)]
        before = {t: _hash_tree(t) for t in targets}
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cap.jsonl")
            writer = JsonlWriter(path)
            rec = GameRecorder(writer, game_id="g", cohort="u", game_seed=1, safe_seat=0,
                               agents_by_seat={0: "safe_agent", 1: "safe_agent"},
                               decks_by_seat={0: "d", 1: "d"})
            rec.write_start()
            rec.record_decision(agent_name="safe_agent", player_index=0, seat=0,
                                is_safe_agent=True, obs=_decision_obs(3, 1, 1, 0),
                                result=[0], latency_ns=1, decision_ts_ns=1)
            rec.write_terminal(winner=0, terminal_reason="normal", duration_s=0.0,
                               error_status=None, statuses=["DONE", "DONE"], rewards=[1, -1])
            writer.close()
        after = {t: _hash_tree(t) for t in targets}
        self.assertEqual(before, after, "capture must not modify c000/c001 results")


class TestSafeBehaviorUnchanged(unittest.TestCase):
    def test_selector_deterministic(self):
        self.assertEqual(select_indices(5, 1, 2), [0, 1])
        self.assertEqual(select_indices(5, 1, 2), select_indices(5, 1, 2))
        self.assertEqual(select_indices(0, 0, 0), [])

    def test_deck_selection_deterministic(self):
        obs = {"select": None, "logs": [], "current": None}
        first = safe_agent(obs)
        second = safe_agent(obs)
        self.assertEqual(len(first), 60)
        self.assertEqual(first, second)

    def test_capturing_agent_preserves_result(self):
        # The capture wrapper must return the inner agent's result unchanged.
        with tempfile.TemporaryDirectory() as td:
            writer = JsonlWriter(os.path.join(td, "w.jsonl"))
            rec = GameRecorder(writer, game_id="g", cohort="u", game_seed=1, safe_seat=0,
                               agents_by_seat={0: "x", 1: "y"}, decks_by_seat={0: "d", 1: "d"})
            rec.write_start()
            sentinel = _decision_obs(4, 1, 3, 0)
            inner_called = {}

            def inner(obs):
                inner_called["result"] = [0, 1, 2]
                return [0, 1, 2]

            wrapped = make_capturing_agent(rec, inner, agent_name="x", player_index=0,
                                           seat=0, is_safe_agent=True)
            self.assertEqual(wrapped(sentinel), [0, 1, 2])
            writer.close()


if __name__ == "__main__":
    unittest.main()

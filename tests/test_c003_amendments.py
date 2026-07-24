"""AC-01: c004 Phase-0 amendments to the c003 platform (stdlib unittest).

1. final_state_terminal — terminal error extraction from the FINAL step.
2. legal_option_metadata equality with observation.select.option.
3. replay registry — verify agent identity/version/source hashes before invoking.
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
from cg.episode_schema import final_state_terminal
from cg.replay_registry import (
    HASH_MISMATCH, OK, STOCHASTIC, UNREGISTERED, build_registry, resolve,
)
from tests._v2_helpers import (
    decision_record, game_start_record, run_metadata_record, terminal_record, test_registry,
)


class _FakeEnv:
    def __init__(self, steps):
        self.steps = steps


class TestFinalStateTerminal(unittest.TestCase):
    def test_reads_final_step_not_first(self):
        env = _FakeEnv([
            [{"status": "ACTIVE", "error": "stale-step0"}, {"status": "ACTIVE"}],
            [{"status": "DONE", "reward": 1}, {"status": "INVALID", "reward": -1}],
        ])
        statuses, rewards, error = final_state_terminal(env)
        self.assertEqual(statuses, ["DONE", "INVALID"])
        self.assertEqual(rewards, [1, -1])

    def test_step0_error_surfaced_only_when_final_state_errored(self):
        # Final state IS an error -> the step-0 deck error text is surfaced.
        env = _FakeEnv([
            [{"status": "ACTIVE", "error": "Player 1's deck does not have 60 cards."}, {"status": "ACTIVE"}],
            [{"status": "DONE", "reward": 1}, {"status": "INVALID", "reward": -1}],
        ])
        _s, _r, error = final_state_terminal(env)
        self.assertEqual(error, "Player 1's deck does not have 60 cards.")

    def test_step0_error_not_surfaced_on_clean_win(self):
        # The defect being fixed: a stale step-0 error must NOT leak into a clean DONE/DONE terminal.
        env = _FakeEnv([
            [{"status": "ACTIVE", "error": "stale first-step error"}, {"status": "ACTIVE"}],
            [{"status": "DONE", "reward": 1}, {"status": "DONE", "reward": -1}],
        ])
        _s, _r, error = final_state_terminal(env)
        self.assertIsNone(error)


class TestLegalOptionMetadataEquality(unittest.TestCase):
    def test_mismatch_detected(self):
        reg = test_registry()
        dec = decision_record(4, 1, 2, 0, [0, 1],
                              corrupt={"legal_option_metadata": [{"type": 9, "index": 99}]})
        recs = [run_metadata_record(), game_start_record(), dec,
                terminal_record(decisions_by_player={"0": 1})]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
            res = v2.validate(path, registry=reg)
            self.assertFalse(res["ok"])
            self.assertTrue(any("legal_option_metadata !=" in e["message"]
                                for e in res["validation"]["errors"]))


class TestReplayRegistry(unittest.TestCase):
    def test_resolve_ok_on_matching_lineage(self):
        reg = build_registry(_REPO_ROOT)
        from cg.agents import safe_agent_definition
        recorded = safe_agent_definition(_REPO_ROOT).lineage()
        status, fn = resolve(reg, "safe_agent", recorded)
        self.assertEqual(status, OK)
        self.assertIsNotNone(fn)

    def test_resolve_hash_mismatch(self):
        reg = build_registry(_REPO_ROOT)
        bad = {"agent_version": "c001.1", "source_files": [{"path": "starter_kit/main.py", "sha256": "WRONG"}]}
        status, fn = resolve(reg, "safe_agent", bad)
        self.assertEqual(status, HASH_MISMATCH)
        self.assertIsNone(fn)

    def test_resolve_version_mismatch(self):
        reg = build_registry(_REPO_ROOT)
        from cg.agents import safe_agent_definition
        rec = safe_agent_definition(_REPO_ROOT).lineage()
        rec = dict(rec, agent_version="different")
        status, _ = resolve(reg, "safe_agent", rec)
        self.assertEqual(status, HASH_MISMATCH)

    def test_resolve_stochastic(self):
        reg = build_registry(_REPO_ROOT)
        status, fn = resolve(reg, "random_baseline", {"agent_version": "c002.1", "source_files": []})
        self.assertEqual(status, STOCHASTIC)
        self.assertIsNone(fn)

    def test_resolve_unregistered(self):
        reg = build_registry(_REPO_ROOT)
        status, _ = resolve(reg, "mystery_agent", {"agent_version": "x", "source_files": []})
        self.assertEqual(status, UNREGISTERED)

    def test_validator_marks_unavailable_on_mismatch(self):
        # Synthetic records use fake hashes; the DEFAULT registry has real hashes,
        # so replay must be marked unavailable (not invoked, not a mismatch/pass).
        recs = [run_metadata_record(), game_start_record(),
                decision_record(4, 1, 2, 0, [0, 1]),
                terminal_record(decisions_by_player={"0": 1})]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for r in recs:
                    fh.write(json.dumps(r) + "\n")
            res = v2.validate(path)  # default registry -> hash mismatch
            self.assertEqual(res["semantic"]["safe_decisions_checked"], 0)
            self.assertGreaterEqual(res["semantic"]["replay_unavailable"], 1)


if __name__ == "__main__":
    unittest.main()

"""AC-03: honest seed + decision provenance (stdlib unittest)."""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.agents import random_baseline_definition, safe_agent_definition
from cg.episode_capture_v2 import GameRecorderV2, RunWriter
from tests._v2_helpers import decision_obs


class TestDecisionSourceIsPolicyProperty(unittest.TestCase):
    def test_safe_agent_source_same_in_both_seats(self):
        safe = safe_agent_definition(_REPO_ROOT)
        obs = decision_obs(3, 1, 1, 0)
        for seat in (0, 1):
            prov = safe.classify_decision(obs, [0])
            self.assertEqual(prov["decision_source"], "fallback")
            self.assertTrue(prov["used_fallback"])
            self.assertEqual(prov["fallback_reason"], "no_strategy_policy_configured")

    def test_random_baseline_source_same_in_both_seats(self):
        rnd = random_baseline_definition(_REPO_ROOT, seed=1, deck=[1] * 60)
        obs = decision_obs(3, 1, 1, 0)
        for seat in (0, 1):
            prov = rnd.classify_decision(obs, [0])
            self.assertEqual(prov["decision_source"], "random_baseline")
            self.assertFalse(prov["used_fallback"])
            self.assertIsNone(prov["fallback_reason"])


class TestCapturedRecordsProvenance(unittest.TestCase):
    def _capture(self, path):
        writer = RunWriter(path)
        safe = safe_agent_definition(_REPO_ROOT)
        rec = GameRecorderV2(
            writer, run_id="run_x", game_id="g0", cohort="unit",
            seat_agent_ids={0: "safe_agent", 1: "safe_agent"},
            seat_deck_ids={0: "sha256:d", 1: "sha256:d"},
            seed_meta={"runner_seed": 1, "opponent_policy_seed": 2, "requested_engine_seed": 1,
                       "engine_rng_controlled": False, "engine_rng_note": "n"},
            seq=[0])
        rec.write_game_start()
        rec.record_decision(player_index=0, seat=0, agent_def=safe,
                            obs_snapshot=decision_obs(3, 1, 1, 0), result=[0],
                            latency_ns=1, ts_ns=1)
        rec.write_terminal(statuses=["DONE", "DONE"], rewards=[1, -1], error=None,
                           exception=None, duration_s=0.0)
        writer.close()

    def test_no_game_seed_and_provenance_present(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            self._capture(path)
            recs = [json.loads(l) for l in open(path, encoding="utf-8")]
            for r in recs:
                self.assertNotIn("game_seed", r, f"{r['record_type']} leaked game_seed")
            gs = next(r for r in recs if r["record_type"] == "game_start")
            self.assertFalse(gs["seed"]["engine_rng_controlled"])
            for k in ("runner_seed", "opponent_policy_seed", "requested_engine_seed"):
                self.assertIn(k, gs["seed"])
            dec = next(r for r in recs if r["record_type"] == "decision")
            for k in ("decision_source", "used_fallback", "fallback_reason"):
                self.assertIn(k, dec)
            self.assertEqual(dec["decision_source"], "fallback")


if __name__ == "__main__":
    unittest.main()

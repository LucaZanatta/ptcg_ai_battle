"""AC-05: mutation-safe observation snapshot (stdlib unittest).

A deliberately mutating fake policy must not be able to change the recorded
observation, because the snapshot is taken (deep) BEFORE the policy is invoked.
"""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.agents import AgentDefinition
from cg.episode_capture_v2 import GameRecorderV2, RunWriter, make_capturing_agent
from tests._v2_helpers import decision_obs


class _MutatingAgent(AgentDefinition):
    """Fake policy that mutates a NESTED field of its input before returning."""

    def __init__(self):
        super().__init__(agent_id="mutator", agent_version="0", policy_type="test",
                         source_paths=[], configuration={}, policy=self._policy_fn,
                         repo_root=_REPO_ROOT)

    def _policy_fn(self, obs):
        obs["select"]["option"][0]["MUTATED"] = True  # nested mutation
        obs["select"]["maxCount"] = 999                # top-level mutation
        return [0]

    def classify_decision(self, obs, result):
        return {"decision_source": "unknown", "used_fallback": False, "fallback_reason": None}


class TestObservationSnapshot(unittest.TestCase):
    def test_snapshot_unaffected_by_nested_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "e.jsonl")
            writer = RunWriter(path)
            rec = GameRecorderV2(writer, run_id="r", game_id="g", cohort="u",
                                 seat_agent_ids={0: "mutator", 1: "mutator"},
                                 seat_deck_ids={0: "d", 1: "d"},
                                 seed_meta={"runner_seed": 1, "opponent_policy_seed": 2,
                                            "requested_engine_seed": 1,
                                            "engine_rng_controlled": False, "engine_rng_note": "n"},
                                 seq=[0])
            rec.write_game_start()
            agent = _MutatingAgent()
            wrapped = make_capturing_agent(rec, agent, player_index=0, seat=0)
            live_obs = decision_obs(3, 1, 2, 0)
            wrapped(live_obs)
            rec.write_terminal(statuses=["DONE", "DONE"], rewards=[1, -1], error=None,
                               exception=None, duration_s=0.0)
            writer.close()

            # The live obs WAS mutated by the policy (sanity check).
            self.assertTrue(live_obs["select"]["option"][0].get("MUTATED"))
            self.assertEqual(live_obs["select"]["maxCount"], 999)

            # The RECORDED observation must be the pre-policy snapshot (unmutated).
            dec = next(json.loads(l) for l in open(path, encoding="utf-8")
                       if json.loads(l)["record_type"] == "decision")
            self.assertNotIn("MUTATED", dec["observation"]["select"]["option"][0])
            self.assertEqual(dec["observation"]["select"]["maxCount"], 2)
            self.assertEqual(dec["max_count"], 2)


if __name__ == "__main__":
    unittest.main()

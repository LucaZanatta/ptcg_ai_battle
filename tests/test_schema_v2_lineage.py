"""AC-01: schema-v2 run/agent/environment/engine lineage (stdlib unittest)."""

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.agents import random_baseline_definition, safe_agent_definition
from cg.episode_schema import (
    collect_engine_info, collect_environment, collect_git_info, implementation_sha256,
    seed_metadata,
)


class TestGitLineage(unittest.TestCase):
    def test_git_info(self):
        g = collect_git_info(_REPO_ROOT)
        self.assertTrue(g["commit"])
        self.assertTrue(g["branch"])
        self.assertIn(g["dirty"], (True, False))


class TestEnvironmentLineage(unittest.TestCase):
    def test_environment_fields(self):
        e = collect_environment()
        self.assertTrue(e["python_version"])
        self.assertTrue(e["platform"])
        self.assertTrue(e["machine"])
        self.assertTrue(e["kaggle_environments_version"])


class TestEngineLineage(unittest.TestCase):
    def test_engine_sha_size(self):
        info = collect_engine_info(os.path.join(_REPO_ROOT, "starter_kit", "libcg.so"), _REPO_ROOT)
        self.assertEqual(info["path"], os.path.join("starter_kit", "libcg.so"))
        self.assertIsNotNone(info["sha256"])
        self.assertGreater(info["size_bytes"], 0)


class TestAgentLineage(unittest.TestCase):
    def test_safe_agent_lineage(self):
        lin = safe_agent_definition(_REPO_ROOT).lineage()
        self.assertEqual(lin["agent_id"], "safe_agent")
        self.assertEqual(lin["policy_type"], "deterministic_safe_fallback")
        self.assertTrue(lin["agent_version"])
        paths = {sf["path"] for sf in lin["source_files"]}
        self.assertIn(os.path.join("starter_kit", "safe_policy.py"), paths)
        for sf in lin["source_files"]:
            self.assertIsNotNone(sf["sha256"])

    def test_random_baseline_distinct_identity(self):
        r = random_baseline_definition(_REPO_ROOT, seed=1, deck=[1] * 60).lineage()
        s = safe_agent_definition(_REPO_ROOT).lineage()
        self.assertNotEqual(r["agent_id"], s["agent_id"])
        self.assertNotEqual(r["policy_type"], s["policy_type"])


class TestImplementationHash(unittest.TestCase):
    def test_stable_and_order_independent(self):
        files = ["starter_kit/main.py", "starter_kit/safe_policy.py"]
        h1 = implementation_sha256(files, _REPO_ROOT)
        h2 = implementation_sha256(list(reversed(files)), _REPO_ROOT)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


class TestSeedMetadata(unittest.TestCase):
    def test_engine_rng_not_claimed_controlled(self):
        s = seed_metadata(runner_seed=5, opponent_policy_seed=6, requested_engine_seed=5)
        self.assertFalse(s["engine_rng_controlled"])
        self.assertIn("random_device", s["engine_rng_note"])
        self.assertEqual(s["runner_seed"], 5)


if __name__ == "__main__":
    unittest.main()

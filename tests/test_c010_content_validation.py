"""c010 AC-14: prove the evidence validator is CONTENT-aware, not existence-based.

Each test copies the real artifact tree, corrupts exactly one piece of content while leaving
every filename in place, and asserts the validator fails on the specific check that should
catch it. A control test asserts the pristine copy passes, so the failures are attributable to
the corruption rather than to copying.

These tests are skipped until the run has produced the artifacts they inspect.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts")
VALIDATOR = os.path.join(_REPO, "tools", "c010_validate_evidence.py")
REQUIRED = ["experiment_registry.json", "arm_configuration_diff.json",
            "baseline_incumbent_registry.json", "dependency_verification.json",
            "immutability_verification.json", "ppo_validation.json"]


def artifacts_ready():
    return all(os.path.exists(os.path.join(ART, f)) for f in REQUIRED)


def run_validator(art_dir, log_dir):
    subprocess.run([sys.executable, VALIDATOR, "--art-dir", art_dir, "--log-dir", log_dir,
                    "--quiet"], capture_output=True, text=True, timeout=1800)
    return json.load(open(os.path.join(art_dir, "evidence_validation.json")))


@unittest.skipUnless(artifacts_ready(), "c010 artifacts not produced yet")
class ValidatorContentAwareness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="c010val_")
        cls.src = os.path.join(cls.tmp, "src")
        shutil.copytree(ART, cls.src)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _fresh(self):
        d = tempfile.mkdtemp(dir=self.tmp)
        art = os.path.join(d, "artifacts")
        shutil.copytree(self.src, art)
        return art, os.path.join(d, "logs")

    def _failed(self, res, name):
        return any((not c["ok"]) and c["check"] == name for c in res["checks"])

    def test_pristine_copy_passes(self):
        art, log = self._fresh()
        res = run_validator(art, log)
        self.assertTrue(res["all_ok"],
                        [c["check"] for c in res["checks"] if not c["ok"]])

    def test_arm_C_extra_change_detected(self):
        """Arm C may differ from exact R1 in exactly three registered values, nothing else."""
        art, log = self._fresh()
        p = os.path.join(art, "experiment_registry.json")
        d = json.load(open(p))
        d["arms"]["C"]["ppo"]["clip"] = 0.31          # an unregistered change
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "arm_C_changes_exactly_three_registered_values"))

    def test_arm_A_deviation_from_exact_r1_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "experiment_registry.json")
        d = json.load(open(p))
        d["arms"]["A"]["ppo"]["learning_rate"] = 5e-4
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "arm_A_config_equals_exact_r1"))

    def test_recipe_drift_from_c008_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "experiment_registry.json")
        d = json.load(open(p))
        d["exact_r1_recipe"]["gamma"] = 0.99
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "exact_r1_matches_c008_source"))

    def test_tampered_baseline_hash_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "baseline_incumbent_registry.json")
        d = json.load(open(p))
        d["I0"]["checkpoint_sha256"] = "0" * 64
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "I0_hash_unchanged_on_disk"))

    def test_unprotected_incumbent_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "baseline_incumbent_registry.json")
        d = json.load(open(p))
        d["I0"]["protected"] = False
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "I0_marked_protected"))

    def test_ppo_validation_failure_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "ppo_validation.json")
        d = json.load(open(p)); d["all_pass"] = False
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "ppo_validation_passed"))

    def test_initialisation_fidelity_regression_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "ppo_validation.json")
        d = json.load(open(p)); d["initialization_fidelity"]["ok"] = False
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "b0_initialisation_fidelity_guarded"))

    @unittest.skipUnless(os.path.exists(os.path.join(ART, "best_agent_selection.json")),
                         "final panel not produced yet")
    def test_unjustified_promotion_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "best_agent_selection.json")
        d = json.load(open(p))
        d["best_agent"] = "SOMETHING_ELSE"; d["qualified"] = []
        json.dump(d, open(p, "w"))
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "best_agent_defaults_to_incumbent_when_nothing_qualifies"))

    @unittest.skipUnless(os.path.exists(os.path.join(ART, "submission_E_validation.json")),
                         "submission decision not produced yet")
    def test_stray_archive_while_gated_off_detected(self):
        art, log = self._fresh()
        sub = json.load(open(os.path.join(art, "submission_E_validation.json")))
        if sub.get("submission_E") != "DO_NOT_SUBMIT":
            self.skipTest("gate is SUBMIT in this run")
        open(os.path.join(art, "submission_E_fixed_deck_rl_v2.tar.gz"), "wb").write(b"not-real")
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "no_archive_when_gated_off"))

    @unittest.skipUnless(os.path.exists(os.path.join(ART, "evaluation_games.jsonl.gz")),
                         "evaluation games not produced yet")
    def test_dropped_evaluation_game_detected(self):
        import gzip
        art, log = self._fresh()
        p = os.path.join(art, "evaluation_games.jsonl.gz")
        rows = [l for l in gzip.open(p, "rt")]
        with gzip.open(p, "wt") as fh:
            fh.writelines(rows[:-1])
        res = run_validator(art, log)
        self.assertFalse(res["all_ok"])
        self.assertTrue(self._failed(res, "evaluation_manifest_count_matches_raw")
                        or self._failed(res, "evaluation_manifest_sha_matches")
                        or self._failed(res, "panel_sizes_exact"))


if __name__ == "__main__":
    unittest.main()

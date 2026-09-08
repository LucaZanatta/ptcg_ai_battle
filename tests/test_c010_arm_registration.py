"""c010 AC-03: the three arms must be registered exactly as the contract specifies —
Arms A and B identical to the resolved c008 R1 recipe, Arm C differing in exactly the three
registered values, with an identical population and budgets inside the hard cap."""

import json
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
ART = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts")
C008_REG = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl",
                        "results", "artifacts", "experiment_registration.json")

ARM_C_CHANGES = {"learning_rate": 3e-5, "rollout_game_target": 256,
                 "min_trainable_decisions": 32768}


class ArmRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.load(open(os.path.join(ART, "experiment_registry.json")))
        cls.diff = json.load(open(os.path.join(ART, "arm_configuration_diff.json")))
        cls.c008 = json.load(open(C008_REG))

    # ---- arms / seeds / budgets ----
    def test_three_arms_registered(self):
        self.assertEqual(sorted(self.reg["arms"]), ["A", "B", "C"])

    def test_registered_seeds(self):
        self.assertEqual(self.reg["arms"]["A"]["seeds"], [311, 322, 333])
        self.assertEqual(self.reg["arms"]["B"]["seeds"], [411, 422, 433])
        self.assertEqual(self.reg["arms"]["C"]["seeds"], [511, 522, 533])

    def test_registered_budgets_and_hard_cap(self):
        b = self.reg["budgets"]
        self.assertEqual(b["arm_A"], 36000)
        self.assertEqual(b["arm_B"], 22500)
        self.assertEqual(b["arm_C"], 60000)
        self.assertEqual(b["total"], 118500)
        self.assertLessEqual(b["total"], b["hard_maximum_including_spillover"])
        self.assertEqual(b["hard_maximum_including_spillover"], 120000)

    def test_max_games_per_seed(self):
        self.assertEqual(self.reg["arms"]["A"]["max_games_per_seed"], 12000)
        self.assertEqual(self.reg["arms"]["B"]["max_games_per_seed"], 7500)
        self.assertEqual(self.reg["arms"]["C"]["max_games_per_seed"], 20000)

    def test_evaluation_points(self):
        self.assertEqual(self.reg["arms"]["A"]["evaluation_points"], [0, 2500, 5000, 7500, 10000, 12000])
        self.assertEqual(self.reg["arms"]["B"]["evaluation_points"], [0, 2500, 5000, 7500])
        self.assertEqual(self.reg["arms"]["C"]["evaluation_points"],
                         [0, 2500, 5000, 7500, 10000, 15000, 20000])

    def test_initializations(self):
        self.assertEqual(self.reg["arms"]["A"]["initialization"], "B0")
        self.assertEqual(self.reg["arms"]["B"]["initialization"], "I0")
        self.assertEqual(self.reg["arms"]["C"]["initialization"], "I0")

    # ---- exact R1 fidelity ----
    def test_exact_r1_resolved_from_c008(self):
        r, c8 = self.reg["exact_r1_recipe"], self.c008["ppo"]
        self.assertEqual(r["gamma"], c8["gamma"])
        self.assertEqual(r["gae_lambda"], c8["gae_lambda"])
        self.assertEqual(r["clip"], c8["clip"])
        self.assertEqual(r["value_coef"], c8["value_coef"])
        self.assertEqual(r["max_grad_norm"], c8["max_grad_norm"])
        self.assertEqual(r["epochs"], c8["epochs_per_rollout"])
        self.assertEqual(r["learning_rate"], c8["lr"]["R1"])
        self.assertEqual(r["weight_decay"], c8["weight_decay"])
        self.assertEqual(r["rollout_game_target"], c8["target_rollout_games"])
        self.assertEqual(r["min_trainable_decisions"], c8["min_trainable_decisions_per_update"])
        self.assertEqual(r["entropy_coef_start"], c8["entropy_coef"]["start"])
        self.assertEqual(r["entropy_coef_end"], c8["entropy_coef"]["end"])

    def test_expected_recipe_values(self):
        r = self.reg["exact_r1_recipe"]
        for k, v in {"gamma": 0.997, "gae_lambda": 0.95, "clip": 0.20, "value_coef": 0.50,
                     "max_grad_norm": 0.50, "epochs": 4, "learning_rate": 1e-4,
                     "weight_decay": 1e-5, "rollout_game_target": 128,
                     "min_trainable_decisions": 8192}.items():
            self.assertEqual(r[k], v, k)

    def test_both_threshold_rollout_rule(self):
        self.assertTrue(self.reg["exact_r1_provenance"]["implementation_matches_both_thresholds_rule"])
        self.assertIn("BOTH", self.reg["exact_r1_recipe"]["rollout_rule"])

    # ---- the diff the contract requires ----
    def test_arm_A_identical_to_exact_r1(self):
        self.assertTrue(self.diff["arm_A_vs_exact_r1"]["identical"])
        self.assertEqual(self.diff["arm_A_vs_exact_r1"]["differences"], {})

    def test_arm_B_identical_to_exact_r1(self):
        self.assertTrue(self.diff["arm_B_vs_exact_r1"]["identical"])
        self.assertEqual(self.diff["arm_B_vs_exact_r1"]["differences"], {})

    def test_arm_C_changes_exactly_three_values(self):
        d = self.diff["arm_C_vs_exact_r1"]
        self.assertTrue(d["changes_exactly_the_three_registered_values"])
        self.assertEqual(sorted(d["changed_keys"]), sorted(ARM_C_CHANGES))
        for k, v in ARM_C_CHANGES.items():
            self.assertEqual(self.reg["arms"]["C"]["ppo"][k], v, k)

    def test_arm_C_shares_every_other_value_with_exact_r1(self):
        r, c = self.reg["exact_r1_recipe"], self.reg["arms"]["C"]["ppo"]
        for k in r:
            if k in ARM_C_CHANGES:
                continue
            self.assertEqual(c[k], r[k], f"Arm C changed unregistered key {k}")

    # ---- population / prohibitions / panels ----
    def test_population_identical_and_abomasnow_held_out(self):
        self.assertTrue(self.diff["population_identical_across_arms"])
        self.assertIn("EVALUATION ONLY", self.reg["population"]["abomasnow"])
        w = self.reg["population"]["with_lagged"]
        self.assertAlmostEqual(w["teacher"] + w["mega_lucario"] + w["iono"]
                               + w["lagged_selfplay"] + w["control"], 1.0, places=9)

    def test_prohibited_techniques_registered(self):
        p = " ".join(self.diff["prohibited_in_all_arms"]).lower()
        for term in ("replay", "kl", "reward shaping", "deck", "random-initialized",
                     "search", "abomasnow"):
            self.assertIn(term, p)

    def test_panels_match_contract(self):
        p = self.reg["panels"]
        self.assertEqual(p["screen"]["total_per_checkpoint"], 100)
        self.assertEqual(p["confirmation"]["total_per_checkpoint"], 500)
        self.assertEqual(p["final"]["total_per_finalist"], 1000)
        self.assertEqual((p["screen"]["teacher"], p["screen"]["mega_lucario"]), (20, 10))
        self.assertEqual((p["final"]["teacher"], p["final"]["mega_lucario"]), (200, 100))

    def test_field_metric_excludes_the_mirror(self):
        base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
        d = base["_metric_definitions"]["strategic_field_score"]
        self.assertIn("Lucario", d); self.assertIn("Iono", d); self.assertIn("Abomasnow", d)
        self.assertIn("NOT in the field", d)


if __name__ == "__main__":
    unittest.main()

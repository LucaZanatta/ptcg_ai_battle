"""c010 §17–§25 decision rules, exercised with synthetic evidence.

The load-bearing property: the incumbent is protected — a candidate that is merely newer, or
better on one dimension while worse on another, or better without statistical support, must
NOT be promoted.
"""

import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from cg import c010_decisions as D  # noqa: E402


def cand(teacher, field, abom=None, luc=None, iono=None, defects=0, games=1000, cid="X"):
    abom = field if abom is None else abom
    luc = field if luc is None else luc
    iono = field if iono is None else iono
    per = {D.TEACHER: {"point": teacher}, "mega_lucario": {"point": luc},
           "iono": {"point": iono}, "mega_abomasnow": {"point": abom}}
    pts = {k: v["point"] for k, v in per.items()}
    return {"candidate_id": cid, "teacher_score": teacher,
            "strategic_field_score": D.field_score(pts), "promotion_composite": D.composite(pts),
            "per_opponent": per, "training_games": games,
            "reliability": {"defects": defects, "invalid": 0, "exceptions": 0, "timeouts": 0}}


def boots(diff_mean, n=4000, sd=0.02, seed=0):
    return np.random.default_rng(seed).normal(diff_mean, sd, n)


class Metrics(unittest.TestCase):
    def test_field_excludes_teacher(self):
        pts = {D.TEACHER: 0.9, "mega_lucario": 0.3, "iono": 0.2, "mega_abomasnow": 0.1}
        self.assertAlmostEqual(D.field_score(pts), 0.2)

    def test_composite_weights(self):
        pts = {D.TEACHER: 1.0, "mega_lucario": 0.0, "iono": 0.0, "mega_abomasnow": 0.0}
        self.assertAlmostEqual(D.composite(pts), 0.55)

    def test_major_regression_needs_both_magnitude_and_probability(self):
        self.assertTrue(D.major_regression(0.20, 0.30, boots(-0.10, sd=0.01)))
        self.assertFalse(D.major_regression(0.28, 0.30, boots(-0.02, sd=0.01)))   # too small
        self.assertFalse(D.major_regression(0.20, 0.30, boots(-0.10, sd=0.30)))   # too uncertain


class Promotion(unittest.TestCase):
    def setUp(self):
        self.inc = cand(0.22, 0.29, cid="I0_incumbent")

    def test_clearly_better_candidate_is_promoted(self):
        c = cand(0.30, 0.35, cid="C_511_g10000")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.08), "field": boots(0.06)})
        self.assertTrue(r["qualifies"], r["criteria"])

    def test_newer_but_equal_candidate_is_not_promoted(self):
        c = cand(0.22, 0.29, games=99999, cid="C_511_g20000")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.0), "field": boots(0.0)})
        self.assertFalse(r["qualifies"])
        self.assertFalse(r["criteria"]["composite_higher"])

    def test_better_teacher_but_worse_field_is_not_promoted(self):
        c = cand(0.30, 0.20, cid="B_411_g7500")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.08), "field": boots(-0.09)})
        self.assertFalse(r["qualifies"])
        self.assertFalse(r["criteria"]["field_not_lower"])

    def test_improvement_without_statistical_support_is_not_promoted(self):
        c = cand(0.24, 0.30, cid="A_311_g12000")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.02, sd=0.20),
                                                "field": boots(0.01, sd=0.20)})
        self.assertFalse(r["qualifies"])
        self.assertFalse(r["criteria"]["one_primary_improvement_90pct"])

    def test_major_regression_blocks_promotion(self):
        c = cand(0.30, 0.34, abom=0.10, cid="C_522_g15000")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.08), "field": boots(0.05),
                                                f"opp::mega_abomasnow": boots(-0.19, sd=0.01)})
        self.assertFalse(r["qualifies"])
        self.assertIn("mega_abomasnow", r["major_regressions"])

    def test_reliability_failure_blocks_promotion(self):
        c = cand(0.35, 0.40, defects=3, cid="C_533_g20000")
        r = D.promotion_qualifies(c, self.inc, {"teacher": boots(0.13), "field": boots(0.11)})
        self.assertFalse(r["qualifies"])
        self.assertFalse(r["criteria"]["reliability_passes"])

    def test_tiebreak_prefers_teacher_then_field_then_abomasnow(self):
        a = cand(0.30, 0.30, cid="a"); b = cand(0.28, 0.40, cid="b")
        self.assertGreater(D.promotion_tiebreak_key(a), D.promotion_tiebreak_key(b))

    def test_tiebreak_prefers_earlier_checkpoint_when_otherwise_equal(self):
        early = cand(0.30, 0.30, games=5000, cid="early")
        late = cand(0.30, 0.30, games=20000, cid="late")
        self.assertGreater(D.promotion_tiebreak_key(early), D.promotion_tiebreak_key(late))


class Reproducibility(unittest.TestCase):
    def setUp(self):
        self.b0 = cand(0.16, 0.1533, cid="B0_v2a")

    def test_proven_when_all_conditions_hold(self):
        seeds = [cand(0.22, 0.26, cid="A_311"), cand(0.21, 0.25, cid="A_322"),
                 cand(0.20, 0.24, cid="A_333")]
        db = {s["candidate_id"]: {"teacher": boots(0.05), "field": boots(0.09)} for s in seeds}
        r = D.exact_reproducibility(seeds, self.b0, db, True)
        self.assertEqual(r["decision"], "PROVEN", r["conditions"])

    def test_failed_when_no_seed_improves_and_evidence_is_clear(self):
        seeds = [cand(0.10, 0.10, cid="A_311"), cand(0.11, 0.11, cid="A_322"),
                 cand(0.09, 0.09, cid="A_333")]
        db = {s["candidate_id"]: {"teacher": boots(-0.06, sd=0.01),
                                  "field": boots(-0.05, sd=0.01)} for s in seeds}
        self.assertEqual(D.exact_reproducibility(seeds, self.b0, db, True)["decision"], "FAILED")

    def test_inconclusive_when_gains_are_small_or_uncertain(self):
        seeds = [cand(0.18, 0.17, cid="A_311"), cand(0.17, 0.16, cid="A_322"),
                 cand(0.15, 0.15, cid="A_333")]
        db = {s["candidate_id"]: {"teacher": boots(0.02, sd=0.05),
                                  "field": boots(0.01, sd=0.05)} for s in seeds}
        self.assertEqual(D.exact_reproducibility(seeds, self.b0, db, True)["decision"], "INCONCLUSIVE")

    def test_reliability_failure_blocks_proven(self):
        seeds = [cand(0.22, 0.26, cid="A_311"), cand(0.21, 0.25, cid="A_322"),
                 cand(0.20, 0.24, cid="A_333")]
        db = {s["candidate_id"]: {"teacher": boots(0.05), "field": boots(0.09)} for s in seeds}
        self.assertNotEqual(D.exact_reproducibility(seeds, self.b0, db, False)["decision"], "PROVEN")


class Continuation(unittest.TestCase):
    def setUp(self):
        self.i0 = cand(0.22, 0.29, cid="I0_incumbent")

    def test_extended_when_two_seeds_and_median_gains(self):
        seeds = [cand(0.28, 0.34, cid="C_511"), cand(0.27, 0.33, cid="C_522"),
                 cand(0.26, 0.32, cid="C_533")]
        db = {s["candidate_id"]: {"teacher": boots(0.05), "field": boots(0.04)} for s in seeds}
        self.assertEqual(D.continuation(seeds, self.i0, db, True)["decision"], "EXTENDED")

    def test_not_extended_when_no_seed_improves(self):
        seeds = [cand(0.18, 0.24, cid="B_411"), cand(0.17, 0.23, cid="B_422"),
                 cand(0.19, 0.25, cid="B_433")]
        db = {s["candidate_id"]: {"teacher": boots(-0.04, sd=0.01),
                                  "field": boots(-0.05, sd=0.01)} for s in seeds}
        self.assertEqual(D.continuation(seeds, self.i0, db, True)["decision"], "NOT_EXTENDED")

    def test_strong_flag_requires_30_percent_on_both(self):
        seeds = [cand(0.31, 0.32, cid="C_511"), cand(0.30, 0.31, cid="C_522"),
                 cand(0.20, 0.20, cid="C_533")]
        db = {s["candidate_id"]: {"teacher": boots(0.05), "field": boots(0.03)} for s in seeds}
        self.assertTrue(D.continuation(seeds, self.i0, db, True)["strong_continuation_flag"])


class StatusAndGates(unittest.TestCase):
    def test_validated_requires_everything(self):
        self.assertEqual(D.training_loop_status("PROVEN", "EXTENDED", "INCONCLUSIVE", True, True,
                                                False, True), "VALIDATED")
        self.assertEqual(D.training_loop_status("PROVEN", "NOT_EXTENDED", "NOT_EXTENDED", False,
                                                False, False, True), "PROMISING")
        self.assertEqual(D.training_loop_status("FAILED", "NOT_EXTENDED", "NOT_EXTENDED", False,
                                                False, False, False), "REJECTED")

    def test_submission_requires_non_inferiority_and_improvement(self):
        best = cand(0.30, 0.35, cid="C_511_g10000")
        r = D.submission_gate("C_511_g10000", best, 0.28, True, False, True, True)
        self.assertEqual(r["decision"], "DO_NOT_SUBMIT")
        self.assertFalse(r["criteria"]["teacher_non_inferiority_lb95_ge_0.47"])
        r2 = D.submission_gate("C_511_g10000", best, 0.50, True, False, True, True)
        self.assertEqual(r2["decision"], "SUBMIT")

    def test_incumbent_itself_can_never_be_submitted_as_new(self):
        r = D.submission_gate("I0_incumbent", cand(0.22, 0.29), 0.99, True, False, True, True)
        self.assertEqual(r["decision"], "DO_NOT_SUBMIT")
        self.assertFalse(r["criteria"]["best_agent_is_new"])

    def test_next_step_rules(self):
        self.assertEqual(D.next_step("VALIDATED", True, True, False), "SCALE_FIXED_DECK_RL")
        self.assertEqual(D.next_step("REJECTED", True, False, False), "REDESIGN_FIXED_DECK_AGENT")
        self.assertEqual(D.next_step("PROMISING", True, False, False), "REDESIGN_FIXED_DECK_AGENT")


if __name__ == "__main__":
    unittest.main()


class TeacherExtensionRule(unittest.TestCase):
    """§16: the 800-game teacher extension fires only while non-inferiority is still live."""

    def test_extends_when_interval_still_reaches_threshold(self):
        self.assertTrue(D.plausibly_teacher_non_inferior([0.40, 0.50]))

    def test_extends_at_exact_threshold(self):
        self.assertTrue(D.plausibly_teacher_non_inferior([0.30, 0.47]))

    def test_does_not_extend_when_ruled_out(self):
        self.assertFalse(D.plausibly_teacher_non_inferior([0.20, 0.34]))

    def test_missing_interval_does_not_extend(self):
        self.assertFalse(D.plausibly_teacher_non_inferior(None))
        self.assertFalse(D.plausibly_teacher_non_inferior([0.2, None]))

    def test_weaker_than_the_promotion_gate(self):
        """A finalist can warrant extension yet still fail the one-sided LB>=0.47 gate."""
        self.assertTrue(D.plausibly_teacher_non_inferior([0.35, 0.49]))
        gate = D.submission_gate("X", {"promotion_composite": 0.9}, 0.35, True, False, True, True)
        self.assertFalse(gate["criteria"]["teacher_non_inferiority_lb95_ge_0.47"])

"""c010 AC-05: evaluation identity must survive arbitrary completion order and fail loudly on
missing, duplicated, mislabeled, miscounted, wrong-hash or wrong-deck results.

c010 reuses the c009 job protocol, so these tests exercise that protocol against c010's frozen
panel shapes (screen 100 / confirmation 500 / final 1000 games per checkpoint).
"""

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg.c009_eval import (IDENTITY_FIELDS, IdentityError, assert_identity,  # noqa: E402
                          deck_fingerprint, make_job)

DECK = list(range(1, 61))
FP = deck_fingerprint(DECK)
PANELS = {"screen": {"dragapult": 20, "mega_lucario": 10, "iono": 10, "mega_abomasnow": 10},
          "confirmation": {"dragapult": 100, "mega_lucario": 50, "iono": 50, "mega_abomasnow": 50},
          "final": {"dragapult": 200, "mega_lucario": 100, "iono": 100, "mega_abomasnow": 100}}
REGISTRY = {
    "B0_v2a": {"candidate_id": "B0_v2a", "arm": "B0", "seed": None, "kind": "v2a_init",
               "checkpoint_path": "p/b0.npz", "checkpoint_sha256": "a" * 64},
    "I0_incumbent": {"candidate_id": "I0_incumbent", "arm": "I0", "seed": 101, "kind": "rl_ckpt",
                     "checkpoint_path": "p/i0.npz", "checkpoint_sha256": "b" * 64},
    "A_311_g12000": {"candidate_id": "A_311_g12000", "arm": "A", "seed": 311, "kind": "rl_ckpt",
                     "checkpoint_path": "p/a.npz", "checkpoint_sha256": "c" * 64},
    "C_511_g20000": {"candidate_id": "C_511_g20000", "arm": "C", "seed": 511, "kind": "rl_ckpt",
                     "checkpoint_path": "p/c.npz", "checkpoint_sha256": "d" * 64},
}


def build_jobs(panel="screen", candidates=("B0_v2a", "I0_incumbent", "A_311_g12000")):
    jobs = []
    for cid in candidates:
        for opp, per_seat in PANELS[panel].items():
            for seat in (0, 1):
                for r in range(per_seat):
                    jobs.append(make_job(REGISTRY[cid], opp, seat, r, panel,
                                         requested_seed=1000 + len(jobs), deck=DECK))
    return jobs


def result_for(job):
    rec = {k: job[k] for k in IDENTITY_FIELDS}
    rec.update({"arm": job["arm"], "seed": job["seed"], "candidate_kind": job["candidate_kind"],
                "outcome": "win", "score": 1.0, "terminal": True, "decision_count": 40,
                "fallback_count": 0, "invalid_action_count": 0, "exception_count": 0,
                "timeout_count": 0, "latency_p50_ms": 1.0, "latency_p95_ms": 2.0,
                "latency_p99_ms": 3.0, "duration_seconds": 0.4,
                "verified_checkpoint_sha256": job["checkpoint_sha256"],
                "deck_fingerprint": FP, "defect": None})
    return rec


class PanelShapes(unittest.TestCase):
    def test_panel_totals_match_contract(self):
        for panel, expected in (("screen", 100), ("confirmation", 500), ("final", 1000)):
            n = sum(v * 2 for v in PANELS[panel].values())
            self.assertEqual(n, expected, panel)

    def test_every_panel_uses_both_seats_and_all_four_opponents(self):
        for panel in PANELS:
            jobs = build_jobs(panel, ("B0_v2a",))
            self.assertEqual({j["seat"] for j in jobs}, {0, 1})
            self.assertEqual({j["opponent_id"] for j in jobs},
                             {"dragapult", "mega_lucario", "iono", "mega_abomasnow"})

    def test_job_ids_unique_within_and_across_panels(self):
        ids = [j["job_id"] for p in PANELS for j in build_jobs(p)]
        self.assertEqual(len(ids), len(set(ids)))


class IdentityUnderReordering(unittest.TestCase):
    def setUp(self):
        self.jobs = build_jobs("screen")
        self.res = [result_for(j) for j in self.jobs]

    def test_clean_passes(self):
        self.assertTrue(assert_identity(self.jobs, self.res, REGISTRY,
                                        expected_deck_fingerprint=FP)["ok"])

    def test_reversed_order_passes(self):
        self.assertTrue(assert_identity(self.jobs, self.res[::-1], REGISTRY,
                                        expected_deck_fingerprint=FP)["ok"])

    def test_shuffled_order_passes(self):
        import random
        r = list(self.res); random.Random(3).shuffle(r)
        self.assertTrue(assert_identity(self.jobs, r, REGISTRY, expected_deck_fingerprint=FP)["ok"])

    def test_positional_relabeling_is_rejected(self):
        """The c008 defect shape must not survive into c010."""
        res = self.res[::-1]
        for j, r in zip(self.jobs, res):
            r["candidate_id"] = j["candidate_id"]; r["arm"] = j["arm"]
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, res, REGISTRY, expected_deck_fingerprint=FP)


class IdentityFailures(unittest.TestCase):
    def setUp(self):
        self.jobs = build_jobs("screen")
        self.res = [result_for(j) for j in self.jobs]

    def _expect_fail(self):
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_missing_result(self):
        self.res.pop(11); self._expect_fail()

    def test_duplicate_result(self):
        self.res.append(dict(self.res[0])); self._expect_fail()

    def test_mislabeled_candidate(self):
        self.res[5]["candidate_id"] = "C_511_g20000"; self._expect_fail()

    def test_mislabeled_seat(self):
        self.res[6]["seat"] = 1 - self.res[6]["seat"]; self._expect_fail()

    def test_mislabeled_opponent(self):
        self.res[7]["opponent_id"] = "iono"; self._expect_fail()

    def test_wrong_checkpoint_hash(self):
        self.res[8]["verified_checkpoint_sha256"] = "f" * 64; self._expect_fail()

    def test_wrong_deck(self):
        self.res[9]["deck_fingerprint"] = "e" * 64; self._expect_fail()

    def test_unclassified_non_terminal(self):
        self.res[0]["terminal"] = False; self.res[0]["defect"] = None; self._expect_fail()

    def test_miscount_detected(self):
        extra = dict(self.res[0]); extra["job_id"] = extra["job_id"] + "-x"
        self.res.append(extra); self._expect_fail()

    def test_classified_defect_is_allowed(self):
        self.res[0]["terminal"] = False
        self.res[0]["defect"] = "non_terminal:['DONE','ERROR']"
        self.res[0]["score"] = None
        rep = assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)
        self.assertTrue(rep["ok"]); self.assertEqual(rep["defects"], 1)


if __name__ == "__main__":
    unittest.main()

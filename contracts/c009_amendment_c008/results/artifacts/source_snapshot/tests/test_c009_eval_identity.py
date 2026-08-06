"""c009 AC-03: the identity-safe evaluator must preserve job identity under ANY completion
order, and must FAIL loudly on missing, duplicated, mislabeled, miscounted, wrong-hash, or
wrong-deck results. Includes a direct demonstration that the c008 positional-zip pattern is
rejected by these assertions."""

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg.c009_eval import (IDENTITY_FIELDS, IdentityError, assert_identity,  # noqa: E402
                          deck_fingerprint, make_job, make_job_id)

DECK = list(range(1, 61))
FP = deck_fingerprint(DECK)

REGISTRY = {
    "B0_v2a": {"candidate_id": "B0_v2a", "arm": "B0", "seed": None,
               "checkpoint_sha256": "a" * 64, "kind": "v2a_init", "checkpoint_path": "p/a.npz"},
    "R1_101": {"candidate_id": "R1_101", "arm": "R1", "seed": 101,
               "checkpoint_sha256": "b" * 64, "kind": "rl_ckpt", "checkpoint_path": "p/b.npz"},
    "R2_303": {"candidate_id": "R2_303", "arm": "R2", "seed": 303,
               "checkpoint_sha256": "c" * 64, "kind": "rl_ckpt", "checkpoint_path": "p/c.npz"},
}


def build_jobs(opponents=("dragapult", "iono"), reps=3):
    jobs = []
    for cid, cand in REGISTRY.items():
        c = dict(cand)
        c["arm"] = cand["arm"]
        for opp in opponents:
            for seat in (0, 1):
                for r in range(reps):
                    jobs.append(make_job(c, opp, seat, r, "phaseX", 1000 + len(jobs), DECK))
    return jobs


def result_for(job, score=1.0):
    """A well-behaved worker: echoes identity verbatim."""
    rec = {k: job[k] for k in IDENTITY_FIELDS}
    rec.update({"arm": job["arm"], "seed": job["seed"], "candidate_kind": job["candidate_kind"],
                "outcome": "win", "score": score, "terminal": True, "decision_count": 10,
                "fallback_count": 0, "invalid_action_count": 0, "exception_count": 0,
                "timeout_count": 0, "latency_p50_ms": 1.0, "latency_p95_ms": 2.0,
                "latency_p99_ms": 3.0, "duration_seconds": 0.5,
                "verified_checkpoint_sha256": job["checkpoint_sha256"],
                "deck_fingerprint": FP, "defect": None})
    return rec


class TestIdentityUnderReordering(unittest.TestCase):
    def test_clean_passes(self):
        jobs = build_jobs()
        res = [result_for(j) for j in jobs]
        rep = assert_identity(jobs, res, REGISTRY, expected_deck_fingerprint=FP)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["n_results"], len(jobs))

    def test_reversed_completion_order_preserves_identity(self):
        jobs = build_jobs()
        res = [result_for(j) for j in jobs][::-1]          # completion order reversed
        rep = assert_identity(jobs, res, REGISTRY, expected_deck_fingerprint=FP)
        self.assertTrue(rep["ok"])

    def test_arbitrary_shuffle_preserves_identity(self):
        import random
        jobs = build_jobs()
        res = [result_for(j) for j in jobs]
        random.Random(7).shuffle(res)
        self.assertTrue(assert_identity(jobs, res, REGISTRY, expected_deck_fingerprint=FP)["ok"])

    def test_c008_positional_zip_pattern_is_rejected(self):
        """Reproduces the c008 bug shape: results arrive out of order and the arm/candidate
        label is re-attached positionally. The assertions must reject it."""
        jobs = build_jobs()
        res = [result_for(j) for j in jobs][::-1]
        for j, r in zip(jobs, res):                        # <-- the c008 defect
            r["candidate_id"] = j["candidate_id"]
            r["arm"] = j["arm"]
        with self.assertRaises(IdentityError):
            assert_identity(jobs, res, REGISTRY, expected_deck_fingerprint=FP)


class TestIdentityFailures(unittest.TestCase):
    def setUp(self):
        self.jobs = build_jobs()
        self.res = [result_for(j) for j in self.jobs]

    def test_missing_job_detected(self):
        self.res.pop(5)
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_duplicated_job_detected(self):
        self.res.append(dict(self.res[0]))
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_mislabeled_candidate_detected(self):
        self.res[3]["candidate_id"] = "R2_303"
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_mislabeled_seat_detected(self):
        self.res[4]["seat"] = 1 - self.res[4]["seat"]
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_mislabeled_opponent_detected(self):
        self.res[6]["opponent_id"] = "mega_lucario"
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_unknown_candidate_detected(self):
        for r in self.res:
            if r["candidate_id"] == "R1_101":
                r["candidate_id"] = "GHOST"
                r["job_id"] = r["job_id"].replace("R1_101", "GHOST")
                break
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_checkpoint_hash_mismatch_detected(self):
        self.res[2]["verified_checkpoint_sha256"] = "f" * 64
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_registry_hash_mismatch_detected(self):
        self.res[2]["checkpoint_sha256"] = "d" * 64
        self.res[2]["verified_checkpoint_sha256"] = "d" * 64
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_wrong_deck_detected(self):
        self.res[1]["deck_fingerprint"] = "e" * 64
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_unclassified_nonterminal_detected(self):
        self.res[0]["terminal"] = False
        self.res[0]["defect"] = None
        with self.assertRaises(IdentityError):
            assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)

    def test_classified_defect_allowed(self):
        self.res[0]["terminal"] = False
        self.res[0]["defect"] = "non_terminal:['DONE', 'ERROR']"
        self.res[0]["score"] = None
        rep = assert_identity(self.jobs, self.res, REGISTRY, expected_deck_fingerprint=FP)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["defects"], 1)


class TestJobIdUniqueness(unittest.TestCase):
    def test_job_ids_unique_across_grid(self):
        jobs = build_jobs(opponents=("dragapult", "iono", "mega_abomasnow"), reps=5)
        ids = [j["job_id"] for j in jobs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_job_id_is_deterministic(self):
        a = make_job_id("R1_101", "iono", 0, 3, "phaseA")
        b = make_job_id("R1_101", "iono", 0, 3, "phaseA")
        self.assertEqual(a, b)
        self.assertNotEqual(a, make_job_id("R1_101", "iono", 1, 3, "phaseA"))


if __name__ == "__main__":
    unittest.main()

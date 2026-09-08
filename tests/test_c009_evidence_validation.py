"""c009 AC-12: prove the evidence validator is CONTENT-aware, not existence-based.

Each test copies the real artifact tree, corrupts exactly one piece of content while leaving
every filename in place, and asserts the validator fails. A control test asserts the pristine
copy passes — so the failures are attributable to the corruption, not to the copy.
"""

import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(_REPO, "contracts", "c009_amendment_c008", "results", "artifacts")
VALIDATOR = os.path.join(_REPO, "tools", "c009_validate_evidence.py")


def run_validator(art_dir, log_dir):
    r = subprocess.run([sys.executable, VALIDATOR, "--art-dir", art_dir,
                        "--log-dir", log_dir, "--quiet"],
                       capture_output=True, text=True, timeout=900)
    res = json.load(open(os.path.join(art_dir, "evidence_validation.json")))
    return r.returncode, res


class ValidatorContentAwareness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="c009val_")
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

    # ---- control ----
    def test_pristine_copy_passes(self):
        art, log = self._fresh()
        code, res = run_validator(art, log)
        self.assertEqual(code, 0, f"pristine copy should pass; failures: "
                                  f"{[c['check'] for c in res['checks'] if not c['ok']]}")
        self.assertTrue(res["all_ok"])

    # ---- corrupted aggregates (files still exist!) ----
    def test_tampered_matchup_score_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_matchup_matrix.csv")
        rows = list(csv.DictReader(open(p)))
        rows[0]["seat_balanced_score"] = str(round(float(rows[0]["seat_balanced_score"]) + 0.25, 4))
        with open(p, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "matchup_scores_reproduce_raw_games"))

    def test_tampered_matchup_count_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_matchup_matrix.csv")
        rows = list(csv.DictReader(open(p)))
        rows[0]["n"] = str(int(rows[0]["n"]) + 7)
        with open(p, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "matchup_counts_reproduce_raw_games"))

    def test_tampered_teacher_noninferiority_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_teacher_noninferiority.json")
        d = json.load(open(p))
        cid = next(iter(d["candidates"]))
        d["candidates"][cid]["point"] = 0.99
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "teacher_h2h_values_reproduce_raw_games"))

    def test_flipped_noninferiority_flag_detected(self):
        """A 'PASS' claimed without the underlying bound must be caught."""
        art, log = self._fresh()
        p = os.path.join(art, "amended_teacher_noninferiority.json")
        d = json.load(open(p))
        cid = next(iter(d["candidates"]))
        d["candidates"][cid]["non_inferior"] = True          # bound unchanged, flag flipped
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "teacher_h2h_values_reproduce_raw_games")
                        or self._failed(res, "teacher_noninferiority_decision_follows_evidence"))

    def test_holdout_using_wrong_opponent_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_holdout_report.json")
        d = json.load(open(p)); d["held_out_opponent"] = "iono"
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "holdout_report_uses_only_abomasnow"))

    def test_tampered_global_ranking_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_global_ranking.json")
        d = json.load(open(p))
        cid = next(iter(d["candidates"]))
        d["candidates"][cid]["mean_vs_field"] = 0.95
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "global_ranking_reproduces_raw_games"))

    # ---- corrupted raw evidence ----
    def test_dropped_raw_game_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "corrected_games.jsonl.gz")
        rows = [l for l in gzip.open(p, "rt")]
        with gzip.open(p, "wt") as fh:
            fh.writelines(rows[:-1])                          # drop one game
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "manifest_count_matches_raw")
                        or self._failed(res, "manifest_raw_sha_matches"))

    def test_duplicated_job_id_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "corrected_games.jsonl.gz")
        rows = [l for l in gzip.open(p, "rt")]
        rows.append(rows[0])
        with gzip.open(p, "wt") as fh:
            fh.writelines(rows)
        m = os.path.join(art, "corrected_game_manifest.json")
        man = json.load(open(m)); man["total_games"] = len(rows)
        import hashlib
        json.dump(man, open(m, "w"))
        man["raw_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        json.dump(man, open(m, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "job_ids_unique"))

    def test_mislabeled_arm_in_raw_games_detected(self):
        """The exact c008 failure mode: a game attributed to the wrong candidate."""
        art, log = self._fresh()
        p = os.path.join(art, "corrected_games.jsonl.gz")
        rows = [json.loads(l) for l in gzip.open(p, "rt")]
        for r in rows:
            if r["candidate_id"] == "R1_101":
                r["candidate_id"] = "B0_v2a"                  # identity corruption
                break
        with gzip.open(p, "wt") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        import hashlib
        m = os.path.join(art, "corrected_game_manifest.json")
        man = json.load(open(m))
        man["raw_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        json.dump(man, open(m, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        # a mislabeled game breaks weight attribution and/or seat/cell counts
        self.assertTrue(any(not c["ok"] for c in res["checks"]))

    def test_wrong_checkpoint_hash_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "candidate_checkpoint_registry.json")
        d = json.load(open(p))
        d["R1_101"]["checkpoint_sha256"] = "0" * 64
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "registry_checkpoint_hashes_match_disk"))

    # ---- corrupted decisions / conditional artifacts ----
    def test_unjustified_submit_decision_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_checkpoint_selection.json")
        d = json.load(open(p)); d["submission_D_amended"] = "SUBMIT"
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "submission_decision_follows_amended_gate"))

    def test_archive_present_while_do_not_submit_detected(self):
        art, log = self._fresh()
        open(os.path.join(art, "submission_D_amended_rl.tar.gz"), "wb").write(b"not-a-real-archive")
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "conditional_archive_absent_when_do_not_submit"))

    def test_overclaimed_best_checkpoint_detected(self):
        art, log = self._fresh()
        p = os.path.join(art, "amended_checkpoint_selection.json")
        d = json.load(open(p)); d["best_saved_checkpoint"] = "R2_303_ckpt_g5054"
        json.dump(d, open(p, "w"))
        code, res = run_validator(art, log)
        self.assertNotEqual(code, 0)
        self.assertTrue(self._failed(res, "best_saved_checkpoint_follows_rule"))


if __name__ == "__main__":
    unittest.main()

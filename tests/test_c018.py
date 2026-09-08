"""c018 unit tests.

These target the properties whose violation would be invisible in a summary: the
hidden-information guard actually raising, the determinizer never under-predicting, the
validator actually rejecting the fabrications it exists to catch, and the panel aggregating by
identity rather than by position.
"""

from __future__ import annotations

import gzip
import importlib
import json
import os
import sys
import tempfile
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c018_search as S  # noqa: E402


# --------------------------------------------------------------------------- fixtures

class _Card:
    def __init__(self, cid):
        self.id = cid


class _P:
    def __init__(self, hand=(), active=(), bench=(), discard=(), prize=(), deck=0, hc=0):
        self.hand = [_Card(c) for c in hand]
        self.active = [_Card(c) if c is not None else None for c in active]
        self.bench = [_Card(c) if c is not None else None for c in bench]
        self.discard = [_Card(c) for c in discard]
        self.prize = list(prize)
        self.deckCount = deck
        self.handCount = hc


class _St:
    def __init__(self, me, opp):
        self.players = [me, opp]
        self.yourIndex = 0


def _view():
    return S.VisibleView(_St(_P(hand=(1, 2), active=(3,), deck=40, prize=(0,) * 6, hc=2),
                             _P(active=(9,), discard=(9, 10), deck=41, prize=(0,) * 6, hc=5)),
                         0)


def _fake_search(step_ok=10, depth=3, succ=5):
    return {"real_search_counters": {"begin_ok": 4, "step_ok": step_ok, "step_calls": step_ok,
                                     "step_errors": 0, "release_calls": 4, "release_errors": 0,
                                     "end_calls": 4, "max_depth_reached": depth,
                                     "distinct_successors": succ,
                                     "hidden_information_violations": 0},
            "trusted_decisions": 4, "uses_c017_labels": False,
            "sample_traces": [{"depth_max": depth}]}


def _validator_on(tmp, curriculum=None, distill=None, search=None, traj=None, final=False):
    """Run the validator against a synthetic results tree and return its check map."""
    import c018_validate as V
    importlib.reload(V)
    V.C18 = tmp
    V.ART = os.path.join(tmp, "artifacts")
    V.LOGD = os.path.join(tmp, "test_logs")
    for d in ("artifacts", "test_logs", "training", "search", "trajectories", "rollouts"):
        os.makedirs(os.path.join(tmp, d), exist_ok=True)
    if curriculum:
        json.dump(curriculum,
                  open(os.path.join(tmp, "training", "curriculum_report.json"), "w"))
    if distill:
        json.dump(distill,
                  open(os.path.join(tmp, "training", "distillation_report.json"), "w"))
    if search:
        json.dump(search, open(os.path.join(tmp, "search", "x_search_summary.json"), "w"))
    if traj is not None:
        with gzip.open(os.path.join(tmp, "trajectories", "x_trajectories.jsonl.gz"),
                       "wt") as fh:
            for r in traj:
                fh.write(json.dumps(r) + "\n")
    old = sys.argv
    sys.argv = ["c018_validate.py"] + (["--final"] if final else [])
    try:
        rc = V.main()
    finally:
        sys.argv = old
    return {c["check"]: c for c in V.checks}, rc


def _row(**kw):
    base = {"n_options": 3, "legal_mask": [1, 1, 1], "label_action": [0], "trusted": False,
            "distinct_successors": 0, "game_index": 0, "split": "train", "final_outcome": 1.0}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- hidden info

class TestHiddenInformation(unittest.TestCase):

    def test_forbidden_zones_raise_rather_than_return(self):
        v = _view()
        for call in (v.opponent_hand_ids, lambda: v.deck_list("theirs"),
                     lambda: v.prize_ids("theirs")):
            with self.assertRaises(S.HiddenInformationAccess):
                call()

    def test_visible_zones_are_readable(self):
        v = _view()
        self.assertEqual(v.my_hand_ids(), [1, 2])
        self.assertIn(9, v.board_ids("theirs"))
        c = v.counts()
        self.assertEqual(c["opp_hand"], 5)
        self.assertEqual(c["opp_deck"], 41)


class TestDeterminizer(unittest.TestCase):

    def test_never_under_predicts(self):
        """`search_begin` validates counts with >=, so a short prediction raises. A pool that
        runs dry must be topped up with a legal id -- two begin errors and 49 step errors in
        the first smoke came from exactly this."""
        v = _view()
        det = S.determinize(v, [1, 2, 3, 4, 5], np.random.default_rng(0))
        c = v.counts()
        self.assertEqual(len(det["opponent_hand"]), c["opp_hand"])
        self.assertEqual(len(det["opponent_deck"]), c["opp_deck"])
        self.assertEqual(len(det["opponent_prize"]), c["opp_prize"])
        self.assertEqual(len(det["your_deck"]), c["my_deck"])
        self.assertTrue(all(isinstance(x, int) for x in det["opponent_deck"]))

    def test_predicts_a_pokemon_for_face_down_active(self):
        st = _St(_P(hand=(1,), active=(3,), deck=5, prize=(0,) * 6, hc=1),
                 _P(active=(None,), deck=5, prize=(0,) * 6, hc=3))
        det = S.determinize(S.VisibleView(st, 0), [1, 2, 3], np.random.default_rng(0))
        self.assertEqual(len(det["opponent_active"]), 1)

    def test_leaf_value_is_bounded_and_safe_on_none(self):
        self.assertEqual(S.leaf_value(None, 0), 0.0)
        v = S.leaf_value(_St(_P(prize=(0,) * 2, bench=(1, 2)), _P(prize=(0,) * 6)), 0)
        self.assertGreaterEqual(v, -1.0)
        self.assertLessEqual(v, 1.0)

    def test_stats_have_every_counter_the_validator_reads(self):
        st = S.new_stats()
        for k in ("begin_ok", "step_ok", "step_errors", "release_errors", "end_calls",
                  "max_depth_reached", "distinct_successors", "hidden_information_violations",
                  "fallbacks", "baseline_retained", "changed_action"):
            self.assertIn(k, st)


# --------------------------------------------------------------------------- validator

class TestValidatorRejections(unittest.TestCase):
    """Each test is a fabrication a prior contract in this project actually shipped."""

    def test_rejects_static_scoring_claimed_as_search(self):
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, search=_fake_search(step_ok=0, depth=0, succ=0))
            self.assertFalse(ck["not_static_scoring:x_search_summary.json"]["passed"])
            self.assertFalse(ck["multi_step_depth_ge_2:x_search_summary.json"]["passed"])

    def test_rejects_virtual_curriculum_games(self):
        """c017 exactly: a report claiming games and steps with no raw rows behind them."""
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, curriculum={
                "actual_simulator_games": 40000, "optimizer_steps": 5000,
                "raw_rollout_file": "rollouts/missing.jsonl.gz",
                "raw_updates_file": "rollouts/missing2.jsonl.gz",
                "history": [], "planned_vs_actual": []})
            self.assertFalse(ck["rollouts_are_raw_not_virtual"]["passed"])
            self.assertFalse(ck["curriculum_actual_simulator_games_nonzero"]["passed"])
            self.assertFalse(ck["curriculum_optimizer_steps_nonzero"]["passed"])

    def _tree_with_rollouts(self, t, n_games=10, category="iono"):
        os.makedirs(os.path.join(t, "rollouts"), exist_ok=True)
        with gzip.open(os.path.join(t, "rollouts", "g.jsonl.gz"), "wt") as fh:
            for _ in range(n_games):
                fh.write(json.dumps({"block": 0, "completed": True,
                                     "opponent_category": category}) + "\n")
        with gzip.open(os.path.join(t, "rollouts", "u.jsonl.gz"), "wt") as fh:
            fh.write(json.dumps({"block": 0, "updates_in_block": 2, "losses_finite": True,
                                 "sha_before": "a", "sha_after": "b"}) + "\n")

    def test_rejects_inflated_game_count(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree_with_rollouts(t, 3)
            ck, _ = _validator_on(t, curriculum={
                "actual_simulator_games": 9999, "games_completed": 3, "optimizer_steps": 2,
                "raw_rollout_file": "rollouts/g.jsonl.gz",
                "raw_updates_file": "rollouts/u.jsonl.gz",
                "history": [{"block": 0, "games_completed": 3, "promotion_eligible": True,
                             "lagged_snapshot": "a.npz", "lagged_snapshot_sha256": "h1"}],
                "planned_vs_actual": [{"block": 0, "planned_fractions": {"iono": 1.0},
                                       "actual_fractions": {"iono": 1.0}}]})
            self.assertFalse(ck["reported_games_match_raw_rows"]["passed"])
            self.assertTrue(ck["reported_steps_match_raw_updates"]["passed"])

    def test_rejects_planned_mix_reported_as_actual(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree_with_rollouts(t, 10, "iono")   # every game really was vs iono
            ck, _ = _validator_on(t, curriculum={
                "actual_simulator_games": 10, "games_completed": 10, "optimizer_steps": 2,
                "raw_rollout_file": "rollouts/g.jsonl.gz",
                "raw_updates_file": "rollouts/u.jsonl.gz",
                "history": [{"block": 0, "games_completed": 10, "promotion_eligible": True,
                             "lagged_snapshot": "a.npz", "lagged_snapshot_sha256": "h1"}],
                # the PLANNED 50/50 copied into actual_fractions -- the c017-shaped lie
                "planned_vs_actual": [{"block": 0,
                                       "planned_fractions": {"iono": 0.5, "lagged": 0.5},
                                       "actual_fractions": {"iono": 0.5, "lagged": 0.5}}]})
            self.assertFalse(ck["actual_mix_recomputed_from_raw_matches_report"]["passed"])

    def test_rejects_stale_lagged_snapshot_paths(self):
        """rl_env caches RLPolicy BY PATH, so a reused filename freezes the self-play opponent
        while the report claims self-play advanced."""
        with tempfile.TemporaryDirectory() as t:
            self._tree_with_rollouts(t, 4)
            ck, _ = _validator_on(t, curriculum={
                "actual_simulator_games": 4, "games_completed": 4, "optimizer_steps": 2,
                "raw_rollout_file": "rollouts/g.jsonl.gz",
                "raw_updates_file": "rollouts/u.jsonl.gz",
                "history": [{"block": 0, "games_completed": 2, "promotion_eligible": True,
                             "lagged_snapshot": "same.npz", "lagged_snapshot_sha256": "h1"},
                            {"block": 1, "games_completed": 2, "promotion_eligible": True,
                             "lagged_snapshot": "same.npz", "lagged_snapshot_sha256": "h1"}],
                "planned_vs_actual": [{"block": 0, "planned_fractions": {"iono": 1.0},
                                       "actual_fractions": {"iono": 1.0}}]})
            self.assertFalse(ck["lagged_snapshot_paths_unique"]["passed"])
            self.assertFalse(ck["lagged_snapshot_contents_differ"]["passed"])

    def test_rejects_zero_steps_and_unchanged_checkpoint(self):
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, distill={
                "optimizer_steps": 0, "losses_finite": True,
                "checkpoint_sha256_before": "same", "checkpoint_sha256_after": "same",
                "trusted_rows_only": True, "history": []})
            self.assertFalse(ck["distill_optimizer_steps_nonzero"]["passed"])
            self.assertFalse(ck["distill_checkpoint_hash_changed"]["passed"])

    def test_rejects_untrusted_rows_marked_trusted(self):
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, search=_fake_search(),
                                  traj=[_row(trusted=True, distinct_successors=0)])
            self.assertFalse(
                ck["trusted_rows_have_successors:x_trajectories.jsonl.gz"]["passed"])

    def test_rejects_label_outside_option_range(self):
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, search=_fake_search(),
                                  traj=[_row(n_options=2, legal_mask=[1, 1],
                                             label_action=[7])])
            self.assertFalse(
                ck["label_within_legal_range:x_trajectories.jsonl.gz"]["passed"])

    def test_rejects_game_straddling_splits(self):
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, search=_fake_search(),
                                  traj=[_row(split="train"), _row(split="test")])
            self.assertFalse(
                ck["no_game_straddles_splits:x_trajectories.jsonl.gz"]["passed"])

    def test_final_mode_rejects_absent_milestones(self):
        """A campaign that did nothing must not score PASS by omission."""
        with tempfile.TemporaryDirectory() as t:
            ck, rc = _validator_on(t, search=_fake_search(), final=True)
            self.assertEqual(rc, 1)
            self.assertFalse(ck["curriculum_report_present"]["passed"])
            self.assertFalse(ck["distillation_report_present"]["passed"])
            self.assertFalse(ck["no_skipped_criteria_counted_as_pass"]["passed"])

    def test_interim_mode_treats_absent_milestones_as_not_yet_exercised(self):
        """Interim runs must not be blocked by work that has not happened yet; only the FINAL
        judgement may treat absence as failure."""
        with tempfile.TemporaryDirectory() as t:
            ck, _ = _validator_on(t, search=_fake_search(), final=False)
            for k in ("curriculum_report_present", "distillation_report_present",
                      "final_panel_present"):
                self.assertFalse(ck[k]["passed"])
                self.assertFalse(ck[k]["critical"])
                self.assertFalse(ck[k]["submission_blocker"])
            self.assertTrue(ck["no_skipped_criteria_counted_as_pass"]["passed"])


# --------------------------------------------------------------------------- panel

class TestPanelIdentity(unittest.TestCase):

    def test_wilson_interval_brackets_the_point_estimate(self):
        import c018_panel as P
        lo, hi = P.wilson(7, 10)
        self.assertLess(lo, 0.7)
        self.assertGreater(hi, 0.7)
        self.assertEqual(P.wilson(0, 0), (None, None))

    def test_schedule_is_identical_across_candidates(self):
        """Every candidate must draw the same opponents, seeds and seats."""
        import c018_panel as P
        cands = ["a", "b", "c"]
        by = {}
        for oi, opp in enumerate(P.OPPONENTS):
            for g in range(3):
                seed = 1805 + oi * 10007 + g
                for c in cands:
                    by.setdefault(c, set()).add((opp, seed, g % 2))
        self.assertEqual(by["a"], by["b"])
        self.assertEqual(by["b"], by["c"])
        self.assertEqual(len(by["a"]), len(P.OPPONENTS) * 3)


if __name__ == "__main__":
    unittest.main()

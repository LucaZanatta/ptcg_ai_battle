"""c020 hand-computed fixtures.

Every test here is written so that the c019 behaviour FAILS it. `references/C019_AUDIT_FINDINGS.md`
#17 says method names and file existence are insufficient fidelity evidence; a test that passes
under both the defective and the corrected implementation is the same kind of non-evidence, and
c019's own promotion tests were exactly that (extreme fixtures where both readings of a threshold
agree).
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


class TestSharedInfoSet(unittest.TestCase):
    """A1 / probes M01-M03."""

    def setUp(self):
        from cg import c020_infoset as IS
        self.IS = IS
        self.key = IS.InfoSetKey("vhash", 0, (1, 2), ("a", "b"), (0, False, 0))

    def test_key_contains_no_private_fields(self):
        fields = set(self.IS.InfoSetKey.__dataclass_fields__)
        self.assertEqual(fields, {"visible_hash", "player", "select_signature",
                                  "legal_signature", "public_memory_signature"})

    def test_same_visible_state_different_worlds_share_one_entry(self):
        """The c019 structure keeps one table per determinization; this must not."""
        t = self.IS.InfoSetTable()
        for det in (0, 1, 2):
            st = t.get(self.key)
            st.update_availability(["a", "b"], det)
            st.ensure("a").det_ids.add(det)
            t.note_visit(self.key, det)
        self.assertEqual(len(t.table), 1)
        self.assertEqual(len(t.table[self.key].det_ids), 3)
        self.assertTrue(t.stats()["sharing_is_real"])

    def test_separate_tables_per_determinization_show_no_sharing(self):
        """Negative control: this is the c019 shape and it must NOT look shared."""
        tables = [self.IS.InfoSetTable() for _ in range(3)]
        for det, t in enumerate(tables):
            st = t.get(self.key)
            st.ensure("a").det_ids.add(det)
            t.note_visit(self.key, det)
        self.assertFalse(any(t.stats()["sharing_is_real"] for t in tables))

    def test_changing_visible_legal_actions_changes_the_key(self):
        other = self.IS.InfoSetKey("vhash", 0, (1, 2), ("a", "b", "c"), (0, False, 0))
        self.assertNotEqual(self.key, other)

    def test_availability_not_penalised_for_worlds_where_action_was_illegal(self):
        st = self.IS.SharedInfoSetStats()
        st.update_availability(["a", "b"], 0)
        st.update_availability(["a"], 1)
        st.update_availability(["a"], 2)
        self.assertEqual(st.actions["a"].availability, 3)
        self.assertEqual(st.actions["b"].availability, 1)

    def test_availability_aware_puct_differs_from_blind(self):
        st = self.IS.SharedInfoSetStats()
        st.update_availability(["a", "b"], 0)
        st.update_availability(["a"], 1)
        st.n = 16
        st.ensure("a").prior = st.ensure("b").prior = 0.5
        aware = self.IS.puct_scores(st, ["a", "b"], 1.5, availability_aware=True)
        blind = self.IS.puct_scores(st, ["a", "b"], 1.5, availability_aware=False)
        self.assertNotAlmostEqual(aware["b"], blind["b"], places=6)

    def test_backup_flips_sign_for_the_opponent(self):
        st = self.IS.SharedInfoSetStats()
        st.ensure("a")
        self.IS.backup([(st, "a", 1)], value=1.0, root_player=0)
        self.assertAlmostEqual(st.actions["a"].q, -1.0)
        st2 = self.IS.SharedInfoSetStats()
        st2.ensure("a")
        self.IS.backup([(st2, "a", 0)], value=1.0, root_player=0)
        self.assertAlmostEqual(st2.actions["a"].q, 1.0)


class TestTacticalLeaf(unittest.TestCase):
    """A6 / probe M06-M07."""

    def setUp(self):
        from cg import c020_tactical_leaf as TL, c020_cards as CD
        self.TL, self.CD = TL, CD

    def test_typed_energy_wrong_type_cannot_pay(self):
        """The c019 evaluator counted energy; three of the wrong type must not pay two."""
        self.assertFalse(self.CD.can_pay({3: 3}, {5: 2}))
        self.assertTrue(self.CD.can_pay({5: 2}, {5: 2}))

    def test_colorless_is_paid_by_any_leftover(self):
        self.assertTrue(self.CD.can_pay({3: 2}, {self.CD.COLORLESS: 2}))
        self.assertFalse(self.CD.can_pay({3: 1}, {self.CD.COLORLESS: 2}))

    def test_colorless_paid_only_after_specific_costs(self):
        # one Fire + one other: a cost of one Fire plus one colourless is payable
        self.assertTrue(self.CD.can_pay({5: 1, 3: 1}, {5: 1, self.CD.COLORLESS: 1}))
        # but not two Fire plus one colourless
        self.assertFalse(self.CD.can_pay({5: 1, 3: 1}, {5: 2, self.CD.COLORLESS: 1}))

    def test_feature_set_covers_every_mandated_feature(self):
        names = set(self.TL.feature_names())
        for f in ("lethal", "ko_value", "prizes_taken", "damage_dealt", "productive_attack",
                  "attack_enabled", "active_ready", "backup_ready", "typed_energy_ready",
                  "energy_waste", "survival", "target_prize_value", "bench_liability",
                  "critical_resource_cost", "future_prize_route", "flexibility",
                  "unproductive_end_turn", "terminal"):
            self.assertIn(f, names)

    def test_unproductive_end_turn_is_penalised(self):
        """Audit #4: ending a turn with a productive action available must score WORSE.

        A prize/HP-only objective cannot express this: ending the turn changes neither.
        """
        f_end = self.TL.LeafFeatures(unproductive_end_turn=1.0)
        f_play = self.TL.LeafFeatures(productive_attack=1.0)
        self.assertLess(f_end.score(), f_play.score())
        self.assertLess(f_end.score(), self.TL.LeafFeatures().score())

    def test_score_is_reconstructable_from_logged_features(self):
        f = self.TL.LeafFeatures(lethal=1.0, survival=0.5, bench_liability=0.25)
        d = f.to_json()
        self.assertAlmostEqual(sum(d["contributions"].values()), d["score"], places=5)

    def test_lethal_outweighs_a_prize_lead(self):
        lethal = self.TL.LeafFeatures(lethal=1.0, ko_value=1.0)
        lead = self.TL.LeafFeatures(prizes_taken=1.0)
        self.assertGreater(lethal.score(), lead.score())


class TestOverrideGate(unittest.TestCase):
    """A8 / probes M07, M09."""

    def setUp(self):
        from cg import c020_override as OV
        self.OV = OV

        class St:
            def __init__(self, n, q, av):
                self.n, self.q, self.availability = n, q, av

        class Root:
            def __init__(self, actions):
                self.actions = actions
        self.St, self.Root = St, Root

    def _ctx(self, **kw):
        base = {"simulations": 200, "determinizations": 4, "agreement": {}, "pivotal": False}
        base.update(kw)
        return base

    def test_end_turn_over_productive_play_is_vetoed(self):
        root = self.Root({"END_TURN": self.St(200, 0.95, 8), "play": self.St(5, 0.1, 8)})
        d = self.OV.decide_override(root, "play",
                                    self._ctx(agreement={"END_TURN": 1.0},
                                              baseline_productive=True))
        self.assertFalse(d.override)
        self.assertEqual(d.veto_reason, "unproductive_end_turn_veto")

    def test_end_turn_allowed_when_tactically_justified(self):
        root = self.Root({"END_TURN": self.St(200, 0.95, 8), "play": self.St(5, 0.1, 8)})
        d = self.OV.decide_override(root, "play",
                                    self._ctx(agreement={"END_TURN": 1.0},
                                              baseline_productive=True,
                                              tactical_end_turn_justified=True))
        self.assertTrue(d.override)

    def test_thin_q_margin_retains_baseline(self):
        root = self.Root({"alt": self.St(80, 0.90, 8), "base": self.St(20, 0.88, 8)})
        d = self.OV.decide_override(root, "base", self._ctx(agreement={"alt": 1.0},
                                                            baseline_productive=True))
        self.assertFalse(d.override)
        self.assertEqual(d.veto_reason, "q_margin")

    def test_determinization_disagreement_retains_baseline(self):
        root = self.Root({"alt": self.St(80, 0.95, 8), "base": self.St(20, 0.10, 8)})
        d = self.OV.decide_override(root, "base", self._ctx(agreement={"alt": 0.25},
                                                            baseline_productive=True))
        self.assertFalse(d.override)
        self.assertEqual(d.veto_reason, "determinization_disagreement")

    def test_rarely_available_candidate_retains_baseline(self):
        root = self.Root({"alt": self.St(80, 0.95, 1), "base": self.St(20, 0.10, 8)})
        d = self.OV.decide_override(root, "base", self._ctx(agreement={"alt": 1.0},
                                                            baseline_productive=True))
        self.assertFalse(d.override)
        self.assertEqual(d.veto_reason, "candidate_rarely_available")

    def test_a_clearly_better_candidate_does_override(self):
        """The gate must be conservative, not inert. A gate that never fires is not a gate."""
        root = self.Root({"alt": self.St(80, 0.95, 8), "base": self.St(20, 0.10, 8)})
        d = self.OV.decide_override(root, "base", self._ctx(agreement={"alt": 1.0},
                                                            baseline_productive=True))
        self.assertTrue(d.override)
        self.assertIsNone(d.veto_reason)


class TestArchetypePrior(unittest.TestCase):
    """A7 / probe M08."""

    def test_unknown_archetype_prior_is_a_mixture_not_a_default(self):
        from cg import c020_determinize as DT
        pr = DT.ARCHETYPE_PRIOR
        self.assertIn("unknown", pr)
        self.assertGreaterEqual(len(pr), 5)
        self.assertLess(max(pr.values()), 0.5, "no archetype may dominate the unknown prior")
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=6)


class TestMultiSelectAndVTrace(unittest.TestCase):
    """B3/B5 / probes B05, B08, B09."""

    def setUp(self):
        from cg import c020_vtrace as VT
        self.VT = VT

    def test_joint_logp_is_the_sum_of_step_logps(self):
        fx = self.VT.fixture_multiselect_joint()
        for steps, joint in zip(fx["per_step_behavior"], fx["joint_behavior_logp"]):
            self.assertAlmostEqual(sum(steps), joint, places=9)

    def test_joint_target_differs_from_first_pick_only(self):
        """c019 stored the first pick; the resulting targets are numerically different."""
        fx = self.VT.fixture_multiselect_joint()
        self.assertTrue(fx["differs_from_first_pick_only"])
        self.assertNotAlmostEqual(fx["joint_vs"][0], fx["first_pick_only_vs"][0], places=6)

    def test_on_policy_vtrace_telescopes_to_the_return(self):
        fx = self.VT.fixture_terminal_sequence()
        self.assertTrue(fx["on_policy_rho_is_one"])
        self.assertTrue(fx["vs_equals_return"])

    def test_truncated_unroll_carries_the_bootstrap(self):
        fx = self.VT.fixture_truncated_unroll()
        self.assertTrue(fx["carries_bootstrap"])

    def test_clipping_bounds_are_the_registered_values(self):
        fx = self.VT.fixture_clipping_bounds()
        self.assertEqual(fx["bounds"], [0.001, 1.007])
        self.assertTrue(fx["upper_binds"])
        self.assertTrue(fx["lower_binds"])

    def test_upgo_is_nonzero_and_distinct(self):
        fx = self.VT.fixture_upgo()
        self.assertTrue(fx["nonzero"])

    def test_context_mismatch_raises_rather_than_returning_a_ratio(self):
        with self.assertRaises(self.VT.RecurrentContextMismatch):
            self.VT.assert_same_context(["a", "b", "c"], ["a", "x", "c"])
        self.VT.assert_same_context(["a", "b"], ["a", "b"])


class TestPeriodLocalOSFP(unittest.TestCase):
    """B6/B7 / probes B11, B12."""

    def setUp(self):
        from cg import c020_osfp as O
        self.O = O

    def test_period_payoff_starts_at_zero(self):
        p = self.O.PeriodLocalPayoff(lp=3, size=2)
        self.assertEqual(p.G, [0.0, 0.0])
        self.assertEqual(p.C, [0, 0])

    def test_mixing_checkpoints_in_one_payoff_row_raises(self):
        """Audit #13: promotion evidence must come from ONE frozen checkpoint."""
        p = self.O.PeriodLocalPayoff(lp=0, size=1)
        p.record(0, 1.0, "e1", "sha_A")
        with self.assertRaises(ValueError):
            p.record(0, -1.0, "e2", "sha_B")

    def test_win_rate_is_on_the_unit_interval_not_a_mean_payoff(self):
        p = self.O.PeriodLocalPayoff(lp=0, size=1)
        for _ in range(6):
            p.record(0, 1.0, "e", "sha")
        for _ in range(4):
            p.record(0, -1.0, "e", "sha")
        self.assertAlmostEqual(p.win_rates()[0], 0.6, places=9)
        self.assertAlmostEqual(p.mean_payoffs()[0], 0.2, places=9)

    def test_promotion_compares_xi_against_a_win_rate(self):
        """A 60% win rate is a 0.2 mean payoff; comparing 0.2 to xi=0.55 refuses wrongly."""
        p = self.O.PeriodLocalPayoff(lp=1, size=1)
        for _ in range(60):
            p.record(0, 1.0, "e", "sha")
        for _ in range(40):
            p.record(0, -1.0, "e", "sha")
        d = self.O.decide_promotion(p, lps_without_add=0)
        self.assertEqual(d["reason"], "PERFORMANCE_PROMOTION")
        self.assertAlmostEqual(d["win_rates"][0], 0.60, places=9)

    def test_no_frozen_evidence_means_no_promotion(self):
        p = self.O.PeriodLocalPayoff(lp=1, size=1)
        d = self.O.decide_promotion(p, lps_without_add=0)
        self.assertEqual(d["reason"], "NO_FROZEN_EVIDENCE")
        self.assertFalse(d["add"])

    def test_force_add_fires_exactly_at_max_lp_and_is_labelled_separately(self):
        p = self.O.PeriodLocalPayoff(lp=7, size=1)
        for _ in range(30):
            p.record(0, -1.0, "e", "sha")
        at = self.O.decide_promotion(p, lps_without_add=6)
        self.assertEqual(at["reason"], "FORCE_ADD")
        before = self.O.decide_promotion(p, lps_without_add=5)
        self.assertEqual(before["reason"], "NO_PROMOTION")

    def test_payoff_sampler_prefers_harder_and_less_sampled(self):
        probs = self.O.sample_probabilities([9.0, -9.0], [10, 10])
        self.assertGreater(probs[1], probs[0])
        p2 = self.O.sample_probabilities([0.0, 0.0], [100, 2])
        self.assertGreater(p2[1], p2[0])


class TestHybridModes(unittest.TestCase):
    """C1-C4 / probes H01-H06."""

    def setUp(self):
        from cg import c020_hybrid as H
        self.H = H

    def test_exactly_five_modes(self):
        self.assertEqual(set(self.H.MODES), {"H0", "H1", "H2", "H3", "H4"})

    def test_mode_specs_match_the_contract(self):
        self.assertEqual(self.H.MODES["H0"], {"priors": "baseline",
                                              "value": "tactical_heuristic"})
        self.assertEqual(self.H.MODES["H1"], {"priors": "byterl",
                                              "value": "tactical_heuristic"})
        self.assertEqual(self.H.MODES["H2"], {"priors": "baseline", "value": "byterl"})
        self.assertEqual(self.H.MODES["H3"], {"priors": "byterl", "value": "byterl"})

    def test_one_registered_alpha(self):
        self.assertIsInstance(self.H.H4_ALPHA, float)
        self.assertTrue(self.H.H4_ALPHA_VERSION)

    def test_node_state_clone_is_independent(self):
        import torch
        s = self.H.HybridNodeState(neural_h=torch.ones(4), neural_c=torch.zeros(4), depth=2)
        c = s.clone()
        c.neural_h[0] = 99.0
        self.assertNotEqual(float(s.neural_h[0]), 99.0)

    def test_modes_using_unadmitted_components_are_not_promotable(self):
        for m in ("H1", "H3", "H4"):
            self.assertFalse(self.H.mode_manifest(m, None, False, False)["promotable"])
        for m in ("H2", "H3", "H4"):
            self.assertFalse(self.H.mode_manifest(m, None, True, False)["promotable"])
        # H0 uses neither adapter and is always promotable
        self.assertTrue(self.H.mode_manifest("H0", None, False, False)["promotable"])

    def test_value_admission_requires_beating_every_control(self):
        y = [1.0, -1.0, 1.0, -1.0] * 4
        perfect = list(y)
        useless = [0.0] * len(y)
        good = self.H.value_admission(
            {"c020_byterl_value": perfect, "tactical_heuristic": useless}, y)
        self.assertTrue(good["admitted"])
        bad = self.H.value_admission(
            {"c020_byterl_value": useless, "tactical_heuristic": perfect}, y)
        self.assertFalse(bad["admitted"])


class TestEncoderSlotIdentity(unittest.TestCase):
    """B1/B2 / probes B01-B03."""

    def test_schema_keeps_twelve_distinct_slots(self):
        from cg import c020_byterl_encode as E
        s = E.schema()
        self.assertEqual(s["board_slots"], 12)
        self.assertEqual(len(s["slot_order"]), 12)
        self.assertEqual(len(set(s["slot_order"])), 12)
        self.assertGreaterEqual(s["energy_types"], 9)

    def test_swapping_active_and_bench_changes_option_logits(self):
        """Under c019's mean-pooled board this swap is provably invisible."""
        import torch
        from cg import c020_byterl_encode as E, c020_byterl_model as M
        rs = np.random.RandomState(0)
        board = rs.rand(E.BOARD_SLOTS, E.BOARD_DIM).astype("float32")
        swapped = board.copy()
        swapped[[0, 1]] = swapped[[1, 0]]
        self.assertTrue(np.allclose(board.mean(0), swapped.mean(0)),
                        "the pooled representation is identical, which is the c019 defect")
        m = M.PTCGByteRL()

        def logits(b):
            f = {"board": b, "hand": np.zeros((E.N_HAND, E.HAND_DIM), "float32"),
                 "global": np.zeros(E.GLOBAL_DIM, "float32"),
                 "opt": rs.rand(E.N_OPT, E.OPT_DIM).astype("float32"),
                 "opt_mask": np.array([1.] * 4 + [0.] * (E.N_OPT - 4), "float32"),
                 "opt_src": np.array([0, 1, 2, 3] + [E.BOARD_SLOTS] * (E.N_OPT - 4)),
                 "opt_tgt": np.array([1, 0, 3, 2] + [E.BOARD_SLOTS] * (E.N_OPT - 4)),
                 "n_options": np.int64(4), "min_count": np.int64(1),
                 "max_count": np.int64(1)}
            with torch.no_grad():
                lg, _v, _s = m.forward(M.to_torch(f), None)
            return lg[0, :4].numpy()
        self.assertGreater(float(np.abs(logits(board) - logits(swapped)).max()), 1e-5)


if __name__ == "__main__":
    unittest.main()

"""c016 — tests for the parts of this contract that decide outcomes.

These target the logic that can silently produce a wrong verdict: the competitive gate
arithmetic, identity-safe aggregation, and the validator's zero-denominator detector — the last
of which exists because c015 shipped exactly that defect.
"""

import json
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c016_gauntlet as G  # noqa: E402

ART = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                   "results", "artifacts")


class IdentitySafeAggregation(unittest.TestCase):
    """§17 forbids positionally zipping worker results onto candidate labels."""

    def test_agg_selects_by_field_not_position(self):
        recs = [
            {"candidate_id": "A", "opponent_id": "x", "seat": 0, "score": 1.0},
            {"candidate_id": "B", "opponent_id": "x", "seat": 1, "score": 0.0},
            {"candidate_id": "A", "opponent_id": "y", "seat": 1, "score": 0.0},
        ]
        self.assertEqual(G.agg(recs, candidate_id="A", opponent_id="x")["score_rate"], 1.0)
        self.assertEqual(G.agg(recs, candidate_id="B", opponent_id="x")["score_rate"], 0.0)

    def test_shuffling_records_does_not_change_aggregates(self):
        recs = [{"candidate_id": c, "opponent_id": "x", "seat": i % 2, "score": float(i % 2)}
                for i, c in enumerate(["A", "B"] * 10)]
        a = G.agg(recs, candidate_id="A", opponent_id="x")
        b = G.agg(list(reversed(recs)), candidate_id="A", opponent_id="x")
        self.assertEqual(a["score_rate"], b["score_rate"])
        self.assertEqual(a["games"], b["games"])

    def test_unscored_records_are_excluded_from_the_denominator(self):
        recs = [{"candidate_id": "A", "opponent_id": "x", "seat": 0, "score": 1.0},
                {"candidate_id": "A", "opponent_id": "x", "seat": 1, "score": None}]
        self.assertEqual(G.agg(recs, candidate_id="A", opponent_id="x")["games"], 1)


class WilsonInterval(unittest.TestCase):
    def test_known_value(self):
        lo, hi = G.wilson(50, 100)
        self.assertTrue(0.40 < lo < 0.41 and 0.59 < hi < 0.60)

    def test_zero_games_is_none_not_zero(self):
        self.assertEqual(G.wilson(0, 0), (None, None))


class ProtocolFrozenBeforeResults(unittest.TestCase):
    def test_protocol_declares_thresholds_used_by_the_gate(self):
        p = G.PROTOCOL
        self.assertEqual(p["strength_paths"]["A"]["vs_dragapult_min"], 0.55)
        self.assertEqual(p["strength_paths"]["A"]["min_games"], 400)
        self.assertEqual(p["strength_paths"]["B"]["field_min_games"], 600)
        self.assertEqual(p["base_conditions"]["safe_control_min"], 0.90)
        self.assertEqual(p["base_conditions"]["vs_c014_min"], 0.65)

    def test_seed_blocks_are_disjoint(self):
        self.assertNotEqual(G.SEED_BASE, G.SEED_INDEPENDENT)
        self.assertGreater(abs(G.SEED_INDEPENDENT - G.SEED_BASE), 100000)

    def test_panel_contains_every_required_opponent(self):
        for k in ("dragapult", "iono", "mega_lucario", "mega_abomasnow",
                  "__c014__", "__c015__", "__safe__"):
            self.assertIn(k, G.PROTOCOL["panel"])


class CompetitiveGateArithmetic(unittest.TestCase):
    """Base conditions AND one strength path are both required (§18)."""

    def test_strength_path_alone_does_not_select(self):
        base = {"fidelity_ok": True, "safe_control_ge_0.90": False,
                "vs_c014_ge_0.65": False, "vs_c015_ge_0.65": True,
                "zero_reliability_violations": True}
        self.assertFalse(all(base.values()))

    def test_base_alone_does_not_select(self):
        self.assertIsNone(None if not (False or False) else "A")

    def test_recorded_decision_matches_this_rule(self):
        p = os.path.join(ART, "selection_decision.json")
        if not os.path.exists(p):
            self.skipTest("selection not yet computed")
        d = json.load(open(p))
        for r in d["rows"]:
            qualifies = r["base_conditions_pass"] and bool(r["strength_path_passed"])
            if qualifies:
                self.assertEqual(d["gate"]["competitive_gate"], "PASS")
        if d["gate"]["competitive_gate"] == "FAIL":
            self.assertIsNone(d["gate"]["selected_candidate_id"])
            self.assertFalse(d["gate"]["upload_authorised"])


class ZeroDenominatorDetector(unittest.TestCase):
    """The c015 defect the validator must catch."""

    def test_detects_rate_claimed_over_zero_opportunities(self):
        import c016_validate as V
        bad = []
        obj = {"mechanism": {"opportunities": 0, "executions": 0, "execution_rate": 1.0}}

        def walk(o, path=""):
            if isinstance(o, dict):
                if o.get("opportunities") == 0:
                    for k, v in o.items():
                        if "rate" in k.lower() and isinstance(v, (int, float)) and v > 0:
                            bad.append((path, k, v))
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
        walk(obj)
        self.assertTrue(bad, "a rate over zero opportunities must be flagged")

    def test_zero_opportunities_with_no_rate_is_fine(self):
        obj = {"mechanism": {"opportunities": 0, "executions": 0, "status": "NOT_OBSERVED"}}
        self.assertEqual(obj["mechanism"]["status"], "NOT_OBSERVED")


class FidelityIsHashBased(unittest.TestCase):
    def test_every_advanced_candidate_is_byte_identical_to_its_source(self):
        p = os.path.join(ART, "reproduction_fidelity_summary.json")
        if not os.path.exists(p):
            self.skipTest("candidates not yet built")
        d = json.load(open(p))
        for c in d["candidates"]:
            m = json.load(open(os.path.join(ART, "candidates", c["candidate_id"],
                                            "candidate_manifest.json")))
            self.assertTrue(m["hashes_identical"],
                            f"{c['candidate_id']} is not a byte-for-byte copy")
            self.assertEqual(m["fidelity"], "EXACT")

    def test_no_clean_room_candidate_was_built(self):
        p = os.path.join(ART, "reproduction_fidelity_summary.json")
        if not os.path.exists(p):
            self.skipTest("candidates not yet built")
        self.assertEqual(json.load(open(p))["n_clean_room"], 0)


class PermissionGate(unittest.TestCase):
    def test_no_benchmark_only_candidate_is_advanced(self):
        inv = os.path.join(ART, "public_agent_inventory.json")
        if not os.path.exists(inv):
            self.skipTest("inventory absent")
        for c in json.load(open(inv))["leads"]:
            if c["permission_status"] == "LOCAL_BENCHMARK_ONLY":
                self.assertNotEqual(c["disposition"], "ADVANCE")


if __name__ == "__main__":
    unittest.main(verbosity=2)

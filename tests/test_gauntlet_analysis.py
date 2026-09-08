"""Analysis + tactical-mining tool tests over synthetic captures (stdlib)."""

import gzip
import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import tools.analyze_gauntlet as ag
import tools.mine_tactical_failures as mtf


def _terminal(gid, c0, c1, winner_seat):
    w = "draw" if winner_seat is None else (c0 if winner_seat == 0 else c1)
    return {"schema_version": 2, "record_type": "game_terminal", "run_id": "r", "game_id": gid,
            "phase": "gauntlet", "pair_id": f"{c0}|{c1}",
            "seat_candidate_ids": {"0": c0, "1": c1}, "terminal_type": "normal_win",
            "winner_seat": winner_seat, "winner_candidate": w,
            "reliability": {"0": {"candidate_id": c0, "invalid_selections": 0, "agent_error": False, "timeout": False},
                            "1": {"candidate_id": c1, "invalid_selections": 0, "agent_error": False, "timeout": False}},
            "env_exception": None, "decisions_by_seat": {"0": 3, "1": 3},
            "latency_ns_by_seat": {"0": [1000, 2000, 3000], "1": [1000, 2000, 3000]},
            "fallback_by_seat": {"0": 3, "1": 0}}


def _write_gz(records, path):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


class TestAnalyze(unittest.TestCase):
    def _capture(self, d):
        # A beats B in both seat orders (A strong). 20 games each orientation.
        recs = []
        for i in range(20):
            recs.append(_terminal(f"gA{i}", "A", "B", 0))   # A seat0 wins
        for i in range(20):
            recs.append(_terminal(f"gB{i}", "B", "A", 1))   # A seat1 wins
        _write_gz(recs, os.path.join(d, "gauntlet_games.jsonl.gz"))

    def test_ranking_selection_and_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            self._capture(d)
            dec1, _ = ag.analyze(d, d)
            self.assertEqual(dec1["candidate_rankings"][0], "A")
            self.assertEqual(dec1["primary_baseline"], "A")
            self.assertEqual(dec1["backup_baseline"], "B")
            self.assertEqual(dec1["reliability_gate"], {"A": True, "B": True})
            bt1 = json.load(open(os.path.join(d, "bradley_terry_ranking.json")))
            # reproducible: re-run yields identical BT ranking
            ag.analyze(d, d)
            bt2 = json.load(open(os.path.join(d, "bradley_terry_ranking.json")))
            self.assertEqual(bt1["ranking"], bt2["ranking"])
            self.assertTrue(all(v > 0 for v in bt1["strengths"].values()))  # finite/positive

    def test_reliability_gate_blocks_primary(self):
        with tempfile.TemporaryDirectory() as d:
            recs = []
            for i in range(20):
                t = _terminal(f"g{i}", "A", "B", 0)
                if i == 0:  # A commits one invalid selection -> ineligible
                    t["reliability"]["0"]["invalid_selections"] = 1
                recs.append(t)
            for i in range(20):
                recs.append(_terminal(f"h{i}", "B", "A", 1))
            _write_gz(recs, os.path.join(d, "gauntlet_games.jsonl.gz"))
            dec, _ = ag.analyze(d, d)
            self.assertFalse(dec["reliability_gate"]["A"])
            self.assertNotEqual(dec["primary_baseline"], "A")  # A cannot be primary


class TestMineTactical(unittest.TestCase):
    def test_finds_declined_attack(self):
        with tempfile.TemporaryDirectory() as d:
            # MAIN decision: options include an ATTACK (type 13) but chose option 0 (ATTACH type 8).
            dec = {"schema_version": 2, "record_type": "decision", "candidate_id": "det_starter",
                   "game_id": "g", "phase": "gauntlet", "select_context": 0, "context_name": "MAIN",
                   "min_count": 1, "max_count": 1, "legal_option_count": 3,
                   "option": [{"type": 8}, {"type": 13, "attackId": 5}, {"type": 14}],
                   "selected_indices": [0]}
            noise = dict(dec, select_context=7, option=[{"type": 3}])  # non-MAIN, ignored
            _write_gz([dec, noise], os.path.join(d, "gauntlet_games.jsonl.gz"))
            out = os.path.join(d, "t.jsonl")
            summ = mtf.mine(d, out, "det_starter")
            self.assertEqual(summ["attack_available_not_taken"], 1)
            lines = [json.loads(x) for x in open(out)]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["failure"], "declined_available_attack")
            self.assertEqual(lines[0]["attack_option_indices"], [1])


if __name__ == "__main__":
    unittest.main()

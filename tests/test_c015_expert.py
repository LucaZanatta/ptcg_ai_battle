"""c015 AC-03 — focused tests for the anti-meta deck's highest-risk decisions and BOTH
counter mechanisms.

§11 requires the two mechanisms to be visible in inspectable rule code; these tests assert they
are also *behaviourally* present, including the two measurement bugs that made them read as
absent during development.
"""

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c015_iono_expert as X  # noqa: E402

DECK = [int(x) for x in open(os.path.join(
    _REPO, "contracts/c015_anti_meta_deck_agent_v0/results/artifacts",
    "anti_meta_deck.csv")) if x.strip()]


def sel(context, options, lo=1, hi=1):
    return {"context": context, "option": options, "minCount": lo, "maxCount": hi}


def obs(select, hand=(), active=(), bench=(), discard=(), op_active=(), op_bench=(),
        stadium=None, supporter=False, energy=False):
    def poke(cid, energies=0):
        return {"id": cid, "energyCards": [{"id": X.BASIC_L_ENERGY}] * energies,
                "energies": [0] * energies, "hp": 100, "maxHp": 100}
    return {"select": select,
            "current": {"yourIndex": 0, "turn": 3, "stadium": stadium,
                        "supporterPlayed": supporter, "energyAttached": energy,
                        "looking": None,
                        "players": [
                            {"hand": [{"id": c} for c in hand],
                             "active": [poke(*c) if isinstance(c, tuple) else poke(c)
                                        for c in active],
                             "bench": [poke(*c) if isinstance(c, tuple) else poke(c)
                                       for c in bench],
                             "discard": [{"id": c} for c in discard],
                             "prize": [1] * 6, "benchMax": 5},
                            {"hand": [], "active": [poke(c) for c in (op_active or [169])],
                             "bench": [poke(c) for c in op_bench],
                             "discard": [], "prize": [1] * 6, "benchMax": 5}]}}


class DeckIntegrity(unittest.TestCase):
    def test_exactly_60_cards(self):
        self.assertEqual(len(DECK), 60)

    def test_distinct_from_c014_and_not_dragapult(self):
        import hashlib
        h = hashlib.sha256(("\n".join(map(str, DECK)) + "\n").encode()).hexdigest()
        c14 = open(os.path.join(
            _REPO, "contracts/c014_public_meta_baseline_and_rapid_submission/results",
            "artifacts/selected_deck.sha256")).read().split()[0]
        self.assertNotEqual(h, c14)
        self.assertNotIn(119, DECK)   # Dreepy
        self.assertNotIn(190, DECK)   # Archaludon ex — c014's win condition

    def test_contains_both_mechanism_cards(self):
        self.assertIn(X.IONOS_BELLIBOLT_EX, DECK)   # Mechanism A
        self.assertIn(X.IONOS_VOLTORB, DECK)        # Mechanism B
        self.assertGreaterEqual(DECK.count(X.BASIC_L_ENERGY), 20)


class MechanismA(unittest.TestCase):
    """Electric Streamer outranks every other action while a {L} is in hand."""

    def test_ability_beats_all_other_main_actions(self):
        opts = [{"type": X.O_END},
                {"type": X.O_PLAY, "index": 0},
                {"type": X.O_ATTACK, "damage": 230},
                {"type": X.O_ABILITY}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.BASIC_L_ENERGY],
                      active=[X.IONOS_BELLIBOLT_EX], bench=[X.IONOS_VOLTORB]))
        self.assertEqual(r, [3])

    def test_availability_requires_energy_in_hand_and_bellibolt(self):
        e = X.build(DECK)
        self.assertTrue(e._mechanism_a_electric_streamer(
            {"l_energy_in_hand": 1, "bellibolt_in_play": True}))
        self.assertFalse(e._mechanism_a_electric_streamer(
            {"l_energy_in_hand": 0, "bellibolt_in_play": True}))
        self.assertFalse(e._mechanism_a_electric_streamer(
            {"l_energy_in_hand": 3, "bellibolt_in_play": False}))


class MechanismB(unittest.TestCase):
    """Voltaic Chain scales +20 per {L} on ALL my Pokemon. The engine reports its static
    damage as 20, so the scaled value must be computed or the attack is never chosen."""

    def test_damage_scales_with_total_energy_in_play(self):
        e = X.build(DECK)
        o = obs(sel(X.C_MAIN, [{"type": X.O_END}]),
                active=[(X.IONOS_VOLTORB, 2)], bench=[(X.IONOS_BELLIBOLT_EX, 3)])
        me = o["current"]["players"][0]
        self.assertEqual(e._total_l_energy(me), 5)
        self.assertEqual(e._mechanism_b_voltaic_chain_damage(me), 20 + 20 * 5)

    def test_scaled_voltaic_chain_beats_a_higher_static_attack(self):
        # static: Voltaic Chain 20 vs Tiny Charge 30. Scaled with 5 energy: 120 vs 30.
        opts = [{"type": X.O_ATTACK, "damage": 30},
                {"type": X.O_ATTACK, "damage": 20}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), active=[(X.IONOS_VOLTORB, 3)],
                      bench=[(X.IONOS_BELLIBOLT_EX, 2)], energy=True))
        self.assertEqual(r, [1], "the scaled attack must win, or Mechanism B never fires")

    def test_static_damage_alone_would_choose_wrongly(self):
        """Negative control for the real bug: ranking by the static field picks 30 over 20."""
        static = [30, 20]
        self.assertEqual(max(range(2), key=lambda i: static[i]), 0)


class SequencingAndLiability(unittest.TestCase):
    def test_bellibolt_evolution_outranks_development_plays(self):
        opts = [{"type": X.O_PLAY, "index": 0},
                {"type": X.O_EVOLVE, "index": 1},
                {"type": X.O_END}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.IONOS_BELLIBOLT_EX],
                      active=[X.IONOS_TADBULB], bench=[X.IONOS_VOLTORB], energy=True))
        self.assertEqual(r, [1])

    def test_benching_outranks_items_when_bench_empty(self):
        opts = [{"type": X.O_PLAY, "index": 0},
                {"type": X.O_PLAY, "index": 1},
                {"type": X.O_END}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.IONOS_TADBULB],
                      active=[X.IONOS_VOLTORB], bench=[], energy=True))
        self.assertEqual(r, [1])

    def test_attack_ranks_below_development(self):
        opts = [{"type": X.O_ATTACK, "damage": 230}, {"type": X.O_PLAY, "index": 0}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.BUDDY_BUDDY_POFFIN],
                      active=[X.IONOS_BELLIBOLT_EX], bench=[X.IONOS_VOLTORB], energy=True))
        self.assertEqual(r, [1], "attacking ends the turn, so development comes first")

    def test_setup_leads_with_tadbulb(self):
        opts = [{"type": X.O_CARD, "area": 2, "index": 0, "playerIndex": 0},
                {"type": X.O_CARD, "area": 2, "index": 1, "playerIndex": 0}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_SETUP_ACTIVE, opts), hand=[X.IONOS_VOLTORB, X.IONOS_TADBULB]))
        self.assertEqual(r, [1])

    def test_discard_never_dumps_the_engine(self):
        self.assertEqual(X.DISCARD_PREFERENCE[-1], X.IONOS_BELLIBOLT_EX)
        self.assertEqual(X.DISCARD_PREFERENCE[-2], X.IONOS_TADBULB)


class OpponentInference(unittest.TestCase):
    def test_detects_unevolved_target_line(self):
        e = X.build(DECK)
        o = obs(sel(X.C_MAIN, [{"type": X.O_END}]), op_active=[169])
        info = e._target_metal_line_present(o["current"]["players"][1])
        self.assertTrue(info["target_archetype_detected"])
        self.assertTrue(info["unevolved_duraludon_present"])
        self.assertFalse(info["archaludon_present"])


class LegalityAndFallback(unittest.TestCase):
    def test_unknown_context_falls_back_legally(self):
        e = X.build(DECK)
        r = e.act(obs(sel(9999, [{"type": X.O_CARD}, {"type": X.O_CARD}], lo=1, hi=1)))
        self.assertEqual(len(r), 1)
        self.assertEqual(e.n_fallback, 1)

    def test_multiselect_respects_bounds(self):
        e = X.build(DECK)
        opts = [{"type": X.O_CARD, "area": 2, "index": i, "playerIndex": 0} for i in range(5)]
        r = e.act(obs(sel(X.C_TO_HAND, opts, lo=2, hi=3), hand=[X.BASIC_L_ENERGY] * 5))
        self.assertTrue(2 <= len(r) <= 3)
        self.assertEqual(len(set(r)), len(r))

    def test_new_game_resets_counters(self):
        e = X.build(DECK)
        e.mech_a_executions = 42
        r = e.act({"select": None})
        self.assertEqual(len(r), 60)
        self.assertEqual(e.mech_a_executions, 0)

    def test_determinism(self):
        o = obs(sel(X.C_MAIN, [{"type": X.O_PLAY, "index": 0}, {"type": X.O_END}]),
                hand=[X.ULTRA_BALL], active=[X.IONOS_TADBULB], bench=[X.IONOS_VOLTORB])
        self.assertEqual(X.build(DECK).act(o), X.build(DECK).act(o))


class NoForbiddenTechniques(unittest.TestCase):
    def test_no_search_or_learning_in_source(self):
        src = open(os.path.join(_REPO, "tools", "c015_iono_expert.py")).read().lower()
        for bad in ("import torch", "mcts", "expectimax", "minimax", "rollout(",
                    "tensorflow", "sklearn"):
            self.assertNotIn(bad, src)

    def test_does_not_import_the_c014_expert(self):
        src = open(os.path.join(_REPO, "tools", "c015_iono_expert.py")).read()
        self.assertNotIn("c014_archaludon_expert", src,
                         "§6 forbids a shared multi-deck framework")


if __name__ == "__main__":
    unittest.main(verbosity=2)

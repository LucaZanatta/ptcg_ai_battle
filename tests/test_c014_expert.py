"""c014 AC-03 — focused tests for the highest-risk decision categories of the selected deck.

§10 asks for focused tests on the selected deck's risky decisions, not a universal rule-engine
suite. The three deck-specific inversions are tested directly, because each is a rule a generic
agent gets backwards and each was a real bug or near-bug during implementation.
"""

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c014_archaludon_expert as X  # noqa: E402

DECK = [int(x) for x in open(os.path.join(
    _REPO, "contracts/c014_public_meta_baseline_and_rapid_submission/results/artifacts",
    "selected_deck.csv")) if x.strip()]


def sel(context, options, lo=1, hi=1):
    return {"context": context, "option": options, "minCount": lo, "maxCount": hi}


def obs(select, hand=(), active=(), bench=(), discard=(), stadium=None,
        supporter=False, energy=False):
    def poke(cid):
        return {"id": cid, "energyCards": [], "energies": [], "hp": 100, "maxHp": 100}
    return {"select": select,
            "current": {"yourIndex": 0, "turn": 3, "stadium": stadium,
                        "supporterPlayed": supporter, "energyAttached": energy,
                        "looking": None,
                        "players": [
                            {"hand": [{"id": c} for c in hand],
                             "active": [poke(c) for c in active],
                             "bench": [poke(c) for c in bench],
                             "discard": [{"id": c} for c in discard],
                             "prize": [1] * 6, "benchMax": 5},
                            {"hand": [], "active": [poke(X.DURALUDON)], "bench": [],
                             "discard": [], "prize": [1] * 6, "benchMax": 5}]}}


class DeckIntegrity(unittest.TestCase):
    def test_deck_is_exactly_60_cards(self):
        self.assertEqual(len(DECK), 60)

    def test_deck_is_not_dragapult(self):
        # Dreepy/Drakloak/Dragapult ex ids from the c005 teacher list
        self.assertNotIn(119, DECK)
        self.assertNotIn(120, DECK)

    def test_deck_contains_the_evolution_line(self):
        self.assertIn(X.DURALUDON, DECK)
        self.assertIn(X.ARCHALUDON_EX, DECK)


class EvolutionIsTopPriority(unittest.TestCase):
    """Evolving into Archaludon ex is the highest-value action: Assemble Alloy makes it an
    energy gain as well as a body upgrade."""

    def test_evolve_beats_every_other_main_action(self):
        opts = [{"type": X.O_END},
                {"type": X.O_PLAY, "index": 0},
                {"type": X.O_ATTACK},
                {"type": X.O_EVOLVE, "index": 1}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.ARCHALUDON_EX],
                      active=[X.DURALUDON], bench=[X.DURALUDON]))
        self.assertEqual(r, [3])


class AttachmentOutranksCardPlays(unittest.TestCase):
    """The regression that mattered: with ATTACH below card plays the agent emptied its hand
    every turn, never attached energy, and therefore never attacked at all."""

    def test_attach_beats_item_plays_when_energy_not_yet_attached(self):
        opts = [{"type": X.O_PLAY, "index": 0},      # Ultra Ball
                {"type": X.O_ATTACH, "index": 1},
                {"type": X.O_END}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.BASIC_M_ENERGY],
                      active=[X.DURALUDON], bench=[X.DURALUDON], energy=False))
        self.assertEqual(r, [1], "attachment must outrank item plays")

    def test_attach_is_deprioritised_once_spent(self):
        opts = [{"type": X.O_PLAY, "index": 0},
                {"type": X.O_ATTACH, "index": 1},
                {"type": X.O_END}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.BASIC_M_ENERGY],
                      active=[X.DURALUDON], bench=[X.DURALUDON], energy=True))
        self.assertEqual(r, [0], "a second attachment is not legal value")


class DiscardBanksEnergy(unittest.TestCase):
    """Deck-specific inversion: Assemble Alloy recovers 2 Basic {M} from the DISCARD, so
    discarding energy is banking it. A generic agent discards energy last."""

    def test_basic_metal_energy_is_discarded_before_other_cards(self):
        opts = [{"type": X.O_CARD, "area": 2, "index": 0, "playerIndex": 0},   # Ultra Ball
                {"type": X.O_CARD, "area": 2, "index": 1, "playerIndex": 0}]   # {M} Energy
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_DISCARD, opts, lo=1, hi=1),
                      hand=[X.ULTRA_BALL, X.BASIC_M_ENERGY], active=[X.DURALUDON]))
        self.assertEqual(r, [1])

    def test_duraludon_is_discarded_last(self):
        self.assertEqual(X.DISCARD_PREFERENCE[-1], X.DURALUDON)
        self.assertEqual(X.DISCARD_PREFERENCE[0], X.BASIC_M_ENERGY)


class BenchLiability(unittest.TestCase):
    """An empty bench loses the game outright on a knockout, and this deck runs only 5 Basic
    Pokemon in 60 cards."""

    def test_benching_outranks_items_when_bench_is_empty(self):
        opts = [{"type": X.O_PLAY, "index": 0},      # Ultra Ball
                {"type": X.O_PLAY, "index": 1},      # Duraludon
                {"type": X.O_END}]
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_MAIN, opts), hand=[X.ULTRA_BALL, X.DURALUDON],
                      active=[X.CINDERACE], bench=[], energy=True))
        self.assertEqual(r, [1])


class SetupAndPromotion(unittest.TestCase):
    def test_cinderace_preferred_as_setup_active(self):
        opts = [{"type": X.O_CARD, "area": 2, "index": 0, "playerIndex": 0},   # Duraludon
                {"type": X.O_CARD, "area": 2, "index": 1, "playerIndex": 0}]   # Cinderace
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_SETUP_ACTIVE, opts), hand=[X.DURALUDON, X.CINDERACE]))
        self.assertEqual(r, [1], "Explosiveness is the only way Cinderace ever enters play")

    def test_promotion_prefers_archaludon(self):
        opts = [{"type": X.O_CARD, "area": 5, "index": 0, "playerIndex": 0},   # Relicanth
                {"type": X.O_CARD, "area": 5, "index": 1, "playerIndex": 0}]   # Archaludon
        e = X.build(DECK)
        r = e.act(obs(sel(X.C_SWITCH, opts), bench=[X.RELICANTH, X.ARCHALUDON_EX]))
        self.assertEqual(r, [1])


class LegalityAndFallback(unittest.TestCase):
    def test_unknown_context_falls_back_legally(self):
        e = X.build(DECK)
        r = e.act(obs(sel(9999, [{"type": X.O_CARD}, {"type": X.O_CARD}], lo=1, hi=1)))
        self.assertEqual(len(r), 1)
        self.assertTrue(all(0 <= i < 2 for i in r))
        self.assertEqual(e.n_fallback, 1)

    def test_malformed_state_does_not_raise(self):
        e = X.build(DECK)
        r = e.act({"select": sel(X.C_MAIN, [{"type": X.O_END}, {"type": X.O_PLAY}], 1, 1)})
        self.assertEqual(len(r), 1)

    def test_multiselect_respects_min_and_max(self):
        e = X.build(DECK)
        opts = [{"type": X.O_CARD, "area": 2, "index": i, "playerIndex": 0} for i in range(5)]
        r = e.act(obs(sel(X.C_TO_HAND, opts, lo=2, hi=3),
                      hand=[X.BASIC_M_ENERGY] * 5))
        self.assertGreaterEqual(len(r), 2)
        self.assertLessEqual(len(r), 3)
        self.assertEqual(len(set(r)), len(r))

    def test_deck_returned_on_none_select_and_state_resets(self):
        e = X.build(DECK)
        e.n_decisions = 99
        r = e.act({"select": None})
        self.assertEqual(len(r), 60)
        self.assertEqual(e.n_decisions, 0, "a new game must reset per-game counters")

    def test_determinism_same_state_same_choice(self):
        o = obs(sel(X.C_MAIN, [{"type": X.O_PLAY, "index": 0}, {"type": X.O_END}]),
                hand=[X.ULTRA_BALL], active=[X.DURALUDON], bench=[X.DURALUDON])
        a = X.build(DECK).act(o)
        b = X.build(DECK).act(o)
        self.assertEqual(a, b)


class NoForbiddenTechniques(unittest.TestCase):
    def test_source_contains_no_search_or_learning(self):
        src = open(os.path.join(_REPO, "tools", "c014_archaludon_expert.py")).read().lower()
        for bad in ("import torch", "mcts", "expectimax", "minimax", "rollout(",
                    "tensorflow", "sklearn"):
            self.assertNotIn(bad, src, f"§6 forbids {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

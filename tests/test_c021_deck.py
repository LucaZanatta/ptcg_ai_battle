"""c021 B2 fixtures — deck-construction legality, including the defects it must reject."""
import os, sys
import numpy as np
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cg import c020_cards as CD
from cg import c021_byterl_deck as D


@pytest.fixture(scope="module")
def pool():
    return D.CardPool.from_archetypes()


def test_reference_deck_is_legal(pool):
    ok, det = D.legality(D.greedy_reference_deck(pool), pool)
    assert ok, det
    assert det["size"] == 60 and det["basic_pokemon"] >= 1


def test_energy_exemption_is_structural_not_name_based(pool):
    """Regression: 'Energy Retrieval' is a Trainer and MUST be capped at 4."""
    assert 1118 in pool.card_ids, "Energy Retrieval expected in the pool"
    assert 1118 not in pool.basic_energy, "Trainer classified as uncapped basic energy"
    for cid in pool.basic_energy:
        assert int(getattr(CD.card(cid), "cardType", -1)) == D.CARD_TYPE_ENERGY


def test_twenty_copies_of_a_trainer_is_rejected(pool):
    deck = [1118] * 20 + [c for c in pool.basic_energy][:1] * 30
    deck += [next(iter(pool.basic_pokemon))] * (60 - len(deck))
    ok, det = D.legality(deck, pool)
    assert not ok and 1118 in det["over_copy_limit"]


def test_twenty_copies_of_basic_energy_is_legal(pool):
    e = sorted(pool.basic_energy)[0]
    b = sorted(pool.basic_pokemon)[0]
    ok, det = D.legality([e] * 59 + [b], pool)
    assert ok, det


def test_deck_with_no_basic_pokemon_is_rejected(pool):
    e = sorted(pool.basic_energy)[0]
    ok, det = D.legality([e] * 60, pool)
    assert not ok and not det["basics_ok"]


def test_wrong_size_and_unknown_card_rejected(pool):
    b = sorted(pool.basic_pokemon)[0]
    assert not D.legality([b] * 59, pool)[0]
    e = sorted(pool.basic_energy)[0]
    ok, det = D.legality([999999] + [e] * 58 + [b], pool)
    assert not ok and det["unknown_cards"] == [999999]


@pytest.mark.parametrize("seed", list(range(12)))
def test_sampled_decks_are_always_legal(pool, seed):
    deck, steps = D.sample_deck(pool, np.random.default_rng(seed))
    ok, det = D.legality(deck, pool)
    assert ok, det
    assert len(steps) == 60 and all(s["n_legal"] > 0 for s in steps)


def test_mask_forbids_exceeding_copy_limit(pool):
    non_energy = [c for c in pool.card_ids if c not in pool.basic_energy][0]
    m = D.legal_mask([non_energy] * 4, pool)
    assert m[pool.card_ids.index(non_energy)] == 0.0


def test_mask_forces_a_basic_on_the_final_slot(pool):
    e = sorted(pool.basic_energy)[0]
    m = D.legal_mask([e] * 59, pool)
    chosen = {pool.card_ids[i] for i in np.nonzero(m)[0]}
    assert chosen and chosen <= pool.basic_pokemon


def test_serialize_rejects_short_deck(pool):
    with pytest.raises(D.IllegalDeck):
        D.serialize([1, 2, 3])

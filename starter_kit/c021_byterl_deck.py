"""c021 B2 — end-to-end PTCG deck-construction meta-environment.

`FIDELITY_RULES §4` forbids "fixed-deck battle-only training for end-to-end deck construction plus
battle", and `MANDATORY_IMPLEMENTATION B2` requires one episode to contain:

    legal deck construction -> freeze/validation -> battle init -> match -> terminal reward
    propagated to BOTH construction and battle decisions

c019 and c020 both trained battle-only on a frozen deck. That is the substitution this file
exists to prevent.

Deck legality is enforced structurally, not by hoping the policy learns it: exactly 60 cards, at
most 4 copies of any non-basic-energy card, at least one Basic Pokemon, and every card drawn from
the permitted pool. An illegal construction is rejected before the battle, never silently
repaired, so the policy receives an honest signal.
"""

from __future__ import annotations

import collections
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c020_cards as CD  # noqa: E402

DECK_SIZE = 60
MAX_COPIES = 4                 # standard construction rule for non-basic-energy cards
MIN_BASIC_POKEMON = 1
CONSTRUCTION_STEPS = DECK_SIZE  # one card chosen per step: an autoregressive construction episode


class IllegalDeck(Exception):
    """Raised rather than repaired. A silently fixed deck teaches the policy nothing."""


CARD_TYPE_ENERGY = 5


def is_basic_energy(cd) -> bool:
    """Only Basic Energy is exempt from the 4-copy cap.

    Structural, via the engine's own `cardType` field, NOT a name match. The first version of
    this function tested `"energy" in name.lower()`, which classified *Energy Retrieval* -- a
    Trainer, cardType 1 -- as uncapped, so a deck of 20 Energy Retrieval read as legal. That is
    the same defect shape as the c020 A8 end-turn veto that substring-matched words against a
    tuple of integers; see results/failures/DEFECT_substring_classification_recurrence.md.

    `cardType == 5` selects Energy. Special Energy carries its rules text as `skills` and is
    capped at 4, so the absence of skills is what distinguishes Basic. The shipped card database
    holds exactly 8 energy cards (ids 1-8), all Basic, all with zero skills; the skills test is
    kept so a future Special Energy is capped rather than silently exempted.
    """
    if cd is None:
        return False
    if int(getattr(cd, "cardType", -1) or -1) != CARD_TYPE_ENERGY:
        return False
    return not (getattr(cd, "skills", None) or [])


@dataclass
class CardPool:
    """The legal card pool for construction, derived from permitted decklists."""

    card_ids: List[int]
    basic_pokemon: set
    basic_energy: set
    meta: Dict[int, Any] = field(default_factory=dict)

    @staticmethod
    def from_archetypes(archetypes: Optional[List[str]] = None) -> "CardPool":
        from cg import c019_determinize as D19
        decks = D19.archetype_decks()
        names = archetypes or list(decks)
        ids = []
        for a in names:
            ids.extend(int(x) for x in decks.get(a, []))
        uniq = sorted(set(ids))
        basics, energies, meta = set(), set(), {}
        for cid in uniq:
            cd = CD.card(cid)
            meta[cid] = cd
            if cd is None:
                continue
            if bool(getattr(cd, "basic", False)) and int(getattr(cd, "hp", 0) or 0) > 0:
                basics.add(cid)
            if is_basic_energy(cd):
                energies.add(cid)
        return CardPool(card_ids=uniq, basic_pokemon=basics, basic_energy=energies, meta=meta)

    def size(self) -> int:
        return len(self.card_ids)


def legality(deck: List[int], pool: CardPool) -> Tuple[bool, Dict[str, Any]]:
    """Deterministic legality test. Returns (ok, per-rule detail) -- never raises."""
    counts = collections.Counter(deck)
    unknown = [c for c in counts if c not in set(pool.card_ids)]
    over = {c: n for c, n in counts.items()
            if n > MAX_COPIES and c not in pool.basic_energy}
    basics = sum(n for c, n in counts.items() if c in pool.basic_pokemon)
    detail = {
        "size": len(deck), "size_ok": len(deck) == DECK_SIZE,
        "distinct": len(counts),
        "unknown_cards": unknown[:8], "unknown_ok": not unknown,
        "over_copy_limit": over, "copies_ok": not over,
        "basic_pokemon": basics, "basics_ok": basics >= MIN_BASIC_POKEMON,
    }
    detail["legal"] = all(detail[k] for k in
                          ("size_ok", "unknown_ok", "copies_ok", "basics_ok"))
    return detail["legal"], detail


def legal_mask(partial: List[int], pool: CardPool) -> np.ndarray:
    """Which pool cards may still be added, given the partial deck.

    This is the construction-stage action mask. It is recomputed for every prefix, exactly as B4
    requires for the battle stage, so construction is autoregressive under the same rules.
    """
    counts = collections.Counter(partial)
    remaining = DECK_SIZE - len(partial)
    mask = np.zeros(len(pool.card_ids), dtype=np.float32)
    need_basic = sum(n for c, n in counts.items() if c in pool.basic_pokemon) < MIN_BASIC_POKEMON
    for i, cid in enumerate(pool.card_ids):
        if cid not in pool.basic_energy and counts.get(cid, 0) >= MAX_COPIES:
            continue
        # if the last slots are the only chance left to satisfy the basic-Pokemon rule,
        # restrict the mask to basics rather than allowing an illegal deck to be built
        if need_basic and remaining <= 1 and cid not in pool.basic_pokemon:
            continue
        mask[i] = 1.0
    if mask.sum() == 0:                      # never hand back an empty mask
        for i, cid in enumerate(pool.card_ids):
            if cid in pool.basic_energy:
                mask[i] = 1.0
        if mask.sum() == 0:
            mask[:] = 1.0
    return mask


def serialize(deck: List[int]) -> List[int]:
    """Exact submitted-deck serialization: the engine expects a flat 60-id list."""
    if len(deck) != DECK_SIZE:
        raise IllegalDeck(f"deck has {len(deck)} cards, expected {DECK_SIZE}")
    return [int(x) for x in deck]


def construction_features(partial: List[int], pool: CardPool) -> Dict[str, np.ndarray]:
    """Construction-stage observation: what is chosen so far and what remains legal."""
    counts = collections.Counter(partial)
    n = len(pool.card_ids)
    chosen = np.zeros(n, dtype=np.float32)
    for i, cid in enumerate(pool.card_ids):
        chosen[i] = min(counts.get(cid, 0), MAX_COPIES) / MAX_COPIES
    g = np.zeros(12, dtype=np.float32)
    g[0] = len(partial) / DECK_SIZE
    g[1] = (DECK_SIZE - len(partial)) / DECK_SIZE
    g[2] = sum(v for c, v in counts.items() if c in pool.basic_pokemon) / 20.0
    g[3] = sum(v for c, v in counts.items() if c in pool.basic_energy) / 20.0
    g[4] = len(counts) / max(1, n)
    g[5] = 1.0                                    # stage flag: construction
    return {"chosen": chosen, "global": g, "mask": legal_mask(partial, pool)}


def greedy_reference_deck(pool: CardPool, archetype: str = "mega_lucario") -> List[int]:
    """The frozen permitted deck, used as the construction control and legality fixture."""
    from cg import c019_determinize as D19
    d = [int(x) for x in D19.archetype_decks()[archetype]]
    if len(d) != DECK_SIZE:
        raise IllegalDeck(f"reference deck has {len(d)} cards")
    return d


def sample_deck(pool: CardPool, rng, logits_fn=None) -> Tuple[List[int], List[Dict[str, Any]]]:
    """Build one deck autoregressively, recording every step for the learner.

    `logits_fn(features) -> np.ndarray` scores the pool; when None the construction is uniform
    over the legal mask, which is the BR0/BR1 behaviour before the published random
    initialization enters at BR1_5.
    """
    deck: List[int] = []
    steps: List[Dict[str, Any]] = []
    for t in range(CONSTRUCTION_STEPS):
        feats = construction_features(deck, pool)
        mask = feats["mask"]
        if logits_fn is not None:
            logits = np.asarray(logits_fn(feats), dtype=np.float64)
            logits = np.where(mask > 0, logits, -np.inf)
            m = logits.max()
            p = np.exp(logits - m) * (mask > 0)
            p = p / p.sum() if p.sum() > 0 else mask / mask.sum()
        else:
            p = mask / mask.sum()
        idx = int(rng.choice(len(p), p=p))
        deck.append(pool.card_ids[idx])
        steps.append({"t": t, "chosen_index": idx, "card_id": pool.card_ids[idx],
                      "logp": float(np.log(max(p[idx], 1e-12))),
                      "n_legal": int((mask > 0).sum())})
    return deck, steps

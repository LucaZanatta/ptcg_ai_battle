"""c019 Branch A — legal information-set determinization (M02).

METHOD_FIDELITY A: sample hidden zones WITHOUT REPLACEMENT from a known deck multiset, reject
impossible determinizations, and never top up with duplicate filler IDs.

c018 did exactly the forbidden thing: when its candidate pool ran dry it padded with copies of
one card id, producing worlds containing eight copies of a card whose deck limit is four. Those
worlds are not merely unlikely, they are illegal, and a search that plans against them is
planning against a game that cannot occur. Here a pool that runs dry is a REJECTED world, counted
and reported.

Hidden zones are predicted from public information only: the opponent archetype is inferred from
cards it has actually revealed, and the true local opponent deck/hand/prizes are never read. The
`VisibleObservation` guard makes that structural rather than promised.
"""

from __future__ import annotations

import collections
import hashlib
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

DETERMINIZE_VERSION = "c019.determinize.v1"
ARCHETYPES = ("dragapult", "mega_lucario", "iono", "mega_abomasnow")

_DECKS: Dict[str, List[int]] = {}


def archetype_decks() -> Dict[str, List[int]]:
    """Public archetype decklists used as PRIORS over hidden zones."""
    global _DECKS
    if not _DECKS:
        from cg import teachers as T, c009_eval as ce
        for a in ARCHETYPES:
            try:
                _DECKS[a] = [int(x) for x in T.read_deck(a, ce.SOURCES)]
            except Exception:  # noqa: BLE001
                pass
    return _DECKS


@dataclass
class Determinization:
    """One legal sampled world, plus everything needed to audit it."""

    det_id: str
    archetype: str                # INFERRED label; may be "unknown"
    pool_archetype: str           # the decklist actually sampled from; always concrete
    archetype_confidence: float
    your_deck: List[int]
    your_prize: List[int]
    opponent_deck: List[int]
    opponent_prize: List[int]
    opponent_hand: List[int]
    opponent_active: List[int]
    counts: Dict[str, int] = field(default_factory=dict)
    revealed: Dict[int, int] = field(default_factory=dict)
    legal: bool = True
    rejection: Optional[str] = None

    def summary(self) -> Dict[str, Any]:
        return {"det_id": self.det_id, "archetype": self.archetype,
                "pool_archetype": self.pool_archetype,
                "confidence": self.archetype_confidence, "counts": self.counts,
                "legal": self.legal, "rejection": self.rejection,
                "sizes": {"your_deck": len(self.your_deck),
                          "your_prize": len(self.your_prize),
                          "opponent_deck": len(self.opponent_deck),
                          "opponent_prize": len(self.opponent_prize),
                          "opponent_hand": len(self.opponent_hand),
                          "opponent_active": len(self.opponent_active)}}


def classify_archetype(view: K.VisibleObservation) -> Tuple[str, float, Dict[int, int]]:
    """Infer the opponent archetype from cards it has ACTUALLY revealed."""
    decks = archetype_decks()
    seen = collections.Counter()
    for c in view.board("theirs")["active"] + view.board("theirs")["bench"]:
        if c is not None:
            seen[int(getattr(c, "id", -1))] += 1
    for c in view.discard("theirs"):
        seen[int(getattr(c, "id", -1))] += 1
    seen.pop(-1, None)
    if not decks:
        return "unknown", 0.0, dict(seen)
    scores = {}
    for name, deck in decks.items():
        ds = collections.Counter(deck)
        scores[name] = sum(min(n, ds.get(cid, 0)) for cid, n in seen.items())
    total = sum(scores.values())
    if total == 0:
        return "unknown", 0.0, dict(seen)
    best = max(scores, key=scores.get)
    return best, round(scores[best] / total, 4), dict(seen)


def _draw(pool: collections.Counter, n: int, rng) -> Optional[List[int]]:
    """Draw n cards WITHOUT replacement. Returns None if the pool cannot supply them.

    Returning None is the whole point: c018 padded here and manufactured illegal worlds.
    """
    if n <= 0:
        return []
    avail = sum(pool.values())
    if avail < n:
        return None
    flat = []
    for cid, k in pool.items():
        flat.extend([cid] * k)
    idx = rng.choice(len(flat), size=n, replace=False)
    drawn = [int(flat[i]) for i in idx]
    for c in drawn:
        pool[c] -= 1
        if pool[c] <= 0:
            del pool[c]
    return drawn


def _basic_pokemon(deck: List[int]) -> Optional[int]:
    """A Basic Pokemon id from a decklist; `search_begin` rejects a non-Pokemon Active."""
    try:
        from cg import api as A
        db = {c.cardId: c for c in A.all_card_data()}
        for cid in deck:
            c = db.get(cid)
            if c is not None and int(c.cardType) == 0 and getattr(c, "basic", False):
                return int(cid)
    except Exception:  # noqa: BLE001
        pass
    return None


def determinize(view: K.VisibleObservation, my_deck: List[int], rng,
                archetype: Optional[str] = None) -> Determinization:
    """Sample ONE legal world, or return an illegal one flagged with its rejection reason."""
    counts = view.counts()
    arch, conf, revealed = classify_archetype(view)
    if archetype:
        arch, conf = archetype, 1.0
    decks = archetype_decks()
    # when the archetype is not yet identifiable, a concrete prior list is still required to
    # sample from -- and WHICH list was used must be recorded, or the world cannot be audited
    pool_arch = arch if arch in decks else ("dragapult" if "dragapult" in decks else "__own__")
    opp_list = decks.get(pool_arch) or list(my_deck)

    det_id = hashlib.sha256(
        f"{DETERMINIZE_VERSION}|{arch}|{sorted(revealed.items())}|"
        f"{rng.integers(0, 1 << 62)}".encode()).hexdigest()[:16]

    def fail(reason) -> Determinization:
        return Determinization(det_id, arch, pool_arch, conf, [], [], [], [], [], [],
                               counts=counts, revealed=revealed, legal=False, rejection=reason)

    # --- opponent pool: their decklist minus everything they have revealed -------------
    opp_pool = collections.Counter(opp_list)
    for cid, n in revealed.items():
        if opp_pool.get(cid, 0) < n:
            # they revealed more copies than this archetype can hold -> wrong archetype
            return fail(f"revealed_exceeds_archetype:card{cid}:{n}>{opp_pool.get(cid, 0)}")
        opp_pool[cid] -= n
        if opp_pool[cid] <= 0:
            del opp_pool[cid]

    need_opp = counts["opp_hand"] + counts["opp_prize"] + counts["opp_deck"]
    if sum(opp_pool.values()) < need_opp:
        return fail(f"opponent_pool_exhausted:{sum(opp_pool.values())}<{need_opp}")

    # face-down opponent Active must be predicted as a real Basic Pokemon
    opp_active: List[int] = []
    try:
        act = view.board("theirs")["active"]
        if act and act[0] is None:
            b = _basic_pokemon(opp_list)
            if b is None:
                return fail("no_basic_pokemon_in_archetype")
            if opp_pool.get(b, 0) <= 0:
                return fail(f"no_remaining_basic_for_active:card{b}")
            opp_pool[b] -= 1
            if opp_pool[b] <= 0:
                del opp_pool[b]
            opp_active = [b]
            need_opp -= 0
    except Exception:  # noqa: BLE001
        opp_active = []

    opp_hand = _draw(opp_pool, counts["opp_hand"], rng)
    if opp_hand is None:
        return fail("opponent_hand_draw_failed")
    opp_prize = _draw(opp_pool, counts["opp_prize"], rng)
    if opp_prize is None:
        return fail("opponent_prize_draw_failed")
    opp_deck = _draw(opp_pool, counts["opp_deck"], rng)
    if opp_deck is None:
        return fail("opponent_deck_draw_failed")

    # --- own pool: our real decklist minus our own visible cards -----------------------
    mine_pool = collections.Counter(int(x) for x in my_deck)
    my_visible = collections.Counter()
    for c in view.my_hand():
        my_visible[int(getattr(c, "id", -1))] += 1
    for c in view.board("mine")["active"] + view.board("mine")["bench"]:
        if c is not None:
            my_visible[int(getattr(c, "id", -1))] += 1
    for c in view.discard("mine"):
        my_visible[int(getattr(c, "id", -1))] += 1
    my_visible.pop(-1, None)
    for cid, n in my_visible.items():
        if mine_pool.get(cid, 0) < n:
            return fail(f"own_visible_exceeds_deck:card{cid}:{n}>{mine_pool.get(cid, 0)}")
        mine_pool[cid] -= n
        if mine_pool[cid] <= 0:
            del mine_pool[cid]

    my_prize = _draw(mine_pool, counts["my_prize"], rng)
    if my_prize is None:
        return fail("own_prize_draw_failed")
    my_deck_pred = _draw(mine_pool, counts["my_deck"], rng)
    if my_deck_pred is None:
        return fail("own_deck_draw_failed")

    d = Determinization(det_id, arch, pool_arch, conf, my_deck_pred, my_prize, opp_deck,
                        opp_prize, opp_hand, opp_active, counts=counts, revealed=revealed)
    ok, why = validate(d, my_deck, opp_list)
    if not ok:
        d.legal = False
        d.rejection = why
    return d


def validate(d: Determinization, my_deck: List[int],
             opp_list: List[int]) -> Tuple[bool, Optional[str]]:
    """Exact multiplicity/count validation. No duplicate filler can survive this."""
    if len(d.your_deck) != d.counts["my_deck"]:
        return False, f"own_deck_size:{len(d.your_deck)}!={d.counts['my_deck']}"
    if len(d.your_prize) != d.counts["my_prize"]:
        return False, f"own_prize_size:{len(d.your_prize)}!={d.counts['my_prize']}"
    if len(d.opponent_deck) != d.counts["opp_deck"]:
        return False, f"opp_deck_size:{len(d.opponent_deck)}!={d.counts['opp_deck']}"
    if len(d.opponent_hand) != d.counts["opp_hand"]:
        return False, f"opp_hand_size:{len(d.opponent_hand)}!={d.counts['opp_hand']}"
    if len(d.opponent_prize) != d.counts["opp_prize"]:
        return False, f"opp_prize_size:{len(d.opponent_prize)}!={d.counts['opp_prize']}"

    # no sampled multiset may exceed its decklist's multiplicity
    limit = collections.Counter(int(x) for x in opp_list)
    used = collections.Counter(d.opponent_deck + d.opponent_prize + d.opponent_hand
                               + d.opponent_active)
    for cid, n in d.revealed.items():
        used[cid] += n
    for cid, n in used.items():
        if n > limit.get(cid, 0):
            return False, f"opp_multiplicity:card{cid}:{n}>{limit.get(cid, 0)}"

    mine_limit = collections.Counter(int(x) for x in my_deck)
    mine_used = collections.Counter(d.your_deck + d.your_prize)
    for cid, n in mine_used.items():
        if n > mine_limit.get(cid, 0):
            return False, f"own_multiplicity:card{cid}:{n}>{mine_limit.get(cid, 0)}"
    if any(n < 0 for n in used.values()) or any(n < 0 for n in mine_used.values()):
        return False, "negative_count"
    return True, None


def sample_many(view, my_deck, rng, n: int) -> Tuple[List[Determinization], Dict[str, int]]:
    """n independent worlds. Illegal ones are RETURNED and counted, never silently retried."""
    out, stats = [], collections.Counter()
    for _ in range(max(1, n)):
        d = determinize(view, my_deck, rng)
        stats["sampled"] += 1
        stats["legal" if d.legal else "rejected"] += 1
        if not d.legal:
            stats[f"reject:{(d.rejection or 'unknown').split(':')[0]}"] += 1
        out.append(d)
    return out, dict(stats)

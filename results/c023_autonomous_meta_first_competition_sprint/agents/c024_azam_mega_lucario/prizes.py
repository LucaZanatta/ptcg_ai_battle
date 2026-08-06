"""c024 — deduce which of our own cards are sitting in the prize pile.

`c023_planner._determinize` builds a concrete world by subtracting every card the observation
reveals from our known 60-card list, then *guessing* which of the remainder are prizes and which
are still in the deck. The guess is deliberately rotated so it is not systematically biased
(D5) — but it is still a guess, and a forward search that plans a winning line through a card
that is actually prized has verified a win the real game cannot reproduce.

This closes the guess whenever the observation makes it closable. It is not always closable, and
the governing rule is that **a wrong prize inference is worse than no prize inference**: every
ambiguous frame returns unknown.

## When it closes

Our unseen cards are exactly `deck + prize`. Subtracting the visible zones leaves that union, and
the two cannot be separated — *unless the deck itself becomes visible*. Several cards in this
format look into the deck (search and draw effects); on those frames `select.deck` carries the
deck's contents, and

    decklist − hand − discard − board − stadium − looking − select.deck − in-flight  ==  prizes

exactly. The count must come out equal to the number of prize slots or the frame is discarded.

## The card that is in no zone at all

While a deck-search effect resolves, the card that caused it has left the hand and has not yet
reached the discard. For those frames it is in no ordinary zone, and forgetting it makes the
remainder one card too large — which either fails the count check (a lost deduction) or, worse,
silently attributes the wrong card to the prizes. `select.effect` names it, and it is subtracted
here. `select.contextCard` is subtracted for the same reason.

Logs are deliberately *not* used to reconstruct this: `obs.logs` covers only what happened since
the previous selection, so on the second and later frames of a single resolving effect the play
event is already gone. Logs are used for one thing only — noticing that a prize was taken.
"""

from __future__ import annotations

import collections
from typing import Any, Dict, List, Optional

try:
    from cg.api import AreaType
except Exception:  # pragma: no cover - the module is importable without the engine for tests
    AreaType = None  # type: ignore


class PrizeTracker:
    """Known prize contents for one player over one game, or `None` while unknown.

    Instantiate once per game with the 60-card list, call `update` on every observation, and read
    `known()`. The tracker never returns a partial answer: it is the whole prize set or nothing.
    """

    def __init__(self, decklist: List[int]) -> None:
        self._deck = collections.Counter(int(c) for c in decklist)
        self._prized: Optional[collections.Counter] = None
        self.deductions = 0          # frames on which a fresh deduction closed
        self.claims = 0              # prize cards removed after being taken
        self.invalidations = 0       # times a maintained set went inconsistent and was dropped

    # ---------------------------------------------------------------- reading

    def known(self) -> Optional[collections.Counter]:
        return self._prized.copy() if self._prized is not None else None

    def is_prized(self, card_id: int) -> Optional[bool]:
        if self._prized is None:
            return None
        return self._prized.get(int(card_id), 0) > 0

    # ---------------------------------------------------------------- updating

    def update(self, obs: Any, mi: Optional[int] = None) -> None:
        st = getattr(obs, "current", None)
        if st is None:
            return
        if mi is None:
            mi = int(st.yourIndex)
        me = st.players[mi]

        # 1. Maintain what is already known. A prize moving to hand is the only way a card leaves
        #    the prize pile, and the log for it carries the card id.
        if self._prized is not None:
            for cid in _prizes_taken(obs, mi):
                if self._prized.get(cid, 0) <= 0:
                    # The set said this card was not prized and the game just took it from the
                    # prizes. The deduction was wrong; drop it rather than carry a lie forward.
                    self._prized = None
                    self.invalidations += 1
                    break
                self._prized[cid] -= 1
                self.claims += 1
            if self._prized is not None:
                self._prized += collections.Counter()      # drop exhausted entries
                if sum(self._prized.values()) != len(me.prize):
                    self._prized = None
                    self.invalidations += 1

        # 2. Attempt a fresh deduction. Only possible on a frame that reveals the deck.
        sel = getattr(obs, "select", None)
        if sel is None or getattr(sel, "deck", None) is None:
            return
        remain = self._deck.copy()
        for cid in _visible_ids(obs, mi):
            remain[cid] -= 1
        for c in (sel.deck or []):
            if c is not None:
                remain[int(c.id)] -= 1
        for c in (getattr(sel, "effect", None), getattr(sel, "contextCard", None)):
            if c is not None:
                remain[int(c.id)] -= 1

        if any(v < 0 for v in remain.values()):
            return                                          # inconsistent: a card seen too often
        remain += collections.Counter()
        if sum(remain.values()) != len(me.prize):
            return                                          # count does not close
        self._prized = remain
        self.deductions += 1


def _prizes_taken(obs: Any, mi: int) -> List[int]:
    out: List[int] = []
    prize = AreaType.PRIZE if AreaType is not None else 6
    hand = AreaType.HAND if AreaType is not None else 2
    for lg in (getattr(obs, "logs", None) or []):
        if getattr(lg, "playerIndex", None) != mi:
            continue
        if lg.fromArea == prize and lg.toArea == hand and lg.cardId is not None:
            out.append(int(lg.cardId))
    return out


def _visible_ids(obs: Any, mi: int) -> List[int]:
    """Every card of ours the observation puts in a zone we can read.

    Kept deliberately parallel to `c023_planner._visible_own_ids` -- the two must agree or the
    determinization and the tracker will disagree about what is left.
    """
    out: List[int] = []
    st = obs.current
    me = st.players[mi]
    for c in (me.hand or []):
        out.append(int(c.id))
    for c in me.discard:
        out.append(int(c.id))
    for p in list(me.active or []) + list(me.bench or []):
        if p is None:
            continue
        out.append(int(p.id))
        for e in p.energyCards:
            out.append(int(e.id))
        for t in p.tools:
            out.append(int(t.id))
        for pe in p.preEvolution:
            out.append(int(pe.id))
    for c in st.stadium:
        if getattr(c, "playerIndex", mi) == mi:
            out.append(int(c.id))
    if st.looking:
        for c in st.looking:
            if c is not None and getattr(c, "playerIndex", mi) == mi:
                out.append(int(c.id))
    # Prize slots are NOT subtracted. A card still in the prize pile has not been spent, so it
    # belongs to the remainder the deduction is trying to name; subtracting it here would make
    # the count come up short by exactly the number of prizes and close nothing, ever.
    return out

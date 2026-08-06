"""c024 — our own Alakazam / Dudunsparce policy. Written from the card text, not from a kernel.

Every community notebook in this repository is classified `LOCAL_BENCHMARK_ONLY` because the
Kaggle API exposes no licence for a notebook. Two of them play this 60-card list and are the two
strongest agents on our panel, so the *deck* is reused — a decklist is configuration, and this
one is public in four places — and the *policy* is written here from the competition's own card
table. No kernel source was copied.

## The archetype, in one paragraph

`EXCHANGE_RATE_CORRECTION.md` has the arithmetic. Powerful Hand costs **one** Psychic Energy and
places two damage counters per card in hand: **20 damage per card**, unbounded, from a 140 HP
Stage 2 that is worth **one prize**. Against a format of 320–340 HP Megas worth two and three
prizes, that is the inverse of the race `FAILURE_TAXONOMY` F8 says Dragapult loses. Sixteen cards
in hand one-shots Dragapult ex and Marnie's Grimmsnarl ex; seventeen one-shots Mega Lucario ex.

## What the measurement says the policy has to do

`HAND_SIZE.json`: the two reference agents declare Powerful Hand at a **mean hand of 9.9 and
10.5** — 198 and 210 damage, the same number Phantom Dive prints — while the observed maximum is
**21–22**. Only 14–16% of their attacks land at the sixteen-card one-shot threshold. The engine
is not doing this on its own, and the headroom is enormous.

So the policy's one job, stated as a number: **raise the hand size at the moment of attack.**
Three things follow from that and they drive most of the scoring below.

1. **Evolving is hand-positive.** Kadabra's Psychic Draw draws 2 when it evolves, Alakazam's
   draws 3. Playing the card costs one, so evolving into Kadabra is net +1 and into Alakazam is
   net +2 — on top of putting the attacker into play. Evolution outranks everything.
2. **Some cards pay for themselves and some do not.** Dawn fetches three (net +2), Hilda two
   (net +1), Poké Pad one (net 0). Buddy-Buddy Poffin puts two Pokémon straight onto the bench
   and never touches the hand, so it is net **−1** — worth it while the board is being built and
   a pure damage loss afterwards.
3. **Once the attack is already lethal, every further card played is 20 damage thrown away.**
   `_suppressed` is that rule: when Powerful Hand can already knock out the opponent's Active,
   nothing hand-negative is allowed to outrank the attack.

## The card the format forgot

**Neutralization Zone** prevents all attack damage to Pokémon without a Rule Box from the
opponent's ex and V Pokémon. *Every Pokémon in this deck is a one-prize Pokémon without a Rule
Box.* Against Dragapult ex, Marnie's Grimmsnarl ex or Mega Lucario ex — which is most of the
ladder above 1000 — the Zone turns off their attacks entirely. It is a single copy and it is
scored accordingly: nothing else in the list is worth as much against an ex deck.

It is not a lock. Munkidori and Froslass do their work through Abilities, which the Zone does not
touch, and that is exactly why Grimmsnarl is this archetype's bad matchup on the panel.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

from cg.api import (AreaType, CardType, OptionType, SelectContext, SelectType,
                    all_attack, all_card_data, to_observation_class)

# ---- deck ------------------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_deck_path = os.path.join(_HERE, "deck.csv")
if not os.path.exists(_deck_path):
    _deck_path = "/kaggle_simulations/agent/deck.csv"
with open(_deck_path) as _fh:
    MY_DECK = [int(x) for x in _fh if x.strip()][:60]

_CARD = {c.cardId: c for c in all_card_data()}
_ATK = {a.attackId: a for a in all_attack()}

# ---- the list, by id -------------------------------------------------------------------------
ABRA, KADABRA, ALAKAZAM = 741, 742, 743
DUNSPARCE_70, DUNSPARCE_60, DUDUNSPARCE = 305, 65, 66
BASIC_P, TELEPATH_P = 5, 19
RARE_CANDY, ENHANCED_HAMMER, BUDDY_POFFIN = 1079, 1081, 1086
NIGHT_STRETCHER, SACRED_ASH, POKE_PAD = 1097, 1129, 1152
BOSS, LANA, XEROSIC = 1182, 1184, 1197
HILDA, LILLIE, DAWN = 1225, 1227, 1231
NEUTRALIZATION_ZONE = 1247

POWERFUL_HAND = 1072
DAMAGE_PER_CARD = 20          # "2 damage counters for each card in your hand"

BASICS = {ABRA, DUNSPARCE_70, DUNSPARCE_60}
ENERGY = {BASIC_P, TELEPATH_P}

# How much we want a card *in hand*, used by every search and recovery effect. The attacker line
# comes first because the deck's whole clock is Abra -> Alakazam; energy is scarce at two basic
# and four Telepath; Dudunsparce is a draw engine, not a board piece.
WANT = {
    ALAKAZAM: 100, RARE_CANDY: 92, KADABRA: 85, ABRA: 80,
    TELEPATH_P: 78, DAWN: 74, HILDA: 70, BASIC_P: 66,
    POKE_PAD: 60, BUDDY_POFFIN: 56, DUNSPARCE_70: 50, DUNSPARCE_60: 48,
    DUDUNSPARCE: 46, BOSS: 44, NIGHT_STRETCHER: 40, NEUTRALIZATION_ZONE: 38,
    XEROSIC: 30, ENHANCED_HAMMER: 26, LANA: 22, LILLIE: 20, SACRED_ASH: 10,
}


# ---- helpers ---------------------------------------------------------------------------------

def _board(ps) -> List[Any]:
    out = [p for p in (ps.active or []) if p is not None]
    out += [p for p in (ps.bench or []) if p is not None]
    return out


def _is_rule_box(card_id: int) -> bool:
    d = _CARD.get(card_id)
    return bool(d and (d.ex or d.megaEx))


def _powerful_hand_damage(hand_size: int) -> int:
    return DAMAGE_PER_CARD * hand_size


def _alakazam_ready(me) -> Optional[Any]:
    """Our Active, if it is an Alakazam that can pay for Powerful Hand."""
    a = me.active[0] if me.active else None
    if a is None or a.id != ALAKAZAM:
        return None
    return a if len(a.energies) >= 1 else None


def _opt_hand_card(me, o) -> Optional[int]:
    """The card id a PLAY / EVOLVE / ATTACH option is spending out of hand.

    These options carry no `area`; the index is into the hand. Reading `area` here returned None
    for every PLAY option in the c023 wrapper and silently made a whole rule inert (D6a), so the
    same shape is handled explicitly rather than through a generic zone lookup.
    """
    i = getattr(o, "index", None)
    if i is None:
        return None
    try:
        return int(me.hand[i].id)
    except Exception:  # noqa: BLE001
        return None


def _target(me, o):
    """The Pokémon in play a PLAY / EVOLVE / ATTACH option acts on, via `inPlayArea`.

    This is the field that decides whether an evolution or an energy attach reaches the Active.
    The first version of this policy scored those options by the *card being spent* alone, so it
    happily evolved a benched Abra while the Active stayed a Dunsparce and attached the turn's one
    energy to a bench slot. The measured symptom was the diagnostic: our hand at attack matched
    the reference agent's exactly (9.50 against 9.51) while ATTACK was on the table in **13.5**
    decisions a game against their **25.6**. Same hand, half the attacker uptime.
    """
    area = getattr(o, "inPlayArea", None)
    i = getattr(o, "inPlayIndex", None)
    if i is None:
        return None, None
    try:
        if area == AreaType.ACTIVE:
            return me.active[i], True
        if area == AreaType.BENCH:
            return me.bench[i], False
    except Exception:  # noqa: BLE001
        return None, None
    return None, None


def _zone_card(st, mi: int, o) -> Optional[int]:
    """The card id a CARD-type option refers to, for the zone-addressed selects."""
    area = getattr(o, "area", None)
    i = getattr(o, "index", None)
    if i is None:
        return None
    pi = getattr(o, "playerIndex", None)
    ps = st.players[mi if pi is None else pi]
    try:
        if area == AreaType.HAND:
            return int(ps.hand[i].id)
        if area == AreaType.DISCARD:
            return int(ps.discard[i].id)
        if area == AreaType.ACTIVE:
            return int(ps.active[i].id)
        if area == AreaType.BENCH:
            return int(ps.bench[i].id)
    except Exception:  # noqa: BLE001
        return None
    return None


def _deck_card(sel, o) -> Optional[int]:
    """Cards offered out of the deck (search effects) live in `select.deck`, not in a player zone."""
    i = getattr(o, "index", None)
    if i is None or not sel.deck:
        return None
    for c in sel.deck:
        if c is not None and getattr(c, "serial", None) is not None:
            pass
    try:
        return int(sel.deck[i].id)
    except Exception:  # noqa: BLE001
        return None


def _card_of(sel, st, mi: int, o) -> Optional[int]:
    cid = getattr(o, "cardId", None)
    if cid is not None:
        return int(cid)
    if getattr(o, "area", None) == AreaType.DECK:
        return _deck_card(sel, o)
    return _zone_card(st, mi, o)


# ---- MAIN ------------------------------------------------------------------------------------

def _score_main(sel, st, mi: int) -> List[int]:
    me = st.players[mi]
    op = st.players[1 - mi]
    hand = len(me.hand)
    bench = len([p for p in (me.bench or []) if p is not None])
    op_active = op.active[0] if op.active else None
    turn = int(st.turn)

    ready = _alakazam_ready(me)
    dmg = _powerful_hand_damage(hand)
    # `_suppressed`: the attack already kills. Anything that costs a card costs 20 damage, and
    # 20 damage we do not need is 20 damage of overkill traded for a worse board next turn --
    # but a card that would drop us BELOW lethal is a strictly losing play, so it is refused.
    lethal_now = bool(ready and op_active is not None and dmg >= op_active.hp)
    margin = (dmg - op_active.hp) // DAMAGE_PER_CARD if (lethal_now and op_active) else 0

    # Energy is this deck's scarcest resource: six cards in sixty, one attach a turn, and every
    # attack in the list needs at least one. "Starved" means nothing in hand can be attached and
    # nothing already in play can pay for an attack.
    energy_in_hand = sum(1 for c in me.hand if c.id in ENERGY)
    energised = [p for p in _board(me) if len(p.energies) >= 1]
    energy_starved = (energy_in_hand == 0 and not energised)

    op_is_rule_box = bool(op_active and _is_rule_box(op_active.id))
    zone_is_ours = any(getattr(c, "playerIndex", None) == mi for c in (st.stadium or []))
    have_alakazam_in_hand = any(c.id == ALAKAZAM for c in me.hand)
    have_kadabra_in_hand = any(c.id == KADABRA for c in me.hand)

    scores: List[int] = []
    for o in sel.option:
        t = o.type
        s = 0

        if t == OptionType.EVOLVE:
            cid = _opt_hand_card(me, o)
            tgt, on_active = _target(me, o)
            # Alakazam draws 3 on evolving and Kadabra draws 2, so both are hand-POSITIVE after
            # paying the card. Nothing else in the deck both develops the board and grows the hand.
            s = 100000 if cid == ALAKAZAM else 90000 if cid == KADABRA else 60000
            # ...but only the Active can attack. An evolution that lands on the bench builds a
            # replacement; one that lands on the Active builds this turn's damage.
            if on_active:
                s += 6000
            elif tgt is not None and len(tgt.energies) >= 1:
                s += 2000                       # a benched piece already carrying energy is next

        elif t == OptionType.ABILITY:
            # Run Away Draw is +3 cards but shuffles the Dudunsparce away. Worth it while the hand
            # is thin; a waste of a board slot's worth of tempo once the hand is already large.
            s = 66000 if hand <= 8 else 24000

        elif t == OptionType.ATTACH:
            cid = _opt_hand_card(me, o)
            tgt, on_active = _target(me, o)
            if cid == TELEPATH_P:
                # Attaching it searches two Basic {P} onto the bench: an energy attach and two
                # free Abra in the same action.
                s = 76000
            elif cid == BASIC_P:
                s = 74000
            else:
                s = 40000
            # One energy attach per turn. Spending it anywhere but on the Pokemon that is about to
            # attack costs a whole turn of Powerful Hand, which is the single most expensive
            # mistake available in this deck.
            if tgt is None:
                s -= 20000
            elif tgt.id == ALAKAZAM:
                s += 12000 if on_active else 4000
            elif tgt.id == KADABRA and have_alakazam_in_hand:
                s += 8000 if on_active else 2000    # it evolves into the attacker next
            elif on_active:
                s += 1000
            else:
                s -= 12000
            if tgt is not None and len(tgt.energies) >= 1:
                s -= 15000                      # it can already pay Powerful Hand; one is enough

        elif t == OptionType.PLAY:
            cid = _opt_hand_card(me, o)
            if cid == RARE_CANDY and have_alakazam_in_hand:
                s = 95000                       # skips Kadabra entirely: the fastest attacker
            elif cid == NEUTRALIZATION_ZONE and op_is_rule_box and not zone_is_ours:
                # Every Pokemon in this deck is Rule-Box-free, so against an ex or Mega deck the
                # Zone turns their attacks off outright. Nothing else here is worth as much.
                s = 93000
            elif cid == DAWN:
                # Searches three (net +2 cards) but cannot find an Energy.
                s = 80000 if not energy_starved else 60000
            elif cid == HILDA:
                # Searches an Evolution Pokemon AND an Energy card: net +1 card, and the only
                # supporter in the list that can go and get energy.
                #
                # This ordering is the deck's binding constraint, not a preference. Six energy
                # cards in sixty and one attach a turn: measured against the reference agent we
                # held 0.50 energy per decision against their 0.79, our Active had no energy in
                # 67% of decisions against their 53%, and an ATTACK was on the table in 27% of
                # our decisions against 47% of theirs. Dawn outscoring Hilda unconditionally is
                # what produced that -- the bigger hand is worth nothing if nothing can attack.
                s = 96000 if energy_starved else 78000
            elif cid == BOSS and op.bench:
                # Only worth a supporter when it drags out something we can actually knock out.
                best = max((p for p in op.bench if p is not None), key=lambda p: -p.hp, default=None)
                s = 88000 if (best is not None and ready and dmg >= best.hp) else 26000
            elif cid == POKE_PAD:
                s = 60000                       # net zero cards, but it finds the attacker line
            elif cid == BUDDY_POFFIN and bench < 4:
                s = 70000 if turn <= 3 else 52000
            elif cid == NIGHT_STRETCHER:
                # It retrieves a Pokemon *or a Basic Energy*, so it is also an energy card when
                # the deck's six have started hitting the discard.
                if energy_starved and any(c.id == BASIC_P for c in me.discard):
                    s = 91000
                elif any(c.id in (ALAKAZAM, KADABRA, ABRA) for c in me.discard):
                    s = 46000
                else:
                    s = 18000
            elif cid == XEROSIC and len(op.hand or []) > 3:
                s = 34000
            elif cid == ENHANCED_HAMMER:
                s = 32000
            elif cid == LILLIE:
                # Shuffle the hand away and draw six. Only ever right when the hand is worse than
                # six cards, and catastrophic when the hand is what the attack is made of.
                s = 72000 if hand <= 4 else 0
            elif cid == LANA:
                # Up to three non-Rule-Box Pokemon *and Basic Energy* out of the discard, which is
                # the largest single refill in the list once the game has gone long.
                s = 84000 if energy_starved else (52000 if len(me.discard) >= 8 else 30000)
            elif cid == SACRED_ASH:
                s = 12000 if me.deckCount <= 12 else 0
            else:
                s = 20000

        elif t == OptionType.ATTACK:
            aid = getattr(o, "attackId", None)
            s = 10000
            if aid == POWERFUL_HAND:
                s = 12000
            # An attack that knocks the Active out is the whole point; rank it above the
            # low-value plays but still below anything that grows the hand first.
            if lethal_now:
                s = 30000

        elif t == OptionType.RETREAT:
            a = me.active[0] if me.active else None
            better = any(p.id == ALAKAZAM for p in (me.bench or []) if p is not None)
            s = 22000 if (a is not None and a.id != ALAKAZAM and better) else 500

        elif t == OptionType.END:
            s = 100

        else:
            s = 1000

        # The suppression rule. A card play that drops the hand below what the knockout needs is
        # trading a prize for a card, so it is pushed under the attack.
        if lethal_now and t in (OptionType.PLAY, OptionType.ATTACH) and margin <= 0:
            s = min(s, 5000)
        scores.append(s)
    return scores


# ---- the non-MAIN contexts -------------------------------------------------------------------

def _score_card_select(sel, st, mi: int, ctx) -> List[int]:
    me = st.players[mi]
    scores = []
    for o in sel.option:
        cid = _card_of(sel, st, mi, o)
        base = WANT.get(cid, 15) if cid is not None else 15
        if ctx == SelectContext.TO_BENCH:
            # Bench slots want Abra above all: it is the only card that becomes the attacker.
            base = {ABRA: 100, DUNSPARCE_70: 60, DUNSPARCE_60: 55}.get(cid, base)
        elif ctx == SelectContext.TO_ACTIVE:
            # Promote whatever can attack soonest, and never promote into a dead Active.
            pk = None
            try:
                if o.area == AreaType.BENCH:
                    pk = me.bench[o.index]
            except Exception:  # noqa: BLE001
                pk = None
            # Promotion order is about who can attack SOON, not who has the most HP. Dudunsparce
            # is 140 HP and looks like the safe promote, but Land Crush costs three energy in a
            # deck holding six, and its retreat is three -- promoting it parks the Active on a
            # Pokémon that cannot attack and cannot leave. Abra and Kadabra attack for one energy
            # and evolve into the attacker in place, which is why the reference agent's Active is
            # an Abra 37% of the time and ours was a Dudunsparce or a Dunsparce 33% of the time.
            base = {ALAKAZAM: 100, KADABRA: 80, ABRA: 70,
                    DUNSPARCE_70: 40, DUNSPARCE_60: 35, DUDUNSPARCE: 20}.get(cid, base)
            if pk is not None and len(pk.energies) >= 1:
                base += 50 if cid == ALAKAZAM else 20
        elif ctx == SelectContext.TO_DECK:
            base = 100 - base          # putting the *least* wanted card back is correct
        scores.append(base)
    return scores


def _choose(obs) -> List[int]:
    sel, st = obs.select, obs.current
    mi = int(st.yourIndex)
    ctx = sel.context
    n = len(sel.option)
    lo, hi = int(sel.minCount), int(sel.maxCount)

    if ctx == SelectContext.MAIN:
        scores = _score_main(sel, st, mi)
        return [max(range(n), key=lambda i: scores[i])]

    if ctx in (SelectContext.IS_FIRST, SelectContext.ACTIVATE):
        # YES for both. Going first buys a turn of setup for a deck whose clock is a Stage 2, and
        # every ACTIVATE offered by this list is a draw ability.
        for i, o in enumerate(sel.option):
            if o.type == OptionType.YES:
                return [i]
        return list(range(min(hi, n)))[:max(lo, 1)]

    if ctx == SelectContext.EVOLVE:
        return list(range(min(hi, n)))[:max(lo, 1)]

    if ctx == SelectContext.DRAW_COUNT:
        # Always draw the most on offer.
        best = max(range(n), key=lambda i: (getattr(sel.option[i], "number", 0) or 0))
        return [best]

    if ctx == SelectContext.SWITCH:
        # Their side: drag out whatever we can kill, else the biggest prize.
        op = st.players[1 - mi]
        me = st.players[mi]
        ready = _alakazam_ready(me)
        dmg = _powerful_hand_damage(len(me.hand))
        best, bv = 0, None
        for i, o in enumerate(sel.option):
            pk = None
            try:
                pk = op.bench[o.index] if o.area == AreaType.BENCH else (op.active[o.index])
            except Exception:  # noqa: BLE001
                pk = None
            if pk is None:
                v = 0
            else:
                d = _CARD.get(pk.id)
                prize = 3 if (d and d.megaEx) else 2 if (d and d.ex) else 1
                v = (1000 if (ready and dmg >= pk.hp) else 0) + prize * 100 - pk.hp
            if bv is None or v > bv:
                best, bv = i, v
        return [best]

    if ctx in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON):
        order = {ABRA: 100, DUNSPARCE_70: 60, DUNSPARCE_60: 55}
        scores = [order.get(_card_of(sel, st, mi, o), 10) for o in sel.option]
        want = min(hi, n)
        picked = sorted(range(n), key=lambda i: -scores[i])[:want]
        if len(picked) < lo:
            picked = list(range(min(lo, n)))
        return sorted(picked)

    if ctx in (SelectContext.TO_HAND, SelectContext.TO_BENCH, SelectContext.TO_ACTIVE,
               SelectContext.TO_DECK):
        scores = _score_card_select(sel, st, mi, ctx)
        want = min(hi, n)
        picked = sorted(range(n), key=lambda i: -scores[i])[:want]
        if len(picked) < lo:
            picked = list(range(min(lo, n)))
        return sorted(picked)

    # Anything unmodelled: take the smallest legal selection rather than guess.
    return list(range(min(max(lo, 1), n)))


def _legal(sel, action) -> bool:
    n = len(sel.option)
    return (isinstance(action, list)
            and int(sel.minCount) <= len(action) <= int(sel.maxCount)
            and len(action) == len(set(action))
            and all(isinstance(i, int) and 0 <= i < n for i in action))


def agent(obs_dict: dict) -> list:
    obs = to_observation_class(obs_dict)
    if obs.select is None or obs.current is None:
        return MY_DECK
    sel = obs.select
    try:
        action = _choose(obs)
    except Exception:  # noqa: BLE001
        action = None
    if action is None or not _legal(sel, action):
        # A from-scratch policy has no expert to fall back on, so the guard is the guard. The
        # smallest legal selection is always available and always legal.
        k = max(1, int(sel.minCount))
        action = list(range(min(k, len(sel.option))))
    return action

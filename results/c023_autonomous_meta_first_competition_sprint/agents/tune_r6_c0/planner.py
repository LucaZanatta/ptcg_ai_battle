"""c023 — a one-turn planner built on the engine's forward-search API.

The official sample agents choose by scoring each option in isolation with a hand-written
constant. That is a greedy policy: it cannot see that playing card A *first* makes card B
reachable, or that this turn's attack costs next turn's attacker. This module replaces the
choice at MAIN decisions with the outcome of actually playing the turn out.

    for each legal option at the root:
        take it, then let the BASE AGENT finish the turn from there,
        and score the board it leaves behind.

Using the base agent as the continuation policy is deliberate: it makes this one step of policy
improvement over the expert rather than a different agent wearing its name, and it means every
line is evaluated under a continuation the expert would actually play. The expert also remains
the fallback — the planner only overrides when its own evaluation of the expert's action is
worse than the best line by a stated margin.

Three things this is careful about, each because the repository has paid for the alternative:

* **Handles are always released.** The engine's search-handle buffer has capacity 7 and an
  eighth allocation throws an uncaught C++ exception that kills the process by SIGABRT. Every
  state this module creates is released on every path, including exceptions.
* **The clock is checked between lines, not assumed.** Planning stops at the budget and returns
  the best line found so far; a partially explored decision is a slightly worse decision, while
  an overrun is a forfeited game.
* **Only our own turn is simulated.** The opponent's hidden cards are filled with a placeholder,
  which is honest for evaluating our turn and worthless for evaluating theirs — so the rollout
  stops the moment the turn passes.
"""

from __future__ import annotations

import collections
import time
from typing import Any, Dict, List, Optional, Tuple

from cg.api import (AreaType, OptionType, Pokemon, SelectContext, all_attack, all_card_data,
                    search_begin, search_end, search_release, search_step,
                    to_observation_class)

_CARD = {c.cardId: c for c in all_card_data()}
_ATK = {a.attackId: a for a in all_attack()}

# A basic Pokemon id used to fill the opponent's unknown zones. It only has to be a legal card
# and a Basic Pokemon; nothing in our own turn depends on which one it is.
_FILLER_BASIC = 119

DEFAULTS: Dict[str, float] = {
    "max_root_options": 8,
    "max_turn_steps": 16,
    # A SAFETY VALVE, not the work budget. Search effort is set by max_root_options x
    # max_turn_steps so that a contended machine makes an arm slower and never weaker; a
    # wall-clock work budget silently buys fewer lines under load and biases the measurement.
    # This repository has had three results corrupted by exactly that.
    "budget_ms": 700.0,
    "min_turn": 2,
    "all_contexts": 0.0,         # 1.0 = plan at every single-select decision, not only MAIN
    "prize_only": 0.0,           # 1.0 = override ONLY on an exact gain: strictly more prizes
                                 # taken, fewer prizes conceded, or a terminal term
    "use_ko_risk": 0.0,          # 1.0 = break exact-gain ties on immediate knockout exposure
    "determinization_rotation": 1.0,
    "override_margin": 1.0,      # keep the expert's action unless a line beats it by this much
    "w_prize_taken": 10000.0,
    "w_prize_lost": 12000.0,
    "w_terminal": 1000000.0,
    "w_op_hp": -1.0,
    "w_my_hp": 0.6,
    "w_my_energy": 25.0,
    "w_my_stage1": 60.0,
    "w_my_stage2": 140.0,
    "w_my_bench_ex": -60.0,
    "w_hand": 5.0,
    "w_deck": 0.0,
}


def _board(ps) -> List[Any]:
    out = []
    for p in list(ps.active) + list(ps.bench):
        if p is not None:
            out.append(p)
    return out


def _visible_own_ids(obs, mi: int) -> List[int]:
    """Every card of ours the observation reveals; the remainder is deck + prize."""
    out: List[int] = []
    st = obs.current
    me = st.players[mi]
    for c in me.hand:
        out.append(c.id)
    for c in me.discard:
        out.append(c.id)
    for p in _board(me):
        out.append(p.id)
        for e in p.energyCards:
            out.append(e.id)
        for t in p.tools:
            out.append(t.id)
        for pe in p.preEvolution:
            out.append(pe.id)
    for c in st.stadium:
        if getattr(c, "playerIndex", mi) == mi:
            out.append(c.id)
    if st.looking:
        for c in st.looking:
            if getattr(c, "playerIndex", mi) == mi:
                out.append(c.id)
    return out


_ROT = [0]


def _determinize(obs, mi: int, my_deck: List[int], rotate: bool = True):
    """A concrete world consistent with what we can see.

    Our own side is exact: the deck list is known, so the unseen remainder is exactly the deck
    plus the prizes and only the split between them is guessed. The opponent's hidden zones are
    filled with a placeholder, which is why the rollout never enters their turn.
    """
    st = obs.current
    me = st.players[mi]
    op = st.players[1 - mi]

    remain = collections.Counter(my_deck)
    for cid in _visible_own_ids(obs, mi):
        if remain[cid] > 0:
            remain[cid] -= 1
    pool = [c for c, n in sorted(remain.items()) for _ in range(n)]
    # Rotate which unseen cards land in the prizes. Without this the SAME cards are hidden in
    # every prize slot at every decision of every game -- a systematic bias, not a sample.
    if rotate and pool:
        _ROT[0] = (_ROT[0] + 1) % max(1, len(pool))
        pool = pool[_ROT[0]:] + pool[:_ROT[0]]
    need = len(me.prize) + me.deckCount
    if len(pool) < need:                      # a card we could not account for; pad legally
        pool = pool + [_FILLER_BASIC] * (need - len(pool))
    my_prize = pool[:len(me.prize)]
    my_deck_pred = pool[len(me.prize):need]

    op_active = [_FILLER_BASIC] if (op.active and op.active[0] is None) else []
    return (my_deck_pred, my_prize,
            [_FILLER_BASIC] * op.deckCount, [_FILLER_BASIC] * len(op.prize),
            [_FILLER_BASIC] * op.handCount, op_active)


def _prize_value(p) -> int:
    d = _CARD.get(p.id)
    if d is None:
        return 1
    return 3 if d.megaEx else 2 if d.ex else 1


def _ko_risk(obs, mi: int) -> int:
    """Prizes the opponent can take immediately, from cards we can actually see.

    Their active Pokemon, its attached energy and its attacks are all public, and so is our own
    active's remaining HP and weakness. So "can they knock this out on their next turn" is a
    computation over observed state, not a guess about their hand -- which is what makes it
    admissible in the same gate as prizes taken.
    """
    st = obs.current
    if st is None:
        return 0
    me = st.players[mi]
    op = st.players[1 - mi]
    if not me.active or me.active[0] is None:
        return 0
    mine = me.active[0]
    mydata = _CARD.get(mine.id)
    if not op.active or op.active[0] is None:
        return 0
    theirs = op.active[0]
    tdata = _CARD.get(theirs.id)
    if tdata is None or mydata is None:
        return 0
    have = len(theirs.energies)
    best = 0
    for aid in tdata.attacks:
        a = _ATK.get(aid)
        if a is None or have < len(a.energies):
            continue
        dmg = a.damage
        if mydata.weakness is not None and mydata.weakness == tdata.energyType:
            dmg *= 2
        elif mydata.resistance is not None and mydata.resistance == tdata.energyType:
            dmg -= 30
        best = max(best, dmg)
    return _prize_value(mine) if best >= mine.hp else 0


def _exact_gain(obs, mi: int, root_my_prizes: int, root_op_prizes: int, ko: bool = False):
    """The part of a line's value that is not a matter of taste.

    Prizes taken, prizes conceded and a terminal board are facts about the simulated line; every
    other term in the evaluator is a hand-written opinion about board quality. `prize_only` mode
    overrides the expert on this tuple alone, so an override can be wrong about the game but
    never wrong about its own arithmetic.
    """
    st = obs.current
    if st is None:
        return (0, 0, 0)
    me = st.players[mi]
    op = st.players[1 - mi]
    taken = root_op_prizes - len(op.prize)
    lost = root_my_prizes - len(me.prize)
    terminal = 0
    if len(op.prize) == 0 or not _board(op):
        terminal = 1
    if len(me.prize) == 0 or not _board(me):
        terminal = -1
    if ko:
        return (terminal, taken, -lost, -_ko_risk(obs, mi))
    return (terminal, taken, -lost)


def _evaluate(obs, mi: int, root_my_prizes: int, root_op_prizes: int, w: Dict[str, float]) -> float:
    st = obs.current
    if st is None:
        return 0.0
    me = st.players[mi]
    op = st.players[1 - mi]

    s = 0.0
    s += w["w_prize_taken"] * (root_op_prizes - len(op.prize))
    s -= w["w_prize_lost"] * (root_my_prizes - len(me.prize))
    if len(op.prize) == 0:
        s += w["w_terminal"]
    if len(me.prize) == 0:
        s -= w["w_terminal"]

    for p in _board(op):
        s += w["w_op_hp"] * p.hp
    if not _board(op):                        # no Pokemon left on their side is a win condition
        s += w["w_terminal"]

    for p in _board(me):
        s += w["w_my_hp"] * p.hp
        s += w["w_my_energy"] * len(p.energies)
        d = _CARD.get(p.id)
        if d is not None:
            if d.stage2:
                s += w["w_my_stage2"]
            elif d.stage1:
                s += w["w_my_stage1"]
    for p in list(me.bench):
        if p is None:
            continue
        d = _CARD.get(p.id)
        if d is not None and (d.ex or d.megaEx):
            s += w["w_my_bench_ex"]
    if not _board(me):
        s -= w["w_terminal"]

    s += w["w_hand"] * len(me.hand)
    s += w["w_deck"] * me.deckCount
    return s


def _rollout(state, mi: int, root_turn: int, base_agent, max_steps: int,
             deadline: float) -> Tuple[Optional[Any], List[int]]:
    """Finish our own turn from `state` with the base agent, returning the final observation.

    Returns (observation, handles_created). The caller releases them; doing it here would free a
    state we still need to read.
    """
    handles: List[int] = []
    cur = state
    obs = cur.observation
    for _ in range(max_steps):
        if time.perf_counter() > deadline:
            break
        if obs is None or obs.select is None or obs.current is None:
            break
        if obs.current.yourIndex != mi or obs.current.turn != root_turn:
            break                                   # the turn has passed; stop simulating
        n = len(obs.select.option)
        if n == 0:
            break
        try:
            action = base_agent.agent(_to_dict(obs))
        except Exception:
            k = max(1, int(obs.select.minCount))
            action = list(range(min(k, n)))
        if not action:
            k = max(1, int(obs.select.minCount))
            action = list(range(min(k, n)))
        try:
            cur = search_step(cur.searchId, list(action))
        except Exception:
            break
        handles.append(cur.searchId)
        obs = cur.observation
    return obs, handles


def _to_dict(obs) -> Dict[str, Any]:
    """Dataclass -> plain dict, so `to_observation_class` round-trips it for the base agent."""
    import dataclasses

    def conv(x):
        if dataclasses.is_dataclass(x):
            return {f.name: conv(getattr(x, f.name)) for f in dataclasses.fields(x)}
        if isinstance(x, list):
            return [conv(i) for i in x]
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if hasattr(x, "value") and hasattr(x, "name"):      # IntEnum
            return x.value
        return x

    return conv(obs)


def plan(obs, base_action: List[int], my_deck: List[int], base_agent,
         cfg: Optional[Dict[str, float]] = None,
         restrict: Optional[List[int]] = None) -> Optional[List[int]]:
    """Return a better MAIN action than `base_action`, or None to keep the expert's."""
    w = dict(DEFAULTS)
    if cfg:
        w.update(cfg)

    sel = obs.select
    if sel is None:
        return None
    if not w["all_contexts"] and sel.context != SelectContext.MAIN:
        return None
    if int(sel.maxCount) != 1 or len(sel.option) < 2:
        return None
    st = obs.current
    if st is None or st.turn < w["min_turn"]:
        return None

    mi = st.yourIndex
    root_turn = st.turn
    root_my_prizes = len(st.players[mi].prize)
    root_op_prizes = len(st.players[1 - mi].prize)
    deadline = time.perf_counter() + w["budget_ms"] / 1000.0

    # The expert's own choice is evaluated first, so a budget exhausted early still leaves a
    # meaningful comparison rather than an arbitrary one.
    if restrict:
        # Only options the expert itself ranked highly. This matters: searching every option
        # means the evaluator argues with constants that encode deck knowledge it does not have,
        # and the plan_screen1 arms lost monotonically in how often they overrode. Restricting
        # to the expert's own shortlist means every candidate is already expert-approved and the
        # search only has to break the tie.
        order = [i for i in restrict if 0 <= i < len(sel.option)]
    else:
        order = [int(base_action[0])] if base_action else []
        for i in range(len(sel.option)):
            if i not in order:
                order.append(i)
    order = order[:int(w["max_root_options"])]

    root = None
    created: List[int] = []
    best_i, best_v = None, None
    base_v = None
    exact: Dict[int, Any] = {}
    try:
        d = _determinize(obs, mi, my_deck, bool(w["determinization_rotation"]))
        root = search_begin(obs, d[0], d[1], d[2], d[3], d[4], d[5])
        created.append(root.searchId)
        for i in order:
            if time.perf_counter() > deadline and best_i is not None:
                break
            try:
                child = search_step(root.searchId, [i])
            except Exception:
                continue
            created.append(child.searchId)
            leaf, handles = _rollout(child, mi, root_turn, base_agent,
                                     int(w["max_turn_steps"]), deadline)
            created.extend(handles)
            if leaf is None or leaf.current is None:
                continue
            v = _evaluate(leaf, mi, root_my_prizes, root_op_prizes, w)
            exact[i] = _exact_gain(leaf, mi, root_my_prizes, root_op_prizes,
                                   bool(w["use_ko_risk"]))
            if base_action and i == int(base_action[0]):
                base_v = v
            if best_v is None or v > best_v:
                best_v, best_i = v, i
    except Exception:
        return None
    finally:
        for h in created:
            try:
                search_release(h)
            except Exception:
                pass
        try:
            search_end()
        except Exception:
            pass

    if w["prize_only"]:
        # Conservative admission: replace the expert only where the simulated line is strictly
        # better on facts -- terminal result first, then prizes taken, then prizes conceded.
        if not base_action or int(base_action[0]) not in exact:
            return None
        b = int(base_action[0])
        cand = max((i for i in exact if i != b), key=lambda i: exact[i], default=None)
        if cand is None or exact[cand] <= exact[b]:
            return None
        return [cand]

    if best_i is None:
        return None
    if base_action and best_i == int(base_action[0]):
        return None
    if base_v is not None and best_v is not None and best_v - base_v < w["override_margin"]:
        return None
    return [best_i]

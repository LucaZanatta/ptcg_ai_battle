"""c024 — finish mode: override the expert only when a win *this turn* has been verified.

## Why this and not another planner

`FAILURE_TAXONOMY` F3 killed four `turn_planner` variants and the ordering was the finding: the
arms lost **monotonically in how often they overrode**. `plan2`, which planned at every
single-select decision, was the worst at 0.479; `plan1`, the most conservative, was the best at
0.4985. The diagnosis was that a search scored by a hand-written board evaluator is arguing with
constants that encode deck knowledge the evaluator does not have, and it loses that argument.

Finish mode is the far end of that same curve, and it is the end nobody sampled. It overrides on
**one condition only: the simulated line ends the game in our favour** — the opponent's last
prize taken, or their last Pokémon removed. That is not an opinion about board quality; it is the
game's own terminal condition. An override here can be wrong about the world it sampled, but it
cannot be wrong about what it is optimising.

## Why the world it samples is the whole risk

The rollout finishes our turn inside the engine, and the engine needs a concrete hidden state.
Two things can make a verified win imaginary:

1. **A card that is actually prized.** `c023_planner._determinize` guesses the prize/deck split.
   A line that wins by playing a card sitting under a prize is a fantasy. `c024_prizes` closes
   this whenever the observation allows, and `PRIZE_ORACLE.json` is the evidence that it does not
   lie when it speaks.
2. **Deck order.** Even with the right cards in the deck, a line that only wins when the top card
   cooperates is luck, not a plan. So a win must reproduce in **every** sampled world: `worlds`
   independent determinizations, unanimity required. One dissenting world vetoes the override.

Both failures push the same way -- towards claiming a win that is not there -- so both guards are
one-sided, and the cost of being wrong is one bad action while the cost of being silent is zero.
"""

from __future__ import annotations

import collections
import time
from typing import Any, Dict, List, Optional, Tuple

from cg.api import OptionType, SelectContext, search_begin, search_end, search_release, search_step

# A packaged candidate ships the planner as a flat `planner.py` beside `main.py`, because the
# Kaggle image has only the official `cg` package and nothing of this repository. Prefer that
# name; fall back to the repository module so the same file is importable from a checkout.
try:
    from planner import _FILLER_BASIC, _board, _rollout, _visible_own_ids  # type: ignore
except ImportError:  # pragma: no cover - only taken outside a packaged candidate
    from cg.c023_planner import _FILLER_BASIC, _board, _rollout, _visible_own_ids

DEFAULTS: Dict[str, float] = {
    "worlds": 3.0,             # determinizations that must ALL agree before an override
    "max_root_options": 8.0,   # root actions examined per world
    "max_turn_steps": 60.0,    # engine steps allowed to finish one simulated turn
    "max_op_prizes": 3.0,      # do not even look unless a win this turn is arithmetically possible
    "min_turn": 2.0,
    "budget_ms": 900.0,        # safety valve; the count caps above are the real budget
    "require_prizes_known": 0.0,   # 1.0 = only fire when the prize pile has been deduced
}


class Stats:
    """Counters the wrapper reports, so an inert rule is visible without an outcome study."""

    def __init__(self) -> None:
        self.considered = 0        # decisions passing the cheap gate
        self.searched = 0          # decisions that reached the engine
        self.fired = 0             # decisions where the expert's action was replaced
        self.base_already_won = 0  # a win existed and the expert was already taking it
        self.vetoed = 0            # a win in some worlds but not all
        self.errors = 0

    def as_dict(self) -> Dict[str, int]:
        return {k: v for k, v in vars(self).items()}


def _determinize(obs: Any, mi: int, my_deck: List[int], prized: Optional[collections.Counter],
                 salt: int) -> Tuple[List[int], List[int], List[int], List[int], List[int], List[int]]:
    """A concrete world, with the prize split taken from knowledge when there is any.

    When `prized` is None this degrades to the c023 behaviour -- an arbitrary but rotated split --
    and the unanimity requirement is what keeps that honest.
    """
    st = obs.current
    me = st.players[mi]
    op = st.players[1 - mi]

    remain = collections.Counter(my_deck)
    for cid in _visible_own_ids(obs, mi):
        if remain[cid] > 0:
            remain[cid] -= 1

    if prized is not None and sum(prized.values()) == len(me.prize):
        rest = remain.copy()
        ok = True
        for cid, n in prized.items():
            if rest[cid] < n:
                ok = False
                break
            rest[cid] -= n
        if ok:
            my_prize = [c for c, n in sorted(prized.items()) for _ in range(n)]
            pool = [c for c, n in sorted(rest.items()) for _ in range(n)]
            pool = _rotate(pool, salt)
            need = me.deckCount
            if len(pool) < need:
                pool = pool + [_FILLER_BASIC] * (need - len(pool))
            return (pool[:need], my_prize,
                    [_FILLER_BASIC] * op.deckCount, [_FILLER_BASIC] * len(op.prize),
                    [_FILLER_BASIC] * op.handCount,
                    [_FILLER_BASIC] if (op.active and op.active[0] is None) else [])

    pool = _rotate([c for c, n in sorted(remain.items()) for _ in range(n)], salt)
    need = len(me.prize) + me.deckCount
    if len(pool) < need:
        pool = pool + [_FILLER_BASIC] * (need - len(pool))
    return (pool[len(me.prize):need], pool[:len(me.prize)],
            [_FILLER_BASIC] * op.deckCount, [_FILLER_BASIC] * len(op.prize),
            [_FILLER_BASIC] * op.handCount,
            [_FILLER_BASIC] if (op.active and op.active[0] is None) else [])


def _rotate(pool: List[int], salt: int) -> List[int]:
    if not pool:
        return pool
    k = salt % len(pool)
    return pool[k:] + pool[:k]


def _is_win(leaf: Any, mi: int) -> bool:
    """The game is over and we are the one still standing.

    Read off the same two conditions the engine ends on -- their prizes exhausted, or nothing left
    on their board -- and require that neither has happened to us in the same line.
    """
    st = getattr(leaf, "current", None)
    if st is None:
        return False
    me = st.players[mi]
    op = st.players[1 - mi]
    if len(me.prize) == 0 or not _board(me):
        return False
    return len(op.prize) == 0 or not _board(op)


def finish(obs: Any, base_action: Optional[List[int]], my_deck: List[int], base_agent: Any,
           prized: Optional[collections.Counter] = None,
           cfg: Optional[Dict[str, float]] = None,
           stats: Optional[Stats] = None) -> Optional[List[int]]:
    """A root action that wins the game this turn in every sampled world, or None."""
    w = dict(DEFAULTS)
    if cfg:
        w.update(cfg)
    sel = getattr(obs, "select", None)
    st = getattr(obs, "current", None)
    if sel is None or st is None:
        return None
    if sel.context != SelectContext.MAIN or int(sel.maxCount) != 1 or len(sel.option) < 2:
        return None
    if st.turn < w["min_turn"]:
        return None

    mi = int(st.yourIndex)
    op = st.players[1 - mi]
    # A win this turn needs their last prize taken or their board emptied. Neither is reachable
    # while they hold more prizes than a turn can plausibly take, and the check is free.
    if len(op.prize) > int(w["max_op_prizes"]) and len(_board(op)) > 1:
        return None
    if w["require_prizes_known"] and prized is None:
        return None
    if not any(o.type == OptionType.ATTACK for o in sel.option):
        # Every terminal line in this game ends on an attack. If none is selectable at this
        # decision the win, if there is one, is found at the decision that offers it.
        return None

    if stats:
        stats.considered += 1

    b = int(base_action[0]) if base_action else None
    order: List[int] = []
    if b is not None and 0 <= b < len(sel.option):
        order.append(b)
    for i in range(len(sel.option)):
        if i not in order:
            order.append(i)
    order = order[:int(w["max_root_options"])]

    deadline = time.perf_counter() + w["budget_ms"] / 1000.0
    n_worlds = max(1, int(w["worlds"]))
    wins_per_option = collections.Counter()
    worlds_done = 0

    if stats:
        stats.searched += 1

    for wi in range(n_worlds):
        if time.perf_counter() > deadline:
            break
        created: List[int] = []
        try:
            d = _determinize(obs, mi, my_deck, prized, salt=wi * 7 + 1)
            root = search_begin(obs, d[0], d[1], d[2], d[3], d[4], d[5])
            created.append(root.searchId)
            for i in order:
                if time.perf_counter() > deadline:
                    break
                try:
                    child = search_step(root.searchId, [i])
                except Exception:  # noqa: BLE001
                    continue
                created.append(child.searchId)
                leaf, handles = _rollout(child, mi, int(st.turn), base_agent,
                                         int(w["max_turn_steps"]), deadline)
                created.extend(handles)
                if leaf is not None and _is_win(leaf, mi):
                    wins_per_option[i] += 1
            worlds_done += 1
        except Exception:  # noqa: BLE001
            if stats:
                stats.errors += 1
        finally:
            for h in created:
                try:
                    search_release(h)
                except Exception:  # noqa: BLE001
                    pass
            try:
                search_end()
            except Exception:  # noqa: BLE001
                pass

    if worlds_done == 0:
        return None
    # Unanimity. A line that wins in some worlds and not others depends on the shuffle, and
    # taking it would be gambling with the expert's turn rather than converting a certainty.
    unanimous = [i for i in order if wins_per_option[i] >= worlds_done]
    if not unanimous:
        if stats and wins_per_option:
            stats.vetoed += 1
        return None
    if b is not None and b in unanimous:
        if stats:
            stats.base_already_won += 1
        return None                      # the expert is already winning; do not disturb it
    if stats:
        stats.fired += 1
    return [unanimous[0]]

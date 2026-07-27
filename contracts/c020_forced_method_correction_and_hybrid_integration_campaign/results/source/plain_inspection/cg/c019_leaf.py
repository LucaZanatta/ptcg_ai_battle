"""c019 Branch A — PTCG heuristic leaf evaluator (§8.4).

Versioned, decomposed, and deliberately NOT weight-tuned: §8.4 says configure the evaluator but
do not run a large weight search. The score decomposition is preserved in traces so a bad leaf
value can be attributed to a term rather than guessed at.

c018 measured its leaf heuristic at Pearson 0.180 against actual outcomes, and non-monotonic at
the bottom of its range. That is the single most likely reason its search underperformed: a
forward search maximises whatever the leaf says, so a weak leaf signal makes deeper search worse,
not better. This evaluator therefore leads with the prize race — the actual win condition — and
keeps every other term subordinate to it.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402

LEAF_VERSION = "c019.leaf.v1"

WEIGHTS = {
    "prize_race": 0.55,       # taking prizes IS the win condition
    "board_hp": 0.16,
    "active_readiness": 0.10,
    "backup_attacker": 0.07,
    "energy_route": 0.06,
    "bench_liability": 0.04,
    "resources": 0.02,
}


def _hp_fraction(cards) -> Tuple[float, float]:
    tot = cur = 0.0
    for c in cards:
        if c is None:
            continue
        tot += float(getattr(c, "maxHp", 0) or 0)
        cur += float(getattr(c, "hp", 0) or 0)
    return (cur / tot if tot else 0.0), tot


def _energy(card) -> int:
    if card is None:
        return 0
    return len(getattr(card, "energyCards", None) or getattr(card, "energies", None) or [])


def evaluate(observation, terminal: bool = False,
             your_index: Optional[int] = None) -> Tuple[float, Dict[str, float]]:
    """Leaf value in [-1, 1] from the CURRENT PLAYER's perspective, plus its decomposition."""
    parts: Dict[str, float] = {}
    try:
        v = K.visible_view(observation, your_index)
        counts = v.counts()
        mine = v.board("mine")
        theirs = v.board("theirs")
    except Exception:  # noqa: BLE001
        return 0.0, {"error": 1.0}

    my_prize = counts["my_prize"]
    op_prize = counts["opp_prize"]

    # terminal: prizes exhausted decides the game
    if terminal or my_prize == 0 or op_prize == 0:
        if my_prize == 0 and op_prize > 0:
            return 1.0, {"terminal_win": 1.0}
        if op_prize == 0 and my_prize > 0:
            return -1.0, {"terminal_loss": 1.0}

    # prize race: fewer remaining prizes is better, normalized to [-1, 1]
    parts["prize_race"] = (op_prize - my_prize) / 6.0

    my_cards = list(mine["active"]) + list(mine["bench"])
    op_cards = list(theirs["active"]) + list(theirs["bench"])
    mh, _ = _hp_fraction(my_cards)
    oh, _ = _hp_fraction(op_cards)
    parts["board_hp"] = mh - oh

    my_active = mine["active"][0] if mine["active"] else None
    op_active = theirs["active"][0] if theirs["active"] else None

    # active readiness: an Active with energy and health can actually attack
    if my_active is not None:
        e = min(_energy(my_active), 4) / 4.0
        hp = float(getattr(my_active, "hp", 0) or 0)
        mx = float(getattr(my_active, "maxHp", 1) or 1)
        parts["active_readiness"] = 0.6 * e + 0.4 * (hp / mx if mx else 0.0)
    else:
        parts["active_readiness"] = -1.0        # no Active is close to losing

    # a benched attacker with energy is the answer to losing the Active
    bench = list(mine["bench"])
    ready_bench = sum(1 for c in bench if c is not None and _energy(c) >= 1)
    parts["backup_attacker"] = min(ready_bench, 2) / 2.0

    my_e = sum(_energy(c) for c in my_cards)
    op_e = sum(_energy(c) for c in op_cards)
    parts["energy_route"] = max(-1.0, min(1.0, (my_e - op_e) / 6.0))

    # an empty bench means a knocked-out Active loses the game outright
    n_bench = sum(1 for c in bench if c is not None)
    parts["bench_liability"] = -1.0 if n_bench == 0 else min(n_bench, 3) / 3.0

    # visible threat: an opposing Active loaded with energy is about to attack
    if op_active is not None:
        parts["bench_liability"] -= 0.3 * (min(_energy(op_active), 4) / 4.0)

    parts["resources"] = max(-1.0, min(1.0, (counts["my_hand"] - counts["opp_hand"]) / 8.0
                                       + (counts["my_deck"] - counts["opp_deck"]) / 60.0))

    score = sum(WEIGHTS[k] * parts.get(k, 0.0) for k in WEIGHTS)
    return max(-1.0, min(1.0, score)), parts


def make_leaf_fn(your_index: Optional[int] = None):
    def leaf(observation, terminal: bool = False) -> float:
        s, _ = evaluate(observation, terminal, your_index)
        return s
    return leaf

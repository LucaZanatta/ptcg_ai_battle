"""c020 A6 — tactical PTCG leaf evaluator.

c019's evaluator had four features led by `prize_race: 0.55`, and the campaign's central negative
result was that MORE search made play WORSE (audit #3). That is the signature of a search
optimizing the wrong objective: a correct search maximizing a wrong evaluation finds increasingly
effective ways to be wrong. So the evaluator, not the search mechanics, is the correction most
likely to matter.

The specific failure recorded in audit #4 is that overrides frequently chose END TURN over
productive baseline card play. An evaluator built from prize counts and aggregate HP cannot see
the difference: ending the turn does not change prize counts or HP, so it scores identically to a
useful play while being strictly worse. Two features here exist to make that difference visible —
`productive_attack` and `unproductive_end_turn`.

Every feature is logged separately and the final score is reconstructable from the logged features
and one registered weight vector (`WEIGHTS`), so a disagreement between a score and its components
is detectable rather than hidden.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c020_cards as CD  # noqa: E402

# ONE registered weight vector (A6: "One registered weight vector only after the smoke/repair
# pass. No broad weight sweep."). Registered in results/mcts/configs/leaf_weights.json.
WEIGHTS: Dict[str, float] = {
    "terminal": 1.000,
    "lethal": 0.900,
    "ko_value": 0.220,
    "prizes_taken": 0.260,
    "damage_dealt": 0.120,
    "productive_attack": 0.130,
    "attack_enabled": 0.070,
    "active_ready": 0.080,
    "backup_ready": 0.045,
    "typed_energy_ready": 0.060,
    "energy_waste": -0.055,
    "survival": 0.150,
    "target_prize_value": 0.070,
    "bench_liability": -0.080,
    "critical_resource_cost": -0.060,
    "future_prize_route": 0.070,
    "flexibility": 0.035,
    "unproductive_end_turn": -0.230,
}

WEIGHTS_VERSION = "c020.leaf.v1"


@dataclass
class LeafFeatures:
    """Every feature `MANDATORY_CHANGES A6` enumerates, each independently logged."""

    terminal: float = 0.0
    lethal: float = 0.0
    ko_value: float = 0.0
    prizes_taken: float = 0.0
    damage_dealt: float = 0.0
    productive_attack: float = 0.0
    attack_enabled: float = 0.0
    active_ready: float = 0.0
    backup_ready: float = 0.0
    typed_energy_ready: float = 0.0
    energy_waste: float = 0.0
    survival: float = 0.0
    target_prize_value: float = 0.0
    bench_liability: float = 0.0
    critical_resource_cost: float = 0.0
    future_prize_route: float = 0.0
    flexibility: float = 0.0
    unproductive_end_turn: float = 0.0

    def score(self, weights: Optional[Dict[str, float]] = None) -> float:
        w = weights or WEIGHTS
        s = sum(w.get(k, 0.0) * v for k, v in asdict(self).items())
        return max(-1.0, min(1.0, s))

    def to_json(self) -> Dict[str, Any]:
        w = WEIGHTS
        d = asdict(self)
        return {"features": {k: round(v, 5) for k, v in d.items()},
                "contributions": {k: round(w.get(k, 0.0) * v, 5) for k, v in d.items()},
                "weights_version": WEIGHTS_VERSION,
                "score": round(self.score(), 5)}


@dataclass
class LineContext:
    """What happened along the simulated line, which a static position cannot show.

    A leaf position alone cannot distinguish "ended turn having attacked" from "ended turn having
    done nothing" — the board looks the same. The search records this as it walks the line.
    """

    attacked: bool = False
    damage_dealt: int = 0
    prizes_taken: int = 0
    ended_turn: bool = False
    productive_action_was_available: bool = False
    critical_resources_used: int = 0
    ko_scored: bool = False


def _pk(side_board: Dict[str, List[Any]]) -> Tuple[Optional[Any], List[Any]]:
    act = (side_board.get("active") or [None])
    return (act[0] if act else None), [b for b in (side_board.get("bench") or []) if b]


def evaluate(observation, terminal: bool = False, your_index: Optional[int] = None,
             line: Optional[LineContext] = None,
             weights: Optional[Dict[str, float]] = None) -> Tuple[float, LeafFeatures]:
    """Leaf value in [-1, 1] from the CURRENT PLAYER's perspective, plus its decomposition."""
    f = LeafFeatures()
    line = line or LineContext()
    try:
        v = K.visible_view(observation, your_index)
        counts = v.counts()
        mine = v.board("mine")
        theirs = v.board("theirs")
    except Exception:  # noqa: BLE001
        return 0.0, f

    my_prize = counts["my_prize"]
    op_prize = counts["opp_prize"]
    my_active, my_bench = _pk(mine)
    op_active, op_bench = _pk(theirs)

    # ---------------------------------------------------------------- terminal / lethal
    if terminal or my_prize == 0 or op_prize == 0:
        f.terminal = 1.0 if my_prize == 0 else (-1.0 if op_prize == 0 else 0.0)
        return f.score(weights), f

    if my_active is not None and op_active is not None:
        ko, dmg = CD.can_ko(my_active, op_active)
        if ko:
            # a knockout that takes the last prize IS the game
            f.lethal = 1.0 if op_prize <= CD.prize_value(op_active) else 0.0
            f.ko_value = 1.0
            f.target_prize_value = min(1.0, CD.prize_value(op_active) / 3.0)
        ohp, omx = CD.hp_now(op_active)
        if omx > 0:
            f.damage_dealt = min(1.0, max(0.0, (omx - ohp) / omx))

    # ---------------------------------------------------------------- prize race
    # prize counts REMAINING, so lower is better; the difference of taken fractions is the lead.
    # c019 weighted this at 0.55 and let it dominate everything tactical; here it is 0.26 and
    # competes with lethal, readiness and the end-turn penalty.
    f.prizes_taken = ((6 - my_prize) - (6 - op_prize)) / 6.0

    # ---------------------------------------------------------------- readiness (typed!)
    if my_active is not None:
        legal = CD.legal_attacks(my_active)
        f.active_ready = 1.0 if legal else 0.0
        f.attack_enabled = 1.0 if legal else 0.0
        short = CD.energy_shortfall(my_active)
        f.typed_energy_ready = 1.0 if short == 0 else max(0.0, 1.0 - short / 3.0)
        att = CD.attached_energy(my_active)
        # energy attached but no attack anywhere near payable is stranded value
        if short >= 2 and sum(att.values()) >= 2:
            f.energy_waste = min(1.0, sum(att.values()) / 4.0)
        hp, mx = CD.hp_now(my_active)
        if mx > 0:
            f.survival = hp / mx
            if op_active is not None:
                oko, _d = CD.can_ko(op_active, my_active)
                if oko:
                    # about to lose the active, weighted by what it costs us
                    f.survival -= min(1.0, CD.prize_value(my_active) / 3.0 + 0.35)

    if my_bench:
        best = 0.0
        for b in my_bench:
            s = CD.energy_shortfall(b)
            best = max(best, 1.0 if s == 0 else max(0.0, 1.0 - s / 3.0))
        f.backup_ready = best
        # bench rule-box Pokemon are gust targets
        liab = sum(1 for b in my_bench if CD.prize_value(b) >= 2)
        f.bench_liability = min(1.0, liab / max(1, len(my_bench)))

    # ---------------------------------------------------------------- line-derived
    f.productive_attack = 1.0 if line.attacked else 0.0
    if line.prizes_taken:
        f.prizes_taken += line.prizes_taken / 6.0
    if line.damage_dealt:
        f.damage_dealt = min(1.0, f.damage_dealt + line.damage_dealt / 200.0)
    f.critical_resource_cost = min(1.0, line.critical_resources_used / 3.0)

    # THE audit-#4 feature: ending the turn with a productive action available and no attack made
    if line.ended_turn and not line.attacked and line.productive_action_was_available:
        f.unproductive_end_turn = 1.0

    # ---------------------------------------------------------------- route / flexibility
    f.future_prize_route = min(1.0, (6 - my_prize) / 6.0) if my_prize < op_prize else \
        max(0.0, (6 - my_prize) / 12.0)
    f.flexibility = min(1.0, counts["my_hand"] / 8.0)

    return f.score(weights), f


def make_leaf_fn(your_index: Optional[int] = None, weights: Optional[Dict[str, float]] = None):
    def leaf(observation, terminal: bool = False, line: Optional[LineContext] = None) -> float:
        s, _f = evaluate(observation, terminal, your_index, line, weights)
        return s
    return leaf


def feature_names() -> List[str]:
    return list(asdict(LeafFeatures()).keys())

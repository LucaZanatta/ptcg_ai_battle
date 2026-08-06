from __future__ import annotations
'Second-pass handwritten sequencing refinements for v32.\n\nThe rules in this module are explicit visible-state protocols.  They do not\ncontain fitted parameters, record identifiers, state hashes, learned weights,\nor search.  Each rule requires the currently selected role and replacement\nrole both to be legal.\n'
from dataclasses import dataclass
import os
from . import validated_rule_profile as profile
from .state_model import TurnState

@dataclass(frozen=True)
class RefinementDecision:
    index: int | None
    rule: str

class ManualRefinementArbiter:

    def __init__(self) -> None:
        raw = os.environ.get('PTCG_V32_RULES', 'ALL').strip()
        self.enabled = None if raw in ('', 'ALL') else {x for x in raw.split(',') if x}

    def _on(self, name: str) -> bool:
        return self.enabled is None or name in self.enabled

    def _index(self, state: TurnState, role: str) -> int | None:
        return profile._find_role(state.view, role)

    def resolve(self, state: TurnState, selected: list[int]) -> RefinementDecision:
        if not selected:
            return RefinementDecision(None, 'NO_SELECTION')
        view = state.view
        role = profile._main_role(view['opts'][selected[0]])
        ledger = state.ledger
        history = list(profile._HANDWRITTEN_STATE.get('main_history') or [])
        last_role = history[-1] if history else 'START'
        if self._on('SECOND_MUNK_THEN_MORGREM') and role == 'PLAY_MUNKIDORI' and (last_role == 'PLAY_MUNKIDORI') and ('RETREAT' in state.legal_roles):
            i = self._index(state, 'EVOLVE_MORGREM')
            if i is not None:
                return RefinementDecision(i, 'SECOND_MUNK_THEN_MORGREM')
        if self._on('READY_GRIM_ONE_LINE_ADD_IMPIDIMP') and role == 'PLAY_MUNKIDORI' and (ledger.active_id == profile.GRIMMSNARL) and (ledger.attack_lines == 1):
            i = self._index(state, 'PLAY_IMPIDIMP')
            if i is not None:
                return RefinementDecision(i, 'READY_GRIM_ONE_LINE_ADD_IMPIDIMP')
        if self._on('OPENING_DRAW_BEFORE_PETREL_WITHOUT_FROSLASS') and role == 'PLAY_PETREL' and (ledger.own_prizes == 6) and (ledger.froslass_lines == 0):
            i = self._index(state, 'PLAY_LILLIE')
            if i is not None:
                return RefinementDecision(i, 'OPENING_DRAW_BEFORE_PETREL_WITHOUT_FROSLASS')
        return RefinementDecision(selected[0], 'BASELINE')

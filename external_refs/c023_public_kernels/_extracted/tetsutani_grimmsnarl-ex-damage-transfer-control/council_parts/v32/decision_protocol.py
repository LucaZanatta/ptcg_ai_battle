from __future__ import annotations
'Visible-state, handwritten post-arbitration protocol rules.\n\nThis module is deliberately not a model, fitted table, search routine, or record\nlookup.  It encodes a small set of interpretable action-order protocols observed\nrepeatedly in the public game records.  Every override requires both the baseline role\nand the desired role to be currently legal.\n'
from dataclasses import dataclass
import os
from . import validated_rule_profile as profile
from .domain import MORGREM
from .state_model import TurnState

@dataclass(frozen=True)
class ProtocolDecision:
    index: int | None
    rule: str

class ManualProtocolArbiter:

    def __init__(self) -> None:
        raw = os.environ.get('PTCG_PROTOCOL_RULES', 'ALL').strip()
        self.enabled = None if raw in ('', 'ALL') else {x for x in raw.split(',') if x}

    def _on(self, name: str) -> bool:
        return self.enabled is None or name in self.enabled

    def _index(self, state: TurnState, role: str) -> int | None:
        return profile._find_role(state.view, role)

    def resolve(self, state: TurnState, selected: list[int]) -> ProtocolDecision:
        if not selected:
            return ProtocolDecision(None, 'NO_SELECTION')
        view = state.view
        role = profile._main_role(view['opts'][selected[0]])
        flags = list(view.get('flags') or []) + [False] * 4
        energy_used, _supporter_used, stadium_played, retreated = map(bool, flags[:4])
        history = list(profile._HANDWRITTEN_STATE.get('main_history') or [])
        last_role = history[-1] if history else 'START'
        ledger = state.ledger
        if self._on('SEARCH_AFTER_RETREAT') and role == 'PLAY_POKE_PAD' and retreated and (ledger.opponent_hand_size > 2):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'SEARCH_AFTER_RETREAT')
        if self._on('SEARCH_AFTER_STADIUM') and role == 'ATTACH_MUNKIDORI' and stadium_played and (ledger.attack_lines >= 2):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'SEARCH_AFTER_STADIUM')
        if self._on('ACTIVE_MORGREM_EXACT_SEARCH') and role == 'PLAY_LILLIE' and (state.turn >= 8) and (ledger.active_id == MORGREM):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'ACTIVE_MORGREM_EXACT_SEARCH')
        if self._on('LATE_EVOLUTION_BEFORE_SELECTOR') and role == 'PLAY_PETREL' and (state.turn >= 10) and (not energy_used):
            i = self._index(state, 'EVOLVE_GRIMMSNARL')
            if i is not None:
                return ProtocolDecision(i, 'LATE_EVOLUTION_BEFORE_SELECTOR')
        if self._on('LARGE_HAND_ATTACKER_COMPLETION') and role == 'PLAY_PETREL' and (ledger.hand_size >= 8) and (ledger.froslass_lines == 0):
            i = self._index(state, 'EVOLVE_GRIMMSNARL')
            if i is not None:
                return ProtocolDecision(i, 'LARGE_HAND_ATTACKER_COMPLETION')
        if self._on('PASSIVE_LINE_BEFORE_ATTACK') and role == 'ATTACK_SHADOW_BULLET' and stadium_played:
            i = self._index(state, 'PLAY_SNORUNT')
            if i is not None:
                return ProtocolDecision(i, 'PASSIVE_LINE_BEFORE_ATTACK')
        if self._on('ENDGAME_TARGETED_RECOVERY') and role == 'ABILITY_SPIKEMUTH' and energy_used and (ledger.opponent_prizes <= 2):
            i = self._index(state, 'PLAY_PETREL')
            if i is not None:
                return ProtocolDecision(i, 'ENDGAME_TARGETED_RECOVERY')
        if self._on('ATTACK_LINE_BEFORE_EXTRA_MUNK') and role == 'PLAY_MUNKIDORI' and (ledger.attack_lines == 0):
            i = self._index(state, 'PLAY_IMPIDIMP')
            if i is not None:
                return ProtocolDecision(i, 'ATTACK_LINE_BEFORE_EXTRA_MUNK')
        if self._on('PETREL_BEFORE_LONE_ACTIVE_MUNK_ATTACHMENT') and role == 'ATTACH_MUNKIDORI' and (ledger.active_id == profile.MUNKIDORI) and (ledger.munkidori_total == 1):
            i = self._index(state, 'PLAY_PETREL')
            if i is not None:
                return ProtocolDecision(i, 'PETREL_BEFORE_LONE_ACTIVE_MUNK_ATTACHMENT')
        if self._on('GUST_FROM_DAMAGED_ATTACKER') and role == 'ABILITY_SPIKEMUTH' and (ledger.active_damage >= 180) and (ledger.opponent_active_damage == 0):
            i = self._index(state, 'PLAY_BOSS')
            if i is not None:
                return ProtocolDecision(i, 'GUST_FROM_DAMAGED_ATTACKER')
        if self._on('EXACT_SEARCH_BEFORE_LILLIE_WITH_POFFIN') and role == 'PLAY_LILLIE' and (not energy_used) and ('PLAY_POFFIN' in state.legal_roles):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'EXACT_SEARCH_BEFORE_LILLIE_WITH_POFFIN')
        if self._on('RARE_CANDY_STAGING_SEARCH') and role in ('PLAY_POKE_PAD', 'ATTACH_MUNKIDORI') and (profile.RARE_CANDY in ledger.hand) and (ledger.active_energy == 0) and (ledger.active_id in (profile.IMPIDIMP, profile.MORGREM)):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'RARE_CANDY_STAGING_SEARCH')
        if self._on('SEARCH_BEFORE_SOLE_LINE_EVOLUTION') and role == 'EVOLVE_MORGREM' and (ledger.active_id == profile.IMPIDIMP) and (ledger.attack_lines == 1):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'SEARCH_BEFORE_SOLE_LINE_EVOLUTION')
        if self._on('OPENING_SEARCH_BEFORE_GRIMMSNARL') and role == 'EVOLVE_GRIMMSNARL' and (ledger.opponent_prizes == 6) and (ledger.active_damage == 0):
            i = self._index(state, 'ABILITY_SPIKEMUTH')
            if i is not None:
                return ProtocolDecision(i, 'OPENING_SEARCH_BEFORE_GRIMMSNARL')
        if self._on('LATE_ATTACK_BEFORE_SPARE_EVOLUTION') and role == 'EVOLVE_GRIMMSNARL' and (state.turn >= 14) and (not stadium_played):
            i = self._index(state, 'ATTACK_SHADOW_BULLET')
            if i is not None:
                return ProtocolDecision(i, 'LATE_ATTACK_BEFORE_SPARE_EVOLUTION')
        if self._on('ENDGAME_POFFIN_BEFORE_STADIUM_SEARCH') and role == 'ABILITY_SPIKEMUTH' and (ledger.own_prizes <= 2) and ('ATTACK_SHADOW_BULLET' in state.legal_roles):
            i = self._index(state, 'PLAY_POFFIN')
            if i is not None:
                return ProtocolDecision(i, 'ENDGAME_POFFIN_BEFORE_STADIUM_SEARCH')
        if self._on('FINISH_DAMAGED_ACTIVE_BEFORE_RETREAT') and role == 'RETREAT' and (ledger.munkidori_total == 1) and (ledger.opponent_active_damage >= 180):
            i = self._index(state, 'ATTACK_SHADOW_BULLET')
            if i is not None:
                return ProtocolDecision(i, 'FINISH_DAMAGED_ACTIVE_BEFORE_RETREAT')
        return ProtocolDecision(selected[0], 'BASELINE')

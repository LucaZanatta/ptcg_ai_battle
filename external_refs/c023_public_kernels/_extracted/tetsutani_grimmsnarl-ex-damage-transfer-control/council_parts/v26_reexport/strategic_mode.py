from __future__ import annotations
'Strategic-mode arbitration for the pure handwritten hierarchical engine.\n\nThis layer classifies the public resource ledger into a domain operating mode,\nthen resolves only validated conflicts between already-legal semantic actions.\nNo record identifier, fitted threshold, state hash, rollout, or search is used.\n'
from dataclasses import dataclass
from enum import Enum, auto
from .planner import PlannedObjective, TurnObjective
from .state_model import TurnState

class StrategicMode(Enum):
    OPENING_ESTABLISH = auto()
    EMERGENCY_REBUILD = auto()
    ATTACKER_COMPLETION = auto()
    ENGINE_BUILD = auto()
    BACKUP_BUILD = auto()
    PRESSURE = auto()
    ENDGAME = auto()

@dataclass(frozen=True)
class ModeTrace:
    mode: StrategicMode
    reason: str

class StrategicModeController:

    def classify(self, state: TurnState) -> ModeTrace:
        ledger = state.ledger
        if ledger.ready_attackers == 0:
            if ledger.attack_lines == 0:
                if state.turn >= 5:
                    return ModeTrace(StrategicMode.EMERGENCY_REBUILD, 'no remaining attack line after opening')
                return ModeTrace(StrategicMode.OPENING_ESTABLISH, 'opening board has no attack line')
            return ModeTrace(StrategicMode.ATTACKER_COMPLETION, 'attack bodies exist but no Grimmsnarl is ready')
        if state.turn >= 10 or ledger.opponent_prizes <= 2:
            return ModeTrace(StrategicMode.ENDGAME, 'late turn or opponent within two prizes')
        if ledger.froslass_lines < 1 or ledger.munkidori_powered < 1:
            return ModeTrace(StrategicMode.ENGINE_BUILD, 'primary attacker is online but a support engine is missing')
        if ledger.attack_lines < 2:
            return ModeTrace(StrategicMode.BACKUP_BUILD, 'one ready line needs a backup')
        return ModeTrace(StrategicMode.PRESSURE, 'attack and support resources are online')

    def objectives(self, state: TurnState, provisional_role: str) -> list[PlannedObjective]:
        trace = self.classify(state)
        mode = trace.mode
        ledger = state.ledger
        legal = state.legal_roles
        objectives: list[PlannedObjective] = []
        if provisional_role == 'PLAY_UNFAIR_STAMP' and 'ABILITY_SPIKEMUTH' in legal and (not (mode is StrategicMode.ENDGAME and ledger.hand_size <= 3 and (ledger.ready_attackers >= 1))):
            objectives.append(PlannedObjective(TurnObjective.CONTINUE_EXACT_SEARCH, 1200, 100, 'finish the live exact-search resource before generic hand disruption'))
        if provisional_role == 'PLAY_UNFAIR_STAMP' and mode in (StrategicMode.PRESSURE, StrategicMode.ENDGAME) and ('PLAY_PETREL' in legal):
            objectives.append(PlannedObjective(TurnObjective.TARGETED_RECOVERY, 1199, 100, 'pressure mode selects an exact tactical trainer before generic disruption'))
        if provisional_role in {'PLAY_UNFAIR_STAMP', 'PLAY_BOSS', 'PLAY_LILLIE'} and ledger.munkidori_unpowered >= 1 and (not ledger.energy_attached) and ('ATTACH_MUNKIDORI' in legal):
            objectives.append(PlannedObjective(TurnObjective.POWER_DAMAGE_ENGINE, 1201, 100, 'consume the expiring attachment on an unpowered Munkidori before supporter commitment'))
        return sorted(objectives, key=lambda item: (-item.priority, -item.confidence, item.objective.value))

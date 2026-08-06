from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from .domain import FROSLASS, IMPIDIMP, MORGREM, MUNKIDORI, SNORUNT
from .state_model import TurnState

class TurnObjective(Enum):
    MOVE_DAMAGE = auto()
    ESTABLISH_STADIUM = auto()
    BUILD_ATTACKER = auto()
    BUILD_BACKUP_ATTACKER = auto()
    BUILD_FROSLASS_ENGINE = auto()
    POWER_DAMAGE_ENGINE = auto()
    POWER_ACTIVE_ATTACKER = auto()
    POWER_ACTIVE_ENGINE = auto()
    COMPLETE_ATTACKER = auto()
    ACCELERATE_ATTACKER = auto()
    TACTICAL_SEARCH = auto()
    BROAD_SEARCH = auto()
    REPOSITION = auto()
    POWER_ACTIVE_BASIC = auto()
    BANK_SUPPORTER = auto()
    REFILL_HAND = auto()
    TARGETED_RECOVERY = auto()
    RESET_OPPONENT_HAND = auto()
    EXPAND_BOARD = auto()
    REFRESH_SEARCH_ENGINE = auto()
    REMOVE_TOOL = auto()
    DISRUPT = auto()
    KEEP_PRESSURE = auto()
    ATTACK = auto()
    END_TURN = auto()
    RECOVER_LOST_ATTACKER = auto()
    RESTORE_SEARCH_ENGINE = auto()
    COMPLETE_PASSIVE_ENGINE = auto()
    CONTINUE_ATTACK_DEVELOPMENT = auto()
    CONTINUE_EXACT_SEARCH = auto()
    COMPATIBILITY = auto()

@dataclass(frozen=True)
class PlannedObjective:
    objective: TurnObjective
    priority: int
    confidence: int
    reason: str

class ObjectivePlanner:

    def plan_main(self, state: TurnState, baseline_role: str) -> list[PlannedObjective]:
        l = state.ledger
        out: list[PlannedObjective] = []
        if 'ABILITY_ADRENA' in state.legal_roles:
            out.append(PlannedObjective(TurnObjective.MOVE_DAMAGE, 1000, 100, 'consume available Adrena-Brain damage movement'))
        if 'PLAY_SPIKEMUTH' in state.legal_roles and (not l.stadium_live):
            out.append(PlannedObjective(TurnObjective.ESTABLISH_STADIUM, 930, 95, 'install the persistent one-Pokemon search engine'))
        if baseline_role == 'PLAY_LILLIE' and 'PLAY_UNFAIR_STAMP' in state.legal_roles:
            out.append(PlannedObjective(TurnObjective.RESET_OPPONENT_HAND, 928, 100, 'convert the supporter window into opponent-hand disruption instead of self-draw'))
        if baseline_role == 'PLAY_LILLIE' and 'PLAY_POFFIN' in state.legal_roles and (l.attack_lines <= 2) and (l.bench_free >= 1):
            out.append(PlannedObjective(TurnObjective.EXPAND_BOARD, 927, 96, 'thin the deck and create missing attack bodies before generic hand refill'))
        if l.active_id == MORGREM and l.ready_attackers == 0 and ('EVOLVE_GRIMMSNARL' in state.legal_roles) and (baseline_role == 'PLAY_NIGHT_STRETCHER' and (not l.supporter_used) or (baseline_role == 'PLAY_IMPIDIMP' and 1 <= l.own_prizes <= 5) or (baseline_role == 'PLAY_MUNKIDORI' and l.opponent_prizes <= 2)):
            out.append(PlannedObjective(TurnObjective.COMPLETE_ATTACKER, 925, 98, 'finish the Active Morgrem win condition before recovery or redundant bench development'))
        if baseline_role == 'PLAY_IMPIDIMP' and state.turn >= 3 and (l.attack_lines >= 2) and ('PLAY_SPIKEMUTH' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.REFRESH_SEARCH_ENGINE, 924, 97, 'developed attack board: establish the persistent search engine before another Basic'))
        if baseline_role == 'ABILITY_SPIKEMUTH' and state.turn >= 6 and (l.hand[SNORUNT] == 0) and (l.froslass_lines <= 1) and ('PLAY_TOOL_SCRAPPER' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.REMOVE_TOOL, 921, 96, 'remove an opposing Tool before spending the turn on another one-card search'))
        if l.hand_size <= 3 and l.active_id == MUNKIDORI and (baseline_role == 'ATTACH_MUNKIDORI') and ('ABILITY_SPIKEMUTH' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.BUILD_ATTACKER, 900, 94, 'tiny-hand Munkidori stall: create an attacker before powering the stall'))
        if baseline_role == 'ATTACH_MUNKIDORI' and l.active_id == FROSLASS and (l.ready_attackers == 0) and ('ABILITY_SPIKEMUTH' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.BUILD_ATTACKER, 899, 94, 'active Froslass stall: search an attacker before powering the damage engine'))
        if baseline_role == 'END' and l.active_id == IMPIDIMP and (not l.energy_attached) and (l.munkidori_unpowered == 0) and ('ATTACH_IMPIDIMP' in state.legal_roles) and ('ATTACK_FILCH' not in state.legal_roles) and ('ATTACK_IMPIDIMP' not in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.POWER_ACTIVE_ATTACKER, 898, 94, 'convert the unused attachment into next-turn active pressure'))
        if baseline_role == 'ATTACH_IMPIDIMP' and l.active_id == FROSLASS and (not l.energy_attached) and ('ATTACH_FROSLASS' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.POWER_ACTIVE_ENGINE, 897, 94, 'power the active Froslass engine before a benched attacker'))
        if baseline_role == 'PLAY_POKE_PAD' and l.active_id == MORGREM and (l.active_energy == 0) and ('EVOLVE_GRIMMSNARL' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.COMPLETE_ATTACKER, 896, 93, 'complete the visible active line before broad search'))
        if baseline_role == 'PLAY_NIGHT_STRETCHER' and l.supporter_used and ('PLAY_POKEGEAR' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.BANK_SUPPORTER, 895, 92, 'bank a next-turn supporter after the current supporter is used'))
        if baseline_role == 'ATTACK_SHADOW_BULLET' and l.munkidori_unpowered >= 1 and (not l.energy_attached) and ('ATTACH_MUNKIDORI' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.POWER_DAMAGE_ENGINE, 919, 100, 'activate the remaining Munkidori before converting the turn into damage'))
        if baseline_role == 'PLAY_SNORUNT' and 'ATTACK_SHADOW_BULLET' in state.legal_roles:
            out.append(PlannedObjective(TurnObjective.KEEP_PRESSURE, 918, 92, 'attack-ready board: take Shadow Bullet before adding a future Froslass Basic'))
        if baseline_role == 'ABILITY_ADRENA' and (not l.stadium_live) and (state.turn <= 10) and ('EVOLVE_FROSLASS' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.BUILD_FROSLASS_ENGINE, 917, 98, 'complete the passive damage engine before moving its counters'))
        if baseline_role == 'EVOLVE_MORGREM' and l.attack_lines <= 1 and (l.ready_attackers == 0) and ('PLAY_RARE_CANDY' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.ACCELERATE_ATTACKER, 916, 94, 'single developing line: use Rare Candy to reach the attacker immediately'))
        if baseline_role == 'ABILITY_SPIKEMUTH' and l.attack_lines >= 3 and (l.dark_in_hand >= 1) and ('PLAY_DAWN' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.TACTICAL_SEARCH, 915, 92, 'mature attack board and Energy secured: use Dawn for the missing exact Pokemon'))
        if baseline_role == 'ABILITY_SPIKEMUTH' and l.hand_size <= 4 and (not l.supporter_used) and ('PLAY_LILLIE' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.REFILL_HAND, 914, 92, 'four-or-fewer-card hand: refill before another single-card search'))
        if baseline_role == 'PLAY_POFFIN' and l.froslass_lines >= 1 and (not l.supporter_used) and ('PLAY_PETREL' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.TARGETED_RECOVERY, 913, 90, 'passive engine established: use Petrel to obtain the next functional trainer'))
        if l.ready_attackers == 0:
            out.append(PlannedObjective(TurnObjective.COMPLETE_ATTACKER, 820, 80, 'establish the first attack-ready Grimmsnarl'))
        elif l.attack_lines < 2:
            out.append(PlannedObjective(TurnObjective.BUILD_BACKUP_ATTACKER, 760, 75, 'preserve a second attacker line'))
        if l.munkidori_total > 0 and l.munkidori_powered == 0 and (not l.energy_attached):
            out.append(PlannedObjective(TurnObjective.POWER_DAMAGE_ENGINE, 720, 78, 'bring Adrena-Brain online'))
        if l.froslass_lines == 0 and l.bench_free >= 2:
            out.append(PlannedObjective(TurnObjective.BUILD_FROSLASS_ENGINE, 660, 65, 'establish the passive damage engine'))
        if not l.supporter_used and l.hand_size <= 5:
            out.append(PlannedObjective(TurnObjective.REFILL_HAND, 600, 60, 'low hand requires draw'))
        if l.dual_engine_complete and baseline_role == 'RETREAT' and ('ATTACK_SHADOW_BULLET' in state.legal_roles):
            out.append(PlannedObjective(TurnObjective.KEEP_PRESSURE, 580, 92, 'complete dual-engine board converts the turn into damage now'))
        if 'ATTACK_SHADOW_BULLET' in state.legal_roles:
            out.append(PlannedObjective(TurnObjective.ATTACK, 300, 50, 'take the available main attack'))
        out.append(PlannedObjective(TurnObjective.COMPATIBILITY, 0, 0, 'retain the validated low-level ordering when no objective conflict dominates'))
        return sorted(out, key=lambda x: (-x.priority, -x.confidence, x.objective.value))

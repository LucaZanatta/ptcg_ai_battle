from __future__ import annotations
'Fixed, visible-state protocols for card-effect selections.'
import os
from . import validated_rule_profile as profile
from .state_model import TurnState

class ManualSelectionProtocol:

    def __init__(self) -> None:
        raw = os.environ.get('PTCG_SELECTION_RULES', 'ALL').strip()
        self.enabled = None if raw in ('', 'ALL') else {x for x in raw.split(',') if x}
        refined = os.environ.get('PTCG_V32_SELECTION_RULES', 'ALL').strip()
        self.refined = None if refined in ('', 'ALL') else {x for x in refined.split(',') if x}

    def _on(self, name: str) -> bool:
        return self.enabled is None or name in self.enabled

    def _ref_on(self, name: str) -> bool:
        return self.refined is None or name in self.refined

    @staticmethod
    def _card(view: dict, selected: list[int]) -> int:
        if not selected:
            return 0
        return int(view['opts'][selected[0]].get('source_id', 0) or 0)

    @staticmethod
    def _choose(view: dict, cid: int) -> list[int] | None:
        return profile._choose_first(view, lambda s: int(s.get('source_id', 0) or 0) == cid)

    def resolve_to_hand(self, view: dict, selected: list[int]) -> list[int]:
        if not selected:
            return selected
        state = TurnState.from_view(view)
        baseline = self._card(view, selected)
        effect = int(view.get('effect', 0) or 0)
        l = state.ledger
        if self._on('SPIKEMUTH_MORGREM_FOR_ACTIVE_SNORUNT') and effect == profile.SPIKEMUTH and (baseline == profile.GRIMMSNARL) and (l.active_id == profile.SNORUNT) and (not l.supporter_used):
            hit = self._choose(view, profile.MORGREM)
            if hit:
                return hit
        if self._on('SPIKEMUTH_MORGREM_FOR_THREE_LINES') and effect == profile.SPIKEMUTH and (baseline == profile.IMPIDIMP) and (l.active_id == profile.IMPIDIMP) and (l.attack_lines >= 3):
            hit = self._choose(view, profile.MORGREM)
            if hit:
                return hit
        if self._on('SPIKEMUTH_MORGREM_FOR_NEW_FROSLASS') and effect == profile.SPIKEMUTH and (baseline in (profile.IMPIDIMP, profile.GRIMMSNARL)) and (l.active_id == profile.FROSLASS) and l.active_new:
            hit = self._choose(view, profile.MORGREM)
            if hit:
                return hit
        if self._on('ENDGAME_SPIKEMUTH_GRIMMSNARL') and effect == profile.SPIKEMUTH and (baseline == profile.MORGREM) and (l.own_prizes <= 2):
            hit = self._choose(view, profile.GRIMMSNARL)
            if hit:
                return hit
        if self._on('POKEPAD_MUNKIDORI_FOR_ACTIVE_SNORUNT') and effect == profile.POKE_PAD and (baseline == profile.FROSLASS) and (l.active_id == profile.SNORUNT):
            hit = self._choose(view, profile.MUNKIDORI)
            if hit:
                return hit
        if self._on('PETREL_NIGHT_STRETCHER_FOR_UNPOWERED_MUNK') and effect == profile.PETREL and (baseline == profile.POKE_PAD) and (l.deck_size <= 20) and (l.munkidori_unpowered >= 1):
            hit = self._choose(view, profile.NIGHT_STRETCHER)
            if hit:
                return hit
        if self._on('POKEGEAR_DAWN_WHEN_LILLIE_BANKED') and effect == profile.POKEGEAR and (baseline == profile.PETREL) and (l.hand[profile.LILLIE] >= 1):
            hit = self._choose(view, profile.DAWN)
            if hit:
                return hit
        if self._ref_on('POKEPAD_MUNK_FOR_ACTIVE_IMPIDIMP_WITH_DARK') and effect == profile.POKE_PAD and (baseline == profile.FROSLASS) and (l.active_id == profile.IMPIDIMP) and (l.hand[profile.DARK] > 0):
            hit = self._choose(view, profile.MUNKIDORI)
            if hit:
                return hit
        if self._ref_on('POKEPAD_MORGREM_FOR_FULL_BENCH_ACTIVE_IMPIDIMP') and effect == profile.POKE_PAD and (baseline == profile.IMPIDIMP) and (l.active_id == profile.IMPIDIMP) and (l.bench_free == 0):
            hit = self._choose(view, profile.MORGREM)
            if hit:
                return hit
        if self._ref_on('POKEPAD_FROSLASS_AFTER_SUPPORTER_TWO_PASSIVE_LINES') and effect == profile.POKE_PAD and (baseline == profile.MUNKIDORI) and l.supporter_used and (l.froslass_lines >= 2):
            hit = self._choose(view, profile.FROSLASS)
            if hit:
                return hit
        if self._ref_on('STRETCHER_DARK_FOR_READY_GRIM_UNPOWERED_MUNK') and effect == profile.NIGHT_STRETCHER and (baseline == profile.GRIMMSNARL) and (l.active_id == profile.GRIMMSNARL) and (l.munkidori_unpowered >= 1):
            hit = self._choose(view, profile.DARK)
            if hit:
                return hit
        if self._ref_on('STRETCHER_GRIM_FOR_ACTIVE_IMPIDIMP_AFTER_SUPPORTER') and effect == profile.NIGHT_STRETCHER and (baseline == profile.DARK) and (l.active_id == profile.IMPIDIMP) and l.supporter_used:
            hit = self._choose(view, profile.GRIMMSNARL)
            if hit:
                return hit
        if self._ref_on('SPIKEMUTH_GRIM_FOR_DAMAGED_OPPOSING_ACTIVE') and effect == profile.SPIKEMUTH and (baseline == profile.IMPIDIMP) and (l.active_damage == 0) and (l.opponent_active_damage >= 180):
            hit = self._choose(view, profile.GRIMMSNARL)
            if hit:
                return hit
        if self._ref_on('SPIKEMUTH_IMPIDIMP_FOR_SPARSE_BENCH') and effect == profile.SPIKEMUTH and (baseline == profile.GRIMMSNARL) and (l.bench_used <= 2) and (l.munkidori_unpowered >= 1):
            hit = self._choose(view, profile.IMPIDIMP)
            if hit:
                return hit
        if self._ref_on('POKEPAD_MORGREM_FOR_FROSLASS_PIVOT_THREE_LINES') and effect == profile.POKE_PAD and (baseline == profile.MUNKIDORI) and (l.active_id == profile.FROSLASS) and (l.attack_lines >= 3):
            hit = self._choose(view, profile.MORGREM)
            if hit:
                return hit
        return selected

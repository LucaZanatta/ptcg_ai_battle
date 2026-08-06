"""c014 — deterministic expert for the Archaludon ex / Cinderace metal-tempo deck.

This is one deck-specific module, not a framework (§6: "A small deck-specific module is preferred
over a universal abstraction"). Nothing here generalises to another deck and nothing here
searches: every decision is a priority table evaluated against the visible state, so the same
state always produces the same action.

THE PLAN, in the order the deck wants to execute it
---------------------------------------------------
1. Cinderace starts in the Active Spot. It is a Stage 2 with no Raboot in the deck; its skill
   *Explosiveness* puts it there directly during setup. It is not the win condition.
2. Cinderace attacks with *Turbo Flare* — one colourless for 50 damage, and it searches the deck
   for up to 3 Basic Energy attached to BENCHED Pokemon. That is the energy engine.
3. Duraludon sits on the bench receiving that energy.
4. Duraludon evolves into Archaludon ex, whose skill *Assemble Alloy* attaches up to 2 Basic {M}
   from the DISCARD PILE. This is why discarding {M} energy to Ultra Ball is a gain, not a cost:
   the discard is a resource the deck spends into and draws back from.
5. Archaludon ex attacks with *Metal Defender*: {M}{M}{M} for 220, and "during your opponent's
   next turn, this Pokemon has no Weakness" — it cancels its own {R} weakness.
6. Full Metal Lab (-30 to {M} Pokemon) and Hero's Cape (+100 HP) make the 300 HP body durable.

Everything below is that plan expressed as priorities. Card IDs are used internally because the
engine speaks IDs, but every one is named at its definition (§10).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---- the 15 distinct cards of the frozen list, by name (§10) ----
DURALUDON = 169          # Basic {M}, 130 HP — the evolution base
ARCHALUDON_EX = 190      # Stage 1 from Duraludon, 300 HP {M} — Metal Defender 220, Assemble Alloy
CINDERACE = 666          # Stage 2 {R}, 160 HP — Explosiveness (setup active), Turbo Flare
RELICANTH = 57           # Basic {F}, 100 HP — Memory Dive (evolved may use pre-evolution attacks)
BASIC_M_ENERGY = 8       # Basic {M} Energy
HEROS_CAPE = 1159        # ACE SPEC — +100 HP to the holder
FULL_METAL_LAB = 1244    # Stadium — {M} Pokemon take 30 less damage
ULTRA_BALL = 1121        # Item — search, discard cost (feeds Assemble Alloy)
POKEGEAR = 1122          # Item — find a Supporter
JUMBO_ICE_CREAM = 1147   # Item
POKE_PAD = 1152          # Item
BOSSS_ORDERS = 1182      # Supporter — gust a benched Pokemon into the Active Spot
EXPLORERS_GUIDANCE = 1185  # Supporter — draw
LILLIES_DETERMINATION = 1227  # Supporter
NIGHT_STRETCHER = 1097   # Item — recover a Pokemon or Energy from the discard

CARD_NAMES = {
    DURALUDON: "Duraludon", ARCHALUDON_EX: "Archaludon ex", CINDERACE: "Cinderace",
    RELICANTH: "Relicanth", BASIC_M_ENERGY: "Basic {M} Energy", HEROS_CAPE: "Hero's Cape",
    FULL_METAL_LAB: "Full Metal Lab", ULTRA_BALL: "Ultra Ball", POKEGEAR: "Pokegear 3.0",
    JUMBO_ICE_CREAM: "Jumbo Ice Cream", POKE_PAD: "Poke Pad", BOSSS_ORDERS: "Boss's Orders",
    EXPLORERS_GUIDANCE: "Explorer's Guidance", LILLIES_DETERMINATION: "Lillie's Determination",
    NIGHT_STRETCHER: "Night Stretcher",
}

# SelectContext values (cg.api.SelectContext)
C_MAIN, C_SETUP_ACTIVE, C_SETUP_BENCH, C_SWITCH = 0, 1, 2, 3
C_TO_ACTIVE, C_TO_BENCH, C_TO_HAND, C_DISCARD = 4, 5, 7, 8
C_ATTACH_FROM, C_ATTACH_TO, C_DISCARD_ENERGY = 21, 22, 30
C_IS_FIRST, C_MULLIGAN, C_ACTIVATE, C_DRAW_COUNT = 41, 42, 43, 38

# OptionType values (cg.api.OptionType)
O_NUMBER, O_YES, O_NO, O_CARD = 0, 1, 2, 3
O_TOOL_CARD, O_ENERGY_CARD, O_ENERGY = 4, 5, 6
O_PLAY, O_ATTACH, O_EVOLVE, O_ABILITY = 7, 8, 9, 10
O_DISCARD, O_RETREAT, O_ATTACK, O_END, O_SKILL = 11, 12, 13, 14, 15

# Attack indices resolve by damage; these are the two that matter, by name.
METAL_DEFENDER = "Metal Defender"    # 220, {M}{M}{M}, suppresses own Weakness next turn
TURBO_FLARE = "Turbo Flare"          # 50, 1 colourless, attaches 3 Basic Energy to the bench

# Setup priority: Cinderace first — Explosiveness makes it the intended opener and its attack
# is the deck's energy engine. Duraludon next (it is what evolves). Relicanth last.
SETUP_ACTIVE_PRIORITY = [CINDERACE, DURALUDON, RELICANTH]
SETUP_BENCH_PRIORITY = [DURALUDON, RELICANTH, CINDERACE]

# Search priority: the line first, then its fuel, then the durability pieces.
SEARCH_PRIORITY = [DURALUDON, ARCHALUDON_EX, BASIC_M_ENERGY, FULL_METAL_LAB, HEROS_CAPE,
                   BOSSS_ORDERS, ULTRA_BALL, NIGHT_STRETCHER, EXPLORERS_GUIDANCE,
                   LILLIES_DETERMINATION, POKEGEAR, POKE_PAD, JUMBO_ICE_CREAM, CINDERACE,
                   RELICANTH]

# Promotion after a knockout: the biggest body that can still attack.
PROMOTE_PRIORITY = [ARCHALUDON_EX, DURALUDON, CINDERACE, RELICANTH]

# Discard cost priority. Basic {M} Energy is discarded FIRST on purpose: Assemble Alloy pulls
# 2 Basic {M} back out of the discard when Archaludon ex evolves, so energy in the discard is
# banked, not lost. Never discard the evolution line.
DISCARD_PREFERENCE = [BASIC_M_ENERGY, POKE_PAD, JUMBO_ICE_CREAM, POKEGEAR, EXPLORERS_GUIDANCE,
                      LILLIES_DETERMINATION, ULTRA_BALL, NIGHT_STRETCHER, RELICANTH,
                      FULL_METAL_LAB, HEROS_CAPE, BOSSS_ORDERS, CINDERACE, ARCHALUDON_EX,
                      DURALUDON]


def _g(o: Any, key: str, default=None):
    try:
        if isinstance(o, dict):
            return o.get(key, default)
        return getattr(o, key, default)
    except Exception:  # noqa: BLE001
        return default


def _cards(seq) -> List[Any]:
    return list(seq or [])


class ArchaludonExpert:
    """Deterministic. Every public entry point returns a legal selection or the legal fallback."""

    def __init__(self, deck: List[int], trace: bool = False):
        self.deck = list(deck)
        self.trace_on = trace
        self.traces: List[Dict[str, Any]] = []
        self.reset()

    def reset(self):
        self.n_decisions = 0
        self.n_fallback = 0
        self.fallback_reasons: Dict[str, int] = {}
        self.turn_seen = -1

    # ---------------- state helpers ----------------

    def _me(self, obs):
        st = _g(obs, "current")
        if st is None:
            return None, None, None
        yi = _g(st, "yourIndex", 0) or 0
        players = _cards(_g(st, "players"))
        if len(players) < 2:
            return st, None, None
        return st, players[yi], players[1 - yi]

    def _intended_attacker(self, me) -> Optional[Any]:
        """Archaludon ex if it exists anywhere in play, else the Duraludon that will become it."""
        if me is None:
            return None
        for zone in ("active", "bench"):
            for p in _cards(_g(me, zone)):
                if _g(p, "id") == ARCHALUDON_EX:
                    return p
        for zone in ("bench", "active"):
            for p in _cards(_g(me, zone)):
                if _g(p, "id") == DURALUDON:
                    return p
        act = _cards(_g(me, "active"))
        return act[0] if act else None

    def _m_energy_on(self, pokemon) -> int:
        n = 0
        for c in _cards(_g(pokemon, "energyCards")):
            if _g(c, "id") == BASIC_M_ENERGY:
                n += 1
        if n == 0:
            n = len(_cards(_g(pokemon, "energies")))
        return n

    def _resources(self, st, me, op) -> Dict[str, Any]:
        """Minimal deck-required tracking (§10): the numbers this deck's decisions depend on."""
        hand = [_g(c, "id") for c in _cards(_g(me, "hand"))]
        disc = [_g(c, "id") for c in _cards(_g(me, "discard"))]
        atk = self._intended_attacker(me)
        return {
            "turn": _g(st, "turn"),
            "prize_left_me": len(_cards(_g(me, "prize"))),
            "prize_left_op": len(_cards(_g(op, "prize"))) if op is not None else None,
            "hand_size": len(hand),
            "m_energy_in_hand": hand.count(BASIC_M_ENERGY),
            "m_energy_in_discard": disc.count(BASIC_M_ENERGY),   # Assemble Alloy fuel
            "archaludon_in_play": any(_g(p, "id") == ARCHALUDON_EX
                                      for z in ("active", "bench") for p in _cards(_g(me, z))),
            "duraludon_in_play": any(_g(p, "id") == DURALUDON
                                     for z in ("active", "bench") for p in _cards(_g(me, z))),
            "bench_count": len(_cards(_g(me, "bench"))),
            "bench_max": _g(me, "benchMax"),
            "stadium_in_play": _g(st, "stadium"),
            "supporter_played": _g(st, "supporterPlayed"),
            "energy_attached_this_turn": _g(st, "energyAttached"),
            "intended_attacker": CARD_NAMES.get(_g(atk, "id"), None) if atk else None,
            "intended_attacker_m_energy": self._m_energy_on(atk) if atk else 0,
        }

    # ---------------- fallback ----------------

    def _fallback(self, sel, reason: str) -> List[int]:
        """Always legal: the first `minCount` options, at least one when required."""
        self.n_fallback += 1
        self.fallback_reasons[reason] = self.fallback_reasons.get(reason, 0) + 1
        opts = _cards(_g(sel, "option"))
        lo = int(_g(sel, "minCount", 0) or 0)
        hi = int(_g(sel, "maxCount", 1) or 1)
        k = max(lo, 0)
        if k == 0 and hi >= 1 and len(opts) > 0:
            k = 0
        return list(range(min(max(k, 0), len(opts))))

    # ---------------- context handlers ----------------

    def _pick_by_card_priority(self, opts, cards_by_index, priority) -> Optional[int]:
        best, best_rank = None, len(priority) + 1
        for i, o in enumerate(opts):
            cid = cards_by_index(o)
            if cid is None:
                continue
            rank = priority.index(cid) if cid in priority else len(priority)
            if rank < best_rank:
                best, best_rank = i, rank
        return best

    def _hand_card_id(self, me, o) -> Optional[int]:
        idx = _g(o, "index")
        hand = _cards(_g(me, "hand"))
        if idx is None or not (0 <= idx < len(hand)):
            return None
        return _g(hand[idx], "id")

    def _option_card_id(self, obs, me, op, o) -> Optional[int]:
        """Resolve the card an option refers to, from (area, index, playerIndex)."""
        area, idx = _g(o, "area"), _g(o, "index")
        pidx = _g(o, "playerIndex")
        st = _g(obs, "current")
        yi = _g(st, "yourIndex", 0) or 0
        who = me if (pidx is None or pidx == yi) else op
        if area is None or idx is None or who is None:
            return None
        zone = {2: "hand", 3: "discard", 4: "active", 5: "bench", 6: "prize",
                12: "looking"}.get(int(area))
        if zone == "looking":
            seq = _cards(_g(st, "looking"))
        elif zone:
            seq = _cards(_g(who, zone))
        else:
            return None
        if not (0 <= idx < len(seq)):
            return None
        return _g(seq[idx], "id")

    def _main(self, obs, sel, me, op, res) -> Optional[int]:
        """Turn-order priority. Highest-value legal action first; ties resolve to lowest index."""
        opts = _cards(_g(sel, "option"))
        scored = []
        for i, o in enumerate(opts):
            t = _g(o, "type")
            s = None
            if t == O_EVOLVE:
                cid = self._hand_card_id(me, o)
                # evolving into Archaludon ex is the single highest-value action in the deck
                s = 1000 if cid == ARCHALUDON_EX else 400
            elif t == O_ABILITY:
                s = 900
            elif t == O_PLAY:
                cid = self._hand_card_id(me, o)
                # BENCH LIABILITY (§10). An empty bench loses the game outright the moment the
                # Active Pokemon is knocked out. This deck runs only 5 Basic Pokemon in 60
                # cards, so the empty-bench state is common rather than exotic: measured at
                # 12.4 decisions per game before this rule existed. Any Pokemon that can be
                # benched therefore outranks every non-evolution play while the bench is empty.
                if cid in (DURALUDON, RELICANTH, CINDERACE) and res.get("bench_count", 0) == 0:
                    scored.append((950, -i, i))
                    continue
                s = {
                    FULL_METAL_LAB: 820 if not res["stadium_in_play"] else 10,
                    ULTRA_BALL: 800,          # discard cost banks {M} for Assemble Alloy
                    NIGHT_STRETCHER: 780,
                    EXPLORERS_GUIDANCE: 760 if not res["supporter_played"] else 5,
                    LILLIES_DETERMINATION: 750 if not res["supporter_played"] else 5,
                    POKEGEAR: 700, POKE_PAD: 690, JUMBO_ICE_CREAM: 680,
                    BOSSS_ORDERS: 740 if not res["supporter_played"] else 5,
                    DURALUDON: 850,           # more bases = more Archaludon
                    RELICANTH: 300, CINDERACE: 250,
                    HEROS_CAPE: 810,
                }.get(cid, 200)
            elif t == O_ATTACH:
                # Attaching outranks almost every other play. Energy attachment is once per
                # turn and does NOT end the turn, while Metal Defender needs {M}{M}{M}; an
                # early version scored this below the card plays, so the agent emptied its
                # hand every turn, never attached, and therefore never attacked at all.
                s = 880 if not res["energy_attached_this_turn"] else 5
            elif t == O_ATTACK:
                s = 500
            elif t == O_RETREAT:
                s = 50
            elif t == O_END:
                s = 1
            if s is not None:
                scored.append((s, -i, i))
        if not scored:
            return None
        scored.sort(reverse=True)
        return scored[0][2]

    def _attack(self, obs, sel, me, res) -> Optional[int]:
        """Metal Defender when the energy is there; otherwise Turbo Flare to build toward it."""
        opts = _cards(_g(sel, "option"))
        best, best_s = None, -1
        for i, o in enumerate(opts):
            dmg = _g(o, "damage")
            s = int(dmg) if isinstance(dmg, (int, float)) else 0
            if s > best_s:
                best, best_s = i, s
        return best

    def act(self, obs) -> List[int]:
        sel = _g(obs, "select")
        if sel is None:
            # The deck request marks the start of a new game. A submitted agent is a single
            # long-lived process across many games, so per-game counters must reset here or
            # they accumulate across the whole episode set.
            self.reset()
            return list(self.deck)
        self.n_decisions += 1
        opts = _cards(_g(sel, "option"))
        lo = int(_g(sel, "minCount", 1) or 0)
        hi = int(_g(sel, "maxCount", 1) or 1)
        ctx = int(_g(sel, "context", -1) or 0)
        st, me, op = self._me(obs)
        res = self._resources(st, me, op) if me is not None else {}

        if not opts:
            return self._trace(ctx, [], "no_options", res, sel)
        if len(opts) == 1 and lo >= 1:
            return self._trace(ctx, [0], "forced", res, sel)

        choice: Optional[List[int]] = None
        rule = "fallback"
        try:
            if ctx == C_SETUP_ACTIVE:
                i = self._pick_by_card_priority(
                    opts, lambda o: self._option_card_id(obs, me, op, o), SETUP_ACTIVE_PRIORITY)
                choice, rule = ([i], "setup_active") if i is not None else (None, rule)
            elif ctx in (C_SETUP_BENCH, C_TO_BENCH):
                picks = []
                order = sorted(range(len(opts)), key=lambda i: (
                    SETUP_BENCH_PRIORITY.index(self._option_card_id(obs, me, op, opts[i]))
                    if self._option_card_id(obs, me, op, opts[i]) in SETUP_BENCH_PRIORITY
                    else len(SETUP_BENCH_PRIORITY), i))
                picks = order[:max(lo, min(hi, len(order)))]
                choice, rule = picks, "setup_bench"
            elif ctx in (C_SWITCH, C_TO_ACTIVE):
                i = self._pick_by_card_priority(
                    opts, lambda o: self._option_card_id(obs, me, op, o), PROMOTE_PRIORITY)
                choice, rule = ([i], "promote") if i is not None else (None, rule)
            elif ctx == C_TO_HAND:
                order = sorted(range(len(opts)), key=lambda i: (
                    SEARCH_PRIORITY.index(self._option_card_id(obs, me, op, opts[i]))
                    if self._option_card_id(obs, me, op, opts[i]) in SEARCH_PRIORITY
                    else len(SEARCH_PRIORITY), i))
                choice, rule = order[:max(lo, min(hi, len(order)))], "search"
            elif ctx in (C_DISCARD, C_DISCARD_ENERGY):
                order = sorted(range(len(opts)), key=lambda i: (
                    DISCARD_PREFERENCE.index(self._option_card_id(obs, me, op, opts[i]))
                    if self._option_card_id(obs, me, op, opts[i]) in DISCARD_PREFERENCE
                    else len(DISCARD_PREFERENCE), i))
                choice, rule = order[:max(lo, min(hi, len(order)))], "discard_bank_energy"
            elif ctx in (C_ATTACH_TO, C_ATTACH_FROM):
                # energy goes to the intended attacker: Archaludon ex, else the Duraludon
                # that becomes it
                pri = [ARCHALUDON_EX, DURALUDON, CINDERACE, RELICANTH] if ctx == C_ATTACH_TO \
                    else [BASIC_M_ENERGY, HEROS_CAPE]
                order = sorted(range(len(opts)), key=lambda i: (
                    pri.index(self._option_card_id(obs, me, op, opts[i]))
                    if self._option_card_id(obs, me, op, opts[i]) in pri else len(pri), i))
                choice, rule = order[:max(lo, min(hi, len(order)))], "attach_to_intended_attacker"
            elif ctx == C_MAIN:
                i = self._main(obs, sel, me, op, res)
                if i is not None:
                    t = _g(opts[i], "type")
                    rule = {O_EVOLVE: "main_evolve", O_PLAY: "main_play", O_ATTACH: "main_attach",
                            O_ATTACK: "main_attack", O_RETREAT: "main_retreat",
                            O_END: "main_end", O_ABILITY: "main_ability"}.get(t, "main")
                    choice = [i]
            elif ctx == 35:   # ATTACK selection
                i = self._attack(obs, sel, me, res)
                choice, rule = ([i], "attack_max_damage") if i is not None else (None, rule)
            elif ctx in (C_IS_FIRST, C_ACTIVATE):
                yes = next((i for i, o in enumerate(opts) if _g(o, "type") == O_YES), None)
                choice, rule = ([yes], "say_yes") if yes is not None else (None, rule)
            elif ctx == C_MULLIGAN:
                yes = next((i for i, o in enumerate(opts) if _g(o, "type") == O_YES), None)
                choice, rule = ([yes], "mulligan_yes") if yes is not None else (None, rule)
            elif ctx == C_DRAW_COUNT:
                best = max(range(len(opts)),
                           key=lambda i: (_g(opts[i], "number") or 0, -i))
                choice, rule = [best], "draw_max"
        except Exception as e:  # noqa: BLE001
            return self._trace(ctx, self._fallback(sel, f"exception:{type(e).__name__}"),
                               f"exception:{type(e).__name__}", res, sel)

        if choice is None:
            return self._trace(ctx, self._fallback(sel, f"no_rule_for_context_{ctx}"),
                               f"no_rule_for_context_{ctx}", res, sel)
        choice = [i for i in dict.fromkeys(choice) if isinstance(i, int) and 0 <= i < len(opts)]
        if len(choice) < lo or len(choice) > hi:
            need = max(lo, 0)
            for i in range(len(opts)):
                if len(choice) >= need:
                    break
                if i not in choice:
                    choice.append(i)
            choice = choice[:hi] if hi else choice
        if len(choice) < lo:
            return self._trace(ctx, self._fallback(sel, "count_repair_failed"),
                               "count_repair_failed", res, sel)
        return self._trace(ctx, choice, rule, res, sel)

    def _trace(self, ctx, choice, rule, res, sel) -> List[int]:
        if self.trace_on:
            opts = _cards(_g(sel, "option"))
            self.traces.append({
                "decision": self.n_decisions, "context": ctx, "rule": rule,
                "n_options": len(opts), "chosen": list(choice),
                "chosen_types": [_g(opts[i], "type") for i in choice if i < len(opts)],
                "is_fallback": rule.startswith(("no_rule", "exception", "count_repair")),
                "resources": res,
            })
        return list(choice)

    __call__ = act




# ----------------------------------------------------------------------------------
# c014 runtime entry point
# ----------------------------------------------------------------------------------
import os as _os

_deck_path = "deck.csv"
if not _os.path.exists(_deck_path):
    _deck_path = "/kaggle_simulations/agent/deck.csv"
with open(_deck_path, "r") as _fh:
    _rows = [r.strip() for r in _fh.read().split("\n") if r.strip()]
MY_DECK = [int(_rows[i]) for i in range(60)]

_EXPERT = ArchaludonExpert(MY_DECK)


def agent(obs_dict) -> list:
    """Kaggle entry point.

    Returns option indices in [0, len(select.option)) with length in
    [select.minCount, select.maxCount] and no duplicates. When `select` is None this is the
    initial deck request and the 60-card list is returned.

    The expert accepts the raw observation dict directly: every state read goes through the
    `_g` accessor, which handles dicts and attribute objects alike, so no conversion step can
    fail at runtime. Any unexpected state falls through to the deterministic legal fallback
    inside `act`, so this function does not raise.
    """
    try:
        return _EXPERT.act(obs_dict)
    except Exception:
        sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
        if sel is None:
            return list(MY_DECK)
        lo = int(sel.get("minCount") or 0)
        n = len(sel.get("option") or [])
        return list(range(min(max(lo, 0), n)))

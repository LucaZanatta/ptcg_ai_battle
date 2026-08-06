"""c015 — deterministic anti-meta expert for the Iono's Bellibolt ex Lightning deck.

One deck-specific module, no framework, no search, nothing learned (§6). Written separately from
c014's Archaludon expert rather than abstracted over both: §6 states plainly that duplication is
acceptable when it is faster and safer than abstraction, and a shared "deck engine" would be the
generic multi-deck framework the contract forbids.

THE TWO COUNTER MECHANISMS (§11 requires them visible in rule code)
------------------------------------------------------------------
MECHANISM A — `_mechanism_a_electric_streamer`
    Iono's Bellibolt ex has *Electric Streamer*: "As often as you like during your turn, you may
    attach a Basic {L} Energy card from your hand to 1 of your Iono's Pokemon." The deck runs 22
    Basic {L}. The target archetype (Archaludon metal tempo) can attach exactly once per turn and
    its own declared loss mode is that it "must reach {M}{M}{M} through one manual attachment per
    turn". So this ability is scored ABOVE every other action while a {L} is in hand.

MECHANISM B — `_mechanism_b_voltaic_chain_damage`
    Iono's Voltorb has *Voltaic Chain*: "20 damage. This attack does 20 more damage for each {L}
    Energy attached to all of your Iono's Pokemon." Mechanism A is its input: every energy
    Mechanism A places anywhere on the board raises this attack's damage. The expert computes the
    scaled value explicitly rather than trusting the static `damage` field, because the static
    field reads 20 and would lose every comparison.

The mechanisms are deliberately coupled: A is only worth its high priority because B converts the
stockpile into damage, and B is only strong because A fills the board faster than the target can.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---- the 15 distinct cards of the frozen list, by name (§11) ----
BASIC_L_ENERGY = 4        # Basic {L} Energy — 22 copies, the fuel for Mechanism A
IONOS_VOLTORB = 265       # Basic {L} 70 HP — Voltaic Chain, MECHANISM B
IONOS_TADBULB = 268       # Basic {L} 60 HP — evolves into Bellibolt ex
IONOS_BELLIBOLT_EX = 269  # Stage 1 {L} 280 HP — Electric Streamer (MECHANISM A), Thunderous Bolt
IONOS_WATTREL = 270       # Basic {L} 60 HP — evolves into Kilowattrel
IONOS_KILOWATTREL = 271   # Stage 1 {L} 120 HP — Flashing Draw, Mach Bolt 70
LILLIES_DETERMINATION = 1227  # Supporter — shuffle hand, draw 6 (8 if 6 prizes remain)
CANARI = 1233             # Supporter — discard a card, search up to 4 {L} Pokemon
BUDDY_BUDDY_POFFIN = 1086  # Item — put up to 2 Basic Pokemon with <=70 HP onto the bench
ULTRA_BALL = 1121         # Item — discard 2, search a Pokemon
LEVINCIA = 1254           # Stadium — return up to 2 Basic {L} from discard to hand each turn
NIGHT_STRETCHER = 1097    # Item — a Pokemon or Basic Energy from discard to hand
POKE_PAD = 1152           # Item — search a Pokemon without a Rule Box
MAX_ROD = 1110            # Item — up to 5 Pokemon/Basic Energy from discard to hand
ENERGY_RETRIEVAL = 1118   # Item — 2 Basic Energy from discard to hand

CARD_NAMES = {
    BASIC_L_ENERGY: "Basic {L} Energy", IONOS_VOLTORB: "Iono's Voltorb",
    IONOS_TADBULB: "Iono's Tadbulb", IONOS_BELLIBOLT_EX: "Iono's Bellibolt ex",
    IONOS_WATTREL: "Iono's Wattrel", IONOS_KILOWATTREL: "Iono's Kilowattrel",
    LILLIES_DETERMINATION: "Lillie's Determination", CANARI: "Canari",
    BUDDY_BUDDY_POFFIN: "Buddy-Buddy Poffin", ULTRA_BALL: "Ultra Ball",
    LEVINCIA: "Levincia", NIGHT_STRETCHER: "Night Stretcher", POKE_PAD: "Poke Pad",
    MAX_ROD: "Max Rod", ENERGY_RETRIEVAL: "Energy Retrieval",
}

MY_POKEMON = {IONOS_VOLTORB, IONOS_TADBULB, IONOS_BELLIBOLT_EX, IONOS_WATTREL,
              IONOS_KILOWATTREL}

# metal-tempo target cards, used only for the minimal opponent inference the thesis needs
TARGET_DURALUDON = 169
TARGET_ARCHALUDON_EX = 190

C_MAIN, C_SETUP_ACTIVE, C_SETUP_BENCH, C_SWITCH = 0, 1, 2, 3
C_TO_ACTIVE, C_TO_BENCH, C_TO_HAND, C_DISCARD = 4, 5, 7, 8
C_ATTACH_FROM, C_ATTACH_TO, C_DISCARD_ENERGY = 21, 22, 30
C_IS_FIRST, C_MULLIGAN, C_ACTIVATE, C_DRAW_COUNT, C_ATTACK = 41, 42, 43, 38, 35

O_NUMBER, O_YES, O_NO, O_CARD = 0, 1, 2, 3
O_TOOL_CARD, O_ENERGY_CARD, O_ENERGY = 4, 5, 6
O_PLAY, O_ATTACH, O_EVOLVE, O_ABILITY = 7, 8, 9, 10
O_DISCARD, O_RETREAT, O_ATTACK, O_END, O_SKILL = 11, 12, 13, 14, 15

# Tadbulb leads, so the Active Spot becomes a 280 HP Bellibolt ex rather than a 70 HP Voltorb.
# Measured during development against the c014 target (20 games per arm, before the final panel
# was run): Voltorb-first 0.250, Tadbulb-first 0.400. Voltaic Chain still matters, but it is the
# filler for the turns after Thunderous Bolt locks, not the body that should be exposed.
SETUP_ACTIVE_PRIORITY = [IONOS_TADBULB, IONOS_VOLTORB, IONOS_WATTREL]
SETUP_BENCH_PRIORITY = [IONOS_TADBULB, IONOS_VOLTORB, IONOS_WATTREL]
SEARCH_PRIORITY = [IONOS_TADBULB, IONOS_BELLIBOLT_EX, IONOS_VOLTORB, BASIC_L_ENERGY,
                   IONOS_WATTREL, IONOS_KILOWATTREL, LEVINCIA, BUDDY_BUDDY_POFFIN, CANARI,
                   LILLIES_DETERMINATION, ULTRA_BALL, NIGHT_STRETCHER, MAX_ROD,
                   ENERGY_RETRIEVAL, POKE_PAD]
PROMOTE_PRIORITY = [IONOS_BELLIBOLT_EX, IONOS_KILOWATTREL, IONOS_VOLTORB, IONOS_TADBULB,
                    IONOS_WATTREL]
# never discard the engine or its fuel; spare Items go first
DISCARD_PREFERENCE = [POKE_PAD, ENERGY_RETRIEVAL, MAX_ROD, NIGHT_STRETCHER, ULTRA_BALL,
                      BUDDY_BUDDY_POFFIN, CANARI, LILLIES_DETERMINATION, LEVINCIA,
                      IONOS_WATTREL, IONOS_KILOWATTREL, IONOS_VOLTORB, BASIC_L_ENERGY,
                      IONOS_TADBULB, IONOS_BELLIBOLT_EX]


def _g(o: Any, key: str, default=None):
    try:
        if isinstance(o, dict):
            return o.get(key, default)
        return getattr(o, key, default)
    except Exception:  # noqa: BLE001
        return default


def _cards(seq) -> List[Any]:
    return list(seq or [])


class IonoExpert:
    def __init__(self, deck: List[int], trace: bool = False):
        self.deck = list(deck)
        self.trace_on = trace
        self.traces: List[Dict[str, Any]] = []
        self.reset()

    def reset(self):
        self.n_decisions = 0
        self.n_fallback = 0
        self.fallback_reasons: Dict[str, int] = {}
        self.mech_a_opportunities = 0
        self.mech_a_executions = 0
        self.mech_b_opportunities = 0
        self.mech_b_executions = 0

    # ---------------- state ----------------

    def _me(self, obs):
        st = _g(obs, "current")
        if st is None:
            return None, None, None
        yi = _g(st, "yourIndex", 0) or 0
        players = _cards(_g(st, "players"))
        if len(players) < 2:
            return st, None, None
        return st, players[yi], players[1 - yi]

    def _my_pokemon(self, me) -> List[Any]:
        return _cards(_g(me, "active")) + _cards(_g(me, "bench"))

    def _total_l_energy(self, me) -> int:
        """Total {L} attached across ALL my Pokemon — the input to Mechanism B."""
        n = 0
        for p in self._my_pokemon(me):
            cards = _cards(_g(p, "energyCards"))
            if cards:
                n += sum(1 for c in cards if _g(c, "id") == BASIC_L_ENERGY)
            else:
                n += len(_cards(_g(p, "energies")))
        return n

    # ---------------- MECHANISM B ----------------

    def _mechanism_b_voltaic_chain_damage(self, me) -> int:
        """MECHANISM B — Voltaic Chain: 20 base, +20 per {L} attached to ALL my Pokemon.

        Computed explicitly. The engine reports this attack's static `damage` as 20, so a
        naive max-damage rule would never choose it and the mechanism would never fire.
        """
        return 20 + 20 * self._total_l_energy(me)

    def _target_metal_line_present(self, op) -> Dict[str, Any]:
        """Minimal opponent inference, and only what the thesis needs (§11): is the metal-tempo
        target's evolution line on the board, and is it still un-evolved?"""
        ids = [_g(p, "id") for p in (_cards(_g(op, "active")) + _cards(_g(op, "bench")))]
        return {"target_archetype_detected": any(i in (TARGET_DURALUDON, TARGET_ARCHALUDON_EX)
                                                 for i in ids),
                "unevolved_duraludon_present": TARGET_DURALUDON in ids,
                "archaludon_present": TARGET_ARCHALUDON_EX in ids}

    def _resources(self, st, me, op) -> Dict[str, Any]:
        hand = [_g(c, "id") for c in _cards(_g(me, "hand"))]
        disc = [_g(c, "id") for c in _cards(_g(me, "discard"))]
        tot = self._total_l_energy(me)
        return {
            "turn": _g(st, "turn"),
            "prize_left_me": len(_cards(_g(me, "prize"))),
            "prize_left_op": len(_cards(_g(op, "prize"))) if op is not None else None,
            "hand_size": len(hand),
            "l_energy_in_hand": hand.count(BASIC_L_ENERGY),
            "l_energy_in_discard": disc.count(BASIC_L_ENERGY),
            "total_l_energy_in_play": tot,
            "voltaic_chain_damage": 20 + 20 * tot,
            "bellibolt_in_play": any(_g(p, "id") == IONOS_BELLIBOLT_EX
                                     for p in self._my_pokemon(me)),
            "voltorb_in_play": any(_g(p, "id") == IONOS_VOLTORB
                                   for p in self._my_pokemon(me)),
            "bench_count": len(_cards(_g(me, "bench"))),
            "bench_max": _g(me, "benchMax"),
            "stadium_in_play": _g(st, "stadium"),
            "supporter_played": _g(st, "supporterPlayed"),
            "energy_attached_this_turn": _g(st, "energyAttached"),
            **(self._target_metal_line_present(op) if op is not None else {}),
        }

    # ---------------- fallback ----------------

    def _fallback(self, sel, reason: str) -> List[int]:
        self.n_fallback += 1
        self.fallback_reasons[reason] = self.fallback_reasons.get(reason, 0) + 1
        opts = _cards(_g(sel, "option"))
        lo = int(_g(sel, "minCount", 0) or 0)
        return list(range(min(max(lo, 0), len(opts))))

    # ---------------- helpers ----------------

    def _hand_card_id(self, me, o) -> Optional[int]:
        idx = _g(o, "index")
        hand = _cards(_g(me, "hand"))
        if idx is None or not (0 <= idx < len(hand)):
            return None
        return _g(hand[idx], "id")

    def _option_card_id(self, obs, me, op, o) -> Optional[int]:
        area, idx, pidx = _g(o, "area"), _g(o, "index"), _g(o, "playerIndex")
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

    def _order_by(self, obs, me, op, opts, priority):
        def rank(i):
            cid = self._option_card_id(obs, me, op, opts[i])
            return (priority.index(cid) if cid in priority else len(priority), i)
        return sorted(range(len(opts)), key=rank)

    # ---------------- MECHANISM A + main ----------------

    def _mechanism_a_electric_streamer(self, res) -> bool:
        """MECHANISM A availability: a Basic {L} in hand and Bellibolt ex on the board."""
        return bool(res.get("l_energy_in_hand", 0) > 0 and res.get("bellibolt_in_play"))

    def _main(self, obs, sel, me, op, res) -> Optional[int]:
        opts = _cards(_g(sel, "option"))
        scored = []
        mech_a_available = self._mechanism_a_electric_streamer(res)
        if mech_a_available:
            self.mech_a_opportunities += 1
        mech_b_options = []
        for i, o in enumerate(opts):
            t = _g(o, "type")
            s = None
            if t == O_ABILITY:
                # MECHANISM A. Electric Streamer may be used as often as you like, it does not
                # end the turn, and it is the entire tempo advantage over the target's
                # one-attachment-per-turn clock. It therefore outranks everything.
                s = 1000
            elif t == O_EVOLVE:
                cid = self._hand_card_id(me, o)
                # Bellibolt ex is both the 280 HP body and the engine that grants Mechanism A
                s = 960 if cid == IONOS_BELLIBOLT_EX else 700
            elif t == O_PLAY:
                cid = self._hand_card_id(me, o)
                if cid in MY_POKEMON and res.get("bench_count", 0) == 0:
                    s = 950          # bench liability: an empty bench loses on a knockout
                else:
                    s = {
                        BUDDY_BUDDY_POFFIN: 880,     # two Basics onto the bench at once
                        CANARI: 860 if not res["supporter_played"] else 5,
                        IONOS_TADBULB: 850,          # the Bellibolt line
                        LEVINCIA: 840 if not res["stadium_in_play"] else 10,
                        IONOS_VOLTORB: 830,          # the Mechanism B attacker
                        ULTRA_BALL: 800,
                        NIGHT_STRETCHER: 780, MAX_ROD: 770, ENERGY_RETRIEVAL: 760,
                        LILLIES_DETERMINATION: 750 if not res["supporter_played"] else 5,
                        POKE_PAD: 700, IONOS_WATTREL: 600, IONOS_KILOWATTREL: 600,
                    }.get(cid, 200)
            elif t == O_ATTACH:
                s = 900 if not res["energy_attached_this_turn"] else 5
            elif t == O_ATTACK:
                # MECHANISM B is applied HERE, not only in the dedicated ATTACK context: the
                # engine presents each legal attack as its own option inside MAIN, so a flat
                # score never distinguished Voltaic Chain from a 10-damage Quick Attack and the
                # mechanism measured zero opportunities in smoke.
                dmg = _g(o, "damage")
                v = int(dmg) if isinstance(dmg, (int, float)) else 0
                act = _cards(_g(me, "active"))
                if act and _g(act[0], "id") == IONOS_VOLTORB and v <= 20:
                    v = self._mechanism_b_voltaic_chain_damage(me)   # true scaled damage
                    mech_b_options.append((i, v))
                # attacks END THE TURN, so they stay below every developing play (600+) while
                # still ordering among themselves by real damage
                s = 400 + min(99.0, v / 5.0)
            elif t == O_RETREAT:
                s = 50
            elif t == O_END:
                s = 1
            if s is not None:
                scored.append((s, -i, i))
        if not scored:
            return None
        scored.sort(reverse=True)
        best = scored[0][2]
        if mech_a_available and _g(opts[best], "type") == O_ABILITY:
            self.mech_a_executions += 1
        # Mechanism B rate is measured only over decisions where ATTACKING was the chosen
        # phase. Counting every MAIN decision with Voltorb active would score a correct
        # development play as a missed opportunity and make the rate meaningless.
        if mech_b_options and _g(opts[best], "type") == O_ATTACK:
            self.mech_b_opportunities += 1
            if best in [i for i, _ in mech_b_options]:
                self.mech_b_executions += 1
        return best

    def _attack(self, obs, sel, me, res) -> Optional[int]:
        """MECHANISM B in the attack choice.

        Voltaic Chain's static damage is 20; its real damage is 20 + 20 per {L} in play. Using
        the static field would make the deck's scaling attacker permanently unattractive, so the
        scaled value is substituted when the option is Voltaic Chain.
        """
        opts = _cards(_g(sel, "option"))
        scaled = self._mechanism_b_voltaic_chain_damage(me)
        active = _cards(_g(me, "active"))
        active_id = _g(active[0], "id") if active else None
        if active_id == IONOS_VOLTORB:
            self.mech_b_opportunities += 1
        best, best_v = None, -1
        for i, o in enumerate(opts):
            dmg = _g(o, "damage")
            v = int(dmg) if isinstance(dmg, (int, float)) else 0
            if active_id == IONOS_VOLTORB and v <= 20:
                v = scaled                      # substitute the true scaled value
            if v > best_v:
                best, best_v = i, v
        if active_id == IONOS_VOLTORB and best is not None and best_v == scaled:
            self.mech_b_executions += 1
        return best

    # ---------------- entry ----------------

    def act(self, obs) -> List[int]:
        sel = _g(obs, "select")
        if sel is None:
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
                o = self._order_by(obs, me, op, opts, SETUP_ACTIVE_PRIORITY)
                choice, rule = [o[0]], "setup_active"
            elif ctx in (C_SETUP_BENCH, C_TO_BENCH):
                o = self._order_by(obs, me, op, opts, SETUP_BENCH_PRIORITY)
                choice, rule = o[:max(lo, min(hi, len(o)))], "setup_bench"
            elif ctx in (C_SWITCH, C_TO_ACTIVE):
                o = self._order_by(obs, me, op, opts, PROMOTE_PRIORITY)
                choice, rule = [o[0]], "promote"
            elif ctx == C_TO_HAND:
                o = self._order_by(obs, me, op, opts, SEARCH_PRIORITY)
                choice, rule = o[:max(lo, min(hi, len(o)))], "search"
            elif ctx in (C_DISCARD, C_DISCARD_ENERGY):
                o = self._order_by(obs, me, op, opts, DISCARD_PREFERENCE)
                choice, rule = o[:max(lo, min(hi, len(o)))], "discard_protect_engine"
            elif ctx == C_ATTACH_TO:
                # energy goes onto the board wherever it counts for Mechanism B; Bellibolt ex
                # first because it is also the 280 HP body that must survive
                pri = [IONOS_BELLIBOLT_EX, IONOS_VOLTORB, IONOS_TADBULB, IONOS_KILOWATTREL,
                       IONOS_WATTREL]
                o = self._order_by(obs, me, op, opts, pri)
                choice, rule = o[:max(lo, min(hi, len(o)))], "attach_to_engine"
            elif ctx == C_ATTACH_FROM:
                o = self._order_by(obs, me, op, opts, [BASIC_L_ENERGY])
                choice, rule = o[:max(lo, min(hi, len(o)))], "attach_from_basic_l"
            elif ctx == C_MAIN:
                i = self._main(obs, sel, me, op, res)
                if i is not None:
                    t = _g(opts[i], "type")
                    rule = {O_ABILITY: "main_ability_electric_streamer",
                            O_EVOLVE: "main_evolve", O_PLAY: "main_play",
                            O_ATTACH: "main_attach", O_ATTACK: "main_attack",
                            O_RETREAT: "main_retreat", O_END: "main_end"}.get(t, "main")
                    choice = [i]
            elif ctx == C_ATTACK:
                i = self._attack(obs, sel, me, res)
                choice, rule = ([i], "attack_voltaic_chain_scaled") if i is not None else (None, rule)
            elif ctx in (C_IS_FIRST, C_ACTIVATE):
                yes = next((i for i, o in enumerate(opts) if _g(o, "type") == O_YES), None)
                choice, rule = ([yes], "say_yes") if yes is not None else (None, rule)
            elif ctx == C_MULLIGAN:
                yes = next((i for i, o in enumerate(opts) if _g(o, "type") == O_YES), None)
                choice, rule = ([yes], "mulligan_yes") if yes is not None else (None, rule)
            elif ctx == C_DRAW_COUNT:
                best = max(range(len(opts)), key=lambda i: (_g(opts[i], "number") or 0, -i))
                choice, rule = [best], "draw_max"
        except Exception as e:  # noqa: BLE001
            return self._trace(ctx, self._fallback(sel, f"exception:{type(e).__name__}"),
                               f"exception:{type(e).__name__}", res, sel)

        if choice is None:
            return self._trace(ctx, self._fallback(sel, f"no_rule_for_context_{ctx}"),
                               f"no_rule_for_context_{ctx}", res, sel)
        choice = [i for i in dict.fromkeys(choice) if isinstance(i, int) and 0 <= i < len(opts)]
        if len(choice) < lo:
            for i in range(len(opts)):
                if len(choice) >= lo:
                    break
                if i not in choice:
                    choice.append(i)
        if hi:
            choice = choice[:hi]
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
                "is_fallback": rule.startswith(("no_rule", "exception", "count_repair")),
                "mechanism_a_available": bool(res.get("l_energy_in_hand", 0) > 0
                                              and res.get("bellibolt_in_play")),
                "mechanism_a_used": rule == "main_ability_electric_streamer",
                "mechanism_b_damage": res.get("voltaic_chain_damage"),
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

_EXPERT = IonoExpert(MY_DECK)


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

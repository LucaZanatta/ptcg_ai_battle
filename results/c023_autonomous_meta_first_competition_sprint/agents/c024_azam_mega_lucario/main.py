"""c023 candidate entry point.

This file is c023's own code. It ships alongside `base_agent.py` — an official Kaggle sample
agent, byte-for-byte, credited in `ATTRIBUTION.txt` — and behaves exactly like it unless a named
override rule in `params.json` is enabled and fires.

The architecture is deliberate:

* **The base is consulted on every decision, always.** These sample agents keep module-level plan
  state (attack plans, turn counters, ability flags) that is updated as a side effect of being
  called. Skipping the call on turns we intend to override would desynchronise that state and the
  override would then be reasoning against a stale plan. c007 established this the hard way.
* **An override replaces only the returned indices**, in one named decision class, and only when
  its precondition holds. Anything else falls through to the base.
* **Every returned action is legality-checked** against `minCount`/`maxCount`/option count before
  it leaves this function, and an illegal or raising override falls back to the base action. A
  bad override must cost score, never a forfeited game.

With `params.json` carrying no enabled rules, this file is action-identical to the base agent;
`tools/c023_identity.py` verifies that rather than asserting it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if not os.path.isfile(os.path.join(_HERE, "base_agent.py")):
    _HERE = "/kaggle_simulations/agent"
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ---- params -------------------------------------------------------------------------------
_PARAMS = {"rules": {}}
try:
    with open(os.path.join(_HERE, "params.json")) as _fh:
        _PARAMS = json.load(_fh)
except Exception:
    pass
# Sorted, not a set: iteration order over a set depends on PYTHONHASHSEED, and two rules that
# can fire on the same decision would then resolve differently between runs. A candidate must be
# one policy, not a distribution over policies.
RULES_ON = sorted(k for k, v in (_PARAMS.get("rules") or {}).items() if v)
TH = _PARAMS.get("thresholds") or {}

# ---- deck ---------------------------------------------------------------------------------
_deck_path = os.path.join(_HERE, "deck.csv")
if not os.path.exists(_deck_path):
    _deck_path = "/kaggle_simulations/agent/deck.csv"
with open(_deck_path) as _fh:
    MY_DECK = [int(x) for x in _fh if x.strip()][:60]

# ---- base agent ---------------------------------------------------------------------------
# Imported with the working directory set to this package, because the sample agents read a
# relative `deck.csv` at import time.
_old_cwd = os.getcwd()
try:
    os.chdir(_HERE)
except Exception:
    pass
try:
    _spec = importlib.util.spec_from_file_location("c023_base_agent",
                                                   os.path.join(_HERE, "base_agent.py"))
    _base = importlib.util.module_from_spec(_spec)
    sys.modules["c023_base_agent"] = _base
    _spec.loader.exec_module(_base)
finally:
    try:
        os.chdir(_old_cwd)
    except Exception:
        pass

from cg.api import (AreaType, CardType, EnergyType, OptionType, Pokemon,  # noqa: E402
                    SelectContext, all_card_data, to_observation_class)

_CARD = {c.cardId: c for c in all_card_data()}

# A SECOND, independent instance of the base agent, used only as the planner's continuation
# policy. It must not be the same object as `_base`: the sample agents keep module-level plan
# state that is mutated by every call, and driving one instance with both real and simulated
# observations would corrupt the real game's plan. Loaded lazily so a candidate with no planner
# pays nothing.
_sim = None
_planner = None


class _FinishStats:
    """Counters for finish mode, readable from outside the process boundary.

    An override that fires zero times measures the control and looks like a null result, which is
    D6a exactly. These counters make an inert rule visible without needing an outcome study.
    """

    __slots__ = ("considered", "searched", "fired", "base_already_won", "vetoed", "errors")

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, 0)

    def as_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


FINISH_STATS = _FinishStats()

# The harness forks one child per game, so in-process counters die with the child and a rule can
# look inert when it is merely gated. When C024_FINISH_STATS names a DIRECTORY, each child
# rewrites its own `<pid>.json` snapshot and the caller sums the directory -- which is what
# separates "never fired" from "fired rarely because the expert was already winning".
#
# Written on update rather than at exit on purpose: the harness's children leave via os._exit,
# which does not run atexit handlers, so an exit-time dump produces no files at all.
_FSTAT_DIR = os.environ.get("C024_FINISH_STATS")


def _dump_finish_stats():
    if not _FSTAT_DIR:
        return
    try:
        with open(os.path.join(_FSTAT_DIR, f"{os.getpid()}.json"), "w") as fh:
            json.dump(FINISH_STATS.as_dict(), fh)
    except Exception:
        pass


def _load_planner():
    global _sim, _planner
    if _planner is not None:
        return _planner
    spec = importlib.util.spec_from_file_location("c023_sim_agent",
                                                  os.path.join(_HERE, "base_agent.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["c023_sim_agent"] = m
    cwd = os.getcwd()
    try:
        os.chdir(_HERE)
        spec.loader.exec_module(m)
    finally:
        try:
            os.chdir(cwd)
        except Exception:
            pass
    _sim = m
    pspec = importlib.util.spec_from_file_location("c023_planner_mod",
                                                   os.path.join(_HERE, "planner.py"))
    pm = importlib.util.module_from_spec(pspec)
    sys.modules["c023_planner_mod"] = pm
    pspec.loader.exec_module(pm)
    _planner = pm
    return _planner


class View:
    """Everything an override rule is allowed to look at, resolved once per decision."""

    __slots__ = ("obs", "obs_dict", "state", "select", "context", "options", "my_index", "me",
                 "op", "card", "params")

    def __init__(self, obs, obs_dict=None):
        self.obs = obs
        self.obs_dict = obs_dict
        self.state = obs.current
        self.select = obs.select
        self.context = obs.select.context
        self.options = obs.select.option
        self.my_index = obs.current.yourIndex
        self.me = obs.current.players[self.my_index]
        self.op = obs.current.players[1 - self.my_index]
        self.card = _CARD

    def opt_card(self, o):
        ps = self.state.players[getattr(o, "playerIndex", None) or self.my_index]
        a = getattr(o, "area", None)
        i = getattr(o, "index", -1)
        # PLAY / EVOLVE / ATTACH options carry no `area`; the card always comes from hand, which
        # is what the sample agents assume. Reading `area` alone returned None for every PLAY
        # option and made the bench rule INERT -- 0 fires in 1,329 decisions -- which the
        # rule-firing probe caught and no outcome-based check could have.
        if a is None and o.type in (OptionType.PLAY, OptionType.EVOLVE, OptionType.ATTACH):
            try:
                return self.me.hand[i]
            except Exception:
                return None
        try:
            if a == AreaType.HAND:
                return ps.hand[i]
            if a == AreaType.DISCARD:
                return ps.discard[i]
            if a == AreaType.ACTIVE:
                return ps.active[i]
            if a == AreaType.BENCH:
                return ps.bench[i]
            if a == AreaType.PRIZE:
                return ps.prize[i]
            if a == AreaType.DECK:
                return self.select.deck[i]
            if a == AreaType.STADIUM:
                return self.state.stadium[i]
            if a == AreaType.LOOKING:
                return self.state.looking[i]
        except Exception:
            return None
        return None


# ---- override rules -------------------------------------------------------------------------
# Each rule is `fn(view, base_action) -> list[int] | None`. Returning None means "no opinion".
# A rule must name the failure class it corrects; see FAILURE_TAXONOMY.md.
RULES = {}


def rule(name):
    def deco(fn):
        RULES[name] = fn
        return fn
    return deco


# ---- F1: turn order -------------------------------------------------------------------------
# The official Dragapult sample scores YES = -1 in SelectContext.IS_FIRST, so it always elects to
# go SECOND. That is a single bit with a whole-game consequence and no measurement behind it in
# the sample; a public Mega Lucario agent whose kernel is titled with a 1084.5 leaderboard score
# makes the opposite choice. It is the cheapest testable decision in the whole agent.

@rule("go_first")
def _go_first(v, base_action):
    if v.context != SelectContext.IS_FIRST:
        return None
    for i, o in enumerate(v.options):
        if o.type == OptionType.YES:
            return [i]
    return None


# ---- F2: opening bench width ---------------------------------------------------------------
# The sample benches NOTHING at setup when it is the first player (`if my_index ==
# state.firstPlayer or card.id != Dreepy: score = -1`) and only Dreepy when it is second. A deck
# whose whole plan is Dreepy -> Drakloak -> Dragapult ex needs Dreepy on the board early, and an
# empty bench also means a knocked-out active ends the game outright.

def _basic_pref(cid):
    # Dreepy first: it is the evolution line. Budew next: its item lock is the tempo defence.
    # The three ex support Pokemon are LAST -- each is two prizes sitting on the bench.
    order = {119: 0, 235: 1, 184: 2, 140: 3, 1071: 4}
    return order.get(cid, 5)


def _bench_fill(v, prefer_only=None):
    cands = []
    for i, o in enumerate(v.options):
        c = v.opt_card(o)
        if c is None:
            continue
        if prefer_only is not None and c.id not in prefer_only:
            continue
        cands.append((_basic_pref(c.id), i))
    if not cands:
        return None
    cands.sort()
    k = min(int(v.select.maxCount), len(cands))
    if k < int(v.select.minCount):
        return None
    return [i for _, i in cands[:k]]


@rule("bench_dreepy_always")
def _bench_dreepy_always(v, base_action):
    """Bench Dreepy at setup even when moving first -- the sample declines to."""
    if v.context != SelectContext.SETUP_BENCH_POKEMON:
        return None
    return _bench_fill(v, prefer_only={119})


@rule("bench_wide_setup")
def _bench_wide_setup(v, base_action):
    """Fill the opening bench, Dreepy and Budew first, ex support Pokemon last."""
    if v.context != SelectContext.SETUP_BENCH_POKEMON:
        return None
    return _bench_fill(v)


# ---- F3: greedy option scoring ---------------------------------------------------------------
# The sample scores every option in isolation against a hand-written constant, so it cannot see
# that one action makes another reachable or that this turn's attack costs next turn's attacker.
# `planner.py` plays the turn out through the engine's forward-search API and scores the board
# each line leaves behind, with the base agent itself as the continuation policy.

@rule("turn_planner")
def _turn_planner(v, base_action):
    pm = _load_planner()
    if pm is None:
        return None
    return pm.plan(v.obs, base_action, MY_DECK, _sim, TH.get("planner"))


# ---- c024 finish mode: the minimum-override-rate end of the F3 curve --------------------------
# F3's four planner arms lost monotonically in how often they overrode. This is the one point on
# that curve that was never sampled: it overrides only where the simulated line ENDS THE GAME in
# our favour, in every sampled world. See `c024_finish.py` for why unanimity and prize knowledge
# are both load-bearing.

_finish = None
_prizes = None
_TRACKER = [None, None]      # [tracker, last_turn_seen] -- reset if a new game reuses this module


def _load_finish():
    global _finish, _prizes
    if _finish is not None:
        return _finish
    _load_planner()          # `finish` imports the planner's helpers by the flat name
    for name, path, target in (("c024_prizes_mod", "prizes.py", "_prizes"),
                               ("c024_finish_mod", "finish.py", "_finish")):
        p = os.path.join(_HERE, path)
        if not os.path.isfile(p):
            return None
        spec = importlib.util.spec_from_file_location(name, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        globals()[target] = m
    return _finish


def _tracker(v):
    """One tracker per game. A turn number that went backwards means a new game in this process."""
    if _prizes is None:
        return None
    t, last = _TRACKER
    if t is None or (last is not None and v.state.turn < last):
        t = _prizes.PrizeTracker(MY_DECK)
    _TRACKER[0], _TRACKER[1] = t, v.state.turn
    try:
        t.update(v.obs, v.my_index)
    except Exception:
        pass
    return t


@rule("finish_mode")
def _finish_mode(v, base_action):
    fm = _load_finish()
    if fm is None:
        return None
    t = _tracker(v)
    out = fm.finish(v.obs, base_action, MY_DECK, _sim, t.known() if t else None,
                    TH.get("finish"), FINISH_STATS)
    if _FSTAT_DIR:
        _dump_finish_stats()
    return out


# ---- the veto primitive ----------------------------------------------------------------------
# A rule that says "not that one" needs a replacement, and the only principled replacement is the
# expert's own next preference. This asks it for exactly that: the observation is copied with the
# vetoed options removed, the SIMULATION instance of the base agent is asked to choose from what
# remains, and the answer is mapped back to the real option indices. The real instance is never
# called twice for one decision, so its plan state advances exactly once.

def _obs_without(obs_dict, banned):
    import copy
    d = copy.deepcopy(obs_dict)
    sel = d.get("select")
    if not sel:
        return None, None
    opts = sel.get("option") or []
    keep = [i for i in range(len(opts)) if i not in banned]
    if len(keep) < max(1, int(sel.get("minCount") or 0)):
        return None, None
    sel["option"] = [opts[i] for i in keep]
    if sel.get("maxCount") is not None:
        sel["maxCount"] = min(int(sel["maxCount"]), len(keep))
    if sel.get("minCount") is not None:
        sel["minCount"] = min(int(sel["minCount"]), len(keep))
    return d, keep


def _expert_choice_excluding(obs_dict, banned):
    _load_planner()          # loads the simulation instance as a side effect
    if _sim is None:
        return None
    d, keep = _obs_without(obs_dict, banned)
    if d is None:
        return None
    try:
        alt = _sim.agent(d)
    except Exception:
        return None
    if not alt:
        return None
    try:
        return [keep[i] for i in alt if 0 <= i < len(keep)]
    except Exception:
        return None


# ---- F3-restricted: search only inside the expert's own shortlist ----------------------------
# plan_screen1 measured the full-option planner losing monotonically in how often it overrode:
# planning at every decision (most overrides) was the worst arm, the most conservative was the
# best, and all four sat at or below the control. The mechanism is that a hand-written board
# score is competing with constants that encode deck knowledge it does not have.
#
# This narrows the argument. The expert is asked for its top-k preferences -- by re-asking it
# with each previous choice vetoed -- and the search only chooses among those. Every candidate is
# then already expert-approved, and the search is breaking a tie rather than overruling knowledge.

@rule("shortlist_planner")
def _shortlist_planner(v, base_action):
    pm = _load_planner()
    if pm is None or not base_action:
        return None
    k = int(TH.get("shortlist_k", 3))
    order = [int(base_action[0])]
    banned = {int(base_action[0])}
    while len(order) < k:
        alt = _expert_choice_excluding(v.obs_dict, banned)
        if not alt or alt[0] in banned:
            break
        order.append(int(alt[0]))
        banned.add(int(alt[0]))
    if len(order) < 2:
        return None
    return pm.plan(v.obs, base_action, MY_DECK, _sim, TH.get("planner"), restrict=order)


# ---- F4: bench exposure against a damage-spread deck -----------------------------------------
# Marnie's Grimmsnarl ex is 58.8% of the 1100+ ladder band and the champion scores 0.250 against
# it. The mechanism is legible in the cards: Shadow Bullet hits a BENCHED Pokemon for 30 on top
# of 180 to the active, Froslass puts a counter on every Pokemon with an Ability each checkup, and
# Munkidori moves three counters a turn onto our side. Every small basic we bench is a prize on a
# timer. The sample scores playing a Dreepy at 51000 -- the second-highest score in its table --
# and does it regardless of what is across the board.
#
# Independent evidence that this is the right axis: `bench_wide_setup` lost 6.6 points *in this
# matchup specifically* (0.242 vs 0.308) while costing 5.0 overall.

_SPREAD_IDS = {646, 647, 648,      # Marnie's Impidimp / Morgrem / Grimmsnarl ex
               104, 860,           # Froslass / Snorunt
               112}                # Munkidori

_SMALL_HP = 100                    # a benched Pokemon at or under this dies to chip damage


def _opponent_is_spread(v):
    for p in list(v.op.active) + list(v.op.bench):
        if p is not None and p.id in _SPREAD_IDS:
            return True
    for c in v.op.discard:
        if c.id in _SPREAD_IDS:
            return True
    return False


@rule("bench_discipline_vs_spread")
def _bench_discipline(v, base_action):
    if v.context != SelectContext.MAIN or not base_action:
        return None
    i = int(base_action[0])
    if i >= len(v.options):
        return None
    o = v.options[i]
    if o.type != OptionType.PLAY:
        return None
    card = v.opt_card(o)
    if card is None:
        return None
    d = _CARD.get(card.id)
    if d is None or d.cardType != CardType.POKEMON:
        return None
    # Cards the deck's own plan depends on are never vetoed. Loss mining says winning games
    # have a LARGER mean bench (3.31 vs 2.63), so a veto that blocks the evolution line is
    # attacking development, not exposure.
    if card.id in set(TH.get("bench_protect_ids", []) or []):
        return None
    if d.hp > int(TH.get("bench_small_hp", _SMALL_HP)):
        return None
    if not _opponent_is_spread(v):
        return None
    bench = sum(1 for p in v.me.bench if p is not None)
    if bench < int(TH.get("bench_cap", 2)):
        return None
    return _expert_choice_excluding(v.obs_dict, {i})


def _legal(view, action) -> bool:
    sel = view.select
    n = len(sel.option)
    return (isinstance(action, list)
            and int(sel.minCount) <= len(action) <= int(sel.maxCount)
            and len(action) == len(set(action))
            and all(isinstance(i, int) and 0 <= i < n for i in action))


def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        # Deck handshake. The base agent read the same deck.csv, so this is its deck too.
        _base.agent(obs_dict)
        return MY_DECK

    # Parse our own view BEFORE the base runs, so nothing the base does can change what a rule
    # sees, then call the base so its plan state advances exactly as it would on its own.
    view = View(obs, obs_dict)
    base_action = _base.agent(obs_dict)

    if not RULES_ON:
        return base_action

    for name in RULES_ON:
        fn = RULES.get(name)
        if fn is None:
            continue
        try:
            proposed = fn(view, base_action)
        except Exception:
            proposed = None
        if proposed is not None and _legal(view, list(proposed)):
            return list(proposed)
    return base_action

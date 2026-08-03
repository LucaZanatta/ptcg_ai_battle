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
RULES_ON = {k for k, v in (_PARAMS.get("rules") or {}).items() if v}
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


class View:
    """Everything an override rule is allowed to look at, resolved once per decision."""

    __slots__ = ("obs", "state", "select", "context", "options", "my_index", "me", "op",
                 "card", "params")

    def __init__(self, obs):
        self.obs = obs
        self.state = obs.current
        self.select = obs.select
        self.context = obs.select.context
        self.options = obs.select.option
        self.my_index = obs.current.yourIndex
        self.me = obs.current.players[self.my_index]
        self.op = obs.current.players[1 - self.my_index]
        self.card = _CARD

    def opt_card(self, o):
        ps = self.state.players[getattr(o, "playerIndex", self.my_index)]
        a = getattr(o, "area", None)
        i = getattr(o, "index", -1)
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
    view = View(obs)
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

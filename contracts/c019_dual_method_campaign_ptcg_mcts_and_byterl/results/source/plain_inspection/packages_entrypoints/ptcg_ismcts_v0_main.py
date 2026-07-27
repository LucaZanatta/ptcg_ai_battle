"""PTCG_ISMCTS_V0 — official Mega Lucario agent under information-set MCTS.

The baseline agent is the official sample source, byte-identical (see ATTRIBUTION.md). It supplies
priors and drives rollouts through explicit BRANCH-LOCAL memory, so exploring one child cannot
corrupt the memory another subtree was built from. On any failure the agent plays the baseline
action.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import _c019_ismcts as IS

_DECK = None
_AGENT = None
STATS = None


def _deck():
    global _DECK
    if _DECK is None:
        import csv
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv")
        with open(p) as fh:
            _DECK = [int(r[0]) for r in csv.reader(fh) if r and r[0].strip().isdigit()]
    return _DECK


def _agent():
    global _AGENT, STATS
    if _AGENT is None:
        _AGENT = IS.ISMCTSAgent(_deck(), {"simulations_per_determinization": 12, "determinizations": 1, "max_ms_per_decision": 120, "max_match_ms": 20000}, seed=19000)
        STATS = _AGENT.stats
    return _AGENT


def agent(obs_dict):
    a = _agent()
    sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
    if sel is None:
        return list(_deck())
    try:
        return a.act(obs_dict)
    except Exception:
        try:
            act, a.memory = a.baseline.act(obs_dict, a.memory)
            return act
        except Exception:
            return [0]

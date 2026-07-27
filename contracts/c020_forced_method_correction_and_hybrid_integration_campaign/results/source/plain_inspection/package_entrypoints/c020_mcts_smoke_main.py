"""c020 corrected information-set MCTS -- competition entry point."""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)

from cg import c020_agent as AG

_CFG = json.load(open(os.path.join(_HERE, "config.json")))
_DECK = json.load(open(os.path.join(_HERE, "deck.json")))
_A = {"a": None}
STATS = {"decisions": 0, "searched": 0, "overrides": 0, "fallbacks": 0}


def _agent():
    if _A["a"] is None:
        _A["a"] = AG.CorrectedMCTSAgent(_DECK, _CFG["mcts"], seed=_CFG.get("seed", 0))
    return _A["a"]


def agent(observation):
    STATS["decisions"] += 1
    a = _agent()
    out = a.act(observation)
    STATS["searched"] = a.stats.get("searched_decisions", 0)
    STATS["overrides"] = a.stats.get("overrides", 0)
    STATS["timeouts"] = a.stats.get("timeouts", 0)
    # surface the first search exception: a package that plays without searching is the c018
    # failure mode, and it is invisible unless the swallowed error is reported
    STATS["exceptions"] = [e.get("msg") for e in getattr(a, "exceptions", [])[:2]]
    STATS["counters"] = {k: v for k, v in a.stats.items() if v}
    return out

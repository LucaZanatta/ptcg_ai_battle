"""c020 corrected ByteRL -- competition entry point."""
import json, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)

import torch
from cg import c020_byterl_model as M, c020_byterl_actor as AC

_DECK = json.load(open(os.path.join(_HERE, "deck.json")))
_A = {"actor": None}
STATS = {"decisions": 0, "policy_ok": 0, "fallbacks": 0, "resets": 0}


def _actor():
    if _A["actor"] is None:
        m = M.PTCGByteRL()
        m.load_state_dict(torch.load(os.path.join(_HERE, "model.pt"),
                                     map_location="cpu")["state_dict"])
        m.eval()
        _A["actor"] = AC.ByteRLActor(m, _DECK, version=-1, greedy=True, seed=0)
    return _A["actor"]


def agent(observation):
    # A recurrent policy must reset at TRUE episode boundaries only (B7). The no-select
    # observation IS the deck-submission step that starts a game, so it is the boundary: without
    # this the cached actor carries hidden state from the previous game into the next one, which
    # CONTRACT §8 lists as a packaged-ByteRL blocker.
    sel = observation.get("select") if isinstance(observation, dict) else None
    a = _actor()
    if sel is None:
        a.reset()
        STATS["resets"] += 1
    STATS["decisions"] += 1
    out = a.act(observation)
    STATS["policy_ok"] += 1
    return out

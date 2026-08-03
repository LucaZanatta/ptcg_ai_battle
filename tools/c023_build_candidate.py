"""c023 — build a candidate package from an official sample agent plus this contract's own code.

A candidate is a directory the evaluation harness and the Kaggle packager both understand:

    <candidate>/
        main.py          this contract's wrapper (my code)
        base_agent.py    the official sample agent, byte-for-byte, with attribution
        deck.csv         the 60-card list this candidate plays
        params.json      which named override rules are enabled, and their thresholds
        ATTRIBUTION.txt  what came from where

Why a wrapper rather than an edited copy of the official agent:

* **Attribution stays exact.** `base_agent.py` keeps its original sha256, so "what did we change"
  is answered by one small file rather than by a diff of somebody else's 850 lines.
* **The expert remains the fallback.** Every decision is passed to the base agent first — which
  also keeps its internal plan state synchronised, the property c007 established is load-bearing
  for this architecture — and an override only replaces the *result* in a named decision class.
* **A candidate differs from the champion in data, not code.** `deck.csv` and `params.json` are
  the only things a mutation touches, so a hundred candidates are a hundred small files and the
  behaviour of the shared code is fixed across all of them.

With every rule disabled and the base deck, the wrapper must be action-identical to the official
agent. `tools/c023_identity.py` checks exactly that.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from typing import Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

OUT_ROOT = os.path.join(_REPO, "results", "c023_autonomous_meta_first_competition_sprint")
AGENTS = os.path.join(OUT_ROOT, "agents")
WRAPPER = os.path.join(_REPO, "starter_kit", "c023_wrapper_main.py")
PLANNER = os.path.join(_REPO, "starter_kit", "c023_planner.py")

ATTRIBUTION = {
    "official_dragapult": "Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-dragapult-ex-deck (Kiyota)",
    "official_mega_lucario": "Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck (Kiyota)",
    "official_mega_abomasnow": "Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck (Kiyota)",
    "official_iono": "Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-iono-s-deck (Kiyota)",
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def base_deck(base: str) -> List[int]:
    from cg import c023_players as P
    d = P.resolve(base)
    with open(os.path.join(d, "deck.csv")) as fh:
        return [int(x) for x in fh if x.strip()]


def build(candidate_id: str, base: str, deck: Optional[List[int]] = None,
          params: Optional[Dict] = None, parent: Optional[str] = None,
          rationale: str = "", param_source: Optional[str] = None) -> Dict:
    from cg import c023_players as P
    if base not in ATTRIBUTION:
        raise ValueError(f"{base!r} is not a submission-eligible official base; SOURCES.md "
                         f"classifies community kernels LOCAL_BENCHMARK_ONLY")
    bdir = P.resolve(base)
    deck = list(deck) if deck else base_deck(base)
    if len(deck) != 60:
        raise ValueError(f"deck must be 60 cards, got {len(deck)}")
    params = dict(params or {})
    params.setdefault("base", base)
    params.setdefault("rules", {})

    d = os.path.join(AGENTS, candidate_id)
    os.makedirs(d, exist_ok=True)
    # `param_source` ships the AST-parameterised derivative instead of the sample verbatim. Its
    # defaults reproduce the sample exactly, and tools/c023_identity.py verifies that.
    shutil.copyfile(param_source or os.path.join(bdir, "main.py"),
                    os.path.join(d, "base_agent.py"))
    shutil.copyfile(WRAPPER, os.path.join(d, "main.py"))
    shutil.copyfile(PLANNER, os.path.join(d, "planner.py"))
    with open(os.path.join(d, "deck.csv"), "w") as fh:
        fh.write("\n".join(str(c) for c in deck) + "\n")
    with open(os.path.join(d, "params.json"), "w") as fh:
        json.dump(params, fh, indent=2, sort_keys=True)
    with open(os.path.join(d, "ATTRIBUTION.txt"), "w") as fh:
        fh.write(f"base_agent.py: {ATTRIBUTION[base]}\n"
                 f"reuse class: SUBMISSION_REUSE_ALLOWED (see results/.../SOURCES.md)\n"
                 f"main.py, params.json: c023 contract code (this repository)\n"
                 + ("base_agent.py is a DERIVATIVE of that sample: tools/c023_paramize.py "
                    "replaced its heuristic score constants with parameter lookups whose "
                    "defaults are the original values\n" if param_source else "")
                 + "deck.csv: see DECK_CHANGE_LEDGER.md\n")

    man = {
        "candidate_id": candidate_id,
        "parent": parent or base,
        "base": base,
        "rationale": rationale,
        "deck": deck,
        "deck_sha256": sha256_file(os.path.join(d, "deck.csv")),
        "base_agent_sha256": sha256_file(os.path.join(d, "base_agent.py")),
        "wrapper_sha256": sha256_file(os.path.join(d, "main.py")),
        "planner_sha256": sha256_file(os.path.join(d, "planner.py")),
        "params_sha256": sha256_file(os.path.join(d, "params.json")),
        "params": params,
        "paramized": bool(param_source),
        "param_source": os.path.relpath(param_source, _REPO) if param_source else None,
        "dir": os.path.relpath(d, _REPO),
    }
    os.makedirs(os.path.join(OUT_ROOT, "candidate_manifests"), exist_ok=True)
    with open(os.path.join(OUT_ROOT, "candidate_manifests", candidate_id + ".json"), "w") as fh:
        json.dump(man, fh, indent=2)
    return man


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--deck", help="path to a deck.csv; default = the base's own deck")
    ap.add_argument("--params", help="path to a params.json")
    ap.add_argument("--parent")
    ap.add_argument("--rationale", default="")
    ap.add_argument("--param-source", help="path to an AST-parameterised base agent")
    a = ap.parse_args()
    deck = None
    if a.deck:
        with open(a.deck) as fh:
            deck = [int(x) for x in fh if x.strip()]
    params = json.load(open(a.params)) if a.params else None
    man = build(a.id, a.base, deck, params, a.parent, a.rationale, a.param_source)
    print(json.dumps({k: man[k] for k in ("candidate_id", "base", "deck_sha256",
                                          "base_agent_sha256", "params_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

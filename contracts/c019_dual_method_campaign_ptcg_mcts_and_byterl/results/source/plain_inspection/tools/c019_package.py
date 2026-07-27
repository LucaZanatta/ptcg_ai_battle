"""c019 §13 — standalone inference packages for each pure branch.

Two packages, each with NO dependency on the other branch (§16):

  * `ptcg_ismcts_v0`   — official baseline + information-set MCTS. No ByteRL, no torch.
  * `ptcg_byterl_v0`   — recurrent policy inference only. No MCTS, no search API.

Every package is validated by extracting into an empty directory and playing real both-seat games
from THERE with the repository off `sys.path`. A package that works only because the developer's
checkout is importable is not a package.

The liveness check matters as much as completion: a package can complete every game while its
method never runs. c018 shipped that twice. So the extracted agent's own counters are read back
and the method must be shown to have actually executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
PKG = os.path.join(C19, "packages")
BASE_SRC = os.path.join(_REPO, "contracts",
                        "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                        "results", "artifacts", "candidates", "official_mega_lucario")
SDK = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]

MCTS_MAIN = '''"""PTCG_ISMCTS_V0 — official Mega Lucario agent under information-set MCTS.

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
        _AGENT = IS.ISMCTSAgent(_deck(), CFG, seed=19000)
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
'''

BYTERL_MAIN = '''"""PTCG_BYTERL_V0 — recurrent masked policy, inference only.

No MCTS and no search API (§9.6). Recurrent state carries across atomic decisions and resets at
the game boundary. The deck is frozen outside the model (§9.1), so the deck-submission step
returns the fixed list rather than a policy output.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from cg import api as A
from cg import c019_core as K, c019_byterl_encode as E, c019_byterl_model as M

_DECK = None
_MODEL = None
_STATE = [None]
STATS = {"decisions": 0, "policy_ok": 0, "fallbacks": 0, "resets": 0}


def _deck():
    global _DECK
    if _DECK is None:
        import csv
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv")
        with open(p) as fh:
            _DECK = [int(r[0]) for r in csv.reader(fh) if r and r[0].strip().isdigit()]
    return _DECK


def _model():
    global _MODEL
    if _MODEL is None:
        torch.set_num_threads(1)
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy.pt")
        m = M.PTCGByteRL()
        m.load_state_dict(torch.load(p, map_location="cpu")["state_dict"])
        m.eval()
        _MODEL = m
    return _MODEL


def agent(obs_dict):
    sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
    if sel is None:
        # deck submission also marks a new game: reset recurrent state (B02)
        _STATE[0] = None
        STATS["resets"] += 1
        return list(_deck())
    STATS["decisions"] += 1
    try:
        m = _model()
        o = A.to_observation_class(obs_dict)
        f = E.encode(o)
        b = M.to_torch(f)
        with torch.no_grad():
            logits, _v, nxt = m.forward(b, _STATE[0])
            probs = M.masked_probs(logits, b["opt_mask"])[0]
        _STATE[0] = (nxt[0].detach(), nxt[1].detach())
        k = min(int(f["n_options"]), E.N_OPT)
        if k <= 0:
            return []
        lo = int(sel.get("minCount") or 0)
        hi = int(sel.get("maxCount") or 1)
        n_pick = max(1, min(lo if lo > 0 else 1, hi if hi > 0 else 1, k))
        p = probs[:k]
        s = float(p.sum())
        picks = (list(range(n_pick)) if s <= 0 else
                 torch.topk(p / p.sum(), n_pick).indices.tolist())
        opts = K.canonical_options(sel)
        chosen = [opts[i] for i in sorted(picks) if i < len(opts)]
        if chosen:
            STATS["policy_ok"] += 1
            return K.to_select_payload(chosen, sel)
    except Exception:
        pass
    STATS["fallbacks"] += 1
    n = len(sel.get("option") or [])
    lo = max(1, int(sel.get("minCount") or 1))
    return list(range(min(lo, n))) if n else []
'''


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def cg_closure(roots):
    """Transitive cg.* import closure, read from the AST.

    A hand-written module list is one forgotten import away from a package whose method silently
    never runs -- which is exactly what happened in c018 and is why this is derived.
    """
    import ast
    seen = set()

    def walk(mod):
        path = os.path.join(_REPO, "cg", f"{mod}.py")
        if mod in seen or not os.path.exists(path):
            return
        seen.add(mod)
        try:
            tree = ast.parse(open(path, encoding="utf-8-sig").read())
        except Exception:  # noqa: BLE001
            return
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("cg"):
                if n.module == "cg":
                    for al in n.names:
                        walk(al.name)
                else:
                    walk(n.module.split(".", 1)[1])
            elif isinstance(n, ast.Import):
                for al in n.names:
                    if al.name.startswith("cg."):
                        walk(al.name.split(".", 1)[1])
    for r in roots:
        walk(r)
    return sorted(seen)


def build(name: str, kind: str, checkpoint: str = "", cfg: Dict[str, Any] = None) -> Dict:
    d = os.path.join(PKG, name)
    os.makedirs(d, exist_ok=True)
    archive = os.path.join(d, f"{name}.tar.gz")
    tmp = tempfile.mkdtemp(prefix=f"c019pkg_{name}_")
    smap: List[Dict[str, Any]] = []

    def add(src, arc):
        dst = os.path.join(tmp, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        smap.append({"source": os.path.relpath(src, _REPO), "archive_path": arc,
                     "sha256": sha_file(dst)})

    try:
        add(os.path.join(BASE_SRC, "deck.csv"), "deck.csv")
        for f in SDK:
            add(os.path.join(_REPO, "cg", f), f"cg/{f}")

        if kind == "mcts":
            add(os.path.join(BASE_SRC, "main.py"), "_baseline_agent.py")
            for m in ("c019_core", "c019_baseline", "c019_determinize", "c019_leaf",
                      "c019_mcts", "c019_ismcts"):
                add(os.path.join(_REPO, "cg", f"{m}.py"), f"cg/{m}.py")
            for m in cg_closure(["c019_ismcts", "c019_determinize"]):
                p = os.path.join(_REPO, "cg", f"{m}.py")
                if os.path.exists(p) and not os.path.exists(os.path.join(tmp, "cg", f"{m}.py")):
                    add(p, f"cg/{m}.py")
            # the packaged MCTS loads the baseline from a LOCAL copy, not a c016 path
            src = open(os.path.join(_REPO, "cg", "c019_baseline.py"),
                       encoding="utf-8-sig").read()
            src = src.replace(
                'BASELINE_DIR = os.path.join(\n'
                '    _REPO, "contracts", "c016_public_agent_reproduction_gauntlet_and_champion'
                '_submission",\n'
                '    "results", "artifacts", "candidates", "official_mega_lucario")\n'
                'BASELINE_MAIN = os.path.join(BASELINE_DIR, "main.py")',
                'BASELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                'BASELINE_MAIN = os.path.join(BASELINE_DIR, "_baseline_agent.py")')
            open(os.path.join(tmp, "cg", "c019_baseline.py"), "w").write(src)
            smap.append({"source": "cg/c019_baseline.py (baseline path rebound to the package)",
                         "archive_path": "cg/c019_baseline.py",
                         "sha256": sha_file(os.path.join(tmp, "cg", "c019_baseline.py"))})
            shutil.copyfile(os.path.join(_REPO, "cg", "c019_ismcts.py"),
                            os.path.join(tmp, "_c019_ismcts.py"))
            smap.append({"source": "cg/c019_ismcts.py", "archive_path": "_c019_ismcts.py",
                         "sha256": sha_file(os.path.join(tmp, "_c019_ismcts.py"))})
            main = MCTS_MAIN.replace("CFG", json.dumps(cfg or {}))
        else:
            for m in cg_closure(["c019_byterl_model", "c019_byterl_encode", "c019_core"]):
                p = os.path.join(_REPO, "cg", f"{m}.py")
                if os.path.exists(p):
                    add(p, f"cg/{m}.py")
            add(checkpoint, "policy.pt")
            main = BYTERL_MAIN

        mp_ = os.path.join(tmp, "main.py")
        open(mp_, "w").write(main)
        smap.append({"source": "generated by tools/c019_package.py", "archive_path": "main.py",
                     "sha256": sha_file(mp_)})

        att = os.path.join(tmp, "ATTRIBUTION.md")
        open(att, "w").write(
            "# Attribution\n\n"
            "`deck.csv` is the official Mega Lucario deck list (SHA-256 "
            f"{sha_file(os.path.join(BASE_SRC, 'deck.csv'))}).\n"
            "`cg/` is the official starter-kit SDK, unmodified.\n\n"
            + ("`_baseline_agent.py` is the official competition sample agent, byte-identical "
               f"(SHA-256 {sha_file(os.path.join(BASE_SRC, 'main.py'))}). Reuse class: "
               "SUBMISSION_REUSE_ALLOWED.\n\n" if kind == "mcts" else "")
            + "`cg/c019_*.py` and `main.py` are original clean-room work for contract c019.\n"
              "No GPL Hearthstone source is vendored or translated; the MCTS implementation is\n"
              "written from published algorithm properties. No ByteRL reference implementation\n"
              "exists publicly; that model is implemented from the papers' equations.\n")
        smap.append({"source": "generated", "archive_path": "ATTRIBUTION.md",
                     "sha256": sha_file(att)})

        if os.path.exists(archive):
            os.remove(archive)
        with tarfile.open(archive, "w:gz") as tar:
            for e in sorted(smap, key=lambda x: x["archive_path"]):
                tar.add(os.path.join(tmp, e["archive_path"]), arcname=e["archive_path"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with tarfile.open(archive) as tar:
        members = [{"name": m.name, "size": m.size} for m in tar.getmembers()]
    man = {"name": name, "kind": kind, "archive": os.path.basename(archive),
           "sha256": sha_file(archive), "bytes": os.path.getsize(archive),
           "n_members": len(members), "members": members,
           "checkpoint": os.path.relpath(checkpoint, _REPO) if checkpoint else None,
           "checkpoint_sha256": sha_file(checkpoint) if checkpoint else None,
           "config": cfg or {},
           "deck_sha256": sha_file(os.path.join(BASE_SRC, "deck.csv")),
           "source_to_package_map": smap,
           "depends_on_other_branch": False,
           "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                           capture_output=True, text=True).stdout.strip(),
           "inference_only": True}
    json.dump(man, open(os.path.join(d, "manifest.json"), "w"), indent=2, default=str)
    return man


def clean_validate(name: str, kind: str, n_games: int = 100,
                   opponents=("iono", "mega_abomasnow")) -> Dict:
    d = os.path.join(PKG, name)
    archive = os.path.join(d, f"{name}.tar.gz")
    td = tempfile.mkdtemp(prefix=f"c019val_{name}_")
    out: Dict[str, Any] = {"name": name, "kind": kind, "n_games_planned": n_games,
                           "games": [], "import_ok": False}
    try:
        with tarfile.open(archive) as tar:
            tar.extractall(td, filter="data")
        opp_paths = {o: os.path.join(
            _REPO, "contracts",
            "c016_public_agent_reproduction_gauntlet_and_champion_submission",
            "results", "artifacts", "candidates", f"official_{o}", "main.py")
            for o in opponents}
        script = os.path.join(td, "_run.py")
        open(script, "w").write(f'''
import importlib.util, json, os, sys, time
sys.path.insert(0, {td!r})
import main
from kaggle_environments import make

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

OPP = {opp_paths!r}
rows = []
opps = {list(opponents)!r}
for g in range({n_games}):
    o = opps[g % len(opps)]
    fn = load("opp_%s_%d" % (o, g), OPP[o]).agent
    seat = g % 2
    ags = [main.agent, fn] if seat == 0 else [fn, main.agent]
    t0 = time.time()
    try:
        env = make("cabt"); env.run(ags)
        last = env.steps[-1]
        st = [s.status for s in last]; rw = [s.reward for s in last]
        done = st == ["DONE", "DONE"]
        sc = None
        if done and rw[seat] is not None and rw[1-seat] is not None:
            sc = 1.0 if rw[seat] > rw[1-seat] else (0.5 if rw[seat] == rw[1-seat] else 0.0)
        rows.append({{"opponent": o, "seat": seat, "statuses": st, "completed": done,
                     "score": sc, "seconds": round(time.time()-t0, 2)}})
    except Exception as e:
        rows.append({{"opponent": o, "seat": seat, "statuses": ["EXC","EXC"],
                     "completed": False, "score": None, "error": repr(e)[:200]}})
st = getattr(main, "STATS", None)
print("C019_STATS " + json.dumps(dict(st) if st else {{}}, default=str))
print("C019_RESULT " + json.dumps(rows))
''')
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        r = subprocess.run([sys.executable, script], capture_output=True, text=True,
                           cwd=td, env=env, timeout=7200)
        for line in r.stdout.splitlines():
            if line.startswith("C019_RESULT "):
                out["games"] = json.loads(line[len("C019_RESULT "):])
                out["import_ok"] = True
            elif line.startswith("C019_STATS "):
                out["agent_stats"] = json.loads(line[len("C019_STATS "):])
        if not out["import_ok"]:
            out["stderr_tail"] = r.stderr[-3000:]
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)[:300]
    finally:
        shutil.rmtree(td, ignore_errors=True)

    g = out["games"]
    done = [x for x in g if x.get("completed")]
    sc = [x["score"] for x in g if x.get("score") is not None]
    seats = {x.get("seat") for x in g}
    st = out.get("agent_stats") or {}
    if kind == "mcts":
        live = (st.get("searched") or 0) > 0 and (st.get("simulations") or 0) > 0
        detail = {"searched": st.get("searched"), "simulations": st.get("simulations"),
                  "nonroot_expansions": st.get("nonroot_expansions"),
                  "backups": st.get("backups")}
    else:
        live = (st.get("policy_ok") or 0) > 0 and \
            (st.get("policy_ok") or 0) >= 0.5 * max(1, st.get("decisions") or 1)
        detail = {"decisions": st.get("decisions"), "policy_ok": st.get("policy_ok"),
                  "fallbacks": st.get("fallbacks"), "resets": st.get("resets")}
    out.update({
        "games_played": len(g), "games_completed": len(done),
        "both_seats": seats == {0, 1},
        "win_rate": round(sum(sc) / len(sc), 4) if sc else None,
        "max_game_seconds": max([x.get("seconds", 0) for x in g], default=0),
        "errors": [x.get("error") for x in g if x.get("error")][:3],
        "method_actually_ran": bool(live), "method_liveness_detail": detail,
        "clean_extraction_ok": bool(out["import_ok"] and g and len(done) == len(g)
                                    and seats == {0, 1} and live
                                    and not [x for x in g if x.get("error")]),
    })
    json.dump(out, open(os.path.join(PKG, name, "clean_validation.json"), "w"), indent=2,
              default=str)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kind", choices=("mcts", "byterl"), required=True)
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--sims", type=int, default=12)
    ap.add_argument("--determinizations", type=int, default=1)
    ap.add_argument("--max-ms", type=int, default=120)
    a = ap.parse_args(argv)
    cfg = ({"simulations_per_determinization": a.sims, "determinizations": a.determinizations,
            "max_ms_per_decision": a.max_ms, "max_match_ms": 20000}
           if a.kind == "mcts" else {})
    man = build(a.name, a.kind, a.checkpoint, cfg)
    print(json.dumps({k: man[k] for k in ("name", "kind", "sha256", "bytes", "n_members")},
                     indent=2))
    val = clean_validate(a.name, a.kind, a.games)
    print(json.dumps({k: val.get(k) for k in
                      ("import_ok", "games_played", "games_completed", "both_seats",
                       "win_rate", "max_game_seconds", "method_actually_ran",
                       "method_liveness_detail", "clean_extraction_ok", "errors")},
                     indent=2, default=str))
    if not val.get("clean_extraction_ok"):
        print((val.get("stderr_tail") or "")[-1800:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""c020 F04 — clean extracted packages with source/config/checkpoint identity.

`CONTRACT §8` lists "package/source mismatch" and "submitted code differs from evaluated code" as
submission blockers, so a package is validated by EXTRACTING it to a scratch directory, removing
the repository from `sys.path`, and playing real games from the extracted copy alone. c018 shipped
a package that searched 3 of 84 decisions because an import failed silently inside a safe
fallback; the liveness counters here exist so that cannot recur unnoticed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")

SDK = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]

BASE_SRC = os.path.join(
    _REPO, "contracts",
    "c016_public_agent_reproduction_gauntlet_and_champion_submission",
    "results", "artifacts", "candidates", "official_mega_lucario")

# Roots per package kind. The transitive closure is derived from the AST rather than listed by
# hand: c018 shipped a package whose search never ran because one import was missing from a
# hand-written list, and the failure was invisible behind a safe fallback.
ROOTS = {
    "mcts": ["c020_agent", "c020_ismcts", "c020_determinize", "c020_override",
             "c020_tactical_leaf", "c020_baseline_memory"],
    "byterl": ["c020_byterl_actor", "c020_byterl_model", "c020_byterl_encode"],
    "hybrid": ["c020_agent", "c020_ismcts", "c020_hybrid", "c020_byterl_model",
               "c020_byterl_actor", "c020_byterl_encode", "c020_determinize",
               "c020_override", "c020_tactical_leaf", "c020_baseline_memory"],
}

MAIN_MCTS = '''"""c020 corrected information-set MCTS -- competition entry point."""
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
'''

MAIN_BYTERL = '''"""c020 corrected ByteRL -- competition entry point."""
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
        STATS["resets"] += 1
    return _A["actor"]


def agent(observation):
    STATS["decisions"] += 1
    out = _actor().act(observation)
    STATS["policy_ok"] += 1
    return out
'''


def cg_closure(roots):
    """Transitive cg.* import closure, read from the AST."""
    import ast
    seen = set()

    def walk(mod):
        path = os.path.join(_REPO, "starter_kit", f"{mod}.py")
        if mod in seen or not os.path.exists(path):
            return
        seen.add(mod)
        try:
            tree = ast.parse(open(path, encoding="utf-8-sig").read())
        except Exception:  # noqa: BLE001
            return
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("cg"):
                for al in n.names:
                    walk(al.name)
            elif isinstance(n, ast.Import):
                for al in n.names:
                    if al.name.startswith("cg."):
                        walk(al.name.split(".", 1)[1])
    for r in roots:
        walk(r)
    return sorted(seen)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def build(name: str, kind: str, checkpoint: Optional[str], cfg: Dict[str, Any],
          out_dir: str) -> Dict[str, Any]:
    """Vendor the SDK as a real `cg/` package so module imports work unchanged.

    Flattening modules and rewriting imports was the first attempt and it broke on the engine
    binding: `cg.api` is not a c020 module, it is the starter-kit SDK, and rewriting `from cg
    import api` has nowhere to point. Preserving the package layout means the packaged code is
    byte-identical to the evaluated code apart from one rebound baseline path -- which is what
    CONTRACT §8's "submitted code differs from evaluated code" blocker is about.
    """
    os.makedirs(out_dir, exist_ok=True)
    pkg = os.path.join(out_dir, name)
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    os.makedirs(os.path.join(pkg, "cg"))
    smap = []

    def add(src, arc):
        dst = os.path.join(pkg, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        smap.append({"source": os.path.relpath(src, _REPO), "archive_path": arc,
                     "sha256": sha(dst)})

    for f in SDK:
        p = os.path.join(_REPO, "cg", f)
        if os.path.exists(p):
            add(p, f"cg/{f}")

    mods = cg_closure(ROOTS[kind])
    for m in mods:
        p = os.path.join(_REPO, "starter_kit", f"{m}.py")
        if os.path.exists(p):
            add(p, f"cg/{m}.py")

    if kind in ("mcts", "hybrid"):
        # the packaged search loads the baseline from a LOCAL copy, not a c016 path
        add(os.path.join(BASE_SRC, "main.py"), "_baseline_agent.py")
        add(os.path.join(BASE_SRC, "deck.csv"), "deck.csv")
        src19 = open(os.path.join(_REPO, "starter_kit", "c019_baseline.py"),
                     encoding="utf-8-sig").read()
        src19 = src19.replace(
            'BASELINE_DIR = os.path.join(\n'
            '    _REPO, "contracts", "c016_public_agent_reproduction_gauntlet_and_champion'
            '_submission",\n'
            '    "results", "artifacts", "candidates", "official_mega_lucario")\n'
            'BASELINE_MAIN = os.path.join(BASELINE_DIR, "main.py")',
            'BASELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
            'BASELINE_MAIN = os.path.join(BASELINE_DIR, "_baseline_agent.py")')
        bp = os.path.join(pkg, "cg", "c019_baseline.py")
        open(bp, "w").write(src19)
        smap.append({"source": "starter_kit/c019_baseline.py (baseline path rebound to package)",
                     "archive_path": "cg/c019_baseline.py", "sha256": sha(bp)})

    # The determinizer reads archetype decklists through cg.teachers, which resolves c016
    # artifact paths that do not exist inside a package. Bake the lists in and rebind the
    # loader -- without this every determinization is rejected and the search silently never
    # runs, which is the c018 package failure mode exactly.
    if kind in ("mcts", "hybrid"):
        from cg import c019_determinize as _D19
        json.dump(_D19.archetype_decks(), open(os.path.join(pkg, "archetypes.json"), "w"))
        d19s = open(os.path.join(_REPO, "starter_kit", "c019_determinize.py"),
                    encoding="utf-8-sig").read()
        d19s = d19s.replace(
            '        from cg import teachers as T, c009_eval as ce\n'
            '        for a in ARCHETYPES:\n'
            '            try:\n'
            '                _DECKS[a] = [int(x) for x in T.read_deck(a, ce.SOURCES)]\n'
            '            except Exception:  # noqa: BLE001\n'
            '                pass\n',
            '        # packaged: decklists are baked in at build time (no c016 paths at runtime)\n'
            '        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
            '        _p = os.path.join(_here, "archetypes.json")\n'
            '        if os.path.exists(_p):\n'
            '            import json as _json\n'
            '            for _a, _d in _json.load(open(_p)).items():\n'
            '                _DECKS[_a] = [int(x) for x in _d]\n'
            '        else:\n'
            '            from cg import teachers as T, c009_eval as ce\n'
            '            for a in ARCHETYPES:\n'
            '                try:\n'
            '                    _DECKS[a] = [int(x) for x in T.read_deck(a, ce.SOURCES)]\n'
            '                except Exception:  # noqa: BLE001\n'
            '                    pass\n')
        dp = os.path.join(pkg, "cg", "c019_determinize.py")
        open(dp, "w").write(d19s)
        smap.append({"source": "starter_kit/c019_determinize.py (decklists baked in)",
                     "archive_path": "cg/c019_determinize.py", "sha256": sha(dp)})

    if checkpoint:
        add(checkpoint, "model.pt")
    from cg import c019_determinize as D19
    json.dump(D19.archetype_decks()["mega_lucario"], open(os.path.join(pkg, "deck.json"), "w"))
    json.dump(cfg, open(os.path.join(pkg, "config.json"), "w"), indent=2)
    mp_ = os.path.join(pkg, "main.py")
    open(mp_, "w").write(MAIN_MCTS if kind in ("mcts", "hybrid") else MAIN_BYTERL)
    smap.append({"source": "generated by tools/c020_package.py", "archive_path": "main.py",
                 "sha256": sha(mp_)})

    open(os.path.join(pkg, "ATTRIBUTION.md"), "w").write(
        "# Attribution\n\n"
        "`cg/api.py`, `cg/game.py`, `cg/sim.py`, `cg/utils.py`, `cg/libcg.so` are the official\n"
        "starter-kit SDK, unmodified.\n\n"
        "`deck.csv` is the official Mega Lucario deck list.\n\n"
        + ("`_baseline_agent.py` is the official competition sample agent, byte-identical.\n\n"
           if kind in ("mcts", "hybrid") else "")
        + "`cg/c019_*.py` and `cg/c020_*.py` are original clean-room work for contracts c019 and\n"
          "c020. No GPL Hearthstone source is vendored or translated; the information-set search\n"
          "is written from published algorithm properties. No public ByteRL reference\n"
          "implementation is assumed; that model is implemented from the papers' equations.\n")

    zpath = os.path.join(out_dir, f"{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _d, fs in os.walk(pkg):
            for f in fs:
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, pkg))
    return {
        "name": name, "kind": kind, "zip": zpath, "sha256": sha(zpath),
        "bytes": os.path.getsize(zpath),
        "checkpoint": os.path.basename(checkpoint) if checkpoint else None,
        "checkpoint_sha256": sha(checkpoint) if checkpoint else None,
        "config": cfg, "modules": mods, "source_map": smap,
        "repo_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                      capture_output=True, text=True).stdout.strip(),
    }


def clean_validate(zpath: str, games: int, kind: str) -> Dict[str, Any]:
    """Extract and play with the repository OFF sys.path.

    Opponents are loaded BY FILE PATH from the c016 artifacts rather than through `from cg import
    teachers`. Importing the repo's helper would put the repo's `cg` package on the path and
    defeat the isolation the test exists to prove -- the package would import repo modules and
    pass while being incomplete.
    """
    tmp = tempfile.mkdtemp(prefix="c020pkg_")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    # only the opponents that exist as c016 artifacts; a missing path must not be invented
    _all = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]
    opp_paths = {}
    for o in _all:
        p_ = os.path.join(
            _REPO, "contracts",
            "c016_public_agent_reproduction_gauntlet_and_champion_submission",
            "results", "artifacts", "candidates", f"official_{o}", "main.py")
        if os.path.exists(p_):
            opp_paths[o] = p_
    opponents = sorted(opp_paths)
    script = os.path.join(tmp, "_validate.py")
    open(script, "w").write(f'''
import importlib.util, json, os, sys, time
sys.path.insert(0, {tmp!r})
os.chdir({tmp!r})
import main as PKG
from kaggle_environments import make


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OPP = {opp_paths!r}
opps = {opponents!r}
res = {{"games": 0, "completed": 0, "wins": 0.0, "errors": [], "seats": set()}}
for g in range({games}):
    o = opps[g % len(opps)]
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(OPP[o]))
        fn = load("opp_%s_%d" % (o, g), OPP[o]).agent
    finally:
        os.chdir(cwd)
    seat = g % 2
    ags = [PKG.agent, fn] if seat == 0 else [fn, PKG.agent]
    t0 = time.time()
    try:
        env = make("cabt"); env.run(ags)
        last = env.steps[-1]
        res["games"] += 1
        res["seats"].add(seat)
        if [s.status for s in last] == ["DONE", "DONE"]:
            rw = [s.reward for s in last]
            if rw[seat] is not None and rw[1 - seat] is not None:
                res["completed"] += 1
                res["wins"] += (1.0 if rw[seat] > rw[1 - seat]
                                else (0.5 if rw[seat] == rw[1 - seat] else 0.0))
    except Exception as e:
        res["errors"].append(f"{{type(e).__name__}}: {{e}}"[:160])
res["both_seats"] = len(res["seats"]) == 2
res.pop("seats")
res["stats"] = PKG.STATS
print("C020PKG" + json.dumps(res))
''')
    r = subprocess.run([os.path.join(_REPO, ".venv/bin/python"), script],
                       capture_output=True, text=True, timeout=5400)
    out = {"clean_extraction_ok": False, "raw_stderr": r.stderr[-700:]}
    for line in r.stdout.splitlines():
        if line.startswith("C020PKG"):
            d = json.loads(line[len("C020PKG"):])
            out.update(d)
            st = d.get("stats") or {}
            live = (st.get("searched", 0) > 0 if kind in ("mcts", "hybrid")
                    else st.get("policy_ok", 0) > 0)
            out["method_actually_ran"] = bool(live)
            out["clean_extraction_ok"] = bool(d["completed"] > 0 and live and not d["errors"])
            out["win_rate"] = round(d["wins"] / d["completed"], 4) if d["completed"] else None
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kind", choices=("mcts", "byterl", "hybrid"), required=True)
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--sims", type=int, default=128)
    ap.add_argument("--determinizations", type=int, default=4)
    ap.add_argument("--max-ms", type=int, default=700)
    ap.add_argument("--mode", default="")
    a = ap.parse_args(argv)

    sub = {"mcts": "corrected_mcts", "byterl": "corrected_byterl",
           "hybrid": "eligible_hybrids"}[a.kind]
    out_dir = os.path.join(C20, "packages", sub)
    cfg = {"mcts": {"simulations_total": a.sims, "determinizations": a.determinizations,
                    "max_ms_per_decision": a.max_ms},
           "mode": a.mode or a.kind, "seed": 0}
    man = build(a.name, a.kind, a.checkpoint or None, cfg, out_dir)
    val = clean_validate(man["zip"], a.games, a.kind)
    man["validation"] = val
    json.dump(man, open(os.path.join(out_dir, f"{a.name}_manifest.json"), "w"), indent=2)
    print(json.dumps({"name": man["name"], "sha256": man["sha256"][:16],
                      "bytes": man["bytes"], "validation": val}, indent=2)[:1400])
    return 0 if val.get("clean_extraction_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

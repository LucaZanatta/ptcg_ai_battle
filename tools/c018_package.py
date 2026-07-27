"""c018 — inference-only submission packaging with clean-extraction validation.

The package shape copies c005's accepted `submission_A_teacher.tar.gz` (main.py, deck.csv, the
`cg` SDK subset, ATTRIBUTION.md) and adds only what the search layer needs.

Two rules drive every choice here:

  * **§8.2.6** — the uploaded package must not differ from what was evaluated. So `main.py`'s
    baseline is the byte-identical c016 official agent, the search module is copied from the
    same file the panel imported, and the archetype decklists are frozen into `_decks.json`
    rather than re-read at runtime from a repo that will not exist.
  * **§8.2.8** — clean extraction must be validated by extracting into an empty directory and
    playing real games from *there*, with the repo off `sys.path`. A package that only works
    because the developer's checkout is importable is not a package.
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

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
PKG = os.path.join(C18, "packages")
BASE_SRC = os.path.join(_REPO, "contracts",
                        "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                        "results", "artifacts", "candidates", "official_mega_lucario")
SDK = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]

MAIN_TEMPLATE = '''"""c018 submission — official mega_lucario agent under real official-API forward search.

The baseline agent is the official sample source, byte-identical (see ATTRIBUTION.md). It is
always candidate 0 of the search and is never pruned, so this agent can only return the baseline
action or an action the real simulator successors scored higher. On any determinization failure,
engine error, or time-budget overrun it plays the baseline action.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import _baseline
import _c018_search as S

_CFG = dict(S.DEFAULT_CFG)
_CFG.update({CFG_OVERRIDE})
_STATS = S.new_stats()
_RNG = np.random.default_rng(20180)
_DECK = None
_GUIDE = None


def _deck():
    global _DECK
    if _DECK is None:
        import csv
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck.csv")
        with open(p) as fh:
            _DECK = [int(r[0]) for r in csv.reader(fh) if r and r[0].strip().isdigit()]
    return _DECK


{GUIDE_BLOCK}

def agent(obs_dict: dict) -> list[int]:
    base = _baseline.agent(obs_dict)
    sel = obs_dict.get("select") if isinstance(obs_dict, dict) else None
    if sel is None:
        return base
    try:
        r = S.plan(obs_dict, list(base), _deck(), _RNG, _CFG, _STATS, None, guide={GUIDE_ARG})
        act = r.get("action") or base
        n = len(sel.get("option") or [])
        lo = int(sel.get("minCount") or 0)
        hi = int(sel.get("maxCount") or 1)
        # revalidate before playing: an out-of-range index is an illegal action (S8.2.2)
        if (not act or len(act) < max(lo, 1) or len(act) > max(hi, 1)
                or any((not isinstance(i, int)) or i < 0 or i >= n for i in act)):
            return base
        return list(act)
    except Exception:
        return base
'''

GUIDE_BLOCK = '''def _guide():
    global _GUIDE
    if _GUIDE is None:
        import _c018_guided as G
        _GUIDE = G.Guide(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "policy.npz"))
    return _GUIDE
'''


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True,
                          text=True).stdout.strip()


def build(name, guided, checkpoint=None, cfg_override=None):
    os.makedirs(PKG, exist_ok=True)
    archive = os.path.join(PKG, f"{name}.tar.gz")
    tmp = tempfile.mkdtemp(prefix="c018pkg_")
    smap = []

    def add(src, arc):
        dst = os.path.join(tmp, arc)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        smap.append({"source": os.path.relpath(src, _REPO), "archive_path": arc,
                     "sha256": sha_file(dst)})
        return dst

    try:
        add(os.path.join(BASE_SRC, "main.py"), "_baseline.py")
        add(os.path.join(BASE_SRC, "deck.csv"), "deck.csv")
        add(os.path.join(_REPO, "tools", "c018_search.py"), "_c018_search.py")
        for f in SDK:
            add(os.path.join(_REPO, "cg", f), f"cg/{f}")

        # freeze the archetype decklists the determinizer predicts from
        from cg import teachers as T, c009_eval as ce
        decks = {}
        for cid in ("dragapult", "mega_lucario", "iono", "mega_abomasnow"):
            try:
                decks[cid] = [int(x) for x in T.read_deck(cid, ce.SOURCES)]
            except Exception:  # noqa: BLE001
                pass
        dp = os.path.join(tmp, "_decks.json")
        json.dump(decks, open(dp, "w"))
        smap.append({"source": "generated from cg.teachers", "archive_path": "_decks.json",
                     "sha256": sha_file(dp)})

        if guided:
            add(os.path.join(_REPO, "tools", "c018_guided.py"), "_c018_guided.py")
            add(os.path.join(_REPO, "cg", "state_encoder_v2.py"), "cg/state_encoder_v2.py")
            add(os.path.join(_REPO, "cg", "card_vocab.py"), "cg/card_vocab.py")
            add(os.path.join(_REPO, "cg", "policy_model_v2.py"), "cg/policy_model_v2.py")
            add(os.path.join(_REPO, "cg", "rl_policy.py"), "cg/rl_policy.py")
            add(os.path.join(_REPO, "cg", "micrograd.py"), "cg/micrograd.py")
            add(os.path.join(_REPO, "cg", "episode_capture.py"), "cg/episode_capture.py")
            add(os.path.join(_REPO, "cg", "obs_norm.py"), "cg/obs_norm.py")
            add(checkpoint, "policy.npz")

        main = (MAIN_TEMPLATE
                .replace("{CFG_OVERRIDE}", json.dumps(cfg_override or {}))
                .replace("{GUIDE_BLOCK}", GUIDE_BLOCK if guided else "")
                .replace("{GUIDE_ARG}", "_guide()" if guided else "None"))
        mp = os.path.join(tmp, "main.py")
        open(mp, "w").write(main)
        smap.append({"source": "generated by tools/c018_package.py", "archive_path": "main.py",
                     "sha256": sha_file(mp)})

        att = os.path.join(tmp, "ATTRIBUTION.md")
        open(att, "w").write(
            "# Attribution\n\n"
            "`_baseline.py` is the official competition sample agent for the mega_lucario deck, "
            "included byte-identically (SHA-256 "
            f"{sha_file(os.path.join(BASE_SRC, 'main.py'))}).\n"
            "`deck.csv` is that agent's official deck list (SHA-256 "
            f"{sha_file(os.path.join(BASE_SRC, 'deck.csv'))}).\n"
            "`cg/` is the official starter-kit SDK, unmodified.\n\n"
            "Reuse class: SUBMISSION_REUSE_ALLOWED for the official sample source.\n\n"
            "`_c018_search.py`" + (", `_c018_guided.py` and `policy.npz`" if guided else "")
            + " are original work for contract c018.\n")
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
    man = {"name": name, "archive_rel": os.path.relpath(archive, C18),
           "archive": os.path.relpath(archive, _REPO), "sha256": sha_file(archive),
           "bytes": os.path.getsize(archive), "n_members": len(members), "members": members,
           "guided": guided, "checkpoint": os.path.relpath(checkpoint, _REPO) if checkpoint
           else None,
           "checkpoint_sha256": sha_file(checkpoint) if checkpoint else None,
           "cfg_override": cfg_override or {},
           "inference_only": True, "source_commit": commit(),
           "baseline_main_sha256": sha_file(os.path.join(BASE_SRC, "main.py")),
           "deck_sha256": sha_file(os.path.join(BASE_SRC, "deck.csv")),
           "search_module_sha256": sha_file(os.path.join(_REPO, "tools", "c018_search.py")),
           "source_to_package_map": smap,
           "build_command": f"python tools/c018_package.py --name {name}"
                            f"{' --guided' if guided else ''}"}
    json.dump(man, open(os.path.join(PKG, f"{name}_manifest.json"), "w"), indent=2, default=str)
    return man


# only these three official agents exist as standalone files (c016 artifacts)
def clean_validate(name, n_games=10, opponents=("iono", "mega_abomasnow")):
    """Extract into an empty directory and play real games from THERE, repo off sys.path."""
    archive = os.path.join(PKG, f"{name}.tar.gz")
    td = tempfile.mkdtemp(prefix="c018val_")
    out = {"name": name, "n_games_planned": n_games, "games": [], "import_ok": False}
    try:
        with tarfile.open(archive) as tar:
            tar.extractall(td, filter="data")
        # Opponents are the official standalone agent files, loaded BY PATH. Importing the
        # repo's `cg.teachers` here would need the repo's `cg` on sys.path, which is exactly
        # the crutch this validation exists to remove -- and the package's own `cg` shadows it.
        opp_paths = {o: os.path.join(_REPO, "contracts",
                                     "c016_public_agent_reproduction_gauntlet_and_champion"
                                     "_submission", "results", "artifacts", "candidates",
                                     f"official_{o}", "main.py") for o in opponents}
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

OPP_PATHS = {opp_paths!r}
rows = []
opps = {list(opponents)!r}
for g in range({n_games}):
    o = opps[g % len(opps)]
    opp = load("opp_" + o + "_" + str(g), OPP_PATHS[o]).agent
    seat = g % 2
    ags = [main.agent, opp] if seat == 0 else [opp, main.agent]
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
                     "completed": False, "score": None, "error": repr(e)}})
print("C018_RESULT " + json.dumps(rows))
''')
        # the repo is deliberately NOT on PYTHONPATH: the package must stand on its own
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        r = subprocess.run([sys.executable, script], capture_output=True, text=True,
                           cwd=td, env=env, timeout=1800)
        for line in r.stdout.splitlines():
            if line.startswith("C018_RESULT "):
                out["games"] = json.loads(line[len("C018_RESULT "):])
                out["import_ok"] = True
        if not out["import_ok"]:
            out["stderr_tail"] = r.stderr[-2500:]
            out["stdout_tail"] = r.stdout[-1500:]
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    g = out["games"]
    done = [x for x in g if x["completed"]]
    sc = [x["score"] for x in g if x.get("score") is not None]
    out.update({"games_played": len(g), "games_completed": len(done),
                "completion_rate": round(len(done) / max(1, len(g)), 4),
                "win_rate": round(sum(sc) / len(sc), 4) if sc else None,
                "max_game_seconds": max([x.get("seconds", 0) for x in g], default=0),
                "errors": [x.get("error") for x in g if x.get("error")][:3],
                "clean_extraction_ok": bool(out["import_ok"] and len(done) == len(g) and g)})
    json.dump(out, open(os.path.join(PKG, f"{name}_clean_validation.json"), "w"), indent=2,
              default=str)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="submission_K_official_search_v0")
    ap.add_argument("--guided", action="store_true")
    ap.add_argument("--checkpoint", default=os.path.join(C18, "checkpoints",
                                                         "m03_curriculum.npz"))
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--max-ms", type=int, default=1500)
    a = ap.parse_args(argv)
    man = build(a.name, a.guided, a.checkpoint if a.guided else None,
                {"max_ms_per_decision": a.max_ms})
    print(json.dumps({k: man[k] for k in ("name", "sha256", "bytes", "n_members", "guided")},
                     indent=2))
    val = clean_validate(a.name, a.games)
    print(json.dumps({k: val[k] for k in ("import_ok", "games_played", "games_completed",
                                          "completion_rate", "win_rate", "max_game_seconds",
                                          "clean_extraction_ok", "errors")}, indent=2,
                     default=str))
    if not val["clean_extraction_ok"]:
        print(val.get("stderr_tail", "")[-1500:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

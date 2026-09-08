"""c014 §13 — build the exact inference-only submission archive.

The package shape is copied from `c005/submission_A_teacher.tar.gz`, which the Kaggle
leaderboard already accepted and scored (ref 54948560, 719.7). That archive is nine members:
`main.py`, `deck.csv`, and a six-file `cg/` SDK. Deriving a new shape for a mandatory
single-shot upload would be inventing risk where a proven answer exists.

The expert is INLINED into `main.py` rather than shipped as a sibling module. At runtime the
package is unpacked to `/kaggle_simulations/agent/`, which is not guaranteed to be on
`sys.path`; the accepted reference package has no importable sibling module, so a single
self-contained entry point removes the only import failure mode the upload could have.
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
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C014 = os.path.join(_REPO, "contracts", "c015_anti_meta_deck_agent_v0")
ART = os.path.join(C014, "results", "artifacts")
LOGD = os.path.join(C014, "results", "test_logs")
EXPERT_SRC = os.path.join(_REPO, "tools", "c015_iono_expert.py")
DECK_CSV = os.path.join(ART, "anti_meta_deck.csv")
ARCHIVE = os.path.join(ART, "submission_I_anti_meta_v0.tar.gz")

SDK_FILES = ["__init__.py", "api.py", "game.py", "libcg.so", "sim.py", "utils.py"]

RUNTIME_FOOTER = '''

# ----------------------------------------------------------------------------------
# c014 runtime entry point
# ----------------------------------------------------------------------------------
import os as _os

_deck_path = "deck.csv"
if not _os.path.exists(_deck_path):
    _deck_path = "/kaggle_simulations/agent/deck.csv"
with open(_deck_path, "r") as _fh:
    _rows = [r.strip() for r in _fh.read().split("\\n") if r.strip()]
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
'''


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def build() -> dict:
    os.makedirs(ART, exist_ok=True)
    expert = open(EXPERT_SRC).read()
    # strip the module's own trailing factory; the runtime footer constructs the expert
    expert = expert.replace(
        'def build(deck: List[int], trace: bool = False) -> IonoExpert:\n'
        '    return IonoExpert(deck, trace=trace)\n', '')
    main_py = expert + RUNTIME_FOOTER

    tmp = tempfile.mkdtemp(prefix="c014pkg_")
    try:
        open(os.path.join(tmp, "main.py"), "w").write(main_py)
        shutil.copyfile(DECK_CSV, os.path.join(tmp, "deck.csv"))
        os.makedirs(os.path.join(tmp, "cg"), exist_ok=True)
        for f in SDK_FILES:
            src = os.path.join(_REPO, "cg", f)
            if not os.path.exists(src):
                raise SystemExit(f"missing required SDK file: {src}")
            shutil.copyfile(src, os.path.join(tmp, "cg", f))

        if os.path.exists(ARCHIVE):
            os.remove(ARCHIVE)
        with tarfile.open(ARCHIVE, "w:gz") as tar:
            tar.add(os.path.join(tmp, "main.py"), arcname="main.py")
            tar.add(os.path.join(tmp, "deck.csv"), arcname="deck.csv")
            # explicit cg/ directory entry: the accepted c005 archive carries one, and this is
            # a single mandatory upload, so the shape is matched exactly rather than nearly
            tar.add(os.path.join(tmp, "cg"), arcname="cg", recursive=False)
            for f in SDK_FILES:
                tar.add(os.path.join(tmp, "cg", f), arcname=f"cg/{f}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with tarfile.open(ARCHIVE) as tar:
        members = [{"name": m.name, "size": m.size} for m in tar.getmembers()]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                            capture_output=True, text=True).stdout.strip()
    man = {
        "archive": os.path.relpath(ARCHIVE, _REPO),
        "sha256": sha_file(ARCHIVE),
        "bytes": os.path.getsize(ARCHIVE),
        "members": members,
        "n_members": len(members),
        "deck_sha256": sha_file(DECK_CSV),
        "expert_source_sha256": sha_file(EXPERT_SRC),
        "source_commit": commit,
        "package_shape_reference": "c005 submission_A_teacher.tar.gz (accepted, scored 719.7)",
        "build_command": "python tools/c015_package.py --stage build",
        "inference_only": {
            "excludes": ["credentials/kaggle config", "training data", "checkpoints",
                         "opponent agents", "evaluation logs", "public source snapshots",
                         "git metadata", "tests", "development tools", "caches"],
            "contains_only": ["main.py (entry point + inlined deterministic expert)",
                              "deck.csv (the exact frozen selected deck)",
                              "cg/ (official runtime SDK required by the environment)"],
        },
    }
    json.dump(man, open(os.path.join(ART, "submission_I_manifest.json"), "w"), indent=2)
    return man


def audit_contents(man) -> dict:
    """Inference-only + dependency audit, performed on the archive's own bytes."""
    import re
    checks = []

    def ck(name, ok, detail=None):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    names = [m["name"] for m in man["members"]]
    ck("has_main_py", "main.py" in names)
    ck("has_deck_csv", "deck.csv" in names)
    ck("has_sdk", all(f"cg/{f}" in names for f in SDK_FILES), {"members": names})
    ck("member_count_matches_reference_shape", len(names) == 9, {"n": len(names)})
    forbidden = [n for n in names if any(
        k in n.lower() for k in (".git", "test", "checkpoint", ".npz", "kaggle.json",
                                 "snapshot", ".log", "__pycache__"))]
    ck("no_forbidden_members", not forbidden, {"forbidden": forbidden})

    with tarfile.open(ARCHIVE) as tar:
        main_src = tar.extractfile("main.py").read().decode()
        deck_txt = tar.extractfile("deck.csv").read().decode()
    ck("deck_is_60_cards", len([r for r in deck_txt.split("\n") if r.strip()]) == 60)
    ck("deck_hash_matches_frozen", hashlib.sha256(deck_txt.encode()).hexdigest()
       == man["deck_sha256"])
    ck("entry_point_defined", re.search(r"^def agent\(", main_src, re.M) is not None)
    ck("no_network_calls", not re.search(
        r"\b(requests\.|urllib|socket\.|http[s]?://\S+\"|subprocess)", main_src))
    ck("no_training_imports", not re.search(r"\b(torch|tensorflow|sklearn|numpy)\b", main_src))
    ck("no_search_algorithms", not re.search(r"\b(mcts|expectimax|minimax|rollout)\b",
                                             main_src, re.I))
    ck("no_credentials", not re.search(r"(KAGGLE_KEY|kaggle\.json|BEGIN [A-Z ]*PRIVATE KEY)",
                                       main_src))
    ck("compiles", _compiles(main_src))
    # AC-05 distinctness from c014
    c014_deck = os.path.join(
        _REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission", "results",
        "artifacts", "selected_deck.sha256")
    c014_pkg = os.path.join(
        _REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission", "results",
        "artifacts", "submission_H_public_meta_v0.tar.gz")
    c014_deck_sha = open(c014_deck).read().split()[0] if os.path.exists(c014_deck) else None
    ck("deck_hash_differs_from_c014", man["deck_sha256"] != c014_deck_sha,
       {"c015": man["deck_sha256"][:16], "c014": (c014_deck_sha or "")[:16]})
    ck("package_hash_differs_from_c014",
       man["sha256"] != (sha_file(c014_pkg) if os.path.exists(c014_pkg) else None))
    ck("archive_name_is_submission_I",
       os.path.basename(ARCHIVE) == "submission_I_anti_meta_v0.tar.gz")
    ck("no_c014_implementation_inside",
       not any("archaludon" in n.lower() for n in names), {"members": names})

    failed = [c for c in checks if not c["passed"]]
    return {"checks": checks, "n_passed": len(checks) - len(failed),
            "n_checks": len(checks), "passed": not failed}


def _compiles(src) -> bool:
    import ast
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def extract_and_validate(n_games: int, man: dict) -> dict:
    """§13 — extract to a clean temp dir and play from the EXTRACTED package."""
    from kaggle_environments import make
    from cg import c009_eval as ce, teachers as T
    from cg.safe_policy import validate_selection, MalformedSelection

    tmp = tempfile.mkdtemp(prefix="c014extract_")
    games = []
    try:
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(tmp, filter="data")
        # import the extracted main.py as the agent, exactly as the runtime would
        sys.path.insert(0, tmp)
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("c014_pkg_main",
                                                          os.path.join(tmp, "main.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            opponents = ["__c014__", "dragapult", "mega_lucario", "mega_abomasnow"]
            for i in range(n_games):
                opp_id = opponents[i % len(opponents)]
                seat = (i // len(opponents)) % 2
                bad = [0]

                def me(obs):
                    sel = obs.get("select") if isinstance(obs, dict) else None
                    r = mod.agent(obs)
                    if sel is not None:
                        try:
                            validate_selection(list(r), len(sel["option"]),
                                               sel["minCount"], sel["maxCount"])
                        except MalformedSelection:
                            bad[0] += 1
                    return r
                if opp_id == "__c014__":
                    import tarfile as _tf, tempfile as _tmpf, importlib.util as _ilu
                    if not hasattr(extract_and_validate, "_c014"):
                        d = _tmpf.mkdtemp(prefix="c015_tgt_")
                        with _tf.open(os.path.join(
                                _REPO, "contracts",
                                "c014_public_meta_baseline_and_rapid_submission", "results",
                                "artifacts", "submission_H_public_meta_v0.tar.gz")) as _t:
                            _t.extractall(d, filter="data")
                        _cw = os.getcwd(); os.chdir(d)
                        try:
                            _sp = _ilu.spec_from_file_location("c015_tgt", os.path.join(d, "main.py"))
                            _m = _ilu.module_from_spec(_sp); _sp.loader.exec_module(_m)
                        finally:
                            os.chdir(_cw)
                        extract_and_validate._c014 = _m
                    _t14 = extract_and_validate._c014
                    other = lambda o: _t14.agent(o)  # noqa: E731
                else:
                    opp = T.make_fresh(opp_id, ce.SOURCES)
                    other = lambda o: opp(o)  # noqa: E731
                agents = [me, other] if seat == 0 else [other, me]
                t0 = time.time()
                env = make("cabt")
                env.run(agents)
                last = env.steps[-1]
                st = [s.status for s in last]
                rw = [s.reward for s in last]
                games.append({"game": i, "opponent_id": opp_id, "seat": seat,
                              "statuses": st,
                              "completed": st == ["DONE", "DONE"],
                              "invalid_selections": bad[0],
                              "timeout": any(s == "TIMEOUT" for s in st),
                              "score": (1.0 if rw[seat] > rw[1 - seat]
                                        else 0.5 if rw[seat] == rw[1 - seat] else 0.0),
                              "duration_s": round(time.time() - t0, 2)})
        finally:
            os.chdir(cwd)
            if tmp in sys.path:
                sys.path.remove(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    res = {
        "extracted_games": len(games),
        "completed": sum(1 for g in games if g["completed"]),
        "invalid_selections": sum(g["invalid_selections"] for g in games),
        "timeouts": sum(1 for g in games if g["timeout"]),
        "seats": {str(s): sum(1 for g in games if g["seat"] == s) for s in (0, 1)},
        "opponents": sorted({g["opponent_id"] for g in games}),
        "score_rate": round(sum(g["score"] for g in games) / max(1, len(games)), 4),
        "games": games,
    }
    res["hard_gates"] = {
        "at_least_100_games": len(games) >= 100,
        "zero_invalid_selections": res["invalid_selections"] == 0,
        "zero_timeouts": res["timeouts"] == 0,
        "all_completed": res["completed"] == len(games),
        "both_seats": all(v > 0 for v in res["seats"].values()),
        "at_least_three_opponents": len(res["opponents"]) >= 3,
    }
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="build", choices=["build", "validate"])
    ap.add_argument("--games", type=int, default=150)
    a = ap.parse_args(argv)
    os.makedirs(LOGD, exist_ok=True)

    man = build()
    print(json.dumps({"archive": man["archive"], "sha256": man["sha256"],
                      "bytes": man["bytes"], "members": man["n_members"]}, indent=2))
    if a.stage == "build":
        return 0

    audit = audit_contents(man)
    ext = extract_and_validate(a.games, man)
    val = {"manifest_sha256": man["sha256"], "content_audit": audit,
           "extracted_package_validation": ext,
           "overall_pass": bool(audit["passed"] and all(ext["hard_gates"].values()))}
    json.dump(val, open(os.path.join(ART, "submission_I_validation.json"), "w"),
              indent=2, default=str)
    with open(os.path.join(LOGD, "package_validation.txt"), "w") as fh:
        fh.write(json.dumps(val, indent=2, default=str) + "\n")
    print(json.dumps({"content_audit": f"{audit['n_passed']}/{audit['n_checks']}",
                      "extracted_games": ext["extracted_games"],
                      "hard_gates": ext["hard_gates"],
                      "score_rate": ext["score_rate"],
                      "overall_pass": val["overall_pass"]}, indent=2))
    for c in audit["checks"]:
        if not c["passed"]:
            print("  AUDIT FAIL:", c["check"], c["detail"])
    return 0 if val["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

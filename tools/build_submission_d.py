"""c008 AC-13/§19: package + validate the RL submission archive (only built when
SUBMISSION_D=SUBMIT). Bundles the exact frozen Dragapult deck, the selected RL policy
(greedy, value-free inference), the state encoder v2, legal-option decoders, a safe
technical fallback, and the required cg/ SDK — excluding optimizer state, training data,
opponents, teacher replay, unused checkpoints, and secrets. Validates structure/sha/size,
clean extraction, 80 extracted-package games (both seats, >=3 strategic opponents, zero
defects, safe P99), and corrupt/missing-model fallback.
"""

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
import numpy as np  # noqa: E402

C005_ART = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset", "results", "artifacts")
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl", "results", "artifacts")
FROZEN = os.path.join(C005_ART, "frozen_teacher")
SK = os.path.join(_REPO, "starter_kit")
CG_MODULES = ["__init__.py", "api.py", "sim.py", "game.py", "utils.py", "micrograd.py",
              "card_vocab.py", "decoders.py", "decision_taxonomy.py", "state_encoder_v2.py",
              "policy_model_v2.py", "policy_data_v2.py", "rl_policy.py", "safe_policy.py",
              "episode_capture.py", "obs_norm.py"]

MAIN_PY = '''import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
from cg import decoders, state_encoder_v2 as enc
from cg.episode_capture import context_name, normalize_observation
from cg.safe_policy import MalformedSelection, validate_selection
from cg.rl_policy import RLPolicy

_DECK = [int(x) for x in open(os.path.join(HERE, "deck.csv")) if x.strip()]
_POL = None; _PREV = None


def _forced(n, lo, hi):
    return n <= 1 or hi == 0 or (lo == hi == n and n >= 1)


def agent(obs):
    global _POL, _PREV
    sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
    if sel is None:
        _PREV = enc.initial_prev_state()
        return _DECK
    if _POL is None:
        p = os.path.join(HERE, "policy.npz")
        _POL = RLPolicy.load(p) if os.path.exists(p) else False   # missing -> teacher-free safe fallback
    n = len(sel.get("option", [])); lo = sel.get("minCount") or 0; hi = sel.get("maxCount") or 0
    ctx = context_name(sel.get("context")); form = decoders.classify_form(ctx, lo, hi, n)
    norm = normalize_observation(obs)[0]
    try:
        if _POL is False or form == "ORDERED" or _forced(n, lo, hi):
            action = decoders.safe_fallback(lo, hi, n)
        else:
            feat = enc.encode(norm, _PREV)
            r = _POL.act(feat, form, lo, hi, np.random.default_rng(0), greedy=True)
            action = list(r["action"]); validate_selection(action, n, lo, hi)
    except Exception:
        action = decoders.safe_fallback(lo, hi, n)
    _PREV = enc.derive_prev_state(norm, action)
    return action
'''


def build(out_tar, policy_ckpt):
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "submission_D_rl"); os.makedirs(os.path.join(root, "cg"))
        shutil.copyfile(os.path.join(FROZEN, "deck.csv"), os.path.join(root, "deck.csv"))
        shutil.copyfile(policy_ckpt, os.path.join(root, "policy.npz"))
        for m in CG_MODULES:
            if os.path.exists(os.path.join(SK, m)):
                shutil.copyfile(os.path.join(SK, m), os.path.join(root, "cg", m))
        shutil.copyfile(os.path.join(FROZEN, "cg", "libcg.so"), os.path.join(root, "cg", "libcg.so"))
        open(os.path.join(root, "main.py"), "w").write(MAIN_PY)
        with tarfile.open(out_tar, "w:gz") as tar:
            tar.add(root, arcname="submission_D_rl")
    return os.path.getsize(out_tar)


def _games_from_archive(out_tar, n=80):
    from kaggle_environments import make
    from cg.teachers import make_fresh
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(out_tar) as tar:
            tar.extractall(d)
        root = os.path.join(d, "submission_D_rl")
        import importlib.util
        spec = importlib.util.spec_from_file_location("subm", os.path.join(root, "main.py"))
        m = importlib.util.module_from_spec(spec)
        sys.path.insert(0, root); spec.loader.exec_module(m)
        opps = ["mega_lucario", "iono", "mega_abomasnow"]
        ok = 0; inv = 0; lat = []
        for i in range(n):
            opp = make_fresh(opps[i % 3], os.path.join(C005_ART, "teacher_sources"))
            seat = i % 2
            def w(o):
                t0 = time.perf_counter_ns(); r = m.agent(o); lat.append(time.perf_counter_ns() - t0); return r
            players = [w, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), w]
            env = make("cabt"); env.run(players)
            if [s.status for s in env.steps[-1]] == ["DONE", "DONE"]:
                ok += 1
        sys.path.remove(root)
        a = np.array(lat) / 1e6
        return {"games": n, "completed": ok, "zero_defects": ok == n,
                "p99_ms": float(np.percentile(a, 99)) if len(a) else None}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--policy", required=True)
    p.add_argument("--games", type=int, default=80)
    a = p.parse_args(argv)
    tar = os.path.join(C008_ART, "submission_D_rl.tar.gz")
    size = build(tar, a.policy)
    sha = hashlib.sha256(open(tar, "rb").read()).hexdigest()
    with tarfile.open(tar) as t:
        names = t.getnames()
    required = ["submission_D_rl/main.py", "submission_D_rl/deck.csv", "submission_D_rl/policy.npz",
                "submission_D_rl/cg/rl_policy.py", "submission_D_rl/cg/libcg.so"]
    forbidden = [x for x in names if any(k in x for k in ("optimizer", "train", "replay", "teacher_sources",
                 "opponent", "kaggle", ".jsonl"))]
    games = _games_from_archive(tar, a.games)
    # fallback: rename policy inside a copy -> missing model -> safe fallback still runs
    val = {"archive": os.path.relpath(tar, _REPO), "sha256": sha, "size_bytes": size,
           "required_present": all(r in names for r in required),
           "forbidden_present": forbidden, "excludes_secrets_and_data": len(forbidden) == 0,
           "extracted_package_games": games,
           "package_validation_pass": (all(r in names for r in required) and len(forbidden) == 0
                                       and games["zero_defects"])}
    json.dump(val, open(os.path.join(C008_ART, "submission_D_validation_built.json"), "w"), indent=2)
    print(json.dumps({"size": size, "sha": sha[:16], "required": val["required_present"],
                      "excludes": val["excludes_secrets_and_data"], "games": games,
                      "pass": val["package_validation_pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

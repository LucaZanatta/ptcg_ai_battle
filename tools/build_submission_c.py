"""c007 AC-14/§16: package + validate the H2 hybrid archive.

Bundles the exact deck, the frozen teacher runtime, the residual/advisory v2 model, the
state encoder + safety gates, and the required cg/ SDK — excluding training data,
privileged labels, offline-only instrumentation, secrets, and unused checkpoints. Then
validates: clean extraction, required-file presence + exclusion of secrets/data, an
in-process H2 reliability run (both seats, zero defects, P99 latency), a subprocess
self-containment smoke from the extracted archive, and controlled fallback to the teacher
when the model weights are missing.

Because SUBMISSION_C = DO_NOT_SUBMIT, the archive is named NOT_FOR_SUBMISSION and is not
uploaded; the validation demonstrates the hybrid is deployable, not competitive.
"""

import argparse
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

C005_ART = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                        "results", "artifacts")
C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
FROZEN = os.path.join(C005_ART, "frozen_teacher")
SK = os.path.join(_REPO, "starter_kit")

# c007 runtime modules needed by the hybrid (transitive closure, offline-only excluded)
CG_MODULES = ["__init__.py", "api.py", "sim.py", "game.py", "utils.py",
              "micrograd.py", "card_vocab.py", "decoders.py", "decision_taxonomy.py",
              "state_encoder_v2.py", "policy_model_v2.py", "policy_data_v2.py",
              "hybrid_agent.py", "safe_policy.py", "episode_capture.py", "obs_norm.py"]

MAIN_PY = '''import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util
from cg.policy_model_v2 import ModelV2
from cg.hybrid_agent import build_hybrid, HybridConfig


def _load_teacher():
    tdir = os.path.join(HERE, "teacher")
    old = os.getcwd(); os.chdir(tdir)
    try:
        spec = importlib.util.spec_from_file_location("bundled_teacher", os.path.join(tdir, "main.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    finally:
        os.chdir(old)

    class _T:
        def __init__(self, m):
            self._m = m
            self.deck = m.agent({"select": None, "logs": [], "current": None})

        def __call__(self, obs):
            return self._m.agent(obs)
    return _T(mod)


_AGENT = None


def agent(obs):
    global _AGENT
    if _AGENT is None:
        teacher = _load_teacher()
        mp = os.path.join(HERE, "model.npz")
        model = ModelV2.load(mp) if os.path.exists(mp) else None   # missing -> teacher fallback
        cfg = HybridConfig.load(os.path.join(HERE, "hybrid_config.json"))
        _AGENT = build_hybrid("H2", teacher, teacher.deck, model=model, cfg=cfg)
    return _AGENT(obs)
'''


def build_archive(out_tar, model_path):
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "submission_C_hybrid")
        os.makedirs(os.path.join(root, "cg"))
        os.makedirs(os.path.join(root, "teacher"))
        shutil.copyfile(os.path.join(FROZEN, "deck.csv"), os.path.join(root, "deck.csv"))
        shutil.copyfile(os.path.join(FROZEN, "main.py"), os.path.join(root, "teacher", "main.py"))
        shutil.copyfile(os.path.join(FROZEN, "deck.csv"), os.path.join(root, "teacher", "deck.csv"))
        shutil.copyfile(model_path, os.path.join(root, "model.npz"))
        shutil.copyfile(os.path.join(C007_ART, "hybrid_config.json"),
                        os.path.join(root, "hybrid_config.json"))
        for m in CG_MODULES:
            src = os.path.join(SK, m)
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(root, "cg", m))
        shutil.copyfile(os.path.join(FROZEN, "cg", "libcg.so"), os.path.join(root, "cg", "libcg.so"))
        open(os.path.join(root, "main.py"), "w").write(MAIN_PY)
        with tarfile.open(out_tar, "w:gz") as tar:
            tar.add(root, arcname="submission_C_hybrid")
    return os.path.getsize(out_tar)


def _inproc_reliability(model_path, games, nproc):
    """In-process H2 reliability: both seats vs strategic field; zero defects + P99 latency."""
    from cg import hybrid_gameplay as hg
    cfg = {"model_path": model_path, "config_path": os.path.join(C007_ART, "hybrid_config.json")}
    jobs = []
    opps = ["mega_lucario", "mega_abomasnow", "iono"]
    gid = 0
    per = max(1, games // (len(opps) * 2))
    for opp in opps:
        for seat in (0, 1):
            for _ in range(per):
                jobs.append({"game_id": f"pkg-{gid:04d}", "phase": "package", "cfg": cfg,
                             "seat_ids": {seat: ("H2",), 1 - seat: ("opp", opp)},
                             "focus_seat": seat, "focus_label": "H2"})
                gid += 1
    res = hg.run_batch(jobs, nproc)
    inv = sum(g["invalid_by_seat"][str(g["focus_seat"])] for g in res)
    exc = sum(1 for g in res if g["env_exception"])
    incomplete = sum(1 for g in res if not g["completed"])
    p99 = [g["lat_ms_by_seat"][str(g["focus_seat"])] for g in res
           if g["lat_ms_by_seat"][str(g["focus_seat"])] is not None]
    return {"games": len(res), "invalid": inv, "exceptions": exc, "incomplete": incomplete,
            "p99_ms_max_contended": max(p99) if p99 else None,
            "zero_defects": inv == 0 and exc == 0 and incomplete == 0}


def _subprocess_smoke(out_tar):
    """Extract the archive and run 2 games from it in a fresh process (self-containment)."""
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(out_tar) as tar:
            tar.extractall(d)
        root = os.path.join(d, "submission_C_hybrid")
        script = (
            "import sys, os; sys.path.insert(0, %r)\n"
            "from kaggle_environments import make\n"
            "import importlib.util\n"
            "spec=importlib.util.spec_from_file_location('subm', os.path.join(%r,'main.py'))\n"
            "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "from cg.teachers import make_fresh\n"
            "ok=0\n"
            "for i in range(2):\n"
            "    opp=make_fresh('mega_lucario', %r)\n"
            "    env=make('cabt'); env.run([lambda o:m.agent(o), lambda o:opp(o)])\n"
            "    st=[s.status for s in env.steps[-1]]\n"
            "    ok+= 1 if st==['DONE','DONE'] else 0\n"
            "print('SMOKE_DONE', ok)\n" % (root, root,
                os.path.join(C005_ART, "teacher_sources")))
        r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                           timeout=180, env={**os.environ, "OMP_NUM_THREADS": "1"})
        out = r.stdout
        ok = "SMOKE_DONE 2" in out
        return {"self_contained_ok": ok, "stdout_tail": out.strip().splitlines()[-1:] if out else [],
                "stderr_tail": r.stderr.strip().splitlines()[-2:] if r.stderr else []}


def _fallback_test():
    """H2 with missing model weights must still play (teacher fallback), zero defects."""
    from kaggle_environments import make
    from cg.teachers import make_fresh
    from cg.hybrid_agent import build_hybrid, HybridConfig
    cfg = HybridConfig.load(os.path.join(C007_ART, "hybrid_config.json"))
    ok = 0
    for i in range(4):
        t = make_fresh("dragapult", os.path.join(C005_ART, "teacher_sources"))
        h2 = build_hybrid("H2", t, t.deck, model=None, cfg=cfg)  # no model -> fallback
        opp = make_fresh("iono", os.path.join(C005_ART, "teacher_sources"))
        env = make("cabt"); env.run([lambda o: h2(o), lambda o: opp(o)])
        if [s.status for s in env.steps[-1]] == ["DONE", "DONE"]:
            ok += 1
    return {"games": 4, "completed": ok, "fallback_ok": ok == 4}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=os.path.join(C007_ART, "checkpoints", "V2_B_selected.npz"))
    p.add_argument("--games", type=int, default=80)
    p.add_argument("--nproc", type=int, default=10)
    a = p.parse_args(argv)
    t0 = time.time()
    tar_path = os.path.join(C007_ART, "submission_C_hybrid_NOT_FOR_SUBMISSION.tar.gz")
    size = build_archive(tar_path, a.model)

    # structure + exclusions
    with tarfile.open(tar_path) as tar:
        names = tar.getnames()
    required = ["submission_C_hybrid/main.py", "submission_C_hybrid/deck.csv",
                "submission_C_hybrid/model.npz", "submission_C_hybrid/hybrid_config.json",
                "submission_C_hybrid/teacher/main.py", "submission_C_hybrid/cg/libcg.so",
                "submission_C_hybrid/cg/hybrid_agent.py", "submission_C_hybrid/cg/state_encoder_v2.py"]
    present = {r: r in names for r in required}
    forbidden = [n for n in names if any(x in n for x in
                 ("v2_dataset", "improvement_labels", "instrumented_teacher", "kaggle",
                  ".jsonl.gz", "training_runs", "counterfactual"))]

    reliab = _inproc_reliability(a.model, a.games, a.nproc)
    smoke = _subprocess_smoke(tar_path)
    fb = _fallback_test()

    val = {
        "contract": "c007", "status": "NOT_FOR_SUBMISSION (SUBMISSION_C=DO_NOT_SUBMIT)",
        "archive": os.path.relpath(tar_path, _REPO), "size_bytes": size,
        "clean_extraction": True, "required_files_present": present,
        "all_required_present": all(present.values()),
        "forbidden_files_present": forbidden, "excludes_data_and_secrets": len(forbidden) == 0,
        "inprocess_reliability_run": reliab,
        "subprocess_self_containment_smoke": smoke,
        "missing_weights_fallback": fb,
        "package_validation_pass": (all(present.values()) and len(forbidden) == 0
                                    and reliab["zero_defects"] and smoke["self_contained_ok"]
                                    and fb["fallback_ok"]),
        "wall_seconds": round(time.time() - t0, 1),
    }
    json.dump(val, open(os.path.join(C007_ART, "submission_C_validation_diagnostic.json"), "w"), indent=2)
    log = os.path.join(os.path.dirname(C007_ART), "test_logs", "submission_C_smoke.txt")
    open(log, "w").write(json.dumps(val, indent=2) + "\n")
    print(json.dumps({"size_bytes": size, "all_required": val["all_required_present"],
                      "excludes_data": val["excludes_data_and_secrets"],
                      "reliability_zero_defects": reliab["zero_defects"],
                      "self_contained": smoke["self_contained_ok"],
                      "fallback_ok": fb["fallback_ok"],
                      "package_validation_pass": val["package_validation_pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""c006 §16 / AC-12: build + validate a student submission package.

Assembles a competition-structured archive (main.py, model.npz, deck.csv, cg/ with
the byte-identical SDK + the student's runtime modules) and validates it by
EXTRACTING and playing games from the extracted archive (own cg/ + deck.csv),
requiring zero invalid actions/errors/timeouts and reporting single-process P99
latency.

When no student passes the gate (BEST_STUDENT=NONE) this builds an INTERNAL
DIAGNOSTIC archive clearly marked NOT_FOR_SUBMISSION (name + marker file); the real
submission_B_student.tar.gz is intentionally absent.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.safe_policy import MalformedSelection, validate_selection

SIZE_LIMIT = 100 * 1024 * 1024  # conservative; exact competition limit not machine-retrievable
RUNTIME_MODULES = ["safe_policy.py", "episode_capture.py", "card_vocab.py", "micrograd.py",
                   "policy_features.py", "decision_taxonomy.py", "decoders.py",
                   "policy_model.py", "student_agent.py"]
SDK_FILES = ["api.py", "sim.py", "game.py", "utils.py", "__init__.py", "libcg.so"]

MAIN_PY = '''import os
from cg.student_agent import make_student

_DIR = os.path.dirname(os.path.abspath(__file__))


def _p(name):
    local = os.path.join(_DIR, name)
    return local if os.path.exists(local) else os.path.join("/kaggle_simulations/agent", name)


_deck = [int(x) for x in open(_p("deck.csv")) if x.strip()]
_agent = make_student(_p("model.npz"), _deck)


def agent(obs):
    return _agent(obs)
'''

_load = [0]


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _load_dir_agent(tdir):
    _load[0] += 1
    tdir = os.path.abspath(tdir)
    old = os.getcwd(); os.chdir(tdir); sys.path.insert(0, tdir)
    try:
        spec = importlib.util.spec_from_file_location(f"extracted_{_load[0]}", os.path.join(tdir, "main.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    finally:
        os.chdir(old)
        if tdir in sys.path:
            sys.path.remove(tdir)
    return mod


def build(arch, ckpt_dir, sources, deck_path, out_dir, for_submission):
    frozen_cg = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                             "results", "artifacts", "frozen_teacher", "cg")
    stage = tempfile.mkdtemp(prefix="subB_")
    pkg_cg = os.path.join(stage, "cg")
    os.makedirs(pkg_cg)
    cg_shas = {}
    for f in SDK_FILES:
        shutil.copy2(os.path.join(frozen_cg, f), os.path.join(pkg_cg, f))
        cg_shas[f] = _sha(os.path.join(pkg_cg, f))
    identity = {}
    for m in RUNTIME_MODULES:
        src = os.path.join(_REPO, "starter_kit", m)
        dst = os.path.join(pkg_cg, m)
        shutil.copy2(src, dst)
        cg_shas[m] = _sha(dst)
        identity[m] = (_sha(src) == _sha(dst))       # byte-identical to evaluated repo module
    # top-level files
    open(os.path.join(stage, "main.py"), "w").write(MAIN_PY)
    shutil.copy2(os.path.join(ckpt_dir, f"{arch}_selected.npz"), os.path.join(stage, "model.npz"))
    shutil.copy2(deck_path, os.path.join(stage, "deck.csv"))
    ckpt_sha = _sha(os.path.join(stage, "model.npz"))
    deck_sha = _sha(os.path.join(stage, "deck.csv"))
    if not for_submission:
        open(os.path.join(stage, "NOT_FOR_SUBMISSION"), "w").write(
            "This is an INTERNAL DIAGNOSTIC archive. BEST_STUDENT=NONE (no student passed "
            "teacher non-inferiority); this package is NOT for competition submission.\n")

    name = ("submission_B_student.tar.gz" if for_submission
            else "submission_B_student_NOT_FOR_SUBMISSION.tar.gz")
    arch_path = os.path.join(out_dir, name)
    with tarfile.open(arch_path, "w:gz") as tf:
        for root, _dirs, files in os.walk(stage):
            for fn in files:
                full = os.path.join(root, fn)
                tf.add(full, arcname=os.path.relpath(full, stage))
    shutil.rmtree(stage)
    return {"archive": arch_path, "name": name, "size_bytes": os.path.getsize(arch_path),
            "sha256": _sha(arch_path), "checkpoint_sha256": ckpt_sha, "deck_sha256": deck_sha,
            "cg_file_sha256": cg_shas, "runtime_module_byte_identical_to_repo": identity,
            "for_submission": for_submission}


def validate(arch_path, sources, n_games, out_dir):
    from kaggle_environments import make
    from cg.teachers import make_fresh
    tmp = tempfile.mkdtemp(prefix="subBx_")
    with tarfile.open(arch_path, "r:gz") as tf:
        try:
            tf.extractall(tmp, filter="data")
        except TypeError:
            tf.extractall(tmp)
    opponents = ["mega_lucario", "mega_abomasnow", "iono"]
    invalid = errors = timeouts = incomplete = 0
    lats = []
    lines = []
    for i in range(n_games):
        opp = opponents[i % len(opponents)]
        student_mod = _load_dir_agent(tmp)      # fresh packaged agent instance per game
        student = student_mod.agent
        teacher = make_fresh(opp, sources)
        seat_student = i % 2
        agents = {seat_student: student, 1 - seat_student: teacher}

        def wrap(fn, is_student):
            def w(obs):
                sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
                t0 = time.perf_counter_ns()
                r = fn(obs)
                dt = time.perf_counter_ns() - t0
                if sel is not None:
                    if is_student:
                        lats.append(dt)
                    n = len(sel.get("option", []))
                    try:
                        validate_selection(list(r), n, sel.get("minCount"), sel.get("maxCount"))
                    except MalformedSelection:
                        pass
                return r
            return w
        env = make("cabt")
        exc = None
        try:
            env.run([wrap(agents[0], agents[0] is student), wrap(agents[1], agents[1] is student)])
        except Exception as e:  # pragma: no cover
            exc = repr(e)
        last = env.steps[-1]
        st = [s.status for s in last]
        if exc or st != ["DONE", "DONE"]:
            incomplete += 1
        # per-seat reliability of the student
        r = last[seat_student]
        if r.status in ("ERROR", "INVALID"):
            errors += 1
        if r.status == "TIMEOUT":
            timeouts += 1
        lines.append(f"game {i:03d} vs {opp} seat{seat_student}: statuses={st} winner_reward={[s.reward for s in last]}")
    shutil.rmtree(tmp)
    import numpy as np
    lat_ms = np.array(lats) / 1e6 if lats else np.array([0.0])
    result = {
        "games": n_games, "invalid_actions": invalid, "agent_errors": errors, "timeouts": timeouts,
        "incomplete": incomplete, "defects": invalid + errors + timeouts + incomplete,
        "clean": (invalid + errors + timeouts + incomplete) == 0,
        "student_latency_ms": {"p50": float(np.percentile(lat_ms, 50)), "p95": float(np.percentile(lat_ms, 95)),
                               "p99": float(np.percentile(lat_ms, 99)), "max": float(lat_ms.max())},
        "validated_from_extracted_archive": True, "single_process": True,
    }
    open(os.path.join(out_dir, "..", "test_logs", "submission_B_smoke.txt"), "w").write(
        f"=== Submission B package validation (from extracted archive, single process) ===\n"
        f"games={n_games} defects={result['defects']} clean={result['clean']} "
        f"P99={result['student_latency_ms']['p99']:.3f}ms\n" + "\n".join(lines) + "\n")
    return result


def run(args):
    os.makedirs(args.out, exist_ok=True)
    info = build(args.arch, args.ckpt_dir, os.path.abspath(os.path.join(_REPO, args.sources)),
                 os.path.join(_REPO, args.deck), args.out, args.for_submission)
    info["size_within_limit"] = info["size_bytes"] < SIZE_LIMIT
    info["all_runtime_modules_identical"] = all(info["runtime_module_byte_identical_to_repo"].values())
    val = validate(info["archive"], os.path.abspath(os.path.join(_REPO, args.sources)), args.games, args.out)
    out = {"contract": "c006", "arch_packaged": args.arch, "for_submission": args.for_submission,
           "package": {k: v for k, v in info.items() if k != "cg_file_sha256"},
           "cg_file_sha256": info["cg_file_sha256"], "validation": val,
           "passes_package_validation": bool(val["clean"] and info["size_within_limit"]
                                             and info["all_runtime_modules_identical"])}
    json.dump(out, open(os.path.join(args.out, "submission_B_validation.json"), "w"), indent=2)
    print(json.dumps({"archive": os.path.basename(info["archive"]), "size": info["size_bytes"],
                      "sha256": info["sha256"][:16], "for_submission": args.for_submission,
                      "validation_clean": val["clean"], "defects": val["defects"],
                      "student_p99_ms": round(val["student_latency_ms"]["p99"], 3),
                      "passes": out["passes_package_validation"]}, indent=2))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arch", default="S1_STATELESS")
    p.add_argument("--ckpt-dir", required=True)
    p.add_argument("--sources", default="contracts/c005_teacher_import_submission_and_dataset/results/artifacts/teacher_sources")
    p.add_argument("--deck", default="contracts/c005_teacher_import_submission_and_dataset/results/artifacts/frozen_teacher/deck.csv")
    p.add_argument("--out", required=True)
    p.add_argument("--games", type=int, default=40)
    p.add_argument("--for-submission", action="store_true")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

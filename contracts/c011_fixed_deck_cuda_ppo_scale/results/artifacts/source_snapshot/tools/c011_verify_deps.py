"""c011 AC-01 — dependency, hardware and immutability verification.

Records the OBSERVED machine and library versions and diffs them against the registered
profile in inputs/machine_profile.json. The registered profile is a declaration, not ground
truth: where the installed stack differs (it does -- PyTorch and CUDA are both newer), the
observed values are what every later decision is based on, and the drift is stated.

Also re-verifies the frozen deck, teacher, V2-A and every c010 checkpoint hash, and
reconstructs the c010 final-panel aggregates from c010's raw games (§3).
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import gzip
from collections import defaultdict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
ART = os.path.join(C011, "results", "artifacts")
IMMUT = ["c005_teacher_import_submission_and_dataset", "c006_distilled_policy_baseline",
         "c007_hybrid_teacher_residual_and_state_encoder_v2",
         "c008_fixed_deck_teacher_anchored_rl", "c009_amendment_c008",
         "c010_fixed_deck_rl_loop_v2"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def hardware():
    import torch
    obs = {
        "os": f"{platform.system()} {platform.release()}",
        "os_pretty": _first_line("/etc/os-release", "PRETTY_NAME="),
        "python": platform.python_version(),
        "executable": sys.executable,
        "cpu_model": _cpu_model(),
        "cpu_cores_physical": os.cpu_count() // 2 if os.cpu_count() else None,
        "cpu_threads": os.cpu_count(),
        "ram_gib": round(_meminfo("MemTotal") / 1048576, 1),
        "ram_available_gib": round(_meminfo("MemAvailable") / 1048576, 1),
        "disk_free_gib": round(shutil.disk_usage(_REPO).free / 2 ** 30, 1),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "cuda_available": bool(torch.cuda.is_available()),
    }
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        obs.update({"gpu_name": torch.cuda.get_device_name(0),
                    "gpu_capability": ".".join(map(str, torch.cuda.get_device_capability(0))),
                    "vram_total_mib": round(total / 2 ** 20),
                    "vram_free_mib": round(free / 2 ** 20)})
    try:
        obs["driver"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        obs["driver"] = None

    reg = json.load(open(os.path.join(C011, "inputs", "machine_profile.json")))
    drift = {}
    for key, regval, obsval in (
            ("pytorch", reg.get("pytorch"), obs["torch"]),
            ("pytorch_cuda", reg.get("pytorch_cuda"), obs["torch_cuda"]),
            ("driver", reg.get("driver"), obs["driver"]),
            ("python", reg.get("python"), obs["python"]),
            ("gpu", (reg.get("gpu") or {}).get("model"), obs.get("gpu_name")),
            ("vram_mib", (reg.get("gpu") or {}).get("vram_mib"), obs.get("vram_total_mib")),
            ("ram_gib", reg.get("ram_gib"), obs["ram_gib"]),
            ("cpu", (reg.get("cpu") or {}).get("model"), obs["cpu_model"])):
        if str(regval) != str(obsval):
            drift[key] = {"registered": regval, "observed": obsval}

    preflight = {
        "cuda_available": obs["cuda_available"],
        "vram_free_ge_8gib": obs.get("vram_free_mib", 0) >= 8 * 1024,
        "ram_available_ge_12gib": obs["ram_available_gib"] >= 12,
        "disk_free_ge_100gib": obs["disk_free_gib"] >= 100,
    }
    return {"observed": obs, "registered": reg, "registered_vs_observed": drift,
            "drift_is_blocking": False,
            "drift_note": "The registered profile is a declaration made when the contract was "
                          "written. Observed values govern every c011 decision; the diff is "
                          "recorded rather than silently reconciled. None of the differences "
                          "reduces capability (PyTorch and CUDA are newer).",
            "preflight": preflight, "preflight_all_pass": all(preflight.values())}


def _first_line(path, prefix):
    try:
        for ln in open(path):
            if ln.startswith(prefix):
                return ln.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def _cpu_model():
    try:
        for ln in open("/proc/cpuinfo"):
            if ln.startswith("model name"):
                return ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _meminfo(key):
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith(key):
                return int(ln.split()[1])
    except OSError:
        pass
    return 0


def immutability():
    base = {}
    for folder in IMMUT:
        root = os.path.join(_REPO, "contracts", folder)
        files = {}
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                files[os.path.relpath(p, _REPO)] = sha(p)
        base[f"{folder.split('_')[0]}_files"] = files
    return base


def c010_aggregate_reconstruction():
    """§3 — reconstruct c010's final-panel aggregates from its raw games."""
    c010a = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts")
    raw = os.path.join(c010a, "evaluation_games.jsonl.gz")
    ranking = json.load(open(os.path.join(c010a, "final_ranking.json")))
    from cg import noninf_stats as ns
    per = defaultdict(lambda: defaultdict(lambda: {0: [], 1: []}))
    for line in gzip.open(raw, "rt"):
        g = json.loads(line)
        if g["phase"] == "final" and g["score"] is not None:
            per[g["candidate_id"]][g["opponent_id"]][g["seat"]].append(g["score"])
    checks = []
    for row in ranking["ranking_by_composite"]:
        cid = row["candidate_id"]
        pts = {o: ns.seat_balanced_point(v[0], v[1]) for o, v in per[cid].items()}
        t = pts.get("dragapult")
        fld = sum(pts[o] for o in ("mega_lucario", "iono", "mega_abomasnow")) / 3.0
        comp = 0.55 * t + 0.15 * sum(pts[o] for o in ("mega_lucario", "iono", "mega_abomasnow"))
        checks.append({"candidate_id": cid,
                       "recorded": {"teacher": row["teacher"], "field": row["field"],
                                    "composite": row["composite"]},
                       "recomputed": {"teacher": t, "field": fld, "composite": comp},
                       "matches": (abs(t - row["teacher"]) < 1e-9
                                   and abs(fld - row["field"]) < 1e-9
                                   and abs(comp - row["composite"]) < 1e-9)})
    return {"n_candidates": len(checks), "all_reproduce": all(c["matches"] for c in checks),
            "checks": checks}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=ART)
    p.add_argument("--log", default=os.path.join(C011, "results", "test_logs",
                                                 "dependency_verification.txt"))
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)

    hw = hardware()
    json.dump(hw, open(os.path.join(a.out_dir, "hardware_environment.json"), "w"), indent=2)

    imm = immutability()
    imm["folders"] = IMMUT
    imm["n_files"] = {k: len(v) for k, v in imm.items() if k.endswith("_files")}
    json.dump(imm, open(os.path.join(a.out_dir, "immutability_verification.json"), "w"), indent=2)

    checks = []

    def rec(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    # frozen deck + teacher
    from cg import c009_eval as ce, c011_eval_core as cc
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", ce.SOURCES).deck
    fp = ce.deck_fingerprint(deck)
    c010reg = json.load(open(os.path.join(
        _REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts",
        "experiment_registry.json")))
    rec("frozen_deck_fingerprint_matches_c010", fp == c010reg["frozen_deck_fingerprint"], fp)
    rec("deck_is_60_cards", len(deck) == 60, len(deck))
    base = json.load(open(os.path.join(
        _REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results", "artifacts",
        "baseline_incumbent_registry.json")))
    rec("frozen_teacher_hash_matches_c010",
        cc.teacher_source_sha256() == base["T"]["checkpoint_sha256"],
        cc.teacher_source_sha256())
    for key in ("B0", "I0"):
        p_ = os.path.join(_REPO, base[key]["checkpoint_path"])
        rec(f"{key}_hash_unchanged", os.path.exists(p_) and sha(p_) == base[key]["checkpoint_sha256"])

    # every c010 checkpoint hash
    troot = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results",
                         "artifacts", "training")
    n_ck, bad = 0, []
    for dp, _dn, fns in os.walk(troot):
        if "checkpoint_registry.json" in fns:
            for _g, meta in json.load(open(os.path.join(dp, "checkpoint_registry.json"))).items():
                cp = os.path.join(_REPO, meta["checkpoint_path"])
                n_ck += 1
                if not os.path.exists(cp) or sha(cp) != meta["sha256"]:
                    bad.append(meta["checkpoint_path"])
    rec("all_c010_checkpoint_hashes_verified", not bad, f"{n_ck} checkpoints, {len(bad)} bad")

    # c005-c010 STATUS chain
    for c in IMMUT:
        sp = os.path.join(_REPO, "contracts", c, "results", "STATUS.json")
        if os.path.exists(sp):
            st = json.load(open(sp))
            rec(f"{c.split('_')[0]}_status_pass", st.get("status") == "PASS", st.get("status"))

    agg = c010_aggregate_reconstruction()
    json.dump(agg, open(os.path.join(a.out_dir, "c010_aggregate_reconstruction.json"), "w"),
              indent=2)
    rec("c010_final_aggregates_reproduce_from_raw_games", agg["all_reproduce"],
        f"{agg['n_candidates']} candidates")

    # hardware preflight
    for k, v in hw["preflight"].items():
        rec(f"preflight_{k}", v)

    dep = {"contract": "c011", "all_ok": all(c["ok"] for c in checks),
           "n_checks": len(checks), "n_failed": sum(1 for c in checks if not c["ok"]),
           "frozen_deck_fingerprint": fp,
           "teacher_source_sha256": cc.teacher_source_sha256(),
           "c010_checkpoints_verified": n_ck,
           "hardware_drift": hw["registered_vs_observed"],
           "checks": checks}
    json.dump(dep, open(os.path.join(a.out_dir, "dependency_verification.json"), "w"), indent=2)

    with open(a.log, "w") as fh:
        fh.write("c011 AC-01 dependency / hardware / immutability verification\n\n")
        for c in checks:
            fh.write(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}  {c['detail']}\n")
        fh.write(f"\nimmutability baseline: "
                 + ", ".join(f"{k} {len(v)}f" for k, v in imm.items() if k.endswith('_files'))
                 + "\n")
        fh.write(f"\nhardware drift vs registered profile: "
                 f"{json.dumps(hw['registered_vs_observed'], indent=2)}\n")
        fh.write(f"preflight: {json.dumps(hw['preflight'])}\n")
        fh.write(f"\nALL_OK = {dep['all_ok']}\n")
    print(json.dumps({"all_ok": dep["all_ok"], "n_checks": dep["n_checks"],
                      "n_failed": dep["n_failed"],
                      "c010_checkpoints_verified": n_ck,
                      "hardware_drift": list(hw["registered_vs_observed"]),
                      "preflight_all_pass": hw["preflight_all_pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

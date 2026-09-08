"""c012 AC-01/AC-03 — dependency + immutability verification, and the frozen c011 candidate
registry with the list of candidates still needing a confirmation panel (§11).

§11 requires the registry to contain all confirmed finalists, all unconfirmed late
checkpoints, every screen-nominated or near-nominated checkpoint, S611/S622/S633 final
policies, and the c010 incumbent. Membership is resolved from c011's own registries and raw
games -- never inferred from a filename (§3).
"""

import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C012 = os.path.join(_REPO, "contracts",
                    "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART = os.path.join(C012, "results", "artifacts")
LOGD = os.path.join(C012, "results", "test_logs")
C011A = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale", "results", "artifacts")
IMMUT = ["c005_teacher_import_submission_and_dataset", "c006_distilled_policy_baseline",
         "c007_hybrid_teacher_residual_and_state_encoder_v2",
         "c008_fixed_deck_teacher_anchored_rl", "c009_amendment_c008",
         "c010_fixed_deck_rl_loop_v2", "c011_fixed_deck_cuda_ppo_scale"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def machine():
    import torch
    obs = {"os": _first("/etc/os-release", "PRETTY_NAME="), "python": platform.python_version(),
           "cpu": _cpu(), "cpu_threads": os.cpu_count(),
           "ram_gib": round(_mem("MemTotal") / 1048576, 1),
           "ram_available_gib": round(_mem("MemAvailable") / 1048576, 1),
           "disk_free_gib": round(shutil.disk_usage(_REPO).free / 2 ** 30, 1),
           "torch": torch.__version__, "torch_cuda": torch.version.cuda,
           "cuda_available": bool(torch.cuda.is_available())}
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        obs.update({"gpu": torch.cuda.get_device_name(0),
                    "vram_total_mib": round(total / 2 ** 20),
                    "vram_free_mib": round(free / 2 ** 20)})
    try:
        obs["driver"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        obs["driver"] = None
    return obs


def _first(path, pref):
    try:
        for ln in open(path):
            if ln.startswith(pref):
                return ln.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def _cpu():
    try:
        for ln in open("/proc/cpuinfo"):
            if ln.startswith("model name"):
                return ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _mem(key):
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith(key):
                return int(ln.split()[1])
    except OSError:
        pass
    return 0


def build_registry():
    """§11 frozen c011 candidate registry + which candidates still need confirmation."""
    import c012_eval as ev
    reg = ev.build_candidate_registry()
    c011_games = [json.loads(l) for l in
                  gzip.open(os.path.join(C011A, "evaluation_games.jsonl.gz"), "rt")]
    have_conf = {g["candidate_id"] for g in c011_games if g["phase"] == "confirmation"}
    have_screen = {g["candidate_id"] for g in c011_games if g["phase"] == "screen"}
    c010_games_p = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2", "results",
                                "artifacts", "evaluation_games.jsonl.gz")
    if os.path.exists(c010_games_p):
        for l in gzip.open(c010_games_p, "rt"):
            g = json.loads(l)
            if g["phase"] == "confirmation":
                have_conf.add(g["candidate_id"])
    noms = json.load(open(os.path.join(C011A, "screening_nominations.json")))["nominated"]
    bas = json.load(open(os.path.join(C011A, "best_agent_selection.json")))
    inc011 = json.load(open(os.path.join(C011A, "c010_repaired_incumbent.json")))["incumbent_id"]

    # branch budgets for the "late checkpoint" test, from observed final counts
    budgets = defaultdict(int)
    for cid, m in reg.items():
        if m.get("arm") == "S":
            budgets[m["seed"]] = max(budgets[m["seed"]], m["training_games"] or 0)

    members, need = {}, []
    for cid, m in reg.items():
        if cid == "T_teacher":
            continue
        arm = m.get("arm")
        seed = m.get("seed")
        games = m.get("training_games") or 0
        late = bool(arm == "S" and budgets[seed] and games >= 0.75 * budgets[seed])
        reasons = []
        if cid in bas.get("finalists", []):
            reasons.append("c011 finalist")
        if cid == inc011:
            reasons.append("c010/c011 incumbent")
        if cid in noms:
            reasons.append("c011 screen-nominated")
        if arm == "S" and late:
            reasons.append("late c011 checkpoint (>=75% of branch)")
        if arm == "S" and games == budgets[seed]:
            reasons.append("S611/S622/S633 final policy")
        if cid in have_screen and cid not in noms:
            reasons.append("screened but not nominated (near-nominated)")
        if not reasons:
            continue
        members[cid] = {**m, "membership_reasons": reasons,
                        "already_confirmed": cid in have_conf,
                        "needs_c012_confirmation": cid not in have_conf}
        if cid not in have_conf:
            need.append(cid)
    return reg, members, sorted(need)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all", choices=["deps", "registry", "all"])
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    checks = []

    def rec(n, ok, d=""):
        checks.append({"check": n, "ok": bool(ok), "detail": str(d)[:300]})

    mach = machine()
    imm = {}
    for folder in IMMUT:
        root = os.path.join(_REPO, "contracts", folder)
        files = {}
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                fp = os.path.join(dp, fn)
                files[os.path.relpath(fp, _REPO)] = sha(fp)
        imm[f"{folder.split('_')[0]}_files"] = files
    imm["folders"] = IMMUT
    imm["counts"] = {k: len(v) for k, v in imm.items() if k.endswith("_files")}
    json.dump(imm, open(os.path.join(ART, "immutability_verification.json"), "w"), indent=2)

    from cg import c009_eval as ce, c011_eval_core as cc
    from cg.teachers import make_fresh
    deck = make_fresh("dragapult", ce.SOURCES).deck
    fp = ce.deck_fingerprint(deck)
    c011reg = json.load(open(os.path.join(C011A, "evaluation_candidate_registry.json")))
    c010exp = json.load(open(os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2",
                                          "results", "artifacts", "experiment_registry.json")))
    rec("frozen_deck_fingerprint_matches_c010_c011", fp == c010exp["frozen_deck_fingerprint"], fp)
    rec("deck_is_60_cards", len(deck) == 60, len(deck))
    rec("frozen_teacher_hash_matches",
        cc.teacher_source_sha256() == c011reg["T_teacher"]["checkpoint_sha256"])

    bad = []
    n_ck = 0
    for cid, m in c011reg.items():
        if cid == "T_teacher":
            continue
        p_ = os.path.join(_REPO, m["checkpoint_path"])
        n_ck += 1
        if not os.path.exists(p_) or sha(p_) != m["checkpoint_sha256"]:
            bad.append(cid)
    rec("all_c011_candidate_checkpoint_hashes_verified", not bad, f"{n_ck} checkpoints, {len(bad)} bad")

    # c011 raw final games reproduce its recorded final matrix (§3)
    from cg import noninf_stats as ns
    fin = defaultdict(lambda: defaultdict(lambda: {0: [], 1: []}))
    for l in gzip.open(os.path.join(C011A, "evaluation_games.jsonl.gz"), "rt"):
        g = json.loads(l)
        if g["phase"] == "final" and g["score"] is not None:
            fin[g["candidate_id"]][g["opponent_id"]][g["seat"]].append(g["score"])
    rank = json.load(open(os.path.join(C011A, "final_ranking.json")))["ranking_by_composite"]
    mism = []
    for r in rank:
        cid = r["candidate_id"]
        pts = {o: ns.seat_balanced_point(v[0], v[1]) for o, v in fin[cid].items()}
        if r["teacher"] is not None and abs(pts.get("dragapult", -9) - r["teacher"]) > 1e-9:
            mism.append(f"{cid}:teacher")
        f3 = sum(pts[o] for o in ("mega_lucario", "iono", "mega_abomasnow")) / 3
        if abs(f3 - r["field"]) > 1e-9:
            mism.append(f"{cid}:field")
    rec("c011_final_matrix_reproduces_from_raw_games", not mism, mism[:4])

    for c in IMMUT:
        sp = os.path.join(_REPO, "contracts", c, "results", "STATUS.json")
        if os.path.exists(sp):
            st = json.load(open(sp))
            rec(f"{c.split('_')[0]}_status_pass", st.get("status") == "PASS", st.get("status"))

    rec("cuda_available", mach["cuda_available"])
    rec("vram_free_ge_8gib", (mach.get("vram_free_mib") or 0) >= 8 * 1024, mach.get("vram_free_mib"))
    rec("disk_free_ge_100gib", mach["disk_free_gib"] >= 100, mach["disk_free_gib"])
    rec("ram_available_ge_12gib", mach["ram_available_gib"] >= 12, mach["ram_available_gib"])

    dep = {"contract": "c012", "all_ok": all(c["ok"] for c in checks), "n_checks": len(checks),
           "n_failed": sum(1 for c in checks if not c["ok"]),
           "frozen_deck_fingerprint": fp,
           "teacher_source_sha256": cc.teacher_source_sha256(),
           "c011_checkpoints_verified": n_ck,
           "machine": mach,
           "final_commits": {c: _commit_for(c) for c in IMMUT},
           "checks": checks}
    json.dump(dep, open(os.path.join(ART, "dependency_verification.json"), "w"), indent=2)

    reg, members, need = build_registry()
    json.dump({"note": "§11 frozen c011 candidate registry. Membership resolved from c011 "
                       "registries, nominations, finalists and raw games -- never from a "
                       "filename.",
               "n_candidates": len(members), "n_needing_confirmation": len(need),
               "needs_confirmation": need,
               "candidates": members},
              open(os.path.join(ART, "c011_candidate_registry.json"), "w"), indent=2)

    with open(os.path.join(LOGD, "dependency_verification.txt"), "w") as fh:
        fh.write("c012 AC-01 dependency / immutability verification\n\n")
        for c in checks:
            fh.write(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}  {c['detail']}\n")
        fh.write(f"\nimmutability baseline: {imm['counts']}\n")
        fh.write(f"machine: {json.dumps(mach)}\n\nALL_OK = {dep['all_ok']}\n")
    with open(os.path.join(LOGD, "c011_checkpoint_confirmation.txt"), "w") as fh:
        fh.write(f"c012 §11 candidate registry: {len(members)} candidates, "
                 f"{len(need)} need a c012 confirmation panel\n")
        for cid, m in sorted(members.items()):
            fh.write(f"  {cid:20s} conf={m['already_confirmed']} "
                     f"reasons={'; '.join(m['membership_reasons'])}\n")
    print(json.dumps({"all_ok": dep["all_ok"], "n_checks": dep["n_checks"],
                      "n_failed": dep["n_failed"],
                      "c011_checkpoints_verified": n_ck,
                      "registry_candidates": len(members),
                      "needs_confirmation": need}, indent=2))
    return 0


def _commit_for(folder):
    out = subprocess.run(["git", "-C", _REPO, "log", "-1", "--format=%H", "--",
                          f"contracts/{folder}"], capture_output=True, text=True).stdout.strip()
    return out or None


if __name__ == "__main__":
    sys.exit(main())

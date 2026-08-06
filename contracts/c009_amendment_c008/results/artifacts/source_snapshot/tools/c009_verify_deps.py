"""c009 AC-01: dependency + immutability verification for the c008 amendment.

Verifies the c005->c006->c007->c008 chain, the frozen teacher/deck, the untouched c007
V2-A checkpoint (B0), every c008 validation-selected checkpoint, and that the c008 source
and result artifacts needed for the repair are readable. Snapshots a full recursive sha256
tree of ALL FOUR immutable contract folders so AC-16 can prove nothing changed during c009.

Read-only with respect to c005/c006/c007/c008.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = {n: os.path.join(_REPO, "contracts", d) for n, d in {
    "c005": "c005_teacher_import_submission_and_dataset",
    "c006": "c006_distilled_policy_baseline",
    "c007": "c007_hybrid_teacher_residual_and_state_encoder_v2",
    "c008": "c008_fixed_deck_teacher_anchored_rl",
    "c009": "c009_amendment_c008",
}.items()}
ART = {n: os.path.join(p, "results", "artifacts") for n, p in C.items()}

FINAL = {"c005": "4137d983c6a05c0eea8332718d3e7f3acc7b7830",
         "c006": "08ebac88385444a69d0615b7976dea9dbddeb79a",
         "c007": "1f3fc63aaa36be0a45ffce8481c563c89ffa0577",
         "c008": "fb6e592c8c333f758014e2d2e94a39261bb63fe6"}
TEACHER_REF = "54948560"
DECK_ID = "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab"
V2A = os.path.join(ART["c007"], "checkpoints", "V2_A_selected.npz")

# c008 source + artifacts the repair depends on being readable
C008_REQUIRED = ["checkpoint_selection.json", "checkpoint_registry.json",
                 "rl_strategic_games.jsonl.gz", "rl_teacher_noninferiority.json",
                 "rl_matchup_matrix.csv", "training_curves.json"]
C008_SOURCE = [os.path.join(_REPO, "tools", "c008_final_eval.py"),
               os.path.join(_REPO, "tools", "train_rl.py"),
               os.path.join(_REPO, "starter_kit", "rl_policy.py"),
               os.path.join(_REPO, "starter_kit", "rl_env.py")]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*a):
    return subprocess.run(["git", "-C", _REPO, *a], capture_output=True, text=True)


def _tree(root):
    out = {}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            try:
                out[os.path.relpath(p, _REPO)] = sha256_file(p)
            except OSError:
                out[os.path.relpath(p, _REPO)] = "UNREADABLE"
    return dict(sorted(out.items()))


def verify():
    checks = []

    def rec(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # 1. chain of accepted contracts
    st = {}
    for n in ("c005", "c006", "c007", "c008"):
        st[n] = json.load(open(os.path.join(C[n], "results", "STATUS.json")))
        rec(f"{n}_status_and_head", st[n].get("status") == "PASS" and st[n].get("final_head") == FINAL[n],
            {"status": st[n].get("status"), "final_head": st[n].get("final_head")})
    rec("commit_chain", (st["c006"].get("initial_head") == FINAL["c005"]
                         and st["c007"].get("initial_head") == FINAL["c006"]
                         and st["c008"].get("initial_head") == FINAL["c007"]),
        {n: st[n].get("initial_head") for n in ("c006", "c007", "c008")})
    head = _git("rev-parse", "HEAD").stdout.strip()
    rec("c009_branches_from_c008_final",
        head == FINAL["c008"] or _git("merge-base", "--is-ancestor", FINAL["c008"], "HEAD").returncode == 0,
        {"c009_head": head})

    # 2. frozen teacher + deck
    fm = json.load(open(os.path.join(ART["c005"], "frozen_teacher_manifest.json")))
    ft = os.path.join(ART["c005"], "frozen_teacher")
    main_sha = sha256_file(os.path.join(ft, "main.py"))
    deck_sha = sha256_file(os.path.join(ft, "deck.csv"))
    rec("frozen_teacher_main_sha", main_sha == fm["main_sha256"], main_sha)
    rec("frozen_teacher_deck_sha", deck_sha == fm["deck_sha256"], deck_sha)
    rec("frozen_deck_id", fm["frozen_deck_id"] == DECK_ID, fm["frozen_deck_id"])

    # 3. B0 = untouched c007 V2-A
    v2a_sha = sha256_file(V2A) if os.path.exists(V2A) else None
    rec("v2a_baseline_checkpoint_present", v2a_sha is not None,
        {"path": os.path.relpath(V2A, _REPO), "sha256": v2a_sha})

    # 4. every c008 validation-selected checkpoint
    sel = json.load(open(os.path.join(ART["c008"], "checkpoint_selection.json")))
    ck = {}
    missing = []
    for key, v in sorted(sel["per_seed"].items()):
        p = v["selected_checkpoint"]
        ap = os.path.join(_REPO, p)
        if p and os.path.exists(ap):
            ck[key] = {"path": p, "sha256": sha256_file(ap), "size": os.path.getsize(ap),
                       "validation_blend": v["validation_blend"], "games": v["games"]}
        else:
            missing.append(key)
    rec("all_c008_selected_checkpoints_present", not missing,
        {"n_present": len(ck), "missing": missing})
    rec("checkpoint_hashes_distinct", len({c["sha256"] for c in ck.values()}) == len(ck),
        {"n_distinct": len({c["sha256"] for c in ck.values()})})

    # 5. c008 artifacts + source readable (needed for defect reproduction)
    unreadable = [f for f in C008_REQUIRED if not os.path.isfile(os.path.join(ART["c008"], f))]
    rec("c008_required_artifacts_readable", not unreadable, {"missing": unreadable})
    src_missing = [os.path.relpath(p, _REPO) for p in C008_SOURCE if not os.path.isfile(p)]
    rec("c008_source_readable", not src_missing, {"missing": src_missing})

    # 6. teacher submission ref from the c009 input
    ctx = json.load(open(os.path.join(C["c009"], "inputs", "c008_known_findings.json")))
    rec("teacher_submission_ref", ctx.get("teacher_submission_ref") == TEACHER_REF,
        ctx.get("teacher_submission_ref"))

    # 7. opponents (incl. held-out abomasnow) present
    src = os.path.join(ART["c005"], "teacher_sources")
    present = {c: os.path.isfile(os.path.join(src, c, "main.py"))
               for c in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")}
    rec("strategic_opponents_present", all(present.values()), present)

    # 8. runtime
    dep = {}
    for m in ("numpy", "scipy", "kaggle_environments", "cg"):
        try:
            __import__(m); dep[m] = "ok"
        except Exception as e:  # noqa: BLE001
            dep[m] = f"MISSING:{type(e).__name__}"
    rec("runtime_deps", dep["numpy"] == "ok" and dep["cg"] == "ok", dep)

    return {
        "contract": "c009_amendment_c008",
        "chain_final_heads": FINAL, "c009_initial_head": head,
        "teacher_id": fm["teacher_id"], "frozen_deck_id": fm["frozen_deck_id"],
        "frozen_teacher_main_sha256": main_sha, "frozen_teacher_deck_sha256": deck_sha,
        "v2a_baseline": {"path": os.path.relpath(V2A, _REPO), "sha256": v2a_sha},
        "c008_selected_checkpoints": ck,
        "teacher_submission_ref": TEACHER_REF, "runtime_deps": dep,
        "checks": checks, "all_ok": all(c["ok"] for c in checks),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    dep = verify()
    trees = {n: _tree(C[n]) for n in ("c005", "c006", "c007", "c008")}
    imm = {"note": "Baseline sha256 tree of the four immutable contract folders at c009 start; "
                   "AC-16/AC-12 re-hash and diff to prove nothing changed.",
           "final_heads": FINAL}
    for n, t in trees.items():
        imm[f"{n}_file_count"] = len(t)
        imm[f"{n}_tree_sha256"] = hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest()
        imm[f"{n}_files"] = t
    json.dump(dep, open(os.path.join(a.out_dir, "dependency_verification.json"), "w"), indent=2)
    json.dump(imm, open(os.path.join(a.out_dir, "immutability_verification.json"), "w"), indent=2)

    lines = ["c009 AC-01 dependency + immutability", "=" * 55,
             "chain: " + " -> ".join(f"{n} {FINAL[n][:12]}" for n in ("c005", "c006", "c007", "c008"))
             + f" -> c009 init {dep['c009_initial_head'][:12]}",
             f"teacher {dep['teacher_id']} | deck {dep['frozen_deck_id']} | ref {dep['teacher_submission_ref']}",
             f"B0 (untouched V2-A) sha256 {dep['v2a_baseline']['sha256']}",
             f"c008 selected checkpoints: {len(dep['c008_selected_checkpoints'])}", ""]
    for c in dep["checks"]:
        lines.append(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}")
    lines.append("")
    lines.append("immutability baseline: " + ", ".join(
        f"{n} {imm[f'{n}_file_count']}f" for n in ("c005", "c006", "c007", "c008")))
    lines.append(f"ALL_OK = {dep['all_ok']}")
    open(a.log, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if dep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

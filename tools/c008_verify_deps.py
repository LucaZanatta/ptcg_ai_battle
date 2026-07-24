"""c008 AC-01: dependency + immutability + baseline verification.

Verifies the c005 + c006 + c007 frozen dependency chain WITHOUT mutating any earlier
contract file: recomputes the frozen teacher/deck, the c007 selected V2-A checkpoint,
the c007 v2 dataset splits, and the c007 encoder schema hashes; checks the commit chain
and teacher submission ref; snapshots a full recursive sha256 tree of all three immutable
contract folders so AC-16 can prove nothing changed. Read-only w.r.t. c005/c006/c007.
"""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C005 = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset")
C006 = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline")
C007 = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2")
C008 = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl")
C005_ART, C006_ART, C007_ART = (os.path.join(c, "results", "artifacts") for c in (C005, C006, C007))

C005_FINAL = "4137d983c6a05c0eea8332718d3e7f3acc7b7830"
C006_FINAL = "08ebac88385444a69d0615b7976dea9dbddeb79a"
C007_FINAL = "1f3fc63aaa36be0a45ffce8481c563c89ffa0577"
TEACHER_REF = "54948560"
FROZEN_DECK_ID = "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab"


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

    s5 = json.load(open(os.path.join(C005, "results", "STATUS.json")))
    s6 = json.load(open(os.path.join(C006, "results", "STATUS.json")))
    s7 = json.load(open(os.path.join(C007, "results", "STATUS.json")))
    rec("c005_pass_head", s5.get("status") == "PASS" and s5.get("final_head") == C005_FINAL, s5.get("final_head"))
    rec("c006_pass_head", s6.get("status") == "PASS" and s6.get("final_head") == C006_FINAL, s6.get("final_head"))
    rec("c007_pass_head", s7.get("status") == "PASS" and s7.get("final_head") == C007_FINAL, s7.get("final_head"))
    rec("commit_chain", s6.get("initial_head") == C005_FINAL and s7.get("initial_head") == C006_FINAL,
        {"c006_init": s6.get("initial_head"), "c007_init": s7.get("initial_head")})
    head = _git("rev-parse", "HEAD").stdout.strip()
    rec("c008_branches_from_c007_final",
        head == C007_FINAL or _git("merge-base", "--is-ancestor", C007_FINAL, "HEAD").returncode == 0,
        {"c008_head": head})

    # frozen teacher + deck
    fm = json.load(open(os.path.join(C005_ART, "frozen_teacher_manifest.json")))
    ft = os.path.join(C005_ART, "frozen_teacher")
    main_sha = sha256_file(os.path.join(ft, "main.py"))
    deck_sha = sha256_file(os.path.join(ft, "deck.csv"))
    rec("frozen_teacher_main_sha", main_sha == fm["main_sha256"], main_sha)
    rec("frozen_teacher_deck_sha", deck_sha == fm["deck_sha256"], deck_sha)
    rec("frozen_deck_id", fm["frozen_deck_id"] == FROZEN_DECK_ID, fm["frozen_deck_id"])

    # c007 selected V2-A checkpoint
    v2a = os.path.join(C007_ART, "checkpoints", "V2_A_selected.npz")
    v2a_sha = sha256_file(v2a)
    rec("c007_v2a_checkpoint_present", os.path.exists(v2a), {"sha256": v2a_sha, "size": os.path.getsize(v2a)})

    # c007 v2 dataset splits
    ds = os.path.join(C007_ART, "v2_dataset")
    ds_sha = {sp: sha256_file(os.path.join(ds, f"{sp}.jsonl.gz")) for sp in ("train", "validation", "test")}
    # split integrity: no game in two splits
    game_split = {}
    for sp in ("train", "validation", "test"):
        with gzip.open(os.path.join(ds, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                game_split.setdefault(json.loads(line)["game_id"], set()).add(sp)
    leak = {g: sorted(s) for g, s in game_split.items() if len(s) > 1}
    rec("c007_dataset_no_leakage", len(leak) == 0, {"leaking": leak})

    # c007 encoder schema
    enc_schema = os.path.join(C007_ART, "state_encoder_v2_schema.json")
    rec("c007_encoder_schema_present", os.path.exists(enc_schema), sha256_file(enc_schema))

    # teacher submission ref
    base = json.load(open(os.path.join(C008, "inputs", "c008_context.json")))
    rec("teacher_submission_ref", base.get("teacher_submission_ref") == TEACHER_REF, base.get("teacher_submission_ref"))

    # teacher sources present (opponents + held-out abomasnow)
    src = os.path.join(C005_ART, "teacher_sources")
    present = {c: os.path.isfile(os.path.join(src, c, "main.py"))
               for c in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")}
    rec("teacher_sources_present", all(present.values()), present)

    # runtime deps (torch-free by design)
    dep_status = {}
    for m in ("numpy", "scipy", "kaggle_environments", "cg"):
        try:
            __import__(m); dep_status[m] = "ok"
        except Exception as e:  # noqa: BLE001
            dep_status[m] = f"MISSING:{type(e).__name__}"
    rec("runtime_deps", dep_status["numpy"] == "ok" and dep_status["cg"] == "ok", dep_status)

    return {
        "contract": "c008_fixed_deck_teacher_anchored_rl",
        "c005_final_head": C005_FINAL, "c006_final_head": C006_FINAL, "c007_final_head": C007_FINAL,
        "c008_initial_head": head, "teacher_id": fm["teacher_id"], "frozen_deck_id": fm["frozen_deck_id"],
        "frozen_teacher_main_sha256": main_sha, "frozen_teacher_deck_sha256": deck_sha,
        "v2a_checkpoint_sha256": v2a_sha, "c007_dataset_sha256": ds_sha,
        "teacher_submission_ref": TEACHER_REF, "runtime_deps": dep_status,
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
    c5, c6, c7 = _tree(C005), _tree(C006), _tree(C007)
    imm = {
        "note": "Baseline sha256 tree of immutable c005/c006/c007 folders at c008 start; AC-16 re-hashes and diffs.",
        "c005_final_head": C005_FINAL, "c006_final_head": C006_FINAL, "c007_final_head": C007_FINAL,
        "c005_file_count": len(c5), "c006_file_count": len(c6), "c007_file_count": len(c7),
        "c005_tree_sha256": hashlib.sha256(json.dumps(c5, sort_keys=True).encode()).hexdigest(),
        "c006_tree_sha256": hashlib.sha256(json.dumps(c6, sort_keys=True).encode()).hexdigest(),
        "c007_tree_sha256": hashlib.sha256(json.dumps(c7, sort_keys=True).encode()).hexdigest(),
        "c005_files": c5, "c006_files": c6, "c007_files": c7,
    }
    json.dump(dep, open(os.path.join(a.out_dir, "dependency_verification.json"), "w"), indent=2)
    json.dump(imm, open(os.path.join(a.out_dir, "immutability_verification.json"), "w"), indent=2)
    lines = ["c008 AC-01 dependency + immutability", "=" * 50,
             f"chain c005 {C005_FINAL[:12]} -> c006 {C006_FINAL[:12]} -> c007 {C007_FINAL[:12]} -> c008 init {dep['c008_initial_head'][:12]}",
             f"teacher {dep['teacher_id']} deck {dep['frozen_deck_id']}  ref {dep['teacher_submission_ref']}", ""]
    for c in dep["checks"]:
        lines.append(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}")
    lines.append(f"\nimmutability baseline: c005 {imm['c005_file_count']}f c006 {imm['c006_file_count']}f c007 {imm['c007_file_count']}f")
    lines.append(f"ALL_OK = {dep['all_ok']}")
    open(a.log, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if dep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

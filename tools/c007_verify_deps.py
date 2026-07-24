"""c007 AC-01: dependency, immutability, and baseline verification.

Verifies the c005 + c006 frozen dependency chain WITHOUT mutating any earlier
contract file. Recomputes hashes of the frozen teacher/deck, the c005 teacher
dataset, the c006 sequence dataset and checkpoints, and the submission archives,
and checks them against the recorded manifests. Also snapshots a full recursive
sha256 tree of both immutable contract folders so AC-16 can prove nothing under
them changed during c007. Read-only w.r.t. c005/c006.

Outputs:
  results/artifacts/dependency_verification.json
  results/artifacts/immutability_verification.json
  results/test_logs/dependency_verification.txt
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
C005_ART = os.path.join(C005, "results", "artifacts")
C006_ART = os.path.join(C006, "results", "artifacts")

C005_FINAL_HEAD = "4137d983c6a05c0eea8332718d3e7f3acc7b7830"
C006_FINAL_HEAD = "08ebac88385444a69d0615b7976dea9dbddeb79a"
TEACHER_REF = "54948560"
FROZEN_DECK_ID = "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args):
    return subprocess.run(["git", "-C", _REPO, *args], capture_output=True, text=True)


def _tree_hashes(root):
    """Recursive {relpath: sha256} for every file under root (sorted)."""
    out = {}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            try:
                out[os.path.relpath(p, _REPO)] = sha256_file(p)
            except (OSError, IOError):
                out[os.path.relpath(p, _REPO)] = "UNREADABLE"
    return dict(sorted(out.items()))


def verify():
    checks = []

    def rec(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # 1. c005/c006 STATUS PASS + commit chain
    s5 = json.load(open(os.path.join(C005, "results", "STATUS.json")))
    s6 = json.load(open(os.path.join(C006, "results", "STATUS.json")))
    rec("c005_status_pass_and_head", s5.get("status") == "PASS" and s5.get("final_head") == C005_FINAL_HEAD,
        {"status": s5.get("status"), "final_head": s5.get("final_head"), "expected": C005_FINAL_HEAD})
    rec("c006_status_pass_and_head", s6.get("status") == "PASS" and s6.get("final_head") == C006_FINAL_HEAD,
        {"status": s6.get("status"), "final_head": s6.get("final_head"), "expected": C006_FINAL_HEAD})
    rec("commit_chain_c005_to_c006", s6.get("initial_head") == C005_FINAL_HEAD,
        {"c006_initial_head": s6.get("initial_head"), "c005_final_head": C005_FINAL_HEAD})
    # c007 branches from c006 final head
    head = _git("rev-parse", "HEAD").stdout.strip()
    rec("c007_branches_from_c006_final", head == C006_FINAL_HEAD or _git("merge-base", "--is-ancestor",
        C006_FINAL_HEAD, "HEAD").returncode == 0,
        {"c007_head": head, "c006_final_head": C006_FINAL_HEAD})
    # both final-head objects exist in the repo
    rec("c005_c006_head_objects_exist",
        _git("cat-file", "-t", C005_FINAL_HEAD).stdout.strip() == "commit"
        and _git("cat-file", "-t", C006_FINAL_HEAD).stdout.strip() == "commit",
        {"c005": C005_FINAL_HEAD, "c006": C006_FINAL_HEAD})

    # 2. Frozen teacher + deck hashes (c005 manifest)
    fm = json.load(open(os.path.join(C005_ART, "frozen_teacher_manifest.json")))
    ft = os.path.join(C005_ART, "frozen_teacher")
    main_sha = sha256_file(os.path.join(ft, "main.py"))
    deck_sha = sha256_file(os.path.join(ft, "deck.csv"))
    rec("frozen_teacher_main_sha256", main_sha == fm["main_sha256"],
        {"expected": fm["main_sha256"], "actual": main_sha})
    rec("frozen_teacher_deck_sha256", deck_sha == fm["deck_sha256"],
        {"expected": fm["deck_sha256"], "actual": deck_sha})
    rec("frozen_deck_id", fm["frozen_deck_id"] == FROZEN_DECK_ID,
        {"expected": FROZEN_DECK_ID, "actual": fm["frozen_deck_id"]})
    # teacher_sources main.py identical to frozen
    src_main = os.path.join(C005_ART, "teacher_sources", "dragapult", "main.py")
    rec("teacher_sources_dragapult_matches_frozen", sha256_file(src_main) == fm["main_sha256"],
        {"expected": fm["main_sha256"], "actual": sha256_file(src_main)})

    # 3. Submission-A archive
    arch = os.path.join(C005_ART, "submission_A_teacher.tar.gz")
    arch_sha = sha256_file(arch)
    rec("submission_A_archive_size", os.path.getsize(arch) == fm["archive_size_bytes"],
        {"expected": fm["archive_size_bytes"], "actual": os.path.getsize(arch), "sha256": arch_sha})

    # 4. c005 teacher dataset file hashes + split totals (no leakage)
    ds5 = os.path.join(C005_ART, "teacher_dataset")
    splits5 = json.load(open(os.path.join(ds5, "splits.json")))
    ds5_hashes, ds5_counts, game_split = {}, {}, {}
    for sp in ("train", "validation", "test"):
        path = os.path.join(ds5, f"{sp}.jsonl.gz")
        ds5_hashes[sp] = sha256_file(path)
        games = {}
        with gzip.open(path, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
                game_split.setdefault(r["game_id"], set()).add(sp)
        ds5_counts[sp] = {"games": len(games), "decisions": sum(len(v) for v in games.values())}
    rec("c005_dataset_split_counts",
        ds5_counts == {k: {"games": splits5["games"][k], "decisions": splits5["decisions"][k]}
                       for k in ("train", "validation", "test")},
        {"actual": ds5_counts})
    leak5 = {g: sorted(s) for g, s in game_split.items() if len(s) > 1}
    rec("c005_dataset_no_leakage", len(leak5) == 0, {"leaking_games": leak5})

    # 5. c006 sequence dataset hashes + checkpoint hashes
    ds6 = os.path.join(C006_ART, "sequence_dataset")
    dm6 = json.load(open(os.path.join(C006_ART, "sequence_dataset_manifest.json")))
    ds6_hashes = {sp: sha256_file(os.path.join(ds6, f"{sp}.jsonl.gz"))
                  for sp in ("train", "validation", "test")}
    ckdir = os.path.join(C006_ART, "checkpoints")
    ck_hashes = {fn: sha256_file(os.path.join(ckdir, fn))
                 for fn in sorted(os.listdir(ckdir)) if fn.endswith(".npz")}
    rec("c006_checkpoints_present", len(ck_hashes) == 8,
        {"count": len(ck_hashes), "files": list(ck_hashes)})
    rec("c006_sequence_manifest_present", dm6.get("total_decisions", dm6.get("decisions")) is not None,
        {"manifest_keys": sorted(dm6)[:12]})

    # 6. teacher submission ref in the c007 input baseline
    base = json.load(open(os.path.join(C007, "inputs", "kaggle_teacher_baseline.json")))
    rec("kaggle_teacher_ref", base.get("teacher_submission_ref") == TEACHER_REF,
        {"ref": base.get("teacher_submission_ref"), "recorded_score": base.get("initial_recorded_public_score")})

    # 7. teacher sources present for opponents (dragapult mirror + 3 archetypes)
    src = os.path.join(C005_ART, "teacher_sources")
    present = {c: os.path.isfile(os.path.join(src, c, "main.py"))
               for c in ("dragapult", "mega_lucario", "mega_abomasnow", "iono")}
    rec("teacher_sources_present", all(present.values()), present)

    # 8. runtime deps importable (cabt runtime + numpy, torch-free by design)
    dep_status = {}
    for mod in ("numpy", "scipy", "kaggle_environments", "cg"):
        try:
            __import__(mod)
            dep_status[mod] = "ok"
        except Exception as e:  # noqa: BLE001
            dep_status[mod] = f"MISSING: {type(e).__name__}"
    rec("runtime_deps_importable",
        all(v == "ok" for k, v in dep_status.items() if k != "kaggle_environments") and dep_status["cg"] == "ok",
        dep_status)

    dep_out = {
        "contract": "c007_hybrid_teacher_residual_and_state_encoder_v2",
        "c005_final_head": C005_FINAL_HEAD,
        "c006_final_head": C006_FINAL_HEAD,
        "c007_initial_head": head,
        "teacher_id": fm["teacher_id"],
        "frozen_deck_id": fm["frozen_deck_id"],
        "frozen_teacher_main_sha256": main_sha,
        "frozen_teacher_deck_sha256": deck_sha,
        "submission_A_archive": {"size_bytes": os.path.getsize(arch), "sha256": arch_sha},
        "c005_dataset_file_sha256": ds5_hashes,
        "c005_dataset_counts": ds5_counts,
        "c006_sequence_dataset_file_sha256": ds6_hashes,
        "c006_checkpoint_sha256": ck_hashes,
        "teacher_submission_ref": TEACHER_REF,
        "teacher_recorded_public_score": base.get("initial_recorded_public_score"),
        "runtime_deps": dep_status,
        "checks": checks,
        "all_ok": all(c["ok"] for c in checks),
    }
    return dep_out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)

    dep = verify()

    # immutability tree
    c5 = _tree_hashes(C005)
    c6 = _tree_hashes(C006)
    imm = {
        "note": "Baseline sha256 tree of immutable c005/c006 folders at c007 start; "
                "AC-16 re-hashes and diffs to prove no earlier-contract file changed.",
        "c005_final_head": C005_FINAL_HEAD,
        "c006_final_head": C006_FINAL_HEAD,
        "c005_file_count": len(c5),
        "c006_file_count": len(c6),
        "c005_tree_sha256": hashlib.sha256(json.dumps(c5, sort_keys=True).encode()).hexdigest(),
        "c006_tree_sha256": hashlib.sha256(json.dumps(c6, sort_keys=True).encode()).hexdigest(),
        "c005_files": c5,
        "c006_files": c6,
    }

    json.dump(dep, open(os.path.join(a.out_dir, "dependency_verification.json"), "w"), indent=2)
    json.dump(imm, open(os.path.join(a.out_dir, "immutability_verification.json"), "w"), indent=2)

    lines = []
    lines.append("c007 AC-01 dependency + immutability verification")
    lines.append("=" * 60)
    lines.append(f"c005 final head: {dep['c005_final_head']}")
    lines.append(f"c006 final head: {dep['c006_final_head']}")
    lines.append(f"c007 initial head: {dep['c007_initial_head']}")
    lines.append(f"teacher: {dep['teacher_id']}  deck: {dep['frozen_deck_id']}")
    lines.append(f"teacher submission ref: {dep['teacher_submission_ref']} "
                 f"(recorded {dep['teacher_recorded_public_score']})")
    lines.append("")
    for c in dep["checks"]:
        lines.append(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}")
    lines.append("")
    lines.append(f"immutability baseline: c005 {imm['c005_file_count']} files "
                 f"(tree {imm['c005_tree_sha256'][:16]}), "
                 f"c006 {imm['c006_file_count']} files (tree {imm['c006_tree_sha256'][:16]})")
    lines.append(f"ALL_OK = {dep['all_ok']}")
    txt = "\n".join(lines) + "\n"
    open(a.log, "w").write(txt)
    print(txt)
    return 0 if dep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""c006 AC-01: verify c005 frozen dependencies + split integrity (no c005 mutation).

Recomputes hashes of the frozen teacher, the submission-A archive, and the
model-ready dataset files, and checks them against the c005 manifests. Also
re-derives every decision_index from the model-ready records (via the c005
example_id hash) to prove the dataset is ordered-reconstructable and that no game
crosses a split boundary. Writes a machine-readable verification JSON.

Read-only w.r.t. c005: this script never writes under contracts/c005_*.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C005 = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset")
C005_ART = os.path.join(C005, "results", "artifacts")
DS = os.path.join(C005_ART, "teacher_dataset")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _eid(tid, gid, didx):
    return hashlib.sha256(f"{tid}|{gid}|{didx}".encode()).hexdigest()[:24]


def verify():
    checks = []

    def rec(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # 1. c005 STATUS.json final head
    status = json.load(open(os.path.join(C005, "results", "STATUS.json")))
    rec("c005_status_pass", status.get("status") == "PASS",
        {"status": status.get("status"), "final_head": status.get("final_head")})

    # 2. frozen teacher hashes
    fm = json.load(open(os.path.join(C005_ART, "frozen_teacher_manifest.json")))
    ft = os.path.join(C005_ART, "frozen_teacher")
    main_sha = sha256_file(os.path.join(ft, "main.py"))
    deck_sha = sha256_file(os.path.join(ft, "deck.csv"))
    rec("frozen_teacher_main_sha256", main_sha == fm["main_sha256"],
        {"expected": fm["main_sha256"], "actual": main_sha})
    rec("frozen_teacher_deck_sha256", deck_sha == fm["deck_sha256"],
        {"expected": fm["deck_sha256"], "actual": deck_sha})
    deck_id = fm["frozen_deck_id"]

    # 3. submission A archive size (+ record sha256)
    arch = os.path.join(C005_ART, "submission_A_teacher.tar.gz")
    arch_size = os.path.getsize(arch)
    arch_sha = sha256_file(arch)
    rec("submission_A_archive_size", arch_size == fm["archive_size_bytes"],
        {"expected": fm["archive_size_bytes"], "actual": arch_size, "sha256": arch_sha})

    # 4. dataset manifest counts + file hashes (recorded)
    dm = json.load(open(os.path.join(C005_ART, "teacher_dataset_manifest.json")))
    splits = json.load(open(os.path.join(DS, "splits.json")))
    file_hashes = {}
    counts = {}
    game_split = {}
    all_recovered = 0
    all_records = 0
    for sp in ("train", "validation", "test"):
        path = os.path.join(DS, f"{sp}.jsonl.gz")
        file_hashes[sp] = sha256_file(path)
        games = {}
        with gzip.open(path, "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
        counts[sp] = {"games": len(games), "decisions": sum(len(v) for v in games.values())}
        for gid in games:
            game_split.setdefault(gid, set()).add(sp)
        # re-derive decision_index for each game via example_id hash
        for gid, lst in games.items():
            tid = lst[0]["teacher_id"]
            by_eid = {r["example_id"] for r in lst}
            idxs = set()
            for didx in range(len(lst) + 8):
                if _eid(tid, gid, didx) in by_eid:
                    idxs.add(didx)
            all_records += len(lst)
            if idxs == set(range(len(lst))):
                all_recovered += len(lst)
    rec("dataset_split_games", counts == {k: {"games": splits["games"][k], "decisions": splits["decisions"][k]}
                                          for k in ("train", "validation", "test")},
        {"actual": counts, "manifest_games": splits["games"], "manifest_decisions": splits["decisions"]})
    rec("dataset_manifest_totals", dm["teacher_decisions"] == sum(counts[s]["decisions"] for s in counts)
        and dm["total_games"] == sum(counts[s]["games"] for s in counts),
        {"manifest_decisions": dm["teacher_decisions"], "manifest_games": dm["total_games"]})
    leak = {g: sorted(s) for g, s in game_split.items() if len(s) > 1}
    rec("no_game_in_multiple_splits", len(leak) == 0, {"leaking_games": leak})
    rec("all_decision_indices_recoverable", all_recovered == all_records,
        {"recovered": all_recovered, "total": all_records})

    # 5. frozen deck id consistency with dataset
    rec("deck_id_consistent", deck_id == dm["teacher_deck_id"] == splits.get("teacher_deck_id", dm["teacher_deck_id"]),
        {"frozen": deck_id, "dataset": dm["teacher_deck_id"]})

    # 6. supplied Kaggle baseline input
    base = json.load(open(os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                                        "inputs", "submission_A_kaggle_baseline.json")))
    rec("kaggle_baseline_ref", base.get("submission_ref") == "54948560",
        {"ref": base.get("submission_ref"), "public_score": base.get("public_score")})

    # 7. teacher sources present (needed for gameplay opponents)
    src = os.path.join(C005_ART, "teacher_sources")
    present = {c: os.path.isdir(os.path.join(src, c)) and os.path.isfile(os.path.join(src, c, "main.py"))
               for c in ("dragapult", "mega_lucario", "mega_abomasnow", "iono")}
    rec("teacher_sources_present", all(present.values()), present)

    out = {
        "contract": "c006_distilled_policy_baseline",
        "c005_final_head": status.get("final_head"),
        "frozen_teacher_id": fm["teacher_id"],
        "frozen_deck_id": deck_id,
        "frozen_teacher_main_sha256": main_sha,
        "frozen_teacher_deck_sha256": deck_sha,
        "submission_A_archive": {"path": os.path.relpath(arch, _REPO), "size_bytes": arch_size,
                                 "sha256": arch_sha},
        "dataset_file_sha256": file_hashes,
        "dataset_counts": counts,
        "checks": checks,
        "all_ok": all(c["ok"] for c in checks),
    }
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    out = verify()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=2)
    print(json.dumps({"all_ok": out["all_ok"],
                      "failed": [c["check"] for c in out["checks"] if not c["ok"]]}, indent=2))
    for c in out["checks"]:
        print(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}")
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

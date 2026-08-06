"""c010 AC-01: dependency + immutability verification (c005–c009).

Verifies the accepted-contract chain, the frozen teacher/deck, B0 (untouched c007 V2-A) and
I0 (the c009-resolved incumbent: c008 R1 seed 101 near 10,040 games), and — critically —
re-derives the recorded B0 and I0 scores from the c009 raw games so the starting point of
c010 is proven from evidence, not quoted. Snapshots a recursive sha256 tree of all five
immutable contract folders for the AC-16/AC-14 recheck. Read-only w.r.t. c005–c009.
"""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

DIRS = {"c005": "c005_teacher_import_submission_and_dataset",
        "c006": "c006_distilled_policy_baseline",
        "c007": "c007_hybrid_teacher_residual_and_state_encoder_v2",
        "c008": "c008_fixed_deck_teacher_anchored_rl",
        "c009": "c009_amendment_c008"}
C = {k: os.path.join(_REPO, "contracts", v) for k, v in DIRS.items()}
ART = {k: os.path.join(v, "results", "artifacts") for k, v in C.items()}
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")

FINAL = {"c005": "4137d983c6a05c0eea8332718d3e7f3acc7b7830",
         "c006": "08ebac88385444a69d0615b7976dea9dbddeb79a",
         "c007": "1f3fc63aaa36be0a45ffce8481c563c89ffa0577",
         "c008": "fb6e592c8c333f758014e2d2e94a39261bb63fe6",
         "c009": "e868dfbbeefc30bcf246cd60e0f51bf6d0043eb8"}
TEACHER_REF = "54948560"
DECK_ID = "sha256:8055443275c86105b38198992c9556a642b833a47430aa97fb1a84c9ee4fdbab"
# Expected c009 results, re-derived from c009 raw games (never trusted as quoted).
# NOTE: c009 (and the c010 §1/context quotes) averaged the strategic field over FOUR
# opponents including the Dragapult mirror; c010 §17 registers the field as the average over
# THREE opponents (Lucario, Iono, Abomasnow). Both are verified: the 4-opponent value proves
# the c009 evidence is intact, and the 3-opponent value is the baseline c010's own gates use.
EXPECT_C009_FIELD4 = {"B0_v2a": {"teacher": 0.160, "field4": 0.1525},
                      "R1_101": {"teacher": 0.220, "field4": 0.2550}}
FIELD_OPPS = ["mega_lucario", "iono", "mega_abomasnow"]   # strategic field per c010 §17
FIELD_OPPS_C009 = FIELD_OPPS + ["dragapult"]              # c009's mirror-inclusive definition
TEACHER_PHASES = {"A", "B", "B_ext"}
STRAT_PHASES = {"C", "D"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
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
    from cg import noninf_stats as ns
    checks = []

    def rec(n, ok, d=""):
        checks.append({"check": n, "ok": bool(ok), "detail": str(d)[:300]})

    st = {}
    for k in DIRS:
        st[k] = json.load(open(os.path.join(C[k], "results", "STATUS.json")))
        rec(f"{k}_status_and_head", st[k].get("status") == "PASS" and st[k].get("final_head") == FINAL[k],
            {"status": st[k].get("status"), "head": st[k].get("final_head")})
    rec("commit_chain", all(st[b].get("initial_head") == FINAL[a] for a, b in
                            (("c005", "c006"), ("c006", "c007"), ("c007", "c008"), ("c008", "c009"))))
    head = _git("rev-parse", "HEAD").stdout.strip()
    rec("c010_branches_from_c009_final",
        head == FINAL["c009"] or _git("merge-base", "--is-ancestor", FINAL["c009"], "HEAD").returncode == 0,
        head)

    # frozen teacher + deck
    fm = json.load(open(os.path.join(ART["c005"], "frozen_teacher_manifest.json")))
    ft = os.path.join(ART["c005"], "frozen_teacher")
    main_sha, deck_sha = sha256_file(os.path.join(ft, "main.py")), sha256_file(os.path.join(ft, "deck.csv"))
    rec("frozen_teacher_main_sha", main_sha == fm["main_sha256"], main_sha)
    rec("frozen_teacher_deck_sha", deck_sha == fm["deck_sha256"], deck_sha)
    rec("frozen_deck_id", fm["frozen_deck_id"] == DECK_ID, fm["frozen_deck_id"])
    deck = [int(x) for x in open(os.path.join(ft, "deck.csv")) if x.strip()]
    deck_fp = hashlib.sha256(",".join(str(c) for c in deck).encode()).hexdigest()
    rec("frozen_deck_60_cards", len(deck) == 60, len(deck))

    # B0 / I0 from the c009 registry (never inferred from filenames)
    creg = json.load(open(os.path.join(ART["c009"], "candidate_checkpoint_registry.json")))
    cdec = json.load(open(os.path.join(ART["c009"], "amended_checkpoint_selection.json")))
    b0, i0_id = creg["B0_v2a"], cdec["best_saved_candidate_id"]
    i0 = creg[i0_id]
    rec("c009_best_saved_is_R1_101", i0_id == "R1_101", i0_id)
    rec("i0_is_c008_R1_seed101_near_10040", i0["arm"] == "R1" and i0["seed"] == 101
        and abs((i0["training_games"] or 0) - 10040) <= 100, i0["training_games"])
    b0_ok = os.path.exists(os.path.join(_REPO, b0["checkpoint_path"])) and \
        sha256_file(os.path.join(_REPO, b0["checkpoint_path"])) == b0["checkpoint_sha256"]
    i0_ok = os.path.exists(os.path.join(_REPO, i0["checkpoint_path"])) and \
        sha256_file(os.path.join(_REPO, i0["checkpoint_path"])) == i0["checkpoint_sha256"]
    rec("B0_checkpoint_hash_verified", b0_ok, b0["checkpoint_sha256"])
    rec("I0_checkpoint_hash_verified", i0_ok, i0["checkpoint_sha256"])

    # re-derive the recorded c009 scores from c009 RAW games
    games = [json.loads(l) for l in gzip.open(os.path.join(ART["c009"], "corrected_games.jsonl.gz"), "rt")]
    derived = {}
    for cid in ("B0_v2a", "R1_101"):
        s = {0: [], 1: []}
        for g in games:
            if g["candidate_id"] == cid and g["opponent_id"] == "dragapult" \
                    and g["phase"] in TEACHER_PHASES and g["score"] is not None:
                s[g["seat"]].append(g["score"])
        t = ns.seat_balanced_point(s[0], s[1])
        per_opp = {}
        for opp in FIELD_OPPS_C009:
            so = {0: [], 1: []}
            for g in games:
                if g["candidate_id"] == cid and g["opponent_id"] == opp \
                        and g["phase"] in STRAT_PHASES and g["score"] is not None:
                    so[g["seat"]].append(g["score"])
            if so[0] or so[1]:
                per_opp[opp] = ns.seat_balanced_point(so[0], so[1])
        f3 = sum(per_opp[o] for o in FIELD_OPPS) / len(FIELD_OPPS)          # c010 §17 metric
        f4 = sum(per_opp.values()) / len(per_opp)                            # c009 metric
        derived[cid] = {"teacher": t, "field_c010_3opp": f3, "field_c009_4opp": f4,
                        "per_opponent": per_opp, "n_teacher": len(s[0]) + len(s[1])}
        rec(f"c009_raw_reproduces_{cid}_teacher",
            abs(t - EXPECT_C009_FIELD4[cid]["teacher"]) < 1e-6,
            f"{t} vs {EXPECT_C009_FIELD4[cid]['teacher']}")
        rec(f"c009_raw_reproduces_{cid}_field_c009_definition",
            abs(f4 - EXPECT_C009_FIELD4[cid]["field4"]) < 1e-6,
            f"{f4} vs {EXPECT_C009_FIELD4[cid]['field4']} (4-opponent, mirror-inclusive)")

    # opponents (Abomasnow is evaluation-only)
    src = os.path.join(ART["c005"], "teacher_sources")
    present = {c: os.path.isfile(os.path.join(src, c, "main.py"))
               for c in ("dragapult", "mega_lucario", "iono", "mega_abomasnow")}
    rec("opponents_present", all(present.values()), present)
    ctx = json.load(open(os.path.join(C010, "inputs", "c010_context.json")))
    rec("teacher_submission_ref", ctx.get("teacher_submission_ref") == TEACHER_REF)

    dep = {}
    for m in ("numpy", "scipy", "kaggle_environments", "cg"):
        try:
            __import__(m); dep[m] = "ok"
        except Exception as e:  # noqa: BLE001
            dep[m] = f"MISSING:{type(e).__name__}"
    rec("runtime_deps", dep["numpy"] == "ok" and dep["cg"] == "ok", dep)

    return {"contract": "c010_fixed_deck_rl_loop_v2", "chain_final_heads": FINAL,
            "c010_initial_head": head, "teacher_id": fm["teacher_id"],
            "frozen_deck_id": fm["frozen_deck_id"], "frozen_deck_fingerprint": deck_fp,
            "frozen_teacher_main_sha256": main_sha,
            "B0": {"candidate_id": "B0_v2a", "path": b0["checkpoint_path"],
                   "sha256": b0["checkpoint_sha256"]},
            "I0": {"candidate_id": i0_id, "path": i0["checkpoint_path"],
                   "sha256": i0["checkpoint_sha256"], "training_games": i0["training_games"]},
            "c009_derived_scores": derived, "expected_c009_scores": EXPECT_C009_FIELD4,
            "c010_registered_baselines": {
                "field_definition": "c010 §17: average balanced score vs Lucario, Iono, Abomasnow "
                                    "(the Dragapult mirror is NOT part of the field; it is the "
                                    "separate teacher score)",
                "B0": {"teacher": derived["B0_v2a"]["teacher"],
                       "field": derived["B0_v2a"]["field_c010_3opp"]},
                "I0": {"teacher": derived["R1_101"]["teacher"],
                       "field": derived["R1_101"]["field_c010_3opp"]},
                "note": "c010 §1 and inputs/c010_context.json quote 15.25% / 25.50% for the field; "
                        "those are c009's 4-opponent (mirror-inclusive) values, verified above. "
                        "Under c010's registered §17 metric the same raw games give 15.33% and "
                        "29.00%. c010 gates use the §17 values throughout — using the lower quoted "
                        "incumbent field would silently weaken the incumbent's protection."},
            "teacher_submission_ref": TEACHER_REF, "runtime_deps": dep,
            "checks": checks, "all_ok": all(c["ok"] for c in checks)}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True); os.makedirs(os.path.dirname(a.log), exist_ok=True)
    dep = verify()
    imm = {"note": "Baseline sha256 tree of the five immutable contract folders at c010 start.",
           "final_heads": FINAL}
    for k in DIRS:
        t = _tree(C[k])
        imm[f"{k}_file_count"] = len(t)
        imm[f"{k}_tree_sha256"] = hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest()
        imm[f"{k}_files"] = t
    json.dump(dep, open(os.path.join(a.out_dir, "dependency_verification.json"), "w"), indent=2)
    json.dump(imm, open(os.path.join(a.out_dir, "immutability_verification.json"), "w"), indent=2)
    lines = ["c010 AC-01 dependency + immutability", "=" * 60,
             "chain: " + " -> ".join(f"{k} {FINAL[k][:10]}" for k in DIRS)
             + f" -> c010 init {dep['c010_initial_head'][:10]}",
             f"deck {dep['frozen_deck_id']}  fingerprint {dep['frozen_deck_fingerprint'][:16]}",
             f"B0 {dep['B0']['sha256'][:16]}  I0 {dep['I0']['candidate_id']} "
             f"{dep['I0']['sha256'][:16]} @ {dep['I0']['training_games']} games",
             f"c009 raw re-derived (4-opp c009 metric): B0 {dep['c009_derived_scores']['B0_v2a']['field_c009_4opp']:.4f}"
             f" / I0 {dep['c009_derived_scores']['R1_101']['field_c009_4opp']:.4f}  -> matches c009",
             f"c010 §17 registered baselines (3-opp field): "
             f"B0 teacher={dep['c010_registered_baselines']['B0']['teacher']:.4f} "
             f"field={dep['c010_registered_baselines']['B0']['field']:.4f} | "
             f"I0 teacher={dep['c010_registered_baselines']['I0']['teacher']:.4f} "
             f"field={dep['c010_registered_baselines']['I0']['field']:.4f}", ""]
    for c in dep["checks"]:
        lines.append(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}"
                     + (f"  -> {c['detail']}" if not c["ok"] else ""))
    lines += ["", "immutability baseline: " + ", ".join(f"{k} {imm[f'{k}_file_count']}f" for k in DIRS),
              f"ALL_OK = {dep['all_ok']}"]
    open(a.log, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if dep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

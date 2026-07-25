"""c009 AC-04: build the frozen candidate-checkpoint registry.

Contains B0 (the untouched c007 V2-A initialization), the frozen teacher reference, and
EVERY c008 validation-selected checkpoint (R0/R1/R2, all seeds). Identities come from the
c008 selection artifacts — never inferred from filenames. Nothing is written to c005–c008.
"""

import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C007_ART = os.path.join(_REPO, "contracts", "c007_hybrid_teacher_residual_and_state_encoder_v2",
                        "results", "artifacts")
C008_ART = os.path.join(_REPO, "contracts", "c008_fixed_deck_teacher_anchored_rl",
                        "results", "artifacts")
C005_ART = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                        "results", "artifacts")
V2A = os.path.join(C007_ART, "checkpoints", "V2_A_selected.npz")
TEACHER_MAIN = os.path.join(C005_ART, "frozen_teacher", "main.py")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def build():
    sel = json.load(open(os.path.join(C008_ART, "checkpoint_selection.json")))
    reg = {}

    # --- B0: untouched supervised initialization (never RL-updated) ---
    reg["B0_v2a"] = {
        "candidate_id": "B0_v2a", "arm": "B0", "seed": None, "kind": "v2a_init",
        "training_games": 0,
        "checkpoint_path": os.path.relpath(V2A, _REPO), "checkpoint_sha256": sha(V2A),
        "source_selection_metric": None, "source_selection_rank": None,
        "is_median_representative": False, "is_best_within_arm_by_c008_validation": True,
        "description": "exact c007 selected V2-A checkpoint before any RL update; the policy "
                       "R1/R2 were initialized from at game zero (value head + STOP logit at "
                       "their untrained init, which do not affect greedy action selection)",
    }
    # --- frozen teacher reference (Phase C arm; not an RL candidate) ---
    reg["T_teacher"] = {
        "candidate_id": "T_teacher", "arm": "T", "seed": None, "kind": "frozen_teacher",
        "training_games": None,
        "checkpoint_path": os.path.relpath(TEACHER_MAIN, _REPO), "checkpoint_sha256": sha(TEACHER_MAIN),
        "source_selection_metric": None, "source_selection_rank": None,
        "is_median_representative": False, "is_best_within_arm_by_c008_validation": False,
        "description": "frozen c005 Dragapult rule teacher (reference arm, not an RL candidate)",
    }

    # --- every c008 validation-selected checkpoint ---
    by_arm = {}
    for key, v in sel["per_seed"].items():
        arm, seedstr = key.split("/")
        by_arm.setdefault(arm, []).append((int(seedstr.replace("seed", "")), v))
    for arm, entries in by_arm.items():
        ranked = sorted(entries, key=lambda t: -(t[1]["validation_blend"] or -1))
        median_seed = sel["per_arm"].get(arm, {}).get("representative_seed")
        for rank, (seed, v) in enumerate(ranked, start=1):
            cid = f"{arm}_{seed}"
            p = v["selected_checkpoint"]
            ap = os.path.join(_REPO, p)
            reg[cid] = {
                "candidate_id": cid, "arm": arm, "seed": seed, "kind": "rl_ckpt",
                "training_games": v["games"],
                "checkpoint_path": p,
                "checkpoint_sha256": sha(ap) if os.path.exists(ap) else None,
                "source_selection_metric": v["validation_blend"],
                "source_selection_rank": rank,
                "is_median_representative": (seed == median_seed),
                "is_best_within_arm_by_c008_validation": (rank == 1),
                "c008_stop_reason": v.get("stop_reason"),
                "description": f"c008 {arm} seed {seed} validation-selected checkpoint at "
                               f"{v['games']} training games",
            }
    return reg


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    reg = build()

    checks = []

    def rec(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    rec("B0_present_and_hashed", reg.get("B0_v2a", {}).get("checkpoint_sha256") is not None,
        reg["B0_v2a"]["checkpoint_sha256"][:16] if reg.get("B0_v2a", {}).get("checkpoint_sha256") else "")
    r1 = sorted(c for c in reg if c.startswith("R1_"))
    r2 = sorted(c for c in reg if c.startswith("R2_"))
    r0 = sorted(c for c in reg if c.startswith("R0_"))
    rec("R1_seeds_101_202_present", {"R1_101", "R1_202"} <= set(r1), str(r1))
    rec("R2_seeds_101_202_303_present", {"R2_101", "R2_202", "R2_303"} <= set(r2), str(r2))
    rec("R0_controls_present", len(r0) > 0, str(r0))
    missing_hash = [c for c, v in reg.items() if v["checkpoint_sha256"] is None]
    rec("all_checkpoints_hashed", not missing_hash, str(missing_hash))
    shas = [v["checkpoint_sha256"] for v in reg.values() if v["checkpoint_sha256"]]
    rec("all_hashes_distinct", len(set(shas)) == len(shas), f"{len(set(shas))}/{len(shas)}")
    rec("files_exist", all(os.path.exists(os.path.join(_REPO, v["checkpoint_path"])) for v in reg.values()))
    # exactly one best-by-validation per RL arm
    for arm in ("R0", "R1", "R2"):
        best = [c for c, v in reg.items() if v["arm"] == arm and v["is_best_within_arm_by_c008_validation"]]
        rec(f"{arm}_exactly_one_best_by_validation", len(best) == 1, str(best))
    med = [c for c, v in reg.items() if v["is_median_representative"]]
    rec("median_representatives_flagged", len(med) == 3, str(med))

    all_ok = all(c[1] for c in checks)
    json.dump(reg, open(os.path.join(a.out_dir, "candidate_checkpoint_registry.json"), "w"), indent=2)

    lines = ["c009 AC-04 candidate checkpoint registry", "=" * 60,
             f"entries: {len(reg)}  (B0 + frozen teacher + {len(r0)+len(r1)+len(r2)} c008 selected)", ""]
    for cid, v in sorted(reg.items(), key=lambda kv: (kv[1]["arm"], str(kv[1]["seed"]))):
        lines.append(f"  {cid:12s} arm={v['arm']:3s} seed={str(v['seed']):5s} "
                     f"games={str(v['training_games']):6s} metric={str(v['source_selection_metric']):8s} "
                     f"rank={str(v['source_selection_rank']):4s} "
                     f"median={int(v['is_median_representative'])} best={int(v['is_best_within_arm_by_c008_validation'])} "
                     f"sha={v['checkpoint_sha256'][:12] if v['checkpoint_sha256'] else 'NONE'}")
    lines.append("")
    for n, ok, d in checks:
        lines.append(f"  [{'OK ' if ok else 'FAIL'}] {n}  {d}")
    lines.append("")
    lines.append("NOTE: c008 designated the MEDIAN seed as each arm's representative, while the "
                 "c008 final evaluation used the BEST-by-validation checkpoint. c009 evaluates "
                 "every selected checkpoint, so the distinction cannot bias the outcome.")
    lines.append(f"ALL_OK = {all_ok}")
    open(a.log, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

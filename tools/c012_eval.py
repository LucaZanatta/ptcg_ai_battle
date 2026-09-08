"""c011 §17/§18 identity-safe evaluation on the frozen panels.

Reuses the c009 immutable job identity verbatim (every worker returns job_id, candidate_id,
checkpoint SHA-256, opponent, seat, replicate, requested seed, phase, and re-hashes the
weights it actually loaded plus the deck it actually played). Results are matched to jobs by
job_id only -- never by completion position.

c011 adds two things c010 lacked:
  * the FROZEN TEACHER can be evaluated as a candidate, on the same panel and identity
    protocol, so §24's strategic comparison uses a same-panel teacher baseline (§7.2);
  * candidates may carry a trainer-state ID alongside the checkpoint hash (§17).

The teacher plays only the three strategic-field opponents (§7.2/§18.3); a teacher-vs-teacher
mirror is not part of its baseline and is never synthesised.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import c009_eval as ce, c011_eval_core as cc, noninf_stats as ns  # noqa: E402

C012 = os.path.join(_REPO, "contracts", "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C012, "results", "artifacts")
LOGD = os.path.join(C012, "results", "test_logs")

TEACHER = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
ALL_OPPS = [TEACHER] + FIELD
PANELS = {
    "screen": {TEACHER: 20, "mega_lucario": 10, "iono": 10, "mega_abomasnow": 10},
    "confirmation": {TEACHER: 100, "mega_lucario": 50, "iono": 50, "mega_abomasnow": 50},
    "final": {TEACHER: 200, "mega_lucario": 100, "iono": 100, "mega_abomasnow": 100},
}
COMPOSITE_W = {TEACHER: 0.55, "mega_lucario": 0.15, "iono": 0.15, "mega_abomasnow": 0.15}
BOOT = 4000
GAMES = os.path.join(ART, "evaluation_games.jsonl.gz")
MANIFEST = os.path.join(ART, "evaluation_game_manifest.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def opponents_for(cand, panel):
    """The frozen teacher is scored on the strategic field only (§7.2); every policy
    candidate plays the full panel including the teacher head-to-head."""
    spec = PANELS[panel]
    if cand["kind"] == "frozen_teacher":
        return {o: spec[o] for o in FIELD}
    return spec


def build_candidate_registry():
    """B0/I0/teacher/all c010 checkpoints/all c011 checkpoints, with hashes read from disk.
    Nothing is inferred from a filename."""
    reg = {}
    base = json.load(open(os.path.join(C010, "results", "artifacts",
                                       "baseline_incumbent_registry.json")))
    tsha = cc.teacher_source_sha256()
    reg["T_teacher"] = {"candidate_id": "T_teacher", "kind": "frozen_teacher", "arm": "T",
                        "seed": None,
                        "checkpoint_path": os.path.relpath(cc.TEACHER_MAIN, _REPO),
                        "checkpoint_sha256": tsha, "training_games": None, "protected": True,
                        "registered_sha256_c010": base.get("T", {}).get("checkpoint_sha256")}
    # c010's registry records kinds in its TRAINING-initialisation vocabulary
    # ("rl_ckpt_from_v2a"); cg.c009_eval's loader speaks the EVALUATION vocabulary
    # ("v2a_init"). Copying the string verbatim makes every B0 game fail to build an agent,
    # so the kind is translated rather than passed through.
    EVAL_KIND = {"rl_ckpt_from_v2a": "v2a_init", "v2a_init": "v2a_init", "rl_ckpt": "rl_ckpt"}
    for key, cid, arm in (("B0", "B0_v2a", "B0"), ("I0", "I0_incumbent", "I0")):
        b = base[key]
        reg[cid] = {"candidate_id": cid,
                    "kind": EVAL_KIND.get(b.get("kind"), "rl_ckpt") if key == "B0" else "rl_ckpt",
                    "arm": arm, "seed": b.get("seed"),
                    "checkpoint_path": b["checkpoint_path"],
                    "checkpoint_sha256": b["checkpoint_sha256"],
                    "training_games": b.get("training_games", 0), "protected": True}

    # every c010 training checkpoint, from c010's own per-seed registries
    troot = os.path.join(C010, "results", "artifacts", "training")
    if os.path.isdir(troot):
        for armdir in sorted(os.listdir(troot)):
            arm = armdir.replace("arm_", "")
            for sd in sorted(os.listdir(os.path.join(troot, armdir))):
                creg = os.path.join(troot, armdir, sd, "checkpoint_registry.json")
                if not os.path.exists(creg):
                    continue
                for games, meta in json.load(open(creg)).items():
                    cid = f"{arm}_{meta['seed']}_g{games}"
                    reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": arm,
                                "seed": meta["seed"], "checkpoint_path": meta["checkpoint_path"],
                                "checkpoint_sha256": meta["sha256"],
                                "training_games": meta["training_games"],
                                "registered_eval_point": meta.get("registered_eval_point"),
                                "terminal_below_registered_point":
                                    meta.get("terminal_below_registered_point", False),
                                "source_contract": "c010", "protected": False}

    # c011 scale checkpoints (read from c011, never written)
    c11root = os.path.join(C011, "results", "artifacts", "training")
    if os.path.isdir(c11root):
        for sd in sorted(os.listdir(c11root)):
            creg = os.path.join(c11root, sd, "checkpoint_registry.json")
            if not os.path.exists(creg):
                continue
            for games, meta in json.load(open(creg)).items():
                cid = f"S_{meta['seed']}_g{games}"
                reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": "S",
                            "seed": meta["seed"], "checkpoint_path": meta["checkpoint_path"],
                            "checkpoint_sha256": meta["sha256"],
                            "training_games": meta["training_games"],
                            "registered_eval_point": meta.get("registered_eval_point"),
                            "trainer_state_id": meta.get("trainer_state_id"),
                            "source_contract": "c011", "protected": False}

    # c012 P0/P1 scale checkpoints
    for arm in ("P0", "P1"):
        aroot = os.path.join(ART, "training", arm)
        if not os.path.isdir(aroot):
            continue
        for sd in sorted(os.listdir(aroot)):
            creg = os.path.join(aroot, sd, "checkpoint_registry.json")
            if not os.path.exists(creg):
                continue
            for games, meta in json.load(open(creg)).items():
                cid = f"{arm}_{meta['seed']}_g{games}"
                reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": arm,
                            "seed": meta["seed"], "checkpoint_path": meta["checkpoint_path"],
                            "checkpoint_sha256": meta["sha256"],
                            "training_games": meta["training_games"],
                            "registered_eval_point": meta.get("registered_eval_point"),
                            "trainer_state_id": meta.get("trainer_state_id"),
                            "source_contract": "c012", "protected": False}

    # c012 registered weight soups (architecture-identical averages exported to NPZ)
    sreg = os.path.join(ART, "elite_combination_registry.json")
    if os.path.exists(sreg):
        for cid, m in (json.load(open(sreg)).get("soups") or {}).items():
            cp = os.path.join(_REPO, m["checkpoint_path"])
            if os.path.exists(cp):
                reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": "SOUP",
                            "seed": None, "checkpoint_path": m["checkpoint_path"],
                            "checkpoint_sha256": m["sha256"], "training_games": None,
                            "components": m.get("components"),
                            "source_contract": "c012", "protected": False}
    return reg


def panel_jobs(registry, candidates, panel, deck, rng, replicate_offset=0, teacher_only=False):
    jobs = []
    for cid in candidates:
        cand = registry[cid]
        spec = opponents_for(cand, panel)
        if teacher_only:
            spec = {TEACHER: spec[TEACHER]} if TEACHER in spec else {}
        for opp, per_seat in spec.items():
            for seat in (0, 1):
                for r in range(per_seat):
                    jobs.append(ce.make_job(cand, opp, seat, replicate_offset + r, panel,
                                            requested_seed=int(rng.integers(0, 1 << 30)),
                                            deck=deck))
    return jobs


def load_existing():
    if not os.path.exists(GAMES):
        return []
    return [json.loads(l) for l in gzip.open(GAMES, "rt")]


def seat_scores(games, cid, opp, panels):
    s = {0: [], 1: []}
    for g in games:
        if (g["candidate_id"] == cid and g["opponent_id"] == opp and g["score"] is not None
                and g["phase"] in panels):
            s[g["seat"]].append(g["score"])
    return s


def boot_dist(s, rng):
    a = np.asarray(s[0], dtype=float); b = np.asarray(s[1], dtype=float)
    if not len(a) or not len(b):
        return None
    ia = rng.integers(0, len(a), (BOOT, len(a)))
    ib = rng.integers(0, len(b), (BOOT, len(b)))
    return 0.5 * (a[ia].mean(axis=1) + b[ib].mean(axis=1))


def summarize(games, cid, panels, rng):
    """Seat-balanced point estimates + bootstrap. Returns (summary, per-opponent bootstraps).
    A candidate without teacher games (the frozen teacher itself) gets no teacher score and
    no promotion composite -- neither is synthesised."""
    per, dists = {}, {}
    for opp in ALL_OPPS:
        s = seat_scores(games, cid, opp, panels)
        if not (s[0] or s[1]):
            continue
        d = boot_dist(s, rng)
        dists[opp] = d
        per[opp] = {"point": ns.seat_balanced_point(s[0], s[1]), "n": len(s[0]) + len(s[1]),
                    "n_seat0": len(s[0]), "n_seat1": len(s[1]),
                    "seat0_mean": float(np.mean(s[0])) if s[0] else None,
                    "seat1_mean": float(np.mean(s[1])) if s[1] else None,
                    "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                    "one_sided_lb95": float(np.percentile(d, 5))}
    if not per:
        return None, {}
    pts = {o: per[o]["point"] for o in per}
    field_pts = [pts[o] for o in FIELD if o in pts]
    field = float(np.mean(field_pts)) if len(field_pts) == len(FIELD) else None
    composite = (float(sum(COMPOSITE_W[o] * pts[o] for o in COMPOSITE_W))
                 if all(o in pts for o in COMPOSITE_W) else None)
    dd = [g for g in games if g["candidate_id"] == cid and g["phase"] in panels]
    lat = [g["latency_p99_ms"] for g in dd if g.get("latency_p99_ms") is not None]
    out = {"candidate_id": cid, "panels": sorted(panels), "per_opponent": per,
           "teacher_score": pts.get(TEACHER),
           "teacher_one_sided_lb95": per.get(TEACHER, {}).get("one_sided_lb95"),
           "strategic_field_score": field, "promotion_composite": composite,
           "reliability": {"games": len(dd), "defects": sum(1 for g in dd if g.get("defect")),
                           "invalid": sum(g["invalid_action_count"] for g in dd),
                           "exceptions": sum(g["exception_count"] for g in dd),
                           "timeouts": sum(g["timeout_count"] for g in dd),
                           "fallbacks": sum(g["fallback_count"] for g in dd)},
           "latency_p99_max_ms": float(np.max(lat)) if lat else None}
    if len(field_pts) == len(FIELD):
        fd = sum(dists[o] for o in FIELD) / 3.0
        out["field_ci95"] = [float(np.percentile(fd, 2.5)), float(np.percentile(fd, 97.5))]
        out["field_one_sided_lb95"] = float(np.percentile(fd, 5))
        dists["__field__"] = fd
    if composite is not None:
        cd = sum(COMPOSITE_W[o] * dists[o] for o in COMPOSITE_W)
        out["composite_ci95"] = [float(np.percentile(cd, 2.5)), float(np.percentile(cd, 97.5))]
        dists["__composite__"] = cd
    return out, dists


def append_games(new_games, batch_report):
    merged = load_existing() + new_games
    with gzip.open(GAMES, "wt") as fh:
        for g in sorted(merged, key=lambda r: r["job_id"]):
            fh.write(json.dumps(g) + "\n")
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"identity_reports": [],
                                                                      "batches": []}
    cells = Counter((g["candidate_id"], g["opponent_id"], g["seat"], g["phase"]) for g in merged)
    man.update({"contract": "c012", "total_games": len(merged),
                "phases": dict(Counter(g["phase"] for g in merged)),
                "per_candidate": dict(Counter(g["candidate_id"] for g in merged)),
                "seat_balance_ok": all(cells[(c, o, 0, ph)] == cells.get((c, o, 1, ph), 0)
                                       for (c, o, s, ph) in cells if s == 0),
                "terminal": sum(1 for g in merged if g["terminal"]),
                "defects": sum(1 for g in merged if g.get("defect")), "raw_sha256": None})
    man["identity_reports"].append(batch_report)
    man["batches"].append({"panel": batch_report["phase"], "candidates": batch_report["candidates"],
                           "games": batch_report["n_results"]})
    man["raw_sha256"] = sha(GAMES)
    json.dump(man, open(MANIFEST, "w"), indent=2)
    return man


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True, choices=list(PANELS))
    p.add_argument("--candidates", required=True, help="comma-separated ids, or ALL_NEW")
    p.add_argument("--nproc", type=int, default=12)
    p.add_argument("--replicate-offset", type=int, default=0)
    p.add_argument("--teacher-extension", action="store_true",
                   help="teacher-only extension of an existing panel (§18.3, 400 -> 800)")
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)

    registry = build_candidate_registry()
    json.dump(registry, open(os.path.join(ART, "evaluation_candidate_registry.json"), "w"),
              indent=2)
    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ce.SOURCES).deck
    deck_fp = ce.deck_fingerprint(deck)

    existing = load_existing()
    done = {(g["candidate_id"], g["phase"]) for g in existing}
    if a.candidates == "ALL_NEW":
        cands = [c for c in registry if (c, a.panel) not in done]
    else:
        cands = [c.strip() for c in a.candidates.split(",") if c.strip()]
    cands = [c for c in cands if c in registry]
    if not cands:
        print(json.dumps({"panel": a.panel, "candidates": [], "note": "nothing to evaluate"}))
        return 0

    rng = np.random.default_rng(abs(hash((a.panel, tuple(sorted(cands))))) % (2 ** 32))
    off = a.replicate_offset
    if a.teacher_extension and off == 0:
        off = PANELS[a.panel][TEACHER]
    jobs = panel_jobs(registry, cands, a.panel, deck, rng, off, teacher_only=a.teacher_extension)
    existing_ids = {g["job_id"] for g in existing}
    dup = [j["job_id"] for j in jobs if j["job_id"] in existing_ids]
    assert not dup, f"job_id collision with existing evidence: {dup[:3]}"

    t0 = time.time()
    results = cc.run_jobs(jobs, a.nproc)
    rep = ce.assert_identity(jobs, results, registry, expected_deck_fingerprint=deck_fp)
    rep.update({"phase": a.panel, "candidates": cands,
                "wall_seconds": round(time.time() - t0, 1)})
    for r in results:
        r.pop("deck", None)
    man = append_games(results, rep)

    all_games = load_existing()
    summaries = {}
    for c in cands:
        s, _d = summarize(all_games, c, {a.panel}, np.random.default_rng(4242))
        if s:
            summaries[c] = s
    sp = os.path.join(ART, f"panel_{a.panel}_summaries.json")
    prev = json.load(open(sp)) if os.path.exists(sp) else {}
    prev.update(summaries)
    json.dump(prev, open(sp, "w"), indent=2)

    with open(os.path.join(LOGD, "checkpoint_evaluation.txt"), "a") as fh:
        fh.write(f"[{a.panel}] {len(jobs)} games for {len(cands)} candidates in "
                 f"{rep['wall_seconds']}s | identity OK (terminal {rep['terminal']}, "
                 f"defects {rep['defects']})\n")
        for c in cands:
            s = summaries.get(c, {})
            fh.write(f"    {c:20s} teacher={s.get('teacher_score')} "
                     f"field={s.get('strategic_field_score')} "
                     f"composite={s.get('promotion_composite')} "
                     f"defects={s.get('reliability', {}).get('defects')}\n")
    print(json.dumps({"panel": a.panel, "candidates": len(cands), "games": len(jobs),
                      "identity_ok": rep["ok"], "defects": rep["defects"],
                      "total_evaluation_games": man["total_games"],
                      "wall_seconds": rep["wall_seconds"],
                      "scores": {c: {"teacher": summaries.get(c, {}).get("teacher_score"),
                                     "field": summaries.get(c, {}).get("strategic_field_score"),
                                     "composite": summaries.get(c, {}).get("promotion_composite")}
                                 for c in cands}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from cg import c009_eval as ce, c013_eval_core as cc, noninf_stats as ns  # noqa: E402

C013 = os.path.join(_REPO, "contracts", "c013_fixed_deck_policy_combination_and_learnability")
C011 = os.path.join(_REPO, "contracts", "c011_fixed_deck_cuda_ppo_scale")
C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C013, "results", "artifacts")
LOGD = os.path.join(C013, "results", "test_logs")

TEACHER = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
ALL_OPPS = [TEACHER] + FIELD
PANELS = {   # §10 registered panels
    "selection": {TEACHER: 50, "mega_lucario": 25, "iono": 25, "mega_abomasnow": 25},
    "confirmation": {TEACHER: 150, "mega_lucario": 75, "iono": 75, "mega_abomasnow": 75},
    "final": {TEACHER: 250, "mega_lucario": 125, "iono": 125, "mega_abomasnow": 125},
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
    """c013 candidates = frozen singles + registered combinations. Both registries are
    written before any combination result exists (§8)."""
    reg = {}
    cr = os.path.join(ART, "candidate_registry.json")
    if os.path.exists(cr):
        for cid, m in json.load(open(cr))["candidates"].items():
            reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": m["candidate_type"],
                        "seed": None, "checkpoint_path": m["checkpoint_path"],
                        "checkpoint_sha256": m["checkpoint_sha256"],
                        "candidate_type": m["candidate_type"],
                        "component_ids": m["component_ids"], "training_games": None,
                        "protected": True}
    br = os.path.join(ART, "combination_registry.json")
    if os.path.exists(br):
        for cid, m in json.load(open(br))["combinations"].items():
            reg[cid] = {"candidate_id": cid,
                        "kind": ("online_ensemble" if m["candidate_type"] == "online_ensemble"
                                 else "rl_ckpt"),
                        "arm": m["candidate_type"], "seed": None,
                        "checkpoint_path": m["checkpoint_path"],
                        "checkpoint_sha256": m["checkpoint_sha256"],
                        "candidate_type": m["candidate_type"],
                        "ensemble_mode": m.get("ensemble_mode"),
                        "component_ids": m["component_ids"],
                        "component_paths": m.get("component_paths"),
                        "training_games": None, "protected": False}
    tsha = cc.cc.teacher_source_sha256() if hasattr(cc, "cc") else None
    from cg import c011_eval_core as _c11
    reg["T_teacher"] = {"candidate_id": "T_teacher", "kind": "frozen_teacher", "arm": "T",
                        "seed": None,
                        "checkpoint_path": os.path.relpath(_c11.TEACHER_MAIN, _REPO),
                        "checkpoint_sha256": _c11.teacher_source_sha256(),
                        "candidate_type": "frozen_teacher", "component_ids": [],
                        "training_games": None, "protected": True}
    # c013 training checkpoints (Q0/Q1/Q2/smoke)
    troot = os.path.join(ART, "training")
    if os.path.isdir(troot):
        for arm in sorted(os.listdir(troot)):
            for sd in sorted(os.listdir(os.path.join(troot, arm))):
                creg = os.path.join(troot, arm, sd, "checkpoint_registry.json")
                if not os.path.exists(creg):
                    continue
                for games, meta in json.load(open(creg)).items():
                    cid = f"{arm}_{meta['seed']}_g{games}"
                    reg[cid] = {"candidate_id": cid, "kind": "rl_ckpt", "arm": arm,
                                "seed": meta["seed"],
                                "checkpoint_path": meta["checkpoint_path"],
                                "checkpoint_sha256": meta["sha256"],
                                "candidate_type": "single", "component_ids": [],
                                "training_games": meta["training_games"],
                                "protected": False}
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
                    j = ce.make_job(cand, opp, seat, replicate_offset + r, panel,
                                     requested_seed=int(rng.integers(0, 1 << 30)), deck=deck)
                    if cand.get("candidate_type") == "online_ensemble":
                        j["component_paths"] = cand.get("component_paths")
                        j["component_ids"] = cand.get("component_ids")
                        j["ensemble_mode"] = cand.get("ensemble_mode")
                    jobs.append(j)
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

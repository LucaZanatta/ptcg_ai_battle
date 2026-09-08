"""c010 AC-05/AC-10: identity-safe evaluation on the frozen panels.

Reuses the c009 job protocol verbatim (every worker returns job_id, candidate_id, checkpoint
SHA-256, opponent, seat, replicate, requested seed and phase, re-hashes the checkpoint it
loaded and fingerprints the deck it played) and runs the c009 assertion set before anything is
aggregated. Panels are frozen in the experiment registry before any training result is seen.

Panels (games per checkpoint): screen 100, confirmation 500, final 1,000.
Metrics: teacher score, strategic-field score (Lucario/Iono/Abomasnow), promotion composite.
The engineering control is diagnostic-only and never enters promotion metrics.
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
from cg import c009_eval as ce, noninf_stats as ns  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")
LOGD = os.path.join(C010, "results", "test_logs")
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


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def build_candidate_registry():
    """B0, I0 and every registered training checkpoint, with hashes. Never inferred from names."""
    base = json.load(open(os.path.join(ART, "baseline_incumbent_registry.json")))
    reg = {}
    reg["B0_v2a"] = {"candidate_id": "B0_v2a", "kind": "v2a_init", "arm": "B0", "seed": None,
                     "checkpoint_path": base["B0"]["checkpoint_path"],
                     "checkpoint_sha256": base["B0"]["checkpoint_sha256"], "training_games": 0,
                     "protected": True}
    reg["I0_incumbent"] = {"candidate_id": "I0_incumbent", "kind": "rl_ckpt", "arm": "I0",
                           "seed": 101, "checkpoint_path": base["I0"]["checkpoint_path"],
                           "checkpoint_sha256": base["I0"]["checkpoint_sha256"],
                           "training_games": base["I0"]["training_games"], "protected": True}
    reg["T_teacher"] = {"candidate_id": "T_teacher", "kind": "frozen_teacher", "arm": "T",
                        "seed": None, "checkpoint_path": base["T"]["checkpoint_path"],
                        "checkpoint_sha256": base["T"]["checkpoint_sha256"], "protected": True}
    troot = os.path.join(ART, "training")
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
                                "registered_eval_point": meta["registered_eval_point"],
                                "protected": False}
    return reg


def panel_jobs(registry, candidates, panel, deck, rng, replicate_offset=0,
               teacher_only=False):
    # §16 final panel: "If a finalist remains plausibly teacher-non-inferior, extend teacher
    # head-to-head to 800 total games." The extension is teacher-only and carries phase
    # "final" so it pools into the same estimate; the replicate offset keeps job_ids unique.
    spec = {TEACHER: PANELS[panel][TEACHER]} if teacher_only else PANELS[panel]
    jobs = []
    for cid in candidates:
        cand = registry[cid]
        for opp, per_seat in spec.items():
            for seat in (0, 1):
                for r in range(per_seat):
                    jobs.append(ce.make_job(cand, opp, seat, replicate_offset + r, panel,
                                            requested_seed=int(rng.integers(0, 1 << 30)), deck=deck))
    return jobs


def seat_stats(games, cid, opp, panel=None):
    s = {0: [], 1: []}
    for g in games:
        if (g["candidate_id"] == cid and g["opponent_id"] == opp and g["score"] is not None
                and (panel is None or g["phase"] == panel)):
            s[g["seat"]].append(g["score"])
    return s


def summarize(games, cid, rng, panel=None):
    out = {"candidate_id": cid, "panel": panel, "per_opponent": {}}
    dists = {}
    for opp in ALL_OPPS:
        s = seat_stats(games, cid, opp, panel)
        n = len(s[0]) + len(s[1])
        if n == 0:
            continue
        a0, a1 = np.asarray(s[0]), np.asarray(s[1])
        boot = np.empty(BOOT)
        for b in range(BOOT):
            m0 = a0[rng.integers(0, len(a0), len(a0))].mean() if len(a0) else np.nan
            m1 = a1[rng.integers(0, len(a1), len(a1))].mean() if len(a1) else np.nan
            boot[b] = np.nanmean([m0, m1])
        dists[opp] = boot
        out["per_opponent"][opp] = {
            "point": ns.seat_balanced_point(s[0], s[1]), "n": n,
            "n_seat0": len(s[0]), "n_seat1": len(s[1]),
            "seat0_mean": float(a0.mean()) if len(a0) else None,
            "seat1_mean": float(a1.mean()) if len(a1) else None,
            "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "one_sided_lb95": float(np.percentile(boot, 5))}
    if TEACHER in out["per_opponent"]:
        out["teacher_score"] = out["per_opponent"][TEACHER]["point"]
        out["teacher_one_sided_lb95"] = out["per_opponent"][TEACHER]["one_sided_lb95"]
    fpts = [out["per_opponent"][o]["point"] for o in FIELD if o in out["per_opponent"]]
    out["strategic_field_score"] = float(np.mean(fpts)) if fpts else None
    if len(dists) == len(ALL_OPPS):
        out["promotion_composite"] = float(sum(COMPOSITE_W[o] * out["per_opponent"][o]["point"]
                                               for o in ALL_OPPS))
        comp = sum(COMPOSITE_W[o] * dists[o] for o in ALL_OPPS)
        out["composite_ci95"] = [float(np.percentile(comp, 2.5)), float(np.percentile(comp, 97.5))]
        field = sum(dists[o] for o in FIELD) / len(FIELD)
        out["field_ci95"] = [float(np.percentile(field, 2.5)), float(np.percentile(field, 97.5))]
    dd = [g for g in games if g["candidate_id"] == cid and (panel is None or g["phase"] == panel)]
    out["reliability"] = {"games": len(dd), "defects": sum(1 for g in dd if g.get("defect")),
                          "invalid": sum(g["invalid_action_count"] for g in dd),
                          "exceptions": sum(g["exception_count"] for g in dd),
                          "timeouts": sum(g["timeout_count"] for g in dd),
                          "fallbacks": sum(g["fallback_count"] for g in dd)}
    lat = [g["latency_p99_ms"] for g in dd if g.get("latency_p99_ms") is not None]
    out["latency_p99_max_ms"] = float(np.max(lat)) if lat else None
    return out


def load_existing():
    p = os.path.join(ART, "evaluation_games.jsonl.gz")
    return [json.loads(l) for l in gzip.open(p, "rt")] if os.path.exists(p) else []


def append_games(new_games, batch_report):
    p = os.path.join(ART, "evaluation_games.jsonl.gz")
    merged = load_existing() + new_games
    with gzip.open(p, "wt") as fh:
        for g in sorted(merged, key=lambda r: r["job_id"]):
            fh.write(json.dumps(g) + "\n")
    mp_ = os.path.join(ART, "evaluation_game_manifest.json")
    man = json.load(open(mp_)) if os.path.exists(mp_) else {"identity_reports": [], "batches": []}
    cells = Counter((g["candidate_id"], g["opponent_id"], g["seat"], g["phase"]) for g in merged)
    man.update({"contract": "c010", "total_games": len(merged),
                "phases": dict(Counter(g["phase"] for g in merged)),
                "per_candidate": dict(Counter(g["candidate_id"] for g in merged)),
                "seat_balance_ok": all(cells[(c, o, 0, ph)] == cells.get((c, o, 1, ph), 0)
                                       for (c, o, s, ph) in cells if s == 0),
                "terminal": sum(1 for g in merged if g["terminal"]),
                "defects": sum(1 for g in merged if g.get("defect")),
                "raw_sha256": None})
    man["identity_reports"].append(batch_report)
    man["batches"].append({"panel": batch_report["phase"], "candidates": batch_report["candidates"],
                           "games": batch_report["n_results"]})
    man["raw_sha256"] = sha(p)
    json.dump(man, open(mp_, "w"), indent=2)
    return man


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True, choices=list(PANELS))
    p.add_argument("--candidates", required=True, help="comma-separated candidate ids, or 'ALL_NEW'")
    p.add_argument("--nproc", type=int, default=16)
    p.add_argument("--replicate-offset", type=int, default=0)
    p.add_argument("--teacher-extension", action="store_true",
                   help="teacher-only extension of an existing panel (§16, 400 -> 800 games)")
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    registry = build_candidate_registry()
    json.dump(registry, open(os.path.join(ART, "evaluation_candidate_registry.json"), "w"), indent=2)
    reg = json.load(open(os.path.join(ART, "experiment_registry.json")))

    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ce.SOURCES).deck
    deck_fp = ce.deck_fingerprint(deck)
    assert deck_fp == reg["frozen_deck_fingerprint"], "deck is not the exact frozen deck"

    existing = load_existing()
    done = {(g["candidate_id"], g["phase"]) for g in existing}
    if a.candidates == "ALL_NEW":
        cands = [c for c in registry if c != "T_teacher" and (c, a.panel) not in done]
    else:
        cands = [c.strip() for c in a.candidates.split(",") if c.strip()]
    cands = [c for c in cands if c in registry]
    if not cands:
        print(json.dumps({"panel": a.panel, "candidates": [], "note": "nothing to evaluate"}))
        return 0

    rng = np.random.default_rng(abs(hash((a.panel, tuple(cands)))) % (2 ** 32))
    off = a.replicate_offset
    if a.teacher_extension and off == 0:
        off = PANELS[a.panel][TEACHER]   # start past the replicates the base panel used
    jobs = panel_jobs(registry, cands, a.panel, deck, rng, off,
                      teacher_only=a.teacher_extension)
    existing_ids = {g["job_id"] for g in existing}
    dup = [j["job_id"] for j in jobs if j["job_id"] in existing_ids]
    assert not dup, f"job_id collision with existing evidence: {dup[:3]}"

    t0 = time.time()
    results = ce.run_jobs(jobs, a.nproc)
    rep = ce.assert_identity(jobs, results, registry, expected_deck_fingerprint=deck_fp)
    rep.update({"phase": a.panel, "candidates": cands, "wall_seconds": round(time.time() - t0, 1)})
    for r in results:
        r.pop("deck", None)
    man = append_games(results, rep)

    all_games = load_existing()
    summaries = {c: summarize(all_games, c, np.random.default_rng(4242), a.panel) for c in cands}
    sp = os.path.join(ART, f"panel_{a.panel}_summaries.json")
    prev = json.load(open(sp)) if os.path.exists(sp) else {}
    prev.update(summaries)
    json.dump(prev, open(sp, "w"), indent=2)

    with open(os.path.join(LOGD, "checkpoint_evaluation.txt"), "a") as fh:
        fh.write(f"[{a.panel}] {len(jobs)} games for {len(cands)} candidates in "
                 f"{rep['wall_seconds']}s | identity OK (terminal {rep['terminal']}, "
                 f"defects {rep['defects']})\n")
        for c in cands:
            s = summaries[c]
            fh.write(f"    {c:18s} teacher={s.get('teacher_score')} "
                     f"field={s.get('strategic_field_score')} "
                     f"composite={s.get('promotion_composite')} "
                     f"defects={s['reliability']['defects']}\n")
    print(json.dumps({"panel": a.panel, "candidates": len(cands), "games": len(jobs),
                      "identity_ok": rep["ok"], "defects": rep["defects"],
                      "total_evaluation_games": man["total_games"],
                      "wall_seconds": rep["wall_seconds"],
                      "scores": {c: {"teacher": summaries[c].get("teacher_score"),
                                     "field": summaries[c].get("strategic_field_score"),
                                     "composite": summaries[c].get("promotion_composite")}
                                 for c in cands}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

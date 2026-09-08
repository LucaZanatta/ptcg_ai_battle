"""c009 AC-05/06/07/08: staged, identity-safe evaluation of the frozen candidate registry.

Phase A  every candidate vs the frozen Dragapult teacher, 50 games/seat (100 total).
Phase B  advancing candidates extended to 200 games/seat (400 total); extended further to
         400/seat (800) only while the upper uncertainty region overlaps 0.40+.
Phase C  corrected strategic field: T, B0, best corrected R0/R1/R2 vs Mega Lucario, Iono,
         held-out Mega Abomasnow, and the Dragapult teacher mirror, 50 games/seat each.
Phase D  extension for a candidate that passes teacher non-inferiority without strategic
         collapse (does not run otherwise).

Every job carries an immutable identity that the worker returns directly; all nine §8.3
assertions run before anything is aggregated. Raw per-game records are the source of truth.
"""

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import c009_eval as ce  # noqa: E402
from cg import noninf_stats as ns  # noqa: E402

C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")
LOGD = os.path.join(C009, "results", "test_logs")
TEACHER = "dragapult"
STRATEGIC_OPPS = ["mega_lucario", "iono", "mega_abomasnow", TEACHER]  # abomasnow = held-out
HELD_OUT = "mega_abomasnow"
BOOT = 5000


# -------------------- statistics (seat-balanced bootstrap) --------------------

def seat_stats(games, rng, n_boot=BOOT):
    s0 = [g["score"] for g in games if g["seat"] == 0 and g["score"] is not None]
    s1 = [g["score"] for g in games if g["seat"] == 1 and g["score"] is not None]
    if not s0 and not s1:
        return None
    point = ns.seat_balanced_point(s0, s1)
    a0, a1 = np.asarray(s0), np.asarray(s1)
    boot = np.empty(n_boot)
    for b in range(n_boot):
        m0 = a0[rng.integers(0, len(a0), len(a0))].mean() if len(a0) else np.nan
        m1 = a1[rng.integers(0, len(a1), len(a1))].mean() if len(a1) else np.nan
        boot[b] = np.nanmean([m0, m1])
    return {"point": float(point), "n": len(s0) + len(s1), "n_seat0": len(s0), "n_seat1": len(s1),
            "seat0_mean": float(a0.mean()) if len(a0) else None,
            "seat1_mean": float(a1.mean()) if len(a1) else None,
            "seat_effect": (float(a0.mean() - a1.mean()) if len(a0) and len(a1) else None),
            "ci95_lo": float(np.percentile(boot, 2.5)), "ci95_hi": float(np.percentile(boot, 97.5)),
            "one_sided_lb95": float(np.percentile(boot, 5)),
            "one_sided_ub95": float(np.percentile(boot, 95))}


def defect_summary(games):
    return {"games": len(games),
            "terminal": sum(1 for g in games if g["terminal"]),
            "defects": sum(1 for g in games if g.get("defect")),
            "invalid_actions": sum(g["invalid_action_count"] for g in games),
            "exceptions": sum(g["exception_count"] for g in games),
            "timeouts": sum(g["timeout_count"] for g in games),
            "fallbacks": sum(g["fallback_count"] for g in games),
            "decisions": sum(g["decision_count"] for g in games)}


def latency_summary(games):
    p50 = [g["latency_p50_ms"] for g in games if g["latency_p50_ms"] is not None]
    p95 = [g["latency_p95_ms"] for g in games if g["latency_p95_ms"] is not None]
    p99 = [g["latency_p99_ms"] for g in games if g["latency_p99_ms"] is not None]
    if not p50:
        return {"per_game_p50_median_ms": None, "per_game_p95_max_ms": None,
                "per_game_p99_max_ms": None}
    return {"per_game_p50_median_ms": float(np.median(p50)),
            "per_game_p95_max_ms": float(np.max(p95)),
            "per_game_p99_max_ms": float(np.max(p99)),
            "note": "aggregated from per-game percentiles under parallel evaluation "
                    "(contention-inflated; not a single-process latency claim)"}


# -------------------- phase execution --------------------

class Runner:
    def __init__(self, registry, deck, deck_fp, nproc, log):
        self.registry = registry
        self.deck = deck
        self.deck_fp = deck_fp
        self.nproc = nproc
        self.log = log
        self.games = []            # all raw records (source of truth)
        self.identity_reports = []
        self.seen_job_ids = set()
        self.rng = np.random.default_rng(90909)

    def _emit(self, msg):
        self.log.write(msg + "\n"); self.log.flush(); print(msg)

    def run_batch(self, candidates, opponents, per_seat, phase, replicate_offset=0):
        jobs = []
        for cid in candidates:
            cand = self.registry[cid]
            for opp in opponents:
                for seat in (0, 1):
                    for r in range(per_seat):
                        rep = replicate_offset + r
                        j = ce.make_job(cand, opp, seat, rep, phase,
                                        requested_seed=int(self.rng.integers(0, 1 << 30)),
                                        deck=self.deck)
                        if j["job_id"] in self.seen_job_ids:
                            raise ce.IdentityError(f"duplicate job_id would be submitted: {j['job_id']}")
                        jobs.append(j)
        t0 = time.time()
        results = ce.run_jobs(jobs, self.nproc)
        dt = time.time() - t0
        # HARD assertions before anything is aggregated
        rep = ce.assert_identity(jobs, results, self.registry, expected_deck_fingerprint=self.deck_fp)
        rep.update({"phase": phase, "candidates": list(candidates), "opponents": list(opponents),
                    "per_seat": per_seat, "wall_seconds": round(dt, 1)})
        self.identity_reports.append(rep)
        for j in jobs:
            self.seen_job_ids.add(j["job_id"])
        for r in results:
            r.pop("deck", None)
            self.games.append(r)
        self._emit(f"[{phase}] {len(jobs)} games in {dt:.0f}s | identity OK "
                   f"(terminal {rep['terminal']}, defects {rep['defects']})")
        return results

    def candidate_games(self, cid, opponent=None, phases=None):
        return [g for g in self.games if g["candidate_id"] == cid
                and (opponent is None or g["opponent_id"] == opponent)
                and (phases is None or g["phase"] in phases)]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--nproc", type=int, default=16)
    p.add_argument("--phase-a-per-seat", type=int, default=50)
    p.add_argument("--phase-b-per-seat", type=int, default=150)   # -> 200/seat total
    p.add_argument("--phase-b-ext-per-seat", type=int, default=200)  # -> 400/seat total
    p.add_argument("--phase-c-per-seat", type=int, default=50)
    a = p.parse_args(argv)
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    log = open(os.path.join(LOGD, "corrected_evaluation_execution.txt"), "w")
    t_start = time.time()

    registry = json.load(open(os.path.join(ART, "candidate_checkpoint_registry.json")))
    from cg.teachers import make_fresh
    deck = make_fresh(TEACHER, ce.SOURCES).deck
    deck_fp = ce.deck_fingerprint(deck)
    # prove the deck is the exact frozen deck.csv
    frozen_deck = [int(x) for x in open(os.path.join(
        _REPO, "contracts", "c005_teacher_import_submission_and_dataset", "results",
        "artifacts", "frozen_teacher", "deck.csv")) if x.strip()]
    assert ce.deck_fingerprint(frozen_deck) == deck_fp, "deck is not the exact frozen deck"
    log.write(f"frozen deck fingerprint {deck_fp} ({len(deck)} cards) verified against deck.csv\n")

    R = Runner(registry, deck, deck_fp, a.nproc, log)
    rl_candidates = [c for c, v in registry.items() if v["kind"] in ("v2a_init", "rl_ckpt")]
    rl_candidates.sort(key=lambda c: (registry[c]["arm"], str(registry[c]["seed"])))
    R._emit(f"registry: {len(registry)} entries; evaluating {len(rl_candidates)} candidates vs teacher")

    # ---------------- Phase A ----------------
    R.run_batch(rl_candidates, [TEACHER], a.phase_a_per_seat, "A")
    phaseA = {}
    for cid in rl_candidates:
        g = R.candidate_games(cid, TEACHER)
        st = seat_stats(g, R.rng)
        adv_merit = (st["point"] >= 0.25) or (st["one_sided_ub95"] >= 0.35)
        mandatory = (cid == "B0_v2a") or (registry[cid]["arm"] in ("R1", "R2")
                                          and registry[cid]["is_best_within_arm_by_c008_validation"])
        phaseA[cid] = {"stats": st, "defects": defect_summary(g), "latency": latency_summary(g),
                       "advance_on_merit": bool(adv_merit), "advance_mandatory": bool(mandatory),
                       "advances": bool(adv_merit or mandatory)}
        R._emit(f"  A {cid:10s} point={st['point']:.3f} ci95=[{st['ci95_lo']:.3f},{st['ci95_hi']:.3f}] "
                f"ub95={st['one_sided_ub95']:.3f} n={st['n']} -> advance={phaseA[cid]['advances']}"
                f"{' (mandatory)' if mandatory and not adv_merit else ''}")
    advancing = [c for c in rl_candidates if phaseA[c]["advances"]]
    R._emit(f"advancing to Phase B: {advancing}")

    # ---------------- Phase B ----------------
    R.run_batch(advancing, [TEACHER], a.phase_b_per_seat, "B", replicate_offset=1000)
    phaseB = {}
    for cid in advancing:
        g = R.candidate_games(cid, TEACHER)
        st = seat_stats(g, R.rng)
        phaseB[cid] = {"stats": st, "non_inferior": st["one_sided_lb95"] >= 0.47}
        R._emit(f"  B {cid:10s} point={st['point']:.3f} lb95={st['one_sided_lb95']:.3f} "
                f"ub95={st['one_sided_ub95']:.3f} n={st['n']} non_inferior={phaseB[cid]['non_inferior']}")
    # extension only while plausibly near non-inferiority
    extend = [c for c in advancing if phaseB[c]["stats"]["one_sided_ub95"] >= 0.40]
    if extend:
        R._emit(f"extending (upper region overlaps 0.40+): {extend}")
        R.run_batch(extend, [TEACHER], a.phase_b_ext_per_seat, "B_ext", replicate_offset=5000)
        for cid in extend:
            g = R.candidate_games(cid, TEACHER)
            st = seat_stats(g, R.rng)
            phaseB[cid] = {"stats": st, "non_inferior": st["one_sided_lb95"] >= 0.47, "extended": True}
            R._emit(f"  B+ {cid:10s} point={st['point']:.3f} lb95={st['one_sided_lb95']:.3f} n={st['n']} "
                    f"non_inferior={phaseB[cid]['non_inferior']}")
    else:
        R._emit("no candidate's upper region overlaps 0.40 -> no 800-game extension (budget preserved)")

    # ---------------- corrected best per arm (teacher score first) ----------------
    def teacher_point(cid):
        return (phaseB.get(cid) or phaseA[cid])["stats"]["point"]
    best_per_arm = {}
    for arm in ("R0", "R1", "R2"):
        cands = [c for c in rl_candidates if registry[c]["arm"] == arm]
        if cands:
            best_per_arm[arm] = max(cands, key=lambda c: (teacher_point(c),
                                                          registry[c]["source_selection_metric"] or 0))
    R._emit(f"best corrected per arm (by teacher score): {best_per_arm}")

    # ---------------- Phase C: corrected strategic field ----------------
    phaseC_arms = ["T_teacher", "B0_v2a"] + [best_per_arm[a_] for a_ in ("R1", "R2", "R0") if a_ in best_per_arm]
    R._emit(f"Phase C arms: {phaseC_arms}")
    R.run_batch(phaseC_arms, STRATEGIC_OPPS, a.phase_c_per_seat, "C", replicate_offset=20000)

    # ---------------- Phase D (only if a candidate passed non-inferiority) ----------------
    qualifiers = [c for c in advancing if phaseB.get(c, {}).get("non_inferior")]
    phaseD_ran = False
    if qualifiers:
        R._emit(f"Phase D: {qualifiers} passed non-inferiority -> extending strategic comparison")
        R.run_batch(qualifiers + ["T_teacher"], STRATEGIC_OPPS, a.phase_c_per_seat, "D",
                    replicate_offset=40000)
        phaseD_ran = True
    else:
        R._emit("Phase D skipped: no candidate passed teacher non-inferiority "
                "(clearly inferior candidates are not extended to consume budget)")

    # ---------------- global identity assertion over the union ----------------
    all_ids = [g["job_id"] for g in R.games]
    assert len(all_ids) == len(set(all_ids)), "duplicate job_id in the union of all phases"

    # ---------------- write raw evidence ----------------
    raw_path = os.path.join(ART, "corrected_games.jsonl.gz")
    with gzip.open(raw_path, "wt") as fh:
        for g in sorted(R.games, key=lambda r: r["job_id"]):
            fh.write(json.dumps(g) + "\n")
    cells = Counter((g["candidate_id"], g["opponent_id"], g["seat"]) for g in R.games)
    manifest = {
        "contract": "c009", "total_games": len(R.games),
        "deck_fingerprint": deck_fp, "deck_cards": len(deck),
        "phases": dict(Counter(g["phase"] for g in R.games)),
        "per_candidate": dict(Counter(g["candidate_id"] for g in R.games)),
        "per_candidate_opponent_seat": {f"{c}|{o}|{s}": n for (c, o, s), n in sorted(cells.items())},
        "seat_balance_ok": all(cells[(c, o, 0)] == cells[(c, o, 1)]
                               for (c, o, s) in cells if s == 0),
        "identity_reports": R.identity_reports,
        "terminal": sum(1 for g in R.games if g["terminal"]),
        "defects": sum(1 for g in R.games if g.get("defect")),
        "raw_sha256": None, "wall_seconds": round(time.time() - t_start, 1),
        "phase_d_ran": phaseD_ran,
    }
    manifest["raw_sha256"] = ce.sha256_file(raw_path)
    json.dump(manifest, open(os.path.join(ART, "corrected_game_manifest.json"), "w"), indent=2)

    # ---------------- Phase A/B artifacts ----------------
    import csv
    with open(os.path.join(ART, "checkpoint_screening.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "arm", "seed", "training_games", "c008_validation_metric",
                    "phaseA_point", "phaseA_ci95_lo", "phaseA_ci95_hi", "phaseA_n",
                    "advances", "advance_reason", "final_point", "final_lb95", "final_n",
                    "non_inferior"])
        for cid in rl_candidates:
            r = registry[cid]; A = phaseA[cid]; B = phaseB.get(cid)
            fin = (B or A)["stats"]
            w.writerow([cid, r["arm"], r["seed"], r["training_games"], r["source_selection_metric"],
                        round(A["stats"]["point"], 4), round(A["stats"]["ci95_lo"], 4),
                        round(A["stats"]["ci95_hi"], 4), A["stats"]["n"], A["advances"],
                        ("merit" if A["advance_on_merit"] else ("mandatory" if A["advance_mandatory"] else "no")),
                        round(fin["point"], 4), round(fin["one_sided_lb95"], 4), fin["n"],
                        (B or {}).get("non_inferior", False)])

    per_seed = {cid: {"registry": registry[cid], "phaseA": phaseA[cid],
                      "phaseB": phaseB.get(cid), "advanced": cid in advancing}
                for cid in rl_candidates}
    json.dump(per_seed, open(os.path.join(ART, "per_seed_checkpoint_evaluation.json"), "w"), indent=2)

    b0g = R.candidate_games("B0_v2a", TEACHER)
    b0_strat = {opp: seat_stats(R.candidate_games("B0_v2a", opp), R.rng) for opp in STRATEGIC_OPPS}
    json.dump({"candidate_id": "B0_v2a",
               "checkpoint": registry["B0_v2a"]["checkpoint_path"],
               "checkpoint_sha256": registry["B0_v2a"]["checkpoint_sha256"],
               "description": registry["B0_v2a"]["description"],
               "vs_teacher": seat_stats(b0g, R.rng), "defects": defect_summary(b0g),
               "latency": latency_summary(b0g), "strategic": b0_strat},
              open(os.path.join(ART, "v2a_baseline_evaluation.json"), "w"), indent=2)

    noninf = {}
    for cid in advancing:
        g = R.candidate_games(cid, TEACHER)
        st = seat_stats(g, R.rng)
        noninf[cid] = {"stats": st, "rule": "one-sided 95% lower bound >= 0.47 (c008 rule, unchanged)",
                       "non_inferior": st["one_sided_lb95"] >= 0.47,
                       "defects": defect_summary(g), "latency": latency_summary(g),
                       "opponent": TEACHER, "phases": sorted({x["phase"] for x in g})}
    json.dump(noninf, open(os.path.join(ART, "amended_teacher_noninferiority.json"), "w"), indent=2)

    # screening + teacher logs
    with open(os.path.join(LOGD, "checkpoint_screening.txt"), "w") as fh:
        fh.write("c009 Phase A screening (all registered candidates vs frozen teacher)\n")
        for cid in rl_candidates:
            A = phaseA[cid]
            fh.write(f"  {cid:10s} point={A['stats']['point']:.4f} "
                     f"ci95=[{A['stats']['ci95_lo']:.4f},{A['stats']['ci95_hi']:.4f}] "
                     f"n={A['stats']['n']} advances={A['advances']} "
                     f"(merit={A['advance_on_merit']}, mandatory={A['advance_mandatory']})\n")
    with open(os.path.join(LOGD, "amended_teacher_execution.txt"), "w") as fh:
        fh.write("c009 teacher head-to-head (Phase A+B, identity-safe)\n")
        for cid, d in noninf.items():
            s = d["stats"]
            fh.write(f"  {cid:10s} point={s['point']:.4f} lb95={s['one_sided_lb95']:.4f} "
                     f"n={s['n']} (seat0 {s['n_seat0']} / seat1 {s['n_seat1']}) "
                     f"non_inferior={d['non_inferior']} defects={d['defects']['defects']}\n")

    json.dump({"protocol": "c009 identity-safe evaluation",
               "identity_fields": list(ce.IDENTITY_FIELDS),
               "rule": "every worker result returns the submitted identity verbatim; the worker "
                       "additionally re-hashes the checkpoint file it loaded and fingerprints the "
                       "deck it played. No positional reattachment exists anywhere in the pipeline.",
               "assertions": ["submitted job_ids unique", "returned job_ids unique",
                              "submitted set == returned set", "candidate_id in frozen registry",
                              "checkpoint hash matches registry and worker-verified hash",
                              "opponent/seat/phase/replicate/requested_seed round-trip",
                              "exact expected count per candidate/opponent/seat",
                              "no unexpected candidate/opponent/seat cells",
                              "every game terminal or explicitly defect-classified",
                              "deck fingerprint equals the frozen deck"],
               "batches": R.identity_reports,
               "all_batches_ok": all(r["ok"] for r in R.identity_reports)},
              open(os.path.join(ART, "evaluator_identity_protocol.json"), "w"), indent=2)

    R._emit(f"TOTAL evaluation games: {len(R.games)} in {manifest['wall_seconds']}s "
            f"(terminal {manifest['terminal']}, defects {manifest['defects']})")
    log.close()
    print(json.dumps({"total_games": len(R.games), "advancing": advancing,
                      "best_per_arm": best_per_arm,
                      "non_inferior": {c: noninf[c]["non_inferior"] for c in noninf},
                      "phase_d_ran": phaseD_ran}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

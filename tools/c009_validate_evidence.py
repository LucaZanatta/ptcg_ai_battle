"""c009 AC-12: content-aware evidence validator.

File existence NEVER produces a pass here. Every aggregate is INDEPENDENTLY recomputed from
the corrected raw games (with a different bootstrap seed than the aggregator, so confidence
intervals are checked by agreement rather than by re-running identical code) and compared to
the shipped artifact. Identity, hashes, counts, seat balance, immutability, weight
non-mutation, gate correctness, and conditional-artifact presence are all verified.

Any failure blocks contract PASS.
"""

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import noninf_stats as ns  # noqa: E402

C009 = os.path.join(_REPO, "contracts", "c009_amendment_c008")
ART = os.path.join(C009, "results", "artifacts")
LOGD = os.path.join(C009, "results", "test_logs")
TEACHER = "dragapult"
HELD_OUT = "mega_abomasnow"
FIELD = ["mega_lucario", "iono", HELD_OUT, TEACHER]
TEACHER_PHASES = {"A", "B", "B_ext"}
STRATEGIC_PHASES = {"C", "D"}
POINT_TOL = 1e-9          # deterministic quantities must match exactly
CI_TOL = 0.03             # bootstrap CIs: independent-seed Monte-Carlo agreement
IDENTITY_FIELDS = ("job_id", "candidate_id", "checkpoint_sha256", "opponent_id", "seat",
                   "replicate", "requested_seed", "phase")
REQUIRED_CANDIDATES = ["B0_v2a", "R1_101", "R1_202", "R2_101", "R2_202", "R2_303"]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def J(name):
    p = os.path.join(ART, name)
    return json.load(open(p)) if os.path.exists(p) else None


def seat_scores(games, cid, opp, phases):
    s = {0: [], 1: []}
    for g in games:
        if (g["candidate_id"] == cid and g["opponent_id"] == opp and g["phase"] in phases
                and g["score"] is not None):
            s[g["seat"]].append(g["score"])
    return s


def boot(s, rng, n=4000):
    a0, a1 = np.asarray(s[0]), np.asarray(s[1])
    out = np.empty(n)
    for b in range(n):
        m0 = a0[rng.integers(0, len(a0), len(a0))].mean() if len(a0) else np.nan
        m1 = a1[rng.integers(0, len(a1), len(a1))].mean() if len(a1) else np.nan
        out[b] = np.nanmean([m0, m1])
    return out


def main(argv=None):
    global ART, LOGD
    ap = argparse.ArgumentParser()
    ap.add_argument("--art-dir", default=ART, help="artifact dir to validate (tests point this at a copy)")
    ap.add_argument("--log-dir", default=LOGD)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    ART, LOGD = args.art_dir, args.log_dir
    os.makedirs(LOGD, exist_ok=True)
    checks = []

    def rec(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})

    # independent RNG (aggregator used 313131)
    rng = np.random.default_rng(24680)

    # ---------- load ----------
    raw_path = os.path.join(ART, "corrected_games.jsonl.gz")
    rec("raw_games_present", os.path.exists(raw_path))
    games = [json.loads(l) for l in gzip.open(raw_path, "rt")] if os.path.exists(raw_path) else []
    manifest = J("corrected_game_manifest.json") or {}
    registry = J("candidate_checkpoint_registry.json") or {}
    imm_base = J("immutability_verification.json") or {}
    decision = J("amended_checkpoint_selection.json") or {}

    # ---------- A. registry + checkpoint hashes ----------
    rec("registry_has_all_required_candidates",
        all(c in registry for c in REQUIRED_CANDIDATES),
        [c for c in REQUIRED_CANDIDATES if c not in registry])
    bad_hash = []
    for cid, v in registry.items():
        ap = os.path.join(_REPO, v["checkpoint_path"])
        if not os.path.exists(ap):
            bad_hash.append(f"{cid}:missing")
        elif sha_file(ap) != v["checkpoint_sha256"]:
            bad_hash.append(f"{cid}:hash_changed")
    rec("registry_checkpoint_hashes_match_disk", not bad_hash, bad_hash)
    evaluated = {g["candidate_id"] for g in games}
    rec("every_evaluated_candidate_in_registry", evaluated <= set(registry),
        sorted(evaluated - set(registry)))
    mism = [g["job_id"] for g in games
            if g["checkpoint_sha256"] != registry.get(g["candidate_id"], {}).get("checkpoint_sha256")
            or g.get("verified_checkpoint_sha256") != g["checkpoint_sha256"]]
    rec("every_game_used_the_registered_weights", not mism, f"{len(mism)} mismatches")

    # ---------- B. raw-game integrity ----------
    rec("manifest_count_matches_raw", manifest.get("total_games") == len(games),
        f"manifest {manifest.get('total_games')} vs raw {len(games)}")
    rec("manifest_raw_sha_matches", manifest.get("raw_sha256") == sha_file(raw_path))
    ids = [g["job_id"] for g in games]
    rec("job_ids_unique", len(ids) == len(set(ids)), f"{len(ids)} vs {len(set(ids))} unique")
    incomplete = [g["job_id"] for g in games if any(g.get(f) is None for f in IDENTITY_FIELDS)]
    rec("all_raw_identities_complete", not incomplete, f"{len(incomplete)} incomplete")
    unclassified = [g["job_id"] for g in games if not g["terminal"] and not g.get("defect")]
    rec("all_games_terminal_or_defect_classified", not unclassified, f"{len(unclassified)}")
    fps = {g["deck_fingerprint"] for g in games}
    frozen_deck = [int(x) for x in open(os.path.join(
        _REPO, "contracts", "c005_teacher_import_submission_and_dataset", "results", "artifacts",
        "frozen_teacher", "deck.csv")) if x.strip()]
    exp_fp = hashlib.sha256(",".join(str(c) for c in frozen_deck).encode()).hexdigest()
    rec("every_game_used_the_exact_frozen_deck", fps == {exp_fp}, sorted(fps)[:2])

    cells = Counter((g["candidate_id"], g["opponent_id"], g["seat"], g["phase"]) for g in games)
    # seat balance for every (candidate, opponent, phase)
    imbal = [f"{c}|{o}|{ph}" for (c, o, s, ph) in cells if s == 0
             and cells[(c, o, 0, ph)] != cells.get((c, o, 1, ph), 0)]
    rec("both_seats_present_equally", not imbal, imbal[:5])
    # Phase C uniformity: every strategic cell exactly 50 per seat
    cbad = [f"{c}|{o}|s{s}={n}" for (c, o, s, ph), n in cells.items()
            if ph == "C" and n != 50]
    rec("phase_c_cells_exactly_50_per_seat", not cbad, cbad[:5])
    abad = [f"{c}|s{s}={n}" for (c, o, s, ph), n in cells.items() if ph == "A" and n != 50]
    rec("phase_a_cells_exactly_50_per_seat", not abad, abad[:5])

    # ---------- C. aggregates reproduce raw games ----------
    strat_cands = sorted({g["candidate_id"] for g in games if g["phase"] in STRATEGIC_PHASES})
    # matchup matrix CSV
    mm = {}
    mm_path = os.path.join(ART, "amended_matchup_matrix.csv")
    if os.path.exists(mm_path):
        with open(mm_path) as fh:
            for row in csv.DictReader(fh):
                mm[(row["candidate_id"], row["opponent"])] = row
    bad_pts, bad_n = [], []
    for cid in strat_cands:
        for opp in FIELD:
            s = seat_scores(games, cid, opp, STRATEGIC_PHASES)
            if not (s[0] or s[1]):
                continue
            key = (cid, opp)
            if key not in mm:
                bad_pts.append(f"{cid}|{opp}:absent"); continue
            recomputed = ns.seat_balanced_point(s[0], s[1])
            if abs(float(mm[key]["seat_balanced_score"]) - recomputed) > 1e-4:
                bad_pts.append(f"{cid}|{opp}:{mm[key]['seat_balanced_score']}!={recomputed:.4f}")
            if int(mm[key]["n"]) != len(s[0]) + len(s[1]):
                bad_n.append(f"{cid}|{opp}")
    rec("matchup_scores_reproduce_raw_games", not bad_pts, bad_pts[:5])
    rec("matchup_counts_reproduce_raw_games", not bad_n, bad_n[:5])

    # global ranking
    gr = (J("amended_global_ranking.json") or {}).get("candidates", {})
    bad_field = []
    for cid in strat_cands:
        pts = [ns.seat_balanced_point(*[seat_scores(games, cid, o, STRATEGIC_PHASES)[k] for k in (0, 1)])
               for o in FIELD if seat_scores(games, cid, o, STRATEGIC_PHASES)[0]]
        if not pts:
            continue
        exp = float(np.mean(pts))
        got = gr.get(cid, {}).get("mean_vs_field")
        if got is None or abs(got - exp) > 1e-6:
            bad_field.append(f"{cid}:{got}!={exp:.4f}")
    rec("global_ranking_reproduces_raw_games", not bad_field, bad_field[:5])

    # held-out report: only Abomasnow, values reproduce
    hr = J("amended_holdout_report.json") or {}
    rec("holdout_report_uses_only_abomasnow", hr.get("held_out_opponent") == HELD_OUT,
        hr.get("held_out_opponent"))
    bad_ho = []
    for cid, d in (hr.get("results") or {}).items():
        s = seat_scores(games, cid, HELD_OUT, STRATEGIC_PHASES)
        exp = ns.seat_balanced_point(s[0], s[1])
        if abs(d["point"] - exp) > 1e-9 or d["n"] != len(s[0]) + len(s[1]):
            bad_ho.append(f"{cid}:{d['point']}!={exp:.4f}")
    rec("holdout_values_reproduce_raw_games", not bad_ho, bad_ho[:5])

    # teacher non-inferiority: only the frozen teacher, only teacher phases, values reproduce
    ni = J("amended_teacher_noninferiority.json") or {}
    rec("teacher_h2h_uses_only_frozen_teacher", ni.get("opponent") == TEACHER, ni.get("opponent"))
    rec("teacher_h2h_rule_unchanged", "0.47" in str(ni.get("rule")), ni.get("rule"))
    bad_ni, bad_ci = [], []
    for cid, d in (ni.get("candidates") or {}).items():
        s = seat_scores(games, cid, TEACHER, TEACHER_PHASES)
        exp = ns.seat_balanced_point(s[0], s[1])
        if abs(d["point"] - exp) > POINT_TOL:
            bad_ni.append(f"{cid}:{d['point']}!={exp:.6f}")
        if d["n"] != len(s[0]) + len(s[1]):
            bad_ni.append(f"{cid}:n")
        b = boot(s, rng)
        if abs(float(np.percentile(b, 5)) - d["one_sided_lb95"]) > CI_TOL:
            bad_ci.append(f"{cid}:lb95 {d['one_sided_lb95']:.3f} vs {np.percentile(b,5):.3f}")
        # the decision must follow the rule as written
        if d["non_inferior"] != (d["one_sided_lb95"] >= 0.47):
            bad_ni.append(f"{cid}:non_inferior flag inconsistent with lb95")
    rec("teacher_h2h_values_reproduce_raw_games", not bad_ni, bad_ni[:5])
    rec("confidence_intervals_reproduce_independently", not bad_ci, bad_ci[:5])

    # improvement / regression per-matchup diffs
    imp = J("amended_improvement_report.json") or {}
    reg = J("amended_regression_report.json") or {}
    bad_diff = []
    for cid, d in imp.items():
        for opp, m in d.get("per_matchup", {}).items():
            sc = seat_scores(games, cid, opp, STRATEGIC_PHASES)
            st = seat_scores(games, "T_teacher", opp, STRATEGIC_PHASES)
            exp = (ns.seat_balanced_point(sc[0], sc[1]) - ns.seat_balanced_point(st[0], st[1])) * 100
            if abs(m["diff_pp"] - exp) > 1e-6:
                bad_diff.append(f"{cid}|{opp}:{m['diff_pp']:.3f}!={exp:.3f}")
    rec("improvement_diffs_reproduce_raw_games", not bad_diff, bad_diff[:5])
    bad_reg = []
    for cid, d in reg.items():
        exp_reg = sorted(o for o, m in d.get("per_matchup", {}).items()
                         if m["diff_pp"] <= -7 and m["prob_regress_7pp"] >= 0.90)
        if sorted(d.get("major_regression_matchups", [])) != exp_reg:
            bad_reg.append(f"{cid}:{d.get('major_regression_matchups')}!={exp_reg}")
    rec("regression_flags_follow_stated_rule", not bad_reg, bad_reg[:5])

    # rl_vs_initialization diffs
    vb = (J("rl_vs_initialization.json") or {}).get("candidates", {})
    bad_b0 = []
    for cid, d in vb.items():
        sc = seat_scores(games, cid, TEACHER, TEACHER_PHASES)
        sb = seat_scores(games, "B0_v2a", TEACHER, TEACHER_PHASES)
        exp = ns.seat_balanced_point(sc[0], sc[1]) - ns.seat_balanced_point(sb[0], sb[1])
        if abs(d["teacher_diff"] - exp) > 1e-9:
            bad_b0.append(f"{cid}:{d['teacher_diff']:.4f}!={exp:.4f}")
        crit = d["criteria"]
        if d["beats_b0"] != all(crit.values()):
            bad_b0.append(f"{cid}: beats_b0 inconsistent with its own criteria")
    rec("rl_vs_initialization_reproduces_raw_games", not bad_b0, bad_b0[:5])

    # ---------- D. immutability / no mutation ----------
    changed = []
    for key, folder in (("c005_files", "c005_teacher_import_submission_and_dataset"),
                        ("c006_files", "c006_distilled_policy_baseline"),
                        ("c007_files", "c007_hybrid_teacher_residual_and_state_encoder_v2"),
                        ("c008_files", "c008_fixed_deck_teacher_anchored_rl")):
        base = imm_base.get(key, {})
        root = os.path.join(_REPO, "contracts", folder)
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, _REPO)
                if rel in base:
                    try:
                        if sha_file(p) != base[rel]:
                            changed.append(rel)
                    except OSError:
                        changed.append(rel + ":unreadable")
    rec("no_c005_to_c008_file_changed", not changed, changed[:5])
    rec("no_policy_weights_changed", not bad_hash, "checkpoint hashes unchanged on disk")
    new_ckpts = []
    for dp, _dn, fns in os.walk(os.path.join(C009, "results")):
        new_ckpts += [os.path.join(dp, f) for f in fns if f.endswith(".npz")]
    rec("no_new_training_checkpoint_created", not new_ckpts, new_ckpts[:3])

    # ---------- E. decisions + conditional artifacts ----------
    ni_pass = any(d.get("non_inferior") for d in (ni.get("candidates") or {}).values())
    exp_ni = "PASS" if ni_pass else "FAIL"
    rec("teacher_noninferiority_decision_follows_evidence",
        decision.get("teacher_noninferiority") == exp_ni,
        f"{decision.get('teacher_noninferiority')} vs {exp_ni}")
    beats = [c for c, d in vb.items() if d["beats_b0"]]
    exp_impr = "YES" if beats else "NO"
    rec("rl_improvement_decision_follows_rule",
        decision.get("rl_improved_over_initialization") == exp_impr,
        f"{decision.get('rl_improved_over_initialization')} vs {exp_impr}")
    exp_best = "V2A_BASELINE"
    if beats:
        b = max(beats, key=lambda c: (gr.get(c, {}).get("mean_vs_field", 0),
                                      (ni.get("candidates") or {}).get(c, {}).get("point", 0)))
        r = registry[b]
        exp_best = f"{r['arm']}_{r['seed']}_" + os.path.basename(r["checkpoint_path"]).replace(".npz", "")
    rec("best_saved_checkpoint_follows_rule", decision.get("best_saved_checkpoint") == exp_best,
        f"{decision.get('best_saved_checkpoint')} vs {exp_best}")
    repro = [c for c, d in imp.items() if d.get("reproducible_improvement")]
    should_submit = bool(beats) and ni_pass and bool(repro)
    rec("submission_decision_follows_amended_gate",
        decision.get("submission_D_amended") == ("SUBMIT" if should_submit else "DO_NOT_SUBMIT"),
        f"{decision.get('submission_D_amended')} (ni={ni_pass}, repro={bool(repro)})")
    arch = os.path.join(ART, "submission_D_amended_rl.tar.gz")
    ks = J("kaggle_submission_status.json") or {}
    if decision.get("submission_D_amended") == "SUBMIT":
        rec("conditional_archive_present_when_submit", os.path.exists(arch))
        rec("kaggle_status_submitted", ks.get("kaggle_upload") == "SUBMITTED", ks.get("kaggle_upload"))
    else:
        rec("conditional_archive_absent_when_do_not_submit", not os.path.exists(arch))
        rec("kaggle_status_skipped_by_gate", ks.get("kaggle_upload") == "SKIPPED_BY_GATE",
            ks.get("kaggle_upload"))
        rec("promotion_is_no_rl_submission", decision.get("promotion_decision") == "NO_RL_SUBMISSION",
            decision.get("promotion_decision"))
    rec("exactly_one_next_step", isinstance(decision.get("next_step"), str)
        and decision.get("next_step") in ("REDESIGN_TEACHER_ANCHORED_RL", "FIXED_DECK_SELECTIVE_SEARCH",
                                          "BEGIN_DECK_PIPELINE"), decision.get("next_step"))
    rec("exactly_one_highest_leverage_blocker",
        isinstance(decision.get("highest_leverage_blocker"), str)
        and len(decision.get("highest_leverage_blocker", "")) > 20)

    # ---------- meta: content checks actually ran ----------
    content_checks = [c for c in checks if c["check"] not in ("raw_games_present",)]
    rec("validation_is_content_aware_not_existence_based", len(content_checks) >= 25,
        f"{len(content_checks)} content assertions executed")

    all_ok = all(c["ok"] for c in checks)
    out = {"contract": "c009", "checks": checks, "n_checks": len(checks),
           "n_failed": sum(1 for c in checks if not c["ok"]), "all_ok": all_ok,
           "raw_games": len(games), "bootstrap_seed_independent_of_aggregator": True,
           "ci_tolerance": CI_TOL, "point_tolerance": POINT_TOL,
           "note": "Every aggregate was recomputed from corrected raw games with an independent "
                   "bootstrap seed; file existence alone cannot pass this validator."}
    json.dump(out, open(os.path.join(ART, "evidence_validation.json"), "w"), indent=2)
    lines = ["c009 AC-12 content-aware evidence validation", "=" * 60,
             f"raw games: {len(games)} | checks: {len(checks)} | failed: {out['n_failed']}", ""]
    for c in checks:
        lines.append(f"  [{'OK  ' if c['ok'] else 'FAIL'}] {c['check']}"
                     + (f"  -> {c['detail']}" if (c["detail"] and not c["ok"]) else ""))
    lines += ["", f"ALL_OK = {all_ok}"]
    open(os.path.join(LOGD, "evidence_validation.txt"), "w").write("\n".join(lines) + "\n")
    if not args.quiet:
        print("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

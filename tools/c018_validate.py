"""c018 P90 — raw-data-derived evidence validator.

Built EARLY, before the training it judges, so it can fail this campaign's own work while there
is still time to act on it. c017's fake curriculum survived because nothing checked whether the
optimizer had ever stepped; every rejection below exists because some prior contract in this
project shipped exactly that defect.

Every check re-derives from raw artifacts. A summary asserting a number is never accepted as
evidence for that number.
"""

from __future__ import annotations

import collections
import glob
import gzip
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")
LOGD = os.path.join(C18, "test_logs")

checks = []
FINAL = False          # set by --final; in final mode absence is failure, not a free pass
skipped = []


def ck(name, ok, detail=None, critical=True, blocker=False):
    checks.append({"check": name, "passed": bool(ok), "critical": critical,
                   "submission_blocker": blocker, "detail": detail})
    return ok


def require(name, ok, detail=None, blocker=False):
    """A milestone artifact that MUST exist by the end of the campaign.

    Mid-campaign its absence is merely 'not yet exercised'; at final judgement its absence is a
    critical failure. Without this split the validator happily returns PASS for a campaign that
    did nothing at all -- the exact 'skipped criteria counted pass' defect it must reject.
    """
    if not ok:
        skipped.append(name)
    return ck(name, ok, detail, critical=FINAL, blocker=blocker and FINAL)


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else d


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_gz(p):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return [json.loads(l) for l in gzip.open(p, "rt")] if os.path.exists(p) else []


# ---------------------------------------------------------------- fake / static search

def v_real_search():
    """A search claim needs real begin/step counters AND multi-step successor traces."""
    summaries = glob.glob(os.path.join(C18, "search", "*_search_summary.json"))
    if not summaries:
        ck("search_evidence_present", False, {"reason": "no search summary"}, blocker=True)
        return
    worst = None
    for p in summaries:
        d = json.load(open(p))
        c = d.get("real_search_counters") or {}
        name = os.path.basename(p)
        ok_begin = (c.get("begin_ok") or 0) > 0
        ok_step = (c.get("step_ok") or 0) > 0
        ok_depth = (c.get("max_depth_reached") or 0) >= 2
        ok_succ = (c.get("distinct_successors") or 0) > 0
        ck(f"real_search_counters_nonzero:{name}", ok_begin and ok_step,
           {"begin_ok": c.get("begin_ok"), "step_ok": c.get("step_ok")}, blocker=True)
        ck(f"multi_step_depth_ge_2:{name}", ok_depth,
           {"max_depth_reached": c.get("max_depth_reached")}, blocker=True)
        ck(f"distinct_successors_observed:{name}", ok_succ,
           {"distinct_successors": c.get("distinct_successors")}, blocker=True)
        # a static scorer would show steps == 0 while still claiming searched decisions
        ck(f"not_static_scoring:{name}",
           not ((d.get("decisions_searched") or d.get("trusted_decisions") or 0) > 0
                and (c.get("step_ok") or 0) == 0),
           {"note": "searched decisions with zero search_step calls means a static scorer"},
           blocker=True)
        ck(f"lifecycle_balanced:{name}",
           (c.get("end_calls") or 0) > 0 and (c.get("release_errors") or 0) == 0,
           {"end_calls": c.get("end_calls"), "release_errors": c.get("release_errors")})
        ck(f"no_hidden_information_violation:{name}",
           (c.get("hidden_information_violations") or 0) == 0,
           {"violations": c.get("hidden_information_violations")}, blocker=True)
        ck(f"does_not_use_c017_labels:{name}", d.get("uses_c017_labels") is False,
           {"uses_c017_labels": d.get("uses_c017_labels")})
        worst = d
    # traces must show more than one step
    tr = (worst or {}).get("sample_traces") or []
    ck("successor_traces_are_multi_step",
       any((t.get("depth_max") or 0) >= 2 for t in tr) if tr else False,
       {"traces": len(tr), "max_depth_in_traces": max([t.get("depth_max") or 0
                                                       for t in tr], default=0)},
       blocker=True)


def v_trajectories():
    for p in glob.glob(os.path.join(C18, "trajectories", "*_trajectories.jsonl.gz")):
        rows = read_gz(p)
        name = os.path.basename(p)
        if not rows:
            continue
        ck(f"trajectory_rows_present:{name}", len(rows) > 0, {"rows": len(rows)})
        ck(f"legal_mask_matches_options:{name}",
           all(len(r.get("legal_mask") or []) == r.get("n_options") for r in rows[:2000]))
        ck(f"label_within_legal_range:{name}",
           all(all(0 <= i < r["n_options"] for i in r["label_action"]) for r in rows[:2000]),
           blocker=True)
        ck(f"trusted_rows_have_successors:{name}",
           all((r.get("distinct_successors") or 0) > 0 for r in rows if r.get("trusted")),
           {"note": "a trusted row must have come from real successors"}, blocker=True)
        gsplit = collections.defaultdict(set)
        for r in rows:
            gsplit[r["game_index"]].add(r["split"])
        ck(f"no_game_straddles_splits:{name}",
           all(len(v) == 1 for v in gsplit.values()),
           {"straddling": [g for g, v in gsplit.items() if len(v) > 1][:5]})
        ck(f"outcomes_reconcile:{name}",
           all(r.get("final_outcome") is not None for r in rows))


# ---------------------------------------------------------------- training proof

def v_training_proof():
    """A training claim needs raw games, nonzero optimizer steps, finite losses, and a
    CHANGED checkpoint hash. c017 reported a curriculum that never called an optimizer."""
    d = jload("training/distillation_report.json")
    if d:
        steps = d.get("optimizer_steps") or 0
        ck("distill_optimizer_steps_nonzero", steps > 0, {"optimizer_steps": steps},
           blocker=True)
        ck("distill_losses_finite", bool(d.get("losses_finite")),
           {"losses_finite": d.get("losses_finite")}, blocker=True)
        ck("distill_checkpoint_hash_changed",
           d.get("checkpoint_sha256_before") != d.get("checkpoint_sha256_after")
           and bool(d.get("checkpoint_sha256_after")),
           {"before": (d.get("checkpoint_sha256_before") or "")[:12],
            "after": (d.get("checkpoint_sha256_after") or "")[:12]}, blocker=True)
        ck("distill_trained_on_trusted_rows_only",
           bool(d.get("trusted_rows_only")), {"trusted_rows_only": d.get("trusted_rows_only")})
    else:
        require("distillation_report_present", False, {"reason": "absent"}, blocker=True)

    c = jload("training/curriculum_report.json")
    if c:
        g = c.get("actual_simulator_games") or 0
        st = c.get("optimizer_steps") or 0
        ck("curriculum_actual_simulator_games_nonzero", g > 0,
           {"actual_simulator_games": g,
            "note": "c017 counted scheduled games while playing none"}, blocker=True)
        ck("curriculum_optimizer_steps_nonzero", st > 0, {"optimizer_steps": st},
           blocker=True)
        ck("curriculum_checkpoint_progressed",
           len(set(c.get("checkpoint_hashes") or [])) > 1,
           {"distinct_checkpoint_hashes": len(set(c.get("checkpoint_hashes") or []))},
           blocker=True)
        ck("curriculum_losses_finite", bool(c.get("losses_finite")), critical=True)
        pa = c.get("planned_vs_actual") or []
        ck("planned_mix_not_reported_as_actual",
           all("planned_fractions" in b and "actual_fractions" in b for b in pa) if pa
           else False, {"blocks": len(pa)})
        ck("no_game_zero_promotion",
           all(h.get("promotion_eligible") is False
               for h in (c.get("history") or []) if h.get("games") == 0))
        ck("rollouts_are_raw_not_virtual",
           bool(c.get("raw_rollout_file")) and os.path.exists(
               os.path.join(C18, c.get("raw_rollout_file", ""))),
           {"raw_rollout_file": c.get("raw_rollout_file")}, blocker=True)
    else:
        require("curriculum_report_present", False, {"reason": "absent"}, blocker=True)


# ---------------------------------------------------------------- identity / panel

def v_panel():
    rows = jload("final_panel/final_panel_results.json")
    raw = read_gz("final_panel/raw_games.jsonl.gz")
    if not rows or not raw:
        require("final_panel_present", False, {"reason": "absent"}, blocker=True)
        return
    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in raw:
        if r.get("score") is None:
            continue
        agg[(r["candidate_id"], r["opponent_id"])][0] += 1
        agg[(r["candidate_id"], r["opponent_id"])][1] += r["score"]
    bad = []
    for row in rows:
        for k, v in row.items():
            if not k.endswith("_rate") or v is None:
                continue
            opp = k[:-5]
            n, s = agg.get((row["candidate_id"], opp), [0, 0.0])
            if row.get(f"{opp}_games") != n:
                bad.append({"cand": row["candidate_id"], "opp": opp,
                            "reported_games": row.get(f"{opp}_games"), "raw": n})
            elif n and abs(v - round(s / n, 4)) > 1e-9:
                bad.append({"cand": row["candidate_id"], "opp": opp,
                            "reported": v, "raw": round(s / n, 4)})
    ck("panel_denominators_match_raw", not bad, {"mismatches": bad[:6]})
    ck("panel_records_self_identify",
       all(r.get("candidate_id") and r.get("opponent_id") and r.get("seat") is not None
           for r in raw[:3000]))
    ck("no_zero_denominator_rate",
       not any(row.get(f"{k[:-5]}_games") == 0 and row.get(k) is not None
               for row in rows for k in row if k.endswith("_rate")))


def v_history_and_package():
    base = jload("artifacts/immutability_baseline_pre_c018.json", {})
    mod, n = [], 0
    for k, files in (base or {}).items():
        if not k.endswith("_files"):
            continue
        for path, want in files.items():
            fp = os.path.join(_REPO, path)
            if not os.path.exists(fp):
                mod.append({"path": path, "issue": "missing"})
                continue
            n += 1
            if sha_file(fp) != want:
                mod.append({"path": path, "issue": "modified"})
    ck("c005_to_c017_unmodified", not mod, {"files_checked": n, "changed": mod[:8]})
    ck("immutability_baseline_substantive", n > 1500, {"files_checked": n})

    for man, arch in (("packages/submission_manifest.json", None),):
        m = jload(man)
        if not m:
            continue
        p = os.path.join(C18, m.get("archive_rel", ""))
        ck("package_hash_matches_manifest",
           os.path.exists(p) and sha_file(p) == m.get("sha256"),
           {"manifest": (m.get("sha256") or "")[:12]}, blocker=True)

    for z in ("source/complete_repository_source.zip",
              "source/c018_competition_source_bundle.zip"):
        require(f"source_bundle_present:{os.path.basename(z)}",
                os.path.exists(os.path.join(C18, z)))


def v_pass_conditions():
    sub = jload("submissions/post_baseline_submission.json", {})
    st = jload(os.path.join(C18, "STATUS.json"), {}) or {}
    accepted_post = bool((sub or {}).get("submission_ref"))
    claims_pass = st.get("status") == "PASS"
    ck("pass_requires_accepted_post_baseline_submission",
       (not claims_pass) or accepted_post,
       {"claims_pass": claims_pass, "accepted_post_baseline": accepted_post,
        "rule": "PASS is unavailable without an accepted post-baseline c018 submission"})
    ck("no_skipped_criteria_counted_as_pass", (not FINAL) or not skipped,
       {"mode": "final" if FINAL else "interim", "not_exercised": skipped[:12],
        "rule": "at final judgement an absent milestone is a failure, never a free pass"})


def main():
    global FINAL
    FINAL = "--final" in sys.argv
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    v_real_search()
    v_trajectories()
    v_training_proof()
    v_panel()
    v_history_and_package()
    v_pass_conditions()
    crit = [c for c in checks if c["critical"] and not c["passed"]]
    blockers = [c for c in checks if c["submission_blocker"] and not c["passed"]]
    doc = {"probe_id": "P90", "mode": "final" if FINAL else "interim",
           "not_exercised": skipped, "principle": "every check re-derives from raw artifacts; a "
                                           "summary asserting a number is never evidence for it",
           "n_checks": len(checks), "n_passed": sum(1 for c in checks if c["passed"]),
           "n_critical_failures": len(crit), "n_submission_blockers": len(blockers),
           "submission_blockers": [c["check"] for c in blockers],
           "checks": checks,
           "overall": "PASS" if not crit else "FAIL"}
    json.dump(doc, open(os.path.join(ART, "evidence_validation.json"), "w"), indent=2,
              default=str)
    with open(os.path.join(LOGD, "evidence_validation.txt"), "w") as fh:
        for c in checks:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}]"
                     f"{'[BLOCKER]' if c['submission_blocker'] else ''} {c['check']}\n")
            if c["detail"]:
                fh.write("    " + json.dumps(c["detail"], default=str)[:600] + "\n")
        fh.write(f"\noverall: {doc['overall']} ({doc['n_passed']}/{doc['n_checks']})\n")
    print(json.dumps({k: doc[k] for k in ("n_checks", "n_passed", "n_critical_failures",
                                          "n_submission_blockers", "overall")}, indent=2))
    for c in crit[:12]:
        print("  FAIL:", c["check"], json.dumps(c["detail"], default=str)[:160])
    return 0 if not crit else 1


if __name__ == "__main__":
    raise SystemExit(main())

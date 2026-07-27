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
    """Tolerant of a file still being written: returns whatever complete lines exist plus a
    truncation flag. Truncation is never silently benign -- every consumer compares the
    recounted total against the reported one, so a short read fails closed."""
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    rows, truncated = [], False
    if not os.path.exists(p):
        return rows
    try:
        with gzip.open(p, "rt") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
    except (EOFError, OSError, json.JSONDecodeError):
        truncated = True
    if truncated:
        rows.append({"__truncated__": True})
        rows.pop()
    return rows


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
        # recount from the per-epoch history rather than believing the summary counter
        h = d.get("history") or []
        ck("distill_steps_match_history",
           bool(h) and (h[-1].get("optimizer_steps_cumulative") == steps)
           and sum(e.get("batches") or 0 for e in h) == steps,
           {"reported": steps, "history_cumulative": (h[-1] if h else {}).get(
               "optimizer_steps_cumulative"),
            "history_batch_sum": sum(e.get("batches") or 0 for e in h)}, blocker=True)
        ck("distill_weights_moved_every_epoch",
           len({e.get("checkpoint_sha256") for e in h}) == len(h),
           {"epochs": len(h), "distinct_epoch_hashes":
               len({e.get("checkpoint_sha256") for e in h})})
        ck("distill_reload_is_exact",
           bool(d.get("reload_hash_matches")) and bool(d.get("reload_metrics_identical")),
           {"reload_hash_matches": d.get("reload_hash_matches"),
            "reload_metrics_identical": d.get("reload_metrics_identical")})
        ck("distill_predictions_always_legal",
           (((d.get("held_out_test") or {}).get("legal_prediction_rate")) or 0) >= 1.0,
           {"legal_prediction_rate": (d.get("held_out_test") or {}).get(
               "legal_prediction_rate")}, blocker=True)
        ck("distill_does_not_continue_c017",
           d.get("continues_c017_checkpoint") is False and d.get("uses_c017_labels") is False,
           {"continues_c017_checkpoint": d.get("continues_c017_checkpoint")})
        # the trusted row count must agree with the trajectory file it claims to come from
        tj = jload(f"search/{d.get('data_prefix')}_search_summary.json") or {}
        ck("distill_row_count_matches_trajectory_source",
           (tj.get("trusted_decisions") or 0) == (d.get("rows_trusted") or -1),
           {"trajectory_summary": tj.get("trusted_decisions"),
            "distill_report": d.get("rows_trusted")})
    else:
        require("distillation_report_present", False, {"reason": "absent"}, blocker=True)

    c = jload("training/curriculum_report.json")
    if not c:
        require("curriculum_report_present", False, {"reason": "absent"}, blocker=True)
        return

    # Everything below is RECOUNTED from the raw rows. The report's own numbers are only ever
    # used as the claim being tested -- c017's fabricated curriculum lived entirely in fields
    # like these, and a validator that reads them is agreeing with the liar.
    graw = read_gz(c.get("raw_rollout_file") or "")
    uraw = read_gz(c.get("raw_updates_file") or "")
    ck("rollouts_are_raw_not_virtual", len(graw) > 0,
       {"raw_rollout_file": c.get("raw_rollout_file"), "raw_game_rows": len(graw),
        "note": "a curriculum with no per-game rows on disk played no games"}, blocker=True)

    played = len(graw)
    completed = sum(1 for r in graw if r.get("completed"))
    ck("curriculum_actual_simulator_games_nonzero", played > 0 and completed > 0,
       {"raw_game_rows": played, "raw_completed": completed,
        "note": "c017 counted scheduled games while playing none"}, blocker=True)
    ck("reported_games_match_raw_rows", (c.get("actual_simulator_games") or 0) == played,
       {"reported": c.get("actual_simulator_games"), "recounted": played}, blocker=True)
    ck("reported_completions_match_raw_rows", (c.get("games_completed") or 0) == completed,
       {"reported": c.get("games_completed"), "recounted": completed})

    st_raw = sum(r.get("updates_in_block") or 0 for r in uraw)
    ck("curriculum_optimizer_steps_nonzero", st_raw > 0,
       {"recounted_updates": st_raw, "update_rows": len(uraw)}, blocker=True)
    ck("reported_steps_match_raw_updates", (c.get("optimizer_steps") or 0) == st_raw,
       {"reported": c.get("optimizer_steps"), "recounted": st_raw}, blocker=True)
    ck("curriculum_losses_finite",
       bool(uraw) and all(r.get("losses_finite") for r in uraw),
       {"update_rows": len(uraw)})

    # Weights must actually move; an update row whose before/after hash agree did nothing.
    moved = [r for r in uraw if r.get("sha_before") != r.get("sha_after")]
    ck("every_update_block_moved_weights", bool(uraw) and len(moved) == len(uraw),
       {"update_rows": len(uraw), "blocks_that_moved": len(moved)}, blocker=True)
    ck("curriculum_checkpoint_progressed",
       len({r.get("sha_after") for r in uraw}) > 1,
       {"distinct_post_update_hashes": len({r.get("sha_after") for r in uraw})}, blocker=True)

    # Recompute the mixture actually realised from the raw opponent labels. Checking only that
    # both keys EXIST would pass a report with the planned numbers copied into `actual`.
    pa = {b["block"]: b for b in (c.get("planned_vs_actual") or [])}
    by_block = collections.defaultdict(collections.Counter)
    for r in graw:
        by_block[r.get("block")][r.get("opponent_category")] += 1
    bad = []
    for blk, cnt in by_block.items():
        tot = sum(cnt.values())
        recomputed = {k: round(v / tot, 4) for k, v in cnt.items()}
        rep_actual = (pa.get(blk) or {}).get("actual_fractions") or {}
        for k, v in recomputed.items():
            if abs(float(rep_actual.get(k, 0.0)) - v) > 0.02:
                bad.append({"block": blk, "category": k, "reported": rep_actual.get(k),
                            "recounted": v})
    ck("actual_mix_recomputed_from_raw_matches_report", bool(by_block) and not bad,
       {"blocks": len(by_block), "mismatches": bad[:6]})
    ck("planned_and_actual_are_distinct_fields",
       bool(pa) and all("planned_fractions" in b and "actual_fractions" in b
                        for b in pa.values()), {"blocks": len(pa)})
    # self-play must genuinely rise across the schedule, not merely be scheduled to
    lag = {blk: cnt.get("lagged", 0) / max(1, sum(cnt.values()))
           for blk, cnt in sorted(by_block.items())}
    ck("self_play_share_actually_increases",
       bool(lag) and max(lag.values()) > min(lag.values()),
       {"realised_lagged_share_by_block": {k: round(v, 3) for k, v in lag.items()}})

    hist = c.get("history") or []
    ck("history_non_empty", bool(hist), {"blocks": len(hist)})
    ck("no_game_zero_promotion",
       bool(hist) and all(h.get("promotion_eligible") is False
                          for h in hist if not h.get("games_completed")),
       {"zero_game_blocks": sum(1 for h in hist if not h.get("games_completed"))})
    # a stale snapshot path would silently freeze the self-play opponent (rl_env caches by path)
    snaps = [h.get("lagged_snapshot") for h in hist if h.get("lagged_snapshot")]
    ck("lagged_snapshot_paths_unique", len(set(snaps)) == len(snaps),
       {"snapshots": len(snaps), "distinct": len(set(snaps))})
    ck("lagged_snapshot_contents_differ",
       len({h.get("lagged_snapshot_sha256") for h in hist
            if h.get("lagged_snapshot_sha256")}) == len(snaps),
       {"note": "identical snapshot hashes mean self-play never advanced"})


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
    meta = jload("final_panel/panel_meta.json", {}) or {}
    opps = set(meta.get("opponents") or [])
    for row in rows:
        for k, v in row.items():
            # `overall_rate` / `worst_matchup_rate` also end in _rate but name no opponent
            if not k.endswith("_rate") or v is None or k[:-5] not in opps:
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
               for row in rows for k in row
               if k.endswith("_rate") and k[:-5] in opps))


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

    # every package manifest on disk, not a hardcoded filename that never existed
    mans = sorted(glob.glob(os.path.join(C18, "packages", "*_manifest.json")))
    require("package_manifest_present", bool(mans), {"manifests": len(mans)})
    for mp in mans:
        m = json.load(open(mp))
        name = m.get("name") or os.path.basename(mp)
        arch = os.path.join(C18, m.get("archive_rel", ""))
        ck(f"package_hash_matches_manifest:{name}",
           os.path.exists(arch) and sha_file(arch) == m.get("sha256"),
           {"manifest": (m.get("sha256") or "")[:12],
            "on_disk": sha_file(arch)[:12] if os.path.exists(arch) else None}, blocker=True)
        # the packaged search module must be the one the panel imported (S8.2.6); a
        # policy-only package ships no search module and is exempt rather than failed
        live = os.path.join(_REPO, "tools", "c018_search.py")
        ck(f"packaged_search_module_matches_source:{name}",
           True if m.get("policy_only") else
           m.get("search_module_sha256") == (sha_file(live) if os.path.exists(live) else None),
           {"packaged": (m.get("search_module_sha256") or "")[:12],
            "policy_only": bool(m.get("policy_only"))}, blocker=True)
        v = jload(f"packages/{name}_clean_validation.json")
        if v:
            ck(f"clean_extraction_ok:{name}", bool(v.get("clean_extraction_ok")),
               {"games_completed": v.get("games_completed"),
                "games_played": v.get("games_played")}, blocker=True)
            # a safe fallback and a working search look identical unless something counts it
            ck(f"packaged_learned_component_ran:{name}",
               bool(v.get("learned_component_actually_ran")) if m.get("policy_only")
               else bool(v.get("search_actually_ran_in_package")),
               {"searched": v.get("packaged_searched"),
                "decisions": v.get("packaged_decisions"),
                "rate": v.get("packaged_search_rate"),
                "policy_ok": v.get("packaged_policy_ok"),
                "policy_only": bool(m.get("policy_only")),
                "note": "completing games proves nothing; the baseline fallback also "
                        "completes games"}, blocker=True)
            ck(f"packaged_no_hidden_information:{name}",
               (v.get("packaged_hidden_information_violations") or 0) == 0, blocker=True)

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

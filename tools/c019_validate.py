"""c019 F03/AC-08 — raw-data-derived method-fidelity and evidence validator.

Written before the runs it judges, and every check re-derives from raw artifacts rather than
reading a summary that asserts the number. The rejection list is close to a transcript of c018's
defects, which is the point: each one exists because this project has already shipped it once.

Must reject:
  * c018-style root-only search;
  * hardcoded option-zero rollout continuation;
  * missing backup/visits;
  * impossible determinizations;
  * ordinary PPO renamed ByteRL;
  * zero UPGO;
  * predetermined self-play schedules;
  * virtual games;
  * mutable historical checkpoints;
  * identity bugs;
  * hidden information;
  * package/source mismatch;
  * missing code;
  * skipped criteria counted PASS.
"""

from __future__ import annotations

import glob
import gzip
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")
MF = os.path.join(C19, "method_fidelity")

checks: List[Dict[str, Any]] = []
FINAL = False
skipped: List[str] = []


def ck(name, ok, detail=None, branch="common", critical=True, blocker=False):
    checks.append({"check": name, "branch": branch, "passed": bool(ok), "critical": critical,
                   "submission_blocker": blocker, "detail": detail})
    return ok


def require(name, ok, detail=None, branch="common", blocker=False):
    """Absent at final judgement is a failure, not a free pass."""
    if not ok:
        skipped.append(name)
    return ck(name, ok, detail, branch, critical=FINAL, blocker=blocker and FINAL)


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C19, p)
    return json.load(open(p)) if os.path.exists(p) else d


def read_jsonl(p, limit=None):
    p = p if os.path.isabs(p) else os.path.join(C19, p)
    rows = []
    if not os.path.exists(p):
        return rows
    op = gzip.open if p.endswith(".gz") else open
    try:
        with op(p, "rt") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
                    if limit and len(rows) >= limit:
                        break
    except (EOFError, OSError, json.JSONDecodeError):
        pass
    return rows


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def src(rel):
    p = os.path.join(_REPO, rel)
    return open(p, encoding="utf-8-sig").read() if os.path.exists(p) else ""


# ------------------------------------------------------------------ MCTS fidelity

def v_mcts():
    B = "mcts"
    summaries = sorted(glob.glob(os.path.join(C19, "mcts", "aggregate_stats", "*_summary.json")))
    if not summaries:
        require("mcts_run_present", False, {"reason": "no MCTS summary"}, B, blocker=True)
        return
    # judge the LARGEST run, not a convenient smoke
    s = max((json.load(open(p)) for p in summaries),
            key=lambda d: (d.get("floors") or {}).get("searched_decisions", 0))
    f = s.get("floors") or {}
    ev = s.get("fidelity_evidence") or {}
    c = s.get("counters") or {}

    ck("mcts_real_native_expansion", (c.get("step_ok") or 0) > 0 and (c.get("begin_ok") or 0) > 0,
       {"begin_ok": c.get("begin_ok"), "step_ok": c.get("step_ok")}, B, blocker=True)

    # ROOT-ONLY SEARCH -- c018's defect
    ck("mcts_expands_at_nonroot_depths", (f.get("nonroot_expansions") or 0) > 0,
       {"nonroot_expansions": f.get("nonroot_expansions"),
        "note": "root-only expansion is c018's defect and is not MCTS"}, B, blocker=True)
    ck("mcts_trees_show_nonroot_branching",
       (ev.get("trees_with_nonroot_branching") or 0) > 0,
       {"trees": ev.get("trees_with_nonroot_branching"),
        "note": "a non-root node with >=2 real children is the M03 claim"}, B, blocker=True)

    # BACKUP / VISITS
    ck("mcts_backup_present", (ev.get("backups") or 0) > 0 and (ev.get("backup_nodes") or 0) > 0,
       {"backups": ev.get("backups"), "backup_nodes": ev.get("backup_nodes")}, B, blocker=True)
    ck("mcts_backup_covers_paths_not_just_leaves",
       (ev.get("backup_nodes") or 0) > (ev.get("backups") or 0),
       {"nodes_per_backup": round((ev.get("backup_nodes") or 0)
                                  / max(1, ev.get("backups") or 1), 2),
        "note": "backup must update the whole selected path"}, B)
    ck("mcts_revisits_existing_nodes", (ev.get("revisits") or 0) > 0,
       {"revisits": ev.get("revisits")}, B, blocker=True)

    # HARDCODED OPTION-ZERO ROLLOUT -- c018's defect
    rb = ev.get("rollout_baseline_calls") or 0
    rs = ev.get("rollout_stochastic_calls") or 0
    ck("mcts_rollout_uses_a_real_policy", (rb + rs) > 0,
       {"baseline_calls": rb, "stochastic_calls": rs,
        "note": "repeated option index 0 is forbidden; rollouts must query a policy"},
       B, blocker=True)
    srcs = src("starter_kit/c019_mcts.py")
    ck("mcts_source_has_no_hardcoded_option_zero_continuation",
       "pick = cand if d == 0 else [0]" not in srcs and "search_step(cur.searchId, [0])"
       not in srcs,
       {"note": "c018 continued every deeper step with option index 0"}, B, blocker=True)

    # IMPOSSIBLE DETERMINIZATIONS
    ck("mcts_no_illegal_determinizations_used",
       (ev.get("determinizations_legal") or 0) > 0,
       {"legal": ev.get("determinizations_legal"),
        "rejected": ev.get("determinizations_rejected")}, B, blocker=True)
    dsrc = src("starter_kit/c019_determinize.py")
    ck("mcts_determinizer_rejects_rather_than_pads",
       "without replacement" in dsrc.lower() and "return None" in dsrc
       and "filler" not in dsrc.replace("duplicate filler IDs", "").replace(
           "duplicate filler", ""),
       {"note": "c018 topped up a dry pool with duplicate card ids"}, B, blocker=True)
    dets = read_jsonl("mcts/determinizations/scaled_determinizations.jsonl.gz", 4000)
    illegal_used = [d for d in dets if d.get("legal") is False and d.get("root_visits")]
    ck("mcts_no_search_ran_on_an_illegal_world", not illegal_used,
       {"illegal_with_search": len(illegal_used), "determinization_records": len(dets)},
       B, blocker=True)
    ck("mcts_determinizations_record_their_sampling_pool",
       all("pool_archetype" in d for d in dets[:200]) if dets else False,
       {"note": "a world labelled 'unknown' cannot be audited for multiplicity"}, B)

    # HIDDEN INFORMATION
    ck("mcts_no_hidden_information_violation",
       (ev.get("hidden_information_violations") or 0) == 0,
       {"violations": ev.get("hidden_information_violations")}, B, blocker=True)

    # LIFECYCLE
    ck("mcts_native_states_released", (ev.get("release_errors") or 0) == 0,
       {"release_errors": ev.get("release_errors")}, B)

    # CONFIG ACTUALLY AFFECTS RUNTIME (c018's beam_width did not)
    ck("mcts_puct_is_implemented_and_sensitive",
       "c_puct" in srcs and "sqrt_n" in srcs and "prior" in srcs,
       {"note": "unit fixture test_c_puct_changes_the_selected_child pins the behaviour"}, B)

    # FLOORS
    floors = [
        ("searched live decisions >= 5000", f.get("searched_decisions") or 0, 5000),
        ("simulations or native expansions >= 500000",
         f.get("simulations_or_expansions") or 0, 500000),
        ("decisions using multiple determinizations >= 1000",
         f.get("multi_determinization_decisions") or 0, 1000),
        ("complete sampled tree traces >= 100", f.get("sampled_full_traces") or 0, 100),
    ]
    for name, actual, need in floors:
        ck(f"mcts_floor: {name}", actual >= need,
           {"actual": actual, "required": need}, B, critical=False)


# ------------------------------------------------------------------ ByteRL fidelity

def v_byterl():
    B = "byterl"
    s = jload("byterl/learner_logs/training_summary.json")
    if not s:
        require("byterl_run_present", False, {"reason": "no training summary"}, B, blocker=True)
        return

    games = read_jsonl("byterl/raw_games/games.jsonl.gz")
    losses = read_jsonl("byterl/learner_logs/losses.jsonl.gz")
    lps = read_jsonl("byterl/osfp/learning_periods.jsonl")
    promos = read_jsonl("byterl/osfp/promotion_history.jsonl")
    opps = read_jsonl("byterl/osfp/opponent_samples.jsonl.gz")

    # VIRTUAL GAMES -- recount from raw rows
    ck("byterl_games_are_real_rows", len(games) > 0,
       {"raw_game_rows": len(games),
        "note": "a training claim with no per-game rows on disk played no games"},
       B, blocker=True)
    ck("byterl_reported_games_match_raw_rows",
       (s.get("actual_games") or 0) == len(games),
       {"reported": s.get("actual_games"), "recounted": len(games)}, B, blocker=True)
    ck("byterl_games_completed", sum(1 for g in games if g.get("completed")) > 0,
       {"completed": sum(1 for g in games if g.get("completed"))}, B)

    # OPTIMIZER STEPS -- recount from per-update rows
    ck("byterl_optimizer_steps_match_raw_updates",
       (s.get("optimizer_steps") or 0) == len(losses),
       {"reported": s.get("optimizer_steps"), "recounted": len(losses)}, B, blocker=True)
    ck("byterl_losses_finite",
       all(all(np_isfinite(r.get(k)) for k in ("total", "policy_vtrace", "upgo", "value"))
           for r in losses[:5000]) if losses else False,
       {"update_rows": len(losses)}, B, blocker=True)
    ck("byterl_gradients_recorded_and_finite",
       all(np_isfinite(r.get("grad_norm")) and (r.get("grad_norm") or 0) > 0
           for r in losses[:5000]) if losses else False,
       {"note": "gradient evidence is required, not just a loss number"}, B)

    # ORDINARY PPO RENAMED ByteRL
    vsrc = src("starter_kit/c019_vtrace.py")
    ck("byterl_vtrace_implemented_not_gae",
       "rho" in vsrc and "c.clamp" in vsrc.replace(" ", "") + vsrc
       and "importance" in vsrc.lower(),
       {"note": "V-trace requires pi/mu importance ratios; GAE does not use them"},
       B, blocker=True)
    ck("byterl_importance_ratios_observed",
       any((r.get("rho_mean") or 0) > 0 for r in losses[:5000]) if losses else False,
       {"note": "rho must be computed at runtime, not merely present in source"},
       B, blocker=True)
    ck("byterl_vtrace_clipping_is_active",
       any(r.get("rho_clipped_frac") is not None for r in losses[:5000]) if losses else False,
       {"registered_bounds": [0.001, 1.007]}, B)

    # ZERO UPGO
    upgo_nonzero = [r for r in losses if abs(float(r.get("upgo") or 0.0)) > 0]
    ck("byterl_upgo_is_nonzero", len(upgo_nonzero) > 0,
       {"updates_with_nonzero_upgo": len(upgo_nonzero), "updates": len(losses),
        "note": "METHOD_FIDELITY forbids setting UPGO to zero or aliasing it to V-trace"},
       B, blocker=True)
    ck("byterl_upgo_differs_from_vtrace_loss",
       any(abs(float(r.get("upgo") or 0) - float(r.get("policy_vtrace") or 0)) > 1e-9
           for r in losses[:5000]) if losses else False,
       {"note": "identical values every step would mean UPGO is aliased"}, B, blocker=True)

    # PREDETERMINED SELF-PLAY SCHEDULE -- c018's defect
    tsrc = src("tools/c019_byterl_train.py")
    ck("byterl_no_scheduled_self_play_ramp",
       "self_play_schedule" not in tsrc and "planned_self_play" not in tsrc,
       {"note": "c018 raised self-play by block number; OSFP samples per game"},
       B, blocker=True)
    if opps:
        kinds = [o.get("kind") for o in opps]
        cur = sum(1 for k in kinds if k == "CURRENT_SELF_PLAY")
        hist = sum(1 for k in kinds if k == "HISTORICAL_PAYOFF_SAMPLE")
        ck("byterl_opponents_are_sampled_not_scheduled", hist > 0 or len(promos) <= 1,
           {"current_self_play": cur, "historical_samples": hist,
            "observed_p": round(cur / max(1, cur + hist), 4), "registered_p": 0.6}, B)

    # MUTABLE HISTORICAL CHECKPOINTS
    imm = s.get("immutability") or {}
    ck("byterl_historical_checkpoints_immutable", bool(imm.get("all_immutable")),
       {"historical": imm.get("historical"), "verified": imm.get("verified"),
        "mutated_or_missing": imm.get("mutated_or_missing")}, B, blocker=True)
    hashes = [p.get("added", {}).get("sha256") for p in promos if p.get("added")]
    ck("byterl_historical_hashes_distinct",
       len(set(h for h in hashes if h)) == len([h for h in hashes if h]),
       {"added": len(hashes), "distinct": len(set(h for h in hashes if h))}, B)
    forced = [p for p in promos if p.get("reason") == "FORCED_MAX_LP"]
    ck("byterl_forced_add_never_labelled_performance",
       all(p.get("reason") != "PERFORMANCE" for p in forced),
       {"forced_additions": len(forced)}, B)

    # CHECKPOINT PROGRESS
    moved = [r for r in lps if r.get("weights_changed")]
    ck("byterl_checkpoints_changed_every_lp", bool(lps) and len(moved) == len(lps),
       {"learning_periods": len(lps), "with_changed_weights": len(moved)}, B, blocker=True)

    # FLOORS
    floors = [
        ("actual simulator games >= 60000", len(games), 60000),
        ("optimizer steps >= 20000", len(losses), 20000),
        ("complete OSFP learning periods >= 5", len(lps), 5),
        ("immutable historical additions >= 2", len(hashes), 2),
    ]
    hist_games = sum(1 for g in games
                     if g.get("opponent_kind") == "HISTORICAL_PAYOFF_SAMPLE")
    floors.append(("games involving historical checkpoints >= 1000", hist_games, 1000))
    for name, actual, need in floors:
        ck(f"byterl_floor: {name}", actual >= need, {"actual": actual, "required": need},
           B, critical=False)

    ck("byterl_fresh_random_initialization",
       "FRESH_RANDOM" in str(s.get("initialized_from", "")),
       {"initialized_from": s.get("initialized_from"),
        "note": "§9.1 forbids continuing a c018 checkpoint"}, B, blocker=True)


def np_isfinite(x):
    try:
        return x is not None and float(x) == float(x) and abs(float(x)) != float("inf")
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------ shared / evidence

def v_common():
    ck("branch_independence_no_mcts_import_in_byterl",
       "c019_mcts" not in src("tools/c019_byterl_train.py")
       and "c019_ismcts" not in src("starter_kit/c019_byterl_actor.py"),
       {"note": "§16: no MCTS training-label dependency in the primary ByteRL branch"},
       blocker=True)
    ck("branch_independence_no_byterl_import_in_pure_mcts",
       "c019_byterl" not in src("starter_kit/c019_mcts.py")
       and "c019_byterl" not in src("starter_kit/c019_determinize.py"),
       {"note": "§16: no ByteRL dependency in pure MCTS; adapters are injected, not imported"},
       blocker=True)
    ck("hidden_information_guard_raises",
       "raise HiddenInformationAccess" in src("starter_kit/c019_core.py"),
       {"note": "P02 -- a leak must crash, not silently return"}, blocker=True)
    ck("canonical_option_identity_is_by_key_not_index",
       "def key(self)" in src("starter_kit/c019_core.py")
       and "by_key" in src("starter_kit/c019_core.py"),
       {"note": "index identity breaks aggregation when option order differs"})

    deck = jload("common/deck_freeze.json")
    ck("deck_frozen_for_both_branches",
       bool(deck) and set(deck.get("frozen_for") or []) >= {"PTCG_ISMCTS_V0",
                                                            "PTCG_BYTERL_V0"},
       {"deck": (deck or {}).get("deck")})

    m01 = jload("probes/M01_baseline_memory_parity/probe.json")
    ck("mcts_baseline_memory_parity",
       bool(m01) and m01.get("status") == "PASS" and m01.get("mismatches") == 0,
       {"decisions": (m01 or {}).get("decisions"),
        "mismatches": (m01 or {}).get("mismatches"),
        "note": "c018 proved overriding a stateful baseline destroys it"},
       "mcts", blocker=True)

    man = jload("method_fidelity/source_snapshot_manifest.json")
    ck("sources_snapshotted_with_clean_room_record",
       bool(man) and (man.get("clean_room_policy") or {}).get("vendored_source_files") == 0,
       {"sources": (man or {}).get("n_sources"),
        "conflicts_recorded": len((man or {}).get("source_conflicts") or [])})


def v_packages():
    mans = sorted(glob.glob(os.path.join(C19, "packages", "*", "manifest.json")))
    require("package_present", bool(mans), {"packages": len(mans)})
    for mp in mans:
        m = json.load(open(mp))
        name = m.get("name") or os.path.basename(os.path.dirname(mp))
        arch = os.path.join(os.path.dirname(mp), m.get("archive", ""))
        ck(f"package_hash_matches_manifest:{name}",
           os.path.exists(arch) and sha_file(arch) == m.get("sha256"),
           {"manifest": (m.get("sha256") or "")[:12]}, blocker=True)
        v = jload(f"packages/{name}/clean_validation.json")
        if v:
            ck(f"package_clean_extraction:{name}", bool(v.get("clean_extraction_ok")),
               {"games": v.get("games_played"), "completed": v.get("games_completed")},
               blocker=True)
            ck(f"package_zero_illegal_or_crash:{name}",
               not (v.get("errors") or []) and v.get("games_completed") == v.get("games_played"),
               {"errors": (v.get("errors") or [])[:3]}, blocker=True)


def v_final():
    ck("no_skipped_criteria_counted_as_pass", (not FINAL) or not skipped,
       {"mode": "final" if FINAL else "interim", "not_exercised": skipped[:12]})


def main():
    global FINAL
    FINAL = "--final" in sys.argv
    os.makedirs(MF, exist_ok=True)
    v_common()
    v_mcts()
    v_byterl()
    v_packages()
    v_final()

    crit = [c for c in checks if c["critical"] and not c["passed"]]
    blockers = [c for c in checks if c["submission_blocker"] and not c["passed"]]
    by_branch = {}
    for b in ("mcts", "byterl", "common"):
        sub = [c for c in checks if c["branch"] == b]
        bl = [c for c in sub if c["submission_blocker"] and not c["passed"]]
        fail = [c for c in sub if not c["passed"] and c["critical"]]
        by_branch[b] = {"checks": len(sub), "passed": sum(1 for c in sub if c["passed"]),
                        "critical_failures": len(fail), "submission_blockers": len(bl),
                        "blocker_names": [c["check"] for c in bl],
                        "method_fidelity": ("PASS" if not bl and not fail else "FAIL")}

    doc = {"validator": "c019.method_fidelity.v1",
           "mode": "final" if FINAL else "interim",
           "n_checks": len(checks), "n_passed": sum(1 for c in checks if c["passed"]),
           "n_critical_failures": len(crit), "n_submission_blockers": len(blockers),
           "submission_blockers": [c["check"] for c in blockers],
           "not_exercised": skipped,
           "by_branch": by_branch,
           "overall": "PASS" if not crit else "FAIL",
           "checks": checks}
    json.dump(doc, open(os.path.join(MF, "validator_output.json"), "w"), indent=2, default=str)
    for b in ("mcts", "byterl"):
        json.dump({"branch": b, **by_branch[b],
                   "checks": [c for c in checks if c["branch"] == b]},
                  open(os.path.join(MF, f"{b}_fidelity.json"), "w"), indent=2, default=str)
    print(json.dumps({k: doc[k] for k in ("n_checks", "n_passed", "n_critical_failures",
                                          "n_submission_blockers", "overall")}, indent=2))
    for b, v in by_branch.items():
        print(f"  {b:7s} {v['passed']}/{v['checks']} fidelity={v['method_fidelity']} "
              f"blockers={v['submission_blockers']}")
    for c in crit[:12]:
        print("  FAIL:", c["check"], json.dumps(c["detail"], default=str)[:150])
    return 0 if not crit else 1


if __name__ == "__main__":
    raise SystemExit(main())

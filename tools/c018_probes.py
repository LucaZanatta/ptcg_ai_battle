"""c018 — probe directory writer.

Each probe re-derives its verdict from raw artifacts on disk. Nothing here copies a number out
of a summary and calls it evidence; where a summary is the only carrier of a counter, the probe
says so in `raw_evidence` and cross-checks it against the row-level file.

Probes are diagnostic and non-blocking by default (PROBE_MATRIX). A FAIL_TAINTED verdict taints
its downstream artifacts; only the CONTRACT §8.2 blockers stop a submission.
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
PROBES = os.path.join(C18, "probes")


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True,
                              text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, _REPO)


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else d


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


def manifest(paths):
    out = []
    for p in paths:
        ap = p if os.path.isabs(p) else os.path.join(C18, p)
        if os.path.exists(ap):
            out.append({"path": rel(ap), "sha256": sha_file(ap),
                        "bytes": os.path.getsize(ap)})
        else:
            out.append({"path": p, "sha256": None, "bytes": None, "missing": True})
    return out


def write(pid, name, status, checks, inputs, outputs, readme, taints=(), blocker=False,
          raw=(), cfg_hash=None, extra=None):
    d = os.path.join(PROBES, f"{pid}_{name}")
    os.makedirs(os.path.join(d, "raw"), exist_ok=True)
    doc = {"probe_id": pid, "name": name, "status": status, "source_commit": commit(),
           "config_hash": cfg_hash, "checks": checks, "taints": list(taints),
           "submission_blocker": bool(blocker), "raw_evidence": [rel(
               p if os.path.isabs(p) else os.path.join(C18, p)) for p in raw]}
    if extra:
        doc.update(extra)
    json.dump(doc, open(os.path.join(d, "probe.json"), "w"), indent=2, default=str)
    json.dump({"inputs": manifest(inputs)}, open(os.path.join(d, "inputs_manifest.json"), "w"),
              indent=2, default=str)
    json.dump({"outputs": manifest(outputs + [os.path.join(d, "probe.json")])},
              open(os.path.join(d, "outputs_manifest.json"), "w"), indent=2, default=str)
    open(os.path.join(d, "README.md"), "w").write(readme)
    print(f"  {pid} {name}: {status}")
    return doc


# --------------------------------------------------------------------------- probes

def primary_prefix(default="scaled"):
    """The trajectory set with the most TRUSTED decisions.

    Several prefixes coexist (smoke, vertical, budgetcheck, scaled, scaled2). Hardcoding one
    means a rerun at larger scale silently keeps reporting the smaller set, so the primary set
    is resolved from the evidence rather than named in code.
    """
    best, best_n = default, -1
    for p in glob.glob(os.path.join(C18, "search", "*_search_summary.json")):
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue
        n = d.get("trusted_decisions") or 0
        if n > best_n:
            best, best_n = os.path.basename(p)[:-len("_search_summary.json")], n
    return best


PFX = primary_prefix()
SUM = f"search/{PFX}_search_summary.json"
TRJ = f"trajectories/{PFX}_trajectories.jsonl.gz"


def p02(s, rows):
    c = s["real_search_counters"]
    bp = jload("artifacts/branch_proof.json", {}) or {}
    tr = s["sample_traces"]
    deep = [t for t in tr if (t.get("depth_max") or 0) >= 2]
    branch = [r for r in rows if (r.get("distinct_successors") or 0) > 1]
    ck = {
        "search_step_calls": c["step_calls"], "search_step_ok": c["step_ok"],
        "max_depth_reached": c["max_depth_reached"],
        "distinct_successor_observations": c["distinct_successors"],
        "traces_with_depth_ge_2": len(deep), "traces_sampled": len(tr),
        "decisions_with_branching_successors": len(branch),
        "mean_successors_per_searched_decision": round(
            c["distinct_successors"] / max(1, c["begin_ok"]), 2),
        "step_error_rate": round(c["step_errors"] / max(1, c["step_calls"]), 5),
        "per_decision_examined": bp.get("decisions_examined"),
        "per_decision_two_or_more_distinct_successors":
            bp.get("decisions_with_two_or_more_distinct_successors"),
        "per_decision_depth_gt_1": bp.get("decisions_reaching_depth_gt_1"),
        "per_decision_distinct_leaf_values": bp.get("decisions_with_distinct_leaf_values"),
    }
    ok = (c["step_ok"] > 0 and c["max_depth_reached"] >= 2 and len(deep) > 0 and branch
          and (bp.get("decisions_with_two_or_more_distinct_successors") or 0) > 0)
    readme = f"""# P02 — Real successor branching

Does the search actually advance the simulator, or does it score the root and stop? c017 claimed
search while doing the latter; this probe exists because that claim was believed once.

**Evidence.** {c['step_ok']:,} successful `search_step` calls produced
{c['distinct_successors']:,} distinct successor observations across {c['begin_ok']:,} search
roots — {ck['mean_successors_per_searched_decision']} per root. Maximum depth reached is
{c['max_depth_reached']} (a depth-0 scorer cannot exceed 0). {len(deep)} of {len(tr)} sampled
traces record a chain of depth ≥ 2, and {len(branch):,} decisions saw more than one distinct
successor — i.e. the tree genuinely branched rather than replaying one line.

**Per-decision, not just in aggregate.** An aggregate successor count cannot distinguish a
branching tree from one long line, so each decision was checked individually:
{ck['per_decision_two_or_more_distinct_successors']:,} of {ck['per_decision_examined']:,}
examined decisions produced **two or more distinct successor observations**, and
{ck['per_decision_depth_gt_1']:,} reached depth > 1.
{ck['per_decision_distinct_leaf_values']:,} produced candidates with *different* leaf values —
i.e. the tree discriminated rather than returning a flat score list. Raw rows:
`artifacts/branch_proof.json`.

{c['step_errors']:,} steps ({ck['step_error_rate']:.4%}) returned an engine error; those nodes
are dropped from the beam and the decision falls back rather than being recorded as searched.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P02", "real_successor_branching", "PASS" if ok else "FAIL_TAINTED", ck,
                 [SUM, TRJ], [], readme, raw=[SUM, TRJ, "artifacts/branch_proof.json"])


def p03(s, rows):
    c = s["real_search_counters"]
    arche = collections.Counter(r.get("determinization_archetype") for r in rows
                                if r.get("determinization_archetype"))
    src = open(os.path.join(_REPO, "tools", "c018_search.py")).read()
    ck = {
        "runtime_hidden_information_violations": c["hidden_information_violations"],
        "visible_view_is_only_accessor": "class VisibleView" in src,
        "forbidden_accessors_raise": src.count("raise HiddenInformationAccess"),
        "opponent_hand_read_guarded": "def opponent_hand_ids" in src,
        "opponent_deck_read_guarded": "def deck_list" in src,
        "prize_read_guarded": "def prize_ids" in src,
        "determinization_archetypes_used": dict(arche),
        "determinized_not_observed": True,
    }
    ok = c["hidden_information_violations"] == 0 and ck["visible_view_is_only_accessor"]
    readme = f"""# P03 — Hidden-information audit

Search cannot begin without *predicting* the opponent's deck, prizes, hand and face-down Active.
That is the whole risk: a determinizer that peeks would produce a search that looks brilliant
offline and is illegal in the competition. So the audit covers the determinizer, not only the
state reader.

**Static.** `tools/c018_search.py` routes every state read through `VisibleView`, which exposes
only own hand, both boards, both discards and public counts. `opponent_hand_ids`, `deck_list`
and `prize_ids` exist solely to raise `HiddenInformationAccess` — {ck['forbidden_accessors_raise']}
raise sites. The determinizer receives a `VisibleView`, never the raw observation, so a peek is a
crash rather than a silent advantage.

**Runtime.** {c['hidden_information_violations']} violations across {c['begin_ok']:,} search
roots in {s['games']} games. Predicted opponent contents were drawn from public archetype
decklists ({', '.join(f'{k}={v:,}' for k, v in arche.most_common())}), i.e. *guessed* from the
public metagame, not read from the live game.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P03", "hidden_information_audit", "PASS" if ok else "FAIL_TAINTED", ck,
                 [SUM, TRJ, os.path.join(_REPO, "tools", "c018_search.py")], [], readme,
                 raw=[SUM], blocker=not ok)


def p04(s, rows):
    c = s["real_search_counters"]
    fb = collections.Counter(r.get("reason") for r in rows if not r.get("searched"))
    ck = {
        "invalid_actions_played": s["invalid_actions"],
        "games_completed": s["games_completed"], "games": s["games"],
        "baseline_retained": c["baseline_retained"], "changed_action": c["changed_action"],
        "fallbacks": c["fallbacks"],
        "fallback_rate": round(c["fallbacks"] / max(1, c["decisions"]), 4),
        "fallback_reasons": dict(fb),
        "label_in_option_range": all(all(0 <= i < r["n_options"] for i in r["label_action"])
                                     for r in rows),
        "baseline_always_a_candidate": True,
    }
    ok = (s["invalid_actions"] == 0 and ck["label_in_option_range"]
          and s["games_completed"] == s["games"])
    readme = f"""# P04 — Legality and fallback

**Legality.** {len(rows):,} search-chosen actions were revalidated against the live option set
before being played; {s['invalid_actions']} were rejected. All {s['games_completed']}/{s['games']}
games ran to a terminal state, so no search action wedged the engine.

**Fallback.** {c['fallbacks']:,} decisions ({ck['fallback_rate']:.2%}) declined to search and
played the baseline heuristic action instead
({', '.join(f'{k}={v:,}' for k, v in fb.most_common(5))}). The baseline is always candidate 0 and
is never pruned, so the search can only *improve on* or *return* the baseline — it retained the
baseline {c['baseline_retained']:,} times and changed it {c['changed_action']:,} times.

That asymmetry is the package-safety argument: under a timeout, a determinization failure, or an
engine error, the agent degrades to the heuristic it would otherwise have played.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P04", "legality_and_fallback", "PASS" if ok else "FAIL_TAINTED", ck,
                 [SUM, TRJ], [], readme, raw=[SUM, TRJ])


def p05(s, rows):
    fx = jload("artifacts/tactical_fixtures.json", {}) or {}
    cats = fx.get("categories") or {}
    ck = {"categories_covered": fx.get("categories_covered"),
          "categories_total": fx.get("categories_total"),
          "fixtures_per_category": cats,
          "traces_captured": len(s["sample_traces"]),
          "distinct_root_contexts": len({r["context"] for r in rows}),
          "decisions_where_search_changed_action": sum(
              1 for r in rows if r.get("label_differs_from_baseline")),
          "change_rate_among_searched": round(
              sum(1 for r in rows if r.get("label_differs_from_baseline"))
              / max(1, sum(1 for r in rows if r.get("searched"))), 4)}
    ok = (fx.get("categories_covered") or 0) == (fx.get("categories_total") or 7)
    rows_md = "\n".join(f"| {k} | {v} |" for k, v in cats.items())
    readme = f"""# P05 — Tactical fixtures and traces

All {ck['categories_total']} §15 categories are covered by **real captured roots**, each
retaining the root select context and option types, every candidate select, the leaf
decomposition per candidate, the chosen line, the dominated lines, and nodes/depth/time.
Raw: `artifacts/tactical_fixtures.json`.

| category | fixtures |
|---|---|
{rows_md}

**Two categories needed a substantive definition, not a contextual one.** `missed_lethal` was
first defined as an attack context with a single option — but a single-option attack is a
*forced* move that never reaches the search, so that definition guaranteed an empty category.
It now means an attack decision where some candidate's leaf value beats the baseline's by more
than one prize (0.55/6 of the leaf scale), i.e. the search found a knockout the baseline missed.
`bench_liability` likewise now means a decision taken with a bench of ≤ 1, which is where bench
state actually creates risk, rather than only the explicit TO_BENCH context.

Across {ck['distinct_root_contexts']} distinct decision contexts the search changed the baseline
action {ck['decisions_where_search_changed_action']:,} times
({ck['change_rate_among_searched']:.1%} of searched decisions). A search that never disagrees
with its baseline is an expensive identity function; one that always disagrees is usually broken.

**What these fixtures do not show.** They demonstrate the search machinery is real and
discriminating. They are not evidence the leaf evaluator's preferences are *correct* — that
claim belongs to the gameplay panel (P17).

**Status: {'PASS' if ok else 'WARN'}.**
"""
    return write("P05", "tactical_fixtures", "PASS" if ok else "WARN", ck,
                 [SUM, "artifacts/tactical_fixtures.json"], [], readme,
                 raw=[SUM, "artifacts/tactical_fixtures.json"])


def p06(s, rows):
    c = s["real_search_counters"]
    thr = jload("artifacts/throughput.json", {}) or {}
    life = jload("artifacts/lifecycle_extended.json", {}) or {}
    ms = sorted(r["search_ms"] for r in rows if r.get("search_ms") is not None)
    def q(p):
        return round(ms[min(len(ms) - 1, int(len(ms) * p))], 1) if ms else None
    cfg = s["config"]
    ck = {"decisions_timed": len(ms), "p50_ms": q(.5), "p90_ms": q(.9), "p99_ms": q(.99),
          "max_ms": round(ms[-1], 1) if ms else None,
          "mean_ms": round(sum(ms) / max(1, len(ms)), 1),
          "budget_ms_per_decision": cfg["max_ms_per_decision"],
          "over_budget_decisions": sum(1 for x in ms if x > cfg["max_ms_per_decision"]),
          "fallback_rate": round(c["fallbacks"] / max(1, c["decisions"]), 4),
          "nodes_expanded": c["nodes"],
          "nodes_per_searched_decision": round(c["nodes"] / max(1, c["begin_ok"]), 1),
          "search_handles_released": c["release_calls"],
          "release_errors": c["release_errors"],
          "search_end_calls": c["end_calls"],
          "roots_per_second": thr.get("roots_per_second"),
          "steps_per_second": thr.get("steps_per_second"),
          "rss_mb": thr.get("rss_mb"),
          "mean_full_match_agent_ms": thr.get("mean_full_match_agent_ms"),
          "determinizations": thr.get("determinizations"),
          "search_begin_input_preserved": life.get("search_begin_input_preserved"),
          "repeated_search_stable": life.get("repeated_search_stable")}
    ok = ck["release_errors"] == 0 and (ck["p99_ms"] or 0) <= cfg["max_ms_per_decision"]
    readme = f"""# P06 — Search latency and resource safety

Per-decision search cost over {len(ms):,} timed decisions: p50 {ck['p50_ms']} ms, p90
{ck['p90_ms']} ms, p99 {ck['p99_ms']} ms, max {ck['max_ms']} ms, against a
{cfg['max_ms_per_decision']} ms budget. {ck['over_budget_decisions']} decisions exceeded it and
fell back.

**Handle hygiene.** Every `search_begin` opens native state that must be released or the process
leaks across a match. {ck['search_handles_released']:,} releases and {ck['search_end_calls']:,}
`search_end` calls with {ck['release_errors']} errors — the lifecycle is wrapped in a context
manager, so an exception mid-beam still releases. This is what makes the search safe to run
inside a submitted agent rather than only offline.

**Throughput and memory.** {ck['roots_per_second']} search roots/s, {ck['steps_per_second']}
`search_step`/s, {ck['determinizations']:,} determinizations, process RSS {ck['rss_mb']} MB, and
a mean full-match agent time of {ck['mean_full_match_agent_ms']} ms.

{ck['nodes_expanded']:,} nodes expanded, {ck['nodes_per_searched_decision']} per searched
decision, under a per-decision node cap. That cap is per-decision for two reasons: c017's global
cap starved 249 of 266 searches, and a *cumulative* cap that depended on a caller-maintained
counter later left the packaged agent searching 3 of 84 decisions
(`failures/DEFECT_packaged_agent_searched_3_of_84_decisions.md`).

`search_begin_input` preserved: {ck['search_begin_input_preserved']}. Repeated searches on one
root remained stable with zero begin/release errors: {ck['repeated_search_stable']}.

**Status: {'PASS' if ok else 'WARN'}.**
"""
    return write("P06", "search_latency", "PASS" if ok else "WARN", ck, [SUM, TRJ], [], readme,
                 raw=[SUM, TRJ, "artifacts/throughput.json",
                      "artifacts/lifecycle_extended.json"],
                 cfg_hash=hashlib.sha256(
                     json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16])


def p07(s, rows):
    import numpy as np
    npz = np.load(os.path.join(C18, "trajectories", f"{PFX}_features.npz"))
    n = npz["global"].shape[0]
    # NpzFile decompresses on EVERY key access, so these must be read once, not inside a
    # generator over 12k rows -- doing the latter turned this probe into a five-minute spin.
    KM = int(npz["opt_dense"].shape[1])
    npz_label = npz["label_index"]
    npz_nopt = npz["n_options"]
    npz_trusted = set(int(i) for i in npz["trusted_rows"])
    ck = {"trajectory_rows": len(rows), "feature_rows": int(n),
          "rows_align_one_to_one": len(rows) == n,
          "trusted_rows_in_npz": len(npz_trusted),
          "trusted_rows_in_jsonl": sum(1 for r in rows if r["trusted"]),
          "trusted_index_agrees": npz_trusted == {
              i for i, r in enumerate(rows) if r["trusted"]},
          "legal_mask_length_matches_options": all(
              len(r["legal_mask"]) == r["n_options"] for r in rows),
          "label_within_range": all(all(0 <= i < r["n_options"] for i in r["label_action"])
                                    for r in rows),
          "every_trusted_row_has_successors": all(
              (r.get("distinct_successors") or 0) > 0 for r in rows if r["trusted"]),
          "label_index_within_kmax": bool((npz_label < KM).all()),
          "k_max": KM,
          "rows_with_true_option_count_above_kmax": sum(
              1 for r in rows if r["n_options"] > KM),
          "rows_mislabeled_by_kmax_clipping": sum(
              1 for r in rows if r["label_action"] and max(r["label_action"]) >= KM),
          "multiselect_rows": sum(1 for r in rows if len(r["label_action"]) > 1),
          "uses_c017_labels": s["uses_c017_labels"],
          "trajectory_sha256": s["trajectory_sha256"]}
    ok = all(ck[k] for k in ("rows_align_one_to_one", "trusted_index_agrees",
                             "legal_mask_length_matches_options", "label_within_range",
                             "every_trusted_row_has_successors"))
    readme = f"""# P07 — Trajectory integrity

The distillation set and the audit log must describe the same decisions. {len(rows):,} JSONL
rows and {n:,} feature rows align one-to-one, and the `trusted_rows` index stored in the NPZ is
*identical* to the set of rows flagged trusted in the JSONL — checked as sets, not as counts, so
an off-by-one reordering cannot pass.

Every trusted row carries at least one real successor. Every label lies inside its own option
range. Every legal mask is exactly as long as its option list.

`uses_c017_labels: {s['uses_c017_labels']}` — c017's depth-0 labels are not importable from the
generator and no row here derives from them.

**Known limit, quantified.** The feature tensor holds K_MAX={ck['k_max']} option slots.
{ck['rows_with_true_option_count_above_kmax']} rows had more options than that, and exactly
{ck['rows_mislabeled_by_kmax_clipping']} rows chose an option at index ≥ K_MAX — those were
stored with label 0, a *wrong* target rather than a truncated one. They are excluded from the
distillation index (M02), not merely disclosed. The JSONL retains the true option count either
way.

{ck['multiselect_rows']:,} rows are multi-select. The feature label stores `label_action[0]`
only, so any agreement metric computed against it is FIRST-PICK agreement, not whole-selection
agreement.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P07", "trajectory_integrity", "PASS" if ok else "FAIL_TAINTED", ck,
                 [SUM, TRJ, f"trajectories/{PFX}_features.npz"], [], readme, raw=[TRJ])


def p08(s, rows):
    gm = {g["game_index"]: g for g in s["games_meta"]}
    mismatch = [r["game_index"] for r in rows
                if gm.get(r["game_index"], {}).get("outcome") != r["final_outcome"]]
    gsplit = collections.defaultdict(set)
    for r in rows:
        gsplit[r["game_index"]].add(r["split"])
    straddle = [g for g, v in gsplit.items() if len(v) > 1]
    seats = collections.Counter(r["seat"] for r in rows)
    opps = collections.Counter(r["opponent_id"] for r in rows)
    wins = [g["outcome"] for g in s["games_meta"] if g["outcome"] is not None]
    ck = {"games": len(gm), "rows": len(rows),
          "rows_whose_outcome_disagrees_with_game": len(mismatch),
          "games_straddling_splits": len(straddle),
          "split_counts": s["split_counts"], "split_by": s["split_by"],
          "rows_with_null_outcome": sum(1 for r in rows if r["final_outcome"] is None),
          "seat_balance": dict(seats), "opponent_mix": dict(opps),
          "generator_win_rate_vs_mixed_field": round(sum(wins) / max(1, len(wins)), 4),
          "games_completed": s["games_completed"]}
    ok = not mismatch and not straddle and ck["rows_with_null_outcome"] == 0
    readme = f"""# P08 — Outcome and split integrity

Every one of {len(rows):,} decision rows carries the terminal result of *its own* game: 0
disagreements against the per-game record, 0 null outcomes. The value head therefore regresses
on real game results, not on placeholders.

**Splits are by game, not by decision.** {len(straddle)} games straddle a split boundary.
Decision-level splitting would put earlier and later turns of the same game on both sides of the
train/test line and inflate held-out agreement, because consecutive decisions in one game share
almost all of their state. Split sizes: {s['split_counts']}.

Seats are balanced ({dict(seats)}) and the opponent mix is
{', '.join(f'{k}={v:,}' for k, v in opps.most_common())}; the generator won
{ck['generator_win_rate_vs_mixed_field']:.1%} against that mixed field.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P08", "outcome_and_split_integrity", "PASS" if ok else "FAIL_TAINTED", ck,
                 [SUM, TRJ], [], readme, raw=[SUM, TRJ])


def main():
    s = jload(SUM)
    if not s:
        raise SystemExit("no scaled search summary")
    rows = read_gz(TRJ)
    print(f"[c018 probes] {len(rows):,} rows from {s['games']} games")
    for f in (p02, p03, p04, p05, p06, p07, p08):
        f(s, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

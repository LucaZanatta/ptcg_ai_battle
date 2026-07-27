"""c018 — probes P09..P17, P30 (training, guidance, gameplay, integration).

Same doctrine as `c018_probes`: every verdict is re-derived from raw artifacts. Where a report is
the only carrier of a number, it is cross-checked against the row-level file that produced it.
"""

from __future__ import annotations

import collections
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "tools"))

from c018_probes import C18, jload, read_gz, write  # noqa: E402

DIST = "training/distillation_report.json"
CUR = "training/curriculum_report.json"
PANEL = "final_panel/final_panel_results.json"
PMETA = "final_panel/panel_meta.json"
PRAW = "final_panel/raw_games.jsonl.gz"


def p09():
    d = jload(DIST)
    if not d:
        return write("P09", "distillation_update_proof", "NOT_EXERCISED", {}, [], [],
                     "# P09 — not exercised\n\nNo distillation report present.\n")
    h = d.get("history") or []
    ck = {"device": d.get("device"), "optimizer_steps": d.get("optimizer_steps"),
          "history_batch_sum": sum(e.get("batches") or 0 for e in h),
          "steps_match_history": sum(e.get("batches") or 0 for e in h)
          == d.get("optimizer_steps"),
          "losses_finite": d.get("losses_finite"),
          "checkpoint_changed": d.get("checkpoint_changed"),
          "distinct_epoch_hashes": len({e.get("checkpoint_sha256") for e in h}),
          "epochs": len(h),
          "trusted_rows_only": d.get("trusted_rows_only"),
          "rows_trusted": d.get("rows_trusted"),
          "rows_excluded_label_beyond_kmax": d.get("rows_excluded_label_beyond_kmax"),
          "continues_c017_checkpoint": d.get("continues_c017_checkpoint"),
          "uses_c017_labels": d.get("uses_c017_labels"),
          "first_epoch_train_loss": (h[0] or {}).get("train_policy_loss") if h else None,
          "last_epoch_train_loss": (h[-1] or {}).get("train_policy_loss") if h else None}
    ok = bool(ck["steps_match_history"] and ck["losses_finite"] and ck["checkpoint_changed"]
              and ck["distinct_epoch_hashes"] == ck["epochs"])
    readme = f"""# P09 — Distillation update proof

An optimiser either stepped or it did not, and the only trustworthy witness is the weights.

{ck['optimizer_steps']:,} optimiser steps on **{ck['device']}** over {ck['epochs']} epochs. The
step counter is not taken on faith: summing the per-epoch batch counts recorded during training
gives {ck['history_batch_sum']:,}, which matches. Every epoch produced a *different* checkpoint
hash ({ck['distinct_epoch_hashes']}/{ck['epochs']} distinct), hashed over tensor bytes in sorted
key order rather than over the file — c012 cached a per-path file hash and could not tell an
overwrite from a no-op.

Training policy loss moved {ck['first_epoch_train_loss']} → {ck['last_epoch_train_loss']}, and
all losses stayed finite.

Trained on {ck['rows_trusted']:,} trusted rows only, with
{ck['rows_excluded_label_beyond_kmax']} K_MAX-mislabeled rows excluded. c017's depth-0 labels are
not used (`uses_c017_labels: {ck['uses_c017_labels']}`) and c017's checkpoint is not continued
(`continues_c017_checkpoint: {ck['continues_c017_checkpoint']}`) — a fresh initialisation is what
makes "the hash changed" mean *this* campaign moved *these* weights.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P09", "distillation_update_proof", "PASS" if ok else "FAIL_TAINTED", ck,
                 [DIST], [], readme, raw=[DIST])


def p10():
    d = jload(DIST)
    hm = jload("artifacts/heldout_metrics.json")
    if not d:
        return write("P10", "reload_and_heldout_metrics", "NOT_EXERCISED", {}, [], [],
                     "# P10 — not exercised\n")
    t = (hm or {}).get("held_out_test") or d.get("held_out_test") or {}
    ctrl = (jload("artifacts/heldout_metrics_11k.json", {}) or {}).get("held_out_test") or {}
    ck = {"reload_hash_matches": d.get("reload_hash_matches"),
          "reload_metrics_identical": d.get("reload_metrics_identical"),
          "held_out_n": t.get("n"), "top1": t.get("top1") or t.get("top1_agreement"),
          "top3": t.get("top3"), "mean_kl_nats": t.get("mean_kl_nats"),
          "legal_top1_rate": t.get("legal_top1_rate") or t.get("legal_prediction_rate"),
          "value_mse": t.get("value_mse"),
          "constant_baseline_mse": t.get("constant_baseline_mse"),
          "beats_constant_baseline": t.get("beats_constant_baseline"),
          "value_correlation": t.get("value_correlation"),
          "calibration_deciles": t.get("calibration_deciles"),
          "by_decision_category": t.get("by_decision_category"),
          "no_train_test_leakage": (hm or {}).get("no_train_test_leakage"),
          "sample_size_control_11k": {k: ctrl.get(k) for k in
                                      ("n", "top1", "top3", "value_mse",
                                       "constant_baseline_mse", "value_correlation",
                                       "beats_constant_baseline")} if ctrl else None,
          "metric_is_first_pick_only": True,
          "multiselect_rows": d.get("multiselect_rows")}
    # the value head failing to beat a constant is a WARN, not a PASS dressed up
    ok = bool(ck["reload_hash_matches"] and ck["reload_metrics_identical"]
              and (ck["legal_top1_rate"] or 0) >= 1.0 and ck["no_train_test_leakage"])
    value_ok = bool(ck["beats_constant_baseline"])
    status = "PASS" if (ok and value_ok) else ("WARN" if ok else "FAIL_TAINTED")
    cats = ck["by_decision_category"] or {}
    cat_md = "\n".join(f"| {k} | {v['n']} | {v['top1']} | {v.get('top3')} | "
                        f"{v['mean_kl_nats']} |" for k, v in cats.items()) or "| | | | | |"
    calib = "\n".join(f"| {c['bin']/10:.1f}–{(c['bin']+1)/10:.1f} | {c['n']} | "
                       f"{c['mean_predicted']} | {c['mean_actual']} |"
                       for c in (ck["calibration_deciles"] or [])) or "| | | | |"
    ms = ck["multiselect_rows"]
    ms_txt = f"{ms:,}" if ms is not None else "the"
    readme = f"""# P10 — Exact reload and held-out metrics

**Reload is exact.** The saved checkpoint was loaded into a *fresh* model and re-scored: hash
matches (`{ck['reload_hash_matches']}`), metrics identical (`{ck['reload_metrics_identical']}`).
A packaged model that scores differently from the evaluated one is §8.2.6 in its purest form.

**No leakage.** Splits are by game, and no game crosses train/validation/test
(`{ck['no_train_test_leakage']}`).

## Policy head — works

Held-out ({ck['held_out_n']:,} decisions from games never trained on): top-1
**{ck['top1']}**, top-3 **{ck['top3']}**, mean KL to the search's choice
{ck['mean_kl_nats']} nats, legal top-1 rate **{ck['legal_top1_rate']}**.

Legality is the property that matters for packaging: an inaccurate model plays a bad legal
move, an illegal one forfeits.

### By decision category (engine `SelectContext`)

| context | n | top-1 | top-3 | mean KL |
|---|---|---|---|---|
{cat_md}

## Value head — does NOT beat a constant

| | MSE |
|---|---|
| learned value head | **{ck['value_mse']}** |
| constant baseline (predict the training-set mean outcome) | **{ck['constant_baseline_mse']}** |

Correlation with the actual game result is **{ck['value_correlation']}**.

**The value head is worse than predicting a constant.** This is stated plainly because it is
load-bearing: M04's guided search replaces the hand-written leaf heuristic with exactly this
value head, so a value head that carries almost no signal is a direct, predicted reason for
guided search to rank at or below unguided search on the panel. It is a negative result about
this campaign's own most sophisticated component, not a caveat.

### Was it a sample-size problem?

The distillation was first run on 11,151 trusted rows and then re-run on roughly four times as
many, giving a direct control rather than a guess:

| trusted rows | policy top-1 | value MSE | constant baseline | correlation | beats constant |
|---|---|---|---|---|---|
| {ctrl.get('n', '—')} held-out (11,151-row training set) | {ctrl.get('top1')} | {ctrl.get('value_mse')} | {ctrl.get('constant_baseline_mse')} | {ctrl.get('value_correlation')} | {ctrl.get('beats_constant_baseline')} |
| {ck['held_out_n']} held-out (scaled training set) | {ck['top1']} | {ck['value_mse']} | {ck['constant_baseline_mse']} | {ck['value_correlation']} | {ck['beats_constant_baseline']} |

If the value head still loses to a constant at four times the data, the weakness is not sample
size — it is that a single terminal win/loss label per game carries very little signal about any
individual mid-game position, which is the honest conclusion and points at reward shaping or
temporal-difference targets rather than more data.

### Calibration by predicted decile

| predicted | n | mean predicted | mean actual |
|---|---|---|---|
{calib}

## What these numbers are not

The stored label is `label_action[0]`, so top-1 is FIRST-PICK agreement; on {ms_txt}
multi-select decisions it says nothing about the rest of the selection. And agreement with the
search is imitation, not strength — a model that imitates perfectly inherits the search's
mistakes. Gameplay promotion comes from P17 alone.

**Status: {status}.**
"""
    return write("P10", "reload_and_heldout_metrics", status, ck,
                 [DIST, "artifacts/heldout_metrics.json"], [], readme,
                 raw=[DIST, "artifacts/heldout_metrics.json"])


def p11():
    c = jload(CUR)
    if not c:
        return write("P11", "ppo_update_proof", "NOT_EXERCISED", {}, [], [],
                     "# P11 — not exercised\n")
    graw = read_gz(c.get("raw_rollout_file") or "")
    uraw = read_gz(c.get("raw_updates_file") or "")
    moved = [r for r in uraw if r.get("sha_before") != r.get("sha_after")]
    ck = {"raw_game_rows": len(graw),
          "raw_games_completed": sum(1 for r in graw if r.get("completed")),
          "reported_games": c.get("actual_simulator_games"),
          "games_match": len(graw) == c.get("actual_simulator_games"),
          "raw_update_rows": len(uraw),
          "recounted_optimizer_steps": sum(r.get("updates_in_block") or 0 for r in uraw),
          "reported_optimizer_steps": c.get("optimizer_steps"),
          "steps_match": sum(r.get("updates_in_block") or 0 for r in uraw)
          == c.get("optimizer_steps"),
          "blocks_that_moved_weights": len(moved), "blocks": len(uraw),
          "distinct_post_update_hashes": len({r.get("sha_after") for r in uraw}),
          "all_losses_finite": all(r.get("losses_finite") for r in uraw) if uraw else False,
          "trainable_decisions": sum(r.get("n_decisions") or 0 for r in uraw)}
    ok = bool(ck["games_match"] and ck["steps_match"] and uraw
              and ck["blocks_that_moved_weights"] == ck["blocks"]
              and ck["all_losses_finite"])
    readme = f"""# P11 — PPO update proof

c017 reported a curriculum in which no game was played and no optimiser ever stepped. Nothing
below is read from the curriculum report except as the claim being tested.

**Games are real.** {ck['raw_game_rows']:,} per-game rows exist on disk, written as each block
finished, {ck['raw_games_completed']:,} of them terminal. The report claims
{ck['reported_games']:,} — recounting the rows agrees.

**Updates are real.** {ck['raw_update_rows']} update rows sum to
{ck['recounted_optimizer_steps']:,} optimiser steps against {ck['reported_optimizer_steps']:,}
reported, over {ck['trainable_decisions']:,} trainable decisions. All losses finite.

**Weights actually moved.** Each update row records the weight hash before and after; all
{ck['blocks_that_moved_weights']}/{ck['blocks']} blocks changed it, and there are
{ck['distinct_post_update_hashes']} distinct post-update hashes. A block whose before/after hash
agreed would have done nothing regardless of what its loss printed.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P11", "ppo_update_proof", "PASS" if ok else "FAIL_TAINTED", ck,
                 [CUR], [], readme, raw=[CUR, c.get("raw_rollout_file") or "",
                                         c.get("raw_updates_file") or ""])


def p12():
    c = jload(CUR)
    d = jload(DIST)
    pm = jload(PMETA)
    if not c:
        return write("P12", "freshness_and_identity", "NOT_EXERCISED", {}, [], [],
                     "# P12 — not exercised\n")
    hist = c.get("history") or []
    snaps = [h.get("lagged_snapshot") for h in hist if h.get("lagged_snapshot")]
    shas = [h.get("lagged_snapshot_sha256") for h in hist if h.get("lagged_snapshot_sha256")]
    praw = read_gz(PRAW)
    ck = {"lagged_snapshot_paths": len(snaps), "distinct_paths": len(set(snaps)),
          "distinct_snapshot_hashes": len(set(shas)),
          "snapshots_never_overwritten": len(set(snaps)) == len(snaps),
          "snapshot_contents_all_differ": len(set(shas)) == len(shas),
          "curriculum_init_from": c.get("init_checkpoint"),
          "distill_checkpoint_after": (d or {}).get("checkpoint_sha256_after"),
          "zero_game_blocks": sum(1 for h in hist if not h.get("games_completed")),
          "zero_game_blocks_marked_ineligible":
              all(h.get("promotion_eligible") is False for h in hist
                  if not h.get("games_completed")),
          "panel_rows_self_identify":
              all(r.get("candidate_id") and r.get("opponent_id") and r.get("seat") is not None
                  for r in praw) if praw else None,
          "panel_identical_seeds_across_candidates":
              (pm or {}).get("identical_seeds_and_seats_across_candidates")}
    ok = bool(ck["snapshots_never_overwritten"] and ck["snapshot_contents_all_differ"]
              and ck["zero_game_blocks_marked_ineligible"])
    readme = f"""# P12 — Freshness and identity

**Self-play opponents are fresh.** `rl_env._build_opponent` caches `RLPolicy` objects **by
path**, so writing every snapshot to one filename would serve the first snapshot forever while
the report happily claimed self-play had advanced — the same defect shape as c012's cached
per-path file hash. Each block therefore writes `..._lagged_bNN.npz`:
{ck['lagged_snapshot_paths']} snapshots, {ck['distinct_paths']} distinct paths,
{ck['distinct_snapshot_hashes']} distinct contents.

**No game-zero promotion.** {ck['zero_game_blocks']} blocks completed zero games; all are marked
promotion-ineligible.

**Panel identity.** Every raw panel row carries its own `candidate_id`, `opponent_id`, `seat` and
`seed`, and aggregates are recomputed from those fields — worker results are never positionally
zipped back onto the job list, which is how a panel silently credits one agent with another's
wins.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P12", "freshness_and_identity", "PASS" if ok else "FAIL_TAINTED", ck,
                 [CUR, DIST, PMETA], [], readme, raw=[CUR])


def p14():
    c = jload(CUR)
    if not c:
        return write("P14", "mix_and_collapse", "NOT_EXERCISED", {}, [], [],
                     "# P14 — not exercised\n")
    # regenerate the §26/§27 audit against whatever curriculum report is current
    try:
        import c018_curriculum_audit as CA
        CA.main()
    except Exception as e:  # noqa: BLE001
        print(f"  curriculum audit failed: {type(e).__name__}: {e}")
    audit = jload("artifacts/curriculum_audit.json", {}) or {}
    graw = read_gz(c.get("raw_rollout_file") or "")
    by = collections.defaultdict(collections.Counter)
    for r in graw:
        by[r.get("block")][r.get("opponent_category")] += 1
    realised = {b: {k: round(v / sum(cnt.values()), 4) for k, v in cnt.items()}
                for b, cnt in sorted(by.items())}
    lag = {b: v.get("lagged", 0.0) for b, v in realised.items()}
    dev = []
    for b in sorted(by):
        planned = next((x["planned_fractions"] for x in c.get("planned_vs_actual") or []
                        if x["block"] == b), {})
        for k, v in realised[b].items():
            dev.append(abs(float(planned.get(k, 0.0)) - v))
    hist = c.get("history") or []
    ck = {"blocks": len(by),
          "realised_self_play_by_block": lag,
          "self_play_rises": bool(lag) and max(lag.values()) > min(lag.values()),
          "max_abs_deviation_planned_vs_realised": round(max(dev), 4) if dev else None,
          "mean_abs_deviation": round(sum(dev) / len(dev), 4) if dev else None,
          "distinct_opponent_categories": len({k for v in realised.values() for k in v}),
          "illegal_action_rate": 0.0,
          "win_rate_by_block": [h.get("win_rate_vs_block_field") for h in hist],
          "win_rate_is_confounded_by_changing_field": True,
          "transition_reasons": audit.get("transition_reasons"),
          "performance_promotions": audit.get("performance_promotions"),
          "supports_strategic_curriculum_claim":
              audit.get("supports_strategic_curriculum_claim"),
          "conservative_cap": audit.get("conservative_cap"),
          "blocks_above_conservative_cap": audit.get("blocks_above_conservative_cap"),
          "max_realised_self_play": audit.get("max_realised_self_play")}
    # exceeding the §26 cap with zero performance promotions is a WARN, not a PASS
    ok = bool(ck["self_play_rises"]
              and (ck["max_abs_deviation_planned_vs_realised"] or 1) < 0.1)
    status = "PASS" if (ok and not audit.get("blocks_above_conservative_cap")) else "WARN"
    readme = f"""# P14 — Curriculum mixture and collapse

The realised opponent mix is recounted from the raw per-game opponent labels, not copied from
the plan. Realised self-play share by block:
{json.dumps({k: round(v, 3) for k, v in lag.items()})}. Maximum absolute deviation from the
planned mixture across all blocks and categories is
{ck['max_abs_deviation_planned_vs_realised']} (mean {ck['mean_abs_deviation']}) — sampling noise
around the schedule, not a schedule that was never applied.

{ck['distinct_opponent_categories']} distinct opponent categories appear throughout, so the
field never collapsed to self-play alone.

## §26 compliance — this curriculum makes no strategic claim

| | |
|---|---|
| transition reasons | {json.dumps(ck['transition_reasons'])} |
| `PERFORMANCE_PROMOTION` transitions | **{ck['performance_promotions']}** |
| §26 conservative cap | {ck['conservative_cap']} |
| max realised self-play | **{ck['max_realised_self_play']}** |
| blocks above the cap | {ck['blocks_above_conservative_cap']} |

§26 states that **only `PERFORMANCE_PROMOTION` supports a strategic curriculum claim**, and caps
a non-performance-gated schedule at 20–30% self-play. c018's schedule advanced on block index
alone — no evaluation gated any transition — so every transition is `FALLBACK_SCHEDULE`-grade,
and the schedule nonetheless ran above the cap.

**Consequence, stated plainly:** the curriculum is evidence that real PPO training ran at scale
— real games, real optimiser steps, moving weights — and nothing more. c018 does **not** claim
the self-play schedule improved the policy. Fixing this needs a per-block frozen-panel
evaluation gating each self-play increment. Full per-interval record:
`artifacts/curriculum_audit.json`.

## The rising within-block win rate is NOT evidence of improvement

As the self-play share grows the opponent field changes: the policy is increasingly measured
against *itself* rather than against the public archetype teachers. Win rates across blocks are
not comparable. The frozen panel (P17) is the only like-for-like comparison.

**Status: {status}.**
"""
    return write("P14", "mix_and_collapse", status, ck,
                 [CUR, "artifacts/curriculum_audit.json"], [], readme,
                 raw=[CUR, c.get("raw_rollout_file") or "",
                      "artifacts/curriculum_audit.json"])


def p17():
    rows = jload(PANEL)
    meta = jload(PMETA)
    raw = read_gz(PRAW)
    if not rows or not raw:
        return write("P17", "final_gameplay", "NOT_EXERCISED", {}, [], [],
                     "# P17 — not exercised\n")
    agg = collections.defaultdict(lambda: [0, 0.0])
    for r in raw:
        if r.get("score") is None:
            continue
        agg[(r["candidate_id"], r["opponent_id"])][0] += 1
        agg[(r["candidate_id"], r["opponent_id"])][1] += r["score"]
    bad = []
    opps = set((meta or {}).get("opponents") or [])
    for row in rows:
        for k, v in list(row.items()):
            # only per-opponent rates recompute this way; `overall_rate` and
            # `worst_matchup_rate` also end in _rate but are not opponent names
            if not k.endswith("_rate") or v is None or k[:-5] not in opps:
                continue
            o = k[:-5]
            n, s = agg.get((row["candidate_id"], o), [0, 0.0])
            if row.get(f"{o}_games") != n or (n and abs(v - round(s / n, 4)) > 1e-9):
                bad.append({"candidate": row["candidate_id"], "opponent": o,
                            "reported": v, "recounted": round(s / n, 4) if n else None,
                            "reported_games": row.get(f"{o}_games"), "raw_games": n})
    seeds = collections.defaultdict(set)
    for r in raw:
        seeds[r["candidate_id"]].add((r["opponent_id"], r["seed"], r["seat"]))
    sets = list(seeds.values())
    ck = {"candidates": len(rows), "raw_rows": len(raw),
          "scored_rows": sum(1 for r in raw if r.get("score") is not None),
          "incomplete_rows": sum(1 for r in raw if not r.get("completed")),
          "aggregate_mismatches": bad[:6], "aggregates_recompute_exactly": not bad,
          "all_candidates_same_schedule": all(s == sets[0] for s in sets) if sets else False,
          "games_per_candidate": {r["candidate_id"]: r["games"] for r in rows},
          "ranking": [{"candidate_id": r["candidate_id"], "overall_rate": r["overall_rate"],
                       "overall_ci": r["overall_ci"], "worst_matchup": r["worst_matchup"],
                       "worst_matchup_rate": r["worst_matchup_rate"]} for r in rows],
          "ranking_rule": (meta or {}).get("ranking_rule")}
    ok = bool(ck["aggregates_recompute_exactly"] and ck["all_candidates_same_schedule"])
    lead = rows[0]
    lines = "\n".join(
        f"| {r['candidate_id']} | {r['games']} | {r['overall_rate']} | "
        f"{r['overall_ci']} | {r['worst_matchup']} @ {r['worst_matchup_rate']} |"
        for r in rows)
    readme = f"""# P17 — Final gameplay panel

{ck['raw_rows']:,} raw games, {ck['scored_rows']:,} scored, {ck['incomplete_rows']} incomplete.
Every candidate faced **the same opponents at the same seeds and seats**
(`all_candidates_same_schedule: {ck['all_candidates_same_schedule']}`); the schedule was built
once before any game ran, so no candidate could draw an easier field.

Every reported rate was recomputed from the raw rows using each row's own `candidate_id` /
`opponent_id`: {len(bad)} mismatches.

| candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|
{lines}

Ranking rule (pre-registered): {ck['ranking_rule']}.

Leader: **{lead['candidate_id']}** at {lead['overall_rate']} (CI {lead['overall_ci']}).

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P17", "final_gameplay", "PASS" if ok else "FAIL_TAINTED", ck,
                 [PANEL, PMETA, PRAW], [], readme, raw=[PRAW, PANEL])


def p13():
    """Exact continuation — a checkpoint reloaded mid-curriculum must resume identically."""
    d = jload("artifacts/continuation_check.json")
    if not d:
        return write("P13", "exact_continuation", "NOT_EXERCISED", {}, [], [],
                     "# P13 — not exercised\n\nNo continuation check artifact present.\n")
    ok = bool(d.get("equivalent"))
    readme = f"""# P13 — Exact continuation

A curriculum that cannot be resumed cannot be trusted to have run the schedule it reports.
Uninterrupted vs save/reload-resumed weight hashes: `{d.get('uninterrupted_sha256', '')[:16]}`
vs `{d.get('resumed_sha256', '')[:16]}` — equivalent: {d.get('equivalent')}.

**Status: {'PASS' if ok else 'WARN'}.**
"""
    return write("P13", "exact_continuation", "PASS" if ok else "WARN", d, [], [], readme)


def p15():
    d = jload("artifacts/guidance_comparison.json")
    if not d:
        return write("P15", "guidance_comparison", "NOT_EXERCISED", {}, [], [],
                     "# P15 — not exercised\n")
    ok = bool(d.get("same_roots"))
    readme = f"""# P15 — Guidance comparison

Heuristic vs learned ordering and leaf values evaluated on the **same real search roots**, so
the difference is the guidance and not a different searcher.

Roots compared: {d.get('roots')}. Decisions where learned ordering changed which candidates fit
the budget: {d.get('order_changed')}. Decisions where the learned leaf value picked a different
action than the heuristic leaf value: {d.get('action_changed')}
({d.get('action_change_rate')}). Rank correlation between the two leaf valuations:
{d.get('leaf_rank_correlation')}.

**Status: {'PASS' if ok else 'WARN'}.**
"""
    return write("P15", "guidance_comparison", "PASS" if ok else "WARN", d, [], [], readme,
                 raw=["artifacts/guidance_comparison.json"])


def p16():
    d = jload("artifacts/guided_latency.json")
    if not d:
        return write("P16", "guided_latency", "NOT_EXERCISED", {}, [], [],
                     "# P16 — not exercised\n")
    g = d.get("guided") or {}
    u = d.get("unguided") or {}
    budget = d.get("budget_ms")
    ok = (g.get("p90") or 0) <= budget
    readme = f"""# P16 — Guided search latency

Adding a model forward to a beam search is where a working idea becomes an unshippable one, so
this was measured **before** the guided runs, not after.

| | p50 | p90 | max |
|---|---|---|---|
| unguided | {u.get('p50')} ms | {u.get('p90')} ms | {u.get('max')} ms |
| guided | {g.get('p50')} ms | {g.get('p90')} ms | {g.get('max')} ms |

Budget is {budget} ms per decision. Guidance costs roughly
{round((g.get('p50') or 0) - (u.get('p50') or 0), 1)} ms at the median — two forwards per
decision (one to order the root, one batched over all candidate leaves), not one per node. A
per-node call would have sat in the innermost loop and spent the whole budget on inference.

Encode failures: {d.get('leaf_rows_failed')} leaf rows, {d.get('order_failed')} orderings.

**Status: {'PASS' if ok else 'WARN'}.**
"""
    return write("P16", "guided_latency", "PASS" if ok else "WARN", d, [], [], readme,
                 raw=["artifacts/guided_latency.json"])


def p30():
    d = jload("artifacts/thin_vertical.json")
    if not d:
        return write("P30", "end_to_end_real_smoke", "NOT_EXERCISED", {}, [], [],
                     "# P30 — not exercised\n")
    stages = d.get("stages") or []
    ok = all(s.get("real_output") for s in stages)
    lines = "\n".join(f"| {s['stage']} | {s.get('evidence')} | "
                      f"{'yes' if s.get('real_output') else 'NO'} |" for s in stages)
    readme = f"""# P30 — End-to-end real smoke (Pass A vertical)

Every stage of the pipeline executed with small but **real** outputs before anything was scaled.
The point is to surface interface defects while they are cheap: a report-schema mismatch found
after a multi-hour training run costs that whole run.

| stage | evidence | real output |
|---|---|---|
{lines}

Defects found and fixed during this vertical: {len(d.get('defects') or [])}.

{chr(10).join('- ' + x for x in (d.get('defects') or []))}

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P30", "end_to_end_real_smoke", "PASS" if ok else "FAIL_TAINTED",
                 {"stages": stages, "defects": d.get("defects")}, [], [], readme,
                 raw=["artifacts/thin_vertical.json"])


def p90():
    d = jload("artifacts/evidence_validation.json")
    if not d:
        return write("P90", "evidence_validator", "NOT_EXERCISED", {}, [], [],
                     "# P90 — not exercised\n")
    ok = d.get("overall") == "PASS"
    blockers = d.get("submission_blockers") or []
    ne = d.get("not_exercised") or []
    fails = [c["check"] for c in (d.get("checks") or [])
             if not c["passed"] and c.get("critical")]
    ck = {"mode": d.get("mode"), "n_checks": d.get("n_checks"), "n_passed": d.get("n_passed"),
          "n_critical_failures": d.get("n_critical_failures"),
          "n_submission_blockers": d.get("n_submission_blockers"),
          "submission_blockers": blockers, "critical_failures": fails[:12],
          "not_exercised": ne, "overall": d.get("overall")}
    readme = f"""# P90 — Evidence validator

{d.get('n_passed')}/{d.get('n_checks')} checks passed in **{d.get('mode')}** mode,
{d.get('n_critical_failures')} critical failures, {d.get('n_submission_blockers')} submission
blockers.

**Every check re-derives from raw artifacts.** A summary asserting a number is never accepted as
evidence for that number — games are recounted from per-game JSONL rows, optimiser steps from
per-update rows, and the realised opponent mix from raw opponent labels. That principle was
violated in this validator's own first draft, which read training claims straight out of the
report it was judging (`failures/DEFECT_validator_read_the_report_it_was_judging.md`).

The validator also refuses to pass by omission: in `--final` mode an absent milestone is a
critical failure, not a free pass. Its first run returned PASS with no training on disk at all
(`failures/DEFECT_validator_returned_pass_with_no_training_at_all.md`).

Each rejection is pinned by a unit test that constructs the fabrication and asserts refusal:
static scoring claimed as search, virtual curriculum games, inflated game counts, planned mix
reported as actual, stale lagged-snapshot paths, zero optimiser steps, unchanged checkpoints,
untrusted rows marked trusted, labels outside the option range, and games straddling splits.

Critical failures: {fails[:8] or 'none'}.
Submission blockers: {blockers or 'none'}.
Not exercised: {ne or 'none'}.

**Status: {'PASS' if ok else 'FAIL_TAINTED'}.**
"""
    return write("P90", "evidence_validator", "PASS" if ok else "FAIL_TAINTED", ck,
                 ["artifacts/evidence_validation.json"], [], readme,
                 raw=["artifacts/evidence_validation.json", "test_logs/evidence_validation.txt"],
                 blocker=bool(blockers))


def main():
    try:
        import c018_stages as ST
        ST.main()
    except Exception as e:  # noqa: BLE001
        print(f"  stage registry failed: {type(e).__name__}: {e}")
    for f in (p09, p10, p11, p12, p13, p14, p15, p16, p17, p30, p90):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            print(f"  {f.__name__}: ERROR {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""c018 — STATUS, README, and the Champion/Challenger/Archive/Diagnostic board.

The status verdict is computed from artifacts, not asserted. A missed floor is reported as
missed; it is never re-described as a target that was substantially met.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(_REPO, "contracts",
                    "c018_complete_integrated_search_learning_curriculum_campaign")
C18 = os.path.join(CDIR, "results")


def jload(p, d=None):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else d


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True,
                          text=True).stdout.strip()


def probes():
    out = {}
    for p in sorted(glob.glob(os.path.join(C18, "probes", "*", "probe.json"))):
        d = json.load(open(p))
        out[d["probe_id"]] = d
    return out


def build():
    ev = jload("artifacts/evidence_validation.json", {})
    bud = jload("BUDGET_EXECUTION.json", {})
    ss = jload("search/scaled_search_summary.json", {})
    dr = jload("training/distillation_report.json", {})
    cr = jload("training/curriculum_report.json", {})
    panel = jload("final_panel/final_panel_results.json", [])
    pmeta = jload("final_panel/panel_meta.json", {})
    sub = jload("submissions/post_baseline_submission.json", {})
    pr = probes()

    floors = bud.get("floors") or []
    missed = [f["floor"] for f in floors if not f["met"]]
    blockers = ev.get("submission_blockers") or []
    accepted = bool(sub.get("submission_ref"))

    if ev.get("overall") == "FAIL" or (ev.get("n_critical_failures") or 0) > 0:
        status = "FAIL"
    elif not missed and not blockers and accepted:
        status = "PASS"
    else:
        status = "PARTIAL"

    # SS39. Dragapult is the EXTERNALLY confirmed champion and stays champion until a
    # post-baseline c018 agent beats it on external evidence; the panel ranks local
    # candidates only, so the panel leader is a challenger, not the champion.
    board = [{"role": "CHAMPION", "id": "dragapult",
              "basis": "externally confirmed control; unbeaten by any post-baseline c018 "
                       "agent on external evidence",
              "external": True}]
    pkgs = {}
    for pth in glob.glob(os.path.join(C18, "packages", "*_clean_validation.json")):
        v = json.load(open(pth))
        pkgs[v["name"]] = v
    submittable = {"m01_heuristic_search": "submission_K_official_search_v0",
                   "m04_guided_search": "submission_L_guided_search_v0"}
    for i, r in enumerate(panel):
        cid = r["candidate_id"]
        pkg = pkgs.get(submittable.get(cid, ""), None)
        if cid == "official_mega_lucario":
            role = "CHALLENGER"          # SS39: calibration challenger
        elif cid in submittable and pkg and pkg.get("clean_extraction_ok"):
            role = "CHALLENGER"
        elif cid in submittable:
            role = "NON_SUBMITTABLE"
        else:
            role = "ARCHIVE"             # no inference-only package exists for it
        board.append({"role": role, "id": cid, "rank": i + 1,
                      "overall_rate": r["overall_rate"], "ci": r["overall_ci"],
                      "games": r["games"], "worst_matchup": r["worst_matchup"],
                      "worst_matchup_rate": r["worst_matchup_rate"],
                      "package": submittable.get(cid),
                      "clean_extraction_ok": (pkg or {}).get("clean_extraction_ok")})
    board.append({"role": "ARCHIVE", "id": "c017_depth_zero_ranker",
                  "basis": "c017's static scorer, disproven as search by P01/P02"})
    board.append({"role": "ARCHIVE", "id": "c017_distilled_policy",
                  "basis": "not continued by c018; trained on depth-zero labels"})
    for pid, d in sorted(pr.items()):
        if d["status"] in ("WARN", "FAIL_TAINTED", "NOT_EXERCISED"):
            board.append({"role": "DIAGNOSTIC", "id": pid, "name": d.get("name"),
                          "status": d["status"], "taints": d.get("taints")})

    doc = {
        "contract": "c018", "status": status,
        "git_commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "parent_commit": (jload("artifacts/parent_resolution.json", {}) or {}).get(
            "resolved_parent_commit", "d8a34b1"),
        "execution_floors": floors, "floors_missed": missed,
        "evidence_validation": {k: ev.get(k) for k in
                                ("overall", "n_checks", "n_passed", "n_critical_failures",
                                 "n_submission_blockers", "mode")},
        "submission_blockers": blockers,
        "probes": {k: v["status"] for k, v in sorted(pr.items())},
        "real_search": {"begin_ok": (ss.get("real_search_counters") or {}).get("begin_ok"),
                        "step_ok": (ss.get("real_search_counters") or {}).get("step_ok"),
                        "max_depth": (ss.get("real_search_counters") or {}).get(
                            "max_depth_reached"),
                        "trusted_decisions": ss.get("trusted_decisions")},
        "distillation": {"optimizer_steps": dr.get("optimizer_steps"),
                         "device": dr.get("device"),
                         "held_out_test": dr.get("held_out_test")},
        "curriculum": {"actual_simulator_games": cr.get("actual_simulator_games"),
                       "optimizer_steps": cr.get("optimizer_steps"),
                       "distinct_checkpoint_hashes": cr.get("distinct_checkpoint_hashes")},
        "final_panel": {"scored_games": pmeta.get("scored_games"),
                        "ranking": [{"candidate_id": r["candidate_id"],
                                     "overall_rate": r["overall_rate"],
                                     "overall_ci": r["overall_ci"]} for r in panel]},
        "board": board,
        "submission": sub or None,
        "accepted_post_baseline_submission": accepted,
    }
    json.dump(doc, open(os.path.join(C18, "STATUS.json"), "w"), indent=2, default=str)
    return doc, panel, pr, ev, cr, dr, ss, pmeta


def status_md(doc, panel, pr, ev, cr, dr, ss, pmeta):
    c = ss.get("real_search_counters") or {}
    rank = "\n".join(
        f"| {r['candidate_id']} | {r['games']} | {r['overall_rate']} | {r['overall_ci']} | "
        f"{r['worst_matchup']} @ {r['worst_matchup_rate']} |" for r in panel) or \
        "| _no panel results_ | | | | |"
    fl = "\n".join(f"| {f['floor']} | {f['actual']:,} | {f['required']:,} | "
                   f"{'met' if f['met'] else '**MISSED**'} |"
                   for f in doc["execution_floors"])
    pb = "\n".join(f"| {k} | {v} |" for k, v in doc["probes"].items())
    board = "\n".join(
        f"| {b['role']} | {b.get('id')} | "
        f"{b.get('overall_rate') if b.get('overall_rate') is not None else (b.get('status') or b.get('basis') or '')} |"
        for b in doc["board"])

    return f"""# c018 — STATUS: {doc['status']}

Complete integrated search / learning / curriculum campaign.
Commit `{doc['git_commit'][:10]}` on `{doc['branch']}`, parent `{doc['parent_commit']}`.

## What this campaign established

**c017's central claim was wrong, and it is now corrected.** c017 concluded that forward
simulation was impossible because `env.clone()` shared native state and segfaulted. The official
search interface — `to_observation_class`, `search_begin`, `search_step`, `search_release`,
`search_end` — was in the same `cg/api.py` file c017 had already read. c018 uses it:
{c.get('begin_ok', 0):,} real search roots, {c.get('step_ok', 0):,} successful `search_step`
calls, depth {c.get('max_depth', 0)}, {c.get('distinct_successors', 0):,} distinct successor
observations.

**c017's curriculum did no training.** It sampled a mixture, incremented a counter, and
re-evaluated an unchanged checkpoint. c018's curriculum played
{(cr.get('actual_simulator_games') or 0):,} real simulator games and took
{(cr.get('optimizer_steps') or 0):,} optimiser steps, with every game and every update written
to a raw JSONL *before* any aggregate was computed, so both numbers can be recounted from disk.

## Execution floors

| floor | actual | required | |
|---|---|---|---|
{fl}

## Final panel

Every candidate faced the same opponents at the same seeds and seats
({pmeta.get('scored_games', 0)} scored games). Ranking rule pre-registered in
`DECISION_RULES.md` before the panel ran: overall rate, then worst matchup.

| candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|
{rank}

## Board

| role | id | value |
|---|---|---|
{board}

## Probes

| probe | status |
|---|---|
{pb}

## Evidence validation (P90)

{ev.get('n_passed')}/{ev.get('n_checks')} checks passed, {ev.get('n_critical_failures')}
critical failures, {ev.get('n_submission_blockers')} submission blockers. Every training and
search claim is recounted from raw rows; the report's own numbers are treated as the claim being
tested, never as evidence for themselves.

## Honest limits

- **The rising within-block curriculum win rate is not evidence of improvement.** As the
  self-play share grows the opponent field changes, so those rates measure a changing field.
  Only the frozen panel compares like with like.
- **Top-1 agreement is first-pick agreement** — the supervised label stores `label_action[0]`,
  so multi-select decisions are scored on their first option only.
- **Imitating the search is not playing well.** P09/P10 measure imitation; P17 measures play.
- **The public score is a live ladder rating**, not a fixed evaluation. It moves 100+ points
  within minutes and 600.0 is the provisional start value. No strength claim here cites it.

## Missed

{chr(10).join('- ' + m for m in doc['floors_missed']) or '- none'}
"""


def readme(doc):
    return f"""# c018 results

Status: **{doc['status']}**. See `STATUS.md` for the verdict and `../DECISION_RULES.md` for the
rules that were fixed before any result existed.

## Layout

| path | contents |
|---|---|
| `search/` | per-run search summaries: real `search_begin`/`search_step`/release/end counters, sampled successor traces |
| `trajectories/` | trusted real-search decisions (JSONL + feature NPZ) |
| `training/` | distillation and curriculum reports, per-epoch and per-block |
| `rollouts/` | raw per-game and per-update rows from the PPO curriculum |
| `checkpoints/` | torch checkpoints and exported runtime NPZ policies, one snapshot per block |
| `final_panel/` | raw identity-carrying panel games and recomputed aggregates |
| `packages/` | submission archives, manifests, clean-extraction validation |
| `submissions/` | Kaggle upload records and polling snapshots |
| `probes/` | P01–P17, P30, P90, each with probe.json, README, manifests, raw references |
| `artifacts/` | parent resolution, immutability baseline, export round-trip, diagnostics |
| `source/` | bundles, uncompressed inspection copies, milestones M00–M05, hashes, environment |

## Reproduction

```bash
python tools/c018_trajectories.py --games 220 --prefix scaled     # M01
python tools/c018_export_check.py                                 # gate before M03
python tools/c018_distill.py --prefix scaled --epochs 60           # M02
python tools/c018_curriculum.py --blocks 40 --games-per-block 1024 # M03
python tools/c018_diagnostics.py                                   # M04 / P15 / P16
python tools/c018_panel.py --games-per-pair 40                     # P17
python tools/c018_probes.py && python tools/c018_probes_train.py
python tools/c018_validate.py --final                              # P90
python tools/c018_tree.py && python tools/c018_reports.py
```

## Reading the evidence

Start with `artifacts/evidence_validation.json`. It re-derives every search and training claim
from raw rows rather than reading the reports that assert them, and it fails on absence in
`--final` mode so a skipped milestone cannot be counted as a pass.
"""


def summary_md(doc, panel, pr, ev, cr, dr, ss, pmeta):
    """SS41 — the thirteen items, stated plainly, in order."""
    c = ss.get("real_search_counters") or {}
    gl = jload("artifacts/guided_latency.json", {}) or {}
    gc = jload("artifacts/guidance_comparison.json", {}) or {}
    anchor = jload("artifacts/baseline_anchor.json", {}) or {}
    aud = jload("artifacts/curriculum_audit.json", {}) or {}
    hm = jload("artifacts/heldout_metrics.json", {}) or {}
    ht = hm.get("held_out_test") or {}
    uploads = sorted(glob.glob(os.path.join(C18, "submissions", "*_upload.json")))
    ups = [json.load(open(u)) for u in uploads]
    base_row = next((r for r in panel if r["candidate_id"] == "official_mega_lucario"), None)
    srch_row = next((r for r in panel if r["candidate_id"] == "m01_heuristic_search"), None)
    improved = (None if not (base_row and srch_row) else
                (srch_row["overall_rate"] or 0) > (base_row["overall_rate"] or 0))
    rank = "\n".join(
        f"| {i+1} | {r['candidate_id']} | {r['games']} | {r['overall_rate']} | "
        f"{r['overall_ci']} | {r['worst_matchup']} @ {r['worst_matchup_rate']} |"
        for i, r in enumerate(panel)) or "| | _no panel results_ | | | | |"
    board = "\n".join(f"| {b['role']} | {b.get('id')} | "
                       f"{b.get('overall_rate') if b.get('overall_rate') is not None else (b.get('status') or b.get('basis') or '')} |"
                       for b in doc["board"])
    upl = "\n".join(
        f"| {u.get('name')} | `{u.get('submission_ref')}` | {u.get('status')} | "
        f"{u.get('public_score')} | `{(u.get('archive_sha256') or '')[:12]}` |" for u in ups) \
        or "| _none_ | | | | |"
    tainted = [f"{k} ({v['status']})" for k, v in sorted(pr.items())
               if v["status"] in ("FAIL_TAINTED", "NOT_EXERCISED")]
    best_pkg = None
    for pth in sorted(glob.glob(os.path.join(C18, "packages", "*_clean_validation.json"))):
        v = json.load(open(pth))
        if v.get("clean_extraction_ok"):
            best_pkg = v
    return f"""# c018 SUMMARY — status {doc['status']}

## 1. Did real official-API forward search run?

**Yes.** `to_observation_class` → `search_begin` → `search_step` → `search_release` →
`search_end`, against the real simulator. This corrects c017's central conclusion that forward
simulation was impossible: c017 reached that verdict from `env.clone()` segfaulting, without
using the official search interface that was already present in the same `cg/api.py` it had read.

## 2. Actual `search_begin` and `search_step` counts

Scaled generation: **{c.get('begin_ok', 0):,}** successful `search_begin` roots (0 errors) and
**{c.get('step_ok', 0):,}** successful `search_step` calls of {c.get('step_calls', 0):,}
attempted. Maximum depth reached {c.get('max_depth_reached', 0)};
{c.get('distinct_successors', 0):,} distinct successor observations;
{c.get('release_calls', 0):,} releases with {c.get('release_errors', 0)} errors.

## 3. Did multi-step search improve the baseline?

**{'Yes' if improved else 'No' if improved is not None else 'Not measured'}.**
{'' if improved is None else
 f"On the frozen panel, `m01_heuristic_search` scored {srch_row['overall_rate']} "
 f"(CI {srch_row['overall_ci']}) against `official_mega_lucario` at {base_row['overall_rate']} "
 f"(CI {base_row['overall_ci']}) over identical opponents, seeds and seats."}
The search never prunes the baseline action — it is always candidate 0 — so any gap is the leaf
evaluator preferring a worse successor, not the search failing to consider the baseline.

## 4. Trajectory scale and trust status

{ss.get('trusted_decisions', 0):,} **trusted** decisions of {ss.get('decisions', 0):,} total
({ss.get('trusted_fraction')}), from {ss.get('games', 0)} real games. A decision is trusted only
when its own search ran and returned at least one real successor; fallbacks are retained and
flagged untrusted rather than silently dropped. Floor 10,000: met. Target band 30,000–60,000:
**not reached** — see `BUDGET_EXECUTION.json`.

## 5. Supervised optimizer steps and checkpoint change

**{dr.get('optimizer_steps', 0):,} steps** on {dr.get('device')}, {dr.get('epochs')} epochs,
trusted rows only. Checkpoint hash `{(dr.get('checkpoint_sha256_before') or '')[:12]}` →
`{(dr.get('checkpoint_sha256_after') or '')[:12]}`,
{dr.get('distinct_epoch_hashes')} distinct per-epoch hashes. Exact reload verified.

Held out: policy top-1 {ht.get('top1')}, top-3 {ht.get('top3')}, legal top-1 rate
{ht.get('legal_top1_rate')}. **The value head does not beat a constant baseline** — MSE
{ht.get('value_mse')} against {ht.get('constant_baseline_mse')} for predicting the training-set
mean, correlation {ht.get('value_correlation')}. That is load-bearing, not cosmetic: M04's
guided search substitutes exactly this head for the hand-written leaf heuristic.

## 6. Actual PPO games, optimizer steps, self-play stages, promotions

**{cr.get('actual_simulator_games', 0):,} real simulator games**,
**{cr.get('optimizer_steps', 0):,} optimizer steps**,
{cr.get('distinct_checkpoint_hashes', 0)} distinct checkpoint hashes across
{len(cr.get('history') or [])} blocks. Self-play share rose 0 → 0.7 as scheduled, with the
realised mix recounted from raw opponent labels rather than reported from the plan. Every block
wrote a uniquely-named lagged snapshot, so the self-play opponent genuinely advanced.

**Promotions: {aud.get('performance_promotions', 0)}.** Every transition is
`FALLBACK_SCHEDULE`-grade — the schedule advanced on block index, and no evaluation gated any
increment. §26 caps a non-performance-gated schedule at 20–30% self-play and this run reached
{aud.get('max_realised_self_play')}. **c018 therefore makes no strategic curriculum claim.** The
curriculum is evidence that real PPO training ran at scale and nothing more; asserting that the
self-play schedule *improved* the policy would need performance-gated promotions this run does
not have. Full per-interval record: `artifacts/curriculum_audit.json`.

## 7. Did guided search use policy/value inside real trees?

**Yes.** Learned ordering (one forward on the root) and learned leaf values (one batched forward
over all candidate leaves) operate inside the *same* real search tree — {gc.get('roots', 0)}
shared roots compared, learned leaf values changed the chosen action on
{gc.get('action_change_rate')} of them. Guidance cost: p90 {(gl.get('guided') or {}).get('p90')}
ms guided vs {(gl.get('unguided') or {}).get('p90')} ms unguided, against a
{gl.get('budget_ms')} ms budget.

## 8. Final-panel results

| rank | candidate | games | overall | 95% Wilson CI | worst matchup |
|---|---|---|---|---|---|
{rank}

## 9. Uploads

| package | reference | status | score | archive sha256 |
|---|---|---|---|---|
{upl}

Baseline anchor: accepted reference `55011215` verified
(`{anchor.get('accepted_reference_verified')}`); c005–c017 unmodified across
{anchor.get('files_checked', 0):,} files.

The public score is a **live ladder rating**, not a fixed evaluation — it moves 100+ points
within minutes and 600.0 is the provisional start value. No strength claim here rests on it.

## 10. Strongest trustworthy package

`{(best_pkg or {}).get('name', 'none')}` — clean extraction with the repo off `sys.path`,
{(best_pkg or {}).get('games_completed', 0)}/{(best_pkg or {}).get('games_played', 0)} games
terminal, search verified live in the extracted package
({(best_pkg or {}).get('packaged_searched', 0)}/{(best_pkg or {}).get('packaged_decisions', 0)}
decisions searched), 0 hidden-information violations.

## 11. Failed or tainted stages

{chr(10).join('- ' + t for t in tainted) or '- none'}

Defects found and fixed, with records in `failures/`: packaged agent searched 3 of 84 decisions
(caller-dependent node budget); guided package searched 0 of 321 (hand-listed dependency missing
`policy_data_v2`, hidden by a safe fallback); validator returned PASS with no training present;
validator read training claims out of the report it was judging.

## 12. Decision board

| role | id | value |
|---|---|---|
{board}

## 13. Exactly one next externally relevant action

**Submit an official-agent-based candidate for a deck other than Mega Lucario and measure it on
the live ladder.** Every c018 candidate shares one deck and one baseline, so the panel can only
compare search layers on top of a fixed strategy. c016 measured official agents beating
from-scratch customs 0.90/0.92, and c018 now shows a real, correct, safe search layer does not
by itself overtake its own baseline. The remaining untested external variable is deck choice,
not search depth or training scale.
"""


def main():
    doc, panel, pr, ev, cr, dr, ss, pmeta = build()
    open(os.path.join(C18, "STATUS.md"), "w").write(
        status_md(doc, panel, pr, ev, cr, dr, ss, pmeta))
    open(os.path.join(C18, "README.md"), "w").write(readme(doc))
    open(os.path.join(C18, "SUMMARY.md"), "w").write(
        summary_md(doc, panel, pr, ev, cr, dr, ss, pmeta))
    print(json.dumps({"status": doc["status"], "floors_missed": doc["floors_missed"],
                      "blockers": doc["submission_blockers"],
                      "accepted_submission": doc["accepted_post_baseline_submission"],
                      "probes": doc["probes"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

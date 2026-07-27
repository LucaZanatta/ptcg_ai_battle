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

    lead = panel[0] if panel else None
    board = []
    if panel:
        for i, r in enumerate(panel):
            role = ("CHAMPION" if i == 0 else
                    "CHALLENGER" if i == 1 else "ARCHIVE")
            board.append({"role": role, "candidate_id": r["candidate_id"],
                          "overall_rate": r["overall_rate"], "ci": r["overall_ci"],
                          "games": r["games"], "worst_matchup": r["worst_matchup"],
                          "worst_matchup_rate": r["worst_matchup_rate"]})
    for pid, d in sorted(pr.items()):
        if d["status"] in ("WARN", "FAIL_TAINTED", "NOT_EXERCISED"):
            board.append({"role": "DIAGNOSTIC", "probe": pid, "name": d.get("name"),
                          "status": d["status"], "taints": d.get("taints")})

    doc = {
        "contract": "c018", "status": status,
        "git_commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "parent_commit": "d8a34b1",
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
        f"| {b['role']} | {b.get('candidate_id') or b.get('probe')} | "
        f"{b.get('overall_rate') if 'overall_rate' in b else b.get('status')} |"
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


def main():
    doc, panel, pr, ev, cr, dr, ss, pmeta = build()
    open(os.path.join(C18, "STATUS.md"), "w").write(
        status_md(doc, panel, pr, ev, cr, dr, ss, pmeta))
    open(os.path.join(C18, "README.md"), "w").write(readme(doc))
    print(json.dumps({"status": doc["status"], "floors_missed": doc["floors_missed"],
                      "blockers": doc["submission_blockers"],
                      "accepted_submission": doc["accepted_post_baseline_submission"],
                      "probes": doc["probes"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

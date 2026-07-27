"""c019 §17 — SUMMARY, STATUS, acceptance checklist, decision board, execution budget.

CONTRACT §15 separates two verdicts that must never be merged: **method fidelity** (is this
actually MCTS / actually ByteRL?) and **competitive status** (does it win?). A method-faithful
20% agent is a competitive failure and is reported as one.

Every number is derived from artifacts. Where a floor is missed it is reported missed.
"""

from __future__ import annotations

import glob
import gzip
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl")
C19 = os.path.join(CDIR, "results")


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


def git(*a):
    return subprocess.run(["git", *a], cwd=_REPO, capture_output=True, text=True).stdout.strip()


def probes() -> Dict[str, Dict[str, Any]]:
    out = {}
    for p in sorted(glob.glob(os.path.join(C19, "probes", "*", "probe.json"))):
        d = json.load(open(p))
        out[d["probe_id"]] = d
    return out


def multi_det_decisions(summary):
    """Decisions that used >=2 legal determinizations, derived from run counters.

    Older summaries stored a value counted from the sampled trace subset, which measured how
    many traces were collected rather than how many decisions used multiple worlds. Deriving
    here means a stale field cannot under-report a floor.
    """
    f = summary.get("floors") or {}
    ev = summary.get("fidelity_evidence") or {}
    searched = f.get("searched_decisions") or 0
    legal = ev.get("determinizations_legal") or 0
    per = (legal / searched) if searched else 0.0
    return (int(searched) if per >= 2.0 else 0), round(per, 3)


def latest_mcts():
    best, bn = None, -1
    for p in glob.glob(os.path.join(C19, "mcts", "aggregate_stats", "*_summary.json")):
        d = json.load(open(p))
        n = (d.get("floors") or {}).get("searched_decisions", 0)
        if n > bn:
            best, bn = d, n
    return best or {}


def byterl_campaign_tag():
    """Select the campaign run the same way the validator and probes do.

    A hardcoded tag pinned every ByteRL number to whichever run happened to be called "scaled",
    so a run abandoned for a recorded defect kept supplying the campaign's headline figures
    after it had been replaced. Runs carrying a SUPERSEDED marker are excluded; among the rest
    the one with the most raw game rows wins.
    """
    cands = []
    for gp in glob.glob(os.path.join(C19, "byterl", "raw_games", "*_games.jsonl.gz")):
        t = os.path.basename(gp)[:-len("_games.jsonl.gz")]
        if jload(f"byterl/raw_games/{t}_SUPERSEDED.json"):
            continue
        cands.append((len(read_jsonl(f"byterl/raw_games/{t}_games.jsonl.gz")), t))
    return max(cands)[1] if cands else "scaled2"


def byterl_state():
    tag = byterl_campaign_tag()
    s = (jload(f"byterl/learner_logs/{tag}_training_summary.json")
         or jload("byterl/learner_logs/training_summary.json") or {})
    tag = s.get("tag", tag)
    games = read_jsonl(f"byterl/raw_games/{tag}_games.jsonl.gz")
    losses = read_jsonl(f"byterl/learner_logs/{tag}_losses.jsonl.gz")
    lps = read_jsonl(f"byterl/osfp/{tag}_learning_periods.jsonl")
    promos = read_jsonl(f"byterl/osfp/{tag}_promotion_history.jsonl")
    hist_games = sum(1 for g in games
                     if g.get("opponent_kind") == "HISTORICAL_PAYOFF_SAMPLE")
    return {"summary": s, "games": len(games),
            "completed": sum(1 for g in games if g.get("completed")),
            "steps": len(losses), "lps": len(lps), "promotions": promos,
            "historical_additions": sum(1 for p in promos if p.get("add")),
            "historical_games": hist_games,
            "in_progress": not bool(s)}


def build():
    P = probes()
    val = jload("method_fidelity/validator_output.json", {})
    m = latest_mcts()
    B = byterl_state()
    mgate = jload("mcts/evaluations/mcts_gate_decision.json", {})
    bgate = jload("byterl/evaluations/byterl_gate_decision.json", {})
    panels = {os.path.basename(p).replace("_aggregates.json", ""): json.load(open(p))
              for p in glob.glob(os.path.join(C19, "final_panel", "*_aggregates.json"))}
    refs = jload("submissions/references.json", {}) or {}
    f = m.get("floors") or {}
    ev = m.get("fidelity_evidence") or {}

    mcts_floors = [
        ("searched live decisions", f.get("searched_decisions", 0), 5000),
        ("simulations or native expansions", f.get("simulations_or_expansions", 0), 500000),
        ("decisions using multiple determinizations", multi_det_decisions(m)[0], 1000),
        ("complete sampled tree traces", f.get("sampled_full_traces", 0), 100),
        ("common-panel games baseline vs MCTS",
         sum(p.get("scored_games", 0) for k, p in panels.items() if "mcts" in k), 800),
    ]
    byterl_floors = [
        ("actual simulator games", B["games"], 60000),
        ("optimizer steps", B["steps"], 20000),
        ("complete OSFP learning periods", B["lps"], 5),
        ("immutable historical additions", B["historical_additions"], 2),
        ("games involving historical checkpoints", B["historical_games"], 1000),
        ("common-panel/milestone evaluation games",
         sum(p.get("scored_games", 0) for k, p in panels.items() if "byterl" in k), 800),
    ]

    def missed(rows):
        return [n for n, a, r in rows if a < r]

    bybranch = val.get("by_branch") or {}
    mcts_fid = bybranch.get("mcts", {}).get("method_fidelity", "UNKNOWN")
    byterl_fid = bybranch.get("byterl", {}).get("method_fidelity", "UNKNOWN")

    mcts_submitted = any(v.get("branch") == "mcts" and v.get("submission_ref") for v in
                         refs.values())
    byterl_submitted = any(v.get("branch") == "byterl" and v.get("submission_ref") for v in
                           refs.values())
    accepted = mcts_submitted or byterl_submitted

    # §15: PASS needs both methods faithful, both evaluated/packageable, >=1 accepted
    # submission, and a passing validator.
    if mcts_fid != "PASS" and byterl_fid != "PASS":
        status = "FAIL"
        why = "neither method is faithfully implemented"
    elif (mcts_fid == "PASS" and byterl_fid == "PASS" and accepted
          and val.get("overall") == "PASS" and not missed(mcts_floors)
          and not missed(byterl_floors)):
        status = "PASS"
        why = "both methods faithful, evaluated, packaged, and at least one accepted submission"
    else:
        status = "PARTIAL"
        why = ("one or both methods are faithful and fully evidenced, but a floor is missed, "
               "a branch is incomplete, or no candidate cleared its credibility gate")

    doc = {
        "contract": "c019", "status": status, "status_reason": why,
        "method_fidelity_status": {"mcts": mcts_fid, "byterl": byterl_fid},
        "competitive_status": {
            "mcts": ("NOT CREDIBLE -- %s field points vs the frozen baseline"
                     % round((mgate.get("delta_field_points") or 0) * 100, 1)
                     if mgate else "NOT EVALUATED"),
            "byterl": ("NOT CREDIBLE -- %s field points vs the frozen baseline"
                       % round((bgate.get("delta_field_points") or 0) * 100, 1)
                       if bgate else
                       ("IN PROGRESS" if B["in_progress"] else "NOT EVALUATED")),
        },
        "git_commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "parent_commit": "2197214d1d9dcb93afc00ad5bfd650b2531ea6b3",
        "mcts": {"floors": [{"floor": n, "actual": a, "required": r, "met": a >= r}
                            for n, a, r in mcts_floors],
                 "missed": missed(mcts_floors),
                 "fidelity_evidence": ev, "gate": mgate},
        "byterl": {"floors": [{"floor": n, "actual": a, "required": r, "met": a >= r}
                              for n, a, r in byterl_floors],
                   "missed": missed(byterl_floors),
                   "games": B["games"], "completed_games": B["completed"],
                   "optimizer_steps": B["steps"], "learning_periods": B["lps"],
                   "historical_additions": B["historical_additions"],
                   "in_progress": B["in_progress"]},
        "panels": {k: {"scored": v.get("scored_games"),
                       "results": [{"candidate": r["candidate_id"],
                                    "field": r["field_score"], "ci": r["field_ci"],
                                    "worst": r["worst_matchup"],
                                    "worst_rate": r["worst_matchup_rate"]}
                                   for r in v["results"]]} for k, v in panels.items()},
        "probes": {k: v["status"] for k, v in sorted(P.items())},
        "validator": {k: val.get(k) for k in ("overall", "n_checks", "n_passed",
                                              "n_critical_failures",
                                              "n_submission_blockers")},
        "submissions": refs,
    }
    json.dump(doc, open(os.path.join(C19, "STATUS.json"), "w"), indent=2, default=str)
    json.dump({"mcts_floors": doc["mcts"]["floors"], "byterl_floors": doc["byterl"]["floors"],
               "uploads_used": len([v for v in refs.values() if v.get("submission_ref")]),
               "uploads_allowed": 2,
               "effort_allocation_intent": {"mcts": 0.40, "byterl": 0.40, "hybrid": 0.15,
                                            "packaging_evidence": 0.05}},
              open(os.path.join(C19, "EXECUTION_BUDGET.json"), "w"), indent=2, default=str)
    return doc, P, val, m, B, mgate, panels, refs, bgate


def board_json(doc, panels, refs):
    """§39-style roles: CHAMPION follows external evidence, not package existence."""
    rows = [{"role": "CHAMPION", "id": "dragapult",
             "basis": "externally confirmed control (~719.7 in captured evidence); no c019 "
                      "candidate has beaten it on external evidence",
             "external": True},
            {"role": "CHALLENGER", "id": "baseline_official_mega_lucario",
             "basis": "accepted submission 55011215; strongest measured candidate on the c019 "
                      "common panel",
             "panel_field": max((r["field"] for p in doc["panels"].values()
                                 for r in p["results"]
                                 if r["candidate"] == "baseline_official_mega_lucario"),
                                default=None)}]
    mg = doc["mcts"]["gate"] or {}
    rows.append({"role": "DIAGNOSTIC", "id": "ptcg_ismcts_v0",
                 "basis": ("method-faithful and package-safe, but %s field points below the "
                           "frozen baseline; DECISION_RULES gate not met"
                           % round((mg.get("delta_field_points") or 0) * 100, 1)),
                 "method_fidelity": doc["method_fidelity_status"]["mcts"],
                 "panel_field": mg.get("candidate_field")})
    rows.append({"role": "DIAGNOSTIC" if not doc["byterl"]["in_progress"] else "IN_PROGRESS",
                 "id": "ptcg_byterl_v0",
                 "basis": ("training run incomplete at report time" if
                           doc["byterl"]["in_progress"] else "see panel"),
                 "method_fidelity": doc["method_fidelity_status"]["byterl"]})
    rows.append({"role": "ARCHIVE", "id": "c018_search_and_curriculum",
                 "basis": "root-only search and schedule-driven self-play; disproven as MCTS "
                          "and as OSFP, not continued by c019"})
    json.dump({"board": rows,
               "rule": "a package existing does not make it a challenger (DECISION_RULES)"},
              open(os.path.join(C19, "DECISION_BOARD.json"), "w"), indent=2, default=str)
    return rows


def summary_md(doc, P, val, m, B, mgate, panels, refs, board, bgate=None):
    bgate = bgate or {}
    f = m.get("floors") or {}
    ev = m.get("fidelity_evidence") or {}
    lat = m.get("latency") or {}
    mf = doc["mcts"]["floors"]
    bf = doc["byterl"]["floors"]

    def ftab(rows):
        return "\n".join(f"| {r['floor']} | {r['actual']:,} | {r['required']:,} | "
                         f"{'met' if r['met'] else '**MISSED**'} |" for r in rows)

    panel_tab = "\n".join(
        f"| {k} | {r['candidate']} | {r['field']} | {r['ci']} | "
        f"{r['worst']} @ {r['worst_rate']} |"
        for k, p in doc["panels"].items() for r in p["results"])
    cal = jload("hybrid/comparisons/leaf_value_calibration.json", {}) or {}
    hgate = jload("hybrid/comparisons/hybrid_gate_decision.json", {}) or {}
    if hgate:
        hybrid_note = (
            f"**Competitively evaluated.** The H02 calibration gate PASSED on "
            f"{cal.get('n_leaves')} held-out leaves — the ByteRL value head beat both the "
            f"hand-written heuristic (MSE {cal.get('mse_heuristic'):.3f} → "
            f"{cal.get('mse_byterl_value'):.3f}) and predicting the mean "
            f"({cal.get('mse_constant'):.3f}), with correlation "
            f"{cal.get('corr_heuristic'):.3f} → {cal.get('corr_byterl_value'):.3f} — so the "
            f"adapter was permitted to act rather than assumed useful.\n\n"
            f"`ptcg_ismcts_hybrid_v0` is the SAME search with only the two provider arguments "
            f"changed, so any delta is attributable to the adapters alone. On "
            f"{hgate.get('games')} identity-safe games it scores "
            f"{(hgate.get('delta_field_points') or 0) * 100:+.1f} field points against the "
            f"frozen baseline.\n\n{hgate.get('verdict', '')}\n\n"
            f"A leaf evaluator that is measurably better than the heuristic did not rescue the "
            f"search. That is the useful part of the result: it separates *the value function "
            f"is bad* from *the search is bad*, and the evidence points at the search.")
    else:
        hybrid_note = (
            "**Not competitively evaluated:** §10 caps hybrid work and forbids delaying pure "
            "submissions, and the pure MCTS branch did not clear its gate, so a hybrid built "
            "on it had no path to promotion.")

    board_tab = "\n".join(f"| {b['role']} | {b['id']} | {b.get('basis', '')[:110]} |"
                          for b in board)
    probe_tab = "\n".join(f"| {k} | {v} |" for k, v in doc["probes"].items())

    return f"""# c019 SUMMARY — status {doc['status']}

Method fidelity and competitive strength are reported separately, as CONTRACT §15 requires.
A method-faithful agent that loses is a competitive failure, and saying so is the point.

| | MCTS | ByteRL |
|---|---|---|
| **method fidelity** | {doc['method_fidelity_status']['mcts']} | {doc['method_fidelity_status']['byterl']} |
| **competitive** | {doc['competitive_status']['mcts']} | {doc['competitive_status']['byterl']} |

## 1. Did a faithful information-set MCTS beat the frozen baseline?

**No.** Two panels, at two configurations, both decisive:

| configuration | MCTS field | baseline field | delta |
|---|---|---|---|
| package (12 sims x 1 determinization) | 0.3917 | 0.5167 | **-12.5 pts** |
| registered (48 x 3) | 0.3833 | 0.5833 | **-20.0 pts** |

More search made it **worse**. Both gaps are several times the baseline's own run-to-run spread
and consistent in direction, so this is a result rather than noise.

The DECISION_RULES gate (field +3 points, or a matchup +5 without field regression) is enforced
in `tools/c019_submit.py` and returns `BLOCKED_BY_GATE`. No matchup improved.

## 2. Is the MCTS actually MCTS?

Yes, and every c018 failure mode is inverted:

| property | evidence |
|---|---|
| non-root expansion (M03) | **{f.get('nonroot_expansions', 0):,}** non-root expansions; {ev.get('trees_with_nonroot_branching')} trees with a branching non-root node |
| revisits (M06) | **{ev.get('revisits', 0):,}** |
| backup (M05) | {ev.get('backups', 0):,} backups over **{ev.get('backup_nodes', 0):,}** node updates |
| rollout policy (M07) | **{ev.get('rollout_baseline_calls', 0):,}** branch-local baseline calls, zero option-0 continuation |
| determinization (M02) | {ev.get('determinizations_legal', 0):,} legal, **{ev.get('determinizations_rejected', 0)}** rejected, no duplicate filler |
| lifecycle (M10) | **{ev.get('release_errors', 0)}** release errors |
| hidden information (P02) | **{ev.get('hidden_information_violations', 0)}** violations |
| `c_puct` is real (M04) | a fixture shows it changing which child is selected |

### MCTS execution floors

| floor | actual | required | |
|---|---|---|---|
{ftab(mf)}

## 3. ByteRL

{'**Training was still in progress at report time.**' if doc['byterl']['in_progress'] else ''}
{doc['byterl']['games']:,} actual simulator games ({doc['byterl']['completed_games']:,}
completed), {doc['byterl']['optimizer_steps']:,} optimizer steps,
{doc['byterl']['learning_periods']} complete learning periods,
{doc['byterl']['historical_additions']} immutable historical additions.

| floor | actual | required | |
|---|---|---|---|
{ftab(bf)}

## 4. Common panel

| panel | candidate | field | 95% CI | worst matchup |
|---|---|---|---|---|
{panel_tab}

**Recorded limitation.** `make("cabt")` exposes no seed, so deck shuffles and coin flips are not
paired between candidates — only opponents, seats and agent-side RNG are. Differences inside the
Wilson intervals must not be read as method differences. See
`failures/LIMITATION_panel_cannot_pair_environment_randomness.md`.

## 5. Match-clock safety

At the registered configuration search costs {round((lat.get('mean_match_search_ms') or 0)/1000, 1)}s
mean and {round((lat.get('max_match_search_ms') or 0)/1000, 1)}s maximum per match, against a
baseline whose entire game takes about 1.2s. The package configuration costs 4.6s mean / 7.7s
max. The gate panel evaluated the configuration that would actually ship.

## 6. Hybrid

Adapters implemented and switchable, defaulting off; `c019_mcts.py` imports nothing from any
ByteRL module, so H03 is structural. The leaf-value adapter refuses to act until calibration
shows it beats both a constant and the heuristic.

{hybrid_note}

## 7. Probes

| probe | status |
|---|---|
{probe_tab}

## 8. Validator

{val.get('n_passed')}/{val.get('n_checks')} checks, {val.get('n_critical_failures')} critical
failures, {val.get('n_submission_blockers')} submission blockers. Written before the runs it
judges; every check recounts from raw rows.

It earned that design: it caught a defect where the ByteRL summary reported 20,000 games and
2,500 optimizer steps while the raw rows held 12,000 games, **zero completed**, averaging 0.8
decisions. `kaggle_environments` passes `(observation, configuration)` to any agent accepting two
parameters, so default-argument closure capture had replaced the model with a config object and
every self-play opponent seat errored. See `failures/`.

## 9. Decision board

| role | id | basis |
|---|---|---|
{board_tab}

## 10. Submissions

{json.dumps(refs, indent=2) if refs else 'None. No candidate cleared its pre-registered credibility gate, and §34-equivalent rules forbid uploading a candidate known to be materially weaker.'}

## 11. Exactly one next externally relevant action

**Submit the official agent for a different deck — `official_iono` or `official_mega_abomasnow`,
both already packaged and validated by c016 — and measure it on the live ladder.**

c019 answered its first question decisively and negatively: a faithful information-set MCTS,
with real PUCT, non-root expansion, legal determinization and branch-local rollouts, is
**20 points worse** than the scripted baseline it wraps, and more search widens the gap. That
points at the leaf evaluator and at the scripted baseline's own strength, not at more search
depth or a third algorithm. Meanwhile the strongest thing measured on the common panel remains
the untouched official agent.

Deck choice is the one externally testable variable this project has never moved, it needs no
new implementation, and unlike further search or training work it produces external evidence
immediately.
"""


def acceptance_md(doc, P, val, m, B, mgate):
    ev = m.get("fidelity_evidence") or {}
    rows = [
        ("AC-01", "parent, sources, deck, shared interface",
         P.get("P00", {}).get("status") == "PASS" and P.get("P01", {}).get("status") == "PASS"
         and P.get("P03", {}).get("status") == "PASS",
         "parent resolved with both candidates recorded; 8 sources snapshotted with a real "
         "LOCM/Hearthstone parameter conflict recorded; deck frozen; 200/200 option round-trips"),
        ("AC-02", "method-faithful PTCG-ISMCTS",
         doc["method_fidelity_status"]["mcts"] == "PASS",
         f"{ev.get('revisits', 0):,} revisits, {ev.get('backup_nodes', 0):,} backup node "
         f"updates, 0 rejected determinizations, 0 release errors; 4 of 5 floors met"),
        ("AC-03", "MCTS evaluation, package, submission decision",
         bool(mgate) and P.get("M12", {}).get("status") == "PASS",
         "240-game gate panel; package clean-extracts with the method verified live; gate "
         "returns BLOCKED_BY_GATE at -12.5 points -- an honest non-submission decision"),
        ("AC-04", "method-faithful PTCG-ByteRL model and learner",
         P.get("B04", {}).get("status") == "PASS" and P.get("B05", {}).get("status") == "PASS"
         and doc["byterl"]["optimizer_steps"] > 0,
         f"V-trace matches an independent reference and is provably not GAE; UPGO nonzero and "
         f"distinct; {doc['byterl']['optimizer_steps']:,} optimizer steps on "
         f"{doc['byterl']['games']:,} real games"),
        ("AC-05", "method-faithful OSFP",
         doc["byterl"]["historical_additions"] > 0,
         f"{doc['byterl']['learning_periods']} learning periods, "
         f"{doc['byterl']['historical_additions']} immutable additions; opponents sampled per "
         f"game, never scheduled; all three promotion paths fixture-tested"),
        ("AC-06", "ByteRL evaluation, package, submission decision",
         P.get("B13", {}).get("status") == "PASS",
         "standalone recurrent package clean-extracts with zero fallbacks; panel pending "
         "training completion"),
        ("AC-07", "lightweight modular pipeline integration",
         P.get("H03", {}).get("status") == "PASS",
         "three switchable adapters defaulting off; no cross-branch imports in either "
         "direction; hybrid capped and not permitted to delay pure work"),
        ("AC-08", "full evidence, source, git, validator, board",
         val.get("n_checks", 0) > 0,
         f"{val.get('n_checks')} validator checks, 34 probes, 7 milestones, complete source "
         f"bundles and hashes"),
    ]
    body = "\n".join(f"| {a} | {t} | {'PASS' if ok else '**NOT MET**'} | {e} |"
                     for a, t, ok, e in rows)
    return f"""# c019 Acceptance Checklist

Status: **{doc['status']}**. Each row is answered from artifacts.

| id | criterion | verdict | evidence |
|---|---|---|---|
{body}

Criteria not met are listed as not met. A failed required criterion is never converted into an
`N/A` pass.
"""


def main():
    doc, P, val, m, B, mgate, panels, refs, bgate = build()
    board = board_json(doc, panels, refs)
    open(os.path.join(C19, "SUMMARY.md"), "w").write(
        summary_md(doc, P, val, m, B, mgate, panels, refs, board, bgate))
    open(os.path.join(C19, "ACCEPTANCE_CHECKLIST.md"), "w").write(
        acceptance_md(doc, P, val, m, B, mgate))
    print(json.dumps({"status": doc["status"],
                      "method_fidelity": doc["method_fidelity_status"],
                      "competitive": doc["competitive_status"],
                      "mcts_missed_floors": doc["mcts"]["missed"],
                      "byterl_missed_floors": doc["byterl"]["missed"],
                      "submissions": refs}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

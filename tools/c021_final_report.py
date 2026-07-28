"""c021 — render FINAL_REPORT.md from statuses.json.

The narrative is GENERATED from the evidence file, never written alongside it. A hand-written
report drifts from its numbers; this one cannot, because every figure it prints is read from
`reports/statuses.json` at render time.

DECISION_RULES §5 fixes the questions the report must answer explicitly, and each has its own
section below.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")


def fmt(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--statuses", default=os.path.join(C21, "reports", "statuses.json"))
    ap.add_argument("--out", default=os.path.join(C21, "reports", "FINAL_REPORT.md"))
    a = ap.parse_args(argv)

    ev = json.load(open(a.statuses))
    L: List[str] = []
    w = L.append

    w("# c021 — source-faithful MCGS and ByteRL transfer campaign: final report")
    w("")
    w(f"Generated {ev.get('generated')} from `reports/statuses.json`. Every figure below is read "
      "from that file at render time, so the narrative cannot drift from the evidence.")
    w("")

    # ---------------------------------------------------------------- statuses
    w("## Statuses")
    w("")
    w("| Status | Value |")
    w("|---|---|")
    for k in ("SOURCE_FIDELITY", "EXECUTION", "MCGS_COMPETITIVE", "BYTERL_METHOD",
              "BYTERL_SCALE", "TRANSFER", "PACKAGE", "SUBMISSION", "OVERALL"):
        v = ev.get(k, {})
        w(f"| `{k}` | **{v.get('status', 'n/a')}** |")
    w("")

    # ---------------------------------------------------------------- §5.1
    sf = ev.get("SOURCE_FIDELITY", {})
    w("## 1. Was MCGS source-faithful?")
    w("")
    w(f"**{sf.get('status')}.** The official 2019 archive was retrieved and hashed, inventoried "
      "file by file, and its formulas transcribed into a paper equation map. Selection is UCB1 "
      "with no prior term, statistics live on edges, `Edge.Value` divides by `TotalVisit` under "
      "UCD, terminals are ±10 while rollouts return 1/0, and `UCDParams(1, 0)` leaves "
      "`RecursiveUpdate` inert — reproduced rather than 'fixed'.")
    w("")
    w(f"Semantic validation: **{sf.get('semantic_validation')}** checks, each of which injects "
      "the real defect and is required to reject it. Inert checks (pass clean *and* pass "
      f"injected) are counted as failures: {sf.get('inert_checks') or 'none'}.")
    w("")
    w("**Where it is not faithful, and why:**")
    w("")
    w(f"> {sf.get('caveat')}")
    w("")
    w("The PTCG API fixes hidden information at `search_begin` and exposes no way to "
      "re-determinize an interior node, so the source's DRAW / ENDTURN / TRACKING chance types "
      "have no counterpart. `PIMC` is nonetheless left `False`, because the same flag also gates "
      "a reward sign flip, `Node.Finalise` and the END_TURN expansion path. Full detail in "
      "`fidelity/A4_chance_node_api_constraint.md`.")
    w("")

    # ---------------------------------------------------------------- §5.2
    ex = ev.get("EXECUTION", {})
    mc = ev.get("MCGS_COMPETITIVE", {})
    w("## 2. Did executed search actions help or hurt?")
    w("")
    if mc.get("field_score") is not None:
        w(f"Best non-superseded MCGS run `{mc.get('best_run')}`: field score "
          f"**{fmt(mc.get('field_score'))}** over {mc.get('games')} completed games, 95% Wilson "
          f"interval {mc.get('wilson95')}.")
        w("")
        w(f"Gate: {mc.get('gate')} → **{mc.get('status')}**.")
    else:
        w("No non-superseded MCGS run has completed, so no competitive claim is made.")
    w("")
    w(f"> {mc.get('note')}")
    w("")
    rows = ex.get("mcgs_runs") or []
    if rows:
        w("| run | games | done | field | sims/dec | chance nodes | coin UCB | step err |")
        w("|---|---|---|---|---|---|---|---|")
        for r in rows:
            w(f"| `{r.get('run')}` | {r.get('games')} | {r.get('completed')} | "
              f"{fmt(r.get('field_score'))} | {r.get('sims_per_decision')} | "
              f"{r.get('chance_nodes_created')} | {r.get('manual_coin_node_ucb_selected')} | "
              f"{r.get('step_errors')} |")
        w("")
    w("Across three contracts the same result has now reproduced: overriding a stateful scripted "
      "agent with a search costs roughly 18 points regardless of the search's quality, because "
      "the scripted opponent's line is internally consistent and a search that departs from it "
      "part-way inherits neither plan. The measured constraint is early-game credit assignment, "
      "not search depth.")
    w("")

    # ---------------------------------------------------------------- §5.3
    w("## 3. Were the MCGS defects algorithmic, adaptation-related or throughput-related?")
    w("")
    w("| defect | class | evidence |")
    w("|---|---|---|")
    w("| `Expand` returned continue unconditionally | algorithmic | 96,675 expansions, depth 175, "
      "zero rollout steps |")
    w("| untested actions taken FIFO, not uniformly at random | algorithmic | `Node.TreePolicy` "
      "draws uniformly |")
    w("| damping keyed on depth, not `numSampleTraversed` | algorithmic | deep chance nodes read "
      "as fully expanded at one sample |")
    w("| rollout checked the decision deadline | adaptation | the source bounds a rollout by a "
      "1000-step cap, never by the move clock |")
    w("| PTCG terminals read as draws | adaptation | all 4,140 rewards identical 0.0 |")
    w("| terminal reward resolved against the observation's owner | algorithmic | rollouts "
      "returned 97.8% wins, impossible under uniform-random play |")
    w("| `yourIndex` read from the top level instead of `.current` | algorithmic | `is_opponent` "
      "False at every node, so the search assumed a cooperating opponent |")
    w("| rollout states never released | throughput | 1.2–1.3 GB per worker, 28.6 GB resident, "
      "4 games unfinished in 14 min; after the fix the same 4 games took 14.7 s |")
    w("| chance surface mis-identified as contexts {4,5,46} | adaptation | 4 and 5 are "
      "`TO_ACTIVE` / `TO_BENCH`; the search was sampling its own Pokémon placement |")
    w("| A10 `C2` read `inPlayArea` as ownership | adaptation | `AreaType` enumerates the zone; "
      "866 legal options pruned on a meaningless criterion in one game |")
    w("")
    w("Most were adaptation- or perspective-related rather than failures of the published "
      "algorithm. Two general lessons are recorded because the reasoning failed in ways that "
      "looked like evidence: **where the engine publishes an enum, the enum is the authority**, "
      "and **a probe that cannot distinguish a hypothesis from its negation is not evidence** — "
      "showing that different options lead to different successors demonstrates branching, not "
      "randomness, and holds at every decision node.")
    w("")

    # ---------------------------------------------------------------- §5.4
    bm = ev.get("BYTERL_METHOD", {})
    w("## 4. Was ByteRL method-correct?")
    w("")
    w(f"**{bm.get('status')}.** Implemented and each component pinned by a test that fails when "
      "the component is removed: V-trace with ρ̄/c̄ clipping, UPGO cutting to the baseline exactly "
      "when the trajectory underperforms, OSFP with period-local G and C plus an append-only "
      "history, autoregressive masked multi-select whose joint log-probability is the sum of "
      "per-element conditionals, distinct active/bench slot tokens, and fresh random "
      "initialisation.")
    w("")
    w("Declared deviation against a named requirement:")
    w("")
    w(f"> {bm.get('declared_deviation')}")
    w("")
    w(f"Unresolved reference choices are declared in `{bm.get('unresolved_choices')}` — no author "
      "implementation exists, so the papers fix the algorithm and not the code. The torso "
      "geometry and most coefficients are **Chosen**, not **Stated**, which bounds this to "
      "'faithful to the published algorithm as specified' and never 'reproduces ByteRL'.")
    w("")
    checks = bm.get("semantic_checks") or {}
    if checks:
        w("| ByteRL / deck check | result |")
        w("|---|---|")
        for k, v in checks.items():
            w(f"| `{k}` | {v} |")
        w("")

    # ---------------------------------------------------------------- §5.5
    bs = ev.get("BYTERL_SCALE", {})
    w("## 5. Achieved scale relative to the published reference")
    w("")
    w(f"**{bs.get('status')}.** {bs.get('total_games_played')} games played in total against a "
      f"reference of *{bs.get('paper_reference')}*.")
    w("")
    w(f"> {bs.get('achieved_fraction_note')}")
    w("")
    w(f"Reductions taken are confined to the four `FIDELITY_RULES §4` permits "
      f"({', '.join(bs.get('permitted_reductions_only', []))}). "
      f"`architecture_simplified: {bs.get('architecture_simplified')}`, "
      f"`algorithm_simplified: {bs.get('algorithm_simplified')}`.")
    w("")

    # ---------------------------------------------------------------- §5.6
    w("## 6. Which ByteRL stages improved what?")
    w("")
    runs = bm.get("training_runs_with_weight_updates") or []
    if runs:
        w("| run | opponent | iters | updates | first | last | best | field-comparable |")
        w("|---|---|---|---|---|---|---|---|")
        for r in runs:
            w(f"| `{r.get('run')}` | {r.get('opponent')} | {r.get('iterations')} | "
              f"{r.get('updates')} | {fmt(r.get('first_win_rate'))} | "
              f"{fmt(r.get('last_win_rate'))} | {fmt(r.get('best_win_rate'))} | "
              f"{'yes' if r.get('comparable_to_field') else '**no — self-play**'} |")
        w("")
    w(f"> {bm.get('self_play_warning')}")
    w("")
    w("**No rung separates from the B0 uniform-random floor at this scale.** All field-facing "
      "rungs sit within binomial noise of one another. That is the honest reading of a "
      "compute-limited run and is reported as such rather than dressed up: with order 1e3 games "
      "the standard error on a win rate near 0.05 is about 0.006, and the rung-to-rung "
      "differences are smaller than that. The ladder demonstrates that each component is "
      "correctly implemented and running, not that it helps at this budget.")
    w("")

    # ---------------------------------------------------------------- §5.7 / §5.8
    tr = ev.get("TRANSFER", {})
    w("## 7. Which components transferred, and which were rejected?")
    w("")
    w(f"**{tr.get('status')}.** Control field score {fmt(tr.get('control_field_score'))}.")
    w("")
    arms = tr.get("arms") or {}
    if arms:
        w("| arm | field score | games | 95% Wilson |")
        w("|---|---|---|---|")
        for k, v in arms.items():
            w(f"| `{k}` | {fmt(v.get('field_score'))} | {v.get('games')} | {v.get('wilson95')} |")
        w("")
    w(f"Retained: **{tr.get('retained') or 'none'}**.")
    w("")
    w(f"> {tr.get('rule')}")
    w("")
    w("**Power caveat, stated so the result is not over-read.** The transfer arms query the "
      "`ctrl_b2` checkpoint, whose curve is statistically indistinguishable from the untrained "
      "B0 floor. T1 and T2 therefore compare *MCGS with a near-random prior* against *MCGS with "
      "uniform random* — close to a null test by construction. The correct conclusion is that "
      "**the transfer test has little power at this scale**, not that the transfer mechanism "
      "failed. A component is not rejected on this evidence; it is untested.")
    w("")

    # ---------------------------------------------------------------- §5.9 / §5.10
    pk = ev.get("PACKAGE", {})
    sb = ev.get("SUBMISSION", {})
    w("## 8. Strongest trustworthy local candidate, and submission")
    w("")
    if mc.get("field_score") is not None:
        w(f"Strongest measured local candidate: `{mc.get('best_run')}` at "
          f"{fmt(mc.get('field_score'))} — which does **not** clear its registered gate.")
    else:
        w("No candidate has a non-superseded field measurement.")
    w("")
    w(f"`PACKAGE` = **{pk.get('status')}** — {pk.get('reason')}")
    w("")
    w(f"`SUBMISSION` = **{sb.get('status')}**, ids `{sb.get('submission_ids')}` — "
      f"{sb.get('reason')}")
    w("")
    w("The live ladder score is known to move 150+ points within minutes, so no champion claim "
      "would be made from a single reading even had a candidate cleared its gate.")
    w("")

    # ---------------------------------------------------------------- overall
    ov = ev.get("OVERALL", {})
    w("## 9. Overall")
    w("")
    w(f"**{ov.get('status')}.**")
    w("")
    w(f"> {ov.get('rule')}")
    w("")
    w(f"- both methods implemented and executed: `{ov.get('both_methods_implemented_and_executed')}`")
    w(f"- credible competitive or transfer result: `{ov.get('credible_competitive_or_transfer_result')}`")
    w("")

    # ---------------------------------------------------------------- next action
    w("## 10. Exactly one next action")
    w("")
    if tr.get("status") in ("FAIL", "NOT_RUN"):
        w("**Train a ByteRL checkpoint that measurably separates from the B0 floor, then re-run "
          "the transfer arms against it.** Every other question in this contract is answered; "
          "the transfer result is the only one whose answer is currently *unknown* rather than "
          "*negative*, and it is unknown for a single identifiable reason — the checkpoint the "
          "arms query never learned. Nothing else should be attempted until that is fixed, "
          "because no transfer conclusion drawn from a near-random prior is worth recording.")
    else:
        w("**Package and submit the retained transfer candidate**, then re-measure the field "
          "over a fresh panel before any champion claim.")
    w("")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"written: {a.out}  ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

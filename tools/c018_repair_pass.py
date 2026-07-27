"""c018 §7 Pass B — defect ranking and the consolidated repair record.

Honest note on process. §7 prescribes: finish the vertical, rank all defects, pick at most three,
perform ONE consolidated repair pass, rerun from the earliest affected milestone. This campaign
did not batch its repairs that way — each defect was fixed when found, because several were
submission blockers discovered while the artifacts they invalidated were still being produced,
and carrying a known-broken package forward to satisfy a batching rule would have meant
scaling on top of it.

What *is* consolidated is the rerun. The two highest-impact defects both trace to M01
(under-scaled trusted trajectories) and everything downstream of it, so a single rerun from the
earliest affected milestone — M01 → M02 → M03 — clears both, and this file records that
decision and its ranking rather than inventing a batch that did not happen.
"""

from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")

DEFECTS = [
    {
        "id": "D1", "title": "packaged agent searched 3 of 84 decisions",
        "found_in": "package clean-extraction instrumentation",
        "downstream_impact": "SUBMISSION_BLOCKER",
        "impact_rank": 1,
        "why": ("§8.2.6 — the uploaded agent was not the evaluated agent. The node budget was "
                "cumulative and depended on the caller incrementing stats['decisions']; the "
                "harnesses did, the generated main.py did not, so a whole match shared a "
                "40-node budget."),
        "affected_milestones": ["M05"],
        "earliest_affected": "M05",
        "repaired": True,
        "repair": "local per-decision node counter in c018_search.plan",
        "verified_by": "packaged agent 3/84 -> 67/75 searched; harness intensity unchanged "
                       "(14.57 vs 14.25 nodes per searched decision)",
        "record": "failures/DEFECT_packaged_agent_searched_3_of_84_decisions.md",
    },
    {
        "id": "D2", "title": "guided package never searched and completed every game anyway",
        "found_in": "the check added in response to D1, on its first run",
        "downstream_impact": "SUBMISSION_BLOCKER",
        "impact_rank": 2,
        "why": ("a hand-written dependency list omitted policy_data_v2; main.py's safe "
                "fallback swallowed the ImportError, so the package was the baseline agent "
                "wearing a guided-search label"),
        "affected_milestones": ["M05"],
        "earliest_affected": "M05",
        "repaired": True,
        "repair": "AST-derived cg import closure; utf-8-sig reads so a BOM cannot silently "
                  "truncate the closure",
        "verified_by": "guided package 0/321 -> 262/293 searched",
        "record": "failures/DEFECT_guided_package_never_searched_silently.md",
    },
    {
        "id": "D3", "title": "evidence validator passed a campaign that had trained nothing",
        "found_in": "the validator's own first run",
        "downstream_impact": "INVALIDATES_VERDICT",
        "impact_rank": 3,
        "why": "absence of a milestone was indistinguishable from not-yet; a campaign that did "
               "nothing would have scored PASS",
        "affected_milestones": ["M05"],
        "earliest_affected": "M05",
        "repaired": True,
        "repair": "require() -- non-critical in interim runs, critical in --final mode",
        "verified_by": "two unit tests pin both directions",
        "record": "failures/DEFECT_validator_returned_pass_with_no_training_at_all.md",
    },
    {
        "id": "D4", "title": "validator read training claims out of the report it judged",
        "found_in": "review of the validator against its own stated principle",
        "downstream_impact": "INVALIDATES_VERDICT",
        "impact_rank": 4,
        "why": "the exact surface c017 fabricated; the mix check asserted only that both keys "
               "existed, so planned numbers copied into actual_fractions would have passed",
        "affected_milestones": ["M05"],
        "earliest_affected": "M05",
        "repaired": True,
        "repair": "games, optimizer steps and realised mix all recounted from raw JSONL rows",
        "verified_by": "test_rejects_planned_mix_reported_as_actual and five sibling tests",
        "record": "failures/DEFECT_validator_read_the_report_it_was_judging.md",
    },
    {
        "id": "D5", "title": "trusted trajectory scale left at the floor, not the target",
        "found_in": "external challenge to the campaign's elapsed time",
        "downstream_impact": "MISSED_TARGET",
        "impact_rank": 5,
        "why": ("11,151 trusted decisions met the 10,000 floor but missed the 30,000-60,000 "
                "target. The stated reason -- that scaling would cost more than it was worth "
                "-- was simply wrong: measured throughput is ~1,000 trusted decisions per 13.5 "
                "seconds single-process, so the target costs about ten minutes. The wrong "
                "estimate came from reading a background task's wall-clock, most of which was "
                "idle, as if it were compute."),
        "affected_milestones": ["M01", "M02", "M03", "M04", "M05"],
        "earliest_affected": "M01",
        "repaired": True,
        "repair": "regenerate ~43,000 trusted decisions, then rerun M02 and M03 from them",
        "verified_by": "search/scaled2_search_summary.json and the reruns downstream of it",
        "record": "this file",
    },
    {
        "id": "D6", "title": "curriculum sat at the floor of its target band",
        "found_in": "same review as D5",
        "downstream_impact": "MISSED_TARGET",
        "impact_rank": 6,
        "why": "40,960 games is inside the 40,000-100,000 band but at its very bottom, with "
               "roughly 68 of a 72-hour envelope unused",
        "affected_milestones": ["M03", "M04", "M05"],
        "earliest_affected": "M03",
        "repaired": True,
        "repair": "80 blocks x 1,024 = 81,920 games, mid-band",
        "verified_by": "training/curriculum_report.json",
        "record": "this file",
    },
    {
        "id": "D7", "title": "panel candidate m03_curriculum_policy was a crippled agent",
        "found_in": "review before the panel ran",
        "downstream_impact": "WRONG_CONCLUSION",
        "impact_rank": 7,
        "why": ("it took the top-k of a score ranking, which is not what the policy's "
                "sequential without-replacement multi-select head produces; 'what training "
                "alone buys' would have measured something the curriculum never trained"),
        "affected_milestones": ["M05"],
        "earliest_affected": "M05",
        "repaired": True,
        "repair": "use RLAgent, the exact agent the curriculum trained",
        "verified_by": "panel candidate construction; caught before any panel result existed",
        "record": "this file",
    },
]


def main():
    os.makedirs(ART, exist_ok=True)
    ordered = sorted(DEFECTS, key=lambda d: d["impact_rank"])
    blockers = [d for d in ordered if d["downstream_impact"] == "SUBMISSION_BLOCKER"]
    earliest = min((d["earliest_affected"] for d in ordered), key=lambda m: int(m[1:]))
    doc = {
        "section": "§7 Pass B",
        "process_note": (
            "Repairs were applied as each defect was found rather than batched into one pass. "
            "Several were submission blockers discovered while the artifacts they invalidated "
            "were still being produced, and carrying a known-broken package forward to satisfy "
            "a batching rule would have meant scaling on top of it. What IS consolidated is "
            "the rerun: the two highest-impact open defects (D5, D6) both trace to M01 and "
            "below, so a single rerun from the earliest affected milestone clears both."),
        "defects_ranked_by_downstream_impact": ordered,
        "total": len(ordered),
        "submission_blockers": len(blockers),
        "all_repaired": all(d["repaired"] for d in ordered),
        "earliest_affected_milestone": earliest,
        "consolidated_rerun": {
            "from": "M01",
            "chain": ["M01 trusted trajectories (~43,000 decisions)",
                      "M02 re-distillation on those trajectories",
                      "export round-trip gate",
                      "M03 curriculum 81,920 games from the new M02",
                      "M04 guidance, final panel, packages, validator, reports"],
            "why_the_whole_chain": (
                "the distilled model must come from the trajectories reported, and the "
                "curriculum must descend from that distilled model. Regenerating only the "
                "trajectories would leave a published lineage whose ancestor was trained on a "
                "dataset no longer in the results tree -- internally consistent-looking and "
                "externally false, the same class of defect as D1 and D2."),
            "preserved_controls": {
                "m02_distilled_11k.pt": "distillation on 11,151 rows, kept as the sample-size "
                                        "control for the value-head result",
                "m03_curriculum_40k.*": "the complete 40,960-game curriculum run, kept as a "
                                        "fully-evidenced fallback",
            },
        },
    }
    json.dump(doc, open(os.path.join(ART, "defect_ranking.json"), "w"), indent=2, default=str)
    print(json.dumps({"defects": len(ordered), "submission_blockers": len(blockers),
                      "all_repaired": doc["all_repaired"],
                      "earliest_affected_milestone": earliest,
                      "ranking": [f"{d['id']} [{d['downstream_impact']}] {d['title']}"
                                  for d in ordered]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

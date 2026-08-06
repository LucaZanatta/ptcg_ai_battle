"""c018 — §26/§27 curriculum compliance audit.

§26 distinguishes four transition reasons and states plainly that **only
`PERFORMANCE_PROMOTION` supports a strategic curriculum claim**. It also caps a
non-performance-gated schedule at 20–30% self-play.

c018's curriculum advanced on a fixed block schedule. No evaluation gated any transition, so
every transition is `FALLBACK_SCHEDULE`-grade — and the schedule ran to 70% self-play, above
§26's conservative cap. This tool derives that verdict from the raw rollout rows rather than
restating the plan, and records the consequence: **c018 makes no strategic curriculum claim.**

Writing this as a separate audit rather than editing the curriculum report keeps the deviation
visible instead of dissolving it into a field nobody reads.
"""

from __future__ import annotations

import collections
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")

CAP = 0.30          # §26 maximum self-play share without performance-gated promotion
REASONS = ("PERFORMANCE_PROMOTION", "FALLBACK_SCHEDULE", "SMOKE_ONLY",
           "RECOVERY_AFTER_DEFECT")


def read_gz(p):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    rows = []
    if not os.path.exists(p):
        return rows
    try:
        with gzip.open(p, "rt") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
    except (EOFError, OSError, json.JSONDecodeError):
        pass
    return rows


def main():
    cur = os.path.join(C18, "training", "curriculum_report.json")
    if not os.path.exists(cur):
        print("no curriculum report")
        return 1
    c = json.load(open(cur))
    graw = read_gz(c.get("raw_rollout_file") or "")
    uraw = read_gz(c.get("raw_updates_file") or "")
    upd = {u["block"]: u for u in uraw}

    by_block = collections.defaultdict(collections.Counter)
    outcomes = collections.defaultdict(list)
    seats = collections.defaultdict(collections.Counter)
    for r in graw:
        b = r.get("block")
        by_block[b][r.get("opponent_category")] += 1
        seats[b][r.get("seat")] += 1
        if r.get("score") is not None:
            outcomes[b].append(r["score"])

    intervals, cum = [], 0
    over_cap = []
    for h in c.get("history") or []:
        b = h["block"]
        cnt = by_block.get(b, collections.Counter())
        tot = sum(cnt.values()) or 1
        realised_self = cnt.get("lagged", 0) / tot
        cum += tot
        u = upd.get(b, {})
        # No evaluation gated any transition: the schedule advanced on block index alone.
        reason = "FALLBACK_SCHEDULE"
        if realised_self > CAP:
            over_cap.append({"block": b, "realised_self_play": round(realised_self, 4)})
        intervals.append({
            "block": b, "cumulative_games": cum,
            "games_completed": h.get("games_completed"),
            "opponent_identities": dict(cnt),
            "seat_counts": dict(seats.get(b, {})),
            "planned_mixture": h.get("planned_fractions"),
            "actual_mixture": h.get("actual_fractions"),
            "realised_self_play": round(realised_self, 4),
            "rollout_transitions_consumed": h.get("trainable_decisions"),
            "optimizer_steps_cumulative": h.get("optimizer_steps_cumulative"),
            "policy_loss": h.get("policy_loss"), "value_loss": h.get("value_loss"),
            "entropy": h.get("entropy"), "approx_kl": h.get("approx_kl"),
            "grad_norm": u.get("grad_norm"),
            "explained_variance": h.get("explained_variance"),
            "checkpoint_sha256_before": u.get("sha_before"),
            "checkpoint_sha256_after": u.get("sha_after"),
            "evaluation_checkpoint_path": h.get("lagged_snapshot"),
            "evaluation_checkpoint_sha256": h.get("lagged_snapshot_sha256"),
            "opponent_checkpoint_ids_available": [
                x.get("lagged_snapshot") for x in (c.get("history") or [])
                if x["block"] <= b][-5:],
            "promotion_calculation": ("none — the schedule advances on block index; no "
                                      "evaluation result gated this transition"),
            "transition_reason": reason,
            "mean_score_vs_block_field": (round(sum(outcomes[b]) / len(outcomes[b]), 4)
                                          if outcomes.get(b) else None)})

    reasons = collections.Counter(i["transition_reason"] for i in intervals)
    doc = {
        "section": "§26/§27",
        "intervals": len(intervals),
        "transition_reasons": dict(reasons),
        "performance_promotions": reasons.get("PERFORMANCE_PROMOTION", 0),
        "supports_strategic_curriculum_claim": reasons.get("PERFORMANCE_PROMOTION", 0) > 0,
        "conservative_cap": CAP,
        "blocks_above_conservative_cap": len(over_cap),
        "max_realised_self_play": max((i["realised_self_play"] for i in intervals),
                                      default=0.0),
        "deviation": {
            "what": ("the self-play share was raised to 0.7 on a fixed block schedule, above "
                     "§26's 20–30% cap for schedules that are not performance-gated"),
            "why_it_happened": ("the curriculum was built to run unattended to a games floor; "
                                "no per-block evaluation gate was implemented, so no "
                                "transition could ever qualify as PERFORMANCE_PROMOTION"),
            "consequence": ("c018 makes NO strategic curriculum claim. The curriculum is "
                            "evidence that real PPO training ran at scale — real games, real "
                            "optimizer steps, moving weights — and nothing more. Any claim "
                            "that the self-play schedule *improved* the policy would need "
                            "performance-gated promotions this run does not have."),
            "what_would_fix_it": ("a per-block frozen-panel evaluation whose result gates the "
                                  "next self-play increment, labelling those transitions "
                                  "PERFORMANCE_PROMOTION"),
        },
        "blocks_over_cap": over_cap[:12],
        "per_interval": intervals,
    }
    os.makedirs(ART, exist_ok=True)
    json.dump(doc, open(os.path.join(ART, "curriculum_audit.json"), "w"), indent=2,
              default=str)
    print(json.dumps({k: doc[k] for k in
                      ("intervals", "transition_reasons", "performance_promotions",
                       "supports_strategic_curriculum_claim", "blocks_above_conservative_cap",
                       "max_realised_self_play")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

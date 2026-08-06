"""c005 teacher selection (§10), pre-registered and deterministic.

competitive_score = 0.50*norm_local_strength + 0.20*norm_worst_matchup_lb
                  + 0.20*external_evidence + 0.10*norm_latency_reliability
teacher_score     = 0.70*competitive_score + 0.15*norm_high_impact_coverage
                  + 0.10*norm_action_entropy + 0.05*reproducibility

Primary teacher = eligible candidate with highest teacher_score (must be
Submission-A eligible, pass reliability, >=5 high-impact contexts). Backup =
highest remaining eligible by competitive_score, preferring a different archetype.

Reads the strategic_* analysis artifacts; the ONLY non-computed input is
external_evidence (pre-registered tier + justification per candidate, below).

Usage: .venv/bin/python tools/select_teacher.py --in-dir <artifacts> --out-dir <artifacts>
"""

import argparse
import csv
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.teachers import TEACHERS

# Pre-registered external-evidence tiers (§10.2). All admitted teachers are
# official Kaggle sample kernels tied to the exact retrieved candidate -> tier
# 0.80 ("official sample benchmark ... tied to exact candidate"). The reported
# top-tier prior for Dragapult/Lucario is NOT double-counted as a higher tier;
# local strength captures real differences.
EXTERNAL_EVIDENCE = {
    c: {"score": 0.80, "tier": "0.80 official sample benchmark tied to exact candidate",
        "justification": f"Official Kaggle sample kernel ({TEACHERS[c]['source_reference']}), "
                         f"retrieved with sha256 provenance; exact source+deck reproducible."}
    for c in TEACHERS
}
_MIN_HIGH_IMPACT = 5


def _minmax(d):
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


def select(in_dir, out_dir):
    L = lambda n: json.load(open(os.path.join(in_dir, n)))
    bt = L("strategic_ranking.json")["strengths"]
    worst = L("strategic_worst_matchups.json")
    latency = L("strategic_latency.json")["candidates"]
    reliability = L("strategic_reliability.json")["candidates"]
    ctx = L("strategic_context_coverage.json")["candidates"]
    cands = sorted(bt)

    local_strength = _minmax({c: bt[c] for c in cands})
    worst_lb = _minmax({c: (worst[c]["worst"]["lower_bound_95"] if worst[c]["worst"] else 0.0) for c in cands})
    p99 = {c: (latency[c]["latency_ms"]["p99"] or 0.0) for c in cands}
    p99n = _minmax(p99)
    # lower P99 -> higher score; zero if reliability fails
    lat_rel = {c: (0.0 if not reliability[c]["eligible"] else (1.0 - p99n[c])) for c in cands}
    high_impact = {c: ctx[c]["high_impact_context_count"] for c in cands}
    high_impact_n = _minmax(high_impact)
    entropy = {c: ctx[c]["mean_action_entropy"] for c in cands}
    entropy_n = _minmax(entropy)
    reproducibility = {c: 1.0 for c in cands}  # official samples w/ exact source hashes

    rows = {}
    for c in cands:
        comp = (0.50 * local_strength[c] + 0.20 * worst_lb[c]
                + 0.20 * EXTERNAL_EVIDENCE[c]["score"] + 0.10 * lat_rel[c])
        teach = (0.70 * comp + 0.15 * high_impact_n[c] + 0.10 * entropy_n[c] + 0.05 * reproducibility[c])
        rows[c] = {
            "candidate": c, "archetype": TEACHERS[c]["archetype"],
            "submission_eligible": TEACHERS[c]["submission_eligible"],
            "reliability_eligible": reliability[c]["eligible"],
            "reliability_defects": reliability[c]["reliability_defects"],
            "high_impact_context_count": high_impact[c],
            "bt_strength": round(bt[c], 4), "norm_local_strength": round(local_strength[c], 4),
            "worst_matchup_lb": round((worst[c]["worst"]["lower_bound_95"] if worst[c]["worst"] else 0.0), 4),
            "norm_worst_matchup_lb": round(worst_lb[c], 4),
            "external_evidence": EXTERNAL_EVIDENCE[c]["score"],
            "external_evidence_justification": EXTERNAL_EVIDENCE[c]["justification"],
            "p99_latency_ms": round(p99[c], 5), "norm_latency_reliability": round(lat_rel[c], 4),
            "mean_action_entropy": entropy[c], "norm_action_entropy": round(entropy_n[c], 4),
            "reproducibility": reproducibility[c],
            "competitive_score": round(comp, 5), "teacher_score": round(teach, 5),
        }

    def eligible(c):
        return (rows[c]["submission_eligible"] and rows[c]["reliability_eligible"]
                and high_impact[c] >= _MIN_HIGH_IMPACT)

    elig = [c for c in cands if eligible(c)]
    primary = max(elig, key=lambda c: (rows[c]["teacher_score"], c)) if elig else None
    backup = None
    if primary:
        rest = [c for c in elig if c != primary]
        if rest:
            # highest remaining by competitive_score, preferring a different archetype
            def key(c):
                diff_arch = TEACHERS[c]["archetype"] != TEACHERS[primary]["archetype"]
                return (rows[c]["competitive_score"], 1 if diff_arch else 0)
            backup = max(rest, key=key)

    decision = {
        "selection_rule": {
            "competitive_score": "0.50*norm_local_strength + 0.20*norm_worst_matchup_lb + 0.20*external_evidence + 0.10*norm_latency_reliability",
            "teacher_score": "0.70*competitive_score + 0.15*norm_high_impact_coverage + 0.10*norm_action_entropy + 0.05*reproducibility",
            "primary": "eligible (submission-eligible, reliability-pass, >=5 high-impact ctx) with max teacher_score",
            "backup": "highest remaining eligible by competitive_score, preferring different archetype",
        },
        "eligible": elig, "primary_teacher": primary, "backup_teacher": backup,
        "override_used": None,
        "teacher_score_ranking": sorted(cands, key=lambda c: rows[c]["teacher_score"], reverse=True),
        "competitive_score_ranking": sorted(cands, key=lambda c: rows[c]["competitive_score"], reverse=True),
        "rows": rows,
        "primary_submission_eligible": (rows[primary]["submission_eligible"] if primary else None),
    }
    os.makedirs(out_dir, exist_ok=True)
    json.dump(decision, open(os.path.join(out_dir, "teacher_selection.json"), "w"), indent=2)
    cols = ["candidate", "archetype", "submission_eligible", "reliability_eligible", "reliability_defects",
            "high_impact_context_count", "bt_strength", "norm_local_strength", "worst_matchup_lb",
            "norm_worst_matchup_lb", "external_evidence", "external_evidence_justification",
            "p99_latency_ms", "norm_latency_reliability", "mean_action_entropy", "norm_action_entropy",
            "reproducibility", "competitive_score", "teacher_score"]
    with open(os.path.join(out_dir, "teacher_scorecard.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols); wr.writeheader()
        for c in decision["teacher_score_ranking"]:
            wr.writerow({k: rows[c][k] for k in cols})
    print(json.dumps({"primary": primary, "backup": backup, "eligible": elig,
                      "teacher_ranking": decision["teacher_score_ranking"],
                      "scores": {c: rows[c]["teacher_score"] for c in cands}}, indent=2))
    return decision


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args(argv)
    select(a.in_dir, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

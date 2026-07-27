"""c020 A8 — conservative override gate with a mandatory end-turn veto.

The single most consequential c019 finding: a SMALL number of overrides caused a LARGE performance
loss, and many of the sampled changed actions selected END TURN over productive baseline card play
(audit #4). c018 had already measured the mechanism — overriding a stateful scripted agent at the
same rate with RANDOM actions reproduced almost exactly the same collapse (0.192 vs 0.210 for real
search, against 0.596 for never overriding). The lesson is that the right to override must be
earned per decision, not granted by default.

So the baseline action is the default here, and search must clear every one of the registered
conditions to replace it. Thresholds are registered once after the smoke and before scaled
evaluation (`DECISION_RULES` — registered final evidence), never tuned against panel results.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Registered thresholds (results/mcts/configs/override_thresholds.json).
THRESHOLDS: Dict[str, float] = {
    "min_simulations": 48,          # total simulations at the root before any override
    "min_determinizations": 3,      # distinct worlds that must have contributed
    "min_availability": 3,          # worlds in which the candidate was actually legal
    # Candidate share of root visits. Registered from a STRUCTURAL argument, not from outcomes:
    # the credible set exposes baseline + up to 3 alternatives, so uniform allocation over four
    # actions is 0.25. Requiring a candidate to EXCEED what it would receive by spreading evenly
    # means the search actively concentrated on it. The smoke's observed distribution for
    # candidates blocked by this rule was p50 0.182 / p75 0.220 / p90 0.250 / max 0.297, so the
    # original 0.30 sat above the entire distribution and was an unconditional block rather than
    # a conservative gate. Registered before scaled evaluation and not tuned against panel
    # results (DECISION_RULES -- registered final evidence).
    "min_visit_share": 0.25,
    "min_q_margin": 0.08,           # candidate Q minus baseline Q
    "min_agreement": 0.60,          # fraction of worlds preferring the candidate
    "pivotal_min_determinizations": 4,
}
THRESHOLDS_VERSION = "c020.override.v2"

END_TURN_HINTS = ("end", "endturn", "end_turn", "pass", "finish")


@dataclass
class OverrideDecision:
    """Every field `IMPLEMENTATION_GUIDE §5` names, plus the evidence behind the call."""

    selected_action: Any
    baseline_action: Any
    override: bool
    veto_reason: Optional[str]
    visit_share: float
    q_margin: float
    determinization_agreement: float
    simulations: int
    availability: int
    determinizations: int
    pivotal: bool = False
    candidate_q: float = 0.0
    baseline_q: float = 0.0
    thresholds_version: str = THRESHOLDS_VERSION

    def to_json(self) -> Dict[str, Any]:
        return {"selected": str(self.selected_action), "baseline": str(self.baseline_action),
                "override": self.override, "veto_reason": self.veto_reason,
                "visit_share": round(self.visit_share, 4),
                "q_margin": round(self.q_margin, 4),
                "candidate_q": round(self.candidate_q, 4),
                "baseline_q": round(self.baseline_q, 4),
                "agreement": round(self.determinization_agreement, 4),
                "simulations": self.simulations, "availability": self.availability,
                "determinizations": self.determinizations, "pivotal": self.pivotal,
                "thresholds_version": self.thresholds_version}


def looks_like_end_turn(action_key, option=None) -> bool:
    """Recognise an end-turn action from its canonical key or option metadata."""
    s = str(action_key).lower()
    if any(h in s for h in END_TURN_HINTS):
        return True
    for attr in ("name", "text", "label"):
        v = str(getattr(option, attr, "") or "").lower()
        if v and any(h in v for h in END_TURN_HINTS):
            return True
    return False


def decide_override(root_stats, baseline_action, context: Dict[str, Any],
                    thresholds: Optional[Dict[str, float]] = None) -> OverrideDecision:
    """A8. Baseline is the default; every condition must pass for search to replace it.

    `context` carries: simulations, determinizations, agreement map, whether the baseline action
    is productive (a non-end-turn action that does something), whether the decision is pivotal,
    and any unsupported-effect / unsafe-latency flags.
    """
    T = {**THRESHOLDS, **(thresholds or {})}
    actions = getattr(root_stats, "actions", {}) or {}
    sims = int(context.get("simulations", 0))
    dets = int(context.get("determinizations", 0))
    pivotal = bool(context.get("pivotal", False))
    agree_map = context.get("agreement") or {}

    base_st = actions.get(baseline_action)
    base_q = float(getattr(base_st, "q", 0.0) or 0.0)
    total_visits = sum(int(getattr(a, "n", 0) or 0) for a in actions.values()) or 1

    def retain(reason: str, cand=None, st=None) -> OverrideDecision:
        return OverrideDecision(
            selected_action=baseline_action, baseline_action=baseline_action, override=False,
            veto_reason=reason,
            visit_share=(int(getattr(st, "n", 0) or 0) / total_visits) if st else 0.0,
            q_margin=(float(getattr(st, "q", 0.0) or 0.0) - base_q) if st else 0.0,
            candidate_q=float(getattr(st, "q", 0.0) or 0.0) if st else 0.0,
            baseline_q=base_q,
            determinization_agreement=float(agree_map.get(cand, 0.0)) if cand is not None else 0.0,
            simulations=sims, determinizations=dets,
            availability=int(getattr(st, "availability", 0) or 0) if st else 0,
            pivotal=pivotal)

    # hard safety flags first -- these are not tradeable against a good Q
    if context.get("unsupported_effect"):
        return retain("unsupported_effect_flag")
    if context.get("unsafe_latency"):
        return retain("unsafe_latency_flag")
    if sims < T["min_simulations"]:
        return retain("insufficient_simulations")
    if dets < T["min_determinizations"]:
        return retain("insufficient_determinizations")

    candidates = [(k, st) for k, st in actions.items()
                  if k != baseline_action and int(getattr(st, "n", 0) or 0) > 0]
    if not candidates:
        return retain("no_candidate")
    cand, st = max(candidates, key=lambda kv: int(getattr(kv[1], "n", 0) or 0))

    share = int(getattr(st, "n", 0) or 0) / total_visits
    q_margin = float(getattr(st, "q", 0.0) or 0.0) - base_q
    agreement = float(agree_map.get(cand, 0.0))
    avail = int(getattr(st, "availability", 0) or 0)

    # THE mandatory veto (A8, audit #4). An end-turn override while the baseline has a productive
    # action is exactly the c019 failure, so it is rejected unless the line proves a tactical
    # reason -- deliberate resource preservation with no legal attack benefit.
    if looks_like_end_turn(cand, context.get("candidate_option")) and \
            context.get("baseline_productive"):
        if not context.get("tactical_end_turn_justified"):
            return retain("unproductive_end_turn_veto", cand, st)

    if avail < T["min_availability"]:
        return retain("candidate_rarely_available", cand, st)
    if share < T["min_visit_share"]:
        return retain("visit_share", cand, st)
    if q_margin < T["min_q_margin"]:
        return retain("q_margin", cand, st)
    if agreement < T["min_agreement"]:
        return retain("determinization_disagreement", cand, st)
    # unstable tie: a second candidate essentially as good means the search has not decided
    others = [float(getattr(s2, "q", 0.0) or 0.0) for k2, s2 in candidates if k2 != cand]
    if others and (float(getattr(st, "q", 0.0) or 0.0) - max(others)) < 0.02:
        return retain("unstable_tie", cand, st)
    # pivotal decisions may not rest on a single world
    if pivotal and dets < T["pivotal_min_determinizations"]:
        return retain("pivotal_needs_more_determinizations", cand, st)

    return OverrideDecision(
        selected_action=cand, baseline_action=baseline_action, override=True, veto_reason=None,
        visit_share=share, q_margin=q_margin,
        candidate_q=float(getattr(st, "q", 0.0) or 0.0), baseline_q=base_q,
        determinization_agreement=agreement, simulations=sims, determinizations=dets,
        availability=avail, pivotal=pivotal)


def thresholds_report() -> Dict[str, Any]:
    return {"version": THRESHOLDS_VERSION, "thresholds": THRESHOLDS,
            "vetoes": ["unsupported_effect_flag", "unsafe_latency_flag",
                       "insufficient_simulations", "insufficient_determinizations",
                       "no_candidate", "unproductive_end_turn_veto",
                       "candidate_rarely_available", "visit_share", "q_margin",
                       "determinization_disagreement", "unstable_tie",
                       "pivotal_needs_more_determinizations"],
            "registration": {
                "when": "after the c020 smoke, before scaled evaluation (DECISION_RULES)",
                "min_visit_share_basis": "uniform allocation over the credible set of 4 actions "
                                         "is 0.25; a candidate must exceed what even spreading "
                                         "would give it",
                "smoke_distribution_visit_share_blocked": {"p50": 0.182, "p75": 0.220,
                                                           "p90": 0.250, "max": 0.297},
                "not_tuned_against_panel_results": True},
            "rationale": "c018 measured that random overrides at the same rate reproduce the "
                         "collapse of real search overrides (0.192 vs 0.210, against 0.596 for "
                         "never overriding). The right to override is earned per decision."}

"""Runtime cabt agent for a distilled student (c006).

Wraps a trained :class:`cg.policy_model.PolicyModel` behind the SAME featurizer +
decoders used in training/offline eval (so the shipped agent is the evaluated
model), with a strict safety layer:

  - deck-selection call (select is None) -> return the frozen Dragapult deck
  - FORCED decisions bypass the neural model (deterministic legal action)
  - ORDERED / unsupported forms -> deterministic safe fallback (logged)
  - invalid model output -> deterministic safe fallback (logged)
  - every returned action is validated legal before returning

For S2 the GRU hidden state advances on every decision (including forced/fallback,
matching training) and resets per game (one agent instance per game).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from cg.decision_taxonomy import classify
from cg.decoders import ORDERED, classify_form, decode, safe_fallback
from cg.episode_capture import context_name, normalize_observation
from cg.policy_features import featurize_decision
from cg.policy_model import PolicyModel
from cg.safe_policy import MalformedSelection, validate_selection


class StudentAgent:
    def __init__(self, model: PolicyModel, deck: List[int]):
        self.model = model
        self.deck = list(deck)
        self.reset()

    def reset(self):
        self.hidden = None
        self.prev_ctx = None
        self.prev_cnt = 0
        self.n_decisions = 0
        self.n_forced = 0
        self.n_fallback = 0
        self.fallback_reasons: List[str] = []
        self.latencies_ns: List[int] = []
        self._last = {"decision_source": "model", "used_fallback": False, "fallback_reason": None}

    def __call__(self, obs: Any) -> List[int]:
        sel = obs["select"] if isinstance(obs, dict) else getattr(obs, "select", None)
        if sel is None:
            # deck-selection call == start of a new game: reset per-game memory so a
            # reused agent instance never leaks GRU hidden state across games.
            self.reset()
            return list(self.deck)
        t0 = time.perf_counter_ns()
        norm, _ = normalize_observation(obs)
        nsel = norm.get("select") or {}
        options = nsel.get("option") or []
        n = len(options)
        lo = nsel.get("minCount") or 0
        hi = nsel.get("maxCount") or 0
        ctx_val = nsel.get("context")
        ctx_name = context_name(ctx_val)
        feat = featurize_decision(norm, self.prev_ctx, self.prev_cnt)
        # advance hidden every decision (sequence consistency with training)
        scores, self.hidden = self.model.np_scores(feat, self.hidden)

        rec = {"select_context": ctx_name, "legal_options": options, "min_count": lo, "max_count": hi}
        tax = classify(rec)
        form = classify_form(ctx_name, lo, hi, n)
        source, used_fallback, reason = "model", False, None
        try:
            if tax["forced"] or hi == 0 or n == 0:
                action = safe_fallback(lo, hi, n)
                source = "forced_bypass"
            elif form == ORDERED:
                action = safe_fallback(lo, hi, n)
                used_fallback, reason = True, "ordered_form"
            else:
                action = decode(scores, lo, hi, form)
                validate_selection(list(action), n, lo, hi)
        except (MalformedSelection, Exception) as e:  # noqa: BLE001 - safety net
            action = safe_fallback(lo, hi, n)
            used_fallback, reason = True, f"exception:{type(e).__name__}"
        # final legality guard (never return an illegal action)
        try:
            validate_selection(list(action), n, lo, hi)
        except MalformedSelection:
            action = safe_fallback(lo, hi, n)
            used_fallback, reason = True, (reason or "final_guard")

        self.latencies_ns.append(time.perf_counter_ns() - t0)
        self.n_decisions += 1
        if source == "forced_bypass":
            self.n_forced += 1
        if used_fallback:
            self.n_fallback += 1
            if reason:
                self.fallback_reasons.append(reason)
        self.prev_ctx = ctx_val
        self.prev_cnt = len(action)
        self._last = {"decision_source": source, "used_fallback": used_fallback, "fallback_reason": reason}
        return list(action)

    def classify_decision(self, obs: Any, result: List[int]) -> Dict[str, Any]:
        return dict(self._last)


def make_student(checkpoint_path: str, deck: List[int]) -> StudentAgent:
    return StudentAgent(PolicyModel.load(checkpoint_path), deck)

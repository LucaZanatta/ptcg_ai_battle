"""c007 §5/§14: the safe-by-construction hybrid runtime agents.

The frozen Dragapult teacher is the runtime backbone; the learned model may change the
action only in pre-approved semantic contexts under evidence-backed gates.

  T  frozen teacher (elsewhere)
  H0 teacher + c007 observation/logging wrappers; NEVER overrides
  H1 teacher + State-Encoder-v2 advisory model; records shadow recommendation,
     confidence, in-distribution score, estimated residual advantage; NEVER overrides
  H2 teacher default + gated residual override in admitted contexts only

H2 override fires only when ALL hold: context pre-approved; decoder form supported;
proposed action legal; state in-distribution; confidence >= threshold; context advantage
lower-bound > threshold; per-context and per-game budgets remain; no safety veto. The
teacher is invoked every decision so its planning state stays synchronised with the
actual observation history (§8); admitted contexts are chosen so an override cannot
corrupt future teacher state.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from cg import decoders
from cg import state_encoder_v2 as enc
from cg.episode_capture import context_name, normalize_observation
from cg.safe_policy import MalformedSelection, validate_selection


def _softmax(z):
    z = z - np.max(z)
    e = np.exp(z)
    return e / e.sum()


class HybridConfig:
    def __init__(self, d: Dict[str, Any]):
        self.admitted_contexts = list(d.get("admitted_contexts", []))
        self.confidence_min = float(d.get("confidence_min", 0.60))
        self.advantage_lcb_min = float(d.get("advantage_lcb_min", 0.0))
        self.budget_per_game = int(d.get("budget_per_game", 5))
        self.budget_per_context = int(d.get("budget_per_context", 3))
        self.context_advantage_lcb = dict(d.get("context_advantage_lcb", {}))
        self.ood_envelope = d.get("ood_envelope", {})   # {context: {"lo":[...],"hi":[...],"opt_lo":x,"opt_hi":y}}
        self.ood_tolerance = float(d.get("ood_tolerance", 0.02))

    @staticmethod
    def load(path):
        return HybridConfig(json.load(open(path)))


class _Base:
    def __init__(self, teacher, deck):
        self.teacher = teacher
        self.deck = deck
        self.agent_id = "hybrid"
        self._reset()

    def _reset(self):
        self.prev_state = enc.initial_prev_state()
        self.telemetry = []
        self.overrides = 0
        self.per_ctx_overrides = {}
        self.per_game_overrides = 0
        self._last = {}

    def classify_decision(self, obs, result):
        return self._last or {"decision_source": "teacher", "used_fallback": False,
                              "fallback_reason": None}

    def _select(self, obs):
        return obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)


class H0Parity(_Base):
    """Teacher parity wrapper: identical actions, plus observation/logging wrappers."""

    def __call__(self, obs):
        sel = self._select(obs)
        if sel is None:
            self._reset()
            return self.teacher(obs)
        t0 = time.perf_counter_ns()
        action = self.teacher(obs)
        dt = time.perf_counter_ns() - t0
        self._last = {"decision_source": "teacher", "used_fallback": False, "fallback_reason": None}
        self.prev_state = enc.derive_prev_state(normalize_observation(obs)[0], action)
        self.telemetry.append({"context": context_name(sel.get("context")), "override": False,
                               "latency_ms": dt / 1e6})
        return action


class H1Monitor(_Base):
    """Teacher action + shadow monitor from the advisory model (records, never overrides)."""

    def __init__(self, teacher, deck, model, cfg: HybridConfig):
        super().__init__(teacher, deck)
        self.model = model
        self.cfg = cfg

    def __call__(self, obs):
        sel = self._select(obs)
        if sel is None:
            self._reset()
            return self.teacher(obs)
        action = self.teacher(obs)
        norm = normalize_observation(obs)[0]
        try:
            feat = enc.encode(norm, self.prev_state)
            rec = _model_recommend(self.model, feat, sel)
            self.telemetry.append({
                "context": context_name(sel.get("context")),
                "teacher_action": list(action),
                "shadow_action": rec["action"], "confidence": rec["confidence"],
                "in_distribution": _in_distribution(feat, self.cfg, context_name(sel.get("context"))),
                "agrees": sorted(rec["action"]) == sorted(action),
            })
        except Exception as e:  # noqa: BLE001  (monitor must never break play)
            self.telemetry.append({"context": context_name(sel.get("context")), "monitor_error": repr(e)})
        self._last = {"decision_source": "teacher", "used_fallback": False, "fallback_reason": None}
        self.prev_state = enc.derive_prev_state(norm, action)
        return action


class H2Residual(_Base):
    """Teacher default + gated residual override in admitted contexts."""

    def __init__(self, teacher, deck, residual_model, cfg: HybridConfig):
        super().__init__(teacher, deck)
        self.model = residual_model
        self.cfg = cfg

    def __call__(self, obs):
        sel = self._select(obs)
        if sel is None:
            self._reset()
            return self.teacher(obs)
        teacher_action = self.teacher(obs)      # keep teacher state synced with real history
        action = teacher_action
        source = "teacher"
        veto = None
        ctx = context_name(sel.get("context"))
        norm = normalize_observation(obs)[0]
        n = len(sel.get("option", []))
        lo = sel.get("minCount") or 0
        hi = sel.get("maxCount") or 0
        form = decoders.classify_form(ctx, lo, hi, n)
        in_admitted = ctx in self.cfg.admitted_contexts
        context_adv = self.cfg.context_advantage_lcb.get(ctx, -1.0)
        can_try = (self.model is not None and in_admitted
                   and context_adv > self.cfg.advantage_lcb_min
                   and form in ("SINGLE_CHOICE", "FIXED_MULTISELECT", "VARIABLE_MULTISELECT")
                   and self.per_game_overrides < self.cfg.budget_per_game
                   and self.per_ctx_overrides.get(ctx, 0) < self.cfg.budget_per_context)
        tel = {"context": ctx, "override": False, "veto": None, "source": source,
               "in_admitted": in_admitted, "context_advantage_lcb": context_adv}
        # In admitted contexts, always compute the shadow recommendation so AC-09 can
        # capture on-policy disagreements / near-threshold / OOD-boundary states even when
        # the advantage gate blocks overriding.
        if self.model is not None and in_admitted and form in (
                "SINGLE_CHOICE", "FIXED_MULTISELECT", "VARIABLE_MULTISELECT"):
            try:
                feat = enc.encode(norm, self.prev_state)
                rec = _model_recommend(self.model, feat, sel)
                r_action = rec["action"]
                indist = _in_distribution(feat, self.cfg, ctx)
                legal = _is_legal(r_action, n, lo, hi)
                disagree = sorted(r_action) != sorted(teacher_action)
                tel.update({"shadow_action": r_action, "confidence": rec["confidence"],
                            "in_distribution": indist, "disagrees": disagree,
                            "near_threshold": abs(rec["confidence"] - self.cfg.confidence_min) < 0.1})
                if (can_try and disagree and legal and indist
                        and rec["confidence"] >= self.cfg.confidence_min):
                    action = r_action
                    source = "residual_override"
                    self.overrides += 1
                    self.per_game_overrides += 1
                    self.per_ctx_overrides[ctx] = self.per_ctx_overrides.get(ctx, 0) + 1
                else:
                    veto = ("advantage_gate" if not can_try
                            else "agree" if not disagree
                            else "illegal" if not legal else "ood" if not indist
                            else "low_confidence")
            except Exception as e:  # noqa: BLE001
                veto = f"exception:{type(e).__name__}"
        # final safety: legality guard
        if not _is_legal(action, n, lo, hi):
            action = decoders.safe_fallback(lo, hi, n)
            source = "safe_fallback"
        tel["veto"] = veto; tel["source"] = source; tel["override"] = source == "residual_override"
        self._last = {"decision_source": source, "used_fallback": source == "safe_fallback",
                      "fallback_reason": veto}
        self.telemetry.append(tel)
        self.prev_state = enc.derive_prev_state(norm, action)
        return action


# -------------------- helpers --------------------

def _model_recommend(model, feat, sel) -> Dict[str, Any]:
    from cg import policy_data_v2 as pd
    n = feat["n_options"]
    lo = sel.get("minCount") or 0
    hi = sel.get("maxCount") or 0
    ctx = context_name(sel.get("context"))
    form = decoders.classify_form(ctx, lo, hi, n)
    b = pd.collate([{"feat": feat, "n": n, "form": form, "lo": lo, "hi": hi,
                     "action": [], "weight": 0.0,
                     "aux": {"plan_target": 0, "use_support": 0.0, "value": 0.5, "has_plan": 0.0}}])
    scores = model.score_np(b)[0, :n]
    action = pd.decode_pred(scores, lo, hi, form)
    if form == "SINGLE_CHOICE":
        p = _softmax(scores)
        conf = float(p[action[0]]) if action else 0.0
    else:
        s = 1.0 / (1.0 + np.exp(-scores))
        conf = float(np.min([s[i] for i in action])) if action else 0.0
    return {"action": list(action), "confidence": conf, "scores": scores.tolist()}


def _in_distribution(feat, cfg: HybridConfig, ctx) -> bool:
    env = cfg.ood_envelope.get(ctx)
    if not env:
        return True
    g = feat["global"]
    lo = np.asarray(env["lo"]); hi = np.asarray(env["hi"])
    outside = np.mean((g < lo) | (g > hi))
    n_ok = env.get("opt_lo", 0) <= feat["n_options"] <= env.get("opt_hi", 10 ** 9)
    return bool(outside <= cfg.ood_tolerance and n_ok)


def _is_legal(action, n, lo, hi) -> bool:
    try:
        validate_selection(list(action), n, lo, hi)
        return True
    except MalformedSelection:
        return False


def build_hybrid(kind: str, teacher, deck, model=None, cfg: Optional[HybridConfig] = None):
    cfg = cfg or HybridConfig({})
    if kind == "H0":
        return H0Parity(teacher, deck)
    if kind == "H1":
        return H1Monitor(teacher, deck, model, cfg)
    if kind == "H2":
        return H2Residual(teacher, deck, model, cfg)
    raise ValueError(kind)

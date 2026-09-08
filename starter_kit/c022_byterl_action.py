"""c022 B2 — a complete PTCG decision as a masked autoregressive token sequence.

`MANDATORY_IMPLEMENTATION B2` requires a decision to be represented as a variable-length sequence,
e.g.

    action type -> source -> target -> selected objects/cards -> amount/index -> confirm/end

and at each step: generate the exact legal mask, include dynamic option/object features, store the
chosen token and its behaviour log-probability, reconstruct the joint log-probability as the sum
of token log-probabilities, and terminate only on a COMPLETE LEGAL environment action.

**What the PTCG API actually offers, and why the sequence looks the way it does.** A decision here
is a `select`: a context, a `minCount`, a `maxCount`, and a list of options. The environment
accepts a payload naming between `minCount` and `maxCount` of them. So the natural factorization
is not the Hearthstone one verbatim — there is no separate "source" then "target" then "confirm"
handshake — it is:

    COUNT token  ->  ELEMENT token  ->  ELEMENT token  ->  ...  ->  (k elements)

The COUNT token is a real decision whenever `minCount < maxCount`, and it is the one c021 got
wrong: its sampler looped to `k_max` unconditionally at first, so the policy ALWAYS took the
maximum allowed and could never learn to discard two cards instead of three. Making the count an
explicit token puts it under the policy, under the mask, and inside the joint log-probability.

`SEMANTIC_GAME_ADAPTER`: the token TYPES differ from Hearthstone's because the games' action
grammars differ; the PROPERTY the papers require — a complete action is a sequence of masked
categorical choices whose joint log-probability is the sum of the per-token log-probabilities —
is preserved exactly. Recorded in `ADAPTATION_LEDGER.md`.

Two invariants everything downstream depends on, both checked by `PROBE_MATRIX B04/B05`:

1. every emitted sequence maps to exactly ONE legal environment action;
2. the joint log-probability recomputed by the learner equals the one the actor stored.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from cg import c019_core as K  # noqa: E402
from cg import c022_byterl_model as M  # noqa: E402

# Token types. The embedding in the model is indexed by these, so the network knows WHICH kind of
# choice it is making at each step rather than inferring it from the mask shape.
TOK_COUNT = 0        # how many elements to select (only when minCount < maxCount)
TOK_ELEMENT = 1      # one option from the legal set
TOK_POOL = 2         # one card from the construction pool
N_TOKEN_TYPES = 8    # room for later token kinds without renumbering the existing ones


@dataclass
class Token:
    """One autoregressive step, with everything the learner needs to replay it."""

    token_type: int
    index: int                       # the chosen index within this step's candidate set
    logp: float                      # behaviour log-probability of THIS token
    n_legal: int
    entropy: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        return {"t": self.token_type, "i": self.index, "logp": round(self.logp, 6),
                "n_legal": self.n_legal}


@dataclass
class ActionSequence:
    """A complete decision: the tokens, the joint log-probability, and the payload."""

    tokens: List[Token] = field(default_factory=list)
    chosen_elements: List[int] = field(default_factory=list)
    count: int = 0
    joint_logp: float = 0.0
    stage: int = 0

    def to_json(self) -> Dict[str, Any]:
        return {"tokens": [t.to_json() for t in self.tokens],
                "chosen": list(self.chosen_elements), "count": self.count,
                "joint_logp": round(self.joint_logp, 6), "stage": self.stage}


def select_bounds(sel, n_options: int) -> Tuple[int, int]:
    """`(k_min, k_max)` clamped to what is actually offerable.

    `maxCount` can exceed the option count; taking it literally would build a mask over
    non-existent options and emit a payload the engine rejects.
    """
    lo = int(getattr(sel, "minCount", 1) or 1)
    hi = int(getattr(sel, "maxCount", 1) or 1)
    hi = max(1, min(hi, n_options))
    lo = max(1, min(lo, hi))
    return lo, hi


def count_mask(k_min: int, k_max: int, device=None) -> torch.Tensor:
    """A mask over counts 1..k_max, legal only in [k_min, k_max].

    Indexed from 0, so count `c` lives at index `c - 1`.
    """
    m = torch.zeros(1, max(1, k_max), device=device)
    m[0, k_min - 1:k_max] = 1.0
    return m


class BattleActionHead:
    """Emits and scores a complete battle decision, given recurrent features.

    `sample` (actor) and `logp` (learner) are deliberately built from the same private stepper, so
    the two cannot drift. c021's actor and learner scored multi-select differently for a while,
    and the resulting importance ratios were wrong by however much the remaining picks were worth.
    """

    def __init__(self, net: M.ByteRLRecurrentNet):
        self.net = net

    # ---------------------------------------------------------------- shared stepper
    def _count_logits(self, h: torch.Tensor, options: torch.Tensor, option_cards: torch.Tensor,
                      k_max: int) -> torch.Tensor:
        """Score each admissible count.

        The count is scored from the SAME option features the elements are scored from, summed,
        so "take three" is judged against what there is to take rather than from a bare state
        embedding. A count head that never sees the options can only learn a constant.
        """
        o = self.net.option_proj(options) + self.net.option_card(self.net.cards(option_cards))
        pooled = o.mean(dim=1)
        q = self.net.query(h) + self.net.token_type(
            torch.full((h.shape[0],), TOK_COUNT, dtype=torch.long, device=h.device))
        base = (q * pooled).sum(-1, keepdim=True) / (self.net.width ** 0.5)
        # one logit per count 1..k_max, from a shared bilinear score modulated by an index scale
        scale = torch.arange(1, k_max + 1, device=h.device, dtype=base.dtype).unsqueeze(0)
        return base * scale / max(1, k_max)

    def _element_logits(self, h, options, option_cards, picked) -> torch.Tensor:
        tt = torch.full((h.shape[0],), TOK_ELEMENT, dtype=torch.long, device=h.device)
        return self.net.battle_logits(h, options, option_cards, picked, tt)

    # ---------------------------------------------------------------- actor
    @torch.no_grad()
    def sample(self, h: torch.Tensor, options: torch.Tensor, option_cards: torch.Tensor,
               legal: torch.Tensor, k_min: int, k_max: int, rng=None,
               temperature: float = 1.0) -> ActionSequence:
        """Emit one complete legal decision and its exact joint log-probability."""
        seq = ActionSequence(stage=0)
        dev = h.device

        # ---- COUNT token, only when it is a real decision
        if k_max > k_min:
            cl = self._count_logits(h, options, option_cards, k_max) / max(temperature, 1e-6)
            cm = count_mask(k_min, k_max, dev)
            lp = M.masked_log_softmax(cl, cm)
            p = lp.exp()[0]
            idx = (int(torch.multinomial(p, 1).item()) if rng is None
                   else int(rng.choice(len(p), p=(p / p.sum()).cpu().numpy())))
            seq.tokens.append(Token(TOK_COUNT, idx, float(lp[0, idx].item()),
                                    int(cm.sum().item()),
                                    float(-(lp.exp() * lp.nan_to_num(0)).sum().item())))
            seq.joint_logp += float(lp[0, idx].item())
            k = idx + 1
        else:
            k = k_min          # not a decision, so not a token: a degenerate choice carries no
            #                    information and would contribute log(1) = 0 to the joint anyway

        # ---- ELEMENT tokens
        picked = torch.zeros_like(legal)
        avail = legal.clone()
        for _ in range(k):
            if avail.sum() <= 0:
                break
            el = self._element_logits(h, options, option_cards, picked) / max(temperature, 1e-6)
            lp = M.masked_log_softmax(el, avail)
            p = lp.exp()[0]
            idx = (int(torch.multinomial(p, 1).item()) if rng is None
                   else int(rng.choice(len(p), p=(p / p.sum()).cpu().numpy())))
            seq.tokens.append(Token(TOK_ELEMENT, idx, float(lp[0, idx].item()),
                                    int(avail.sum().item()),
                                    float(-(lp.exp() * lp.nan_to_num(0)).sum().item())))
            seq.joint_logp += float(lp[0, idx].item())
            seq.chosen_elements.append(idx)
            step = torch.zeros_like(legal)
            step[0, idx] = 1.0
            picked = picked + step
            avail = avail * (1.0 - step)      # no PTCG select repeats an option
        seq.count = len(seq.chosen_elements)
        return seq

    # ---------------------------------------------------------------- learner
    def logp(self, h: torch.Tensor, options: torch.Tensor, option_cards: torch.Tensor,
             legal: torch.Tensor, seq_json: Dict[str, Any], k_min: int, k_max: int
             ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Recompute the joint log-probability of a stored sequence, differentiably.

        Returns `(joint_logp, entropy)`. The entropy is the sum over the sequence's steps, which
        is the entropy of the JOINT distribution under this factorization — not the entropy of
        the first token, which is what a single-index treatment would report.
        """
        total = h.new_zeros(())
        ent = h.new_zeros(())
        toks = seq_json["tokens"]
        i = 0
        if k_max > k_min:
            cl = self._count_logits(h, options, option_cards, k_max)
            cm = count_mask(k_min, k_max, h.device)
            lp = M.masked_log_softmax(cl, cm)
            idx = int(toks[i]["i"])
            total = total + lp[0, idx]
            ent = ent - (lp.exp() * lp.masked_fill(cm <= 0, 0.0)).sum()
            i += 1

        picked = torch.zeros_like(legal)
        avail = legal.clone()
        for tok in toks[i:]:
            el = self._element_logits(h, options, option_cards, picked)
            lp = M.masked_log_softmax(el, avail)
            idx = int(tok["i"])
            total = total + lp[0, idx]
            ent = ent - (lp.exp() * lp.masked_fill(avail <= 0, 0.0)).sum()
            # Rebuild the masks rather than writing into them. `picked` feeds the option-summary
            # term inside `battle_logits`, so its backward pass needs the tensor it actually saw;
            # an in-place `picked[0, idx] = 1` bumps the version counter and autograd refuses the
            # earlier step's gradient.
            step = torch.zeros_like(legal)
            step[0, idx] = 1.0
            picked = picked + step
            avail = avail * (1.0 - step)
        return total, ent


class ConstructionActionHead:
    """One pool card per construction step. A single masked categorical, so one token."""

    def __init__(self, net: M.ByteRLRecurrentNet):
        self.net = net

    @torch.no_grad()
    def sample(self, h: torch.Tensor, pool_mask: torch.Tensor, rng=None,
               temperature: float = 1.0) -> ActionSequence:
        lg = self.net.construction_logits(h) / max(temperature, 1e-6)
        lp = M.masked_log_softmax(lg, pool_mask)
        p = lp.exp()[0]
        idx = (int(torch.multinomial(p, 1).item()) if rng is None
               else int(rng.choice(len(p), p=(p / p.sum()).cpu().numpy())))
        seq = ActionSequence(stage=1)
        seq.tokens.append(Token(TOK_POOL, idx, float(lp[0, idx].item()),
                                int(pool_mask.sum().item())))
        seq.chosen_elements = [idx]
        seq.count = 1
        seq.joint_logp = float(lp[0, idx].item())
        return seq

    def logp(self, h: torch.Tensor, pool_mask: torch.Tensor, seq_json: Dict[str, Any]
             ) -> Tuple[torch.Tensor, torch.Tensor]:
        lp = M.masked_log_softmax(self.net.construction_logits(h), pool_mask)
        idx = int(seq_json["tokens"][0]["i"])
        ent = -(lp.exp() * lp.masked_fill(pool_mask <= 0, 0.0)).sum()
        return lp[0, idx], ent


# ------------------------------------------------------------------ payload
def to_payload(sel, opts, seq: ActionSequence) -> List[int]:
    """Turn a token sequence into ONE legal environment action.

    B04's pass condition. If the sequence somehow produced no element (an empty legal mask, a
    degenerate select), fall back to the first option rather than emitting an empty payload the
    engine would reject — and the caller counts that fallback, because a silent repair is how a
    policy learns nothing from an illegal action.
    """
    picks = [opts[i] for i in seq.chosen_elements if 0 <= i < len(opts)]
    if not picks:
        picks = [opts[0]]
    return K.to_select_payload(picks, sel)


def sequence_is_legal(sel, opts, seq: ActionSequence) -> Tuple[bool, str]:
    """Does this sequence name a legal action? Used by probe B04 on every emitted sequence."""
    n = len(opts)
    if not seq.chosen_elements:
        return False, "no element chosen"
    if any(i < 0 or i >= n for i in seq.chosen_elements):
        return False, "element index out of range"
    if len(set(seq.chosen_elements)) != len(seq.chosen_elements):
        return False, "repeated element"
    lo, hi = select_bounds(sel, n)
    if not (lo <= len(seq.chosen_elements) <= hi):
        return False, f"count {len(seq.chosen_elements)} outside [{lo},{hi}]"
    return True, ""

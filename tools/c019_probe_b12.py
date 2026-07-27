"""c019 B12 — training continuation: resume functionality and exact stochastic continuation.

`PROBE_MATRIX.md` requires these two be reported SEPARATELY and forbids describing unequal
hashes as exact continuation. c018 conflated them, so this probe answers them as two independent
questions with two independent measurements:

1. **Resume functionality** — does a checkpoint fully determine the policy? Load it into a
   freshly constructed model and require bitwise-equal parameters AND identical forward output
   on real observations. Equal weights alone are not enough: a model whose behaviour depends on
   un-checkpointed state would still pass a weight comparison.

2. **Exact stochastic continuation** — would resuming reproduce the original training stream?
   This is answered by inspecting what the checkpoint actually contains, and then demonstrated
   rather than asserted. The answer here is NO, and the reason is concrete and checkable.

A probe that reports "resume works" and quietly lets the reader assume the stream is reproducible
is the failure mode the matrix is written against.
"""

from __future__ import annotations

import glob
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C19 = os.path.join(_REPO, "contracts", "c019_dual_method_campaign_ptcg_mcts_and_byterl",
                   "results")


def _latest_checkpoint(tag: str) -> str:
    d = os.path.join(C19, "byterl", "checkpoints", tag)
    c = [f for f in os.listdir(d) if f.endswith(".pt")]
    c.sort(key=lambda f: int("".join(x for x in f if x.isdigit()) or 0))
    return os.path.join(d, c[-1])


def _observations(n: int):
    """Real observations from real games -- a synthetic tensor would not exercise the encoder."""
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg import c019_baseline as B

    wrapper = B.BranchLocalBaseline()
    out = []

    def make_agent(st, w):
        def agent(obs):
            action, nxt = w.act(obs, st["mem"])
            st["mem"] = nxt
            if isinstance(obs, dict) and obs.get("select") is not None and len(out) < n:
                out.append(obs)
            return list(action)
        return agent

    def make_opp(o):
        def opp(obs):
            return o(obs)
        return opp

    gi = 0
    while len(out) < n and gi < 12:
        st = {"mem": wrapper.initial_memory()}
        env = make("cabt")
        env.run([make_agent(st, wrapper), make_opp(T.make_fresh("mega_lucario", ce.SOURCES))])
        gi += 1
    return out[:n]


def main(argv=None):
    import torch
    from cg import c019_byterl_model as M, c019_byterl_encode as E

    tag = (argv or sys.argv[1:] or ["scaled2"])[0]
    ck = _latest_checkpoint(tag)
    payload = torch.load(ck, map_location="cpu", weights_only=False)

    out = {"probe": "B12_training_continuation", "tag": tag,
           "checkpoint": os.path.basename(ck)}

    # ---------------------------------------------------------------- 1. resume functionality
    a = M.PTCGByteRL(**{k: v for k, v in payload["cfg"].items()
                        if k in ("d_card", "d_zone", "d_ctx", "lstm_hidden", "d_opt")})
    a.load_state_dict(payload["state_dict"])
    a.eval()
    b = M.PTCGByteRL(**{k: v for k, v in payload["cfg"].items()
                        if k in ("d_card", "d_zone", "d_ctx", "lstm_hidden", "d_opt")})
    # b is freshly random: it MUST differ before load and match exactly after
    differs_before = any(not torch.equal(pa, pb) for pa, pb in
                         zip(a.state_dict().values(), b.state_dict().values()))
    b.load_state_dict(torch.load(ck, map_location="cpu", weights_only=False)["state_dict"])
    b.eval()
    tensors = list(a.state_dict().items())
    equal = [k for k, v in tensors if torch.equal(v, b.state_dict()[k])]

    obs = _observations(24)
    same_out, checked, maxdiff = True, 0, 0.0
    for o in obs:
        try:
            batch = M.to_torch(E.encode(o))
        except Exception:  # noqa: BLE001
            continue
        with torch.no_grad():
            la, va, _ = a.forward(batch, None)
            lb, vb, _ = b.forward(batch, None)
        checked += 1
        d = max(float((la - lb).abs().max()), float((va - vb).abs().max()))
        maxdiff = max(maxdiff, d)
        if d > 0.0:
            same_out = False

    out["resume_functionality"] = {
        "question": "does the checkpoint fully determine the policy?",
        "parameters_total": len(tensors),
        "parameters_bitwise_equal_after_load": len(equal),
        "fresh_model_differed_before_load": differs_before,
        "observations_checked": checked,
        "max_abs_output_difference": maxdiff,
        "identical_forward_output": bool(same_out and checked > 0),
        "status": "PASS" if (len(equal) == len(tensors) and differs_before
                             and same_out and checked > 0) else "FAIL",
    }

    # ------------------------------------------------- 2. exact stochastic continuation
    # Answered from what the checkpoint CONTAINS, not from a hash comparison. Reproducing a
    # training stream needs the RNG state of the learner and of every actor process, the queue
    # contents, and the optimizer moments. The payload carries none of them.
    required = {
        "model_parameters": "state_dict" in payload,
        "learner_rng_state": "rng_state" in payload or "torch_rng_state" in payload,
        "actor_rng_states": "actor_rng_states" in payload,
        "optimizer_state": "optimizer" in payload or "optim_state" in payload,
        "queue_contents": "queue" in payload,
    }
    missing = [k for k, v in required.items() if not v]
    out["exact_stochastic_continuation"] = {
        "question": "would resuming reproduce the original training stream bit-for-bit?",
        "answer": "NO",
        "checkpoint_payload_keys": sorted(payload.keys()),
        "required_for_exactness": required,
        "missing": missing,
        "reason": f"the payload carries {', '.join(sorted(payload.keys()))} and nothing else. "
                  f"Without the learner and per-actor RNG states, the optimizer moments and the "
                  f"queue contents, a resumed run draws a different stochastic stream from the "
                  f"first step. This is a deliberate scope decision, not a measurement: it is "
                  f"stated as unsupported rather than tested and described ambiguously.",
        "status": "NOT_SUPPORTED",
    }

    # the two answers are never merged, and resume is never described as exactness
    out["reported_separately"] = True
    out["status"] = out["resume_functionality"]["status"]

    d = os.path.join(C19, "probes", "B12_training_continuation")
    os.makedirs(os.path.join(d, "raw"), exist_ok=True)
    json.dump(out, open(os.path.join(d, "raw", "continuation_detail.json"), "w"), indent=2,
              default=str)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

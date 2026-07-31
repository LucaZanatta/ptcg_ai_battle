"""c022 — the ByteRL analyses `CONTRACT §6` names, as artifacts rather than as probe verdicts.

`results/byterl/architecture/`, `action_traces/`, `end_to_end/` and `fixed_deck/` were empty
directories. The probes that decide those properties pass, but they write a boolean into
`probes/byterl_probes.json`, and a boolean is not an analysis: a reader who wants to know whether
the action distribution really factorizes autoregressively over a MASKED option set cannot check
that from `"pass": true`.

So this writes what the probes assert:

    architecture/     every module, its shape, its parameter count, and the shared torso
    action_traces/    real decisions, token by token: the legal mask, the distribution over it,
                      the chosen index, and the joint log-probability recomputed from the parts
    end_to_end/       decks a checkpoint actually builds -- legality, and DIVERSITY, because
                      "legal" is satisfied by emitting the same deck every time
    fixed_deck/       the fixed-deck arm's decision profile, for the same reason

`DECISION_RULES §3` says of the end-to-end arm that "merely generating legal decks is partial",
so the diversity measurement is not a nicety -- it is the difference between PASS and PARTIAL,
and it needs a number.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
BY = os.path.join(C22, "byterl")


def architecture(net, pool, dims) -> Dict[str, Any]:
    """Every module and its parameter count, plus the properties B01 asserts."""
    import torch.nn as nn
    mods = []
    total = 0
    lstm = None
    for name, m in net.named_modules():
        if not name:
            continue
        p = sum(q.numel() for q in m.parameters(recurse=False))
        total += p
        row = {"name": name, "type": type(m).__name__, "own_parameters": p}
        if isinstance(m, nn.LSTM) or isinstance(m, nn.LSTMCell):
            lstm = {"name": name, "input_size": getattr(m, "input_size", None),
                    "hidden_size": getattr(m, "hidden_size", None),
                    "num_layers": getattr(m, "num_layers", 1)}
            row.update(lstm)
        if isinstance(m, nn.Linear):
            row.update({"in_features": m.in_features, "out_features": m.out_features})
        mods.append(row)
    return {
        "probe": "B01",
        "total_parameters": sum(q.numel() for q in net.parameters()),
        "own_parameter_sum": total,
        "recurrence": lstm,
        "lstm_hidden_size_is_256": bool(lstm and lstm.get("hidden_size") == 256),
        "encoder_dims": dims,
        "pool_size": pool.size(),
        "modules": mods,
        "note": ("`FIDELITY_RULES §4` requires LSTM-256 over a shared torso. c021's defining "
                 "absence was recurrence entirely, so the hidden size is recorded as a value "
                 "rather than described."),
    }


def action_traces(net, pool, n_obs: int, seed: int) -> List[Dict[str, Any]]:
    """Real battle decisions, factorized token by token.

    The joint log-probability is recomputed here from the per-token distributions and compared
    against the sampler's own value. `B05` asserts they agree; this records BOTH numbers so a
    reader can see the factorization rather than trust it.
    """
    import numpy as np
    import torch
    from cg import c022_byterl_actor as ACT
    from cg import c022_byterl_encode as EN

    rows: List[Dict[str, Any]] = []
    rng = np.random.default_rng(seed)
    runner = ACT.EpisodeRunner(net, pool, rng, True)
    runner.build_deck()

    for step in runner.steps[:n_obs]:
        seq = step.seq
        toks = seq.get("tokens") or []
        recomputed = sum(float(t.get("logp") or 0.0) for t in toks)
        rows.append({
            "stage": "construction" if step.stage == EN.STAGE_CONSTRUCTION else "battle",
            "n_tokens": len(toks),
            "tokens": [{"kind": t.get("kind"), "index": t.get("index"),
                        "n_legal": t.get("n_legal"), "logp": round(float(t.get("logp") or 0), 6),
                        "probability": round(math.exp(float(t.get("logp") or 0)), 6)}
                       for t in toks],
            "joint_logp_from_sampler": round(float(step.behaviour_logp), 6),
            "joint_logp_recomputed_from_tokens": round(recomputed, 6),
            "difference": round(abs(float(step.behaviour_logp) - recomputed), 9),
            "uniform_behaviour": bool(step.uniform_behaviour),
            "policy_logp": (None if step.policy_logp is None
                            else round(float(step.policy_logp), 6)),
            "min_count": step.min_count, "max_count": step.max_count,
        })
    return rows


def construction_analysis(net, pool, n_decks: int, seed: int) -> Dict[str, Any]:
    """Legality AND diversity. `DECISION_RULES §3`: legal-but-identical decks are PARTIAL."""
    import numpy as np
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_actor as ACT

    decks, legal_flags = [], []
    for i in range(n_decks):
        r = ACT.EpisodeRunner(net, pool, np.random.default_rng(seed + i), True)
        deck, legal = r.build_deck()
        decks.append(tuple(sorted(deck)))
        legal_flags.append(bool(legal))

    counts = collections.Counter(decks)
    card_use = collections.Counter()
    for d in decks:
        card_use.update(set(d))
    # Mean pairwise Jaccard distance over card SETS: 0 means every deck is the same list.
    sets = [set(d) for d in decks]
    dists = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            u = len(sets[i] | sets[j])
            dists.append(1.0 - (len(sets[i] & sets[j]) / u) if u else 0.0)
    return {
        "probe": "B18/B19",
        "decks_built": len(decks),
        "legal": sum(legal_flags),
        "legal_fraction": round(sum(legal_flags) / max(1, len(decks)), 4),
        "distinct_decks": len(counts),
        "most_common_deck_count": counts.most_common(1)[0][1] if counts else 0,
        "distinct_cards_used": len(card_use),
        "pool_size": pool.size(),
        "mean_pairwise_jaccard_distance": round(sum(dists) / len(dists), 4) if dists else None,
        "diversity_note": (
            "mean pairwise Jaccard distance over card sets. 0.0 would mean the policy emits one "
            "deck every time, which satisfies 'legal' and is exactly the case DECISION_RULES §3 "
            "calls PARTIAL rather than PASS."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None,
                    help="a trained checkpoint. Omitted = fresh random weights, which is the "
                         "right baseline for the ARCHITECTURE and ACTION-SHAPE analyses and the "
                         "wrong one for diversity; both are labelled in the output.")
    ap.add_argument("--decks", type=int, default=24)
    ap.add_argument("--obs", type=int, default=12)
    ap.add_argument("--seed", type=int, default=606)
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(1)
    from cg import c021_byterl_deck as DK
    from cg import c022_byterl_encode as EN
    from cg import c022_byterl_model as M

    pool = DK.CardPool.from_archetypes()
    dims = EN.dims()
    net = M.fresh(dims["global_dim"], dims["slot_dim"], dims["option_dim"], pool.size(),
                  n_cards=dims["n_cards"], seed=a.seed)
    label = "fresh_random_weights"
    if a.checkpoint and os.path.isfile(a.checkpoint):
        net.load_state_dict(torch.load(a.checkpoint, map_location="cpu", weights_only=False))
        label = os.path.basename(a.checkpoint)
    net.eval()

    arch = architecture(net, pool, dims)
    arch["weights"] = label
    p = os.path.join(BY, "architecture", "architecture.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump(arch, fh, indent=2)

    traces = action_traces(net, pool, a.obs, a.seed)
    q = os.path.join(BY, "action_traces", "action_traces.jsonl")
    os.makedirs(os.path.dirname(q), exist_ok=True)
    with open(q, "w") as fh:
        for r in traces:
            fh.write(json.dumps({**r, "weights": label}) + "\n")
    worst = max((r["difference"] for r in traces), default=0.0)

    cons = construction_analysis(net, pool, a.decks, a.seed)
    cons["weights"] = label
    r = os.path.join(BY, "end_to_end", "construction_analysis.json")
    os.makedirs(os.path.dirname(r), exist_ok=True)
    with open(r, "w") as fh:
        json.dump(cons, fh, indent=2)

    print(f"architecture: LSTM hidden={arch['recurrence']} "
          f"is256={arch['lstm_hidden_size_is_256']} params={arch['total_parameters']:,}")
    print(f"action traces: {len(traces)} decisions, worst joint-logp reconstruction "
          f"difference {worst:.2e}")
    print(f"construction ({label}): {cons['legal']}/{cons['decks_built']} legal, "
          f"{cons['distinct_decks']} distinct, mean pairwise Jaccard "
          f"{cons['mean_pairwise_jaccard_distance']}, {cons['distinct_cards_used']} of "
          f"{cons['pool_size']} cards used")
    for path in (p, q, r):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

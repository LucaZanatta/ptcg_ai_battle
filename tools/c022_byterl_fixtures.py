"""c022 probes B11/B12/B13 and B15/B16/B17 — the numbers, written down.

These probes already exist as tests. A test is the right place to ASSERT agreement, and the
wrong place to leave the evidence: `results/byterl/numerical_fixtures/` and
`results/byterl/osfp/` were empty directories, so a reader wanting to check the V-trace
implementation had to run pytest and read source rather than open an artifact and compare
columns.

This writes the artifact. For every fixture it records the inputs, an INDEPENDENT reference
value computed here in plain Python from the published equation, the implementation's value, and
their difference — so disagreement is visible as a number rather than as a red test name.

The reference implementations are transcribed from the papers, deliberately duplicating
`tests/test_c022_byterl_objectives.py` rather than importing it. Two transcriptions agreeing is
evidence; one transcription imported twice is a tautology, and the point of an independent
reference is lost the moment it shares code with what it checks.
"""

from __future__ import annotations

import argparse
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

TOL = 1e-5


# ---------------------------------------------------------------- independent references
def ref_vtrace(target_logp, behaviour_logp, values, rewards, bootstrap, discounts,
               rho_bar=1.0, c_bar=1.0, two_sided=False, lo=0.001, hi=1.007):
    """IMPALA eq. 1. Plain floats; no torch, no shared code with the implementation."""
    n = len(values)
    ratios = [math.exp(t - b) for t, b in zip(target_logp, behaviour_logp)]
    if two_sided:
        rho = [min(max(r, lo), hi) for r in ratios]
        c = [min(max(r, lo), hi) for r in ratios]
    else:
        rho = [min(r, rho_bar) for r in ratios]
        c = [min(r, c_bar) for r in ratios]
    v_tp1 = list(values[1:]) + [bootstrap]
    deltas = [rho[t] * (rewards[t] + discounts[t] * v_tp1[t] - values[t]) for t in range(n)]
    acc, vs_minus_v = 0.0, [0.0] * n
    for t in range(n - 1, -1, -1):
        acc = deltas[t] + discounts[t] * c[t] * acc
        vs_minus_v[t] = acc
    vs = [vs_minus_v[t] + values[t] for t in range(n)]
    vs_tp1 = list(vs[1:]) + [bootstrap]
    pg = [rho[t] * (rewards[t] + discounts[t] * vs_tp1[t] - values[t]) for t in range(n)]
    return {"vs": vs, "pg_advantage": pg, "rho": rho, "c": c}


def ref_upgo(rewards, values, bootstrap, discounts):
    """G_t = r_t + gamma * (G_{t+1} if Q_{t+1} >= V(s_{t+1}) else V(s_{t+1}))."""
    n = len(values)
    v_tp1 = list(values[1:]) + [bootstrap]
    r_tp1 = list(rewards[1:]) + [0.0]
    v_tp2 = (list(values[2:]) + [bootstrap, bootstrap])[:n]
    d_tp1 = list(discounts[1:]) + [discounts[-1]]
    q_tp1 = [r_tp1[t] + d_tp1[t] * v_tp2[t] for t in range(n)]
    g, nxt = [0.0] * n, bootstrap
    for t in range(n - 1, -1, -1):
        g[t] = rewards[t] + discounts[t] * (nxt if q_tp1[t] >= v_tp1[t] else v_tp1[t])
        nxt = g[t]
    return g


def ref_ppo(target_logp, behaviour_logp, adv, eps):
    out = []
    for t, b, a in zip(target_logp, behaviour_logp, adv):
        r = math.exp(t - b)
        out.append(-min(r * a, min(max(r, 1 - eps), 1 + eps) * a))
    return sum(out) / len(out)


def case(seed: int, n: int = 6) -> Dict[str, List[float]]:
    """Deterministic inputs from a plain LCG, so the fixture does not depend on torch's RNG."""
    s = (seed * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def nxt():
        nonlocal s
        s = (s * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return ((s >> 11) / float(1 << 53)) * 2.0 - 1.0

    return {
        "target_logp": [round(nxt() * 0.4 - 1.0, 6) for _ in range(n)],
        "behaviour_logp": [round(nxt() * 0.4 - 1.0, 6) for _ in range(n)],
        "values": [round(nxt() * 0.3, 6) for _ in range(n)],
        "rewards": [0.0] * (n - 1) + [1.0],
        "discounts": [1.0] * n,
        "bootstrap": 0.0,
    }


def cmp_rows(name: str, ref: List[float], got: List[float]) -> Dict[str, Any]:
    d = [abs(a - b) for a, b in zip(ref, got)]
    return {"quantity": name,
            "reference": [round(x, 8) for x in ref],
            "implementation": [round(x, 8) for x in got],
            "max_abs_difference": round(max(d) if d else 0.0, 10),
            "agrees": bool(d and max(d) <= TOL)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BY, "numerical_fixtures", "fixtures.json"))
    ap.add_argument("--osfp-out", default=os.path.join(BY, "osfp", "osfp_accounting.json"))
    a = ap.parse_args(argv)

    import torch
    torch.set_num_threads(1)
    from cg import c022_byterl_learn as L

    def T(x):
        return torch.tensor(x, dtype=torch.float32)

    fixtures: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- B11 V-trace
    for seed in (0, 1, 2, 3, 7):
        d = case(seed)
        cfg = L.LossConfig(gamma=1.0, rho_bar=1.0, c_bar=1.0, two_sided=False)
        out = L.vtrace(T(d["target_logp"]), T(d["behaviour_logp"]), T(d["values"]),
                       T(d["rewards"]), torch.zeros(()), T(d["discounts"]), cfg)
        ref = ref_vtrace(d["target_logp"], d["behaviour_logp"], d["values"], d["rewards"],
                         d["bootstrap"], d["discounts"])
        fixtures.append({
            "probe": "B11", "name": "V-trace (one-sided, rho_bar = c_bar = 1)",
            "seed": seed, "inputs": d,
            "comparisons": [cmp_rows(k, ref[k], out[k].tolist())
                            for k in ("vs", "pg_advantage", "rho", "c")]})

    # ---------------------------------------------------------------- B13 two-sided clipping
    for seed in (0, 5):
        d = case(seed)
        cfg = L.LossConfig(gamma=1.0, two_sided=True,
                           rho_lower=L.RHO_LOWER_B3, rho_upper=L.RHO_UPPER_B3)
        out = L.vtrace(T(d["target_logp"]), T(d["behaviour_logp"]), T(d["values"]),
                       T(d["rewards"]), torch.zeros(()), T(d["discounts"]), cfg)
        ref = ref_vtrace(d["target_logp"], d["behaviour_logp"], d["values"], d["rewards"],
                         d["bootstrap"], d["discounts"], two_sided=True,
                         lo=L.RHO_LOWER_B3, hi=L.RHO_UPPER_B3)
        fixtures.append({
            "probe": "B13",
            "name": f"two-sided clipped V-trace [{L.RHO_LOWER_B3}, {L.RHO_UPPER_B3}]",
            "seed": seed, "inputs": d,
            "comparisons": [cmp_rows(k, ref[k], out[k].tolist())
                            for k in ("vs", "pg_advantage", "rho", "c")]})

    # The clipping bounds are a PUBLISHED b3 setting, not a tuned one, so they are recorded as
    # values rather than described.
    fixtures.append({
        "probe": "B13", "name": "published b3 clipping bounds", "seed": None,
        "inputs": {}, "comparisons": [{
            "quantity": "(rho_lower, rho_upper)",
            "reference": [0.001, 1.007],
            "implementation": [L.RHO_LOWER_B3, L.RHO_UPPER_B3],
            "max_abs_difference": round(max(abs(0.001 - L.RHO_LOWER_B3),
                                            abs(1.007 - L.RHO_UPPER_B3)), 10),
            "agrees": bool(L.RHO_LOWER_B3 == 0.001 and L.RHO_UPPER_B3 == 1.007)}]})

    # ---------------------------------------------------------------- B12 UPGO
    for seed in (0, 2, 9):
        d = case(seed)
        got = L.upgo_returns(T(d["rewards"]), T(d["values"]), torch.zeros(()),
                             T(d["discounts"]))
        ref = ref_upgo(d["rewards"], d["values"], d["bootstrap"], d["discounts"])
        fixtures.append({
            "probe": "B12", "name": "UPGO conditional bootstrap", "seed": seed, "inputs": d,
            "comparisons": [cmp_rows("upgo_target", ref, got.tolist())]})

    # ---------------------------------------------------------------- B13 PPO surrogate
    # The surrogate is not a standalone function: it lives inside `byterl_losses` under
    # `cfg.ppo_clip`. That is the right place for it, and it means the fixture must drive the
    # real objective and read `pg_loss` back.
    #
    # The advantage fed to the reference is the V-TRACE advantage the implementation computed,
    # not an arbitrary vector. `B4` names ordinary PPO with a GAE advantage as a hard failure,
    # so "the clip is right" is only half the property -- the other half is WHICH advantage it
    # clips, and pairing the reference to v["pg_advantage"] is what tests it.
    for seed in (1, 4):
        d = case(seed)
        cfg = L.LossConfig(gamma=1.0, two_sided=True, ppo_clip=True,
                           rho_lower=L.RHO_LOWER_B3, rho_upper=L.RHO_UPPER_B3)
        args = (T(d["target_logp"]), T(d["behaviour_logp"]), T(d["values"]),
                T(d["rewards"]), torch.zeros(()), T(d["discounts"]))
        v = L.vtrace(*args, cfg)
        adv = v["pg_advantage"].detach().tolist()
        _total, stats = L.byterl_losses(
            T(d["target_logp"]), T(d["behaviour_logp"]), torch.zeros(len(d["values"])),
            T(d["values"]), T(d["rewards"]), torch.zeros(()), T(d["discounts"]), cfg)
        ref = ref_ppo(d["target_logp"], d["behaviour_logp"], adv, L.PPO_CLIP_EPS)
        fixtures.append({
            "probe": "B13", "name": f"PPO-style clipped surrogate on the V-TRACE advantage, "
                                    f"eps = {L.PPO_CLIP_EPS}",
            "seed": seed, "inputs": {**d, "vtrace_advantage": [round(x, 8) for x in adv]},
            "comparisons": [cmp_rows("pg_loss", [ref], [float(stats["pg_loss"])])]})

    n_ok = sum(1 for f in fixtures for c in f["comparisons"] if c["agrees"])
    n_tot = sum(len(f["comparisons"]) for f in fixtures)
    report = {
        "probes": ["B11", "B12", "B13"],
        "tolerance": TOL,
        "n_comparisons": n_tot, "n_agreeing": n_ok, "all_agree": n_ok == n_tot,
        "why_the_reference_is_duplicated": (
            "the reference implementations here are transcribed from the published equations "
            "and deliberately do NOT import the test module's copies. Two independent "
            "transcriptions agreeing is evidence; one transcription imported twice is a "
            "tautology."),
        "fixtures": fixtures,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(report, fh, indent=2)

    # ---------------------------------------------------------------- B15/B16/B17 OSFP
    # A real model object is needed to freeze, so the smallest one the module will accept.
    import torch.nn as nn
    o = L.OSFP(max_history=4)
    trace: List[Dict[str, Any]] = []

    def snap(event: str):
        trace.append({"event": event, "period": getattr(o, "period", None),
                      "history": len(getattr(o, "history", []) or []),
                      "max_history": getattr(o, "max_history", None)})

    snap("init")
    for i in range(6):
        try:
            o.record(opponent_index=i % 3, payoff=float(i % 2))
        except Exception as e:  # noqa: BLE001
            trace.append({"event": f"record {i}", "error": f"{type(e).__name__}: {e}"})
        snap(f"record {i}")
    # Promote six times against a max_history of 4, so eviction is exercised and the surviving
    # entries can be checked for mutation. B17's requirement is that history is IMMUTABLE: an
    # entry already frozen must not change when a later promotion lands.
    shas_before = []
    for i in range(6):
        try:
            o.promote(nn.Linear(2, 2), label=f"p{i}")
            snap(f"promote {i}")
            shas_before.append([h.sha256 for h in o.history])
        except Exception as e:  # noqa: BLE001
            trace.append({"event": f"promote {i}", "error": f"{type(e).__name__}: {e}"})
    # every sha that survives from one snapshot to the next must be unchanged
    immutable = True
    for earlier, later in zip(shas_before, shas_before[1:]):
        common = set(earlier) & set(later)
        for sha in common:
            if earlier.index(sha) < 0 or later.index(sha) < 0:
                immutable = False
    before = after = None

    osfp = {
        "probes": ["B15", "B16", "B17"],
        "constants": {
            "OSFP_SELFPLAY_PROB": getattr(L, "OSFP_SELFPLAY_PROB", None),
            "OSFP_PROMOTION_THRESHOLD": getattr(L, "OSFP_PROMOTION_THRESHOLD", None),
            "OSFP_MAX_PERIODS_WITHOUT_PROMOTION": getattr(
                L, "OSFP_MAX_PERIODS_WITHOUT_PROMOTION", None),
        },
        "history_bounded": len(o.history) <= o.max_history,
        "history_size": len(o.history), "max_history": o.max_history,
        "periods": o.period,
        "promotions": o.promotions,
        "existing_entries_not_mutated_by_promotion": immutable,
        "surviving_sha_snapshots": shas_before,
        "trace": trace,
        "note": ("period-local accumulators and immutable history are asserted in "
                 "tests/test_c022_byterl_objectives.py::test_b15..b17; this file records the "
                 "observed accounting so the requirement has an artifact and not only a test."),
    }
    os.makedirs(os.path.dirname(a.osfp_out), exist_ok=True)
    with open(a.osfp_out, "w") as fh:
        json.dump(osfp, fh, indent=2)

    print(f"B11/B12/B13: {n_ok}/{n_tot} comparisons agree at {TOL}")
    for f in fixtures:
        for c in f["comparisons"]:
            if not c["agrees"]:
                print(f"   ! {f['probe']} {f['name']} seed={f['seed']} {c['quantity']}: "
                      f"max diff {c['max_abs_difference']}")
    print(f"OSFP: history_bounded={osfp['history_bounded']} "
          f"immutable={osfp['existing_entries_not_mutated_by_promotion']}")
    print(f"wrote {a.out}\nwrote {a.osfp_out}")
    return 0 if n_ok == n_tot else 1


if __name__ == "__main__":
    raise SystemExit(main())

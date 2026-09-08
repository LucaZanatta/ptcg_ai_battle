"""c021 A9 — semantic validator: inject every known defect and require the checks to reject it.

A conformance check that has never failed is not evidence. Each check below is paired with an
INJECTION that reproduces the real defect, and the validator asserts two things per check:

    * the clean implementation PASSES, and
    * the injected implementation FAILS.

A check that cannot fail is reported as INERT, which is itself a failure. Every defect here was
actually observed and fixed in c019, c020 or c021 -- none is hypothetical.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C21 = os.path.join(_REPO, "contracts",
                   "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
VAL = os.path.join(C21, "validation")


class Check:
    def __init__(self, cid: str, origin: str, description: str,
                 probe: Callable[[], bool], inject: Callable[[], Any],
                 restore: Callable[[Any], None]):
        self.cid = cid
        self.origin = origin
        self.description = description
        self.probe = probe          # True when the implementation is correct
        self.inject = inject        # break it; returns a token for restore
        self.restore = restore

    def run(self) -> Dict[str, Any]:
        rec: Dict[str, Any] = {"id": self.cid, "origin": self.origin,
                               "description": self.description}
        try:
            rec["clean_pass"] = bool(self.probe())
        except Exception as e:  # noqa: BLE001
            rec["clean_pass"] = False
            rec["clean_error"] = f"{type(e).__name__}: {e}"[:200]
        token = None
        try:
            token = self.inject()
            try:
                rec["injected_pass"] = bool(self.probe())
            except Exception:  # noqa: BLE001
                rec["injected_pass"] = False       # raising counts as rejecting the defect
        except Exception as e:  # noqa: BLE001
            rec["inject_error"] = f"{type(e).__name__}: {e}"[:200]
            rec["injected_pass"] = None
        finally:
            try:
                self.restore(token)
            except Exception as e:  # noqa: BLE001
                rec["restore_error"] = f"{type(e).__name__}: {e}"[:200]
        # the check is meaningful only if it passes clean AND fails injected
        rec["detects_defect"] = bool(rec.get("clean_pass") and rec.get("injected_pass") is False)
        rec["inert"] = bool(rec.get("clean_pass") and rec.get("injected_pass") is True)
        rec["status"] = ("PASS" if rec["detects_defect"]
                         else ("INERT" if rec["inert"] else "FAIL"))
        return rec


def build_checks() -> List[Check]:
    from cg import c021_byterl_deck as DK
    from cg import c021_byterl_learn as BL
    from cg import c021_byterl_model as BM
    from cg import c021_mcgs as S
    from cg import c021_mcgs_graph as G
    import torch

    checks: List[Check] = []

    # ---------------------------------------------------------------- MCGS: UCB1 not PUCT
    def probe_ucb1() -> bool:
        p, c = G.Node(), G.Node()
        p.total_visit, p.visit_count = 100, 40
        c.visit_count, c.rewards = 10, 4.0
        e = G.Edge.connect(p, c, 0)
        e.visit_count = 10
        want = 0.4 + G.UCT_CONSTANT * math.sqrt(2.0 * math.log(100) / 10)
        return abs(e.value(G.UCT_CONSTANT) - want) < 1e-9

    def inject_ucb1():
        orig = G.Edge.value

        def puct(self, c, ucd=True):          # the c020 formula this contract forbids
            x = self.successor.value(0.0)
            if c == 0:
                return x
            n = self.predecessor.total_visit if ucd else self.predecessor.visit_count
            return x + c * math.sqrt(max(n, 1)) / (1 + self.visit_count)
        G.Edge.value = puct
        return orig

    checks.append(Check(
        "MCGS_UCB1_NOT_PUCT", "c020 substituted PUCT for the source's UCB1",
        "Edge.Value must be Q + c*sqrt(2 ln N / n) with no prior term",
        probe_ucb1, inject_ucb1, lambda o: setattr(G.Edge, "value", o)))

    # ---------------------------------------------------------------- UCD divisor
    def probe_total_visit() -> bool:
        p, c = G.Node(), G.Node()
        p.total_visit, p.visit_count = 1000, 10
        c.visit_count, c.rewards = 5, 0.0
        e = G.Edge.connect(p, c, 0)
        e.visit_count = 5
        return e.value(0.285, ucd=True) > e.value(0.285, ucd=False)

    def inject_total_visit():
        orig = G.Edge.value

        def visit_only(self, c, ucd=True):
            return orig(self, c, ucd=False)
        G.Edge.value = visit_only
        return orig

    checks.append(Check(
        "MCGS_UCD_USES_TOTAL_VISIT", "source Edge.Value divides by Predecessor.TotalVisit",
        "under UCD the exploration term uses TotalVisit, not the predecessor's own VisitCount",
        probe_total_visit, inject_total_visit, lambda o: setattr(G.Edge, "value", o)))

    # ---------------------------------------------------------------- inert UCD recursion
    def probe_ucd_inert() -> bool:
        return (G.UCDParams(1, 0).recursion_is_active is False
                and G.UCDParams(2, 0).recursion_is_active is True)

    def inject_ucd_inert():
        orig = G.UCDParams.recursion_is_active
        G.UCDParams.recursion_is_active = property(lambda self: True)
        return orig

    checks.append(Check(
        "MCGS_UCD_DEFAULT_IS_INERT", "FIDELITY_RULES §5: reproduce, do not 'fix'",
        "at the source default (1, 0) RecursiveUpdate must do nothing",
        probe_ucd_inert, inject_ucd_inert,
        lambda o: setattr(G.UCDParams, "recursion_is_active", o)))

    # ---------------------------------------------------------------- damping key
    def probe_damping() -> bool:
        return (G.Node.reduce_function(24, 0) == 24
                and G.Node.reduce_function(24, 1) == 12
                and G.Node.reduce_function(24, 3) == 3)

    def inject_damping():
        orig = G.Node.reduce_function
        G.Node.reduce_function = staticmethod(lambda w, n: w)   # damping removed
        return orig

    checks.append(Check(
        "MCGS_DAMPED_SAMPLING", "c021 port bug 3: damping keyed on depth, not samples traversed",
        "ReduceFunction must divide SampleWidth by DampingParameter^numSampleTraversed",
        probe_damping, inject_damping,
        lambda o: setattr(G.Node, "reduce_function", o)))

    # ---------------------------------------------------------------- A4 chance-node guard
    def probe_coin_guard() -> bool:
        st = S.new_stats()
        n = G.Node(select_context=46, is_random=True)
        for i in range(2):
            G.Edge.connect(n, G.Node(), i)
        n.best_child(0.285, np.random.default_rng(0), st)
        if st["manual_coin_node_ucb_selected"] != 0:
            return False
        st2 = S.new_stats()
        m = G.Node(select_context=46, is_random=False)    # the defect
        for i in range(2):
            G.Edge.connect(m, G.Node(), i)
        m.best_child(0.285, np.random.default_rng(0), st2)
        return st2["manual_coin_node_ucb_selected"] == 1

    def inject_coin_guard():
        orig = G.MANUAL_COIN_CONTEXTS
        G.MANUAL_COIN_CONTEXTS = frozenset()             # guard blinded
        return orig

    checks.append(Check(
        "MCGS_A4_COIN_NEVER_UCB_SELECTED", "A4: a searched coin flip makes the agent clairvoyant",
        "manual-coin contexts must be sampled, never chosen by UCB, and the counter must fire",
        probe_coin_guard, inject_coin_guard,
        lambda o: setattr(G, "MANUAL_COIN_CONTEXTS", o)))

    # ---------------------------------------------------------------- perspective
    class _Cur:
        def __init__(self, yi):
            self.yourIndex = yi

    class _Obs:
        def __init__(self, yi):
            self.current = _Cur(yi)

    def probe_perspective() -> bool:
        return (S.MCGS._your_index(_Obs(0), 9) == 0
                and S.MCGS._your_index(_Obs(1), 9) == 1)

    def inject_perspective():
        orig = S.MCGS._your_index
        S.MCGS._your_index = staticmethod(
            lambda obs, default=0: int(getattr(obs, "yourIndex", default)))   # the real bug
        return orig

    checks.append(Check(
        "MCGS_YOURINDEX_THROUGH_CURRENT",
        "c021: is_opponent was False for every node, so the search assumed a cooperating opponent",
        "yourIndex must be read from observation.current, not the top level",
        probe_perspective, inject_perspective,
        lambda o: setattr(S.MCGS, "_your_index", o)))

    # ---------------------------------------------------------------- dummy edges
    def probe_dummy() -> bool:
        p = G.Node()
        p.total_visit = 100
        t = G.Node()
        t.visit_count, t.rewards = 5, 5.0
        twin = G.Edge.connect(p, t, 0)
        twin.visit_count = 5
        d = G.Edge.connect(p, t, 1)
        d.is_dummy = True
        return d.value(0.285) < twin.value(0.285)

    def inject_dummy():
        orig = G.Edge.is_dummy
        G.Edge.is_dummy = property(lambda self: self._dummy,
                                   lambda self, v: setattr(self, "_dummy", bool(v)))
        return orig

    checks.append(Check(
        "MCGS_DUMMY_EDGE_LOSES_TO_TWIN", "transposition: a dummy edge must not outrank its twin",
        "setting IsDummy must park VisitCount so the twin keeps the larger exploration bonus",
        probe_dummy, inject_dummy, lambda o: setattr(G.Edge, "is_dummy", o)))

    # ---------------------------------------------------------------- deck legality
    pool = DK.CardPool.from_archetypes()

    def probe_energy_cap() -> bool:
        if 1118 in pool.basic_energy:            # Energy Retrieval is a Trainer
            return False
        deck = [1118] * 20 + [sorted(pool.basic_energy)[0]] * 39 + [sorted(pool.basic_pokemon)[0]]
        return not DK.legality(deck, pool)[0]

    def inject_energy_cap():
        orig = DK.is_basic_energy
        DK.is_basic_energy = lambda cd: (cd is not None and
                                         "energy" in str(getattr(cd, "name", "")).lower())
        pool.basic_energy = {c for c in pool.card_ids
                             if DK.is_basic_energy(DK.CD.card(c))}
        return orig

    def restore_energy_cap(o):
        DK.is_basic_energy = o
        pool.basic_energy = {c for c in pool.card_ids if o(DK.CD.card(c))}

    checks.append(Check(
        "DECK_ENERGY_CAP_IS_STRUCTURAL",
        "c021: 'energy' in name classified Energy Retrieval (a Trainer) as uncapped",
        "only cardType 5 with no skills is exempt from the 4-copy limit",
        probe_energy_cap, inject_energy_cap, restore_energy_cap))

    def probe_ace_spec() -> bool:
        a, b = sorted(pool.ace_spec)[:2]
        e, bp = sorted(pool.basic_energy)[0], sorted(pool.basic_pokemon)[0]
        return (DK.legality([a] + [e] * 55 + [bp] * 4, pool)[0]
                and not DK.legality([a, b] + [e] * 54 + [bp] * 4, pool)[0])

    def inject_ace_spec():
        orig = DK.ACE_SPEC_LIMIT
        DK.ACE_SPEC_LIMIT = 99
        return orig

    checks.append(Check(
        "DECK_ACE_SPEC_CATEGORY_LIMIT",
        "c021: the engine returned INVALID for every generated deck",
        "at most ONE ACE SPEC card in total, across the whole category",
        probe_ace_spec, inject_ace_spec, lambda o: setattr(DK, "ACE_SPEC_LIMIT", o)))

    # ---------------------------------------------------------------- masking
    def probe_masking() -> bool:
        logits = torch.randn(1, 20)
        mask = torch.zeros(1, 20)
        mask[0, :5] = 1.0
        p = BM.masked_log_softmax(logits, mask).exp()
        return float((p * (mask <= 0)).sum()) == 0.0 and abs(float(p.sum()) - 1.0) < 1e-5

    def inject_masking():
        orig = BM.masked_log_softmax
        BM.masked_log_softmax = lambda logits, mask: torch.log_softmax(logits, dim=-1)
        return orig

    checks.append(Check(
        "BYTERL_MASK_INSIDE_DISTRIBUTION",
        "masking after sampling leaves probability mass on illegal actions",
        "illegal options must carry exactly zero probability",
        probe_masking, inject_masking,
        lambda o: setattr(BM, "masked_log_softmax", o)))

    # ---------------------------------------------------------------- multi-select joint logp
    def probe_joint_logp() -> bool:
        net = BM.fresh(24, 35, 28, 52, width=64, blocks=1, seed=0)
        h = torch.randn(1, 64)
        o = torch.randn(1, 20, 28)
        legal = torch.ones(1, 20)
        chosen, sampled = net.sample_select(h, o, legal, 3, 3)
        if len(chosen) != 3:
            return False
        recomputed = float(net.select_logprob(h, o, legal, chosen))
        # a single-pick score would be one conditional, not the sum of three
        single = float(BM.masked_log_softmax(net.battle_logits(h, o), legal)[0, chosen[0]])
        return abs(recomputed - sampled) < 1e-4 and abs(recomputed - single) > 1e-3

    def inject_joint_logp():
        orig = BM.ByteRLNet.select_logprob

        def single_only(self, h, options, legal, chosen):     # the c019/c020 defect
            return BM.masked_log_softmax(self.battle_logits(h, options), legal)[0, chosen[0]]
        BM.ByteRLNet.select_logprob = single_only
        return orig

    checks.append(Check(
        "BYTERL_AUTOREGRESSIVE_MULTISELECT",
        "c019/c020 scored a k-element select as a single pick, biasing every V-trace ratio",
        "the joint log-probability must be the sum of per-element conditionals",
        probe_joint_logp, inject_joint_logp,
        lambda o: setattr(BM.ByteRLNet, "select_logprob", o)))

    # ---------------------------------------------------------------- V-trace
    def probe_vtrace() -> bool:
        lp = torch.zeros(4)
        r = torch.tensor([0., 0., 0., 1.])
        out = BL.vtrace(lp, lp, r, torch.zeros(4), torch.tensor(0.), torch.ones(4))
        mc_ok = torch.allclose(out.vs, torch.ones(4))
        big = BL.vtrace(torch.full((3,), -5.), torch.zeros(3), torch.zeros(3),
                        torch.zeros(3), torch.tensor(0.), torch.ones(3),
                        rho_bar=1.0, c_bar=1.0)
        clip_ok = torch.allclose(big.clipped_rho, torch.ones(3))
        return bool(mc_ok and clip_ok)

    def inject_vtrace():
        orig = BL.vtrace

        def unclipped(behaviour_logp, target_logp, rewards, values, bootstrap_value,
                      discounts, rho_bar=1.0, c_bar=1.0):
            return orig(behaviour_logp, target_logp, rewards, values, bootstrap_value,
                        discounts, rho_bar=1e9, c_bar=1e9)
        BL.vtrace = unclipped
        return orig

    checks.append(Check(
        "BYTERL_VTRACE_CLIPS",
        "V-trace without rho-bar/c-bar clipping is not V-trace",
        "importance ratios must be clipped at rho_bar and c_bar",
        probe_vtrace, inject_vtrace, lambda o: setattr(BL, "vtrace", o)))

    # ---------------------------------------------------------------- UPGO
    def probe_upgo() -> bool:
        g = BL.upgo_returns(torch.zeros(3), torch.tensor([0., 5., 0.]),
                            torch.tensor(0.), torch.ones(3))
        cut = abs(float(g[0]) - 5.0) < 1e-6            # cuts to the baseline
        g2 = BL.upgo_returns(torch.tensor([0., 0., 1.]), torch.zeros(3),
                             torch.tensor(0.), torch.ones(3))
        follow = abs(float(g2[0]) - 1.0) < 1e-6        # follows when outperforming
        return cut and follow

    def inject_upgo():
        orig = BL.upgo_returns

        def monte_carlo(rewards, values, bootstrap_value, discounts):
            out, g = [], bootstrap_value
            for t in range(values.shape[0] - 1, -1, -1):
                g = rewards[t] + discounts[t] * g       # never cuts to the baseline
                out.append(g)
            return torch.stack(out[::-1], dim=0)
        BL.upgo_returns = monte_carlo
        return orig

    checks.append(Check(
        "BYTERL_UPGO_CUTS_TO_BASELINE",
        "UPGO that always follows the trajectory is plain Monte-Carlo",
        "the return must bootstrap from V when the one-step return underperforms it",
        probe_upgo, inject_upgo, lambda o: setattr(BL, "upgo_returns", o)))

    # ---------------------------------------------------------------- OSFP period-local
    def probe_osfp() -> bool:
        o = BL.OSFP()
        o.add_checkpoint({}, "ck0")
        o.record(0, 1.0)
        o.reset_period()
        return o.G == {} and o.C == {} and o.mean_payoff(0) == 0.0

    def inject_osfp():
        orig = BL.OSFP.reset_period
        BL.OSFP.reset_period = lambda self: setattr(self, "period", self.period + 1)
        return orig

    checks.append(Check(
        "BYTERL_OSFP_PERIOD_LOCAL",
        "c019/c020 accumulated OSFP payoffs globally across all periods",
        "G and C must be cleared at each promotion",
        probe_osfp, inject_osfp, lambda o: setattr(BL.OSFP, "reset_period", o)))

    def probe_osfp_promote() -> bool:
        o = BL.OSFP()
        return (not o.should_promote(0.9, games=10, min_games=200)
                and not o.should_promote(0.5, games=1000, min_games=200)
                and o.should_promote(0.6, games=1000, min_games=200))

    def inject_osfp_promote():
        orig = BL.OSFP.should_promote
        BL.OSFP.should_promote = (
            lambda self, win_rate, games, threshold=0.55, min_games=200:
            games >= games and win_rate >= 0.0)      # the disabled-guard defect
        return orig

    checks.append(Check(
        "BYTERL_OSFP_PROMOTION_GUARD",
        "c021: min_games was passed len(done), making the guard always true",
        "promotion needs both a win-rate threshold and a real sample-size floor",
        probe_osfp_promote, inject_osfp_promote,
        lambda o: setattr(BL.OSFP, "should_promote", o)))

    # ---------------------------------------------------------------- fresh weights
    def probe_fresh_weights() -> bool:
        a = BM.fresh(24, 35, 28, 52, width=32, blocks=1, seed=1)
        b = BM.fresh(24, 35, 28, 52, width=32, blocks=1, seed=1)
        c = BM.fresh(24, 35, 28, 52, width=32, blocks=1, seed=2)
        same = all(torch.equal(x, y) for x, y in
                   zip(a.state_dict().values(), b.state_dict().values()))
        diff = any(not torch.equal(x, y) for x, y in
                   zip(a.state_dict().values(), c.state_dict().values()))
        return same and diff

    def inject_fresh_weights():
        orig = BM.fresh
        BM.fresh = lambda *a, **k: orig(*a, **{**k, "seed": 0})   # seed ignored
        return orig

    checks.append(Check(
        "BYTERL_FRESH_RANDOM_WEIGHTS",
        "B1/B3: ByteRL must start from fresh random weights, seeded reproducibly",
        "the same seed must reproduce weights and different seeds must not",
        probe_fresh_weights, inject_fresh_weights, lambda o: setattr(BM, "fresh", o)))

    # ---------------------------------------------------------------- Finalise under UCD
    def probe_finalise_ucd() -> bool:
        st = S.new_stats()
        root, a = G.Node(), G.Node()
        G.Edge.connect(root, a, 0)
        G.Edge.connect(root, G.Node(), 1)
        win = G.Node(is_terminal=True, play_state="WON")
        e = G.Edge.connect(a, win, 0)
        win.last_traversed_edge = e
        G.backup_ucd(win, 1.0, G.UCDParams(1, 0), st)
        return st["finalised"] >= 1 and len(a.outgoing_edges) == 1

    def inject_finalise_ucd():
        orig = G.Node.finalise
        G.Node.finalise = lambda self: False        # lethal-sequence collapse disabled
        return orig

    checks.append(Check(
        "MCGS_FINALISE_RUNS_UNDER_UCD",
        "c021: BackupUCD omitted the Finalise block, so with UCD active it was dead code",
        "a proven win must collapse its parent onto the winning edge during a UCD backup",
        probe_finalise_ucd, inject_finalise_ucd,
        lambda o: setattr(G.Node, "finalise", o)))

    # ---------------------------------------------------------------- PIMC flag
    def probe_pimc() -> bool:
        return G.PIMC is False

    def inject_pimc():
        orig = G.PIMC
        G.PIMC = True
        return orig

    checks.append(Check(
        "MCGS_PIMC_STAYS_FALSE",
        "PIMC also gates a reward sign flip, Node.Finalise and the END_TURN expansion path",
        "the port runs the !PIMC configuration",
        probe_pimc, inject_pimc, lambda o: setattr(G, "PIMC", o)))

    return checks


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(VAL, "semantic_validation.json"))
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    checks = build_checks()
    results = []
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        for c in checks:
            results.append(c.run())

    n = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    inert = [r["id"] for r in results if r["status"] == "INERT"]
    failed = [r["id"] for r in results if r["status"] == "FAIL"]
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "total": n, "passed": passed,
           "inert": inert, "failed": failed,
           "all_checks_detect_their_defect": passed == n,
           "checks": results}
    json.dump(out, open(a.out, "w"), indent=2)

    print(f"semantic validation: {passed}/{n} checks pass "
          f"(clean PASS and injected FAIL)")
    for r in results:
        flag = {"PASS": "ok  ", "INERT": "INERT", "FAIL": "FAIL"}[r["status"]]
        print(f"  [{flag}] {r['id']}")
        if r["status"] != "PASS":
            print(f"          clean={r.get('clean_pass')} injected={r.get('injected_pass')} "
                  f"{r.get('clean_error', '')}{r.get('inject_error', '')}")
    if inert:
        print(f"INERT (cannot detect their own defect): {inert}")
    if failed:
        print(f"FAILED: {failed}")
    return 0 if passed == n else 1


if __name__ == "__main__":
    raise SystemExit(main())

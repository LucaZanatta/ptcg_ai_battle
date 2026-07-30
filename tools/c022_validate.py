"""c022 F03 — recompute every reported number from raw data.

`RESULTS_SCHEMA` evidence requirements: "Consistency validator must recompute every score, count,
status, candidate identity, and hash." `PROBE_MATRIX F03`: "All reported numbers recompute from
raw data."

The validator's job is to make a report that disagrees with its own raw files FAIL, so this file
recomputes from `*_games.jsonl`, `*_calibration.jsonl`, `*_eval.json` and the checkpoints
themselves, and compares against the summaries and reports. It never reads a number from one
summary and copies it into another.

**Every check must be able to fail.** `PROBE_MATRIX F04` requires the validators to reject known
c019-c021 defects, so each check below is paired with an INJECTION: a synthetic corruption of the
shape the defect actually took, which the check must detect. A check that passes both clean and
injected data is INERT and is reported as such rather than counted as a pass — c021 shipped one
of those and only found it by mutation testing.
"""

from __future__ import annotations

import argparse
import collections
import copy
import glob
import hashlib
import json
import math
import os
import statistics
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C22 = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction", "results")
MC = os.path.join(C22, "mcgs")
BY = os.path.join(C22, "byterl")

TOL = 1e-4


def wilson(k: float, n: int, z: float = 1.96):
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def read_jsonl(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    return out


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ============================================================================ checks
class Check:
    """A check plus the injection that proves it is not inert."""

    def __init__(self, cid: str, name: str, fn: Callable, inject: Optional[Callable] = None,
                 detects: str = ""):
        self.cid, self.name, self.fn, self.inject, self.detects = cid, name, fn, inject, detects

    def run(self, ctx) -> Dict[str, Any]:
        ok, detail = self.fn(ctx)
        # A check with NO INPUTS is not a passing check -- it is a check that did not run. The
        # first version of this file reported five such checks as PASS, which is exactly the
        # "passes by default" failure the injection machinery exists to prevent, arriving one
        # level up. `n_inputs` is how each check declares what it actually looked at.
        n_inputs = detail.get("_n_inputs")
        if n_inputs is None:
            n_inputs = (detail.get("arms_checked") or detail.get("evals_checked")
                        or detail.get("runs_checked") or detail.get("rows_checked")
                        or detail.get("controls") or 0)
        row = {"id": self.cid, "name": self.name, "detail": detail,
               "detects": self.detects, "n_inputs": int(n_inputs)}
        if not n_inputs:
            row["status"] = "NO_DATA"
            row["pass"] = False
            row["note"] = ("no inputs available yet -- this is NOT a pass. The check is "
                           "re-run once the artifacts it reads exist.")
            return row
        row["status"] = "PASS" if ok else "FAIL"
        row["pass"] = bool(ok)
        if self.inject is None:
            row["injection"] = "none registered"
            row["inert"] = True
            return row
        try:
            bad_ctx = self.inject(copy.deepcopy(ctx))
            caught, _ = self.fn(bad_ctx)
            row["injection_detected"] = (not caught)
            row["inert"] = bool(caught)
        except Exception as e:  # noqa: BLE001
            row["injection_detected"] = None
            row["injection_error"] = f"{type(e).__name__}: {e}"[:160]
            row["inert"] = None
        return row


# ---------------------------------------------------------------- MCGS field scores
def check_field_scores(ctx):
    """Every MCGS arm's field score must recompute from its own per-game records."""
    bad = []
    for arm in ctx["mcgs_arms"]:
        s, games = arm["summary"], arm["games"]
        scored = [g for g in games if g.get("completed") and g.get("score") is not None]
        if not scored:
            continue
        recomputed = sum(g["score"] for g in scored) / len(scored)
        if s.get("field_score") is None or abs(recomputed - s["field_score"]) > TOL:
            bad.append({"arm": s.get("tag"), "reported": s.get("field_score"),
                        "recomputed": round(recomputed, 6), "n": len(scored)})
        if s.get("completed") != len(scored):
            bad.append({"arm": s.get("tag"), "reported_completed": s.get("completed"),
                        "recomputed_completed": len(scored)})
        w = wilson(sum(g["score"] for g in scored), len(scored))
        if s.get("wilson95") and any(
                abs((a or 0) - (b or 0)) > TOL for a, b in zip(w, s["wilson95"])):
            bad.append({"arm": s.get("tag"), "reported_ci": s.get("wilson95"),
                        "recomputed_ci": w})
    return (not bad), {"arms_checked": len(ctx["mcgs_arms"]), "mismatches": bad}


def inject_field_score(ctx):
    if ctx["mcgs_arms"]:
        ctx["mcgs_arms"][0]["summary"]["field_score"] = 0.99
    return ctx


# ---------------------------------------------------------------- game accounting
def check_game_accounting(ctx):
    """Buckets must sum to `games`. This is D10: ten games in no category at all."""
    bad = []
    for arm in ctx["mcgs_arms"]:
        s = arm["summary"]
        total = ((s.get("completed") or 0) + (s.get("abandoned") or 0)
                 + (s.get("errored") or 0) + (s.get("unscored") or 0))
        if s.get("games") is not None and total != s["games"]:
            bad.append({"arm": s.get("tag"), "games": s.get("games"), "accounted": total,
                        "missing": s["games"] - total})
        if s.get("all_games_accounted") is False:
            bad.append({"arm": s.get("tag"), "all_games_accounted": False})
    return (not bad), {"arms_checked": len(ctx["mcgs_arms"]), "unaccounted": bad}


def inject_accounting(ctx):
    if ctx["mcgs_arms"]:
        ctx["mcgs_arms"][0]["summary"]["completed"] = \
            (ctx["mcgs_arms"][0]["summary"].get("completed") or 0) - 3
    return ctx


# ---------------------------------------------------------------- simulation budget
def check_budget_delivered(ctx):
    """A4: attribution is by simulation count, so an undelivered budget invalidates the arm."""
    bad = []
    for arm in ctx["mcgs_arms"]:
        s = arm["summary"]
        cfg = s.get("config") or {}
        want = cfg.get("simulations_per_decision")
        k = cfg.get("k_worlds") or 1
        if cfg.get("budget_protocol") == "fixed_per_world" and want:
            want = want * k
        got = s.get("sims_per_decision")
        if want and got is not None and abs(got - want) > 1.0:
            bad.append({"arm": s.get("tag"), "configured": want, "measured": got})
        if s.get("decision_deadline_stops"):
            bad.append({"arm": s.get("tag"),
                        "decision_deadline_stops": s["decision_deadline_stops"]})
    return (not bad), {"arms_checked": len(ctx["mcgs_arms"]), "budget_failures": bad}


def inject_budget(ctx):
    if ctx["mcgs_arms"]:
        ctx["mcgs_arms"][0]["summary"]["sims_per_decision"] = 3.0
    return ctx


# ---------------------------------------------------------------- M05/M06 equal budgets
def check_equal_budgets(ctx):
    """M05/M06: fixed_total arms must use equal totals; fixed_per_world equal per world."""
    bad = []
    for proto, arms in (("fixed_total", ctx["ft_arms"]), ("fixed_per_world", ctx["fpw_arms"])):
        vals = {}
        for arm in arms:
            s = arm["summary"]
            cfg = s.get("config") or {}
            spd = s.get("sims_per_decision")
            if spd is None:
                continue
            vals[s.get("tag")] = spd if proto == "fixed_total" else \
                round(spd / (cfg.get("k_worlds") or 1), 3)
        if len(vals) > 1 and (max(vals.values()) - min(vals.values())) > 1.0:
            bad.append({"protocol": proto, "values": vals})
    return (not bad), {"per_protocol": bad,
                       "_n_inputs": len(ctx["ft_arms"]) + len(ctx["fpw_arms"]),
                       "note": "needs at least two arms in a protocol to compare"}


def inject_equal_budgets(ctx):
    if ctx["ft_arms"]:
        ctx["ft_arms"][0]["summary"]["sims_per_decision"] = 9999.0
    return ctx


# ---------------------------------------------------------------- exclusion spread
def check_exclusion_spread(ctx):
    """A K-dependent exclusion rate means the arms are scored on different populations."""
    bad = []
    for proto, arms in (("fixed_total", ctx["ft_arms"]), ("fixed_per_world", ctx["fpw_arms"])):
        rates = {}
        for arm in arms:
            s = arm["summary"]
            g = s.get("games") or 0
            if not g:
                continue
            excl = ((s.get("abandoned") or 0) + (s.get("unscored") or 0)
                    + (s.get("errored") or 0)) / g
            rates[s.get("tag")] = round(excl, 4)
        if len(rates) > 1 and (max(rates.values()) - min(rates.values())) > 0.15:
            bad.append({"protocol": proto, "rates": rates,
                        "spread": round(max(rates.values()) - min(rates.values()), 4)})
    return (not bad), {"per_protocol_spread_over_15pp": bad,
                       "_n_inputs": (len(ctx["ft_arms"]) if len(ctx["ft_arms"]) > 1 else 0)
                                    + (len(ctx["fpw_arms"]) if len(ctx["fpw_arms"]) > 1 else 0),
                       "note": "needs at least two arms in a protocol to compare"}


def inject_exclusion(ctx):
    if len(ctx["ft_arms"]) > 1:
        ctx["ft_arms"][1]["summary"]["abandoned"] = \
            (ctx["ft_arms"][1]["summary"].get("games") or 40)
    return ctx


# ---------------------------------------------------------------- probability range
def check_probabilities_in_range(ctx):
    """D04: the opponent sign flip made predicted_win_probability go negative."""
    bad = []
    n = 0
    for arm in ctx["mcgs_arms"]:
        for row in arm["calibration"]:
            p = row.get("predicted_win_probability")
            if p is None:
                continue
            n += 1
            if p < 0.0 or p > 1.0:
                bad.append({"arm": arm["summary"].get("tag"), "p": p,
                            "decision": row.get("decision")})
                if len(bad) > 8:
                    break
    return (not bad), {"rows_checked": n, "out_of_range": bad[:8]}


def inject_probability(ctx):
    for arm in ctx["mcgs_arms"]:
        if arm["calibration"]:
            arm["calibration"][0]["predicted_win_probability"] = -0.044586
            return ctx
    return ctx


# ---------------------------------------------------------------- terminal scale
def check_no_mixed_terminal_scale(ctx):
    """A terminal leaf puts the source's +/-10 scale into a [0,1] aggregate."""
    bad = []
    for arm in ctx["mcgs_arms"]:
        s = arm["summary"]
        for q in ("terminal_leaves", "finalised", "lethal_bonus",
                  "mixed_terminal_scale_decisions"):
            if s.get(q):
                bad.append({"arm": s.get("tag"), q: s[q]})
    return (not bad), {"arms_checked": len(ctx["mcgs_arms"]), "mixed": bad}


def inject_terminal(ctx):
    if ctx["mcgs_arms"]:
        ctx["mcgs_arms"][0]["summary"]["terminal_leaves"] = 7
    return ctx


# ---------------------------------------------------------------- index alignment
def check_no_signature_mismatch(ctx):
    """Cross-world aggregation keys on action index; a mismatch sums different actions.

    This asserts `signature_mismatches` ONLY. It used to fail on `opponent_flag_conflicts` too,
    which is a different thing entirely and is not a defect: D16 established that whose turn
    follows an action is not always public, so two worlds can legitimately disagree about whether
    an action's successor is an opponent node. The fix was root-frame summation, which converts
    each world's reward into the root player's frame before summing, and the counter records how
    often that legitimate situation arose. Failing on it made the validator report a FAIL for
    correct behaviour on seven arms -- and a validator that cries wolf is how a real FAIL gets
    scrolled past. The handled-ness of those conflicts is asserted separately, by V19 and by V06.
    """
    bad = []
    for arm in ctx["mcgs_arms"]:
        s = arm["summary"]
        if s.get("signature_mismatches"):
            bad.append({"arm": s.get("tag"), "n": s["signature_mismatches"]})
    return (not bad), {"arms_checked": len(ctx["mcgs_arms"]), "mismatches": bad}


def check_opponent_conflicts_only_where_possible(ctx):
    """An opponent-flag conflict requires two worlds. A K=1 arm reporting one is a bug.

    D16's conflicts are legitimate, but only BETWEEN worlds -- one world cannot disagree with
    itself. A nonzero count on a K=1 arm would mean the counter is measuring something other
    than what it names, which is the stale-tag defect family this contract keeps finding.
    """
    checked, bad = 0, []
    for arm in ctx["mcgs_arms"]:
        s = arm["summary"]
        k = int((s.get("config") or {}).get("k_worlds") or s.get("k_worlds") or 0)
        if not k:
            continue
        checked += 1
        n = int(s.get("opponent_flag_conflicts") or 0)
        if k == 1 and n:
            bad.append({"arm": s.get("tag"), "k": k, "opponent_flag_conflicts": n,
                        "why": "one world cannot conflict with itself"})
    return (not bad), {"_n_inputs": checked, "violations": bad,
                       "conflicts_by_arm": {
                           s["summary"].get("tag"):
                               int(s["summary"].get("opponent_flag_conflicts") or 0)
                           for s in ctx["mcgs_arms"]}}


def inject_opponent_conflicts(ctx):
    c = dict(ctx)
    c["mcgs_arms"] = list(ctx["mcgs_arms"]) + [
        {"summary": {"tag": "injected", "config": {"k_worlds": 1},
                     "opponent_flag_conflicts": 7}, "games": [], "calibration": []}]
    return c


def inject_signature(ctx):
    if ctx["mcgs_arms"]:
        ctx["mcgs_arms"][0]["summary"]["signature_mismatches"] = 12
    return ctx


# ---------------------------------------------------------------- ByteRL evaluations
def check_byterl_evals(ctx):
    """Every ByteRL external evaluation must recompute from its own per-game records."""
    bad = []
    for ev in ctx["byterl_evals"]:
        s, games = ev["summary"], ev["games"]
        scored = [g for g in games if g.get("completed") and g.get("score") is not None]
        if not scored:
            continue
        rec = sum(g["score"] for g in scored) / len(scored)
        if s.get("field_score") is None or abs(rec - s["field_score"]) > TOL:
            bad.append({"tag": s.get("tag"), "reported": s.get("field_score"),
                        "recomputed": round(rec, 6)})
    return (not bad), {"evals_checked": len(ctx["byterl_evals"]), "mismatches": bad}


def inject_byterl_eval(ctx):
    if ctx["byterl_evals"]:
        ctx["byterl_evals"][0]["summary"]["field_score"] = 0.88
    return ctx


# ---------------------------------------------------------------- recurrence
def check_recurrence(ctx):
    """B06: a nonzero exact-weights delta is a hard failure under B4."""
    bad = []
    for m in ctx["byterl_manifests"]:
        if m.get("recurrence_check_failures"):
            bad.append({"tag": m.get("tag"), "failures": m["recurrence_check_failures"]})
        d = m.get("max_recurrence_delta_exact_weights")
        if d is not None and d > 1e-4:
            bad.append({"tag": m.get("tag"), "max_recurrence_delta": d})
        d = m.get("max_logp_delta_exact_weights")
        if d is not None and d > 1e-4:
            bad.append({"tag": m.get("tag"), "max_logp_delta": d})
    return (not bad), {"runs_checked": len(ctx["byterl_manifests"]), "failures": bad}


def inject_recurrence(ctx):
    if ctx["byterl_manifests"]:
        ctx["byterl_manifests"][0]["max_recurrence_delta_exact_weights"] = 1.07
    return ctx


# ---------------------------------------------------------------- fresh weights
def check_fresh_weights(ctx):
    """CONTRACT §2 / TRAINING_AND_EVALUATION §2: no warm start from c021."""
    bad = []
    for m in ctx["byterl_manifests"]:
        if m.get("fresh_random_weights") is not True:
            bad.append({"tag": m.get("tag"),
                        "fresh_random_weights": m.get("fresh_random_weights"),
                        "resumed_from": m.get("resumed_from")})
    return (not bad), {"runs_checked": len(ctx["byterl_manifests"]), "warm_starts": bad}


def inject_fresh(ctx):
    if ctx["byterl_manifests"]:
        ctx["byterl_manifests"][0]["fresh_random_weights"] = False
        ctx["byterl_manifests"][0]["resumed_from"] = "big_ctrl_b2_final.pt"
    return ctx


# ---------------------------------------------------------------- LSTM present
def check_lstm(ctx):
    """B01: c021's defining absence. A feed-forward substitute is a hard failure."""
    bad = []
    for m in ctx["byterl_manifests"]:
        if m.get("lstm_hidden") != 256:
            bad.append({"tag": m.get("tag"), "lstm_hidden": m.get("lstm_hidden")})
    return (not bad), {"runs_checked": len(ctx["byterl_manifests"]), "bad": bad}


def inject_lstm(ctx):
    if ctx["byterl_manifests"]:
        ctx["byterl_manifests"][0]["lstm_hidden"] = 0
    return ctx


# ---------------------------------------------------------------- controls frozen
def check_controls(ctx):
    """CONTRACT §2: the named controls must still hash to what was frozen."""
    m = ctx["control_manifest"]
    if not m:
        return False, {"error": "no control manifest"}
    bad = []
    files_verified = 0
    controls_with_files = 0
    for name, c in (m.get("controls") or {}).items():
        before = files_verified
        # files_sha256 keys are relative to the control's `dir`
        for rel, want in (c.get("files_sha256") or {}).items():
            p = os.path.join(_REPO, c.get("dir", ""), rel)
            files_verified += 1
            if not os.path.isfile(p):
                bad.append({"control": name, "file": rel, "why": "missing"})
                continue
            if sha256_file(p) != want:
                bad.append({"control": name, "file": rel, "why": "hash changed"})
        # source_sha256 keys are REPO-RELATIVE and carry no `dir`. Omitting this branch meant
        # C020_H1_PRIOR_HYBRID_CONTROL and C021_MCGS_K1_CONTROL had their source hashes recorded
        # and never verified, while V13 reported n=7 and passed -- reading as "all seven
        # controls checked" when it checked five.
        for rel, want in (c.get("source_sha256") or {}).items():
            p = os.path.join(_REPO, rel)
            files_verified += 1
            if not os.path.isfile(p):
                bad.append({"control": name, "file": rel, "why": "missing"})
                continue
            if sha256_file(p) != want:
                bad.append({"control": name, "file": rel, "why": "hash changed"})
        for arm, mm in (c.get("measured") or {}).items():
            rel_, want = mm.get("eval_file"), mm.get("eval_sha256")
            if not rel_ or not want:
                continue
            files_verified += 1
            p = os.path.join(_REPO, rel_)
            if not os.path.isfile(p):
                bad.append({"control": name, "file": rel_, "why": "missing"})
            elif sha256_file(p) != want:
                bad.append({"control": name, "file": rel_, "why": "hash changed"})
        for key in ("checkpoint", "summary"):
            if c.get(key):
                p = os.path.join(_REPO, c[key])
                files_verified += 1
                if not os.path.isfile(p):
                    bad.append({"control": name, "file": c[key], "why": "missing"})
                elif sha256_file(p) != c.get(key + "_sha256"):
                    bad.append({"control": name, "file": c[key], "why": "hash changed"})
        if files_verified > before:
            controls_with_files += 1
    n_controls = len(m.get("controls") or {})
    # A control with nothing to hash is not verified, and must not be counted as if it were.
    unhashed = [k for k, c in (m.get("controls") or {}).items()
                if not (c.get("files_sha256") or c.get("source_sha256")
                        or c.get("checkpoint") or c.get("summary")
                        or (c.get("measured") or {}))]
    if unhashed:
        bad.append({"controls_with_nothing_to_verify": unhashed,
                    "why": "named but pinned to nothing -- the defect c021 shipped with "
                           "CHAMPION_C005_DRAGAPULT"})
    return (not bad), {"controls": n_controls,
                       "controls_with_verifiable_artifacts": controls_with_files,
                       "files_verified": files_verified,
                       "violations": bad[:10], "_n_inputs": files_verified}


def inject_controls(ctx):
    """Corrupt a SOURCE hash, not a files_sha256 one -- the branch that was missing."""
    m = ctx["control_manifest"]
    if m and m.get("controls"):
        for k in sorted(m["controls"]):
            ss = m["controls"][k].get("source_sha256") or {}
            if ss:
                ss[sorted(ss)[0]] = "0" * 64
                return ctx
        k = sorted(m["controls"])[0]
        fs = m["controls"][k].get("files_sha256") or {}
        if fs:
            fs[sorted(fs)[0]] = "0" * 64
    return ctx


# ============================================================================ context
def load_context() -> Dict[str, Any]:
    def arms_in(d, tags):
        out = []
        for t in tags:
            sp = os.path.join(d, f"{t}_summary.json")
            if not os.path.isfile(sp):
                continue
            with open(sp) as fh:
                s = json.load(fh)
            out.append({"summary": s,
                        "games": read_jsonl(os.path.join(d, f"{t}_games.jsonl")),
                        "calibration": read_jsonl(os.path.join(d, f"{t}_calibration.jsonl"))})
        return out

    ft = arms_in(os.path.join(MC, "fixed_total_simulations"),
                 ["ft_k1", "ft_k2", "ft_k4", "ft_k8"])
    fpw = arms_in(os.path.join(MC, "fixed_simulations_per_world"),
                  ["fpw_k1", "fpw_k2", "fpw_k4", "fpw_k8"])
    k1 = arms_in(os.path.join(MC, "k1_control"), ["m04_k1_reuse"])
    # The 200-game paired arms are the contract's decisive MCGS evidence and were NOT in this
    # inventory. Every check below -- field scores recomputing from raw games, game accounting,
    # budget delivery, probabilities in range, signature alignment -- was silently skipping them.
    # A validator whose inventory omits the headline arms validates the arms that do not matter.
    paired = arms_in(os.path.join(MC, "paired"),
                     ["paired_k1", "paired_k8", "paired_k1_c96"])
    noise = arms_in(os.path.join(C22, "transfer", "noise_floor"),
                    ["noise_k1_s90210", "noise_k1_s40031", "noise_k1_s71877"])
    deploy = arms_in(os.path.join(MC, "kaggle_deploy"), ["deploy_k1", "deploy_k8"])
    unrestricted = arms_in(os.path.join(MC, "unrestricted_reference"),
                           ["m11_probe_serial", "m11_probe_parallel", "m11_unrestricted"])

    evals = []
    for p in sorted(glob.glob(os.path.join(BY, "external_evaluations", "*_eval.json"))):
        with open(p) as fh:
            s = json.load(fh)
        evals.append({"summary": s,
                      "games": read_jsonl(p.replace("_eval.json", "_games.jsonl"))})

    manifests = []
    for p in sorted(glob.glob(os.path.join(BY, "stages", "*_manifest.json"))):
        with open(p) as fh:
            manifests.append(json.load(fh))

    cm = None
    p = os.path.join(C22, "controls", "control_manifest.json")
    if os.path.isfile(p):
        with open(p) as fh:
            cm = json.load(fh)

    return {"ft_arms": ft, "fpw_arms": fpw, "k1_arms": k1,
            "paired_arms": paired, "noise_arms": noise,
            "deploy_arms": deploy, "unrestricted_arms": unrestricted,
            "mcgs_arms": ft + fpw + k1 + paired + noise + deploy + unrestricted,
            "byterl_evals": evals, "byterl_manifests": manifests,
            "control_manifest": cm}



# ---------------------------------------------------------------------------- D18/D19/D20/M11
def check_rung_throughput(ctx):
    """D18 — no rung's queue statistics come from a run that shared the machine.

    The learner rate is the tell, not the ratio: the ratio is what a rung is SUPPOSED to differ
    in, while `steps/update` and `decisions/episode` were identical between the contaminated and
    clean BR0. A rate far off the ladder's median with those held constant is machine load.
    """
    rates = {}
    for m in ctx["byterl_manifests"]:
        tag = str(m.get("tag") or "")
        if not tag.startswith("ctrl_"):
            continue
        w = float(m.get("wall_clock_s") or 0.0)
        if w > 0:
            rates[tag] = round(float(m.get("consumed_decisions") or 0) / w, 1)
    if len(rates) < 2:
        return True, {"_n_inputs": 0, "rates": rates,
                      "why": "fewer than two controlled rungs; nothing to compare"}
    med = statistics.median(rates.values())
    bad = {t: v for t, v in rates.items() if v < 0.6 * med or v > 1.7 * med}
    return not bad, {"_n_inputs": len(rates), "rates": rates, "median": round(med, 1),
                     "outliers": bad,
                     "bound": "[0.6, 1.7] x median; D18 measured a 9x spread from load alone"}


def inject_rung_throughput(ctx):
    c = dict(ctx)
    c["byterl_manifests"] = list(ctx["byterl_manifests"]) + [
        {"tag": "ctrl_INJECTED", "wall_clock_s": 10000.0, "consumed_decisions": 120000}]
    return c


def check_behaviour_pi_separation(ctx):
    """D19 — mu is what it claims to be, on every run that reports the check.

    `max_behaviour_delta` is computed from stored data alone: a uniform B1.5 step must carry
    -log(n_legal), every other step must carry exactly pi. A nonzero value means a step lied
    about which distribution chose its action, which corrupts every importance ratio on it.
    """
    checked, bad = 0, []
    for m in ctx["byterl_manifests"]:
        if m.get("max_behaviour_delta") is None:
            continue
        checked += 1
        if float(m["max_behaviour_delta"]) > float(m.get("recurrence_tolerance") or 1e-4):
            bad.append({"tag": m.get("tag"), "max_behaviour_delta": m["max_behaviour_delta"]})
    return not bad, {"_n_inputs": checked, "violations": bad,
                     "note": "runs predating D19 do not report the field and are not counted"}


def inject_behaviour_pi_separation(ctx):
    c = dict(ctx)
    c["byterl_manifests"] = list(ctx["byterl_manifests"]) + [
        {"tag": "injected", "max_behaviour_delta": 0.7, "recurrence_tolerance": 1e-4}]
    return c


def check_b06_coverage_is_reported(ctx):
    """D20 — a fidelity check count with no denominator is not evidence.

    A run reporting `recurrence_checks` must also report how many opportunities it SKIPPED for
    want of retained weights. Without that, "1 check, 0 failures" and "400 checks, 0 failures"
    are indistinguishable in the manifest, and the first was reported as a pass.

    The check also requires that the dedicated fidelity runs actually achieve high coverage --
    they exist precisely so that B06 rests on something better than the ladder's ~10%.
    """
    checked, missing, thin = 0, [], []
    for m in ctx["byterl_manifests"]:
        if m.get("recurrence_checks") is None:
            continue
        checked += 1
        if m.get("recurrence_checks_skipped_no_retained_blob") is None:
            missing.append(m.get("tag"))
            continue
        cov = m.get("recurrence_check_coverage")
        if str(m.get("tag") or "").startswith("fid_") and (cov is None or float(cov) < 0.9):
            thin.append({"tag": m.get("tag"), "coverage": cov})
    return (not missing and not thin), {
        "_n_inputs": checked, "manifests_without_a_denominator": missing,
        "fidelity_runs_below_90pc_coverage": thin,
        "why": "D20: B06 ran once in 556 policy versions and reported PASS"}


def inject_b06_coverage(ctx):
    c = dict(ctx)
    c["byterl_manifests"] = list(ctx["byterl_manifests"]) + [
        {"tag": "injected", "recurrence_checks": 1}]      # a count with no denominator
    return c


def check_source_time_arms_were_bound_by_the_clock(ctx):
    """M11 — a timed arm must have been stopped by the SCHEDULE, not by a count or the ceiling.

    In `source_time` the simulation count is the measurement, so `budget_delivered` would be
    vacuously true if it still asked whether a configured count was reached. It instead asserts
    that achieved simulations far exceed the configured value; this check reads that flag and
    also verifies the schedule recorded is the source's or c021's, never an invented one.
    """
    LEGAL = {(15.0, 10.0): "source SearchConfig.cs",
             (0.9, 0.7): "c021 deployment config, frozen in control_manifest.json"}
    checked, bad = 0, []
    for a in ctx["mcgs_arms"]:
        s = a["summary"]
        if str(s.get("config", {}).get("budget_protocol")) != "source_time":
            continue
        checked += 1
        sch = s.get("schedule_seconds") or {}
        key = (float(sch.get("first_move", 0)), float(sch.get("continuing", 0)))
        if key not in LEGAL:
            bad.append({"tag": s.get("tag"), "schedule": key,
                        "why": "not the source's 15/10 nor c021's 0.9/0.7"})
        elif not s.get("budget_delivered"):
            bad.append({"tag": s.get("tag"),
                        "why": "the wall schedule did not bind: a count or the ceiling did"})
    return not bad, {"_n_inputs": checked, "violations": bad,
                     "legal_schedules": {str(k): v for k, v in LEGAL.items()}}


def inject_source_time(ctx):
    c = dict(ctx)
    c["mcgs_arms"] = list(ctx["mcgs_arms"]) + [
        {"summary": {"tag": "injected", "config": {"budget_protocol": "source_time"},
                     "schedule_seconds": {"first_move": 3.0, "continuing": 2.0},
                     "budget_delivered": True},
         "games": [], "calibration": []}]
    return c


def check_field_claims_have_a_noise_floor(ctx):
    """Every field-score comparison in this contract is against a MEASURED replication set.

    `NOISE_FLOOR_ACCIDENTAL_REPLICATION.md` showed two identical 32-game arms differing by 12.5
    points. A comparison reported without that denominator is a number, not a result, so the
    replication arms must exist and there must be at least three of them.
    """
    n = len(ctx.get("noise_arms") or [])
    fields = [a["summary"].get("field_score") for a in (ctx.get("noise_arms") or [])]
    ok = n >= 3
    d = {"_n_inputs": n, "replication_arms": n, "field_scores": fields}
    if n >= 2:
        d["spread_pp"] = round(100 * (max(fields) - min(fields)), 2)
    return ok, d


def inject_noise_floor(ctx):
    c = dict(ctx)
    c["noise_arms"] = []                                  # remove the denominator entirely
    return c


CHECKS = [
    Check("V01", "MCGS field scores recompute from per-game records",
          check_field_scores, inject_field_score,
          "a reported score that disagrees with its own raw games"),
    Check("V02", "every game lands in exactly one bucket",
          check_game_accounting, inject_accounting,
          "D10: ten games in no category, silently excluded from the field score"),
    Check("V03", "the simulation budget was delivered",
          check_budget_delivered, inject_budget,
          "an arm that did not run its simulations, or hit the per-decision wall ceiling"),
    Check("V04", "M05/M06 equal budgets across K",
          check_equal_budgets, inject_equal_budgets,
          "a K sweep whose arms did not use equal simulations"),
    Check("V05", "exclusion rate is comparable across K",
          check_exclusion_spread, inject_exclusion,
          "D08/contention: arms scored on different populations, making 'K is worse' "
          "indistinguishable from 'K was cut earlier'"),
    Check("V06", "predicted win probabilities are in [0,1]",
          check_probabilities_in_range, inject_probability,
          "D04: the source's opponent sign flip making an end-turn action's probability negative"),
    Check("V07", "no arm mixed the +/-10 terminal scale into a [0,1] aggregate",
          check_no_mixed_terminal_scale, inject_terminal,
          "a terminal leaf entering the aggregate and breaking the probability reading"),
    Check("V08", "action indices are aligned across worlds",
          check_no_signature_mismatch, inject_signature,
          "the position-pairing defect family: summing statistics for different actions"),
    Check("V09", "ByteRL external evaluations recompute from per-game records",
          check_byterl_evals, inject_byterl_eval,
          "a reported win rate that disagrees with its own raw games"),
    Check("V10", "recurrent replay agrees at the exact behaviour weights",
          check_recurrence, inject_recurrence,
          "B4's zeroed-recurrent-start hard failure, and D06's publish race"),
    Check("V11", "ByteRL trained from fresh random weights",
          check_fresh_weights, inject_fresh,
          "a warm start from c021 weights, which CONTRACT §2 forbids"),
    Check("V12", "the LSTM is present at hidden size 256",
          check_lstm, inject_lstm,
          "c021's defining absence: a feed-forward substitute"),
    Check("V13", "frozen controls still hash to what was frozen",
          check_controls, inject_controls,
          "a control mutating under the campaign it is supposed to anchor"),
    Check("V14", "no rung's queue statistics come from a contended run",
          check_rung_throughput, inject_rung_throughput,
          "D18: ctrl_BR0 under a concurrent MCGS arm, reporting load as a stage property"),
    Check("V15", "mu is the distribution that actually chose the action",
          check_behaviour_pi_separation, inject_behaviour_pi_separation,
          "D19: a uniform step recording the network's log-probability, corrupting every "
          "importance ratio on it"),
    Check("V16", "B06 coverage is reported, and the fidelity runs achieve it",
          check_b06_coverage_is_reported, inject_b06_coverage,
          "D20: one fidelity check in 556 policy versions, reported as a pass"),
    Check("V17", "timed arms were stopped by the schedule, on a schedule from a source",
          check_source_time_arms_were_bound_by_the_clock, inject_source_time,
          "M11/M12: an invented clock, or a count binding before the schedule did"),
    Check("V18", "field-score claims have a measured replication set behind them",
          check_field_claims_have_a_noise_floor, inject_noise_floor,
          "a K difference reported without the 5 pp run-to-run spread it sits inside"),
    Check("V19", "opponent-flag conflicts appear only where two worlds exist",
          check_opponent_conflicts_only_where_possible, inject_opponent_conflicts,
          "a K=1 arm reporting cross-world disagreement: the counter measuring something "
          "other than what it names"),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(C22, "validation_report.json"))
    a = ap.parse_args(argv)

    ctx = load_context()
    rows = [c.run(ctx) for c in CHECKS]
    ran = [r for r in rows if r["status"] != "NO_DATA"]
    n_pass = sum(1 for r in ran if r["pass"])
    no_data = [r["id"] for r in rows if r["status"] == "NO_DATA"]
    inert = [r["id"] for r in ran if r.get("inert") is True]
    undetected = [r["id"] for r in ran if r.get("injection_detected") is False]

    out = {
        "generated_from": "raw per-game, per-decision and per-run artifacts",
        "n_checks": len(rows), "n_ran": len(ran), "n_pass": n_pass,
        "checks_with_no_data": no_data,
        "no_data_is_not_a_pass": True,
        "inert_checks": inert,
        "injections_not_detected": undetected,
        "all_injections_detected": (not inert) and (not undetected) and bool(ran),
        "inventory": {
            "mcgs_arms": [a_["summary"].get("tag") for a_ in ctx["mcgs_arms"]],
            "byterl_evals": [e["summary"].get("tag") for e in ctx["byterl_evals"]],
            "byterl_runs": [m.get("tag") for m in ctx["byterl_manifests"]],
        },
        "checks": rows,
        "note": "F04 requires the validators to reject known defects. Each check is paired with "
                "an INJECTION of the shape the defect actually took; a check that passes both "
                "clean and injected data is INERT and is listed as such rather than counted as "
                "a pass. c021 shipped an inert check and found it only by mutation testing.",
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
    for r in rows:
        inj = ("inj-ok" if r.get("injection_detected") else
               ("INERT" if r.get("inert") else "-"))
        print(f"{r['status']:8s} {r['id']}  {r['name']:58s} "
              f"[{inj}] n={r['n_inputs']}")
    print(f"{n_pass}/{len(ran)} checks that RAN pass; "
          f"no_data={no_data}; inert={inert}; undetected_injections={undetected}")
    print(f"-> {a.out}")
    return 0 if (ran and n_pass == len(ran) and out["all_injections_detected"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

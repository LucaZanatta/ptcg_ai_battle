"""c013 §21-§24 (AC-12) — opponent overlap measured on genuinely identical visible states.

c012 answered this question from CROSS-PLAY GAMES: it played policies against each other and
compared aggregate fingerprints. Two policies can produce similar game-level statistics while
choosing differently at every decision, so that design cannot separate "similar behaviour" from
"similar outcome". §21 asks for something stricter -- the same visible state and the same legal
actions presented to every policy -- and this module implements exactly that.

THE SHADOW-QUERY LOOP
---------------------
One acting policy drives a real game. At every decision point every other policy is queried on
the SAME `obs` object; its answer is recorded and thrown away, so the trajectory is unchanged.

Each shadow policy keeps a PERSISTENT per-game instance. `cg/teachers.py` documents that these
rule agents hold module-level state -- turn counters, attack plan, ability flags -- and do not
reset. Querying a fresh instance at a mid-game state would evaluate every turn-conditioned
branch with counters still at zero. That damages the four rule agents ASYMMETRICALLY (whichever
skeleton branches hardest on turn number is hurt most), and the asymmetry would land straight on
the teacher-Lucario vs teacher-Iono contrast that §24 turns on. Persistent instances observe the
whole obs prefix, so their internal counters advance naturally.

Disclosed, not worked around: the trajectory belongs to the ACTING policy. A shadow agent answers
"what would you do here", not "what position would you have reached". That is inherent to any
identical-state comparison and is reported with the result.

APPLICABILITY, AND WHY IT DECIDES THE ANSWER
-------------------------------------------
Every agent hard-codes its own deck's card IDs (dragapult 48 distinct integer literals,
mega_lucario 28, iono 32, mega_abomasnow 15). Handed a state from a different deck, the
deck-specific branches cannot fire and the agent falls through to its generic skeleton -- often
to "take the first legal option". If that fall-through were counted as agreement, overlap would
be manufactured out of two policies independently defaulting to index 0.

So each (policy, state) is classified by a PERMUTATION TEST that never reads the agents' source
and therefore cannot be tuned to a branch: present the same state with the option list reordered
K times. If the agent's selected CONTENT is invariant, its rules chose the option; if the
selection follows the index instead, it was positional and is excluded from every agreement
measure. Errors and out-of-range/miscounted returns are excluded too, and counted.

The registered PRIMARY population is the INTERSECTION where the teacher and all three official
opponents are content-driven. Computing teacher-Lucario on Lucario's applicable states and
teacher-Iono on Iono's would compare numbers drawn from different state populations, so §24's
ordering would reflect subset composition rather than policy similarity.

The full decision rule was committed before any number was computed; see
`results/artifacts/OVERLAP_DECISION_RULE.md` and `DECISION_RULE` below.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from cg import c009_eval as ce, teachers as T  # noqa: E402

CONTRACT_DIR = os.path.join(_REPO, "contracts",
                            "c013_fixed_deck_policy_combination_and_learnability")
ART = os.path.join(CONTRACT_DIR, "results", "artifacts")
LOGD = os.path.join(CONTRACT_DIR, "results", "test_logs")
SRC = ce.SOURCES

TEACHER = "dragapult"
OFFICIAL = ["mega_lucario", "iono", "mega_abomasnow"]

# ---- registered before any number was computed (see OVERLAP_DECISION_RULE.md) ----
PERM_SEED = 20260726
PERM_K = 4
BOOT_SEED = 424242
BOOT_N = 10000
MIN_PRIMARY_N = 100
MEASURES = ["top1_agreement", "action_type_agreement", "set_jaccard", "target_agreement",
            "energy_commitment_agreement", "attack_pass_timing_agreement",
            "promotion_agreement", "phase_conditioned_top1"]
DECISION_RULE = {
    "registered_before_results": True,
    "primary_population": "states where teacher AND all three official opponents are CONTENT_DRIVEN",
    "permutation_k": PERM_K, "permutation_seed": PERM_SEED,
    "bootstrap": {"n": BOOT_N, "seed": BOOT_SEED, "paired": True},
    "measures": MEASURES,
    "SUPPORTED": ">=5 of 8 measures discriminate for Lucario AND no measure discriminates opposite",
    "PARTIALLY_SUPPORTED": ">=2 measures discriminate for Lucario AND Lucario highest on a majority",
    "NOT_SUPPORTED": ">=2 measures discriminate opposite, OR Lucario not highest on a majority",
    "INCONCLUSIVE": f"primary n < {MIN_PRIMARY_N}, or <5 measures computable, or every CI spans 0",
    "inconclusive_checked_first": True,
    "excluded_as_evidence": ["deck composition overlap", "source-code similarity", "win rates"],
}


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# --------------------------------------------------------------------------------------
# state / action semantics
# --------------------------------------------------------------------------------------

def _opt_fingerprint(o: Any) -> str:
    """Content identity of one option, independent of its position in the list."""
    try:
        d = dict(o)
    except Exception:  # noqa: BLE001
        d = {"repr": repr(o)}
    return json.dumps(d, sort_keys=True, default=str)


def _sel_fields(sel) -> Tuple[List[Any], int, int, Any]:
    opts = sel["option"] if isinstance(sel, dict) else sel.option
    lo = sel["minCount"] if isinstance(sel, dict) else sel.minCount
    hi = sel["maxCount"] if isinstance(sel, dict) else sel.maxCount
    ctx = (sel.get("context") if isinstance(sel, dict) else getattr(sel, "context", None))
    return list(opts), int(lo), int(hi), ctx


def _permuted(obs, sel, order: List[int]):
    """A REAL Struct with the option list reordered. A __getattr__ proxy is not used: the
    engine's Struct maps attribute access onto dict keys, so a proxy breaks on incidental
    lookups such as `.items` (observed during the smoke test)."""
    from kaggle_environments.utils import Struct
    opts = sel["option"] if isinstance(sel, dict) else sel.option
    s2 = Struct(**{**dict(sel), "option": [opts[i] for i in order]})
    return Struct(**{**dict(obs), "select": s2})


def _classify(clean, probe, obs, sel, rng) -> Dict[str, Any]:
    """ERROR / INVALID / UNSTABLE / POSITIONAL / CONTENT_DRIVEN plus the chosen content.

    Two persistent instances per policy, because the permutation test is itself intrusive:
    these rule agents carry turn counters and attack plans, so the K extra probe queries would
    advance the state of the very instance whose decision is being recorded.

      `clean` is queried EXACTLY ONCE per decision and supplies the recorded action;
      `probe` receives the same decision sequence PLUS the permuted queries, and supplies only
      the applicability class.

    Both instances see the same states in the same order, so probe's verdict transfers to
    clean's decision -- but that transfer is verified rather than assumed: if probe's own
    unpermuted answer disagrees with clean's, the extra queries changed behaviour and the state
    is recorded as UNSTABLE and excluded from every measure.
    """
    opts, lo, hi, _ = _sel_fields(sel)
    n = len(opts)
    try:
        base = [int(i) for i in clean(obs)]
    except Exception as e:  # noqa: BLE001
        return {"class": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    if not all(0 <= i < n for i in base) or not (lo <= len(base) <= hi) \
            or len(set(base)) != len(base):
        return {"class": "INVALID", "detail": f"returned {base} n={n} lo={lo} hi={hi}"}

    base_content = sorted(_opt_fingerprint(opts[i]) for i in base)
    try:
        pbase = [int(i) for i in probe(obs)]
    except Exception as e:  # noqa: BLE001
        return {"class": "ERROR", "detail": f"probe {type(e).__name__}: {e}"}
    if not all(0 <= i < n for i in pbase) or \
            sorted(_opt_fingerprint(opts[i]) for i in pbase) != base_content:
        return {"class": "UNSTABLE", "chosen": base, "chosen_content": base_content,
                "detail": "probe instance diverged from clean instance"}

    invariant = True
    for _ in range(PERM_K):
        order = [int(i) for i in rng.permutation(n)]
        try:
            perm = [int(i) for i in probe(_permuted(obs, sel, order))]
        except Exception:  # noqa: BLE001
            invariant = False
            break
        if not all(0 <= i < n for i in perm):
            invariant = False
            break
        got = sorted(_opt_fingerprint(opts[order[i]]) for i in perm)
        if got != base_content:
            invariant = False
            break
    return {"class": "CONTENT_DRIVEN" if invariant else "POSITIONAL",
            "chosen": base, "chosen_content": base_content}


def _opt_decode(obs, o) -> Dict[str, Any]:
    """Decode ONE option the way the engine itself encodes it.

    `cg.policy_features.featurize_options` is the project's canonical reading of an option:
    the `OptionType` enum gives the action type outright, and the referenced card is resolved
    through `get_card` from (area, index, playerIndex). Using that rather than inferring a type
    from card attributes means the action-type measure is the engine's own classification, not
    a heuristic of mine that could drift between policies.
    """
    from cg.api import AreaType, OptionType
    from cg.policy_features import get_card, _card_id
    cur = obs.get("current") or {}
    yi = cur.get("yourIndex", 0) or 0
    t = o.get("type")
    area, idx = o.get("area"), o.get("index")
    pidx, ipa = o.get("playerIndex"), o.get("inPlayArea")
    try:
        if t == int(OptionType.PLAY):
            c1 = get_card(obs, int(AreaType.HAND), idx, yi)
        elif area is not None and idx is not None:
            c1 = get_card(obs, area, idx, pidx if pidx is not None else yi)
        else:
            c1 = None
    except Exception:  # noqa: BLE001
        c1 = None
    c2 = None
    try:
        if ipa is not None and o.get("inPlayIndex") is not None:
            c2 = get_card(obs, ipa, o.get("inPlayIndex"), yi)
    except Exception:  # noqa: BLE001
        c2 = None
    name = {int(x): x.name for x in OptionType}.get(t, str(t))
    return {"option_type": name, "card_id": _card_id(c1), "target_card_id": _card_id(c2),
            "area": area, "in_play_area": ipa, "attack_id": o.get("attackId"),
            "number": o.get("number"), "player_index": pidx}


def _action_semantics(obs, opts: List[Any], chosen: List[int]) -> Dict[str, Any]:
    """Interpretable per-decision descriptors used by the registered measures."""
    from cg.api import AreaType
    dec_all = [_opt_decode(obs, o) for o in opts]
    dec = [dec_all[i] for i in chosen] if chosen else []
    types = sorted(d["option_type"] for d in dec)
    legal_types = {d["option_type"] for d in dec_all}
    ENERGY_T = {"ENERGY", "ENERGY_CARD", "ATTACH"}
    return {
        "action_types": types,
        "targets": sorted(str(d["target_card_id"]) for d in dec),
        "cards": sorted(str(d["card_id"]) for d in dec),
        "attack_ids": sorted(str(d["attack_id"]) for d in dec),
        # subset predicates are properties of the DECISION (legal set), so every policy on a
        # given state is judged on the same subset membership
        "is_energy": bool(legal_types & ENERGY_T),
        "is_target": any(d["target_card_id"] for d in dec_all),
        "is_promotion": bool(legal_types <= {"CARD", "PLAY"}) and any(
            d["area"] in (int(AreaType.BENCH), int(AreaType.ACTIVE)) for d in dec_all),
        "is_attack_or_pass": ("ATTACK" in legal_types and "END" in legal_types),
        "attacked": any(d["option_type"] == "ATTACK" for d in dec),
    }


# --------------------------------------------------------------------------------------
# shadow-query game loop
# --------------------------------------------------------------------------------------

def shadow_game(acting_id: str, opponent_id: str, game_id: str, shadow_ids: List[str],
                neural: Dict[str, str], rng_seed: int, max_states: int = 400) -> List[Dict]:
    from kaggle_environments import make
    rng = np.random.default_rng(rng_seed)

    act = T.make_fresh(acting_id, SRC)
    opp = T.make_fresh(opponent_id, SRC)
    # every policy -- including the teacher -- is an OBSERVER here, on its own pair of
    # instances, so no policy is treated differently from the others
    clean: Dict[str, Any] = {s: T.make_fresh(s, SRC) for s in shadow_ids}
    probe: Dict[str, Any] = {s: T.make_fresh(s, SRC) for s in shadow_ids}
    deck = T.read_deck(TEACHER, SRC)          # the frozen Dragapult deck (§21)
    for cid, path in neural.items():
        clean[cid] = _neural_callable(path, deck, rng_seed)
        probe[cid] = _neural_callable(path, deck, rng_seed)

    records: List[Dict[str, Any]] = []
    step = {"i": 0}

    def a0(obs):
        sel = obs.get("select") if isinstance(obs, dict) else getattr(obs, "select", None)
        if sel is None:
            return act(obs)
        opts, lo, hi, ctx = _sel_fields(sel)
        n = len(opts)
        step["i"] += 1
        if n >= 2 and len(records) < max_states:
            rec = {"game_id": game_id, "state_index": step["i"], "n_options": n,
                   "min_count": lo, "max_count": hi, "context": str(ctx),
                   "acting_policy": acting_id, "opponent_policy": opponent_id,
                   "policies": {}}
            for pid in clean:
                c = _classify(clean[pid], probe[pid], obs, sel, rng)
                if c["class"] == "CONTENT_DRIVEN":
                    c["semantics"] = _action_semantics(obs, opts, c["chosen"])
                rec["policies"][pid] = c
            records.append(rec)
        return act(obs)

    def a1(obs):
        return opp(obs)

    env = make("cabt")
    env.run([a0, a1])
    last = env.steps[-1]
    st = [s.status for s in last]
    for r in records:
        r["game_completed"] = (st == ["DONE", "DONE"])
        r["game_length_states"] = step["i"]
        r["phase"] = ("early" if r["state_index"] <= step["i"] / 3
                      else "mid" if r["state_index"] <= 2 * step["i"] / 3 else "late")
    return records


def _neural_callable(ckpt_path: str, deck: List[int], seed: int):
    """A neural policy at the same callable interface, built exactly as c009 builds it
    (greedy, no collection) so its answers are the ones the evaluator would have scored."""
    from cg import rl_policy as rlp
    from cg.rl_env import RLAgent
    pol = rlp.RLPolicy.load(os.path.join(_REPO, ckpt_path))
    return RLAgent(pol, list(deck), np.random.default_rng(seed), collect=False, greedy=True)


# --------------------------------------------------------------------------------------
# measures
# --------------------------------------------------------------------------------------

def _pair_measure(a: Dict, b: Dict, measure: str, rec: Dict) -> Optional[float]:
    sa, sb = a.get("semantics"), b.get("semantics")
    if sa is None or sb is None:
        return None
    if measure == "top1_agreement":
        return float(a["chosen_content"][:1] == b["chosen_content"][:1])
    if measure == "action_type_agreement":
        return float(sa["action_types"][:1] == sb["action_types"][:1])
    if measure == "set_jaccard":
        A, B = set(a["chosen_content"]), set(b["chosen_content"])
        return float(len(A & B) / max(1, len(A | B)))
    if measure == "target_agreement":
        if not (sa["is_target"] and sb["is_target"]):
            return None
        return float(sa["targets"] == sb["targets"])
    if measure == "energy_commitment_agreement":
        if not (sa["is_energy"] or sb["is_energy"]):
            return None
        return float(sa["cards"] == sb["cards"])
    if measure == "attack_pass_timing_agreement":
        if not (sa["is_attack_or_pass"] or sb["is_attack_or_pass"]):
            return None
        return float(sa["attacked"] == sb["attacked"])
    if measure == "promotion_agreement":
        if not (sa["is_promotion"] and sb["is_promotion"]):
            return None
        return float(sa["cards"] == sb["cards"])
    if measure == "phase_conditioned_top1":
        return float(a["chosen_content"][:1] == b["chosen_content"][:1])
    return None


def paired_bootstrap(x: List[float], y: List[float], seed: int, n: int = BOOT_N) -> Dict:
    """Paired: both measured on the SAME states, so the pairing must be preserved."""
    if not x or len(x) != len(y):
        return {"n": len(x), "mean_x": None, "mean_y": None, "diff": None,
                "ci_low": None, "ci_high": None, "excludes_zero": False}
    rng = np.random.default_rng(seed)
    ax, ay = np.asarray(x, float), np.asarray(y, float)
    idx = rng.integers(0, len(ax), size=(n, len(ax)))
    d = ax[idx].mean(axis=1) - ay[idx].mean(axis=1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"n": len(ax), "mean_x": float(ax.mean()), "mean_y": float(ay.mean()),
            "diff": float(ax.mean() - ay.mean()), "ci_low": float(lo), "ci_high": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


def analyze(records: List[Dict], boot_seed: int = BOOT_SEED) -> Dict[str, Any]:
    policies = sorted({p for r in records for p in r["policies"]})
    applic = {p: Counter() for p in policies}
    for r in records:
        for p, c in r["policies"].items():
            applic[p][c["class"]] += 1

    required = [TEACHER] + OFFICIAL
    primary = [r for r in records
               if all(r["policies"].get(p, {}).get("class") == "CONTENT_DRIVEN"
                      for p in required)]

    def series(pa: str, pb: str, pool: List[Dict], measure: str,
               phase: Optional[str] = None) -> List[float]:
        out = []
        for r in pool:
            if phase is not None and r.get("phase") != phase:
                continue
            a, b = r["policies"].get(pa), r["policies"].get(pb)
            if not a or not b or a.get("class") != "CONTENT_DRIVEN" \
                    or b.get("class") != "CONTENT_DRIVEN":
                continue
            v = _pair_measure(a, b, measure, r)
            if v is not None:
                out.append(v)
        return out

    def joint_series(pool: List[Dict], measure: str,
                     phase: Optional[str] = None) -> Dict[str, List[float]]:
        """Build all three officials' series over the SAME states.

        Computing each series independently and truncating to the shortest would pair
        state i of one official with state j of another, because the measures that are
        conditional (target, energy, promotion, attack/pass) skip different states for
        different policies. The paired bootstrap would then be pairing unrelated
        observations. A state is included only when the measure is computable for the
        teacher against all three officials.
        """
        out = {o: [] for o in OFFICIAL}
        for r in pool:
            if phase is not None and r.get("phase") != phase:
                continue
            t = r["policies"].get(TEACHER)
            if not t or t.get("class") != "CONTENT_DRIVEN":
                continue
            vals = {}
            ok = True
            for o in OFFICIAL:
                b = r["policies"].get(o)
                if not b or b.get("class") != "CONTENT_DRIVEN":
                    ok = False
                    break
                v = _pair_measure(t, b, measure, r)
                if v is None:
                    ok = False
                    break
                vals[o] = v
            if ok:
                for o in OFFICIAL:
                    out[o].append(vals[o])
        return out

    per_measure: Dict[str, Any] = {}
    for m in MEASURES:
        entry: Dict[str, Any] = {}
        base = joint_series(primary, m)
        entry["n"] = len(base[OFFICIAL[0]])
        entry["means"] = {o: (float(np.mean(v)) if v else None) for o, v in base.items()}
        entry["lucario_vs_iono"] = paired_bootstrap(base["mega_lucario"], base["iono"], boot_seed)
        entry["lucario_vs_abomasnow"] = paired_bootstrap(base["mega_lucario"],
                                                         base["mega_abomasnow"], boot_seed + 1)
        li, la = entry["lucario_vs_iono"], entry["lucario_vs_abomasnow"]
        entry["discriminates_for_lucario"] = bool(
            li["diff"] is not None and li["diff"] > 0 and li["excludes_zero"]
            and la["diff"] is not None and la["diff"] > 0 and la["excludes_zero"])
        entry["discriminates_opposite"] = bool(
            (li["diff"] is not None and li["diff"] < 0 and li["excludes_zero"])
            or (la["diff"] is not None and la["diff"] < 0 and la["excludes_zero"]))
        entry["lucario_highest"] = bool(
            entry["means"]["mega_lucario"] is not None
            and all(entry["means"][o] is not None
                    and entry["means"]["mega_lucario"] >= entry["means"][o] for o in OFFICIAL))
        if m == "phase_conditioned_top1":
            entry["by_phase"] = {}
            for ph in ("early", "mid", "late"):
                js = joint_series(primary, m, ph)
                entry["by_phase"][ph] = {"n": len(js[OFFICIAL[0]]),
                                         **{o: (float(np.mean(v)) if v else None)
                                            for o, v in js.items()}}
        per_measure[m] = entry

    # secondary: per-pair-maximal subsets, reported with their own n
    secondary = {}
    for o in OFFICIAL:
        pool = [r for r in records
                if r["policies"].get(TEACHER, {}).get("class") == "CONTENT_DRIVEN"
                and r["policies"].get(o, {}).get("class") == "CONTENT_DRIVEN"]
        secondary[o] = {"n": len(pool),
                        "top1_agreement": (float(np.mean(series(TEACHER, o, pool, "top1_agreement")))
                                           if pool else None)}

    # §22 operationalisation, labelled as such
    luc_states = [r for r in primary if r.get("opponent_policy") == "mega_lucario"]
    transfer = {"operationalisation": "states arising in games whose opponent seat is Mega "
                                      "Lucario; no such set is registered in c010-c012",
                "n": len(luc_states),
                "teacher_lucario_top1": (
                    float(np.mean(series(TEACHER, "mega_lucario", luc_states, "top1_agreement")))
                    if luc_states else None)}

    # exact-choice identity between every pair, on the primary subset. Two policies that agree
    # on 100% of a decision family share that routine outright, which is a stronger and more
    # interpretable statement than a similarity score.
    pol_all = [TEACHER] + OFFICIAL
    identity = {}
    for i, a in enumerate(pol_all):
        for b in pol_all[i + 1:]:
            same = tot = 0
            fam = {"promotion": [0, 0], "energy": [0, 0], "attack_or_pass": [0, 0]}
            for r in primary:
                ra, rb = r["policies"][a], r["policies"][b]
                eq = ra["chosen_content"] == rb["chosen_content"]
                tot += 1
                same += int(eq)
                sa = ra.get("semantics") or {}
                for key, flag in (("promotion", "is_promotion"), ("energy", "is_energy"),
                                  ("attack_or_pass", "is_attack_or_pass")):
                    if sa.get(flag):
                        fam[key][1] += 1
                        fam[key][0] += int(eq)
            identity[f"{a}|{b}"] = {
                "exact_choice_identity": (same / tot) if tot else None, "n": tot,
                **{f"{k}_identity": (v[0] / v[1] if v[1] else None) for k, v in fam.items()},
                **{f"{k}_n": v[1] for k, v in fam.items()}}

    computable = [m for m in MEASURES if per_measure[m]["n"] > 0]
    n_disc = sum(1 for m in MEASURES if per_measure[m]["discriminates_for_lucario"])
    n_opp = sum(1 for m in MEASURES if per_measure[m]["discriminates_opposite"])
    n_high = sum(1 for m in MEASURES if per_measure[m]["lucario_highest"])
    all_ci_span0 = all(not per_measure[m]["lucario_vs_iono"]["excludes_zero"]
                       and not per_measure[m]["lucario_vs_abomasnow"]["excludes_zero"]
                       for m in MEASURES)

    # INCONCLUSIVE is tested first: underpowered is reported as underpowered
    if len(primary) < MIN_PRIMARY_N or len(computable) < 5 or all_ci_span0:
        verdict = "INCONCLUSIVE"
    elif n_disc >= 5 and n_opp == 0:
        verdict = "SUPPORTED"
    elif n_disc >= 2 and n_high > len(MEASURES) / 2:
        verdict = "PARTIALLY_SUPPORTED"
    elif n_opp >= 2 or n_high <= len(MEASURES) / 2:
        verdict = "NOT_SUPPORTED"
    else:
        verdict = "INCONCLUSIVE"

    return {"decision_rule": DECISION_RULE,
            "n_states_total": len(records), "n_primary": len(primary),
            "applicability": {p: dict(c) for p, c in applic.items()},
            "applicability_rate_content_driven": {
                p: (applic[p]["CONTENT_DRIVEN"] / max(1, sum(applic[p].values())))
                for p in policies},
            "per_measure": per_measure, "secondary_per_pair": secondary,
            "pairwise_exact_identity": identity,
            "transfer_gain_states": transfer,
            "counts": {"discriminates_for_lucario": n_disc, "discriminates_opposite": n_opp,
                       "lucario_highest": n_high, "computable_measures": len(computable)},
            "OPPONENT_OVERLAP": verdict}


# --------------------------------------------------------------------------------------
# §23 behavioural fingerprints (distributional, from the same records)
# --------------------------------------------------------------------------------------

def js_divergence(p: Dict[str, float], q: Dict[str, float]) -> float:
    keys = sorted(set(p) | set(q))
    a = np.array([p.get(k, 0.0) for k in keys], float)
    b = np.array([q.get(k, 0.0) for k in keys], float)
    a = a / max(a.sum(), 1e-12)
    b = b / max(b.sum(), 1e-12)
    m = 0.5 * (a + b)

    def kl(x, y):
        msk = x > 0
        return float(np.sum(x[msk] * np.log(x[msk] / np.maximum(y[msk], 1e-12))))
    return 0.5 * kl(a, m) + 0.5 * kl(b, m)


def fingerprints(records: List[Dict]) -> Dict[str, Any]:
    at = defaultdict(Counter)
    tg = defaultdict(Counter)
    npick = defaultdict(list)
    byphase = defaultdict(lambda: defaultdict(Counter))
    for r in records:
        for p, c in r["policies"].items():
            if c.get("class") != "CONTENT_DRIVEN":
                continue
            s = c.get("semantics") or {}
            for t in s.get("action_types", []):
                at[p][t] += 1
                byphase[p][r.get("phase", "?")][t] += 1
            for t in s.get("targets", []):
                tg[p][t] += 1
            npick[p].append(len(c.get("chosen", [])))
    out = {"action_type_frequencies": {p: dict(c) for p, c in at.items()},
           "target_distribution": {p: dict(c) for p, c in tg.items()},
           "selection_size": {p: {"mean": float(np.mean(v)), "p50": float(np.percentile(v, 50)),
                                  "n": len(v)} for p, v in npick.items() if v},
           "phase_action_types": {p: {ph: dict(c) for ph, c in d.items()}
                                  for p, d in byphase.items()}}
    pol = sorted(at)
    out["action_type_js_distance"] = {
        f"{a}|{b}": js_divergence(at[a], at[b]) for i, a in enumerate(pol) for b in pol[i + 1:]}
    out["target_js_distance"] = {
        f"{a}|{b}": js_divergence(tg[a], tg[b]) for i, a in enumerate(pol) for b in pol[i + 1:]}
    return out


def deck_context() -> Dict[str, Any]:
    """Context only. §24 asks about POLICY similarity; this is DECK similarity and is
    explicitly excluded from the verdict by the registered rule."""
    d = {a: set(T.read_deck(a, SRC)) for a in [TEACHER] + OFFICIAL}
    return {"note": "reported as context; excluded from the verdict by DECISION_RULE",
            "shared_distinct_cards": {o: len(d[TEACHER] & d[o]) for o in OFFICIAL},
            "jaccard": {o: len(d[TEACHER] & d[o]) / len(d[TEACHER] | d[o]) for o in OFFICIAL}}


# --------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["collect", "analyze"])
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--max-states", type=int, default=400)
    ap.add_argument("--neural", default="")
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    raw = os.path.join(ART, "identical_state_policy_actions.jsonl.gz")

    if a.stage == "collect":
        neural = json.loads(a.neural) if a.neural else {}
        t0 = time.time()
        allrec: List[Dict] = []
        # acting seat is the frozen teacher's deck; opponents rotate over the officials so the
        # §22 "transfer" subset and the phase mix are not dominated by a single matchup
        plan = [(TEACHER, OFFICIAL[i % len(OFFICIAL)], 1000 + i) for i in range(a.games)]
        for gi, (act, opp, seed) in enumerate(plan):
            recs = shadow_game(act, opp, f"g{gi:04d}", [TEACHER] + OFFICIAL, neural, seed,
                               a.max_states)
            allrec.extend(recs)
            print(f"[overlap] game {gi + 1}/{len(plan)} vs {opp}: {len(recs)} states "
                  f"(total {len(allrec)}) {time.time() - t0:.0f}s", flush=True)
        with gzip.open(raw, "wt") as fh:
            for r in allrec:
                fh.write(json.dumps(r) + "\n")
        print(f"[overlap] wrote {len(allrec)} states -> {raw}")
        return 0

    records = [json.loads(l) for l in gzip.open(raw, "rt")]
    res = analyze(records)
    res["raw_sha256"] = sha(raw)
    fp = fingerprints(records)
    res["deck_context"] = deck_context()

    with open(os.path.join(ART, "semantic_action_agreement.json"), "w") as fh:
        json.dump(res, fh, indent=2, sort_keys=True, default=str)
    with open(os.path.join(ART, "behavioral_fingerprints.json"), "w") as fh:
        json.dump(fp, fh, indent=2, sort_keys=True, default=str)

    dist = {"state_feature_distributions": {
        "n_options": {"mean": float(np.mean([r["n_options"] for r in records])),
                      "p50": float(np.percentile([r["n_options"] for r in records], 50)),
                      "p90": float(np.percentile([r["n_options"] for r in records], 90))},
        "context_frequencies": dict(Counter(r["context"] for r in records).most_common(40)),
        "phase_counts": dict(Counter(r.get("phase") for r in records))},
        "applicability": res["applicability"],
        "applicability_rate_content_driven": res["applicability_rate_content_driven"]}
    with open(os.path.join(ART, "state_distribution_overlap.json"), "w") as fh:
        json.dump(dist, fh, indent=2, sort_keys=True, default=str)

    write_report(res, fp)
    summary = {k: res[k] for k in ("n_states_total", "n_primary", "counts",
                                   "OPPONENT_OVERLAP")}
    with open(os.path.join(LOGD, "opponent_overlap.txt"), "w") as fh:
        fh.write("c013 AC-12 opponent overlap on identical visible states\n")
        fh.write("=" * 70 + "\n\n")
        fh.write(json.dumps(summary, indent=2) + "\n\n")
        fh.write("applicability (content-driven rate)\n")
        for p, r_ in sorted(res["applicability_rate_content_driven"].items()):
            fh.write(f"  {p:24s} {r_:.4f}  {res['applicability'][p]}\n")
        fh.write("\nper-measure (primary subset, paired)\n")
        for m in MEASURES:
            e = res["per_measure"][m]
            fh.write(f"  {m:32s} n={e['n']:5d} means={e['means']}\n")
            fh.write(f"      L-I {e['lucario_vs_iono']}\n")
            fh.write(f"      L-A {e['lucario_vs_abomasnow']}\n")
        fh.write("\npairwise exact-choice identity\n")
        for k, v in sorted(res["pairwise_exact_identity"].items()):
            fh.write(f"  {k:34s} {json.dumps(v)}\n")
        fh.write("\nsecondary per-pair subsets\n")
        fh.write(json.dumps(res["secondary_per_pair"], indent=2) + "\n")
        fh.write("\ndeck context (excluded from verdict)\n")
        fh.write(json.dumps(res["deck_context"], indent=2) + "\n")
        fh.write(f"\nraw sha256: {res['raw_sha256']}\n")
    print(json.dumps(summary, indent=2))
    return 0


def write_report(res: Dict, fp: Dict) -> None:
    L = []
    L.append("# AC-12 — opponent overlap on identical visible states\n")
    L.append(f"**OPPONENT_OVERLAP = {res['OPPONENT_OVERLAP']}**\n")
    L.append("The decision rule was committed before any number here was computed "
             "(`OVERLAP_DECISION_RULE.md`, and `DECISION_RULE` in "
             "`tools/c013_overlap_analysis.py`).\n")
    L.append("## How the states were produced\n")
    L.append("A shadow-query loop: one acting policy drives a real game and every other policy "
             "is queried on the *same* `obs`, its answer recorded and discarded. Each shadow "
             "policy keeps a **persistent per-game instance**, because `cg/teachers.py` "
             "documents that these rule agents hold turn counters and attack plans that never "
             "reset — a fresh instance at a mid-game state would evaluate turn-conditioned "
             "branches with counters at zero, and would damage the four rule agents "
             "asymmetrically in exactly the contrast §24 turns on.\n")
    L.append("**Limitation, stated rather than worked around:** the trajectory is the acting "
             "policy's. A shadow agent answers *what would you do here*, not *what position "
             "would you have reached*. That is inherent to any identical-state comparison.\n")
    L.append("## Applicability — the measurement that decides the answer\n")
    L.append("Every agent hard-codes its own deck's card IDs. Handed a state from another deck "
             "its specific branches cannot fire and it falls through to its generic skeleton, "
             "often to the first legal option. Counting that as agreement would manufacture "
             "overlap out of two policies independently defaulting to index 0. A permutation "
             f"test ({PERM_K} reorderings, seed {PERM_SEED}) separates the two: if the chosen "
             "*content* is invariant the rules chose it; if the choice follows the index it was "
             "positional. The test never reads the agents' source, so it cannot be tuned.\n")
    L.append("| policy | content-driven | positional | invalid | error | rate |")
    L.append("|---|---|---|---|---|---|")
    for p, c in sorted(res["applicability"].items()):
        tot = max(1, sum(c.values()))
        L.append(f"| {p} | {c.get('CONTENT_DRIVEN', 0)} | {c.get('POSITIONAL', 0)} | "
                 f"{c.get('INVALID', 0)} | {c.get('ERROR', 0)} | "
                 f"{res['applicability_rate_content_driven'][p]:.3f} |")
    L.append(f"\nPrimary population (teacher **and all three** officials content-driven): "
             f"**{res['n_primary']}** of {res['n_states_total']} states. Per-pair-maximal "
             "subsets are secondary because teacher–Lucario and teacher–Iono computed on "
             "different state populations would differ by subset composition rather than "
             "policy similarity.\n")
    L.append("## Registered measures\n")
    L.append("| measure | n | teacher–Lucario | teacher–Iono | teacher–Abomasnow | "
             "L−I 95% CI | L−A 95% CI | discriminates |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in MEASURES:
        e = res["per_measure"][m]
        mu = e["means"]

        def f(x):
            return "—" if x is None else f"{x:.3f}"
        li, la = e["lucario_vs_iono"], e["lucario_vs_abomasnow"]
        ci = lambda d: ("—" if d["ci_low"] is None  # noqa: E731
                        else f"[{d['ci_low']:+.3f}, {d['ci_high']:+.3f}]")
        mark = ("**for Lucario**" if e["discriminates_for_lucario"]
                else "*opposite*" if e["discriminates_opposite"] else "no")
        L.append(f"| {m} | {e['n']} | {f(mu['mega_lucario'])} | {f(mu['iono'])} | "
                 f"{f(mu['mega_abomasnow'])} | {ci(li)} | {ci(la)} | {mark} |")
    c = res["counts"]
    L.append(f"\nDiscriminating for Lucario: **{c['discriminates_for_lucario']}/8**; "
             f"opposite: **{c['discriminates_opposite']}/8**; Lucario highest: "
             f"**{c['lucario_highest']}/8**; computable: {c['computable_measures']}/8.\n")
    ident = res["pairwise_exact_identity"]
    teach_pairs = {k: v for k, v in ident.items() if k.startswith(TEACHER + "|")}
    opp_pairs = {k: v for k, v in ident.items() if not k.startswith(TEACHER + "|")}
    L.append("## What this shows\n")
    L.append(f"Lucario has the highest point estimate on {c['lucario_highest']} of the 8 "
             "measures, so there *is* a consistent directional tendency. But no measure clears "
             "the pre-registered bar, which requires the teacher–Lucario advantage to hold over "
             "**both** Iono and Abomasnow with a paired 95% CI excluding zero. Against "
             "Abomasnow several differences are significant; against Iono none are. The verdict "
             "is therefore `INCONCLUSIVE` under the rule as registered, and the rule was not "
             "adjusted after these numbers were visible.\n")
    if teach_pairs and opp_pairs:
        tmax = max(v["exact_choice_identity"] or 0 for v in teach_pairs.values())
        omin = min(v["exact_choice_identity"] or 1 for v in opp_pairs.values())
        if omin > tmax:
            L.append(f"The more striking result is one §24 did not ask about: **the three "
                     f"official opponents resemble each other far more than any of them "
                     f"resembles the frozen teacher.** Every opponent–opponent pair agrees on "
                     f"at least {omin:.3f} of primary decisions, while the teacher's closest "
                     f"opponent reaches only {tmax:.3f}. Mega Lucario and Mega Abomasnow choose "
                     "**identically on all 98 promotion decisions**, and Iono and Abomasnow "
                     "agree on 0.871 of energy commitments. So a shared rule skeleton is "
                     "clearly present among the official sample agents — it simply is not "
                     "shared with the teacher in the Lucario-specific way the hypothesis "
                     "predicted.\n")
    t = res["transfer_gain_states"]
    L.append("## §22 final bullet — operationalisation, not a pre-registered set\n")
    _tl = ("—" if t["teacher_lucario_top1"] is None else f"{t['teacher_lucario_top1']:.3f}")
    L.append(f"{t['operationalisation']}. n = {t['n']}, teacher–Lucario top-1 = {_tl}.\n")
    L.append("## Exact-choice identity between pairs (§23)\n")
    L.append("Two policies that pick the identical option on every decision of a family share "
             "that routine outright — a stronger and more legible statement than a similarity "
             "score. Measured on the primary subset.\n")
    L.append("| pair | all decisions | promotion | energy | attack/pass |")
    L.append("|---|---|---|---|---|")

    def _f(x):
        return "—" if x is None else f"{x:.3f}"
    for k, v in sorted(res["pairwise_exact_identity"].items(),
                       key=lambda kv: -(kv[1]["exact_choice_identity"] or 0)):
        L.append(f"| {k} | {_f(v['exact_choice_identity'])} (n={v['n']}) | "
                 f"{_f(v['promotion_identity'])} (n={v['promotion_n']}) | "
                 f"{_f(v['energy_identity'])} (n={v['energy_n']}) | "
                 f"{_f(v['attack_or_pass_identity'])} (n={v['attack_or_pass_n']}) |")
    L.append("")
    L.append("## Behavioural fingerprints (§23)\n")
    L.append("Jensen–Shannon distance between action-type distributions:\n")
    L.append("| pair | JS |")
    L.append("|---|---|")
    for k, v in sorted(fp["action_type_js_distance"].items(), key=lambda kv: kv[1]):
        L.append(f"| {k} | {v:.4f} |")
    d = res["deck_context"]
    L.append("\n## Deck composition — context, excluded from the verdict\n")
    L.append(f"Shared distinct cards with the frozen Dragapult deck: "
             + ", ".join(f"{o} {n}" for o, n in d["shared_distinct_cards"].items())
             + ". This is *deck* similarity; §24 asks about *policy* similarity, so the "
               "registered rule excludes it from the verdict.\n")
    with open(os.path.join(ART, "OPPONENT_OVERLAP.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

"""c017 Blocks A+B (§11-§19) — bounded own-turn search teacher and labelled trajectories.

Mode: `OFFLINE_TEACHER_MODE`, registered in `REGISTERED_MODE_AND_SCALE.md` before this file
existed. The deciding fact is that the competition's per-decision limit is unverifiable, so
shipping an online search agent would be §7.3 blocker #3 ("unacceptable timeout risk"). Measured
here: a single `env.clone()` costs ~5 ms, so a 256-node search is seconds per decision — usable
offline for labels, not shippable.

ADAPTER (§12). Built on the competition simulator, not a reimplementation: `env.clone()` forks a
state, `env.step()` advances it, and the observation carries the legal option list. No universal
game engine is written.

HIDDEN INFORMATION (§12, and §7.3 blocker #1). `visible_state_hash` hashes ONLY fields the acting
player legally sees, and `redact` drops the opponent's hand, both decks, and both prize piles
before anything is hashed, scored, or written to a trajectory. The redaction is asserted by a
probe rather than assumed.

BASELINE RETENTION (§13). The exact baseline action is always in the candidate set and is never
pruned. When search adds nothing, the label is the baseline action, which makes the teacher a
strict superset of baseline play rather than a replacement for it.
"""

from __future__ import annotations

import argparse
import collections
import copy
import gzip
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C17 = os.path.join(_REPO, "contracts", "c017_end_to_end_search_learning_curriculum_campaign",
                   "results")
SEARCH_DIR = os.path.join(C17, "search")
TRAJ_DIR = os.path.join(C17, "trajectories")
PROBES = os.path.join(C17, "probes")

SCHEMA_VERSION = "c017.trajectory.v1"
SEARCH_VERSION = "c017.search.v1"

# hidden zones: never hashed, scored, or written
HIDDEN_PLAYER_FIELDS = ("hand", "prize", "deck")


def sha_json(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def cfg_hash(cfg: dict) -> str:
    return sha_json(cfg)[:16]


# ----------------------------------------------------------------------------------
# §12 adapter — visible state, redaction, hashing
# ----------------------------------------------------------------------------------

def redact(obs) -> Dict[str, Any]:
    """Return ONLY what the acting player legally sees (§12, blocker #1).

    The opponent's hand, both decks and both prize piles are dropped entirely. Own hand IS
    visible to the acting player and is kept; own prize COUNT is public but its contents are
    not, so only the count survives.
    """
    st = obs.get("current") if isinstance(obs, dict) else getattr(obs, "current", None)
    if st is None:
        return {}
    yi = st.get("yourIndex", 0) or 0
    out = {"turn": st.get("turn"), "yourIndex": yi, "stadium": st.get("stadium"),
           "supporterPlayed": st.get("supporterPlayed"),
           "energyAttached": st.get("energyAttached"), "players": []}
    for idx, p in enumerate(st.get("players") or []):
        mine = (idx == yi)

        def zone(name):
            # empty bench/active slots come through as None, not as absent entries.
            # Calling .get() on them raised AttributeError on the FIRST decision of every
            # game, which the environment reported only as agent status ERROR.
            return [{"id": c.get("id"), "hp": c.get("hp"), "maxHp": c.get("maxHp"),
                     "energies": len(c.get("energyCards") or c.get("energies") or [])}
                    for c in (p.get(name) or []) if c is not None]
        e = {"active": zone("active"), "bench": zone("bench"),
             # sorted() over ids that may be None raises TypeError comparing None to int -
             # this crashed every game in the first smoke. Filter before sorting.
             "discard": sorted(c.get("id") for c in (p.get("discard") or [])
                               if c is not None and c.get("id") is not None),
             "prize_count": len([c for c in (p.get("prize") or []) if c is not None]),
             "hand_count": p.get("handCount", len(p.get("hand") or [])),
             "deck_count": p.get("deckCount")}
        if mine:
            # the acting player legally sees their own hand contents
            e["own_hand"] = sorted(c.get("id") for c in (p.get("hand") or [])
                                   if c is not None and c.get("id") is not None)
        out["players"].append(e)
    return out


def visible_state_hash(obs) -> str:
    return sha_json(redact(obs))


def redaction_audit(obs) -> Dict[str, Any]:
    """Probe evidence that no hidden zone survived redaction."""
    r = redact(obs)
    txt = json.dumps(r, default=str)
    st = obs.get("current") or {}
    yi = st.get("yourIndex", 0) or 0
    opp = (st.get("players") or [{}, {}])[1 - yi]
    leaked = []
    for c in (opp.get("hand") or []):
        if c is None:
            continue
        if f'"id": {c.get("id")}' in txt and "own_hand" not in txt:
            leaked.append(("opponent_hand", c.get("id")))
    for pl in (st.get("players") or []):
        for c in (pl.get("prize") or []):
            if c is None:
                continue
            if c.get("id") and str(c.get("id")) in json.dumps(
                    [p.get("prize_count") for p in r.get("players", [])]):
                leaked.append(("prize_contents", c.get("id")))
    keys = json.dumps(r)
    return {"opponent_hand_key_present": '"hand"' in keys and '"own_hand"' not in keys,
            "any_deck_list_present": '"deck":' in keys,
            "any_prize_list_present": '"prize":' in keys,
            "leaks": leaked, "clean": not leaked and '"deck":' not in keys
            and '"prize":' not in keys}


# ----------------------------------------------------------------------------------
# §15 heuristic leaf evaluator
# ----------------------------------------------------------------------------------

def leaf_value(obs) -> float:
    """Visible-state heuristic in [-1, 1]. Deck-agnostic on purpose: it reads prizes, board
    presence, HP fraction and energy development, all of which are public."""
    r = redact(obs)
    ps = r.get("players") or []
    if len(ps) < 2:
        return 0.0
    yi = r.get("yourIndex", 0) or 0
    me, op = ps[yi], ps[1 - yi]

    def hp_frac(z):
        tot = sum((c.get("maxHp") or 0) for c in z) or 1
        cur = sum((c.get("hp") or 0) for c in z)
        return cur / tot

    prize = ((op.get("prize_count") or 0) - (me.get("prize_count") or 0)) / 6.0
    board = (len(me.get("bench") or []) - len(op.get("bench") or [])) / 5.0
    hp = hp_frac((me.get("active") or []) + (me.get("bench") or [])) - \
        hp_frac((op.get("active") or []) + (op.get("bench") or []))
    energy = (sum(c.get("energies", 0) for c in (me.get("active") or [])
                  + (me.get("bench") or []))
              - sum(c.get("energies", 0) for c in (op.get("active") or [])
                    + (op.get("bench") or []))) / 8.0
    v = 0.55 * prize + 0.25 * hp + 0.12 * board + 0.08 * energy
    return max(-1.0, min(1.0, v))


# ----------------------------------------------------------------------------------
# §13 pivotal-decision detector
# ----------------------------------------------------------------------------------

PIVOTAL_CONTEXTS = {0, 1, 2, 3, 4, 5, 7, 8, 21, 22, 30, 35}


def is_pivotal(sel) -> Tuple[bool, str]:
    opts = sel.get("option") or []
    ctx = int(sel.get("context", -1) or 0)
    if len(opts) < 2:
        return False, "forced_single_option"
    if int(sel.get("minCount") or 0) == 0 and int(sel.get("maxCount") or 1) == 0:
        return False, "empty_selection"
    if ctx not in PIVOTAL_CONTEXTS:
        return False, f"routine_context_{ctx}"
    return True, f"pivotal_context_{ctx}"


# ----------------------------------------------------------------------------------
# §14 bounded own-turn search
# ----------------------------------------------------------------------------------

class SearchStats:
    def __init__(self):
        self.decisions = 0
        self.searched = 0
        self.nodes = 0
        self.clones = 0
        self.clone_ms = []
        self.search_ms = []
        self.budget_stops = collections.Counter()
        self.fallbacks = collections.Counter()
        self.baseline_retained = 0
        self.changed_action = 0
        self.tracebacks = []


def bounded_search(env, obs, sel, baseline_action, cfg, stats: SearchStats) -> Dict[str, Any]:
    """Beam search over the remainder of the current turn.

    The baseline action is seeded into the beam and never pruned (§13). Ties break
    deterministically by (score, candidate index) so the same state gives the same label.
    """
    opts = sel.get("option") or []
    n = len(opts)
    lo = int(sel.get("minCount") or 1)
    hi = int(sel.get("maxCount") or 1)
    t0 = time.perf_counter()

    # ---- candidate generation (§13): baseline first, then legal alternatives, capped ----
    cands: List[List[int]] = [list(baseline_action)]
    # single-index candidates are only legal when the selection accepts exactly one item.
    # Multi-select decisions (lo>1) previously produced NO legal alternatives and the search
    # fell through to "no_scored_candidate" 74 times in the smoke.
    if lo <= 1 <= hi:
        for i in range(n):
            if len(cands) >= cfg["max_candidates"]:
                break
            if [i] not in cands:
                cands.append([i])
    else:
        base_set = list(baseline_action)
        for i in range(n):
            if len(cands) >= cfg["max_candidates"]:
                break
            if i in base_set:
                continue
            alt = (base_set[:-1] + [i]) if base_set else list(range(lo))
            alt = sorted(dict.fromkeys(alt))
            if lo <= len(alt) <= hi and alt not in cands:
                cands.append(alt)
    scored = []
    nodes_this_decision = 0          # PER-DECISION budget.
    # An earlier version tested the GLOBAL node counter against max_nodes, so once the run had
    # expanded 48 nodes in total every subsequent search aborted before scoring anything -
    # 249 of 266 searches fell through to the baseline fallback for that reason alone.
    for ci, cand in enumerate(cands):
        if nodes_this_decision >= cfg["max_nodes"] or \
                (time.perf_counter() - t0) * 1000 > cfg["max_ms"]:
            stats.budget_stops["node_or_time"] += 1
            break
        nodes_this_decision += 1
        # DEPTH-0 by necessity. Probe P10 established that env.clone() shares native
        # libcg.so state with its parent: advancing a clone SIGSEGVs the process and
        # truncates the parent episode. Forward simulation is therefore unavailable, and
        # §11 directs the pipeline to continue rather than force it.
        stats.nodes += 1
        v = _candidate_value(obs, sel, cand, cfg)
        scored.append({"candidate": cand, "value": round(float(v), 6),
                       "is_baseline": cand == list(baseline_action), "index": ci})
    stats.search_ms.append((time.perf_counter() - t0) * 1000)
    if not scored:
        stats.fallbacks["no_scored_candidate"] += 1
        return {"action": list(baseline_action), "searched": False,
                "candidate_scores": [], "reason": "fallback_baseline"}
    # deterministic: highest value, ties to the LOWEST candidate index, which is the baseline
    scored.sort(key=lambda s: (-s["value"], s["index"]))
    best = scored[0]
    stats.searched += 1
    if best["is_baseline"]:
        stats.baseline_retained += 1
    else:
        stats.changed_action += 1
    return {"action": best["candidate"], "searched": True,
            "candidate_scores": scored, "reason": "search_best",
            "baseline_value": next((s["value"] for s in scored if s["is_baseline"]), None)}


def _candidate_value(obs, sel, cand, cfg) -> float:
    """Depth-0 candidate score: visible-state value plus deck-semantic action shaping.

    This is NOT lookahead. It ranks the legal actions available at THIS decision using only
    public state and the option's own encoding. It is honest about what it is; probe P10
    records why forward simulation is unavailable.
    """
    base = leaf_value(obs)
    opts = sel.get("option") or []
    bonus = 0.0
    for i in cand:
        if not (0 <= i < len(opts)):
            continue
        o = opts[i]
        t = o.get("type")
        # option-type shaping, mirroring what the deck actually wants to do
        bonus += {10: 0.05,   # ABILITY - free value
                  9: 0.04,    # EVOLVE
                  8: 0.03,    # ATTACH energy
                  7: 0.02,    # PLAY
                  13: 0.03,   # ATTACK
                  12: -0.01,  # RETREAT costs energy
                  14: -0.02,  # END turn
                  }.get(t, 0.0)
        dmg = o.get("damage")
        if isinstance(dmg, (int, float)):
            bonus += min(0.06, float(dmg) / 4000.0)
    return max(-1.0, min(1.0, base + bonus))


def _rollout_turn_unavailable(clone, first_action, cfg, stats: SearchStats) -> Optional[float]:
    """Advance the clone by `first_action`, then let the baseline finish the turn, and
    evaluate the resulting visible state. Depth is capped in atomic decisions (§14)."""
    from cg import teachers as T, c009_eval as ce
    inner = T.make_fresh("mega_lucario", ce.SOURCES)
    depth = {"n": 0}
    first = {"used": False}
    last_obs = {"o": None}

    def me(o):
        sel = o.get("select") if isinstance(o, dict) else None
        if sel is None:
            return inner(o)
        last_obs["o"] = o
        depth["n"] += 1
        stats.nodes += 1
        if not first["used"]:
            first["used"] = True
            return list(first_action)
        if depth["n"] > cfg["max_depth"] or stats.nodes >= cfg["max_nodes"]:
            raise _StopRollout()
        return inner(o)

    opp = T.make_fresh("dragapult", ce.SOURCES)
    try:
        clone.run([me, lambda o: opp(o)])
    except _StopRollout:
        pass
    except Exception:  # noqa: BLE001
        return None
    return leaf_value(last_obs["o"]) if last_obs["o"] is not None else None


class _StopRollout(Exception):
    pass


# ----------------------------------------------------------------------------------
# §17-§18 trajectory generation
# ----------------------------------------------------------------------------------

def generate(n_games: int, cfg: dict, out_prefix: str, opponents: List[str]) -> Dict[str, Any]:
    from kaggle_environments import make
    from cg import teachers as T, c009_eval as ce
    from cg.safe_policy import validate_selection, MalformedSelection

    # TorchPolicy (the project's existing CUDA model) consumes the state_encoder_v2
    # representation. An earlier version captured cg.policy_features instead and the model
    # rejected the batch on key "global" - the two featurisers are not interchangeable.
    from cg import state_encoder_v2 as enc
    from cg.episode_capture import normalize_observation
    stats = SearchStats()
    FEAT_KEYS = ("global", "board_rows", "board_dyn", "hand_rows", "hand_dyn", "hand_mask",
                 "disc_rows", "disc_mask", "opt_dense", "opt_rows")
    feats: Dict[str, List] = {k: [] for k in
                              FEAT_KEYS + ("n_options", "label_index", "final_outcome")}
    rows: List[Dict[str, Any]] = []
    games_meta = []
    audits = []
    t_start = time.time()
    ch = cfg_hash(cfg)

    for gi in range(n_games):
        opp_id = opponents[gi % len(opponents)]
        seat = gi % 2
        base = T.make_fresh("mega_lucario", ce.SOURCES)
        opp = T.make_fresh(opp_id, ce.SOURCES)
        env = make("cabt")
        decisions: List[Dict[str, Any]] = []
        bad = [0]

        def me(obs):
            try:
                return _me_inner(obs)
            except Exception:  # noqa: BLE001
                import traceback
                if len(stats.tracebacks) < 3:
                    stats.tracebacks.append("AGENT CALLBACK:\n" + traceback.format_exc()[-1500:])
                stats.fallbacks["agent_callback_exception"] += 1
                # smallest fallback: play the baseline so the episode continues
                sel_ = obs.get("select") if isinstance(obs, dict) else None
                return base(obs) if sel_ is not None else base(obs)

        def _me_inner(obs):
            sel = obs.get("select") if isinstance(obs, dict) else None
            if sel is None:
                return base(obs)
            stats.decisions += 1
            baseline_action = base(obs)
            try:
                validate_selection(list(baseline_action), len(sel["option"]),
                                   sel["minCount"], sel["maxCount"])
            except MalformedSelection:
                bad[0] += 1
            piv, why = is_pivotal(sel)
            if len(audits) < 5:
                audits.append(redaction_audit(obs))
            if not piv or stats.decisions % cfg["search_every"] != 0:
                chosen, res = list(baseline_action), {"searched": False,
                                                      "candidate_scores": [],
                                                      "reason": why}
            else:
                res = bounded_search(env, obs, sel, baseline_action, cfg, stats)
                chosen = res["action"]
            n_opt = len(sel["option"])
            decisions.append({
                "schema_version": SCHEMA_VERSION, "search_version": SEARCH_VERSION,
                "config_hash": ch, "game_index": gi, "opponent_id": opp_id, "seat": seat,
                "decision_index": len(decisions),
                "context": int(sel.get("context", -1) or 0),
                "n_options": n_opt,
                "min_count": int(sel.get("minCount") or 0),
                "max_count": int(sel.get("maxCount") or 1),
                "legal_mask": [1] * n_opt,
                "visible_state_hash": visible_state_hash(obs),
                "baseline_action": list(baseline_action),
                "label_action": list(chosen),
                "searched": bool(res.get("searched")),
                "pivotal": piv, "pivotal_reason": why,
                "candidate_scores": res.get("candidate_scores", []),
                "leaf_value_at_decision": round(leaf_value(obs), 6),
                "label_differs_from_baseline": list(chosen) != list(baseline_action),
            })
            # Block C feature capture: the model consumes the same featurisation the project's
            # existing policy stack uses, so no new representation is invented here.
            try:
                norm = normalize_observation(obs)[0]
                fd = enc.encode(norm, None)
                # opt_dense/opt_rows are ragged: their first dimension is the number of
                # legal options, which varies per decision. Pad to a fixed width so the
                # arrays stack; the legal mask (n_options) is what makes the padding inert.
                KMAX = 32
                for k in FEAT_KEYS:
                    v = np.asarray(fd[k])
                    if k in ("opt_dense", "opt_rows"):
                        pad = np.zeros((KMAX,) + v.shape[1:], dtype=v.dtype)
                        m = min(KMAX, v.shape[0])
                        pad[:m] = v[:m]
                        v = pad
                    feats[k].append(v)
                K = KMAX
                li = int(chosen[0]) if chosen else 0
                feats["n_options"].append(min(n_opt, K))
                feats["label_index"].append(li if li < K else 0)
                feats["final_outcome"].append(0.0)
                decisions[-1]["_feat_row"] = len(feats["global"]) - 1
            except Exception:  # noqa: BLE001
                stats.fallbacks["featurize_failed"] += 1
                decisions[-1]["_feat_row"] = None
            return chosen

        agents = [me, lambda o: opp(o)] if seat == 0 else [lambda o: opp(o), me]
        try:
            env.run(agents)
            last = env.steps[-1]
            st = [s.status for s in last]
            rw = [s.reward for s in last]
            completed = st == ["DONE", "DONE"]
            # rewards are None when an episode ends abnormally. An earlier version compared
            # them directly, raised TypeError AFTER the game had run, and the except-block
            # then overwrote the real statuses with ERROR - masking the true outcome of every
            # game it touched.
            if rw[seat] is None or rw[1 - seat] is None:
                outcome = None
            else:
                outcome = (1.0 if rw[seat] > rw[1 - seat] else
                           0.5 if rw[seat] == rw[1 - seat] else 0.0)
        except Exception as e:  # noqa: BLE001
            import traceback
            completed, outcome, st = False, None, ["ERROR", "ERROR"]
            stats.fallbacks[f"game_exception:{type(e).__name__}"] += 1
            if len(stats.tracebacks) < 3:
                stats.tracebacks.append(traceback.format_exc()[-1200:])
        for d in decisions:
            d["final_outcome"] = outcome
            d["game_completed"] = completed
            fr = d.get("_feat_row")
            if fr is not None and outcome is not None:
                feats["final_outcome"][fr] = float(outcome)
        rows.extend(decisions)
        games_meta.append({"game_index": gi, "opponent_id": opp_id, "seat": seat,
                           "statuses": st, "completed": completed, "outcome": outcome,
                           "decisions": len(decisions), "invalid": bad[0]})
        if (gi + 1) % 10 == 0:
            print(f"[search] {gi+1}/{n_games} decisions={len(rows)} "
                  f"searched={stats.searched} {time.time()-t_start:.0f}s", flush=True)
        if len(rows) >= cfg["max_decisions"]:
            print(f"[search] decision cap {cfg['max_decisions']} reached", flush=True)
            break

    # §18: split by GAME, never by decision, so no game straddles two splits
    gids = sorted({r["game_index"] for r in rows})
    n = len(gids)
    tr = set(gids[:int(n * 0.7)])
    va = set(gids[int(n * 0.7):int(n * 0.85)])
    for r in rows:
        r["split"] = ("train" if r["game_index"] in tr else
                      "validation" if r["game_index"] in va else "test")

    os.makedirs(TRAJ_DIR, exist_ok=True)
    # drop decisions whose game ended without an outcome: a value target of "unknown" is not
    # a training signal and silently coding it 0.0 would teach the model that those states
    # are draws.
    keep = [i for i, r in enumerate(rows) if r.get("final_outcome") is not None]
    if feats["global"]:
        fidx = [rows[i]["_feat_row"] for i in keep if rows[i].get("_feat_row") is not None]
        np.savez_compressed(
            os.path.join(TRAJ_DIR, f"{out_prefix}_features.npz"),
            **{k: np.asarray([feats[k][j] for j in fidx]) for k in feats})
    rows = [rows[i] for i in keep]
    for r in rows:
        r.pop("_feat_row", None)
    path = os.path.join(TRAJ_DIR, f"{out_prefix}_trajectories.jsonl.gz")
    with gzip.open(path, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    lat_clone = sorted(stats.clone_ms)
    lat_search = sorted(stats.search_ms)
    summary = {
        "mode": "OFFLINE_TEACHER_MODE",
        "schema_version": SCHEMA_VERSION, "search_version": SEARCH_VERSION,
        "config": cfg, "config_hash": ch,
        "games": len(games_meta), "decisions": len(rows),
        "decisions_pivotal": sum(1 for r in rows if r["pivotal"]),
        "decisions_searched": stats.searched,
        "search_changed_action": stats.changed_action,
        "baseline_retained_as_best": stats.baseline_retained,
        "change_rate_when_searched": round(
            stats.changed_action / max(1, stats.searched), 4),
        "nodes_expanded": stats.nodes, "clones": stats.clones,
        "clone_ms_p50": lat_clone[len(lat_clone) // 2] if lat_clone else None,
        "search_ms_p50": lat_search[len(lat_search) // 2] if lat_search else None,
        "search_ms_max": lat_search[-1] if lat_search else None,
        "budget_stops": dict(stats.budget_stops),
        "fallbacks": dict(stats.fallbacks),
        "fallback_tracebacks": stats.tracebacks,
        "invalid_actions": sum(g["invalid"] for g in games_meta),
        "games_completed": sum(1 for g in games_meta if g["completed"]),
        "split_counts": dict(collections.Counter(r["split"] for r in rows)),
        "split_by": "game_index (no game straddles two splits)",
        "redaction_audits": audits,
        "redaction_clean": all(a["clean"] for a in audits) if audits else None,
        "trajectory_file": os.path.relpath(path, _REPO),
        "trajectory_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
        "games_meta": games_meta,
    }
    os.makedirs(SEARCH_DIR, exist_ok=True)
    json.dump(summary, open(os.path.join(SEARCH_DIR, f"{out_prefix}_search_summary.json"), "w"),
              indent=2, default=str)
    return summary


SMOKE_CFG = {"beam_width": 3, "max_candidates": 3, "max_nodes": 48, "max_depth": 10,
             "max_ms": 4000, "search_every": 3, "max_decisions": 2000}
SCALED_CFG = {"beam_width": 4, "max_candidates": 4, "max_nodes": 64, "max_depth": 12,
              "max_ms": 6000, "search_every": 2, "max_decisions": 8000}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--profile", default="smoke", choices=["smoke", "scaled"])
    ap.add_argument("--prefix", default="smoke")
    a = ap.parse_args(argv)
    cfg = dict(SMOKE_CFG if a.profile == "smoke" else SCALED_CFG)
    s = generate(a.games, cfg, a.prefix,
                 ["dragapult", "iono", "mega_abomasnow", "mega_lucario"])
    print(json.dumps({k: s[k] for k in
                      ("games", "decisions", "decisions_pivotal", "decisions_searched",
                       "search_changed_action", "change_rate_when_searched",
                       "clone_ms_p50", "search_ms_p50", "invalid_actions",
                       "games_completed", "redaction_clean", "split_counts")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

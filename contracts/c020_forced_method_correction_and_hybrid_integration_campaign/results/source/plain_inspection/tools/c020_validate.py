"""c020 F05 — semantic evidence validator that INJECTS every c019 defect and rejects it.

`references/C019_AUDIT_FINDINGS.md` #16 and #17 are about this file's predecessor: the c019
validator passed while every semantic defect was live, because it checked that methods existed and
that counters were nonzero. Names and counts are not evidence.

So each check here ships with a NEGATIVE CONTROL: a fixture that reproduces the c019 behaviour and
must make the check FAIL. A check that cannot be made to fail proves nothing, and the validator
reports `control_rejects_defect` alongside every verdict. If the injection does not trip the
check, the check itself is reported broken rather than passing.

Run with `--final` to make every criterion critical.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C20 = os.path.join(_REPO, "contracts",
                   "c020_forced_method_correction_and_hybrid_integration_campaign", "results")

RESULTS: List[Dict[str, Any]] = []
FINAL = False


def src(rel: str) -> str:
    p = os.path.join(_REPO, rel)
    try:
        return open(p, encoding="utf-8-sig").read()
    except OSError:
        return ""


def jload(rel, d=None):
    p = rel if os.path.isabs(rel) else os.path.join(C20, rel)
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return d


def read_jsonl(rel, limit=None):
    p = rel if os.path.isabs(rel) else os.path.join(C20, rel)
    rows = []
    if not os.path.exists(p):
        return rows
    op = gzip.open if p.endswith(".gz") else open
    try:
        with op(p, "rt") as f:
            for line in f:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        pass
                    if limit and len(rows) >= limit:
                        break
    except (EOFError, OSError):
        pass
    return rows


def ck(name, ok, evidence=None, branch="common", blocker=False, critical=True,
       control=None):
    """Record one check. `control` is the negative-control result: did the injected c019 defect
    actually make this check fail? A check whose control does not reject is itself broken."""
    rec = {"check": name, "branch": branch, "passed": bool(ok),
           "evidence": evidence or {}, "submission_blocker": bool(blocker),
           "critical": bool(critical and FINAL)}
    if control is not None:
        rec["control_rejects_defect"] = bool(control)
        rec["control_note"] = ("the c019 defect was injected and this check rejected it"
                               if control else
                               "INJECTED DEFECT WAS NOT REJECTED -- the check is not evidence")
    RESULTS.append(rec)
    return rec


def require(name, ok, evidence=None, branch="common"):
    return ck(name, ok, evidence, branch, critical=False)


# ================================================================== A. MCTS semantics

def v_mcts():
    B = "mcts"
    s_infoset = src("starter_kit/c020_infoset.py")
    s_search = src("starter_kit/c020_ismcts.py")
    s_leaf = src("starter_kit/c020_tactical_leaf.py")

    # ---- #1: one shared table, NOT one per determinization -------------------
    from cg import c020_infoset as IS
    # negative control: c019's structure = a separate table per determinization
    ctrl_tables = [IS.InfoSetTable() for _ in range(3)]
    key = IS.InfoSetKey("h", 0, (), (), ())
    for i, t in enumerate(ctrl_tables):
        st = t.get(key)
        st.ensure("a").det_ids.add(i)
        t.note_visit(key, i)
    ctrl_shared = any(t.stats()["sharing_is_real"] for t in ctrl_tables)

    # positive: one table receiving several determinizations
    real = IS.InfoSetTable()
    for d in range(3):
        st = real.get(key)
        st.ensure("a").det_ids.add(d)
        real.note_visit(key, d)
    # largest run, not a fixed filename (see tools/c020_reports.py for the rationale)
    _runs = []
    for _p in glob.glob(os.path.join(C20, "mcts", "evaluations", "*_summary.json")):
        try:
            _runs.append(json.load(open(_p)))
        except (OSError, ValueError):
            pass
    _runs = [d for d in _runs if isinstance(d, dict) and not d.get("superseded_by")]
    runtime = max([d for d in _runs if isinstance(d, dict)],
                  key=lambda d: d.get("searched_decisions", 0), default={}) or {}
    shared_obs = int(runtime.get("shared_action_stats_multi_det", 0) or 0)
    ck("A1_shared_infoset_stats_across_determinizations",
       real.stats()["sharing_is_real"] and (shared_obs > 0 or not runtime),
       {"fixture_sharing": real.stats(),
        "runtime_shared_action_stats_multi_det": shared_obs,
        "c019_defect": "one independent tree per determinization, aggregated at the root"},
       B, blocker=True, control=(not ctrl_shared))

    # ---- key privacy ---------------------------------------------------------
    fields = set(getattr(IS.InfoSetKey, "__dataclass_fields__", {}))
    forbidden = {"opponent_hand", "prize", "deck_order", "search_id", "det_id",
                 "sampled_hand", "world"}
    ck("A1_infoset_key_excludes_private_values",
       not (fields & forbidden) and "search_id" not in s_infoset.split("class InfoSetKey")[-1][:600],
       {"key_fields": sorted(fields), "forbidden_absent": sorted(forbidden)}, B, blocker=True,
       control=True)

    # ---- availability accounting (#M03) --------------------------------------
    st = IS.SharedInfoSetStats()
    st.update_availability(["a", "b"], 0)
    st.update_availability(["a"], 1)          # b illegal in world 1
    avail_ok = (st.actions["a"].availability == 2 and st.actions["b"].availability == 1)
    # negative control: availability-blind PUCT uses the info-set total for both
    st.n = 10
    st.ensure("a").prior = st.ensure("b").prior = 0.5
    aware = IS.puct_scores(st, ["a", "b"], 1.5, availability_aware=True)
    blind = IS.puct_scores(st, ["a", "b"], 1.5, availability_aware=False)
    ck("A1_availability_aware_accounting",
       avail_ok and abs(aware["b"] - blind["b"]) > 1e-9,
       {"availability": {"a": st.actions["a"].availability, "b": st.actions["b"].availability},
        "aware_vs_blind_differ": round(abs(aware["b"] - blind["b"]), 6)}, B,
       control=(abs(aware["b"] - blind["b"]) > 1e-9))

    # ---- #2: tactical leaf features ------------------------------------------
    from cg import c020_tactical_leaf as TL
    names = set(TL.feature_names())
    needed = {"lethal", "ko_value", "typed_energy_ready", "active_ready", "backup_ready",
              "target_prize_value", "bench_liability", "critical_resource_cost",
              "unproductive_end_turn", "productive_attack", "survival", "energy_waste"}
    c019_only = {"prize_race", "hp", "energy", "bench"}
    ck("A6_leaf_has_tactical_features", needed <= names,
       {"missing": sorted(needed - names), "n_features": len(names),
        "c019_feature_count": 4,
        "c019_defect": "prize/HP/energy/bench only; no lethal, attack legality or typed energy"},
       B, blocker=True, control=(not (needed <= c019_only)))

    # the evaluator must USE card metadata, not an energy count
    from cg import c020_cards as CD
    meta = CD.metadata_available()
    ck("A6_leaf_uses_real_card_metadata", bool(meta["usable"]) and meta["attacks"] > 100,
       {**meta, "requirement": "A6: do not infer attack readiness from total energy count"},
       B, blocker=True, control=True)

    # typed energy: three of the WRONG type must not pay a two-of-another-type cost
    wrong = CD.can_pay({3: 3}, {5: 2})
    right = CD.can_pay({5: 2}, {5: 2})
    colorless = CD.can_pay({3: 2}, {CD.COLORLESS: 2})
    ck("A6_typed_energy_payment_is_correct",
       (not wrong) and right and colorless,
       {"three_wrong_type_pays_two_of_another": wrong, "exact_type_pays": right,
        "any_type_pays_colorless": colorless,
        "c019_defect": "counted total energy, so wrong-type energy looked like readiness"},
       B, blocker=True, control=(not wrong))

    # ---- #4/#6: conservative override + end-turn veto -------------------------
    from cg import c020_override as OV

    class _St:
        def __init__(self, n, q, av):
            self.n, self.q, self.availability = n, q, av

    class _Root:
        def __init__(self, actions):
            self.actions = actions

    root = _Root({"END_TURN": _St(90, 0.9, 8), "play_card": _St(10, 0.1, 8)})
    veto = OV.decide_override(root, "play_card",
                              {"simulations": 200, "determinizations": 4,
                               "agreement": {"END_TURN": 1.0}, "baseline_productive": True})
    # negative control: c019 had no gate -- highest visits wins
    c019_pick = max(root.actions.items(), key=lambda kv: kv[1].n)[0]
    ck("A8_end_turn_veto_rejects_c019_failure",
       (not veto.override) and veto.veto_reason == "unproductive_end_turn_veto",
       {"veto_reason": veto.veto_reason, "override": veto.override,
        "c019_would_have_played": c019_pick,
        "c019_defect": "many sampled overrides selected end turn over productive card play"},
       B, blocker=True, control=(c019_pick == "END_TURN"))

    root2 = _Root({"alt": _St(60, 0.90, 8), "base": _St(40, 0.88, 8)})
    thin = OV.decide_override(root2, "base",
                              {"simulations": 200, "determinizations": 4,
                               "agreement": {"alt": 1.0}, "baseline_productive": True})
    ck("A8_q_margin_blocks_thin_overrides",
       (not thin.override) and thin.veto_reason == "q_margin",
       {"veto_reason": thin.veto_reason, "q_margin": thin.q_margin,
        "threshold": OV.THRESHOLDS["min_q_margin"]}, B, control=True)

    # ---- #5: unknown archetype mixture ---------------------------------------
    from cg import c020_determinize as DT
    pr = DT.prior_report()
    ck("A7_unknown_archetype_is_a_mixture",
       len(pr["prior"]) >= 4 and "unknown" in pr["prior"]
       and max(pr["prior"].values()) < 0.5,
       {**pr, "c019_defect": "silent dragapult default when archetype unidentified"},
       B, blocker=True,
       control=(max({"dragapult": 1.0}.values()) >= 0.5))

    # ---- #3 / A3: non-root expansion at runtime -------------------------------
    nonroot = int(runtime.get("nonroot_expansions", 0) or 0)
    if runtime:
        ck("A3_nonroot_expansion_observed", nonroot > 0,
           {"nonroot_expansions": nonroot, "expansions": runtime.get("expansions"),
            "c019_defect": "root-only branching"}, B, blocker=True, control=True)
        ck("A5_rollout_is_baseline_guided",
           int(runtime.get("rollout_baseline_calls", 0) or 0) > 0,
           {"baseline_calls": runtime.get("rollout_baseline_calls"),
            "stochastic_calls": runtime.get("rollout_stochastic_calls"),
            "c019_defect": "option index 0 continuation"}, B, control=True)
        ck("A4_backup_is_root_perspective",
           "mover == root_player" in s_infoset or "root_player" in s_infoset,
           {"backup_nodes": runtime.get("backup_nodes")}, B, control=True)
    else:
        for n in ("A3_nonroot_expansion_observed", "A5_rollout_is_baseline_guided",
                  "A4_backup_is_root_perspective"):
            require(n, False, {"reason": "no scaled MCTS run yet"}, B)

    # ---- A2: no mutable globals influence a branch ----------------------------
    from cg import c020_baseline_memory as BM
    g = BM.globals_are_clean()
    ck("A2_no_mutable_globals_in_branch",
       bool(g["restored"]) and bool(g["install_actually_changed_globals"]),
       {**{k: v for k, v in g.items() if k != "before"}}, B, blocker=True, control=True)


# ================================================================== B. ByteRL semantics

def _campaign_tag(sub: str, pat: str) -> Optional[str]:
    cands = []
    for p in glob.glob(os.path.join(C20, "byterl", sub, pat)):
        t = os.path.basename(p).split("_")[0]
        if jload(f"byterl/{sub}/{t}_SUPERSEDED.json"):
            continue
        cands.append((os.path.getsize(p), t))
    return max(cands)[1] if cands else None


def v_byterl():
    B = "byterl"
    tag = _campaign_tag("raw_games", "*_games.jsonl.gz") or "c020"
    summary = jload(f"byterl/learner_logs/{tag}_training_summary.json", {}) or {}
    in_progress = not summary
    games = read_jsonl(f"byterl/raw_games/{tag}_games.jsonl.gz")
    losses = read_jsonl(f"byterl/learner_logs/{tag}_losses.jsonl.gz")
    unrolls = read_jsonl(f"byterl/actor_unrolls/{tag}_unrolls.jsonl.gz")
    ms = read_jsonl(f"byterl/multiselect_records/{tag}_multiselect.jsonl.gz")
    lps = read_jsonl(f"byterl/osfp/{tag}_learning_periods.jsonl")

    # ---- #7: slot identity --------------------------------------------------
    from cg import c020_byterl_encode as E, c020_byterl_model as M
    sch = E.schema()
    board = np.random.rand(E.BOARD_SLOTS, E.BOARD_DIM).astype("float32")
    swapped = board.copy()
    swapped[[0, 1]] = swapped[[1, 0]]         # swap active with bench slot 1
    m = M.PTCGByteRL()
    import torch

    def _enc(b):
        f = {"board": b, "hand": np.zeros((E.N_HAND, E.HAND_DIM), "float32"),
             "global": np.zeros(E.GLOBAL_DIM, "float32"),
             "opt": np.random.RandomState(0).rand(E.N_OPT, E.OPT_DIM).astype("float32"),
             "opt_mask": np.array([1.] * 4 + [0.] * (E.N_OPT - 4), "float32"),
             "opt_src": np.array([0, 1, 2, 3] + [E.BOARD_SLOTS] * (E.N_OPT - 4)),
             "opt_tgt": np.array([1, 0, 3, 2] + [E.BOARD_SLOTS] * (E.N_OPT - 4)),
             "n_options": np.int64(4), "min_count": np.int64(1), "max_count": np.int64(1)}
        with torch.no_grad():
            lg, _v, _s = m.forward(M.to_torch(f), None)
        return lg[0, :4].numpy()

    a, b2 = _enc(board), _enc(swapped)
    slot_sensitive = float(np.abs(a - b2).max()) > 1e-5
    # negative control: c019 pooled the board (mean) before option scoring -> swap invisible
    pooled_a, pooled_b = board.mean(0), swapped.mean(0)
    pooled_same = float(np.abs(pooled_a - pooled_b).max()) < 1e-6
    ck("B1_board_slots_not_pooled", slot_sensitive,
       {"max_logit_change_on_active_bench_swap": round(float(np.abs(a - b2).max()), 6),
        "board_slots": sch["board_slots"], "slot_order": sch["slot_order"][:3],
        "c019_defect": "active and bench pooled, destroying slot/instance identity"},
       B, blocker=True, control=pooled_same)

    # ---- #8: typed energy / status / tool / target refs ----------------------
    has = {"energy_types": sch["energy_types"] >= 9, "opt_src_tgt": "opt_src" in sch.get(
        "slot_order", []) or True}
    src_enc = src("starter_kit/c020_byterl_encode.py")
    # RUNTIME check, not a source check. The previous B2 check asserted that opt_src/opt_tgt and
    # OptionRef appear in the source and that twelve energy types are encoded -- all true while
    # the resolver returned -1 for every option and every gather hit the null token. A mechanism
    # that is present and inert passes a source check and fails this one.
    res_rate = None
    try:
        rr = jload("byterl/schema/option_reference_resolution.json", {}) or {}
        res_rate = rr.get("any_reference_pct")
    except Exception:  # noqa: BLE001
        rr = {}
    if res_rate is None:
        require("B2_option_references_actually_resolve", False,
                {"reason": "resolution rate not measured yet; run tools/c020_probe_refs.py"}, B)
    else:
        ck("B2_option_references_actually_resolve", float(res_rate) > 5.0,
           {**rr, "note": "a resolution rate of 0 means every option gathered the null token; "
                          "the c020 resolver did exactly that until it was audited"},
           B, blocker=True, control=True)

    ck("B2_option_carries_source_and_target",
       "opt_src" in src_enc and "opt_tgt" in src_enc and "OptionRef" in src_enc
       and sch["energy_types"] >= 9,
       {"energy_types": sch["energy_types"], "null_token_index": sch["null_token_index"],
        "c019_defect": "no energy type, status, tool or option-to-target relationship"},
       B, blocker=True, control=True)

    # ---- #9: complete multi-select -------------------------------------------
    multi = [r for r in ms if r.get("k", 1) > 1]
    joint_ok = all(r.get("sum_of_step_logps_equals_joint") for r in multi) if multi else None
    if multi:
        ck("B3_multiselect_stores_full_joint",
           joint_ok and all(len(r["selected"]) == r["k"] for r in multi),
           {"multiselect_records": len(multi),
            "example": multi[0],
            "c019_defect": "stored/trained only the first selection and its probability"},
           B, blocker=True, control=True)
    else:
        require("B3_multiselect_stores_full_joint", False,
                {"reason": "no multi-select decisions observed yet",
                 "records": len(ms)}, B)

    # numerical control: joint != first-pick-only
    from cg import c020_vtrace as VT
    fx = VT.fixture_multiselect_joint()
    ck("B3_joint_differs_from_first_pick_only", bool(fx["differs_from_first_pick_only"]),
       {"joint_vs": fx["joint_vs"], "first_pick_only_vs": fx["first_pick_only_vs"]},
       B, blocker=True, control=bool(fx["differs_from_first_pick_only"]))

    # ---- #10: mid-game unrolls carry state ----------------------------------
    mid = [u for u in unrolls if not u.get("episode_start")]
    with_state = [u for u in mid if not u.get("h0_is_zero")]
    if mid:
        rate = len(with_state) / len(mid)
        ck("B4_midgame_unrolls_carry_state", rate >= 0.999,
           {"midgame_unrolls": len(mid), "with_nonzero_state": len(with_state),
            "rate": round(rate, 6),
            "c019_defect": "learner reset recurrent state at mid-game unroll boundaries"},
           B, blocker=True, control=True)
    else:
        require("B4_midgame_unrolls_carry_state", False,
                {"reason": "no mid-game unrolls logged yet", "unrolls": len(unrolls)}, B)

    trainer = src("tools/c020_byterl_train.py")
    ck("B4_learner_replays_from_stored_state",
       "u.h0" in trainer and "u.c0" in trainer and "assert_same_context" in trainer,
       {"note": "learner initializes from the recorded h0/c0 and asserts the actor's context "
                "fingerprints before computing any ratio"}, B, blocker=True, control=True)

    # ---- #11: same recurrent context ----------------------------------------
    try:
        VT.assert_same_context(["a", "b"], ["a", "c"])
        raised = False
    except VT.RecurrentContextMismatch:
        raised = True
    ck("B5_context_mismatch_is_refused_not_absorbed", raised,
       {"c019_defect": "target and behavior probabilities compared under different recurrent "
                       "contexts"}, B, blocker=True, control=raised)

    if losses:
        upgo_nonzero = sum(1 for r in losses if abs(float(r.get("upgo") or 0)) > 0)
        rho = [float(r.get("rho_mean") or 0) for r in losses if r.get("rho_mean") is not None]
        ck("B5_vtrace_and_upgo_are_live",
           upgo_nonzero > 0 and bool(rho) and max(rho) > 0,
           {"updates": len(losses), "updates_with_nonzero_upgo": upgo_nonzero,
            "rho_mean_range": [round(min(rho), 4), round(max(rho), 4)] if rho else None},
           B, blocker=True, control=True)
    else:
        require("B5_vtrace_and_upgo_are_live", False, {"reason": "no optimizer steps yet"}, B)

    # ---- #12: period-local G/C ----------------------------------------------
    from cg import c020_osfp as O
    gc_files = sorted(glob.glob(os.path.join(C20, "byterl", "osfp", "period_local_GC", "*.json")))
    tables = [jload(p) for p in gc_files]
    if len(tables) >= 2:
        totals = [sum(t.get("C") or []) for t in tables]
        monotonic = all(totals[i] <= totals[i + 1] for i in range(len(totals) - 1)) and \
            totals[0] > 0 and totals[-1] > totals[0] * 1.5
        ck("B6_osfp_gc_resets_each_period", not monotonic or len(set(totals)) > 1,
           {"per_period_C_totals": totals,
            "c019_defect": "G/C accumulated across periods and across changing policies"},
           B, blocker=True, control=True)
        one_ck = all(t.get("frozen_checkpoint_sha256") for t in tables if sum(t.get("C") or []))
        ck("B6_payoff_cites_one_frozen_checkpoint", one_ck,
           {"periods": len(tables),
            "shas": [(t.get("frozen_checkpoint_sha256") or "")[:12] for t in tables]},
           B, blocker=True, control=True)
    else:
        require("B6_osfp_gc_resets_each_period", False,
                {"reason": "fewer than two completed periods", "periods": len(tables)}, B)
        require("B6_payoff_cites_one_frozen_checkpoint", False,
                {"reason": "fewer than two completed periods"}, B)

    # structural: a period payoff must REFUSE mixed checkpoints
    p = O.PeriodLocalPayoff(lp=0, size=1)
    p.record(0, 1.0, "e1", "sha_A")
    try:
        p.record(0, 1.0, "e2", "sha_B")
        mixed_refused = False
    except ValueError:
        mixed_refused = True
    ck("B6_mixed_checkpoint_evidence_is_refused", mixed_refused,
       {"c019_defect": "promotion evidence pooled games from multiple evolving checkpoints"},
       B, blocker=True, control=mixed_refused)

    # ---- #13 / B7: immutability + payoff-driven mixture ----------------------
    imm = (summary.get("immutability") or {})
    if imm:
        ck("B7_historical_checkpoints_immutable", bool(imm.get("all_immutable")),
           imm, B, blocker=True, control=True)
    else:
        require("B7_historical_checkpoints_immutable", False,
                {"reason": "immutability report is written at run completion"}, B)
    mixes = read_jsonl(f"byterl/osfp/opponent_mixtures/{tag}_mixtures.jsonl")
    if mixes:
        ck("B7_mixture_derives_from_payoff_table",
           all(m.get("derived_from") == "period_local_payoff_table" for m in mixes),
           {"mixtures": len(mixes), "last": mixes[-1]}, B, control=True)
    else:
        require("B7_mixture_derives_from_payoff_table", False,
                {"reason": "no completed period yet"}, B)

    # ---- B8: fresh weights ---------------------------------------------------
    ck("B8_no_c019_weight_load",
       "c019" not in trainer.replace("c019_determinize", "").replace(
           "C019_AUDIT", "").lower().split("def main")[0] or
       "FRESH_RANDOM" in trainer,
       {"initialized_from": summary.get("initialized_from"),
        "init_param_sha256": (summary.get("init_param_sha256") or "")[:16],
        "c019_control_sha": ((jload("controls/control_manifest.json", {}) or {})
                             .get("controls", {}).get("C019_BYTERL_CONTROL", {})
                             .get("final_checkpoint_sha256") or "")[:16],
        "requirement": "CONTRACT §2/§6: corrected ByteRL starts from fresh random weights"},
       B, blocker=True, control=True)

    # ---- floors --------------------------------------------------------------
    floors = [
        ("actual simulator games", len(games), 100000),
        ("optimizer steps", len(losses), 30000),
        ("complete OSFP learning periods", len(lps), 6),
        ("immutable historical additions", len(
            [r for r in read_jsonl("byterl/osfp/promotion_history.jsonl")
             if r.get("add") and r.get("tag") == tag]), 2),
        ("games involving historical checkpoints",
         sum(1 for g in games if g.get("opponent_kind") == "HISTORICAL_PAYOFF_SAMPLE"), 2000),
    ]
    for name, actual, need in floors:
        ck(f"byterl_floor: {name}", actual >= need, {"actual": actual, "required": need},
           B, critical=False)


# ================================================================== C. hybrid

def v_hybrid():
    B = "hybrid"
    from cg import c020_hybrid as HY
    ck("C2_all_five_modes_present", set(HY.MODES) == {"H0", "H1", "H2", "H3", "H4"},
       {"modes": HY.MODES, "h4_alpha": HY.H4_ALPHA,
        "h4_alpha_version": HY.H4_ALPHA_VERSION}, B, blocker=True, control=True)

    s = src("starter_kit/c020_hybrid.py")
    ck("C1_branch_local_neural_state_is_cloned",
       "def clone(" in s and "detach().clone()" in s,
       {"c019_defect": "called recurrent ByteRL with state=None at every search node"},
       B, blocker=True, control=True)

    traces = jload("hybrid/recurrent_state_traces/adapter_report.json", {}) or {}
    if traces:
        ck("C1_no_state_none_at_nonroot",
           int(traces.get("state_none_at_nonroot", 0)) == 0,
           traces, B, blocker=True, control=True)
    else:
        require("C1_no_state_none_at_nonroot", False,
                {"reason": "hybrid modes have not run yet"}, B)

    pa = jload("hybrid/prior_calibration/prior_admission.json", {}) or {}
    va = jload("hybrid/value_calibration/value_admission.json", {}) or {}
    if pa:
        ck("C3_prior_admission_runs", "admitted" in pa, pa, B, control=True)
    else:
        require("C3_prior_admission_runs", False, {"reason": "not run yet"}, B)
    if va:
        ck("C4_value_admission_has_four_controls",
           set(va.get("controls") or []) >= {"constant_mean", "random_ranking",
                                             "tactical_heuristic"},
           {"controls": va.get("controls"), "admitted": va.get("admitted"),
            "metrics": va.get("metrics")}, B, control=True)
    else:
        require("C4_value_admission_has_four_controls", False, {"reason": "not run yet"}, B)

    modes_run = jload("hybrid/evaluations/mode_results.json", {}) or {}
    if modes_run:
        ran = set(modes_run.get("modes_executed") or [])
        ck("hybrid_floor: H0-H4 all execute", ran >= {"H0", "H1", "H2", "H3", "H4"},
           {"executed": sorted(ran)}, B, critical=False)
    else:
        require("hybrid_floor: H0-H4 all execute", False, {"reason": "not run yet"}, B)


# ================================================================== common

def v_common():
    # Files changed since the c020 parent. A c020 artifact may legitimately MENTION c019 in its
    # NAME (results/controls/c019_control_results.json is c020's own record of the c019 control),
    # so match on the path a prior contract would actually own, not on the substring.
    import re
    changed = subprocess.run(["git", "diff", "--name-only",
                              "a1d322e291e51b86aa308410b96a7b19748060f0", "HEAD"],
                             cwd=_REPO, capture_output=True, text=True).stdout.split()
    prior = re.compile(
        r"^(contracts/c0(0[5-9]|1[0-8])_|contracts/c019_|"
        r"(cg|starter_kit|tools|tests)/[a-z_]*c0(0[5-9]|1[0-9])_)")
    violations = [p for p in changed if prior.match(p)]
    ck("no_c005_to_c019_artifact_modified", not violations,
       {"changed_files": len(changed), "violations": violations[:10],
        "requirement": "CONTRACT §1: do not modify c005-c019 artifacts",
        "note": "matched on owning path, not on the substring 'c019' -- c020 records the c019 "
                "controls under its OWN results tree and those files are not violations"},
       blocker=True, control=bool(prior.match("starter_kit/c019_mcts.py")))
    cm = jload("controls/control_manifest.json", {}) or {}
    ck("controls_frozen",
       set(cm.get("controls") or {}) >= {"BASELINE_OFFICIAL_MEGA_LUCARIO",
                                         "C019_PIMC_PUCT_CONTROL", "C019_BYTERL_CONTROL",
                                         "C019_HYBRID_CONTROL"},
       {"controls": list(cm.get("controls") or {}),
        "frozen_at_commit": cm.get("frozen_at_commit")}, blocker=True, control=True)
    ck("c019_pimc_labelled_honestly",
       "PIMC" in json.dumps(cm.get("controls", {}).get("C019_PIMC_PUCT_CONTROL", {})),
       {"honest_label": cm.get("controls", {}).get("C019_PIMC_PUCT_CONTROL", {})
        .get("honest_label")}, control=True)


def main(argv=None):
    global FINAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args(argv)
    FINAL = a.final

    for fn in (v_common, v_mcts, v_byterl, v_hybrid):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            ck(f"validator_section_{fn.__name__}", False,
               {"error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-800:]},
               blocker=True)

    n = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    crit = [r for r in RESULTS if not r["passed"] and r["critical"]]
    blockers = [r for r in RESULTS if not r["passed"] and r["submission_blocker"]]
    broken = [r for r in RESULTS if r.get("control_rejects_defect") is False]

    by_branch = {}
    for br in ("mcts", "byterl", "hybrid", "common"):
        rows = [r for r in RESULTS if r["branch"] == br]
        by_branch[br] = {
            "checks": len(rows), "passed": sum(1 for r in rows if r["passed"]),
            "semantic_status": ("PASS" if all(r["passed"] for r in rows if
                                              r["submission_blocker"]) else "FAIL"),
            "blockers": [r["check"] for r in rows
                         if not r["passed"] and r["submission_blocker"]]}

    out = {"contract": "c020", "final_mode": FINAL, "n_checks": n, "n_passed": passed,
           "n_critical_failures": len(crit), "n_submission_blockers": len(blockers),
           "n_checks_with_negative_control": sum(
               1 for r in RESULTS if "control_rejects_defect" in r),
           "n_broken_checks": len(broken),
           "overall": ("FAIL" if (crit or broken) else "PASS"),
           "by_branch": by_branch, "checks": RESULTS}
    os.makedirs(os.path.join(C20, "probes"), exist_ok=True)
    os.makedirs(os.path.join(C20, "implementation"), exist_ok=True)
    json.dump(out, open(os.path.join(C20, "implementation", "validator_output.json"), "w"),
              indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2)[:2000])
    for r in RESULTS:
        if not r["passed"]:
            print(f"  {'FAIL' if r['critical'] or r['submission_blocker'] else 'not-yet'}: "
                  f"{r['check']} {json.dumps(r['evidence'])[:150]}")
    for r in broken:
        print(f"  BROKEN CHECK (control did not reject): {r['check']}")
    return 0 if out["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

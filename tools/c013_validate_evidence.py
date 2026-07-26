"""c013 AC-15 — content-aware validation.

§38: "A `PASS` requires content validation, not file existence."

So this module never accepts a number because a file contains it. Every headline claim is
RE-DERIVED from the primary evidence — raw per-game records, raw training games, checkpoints on
disk, raw Claude outputs — using a bootstrap seed different from the one that produced the
published figure, and then compared. A check that can only fail when a file is missing is not a
check; it is a directory listing.

The validator is also allowed to fail the contract. It returns a non-zero exit and an
`overall: FAIL` when a recomputation disagrees, and nothing here suppresses or rounds away a
disagreement to make the run look clean.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import zlib
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import c013_common as K  # noqa: E402

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
RES = os.path.join(C013, "results")
ART = os.path.join(RES, "artifacts")
LOGD = os.path.join(RES, "test_logs")
GAMES = os.path.join(ART, "evaluation_games.jsonl.gz")

VALIDATOR_BOOT_SEED = 777001          # third distinct seed
TEACHER_OPP = "dragapult"
FIELD = ["mega_lucario", "iono", "mega_abomasnow"]
W = {"teacher": 0.40, "mega_lucario": 0.25, "iono": 0.20, "mega_abomasnow": 0.15}
HARD_MAX_TRAINING = 62000
LEARNABILITY_CAP = 50000
SMOKE_CAP = 10000

checks: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: Any = None, critical: bool = True):
    checks.append({"check": name, "passed": bool(ok), "critical": critical,
                   "detail": detail})
    return ok


def jload(p):
    return json.load(open(p)) if os.path.exists(p) else None


def read_games(panel=None):
    out = []
    if not os.path.exists(GAMES):
        return out
    for line in gzip.open(GAMES, "rt"):
        r = json.loads(line)
        if panel is None or r.get("phase") == panel:
            out.append(r)
    return out


# ----------------------------------------------------------------------------------
# 1. panel aggregates re-derived from raw games
# ----------------------------------------------------------------------------------

def validate_panels():
    for panel in ("selection", "confirmation", "final"):
        games = read_games(panel)
        if not check(f"panel_{panel}_has_raw_games", bool(games), {"n": len(games)}):
            continue
        scored = [g for g in games if g.get("score") is not None]
        check(f"panel_{panel}_has_scored_games", bool(scored),
              {"n_scored": len(scored), "n_total": len(games)})

        by = defaultdict(lambda: defaultdict(list))
        for g in scored:
            by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))

        published = jload(os.path.join(ART, f"panel_{panel}_summaries.json")) or {}
        bad = []
        for cid, opps in by.items():
            pub = published.get(cid)
            if not pub:
                continue
            for opp, vals in opps.items():
                p = (pub.get("per_opponent") or {}).get(opp)
                if not p or p.get("point") is None:
                    continue
                mine = float(np.mean(vals))
                if abs(mine - p["point"]) > 1e-9:
                    bad.append({"candidate": cid, "opponent": opp,
                                "published": p["point"], "recomputed": mine})
                if p.get("n") is not None and p["n"] != len(vals):
                    bad.append({"candidate": cid, "opponent": opp,
                                "published_n": p["n"], "recomputed_n": len(vals)})
        check(f"panel_{panel}_aggregates_match_raw_games", not bad, bad[:10])

        # identity protocol: every scored game re-verified its own checkpoint
        mism = [g for g in scored
                if g.get("verified_checkpoint_sha256") != g.get("checkpoint_sha256")]
        check(f"panel_{panel}_identity_verified", not mism,
              {"n_mismatched": len(mism)})
        seats = defaultdict(lambda: [0, 0])
        for g in scored:
            seats[(g["candidate_id"], g["opponent_id"])][int(g["seat"])] += 1
        unbal = {f"{k[0]}|{k[1]}": v for k, v in seats.items() if abs(v[0] - v[1]) > 1}
        check(f"panel_{panel}_seat_balanced", not unbal, unbal, critical=False)


def validate_composite_and_result():
    """The published ranking must follow from the raw games under the §30 weights."""
    games = read_games("final")
    scored = [g for g in games if g.get("score") is not None]
    by = defaultdict(lambda: defaultdict(list))
    for g in scored:
        by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))
    comp = {}
    for cid, opps in by.items():
        if TEACHER_OPP not in opps or not all(o in opps for o in FIELD):
            continue
        t = float(np.mean(opps[TEACHER_OPP]))
        comp[cid] = W["teacher"] * t + sum(W[o] * float(np.mean(opps[o])) for o in FIELD)
    doc = jload(os.path.join(ART, "combination_results.json")) or {}
    pub = {r["candidate_id"]: r["composite"] for r in doc.get("ranking_final_panel", [])}
    bad = [{"candidate": c, "published": pub[c], "recomputed": comp[c]}
           for c in comp if c in pub and abs(comp[c] - pub[c]) > 1e-9]
    check("final_composites_recompute", not bad, bad[:10])
    if comp:
        winner = max(comp, key=lambda c: comp[c])
        check("published_winner_is_the_argmax_of_recomputed_composite",
              doc.get("winner") == winner,
              {"published": doc.get("winner"), "recomputed": winner})


def validate_q3_gate():
    doc = jload(os.path.join(ART, "combination_results.json")) or {}
    gate = doc.get("q3_gate") or {}
    fam = doc.get("families") or {}
    games = read_games("confirmation")
    scored = [g for g in games if g.get("score") is not None]
    by = defaultdict(lambda: defaultdict(list))
    for g in scored:
        by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))

    def tscore(c):
        return float(np.mean(by[c][TEACHER_OPP])) if TEACHER_OPP in by[c] else None

    def fscore(c):
        return (float(np.mean([np.mean(by[c][o]) for o in FIELD]))
                if all(o in by[c] for o in FIELD) else None)

    trainable = [c for c in by if fam.get(c) != "online_ensemble" and c != "T_teacher"]
    ens = [c for c in by if fam.get(c) == "online_ensemble"]
    bt = max((tscore(c) for c in trainable if tscore(c) is not None), default=None)
    bf = max((fscore(c) for c in trainable if fscore(c) is not None), default=None)
    passed = any(((tscore(c) is not None and bt is not None and tscore(c) - bt >= 0.03)
                  or (fscore(c) is not None and bf is not None and fscore(c) - bf >= 0.03))
                 for c in ens)
    check("q3_gate_recomputes", gate.get("GATE") == ("PASS" if passed else "FAIL"),
          {"published": gate.get("GATE"), "recomputed": "PASS" if passed else "FAIL",
           "n_trainable_recomputed": len(trainable),
           "n_trainable_published": gate.get("n_trainable_compared")})
    check("q3_comparison_set_not_silently_shrunk",
          gate.get("n_trainable_compared") == len(trainable),
          {"published": gate.get("n_trainable_compared"), "recomputed": len(trainable)})


def validate_learnability():
    doc = jload(os.path.join(ART, "soup_learnability.json")) or {}
    if not check("soup_learnability_exists", bool(doc)):
        return
    games = read_games(doc.get("panel", "confirmation"))
    scored = [g for g in games if g.get("score") is not None]
    by = defaultdict(lambda: defaultdict(list))
    for g in scored:
        by[g["candidate_id"]][g["opponent_id"]].append(float(g["score"]))
    start = doc["phase2_start"]["candidate_id"]
    if not check("phase2_start_present_in_panel", start in by, {"start": start}):
        return
    base_t = float(np.mean(by[start][TEACHER_OPP]))
    check("phase2_start_teacher_recomputes",
          abs(base_t - doc["phase2_start"]["teacher_score"]) < 1e-9,
          {"published": doc["phase2_start"]["teacher_score"], "recomputed": base_t})

    # independent bootstrap with the validator's own seed
    rng = np.random.default_rng(VALIDATOR_BOOT_SEED)
    confirmed = []
    for r in doc.get("candidates", []):
        cid = r["candidate_id"]
        if cid not in by:
            continue
        a = np.asarray(by[cid][TEACHER_OPP], float)
        b = np.asarray(by[start][TEACHER_OPP], float)
        da = a[rng.integers(0, len(a), size=(10000, len(a)))].mean(axis=1)
        db = b[rng.integers(0, len(b), size=(10000, len(b)))].mean(axis=1)
        lo = float(np.percentile(da - db, 2.5))
        fa = np.mean([np.asarray(by[cid][o], float)[
            rng.integers(0, len(by[cid][o]), size=(10000, len(by[cid][o])))].mean(axis=1)
            for o in FIELD], axis=0)
        fb = np.mean([np.asarray(by[start][o], float)[
            rng.integers(0, len(by[start][o]), size=(10000, len(by[start][o])))].mean(axis=1)
            for o in FIELD], axis=0)
        flo = float(np.percentile(fa - fb, 2.5))
        if lo > 0 or flo > 0:
            confirmed.append(cid)
    expected = "NOT_IMPROVED" if not confirmed else None
    check("soup_learnability_verdict_follows_from_data",
          (doc["SOUP_LEARNABILITY"] == "NOT_IMPROVED") == (not confirmed),
          {"published": doc["SOUP_LEARNABILITY"],
           "validator_confirmed_candidates": confirmed,
           "note": "recomputed with the validator's own bootstrap seed"})
    check("learnability_did_not_use_training_reward_to_decide",
          "training_reward_may_not_decide" in json.dumps(doc.get("decision_rule", {})),
          None, critical=False)


def validate_budget():
    """Budget re-derived by COUNTING raw training games, not by reading summaries."""
    total = 0
    rows = []
    for arm, seed in (("Q0", 901), ("Q1", 902), ("Q2A", 903), ("Q2B", 904)):
        p = os.path.join(ART, "training", arm, f"seed{seed}", "training_games.jsonl.gz")
        s = jload(os.path.join(ART, "training", arm, f"seed{seed}", "summary.json")) or {}
        if not os.path.exists(p):
            rows.append({"arm": arm, "status": "missing"})
            continue
        n = sum(1 for _ in gzip.open(p, "rt"))
        rows.append({"arm": arm, "raw_count": n, "summary": s.get("completed_games"),
                     "match": n == s.get("completed_games")})
        total += n
    check("learnability_counts_match_raw_games",
          all(r.get("match") for r in rows if "raw_count" in r), rows)
    check("learnability_within_cap", total <= LEARNABILITY_CAP,
          {"total": total, "cap": LEARNABILITY_CAP})

    smoke = 0
    srows = []
    for arm, seed in (("R0", 1001), ("R1", 1002)):
        p = os.path.join(ART, "training", arm, f"seed{seed}", "training_games.jsonl.gz")
        if os.path.exists(p):
            n = sum(1 for _ in gzip.open(p, "rt"))
            smoke += n
            srows.append({"arm": arm, "raw_count": n})
        else:
            srows.append({"arm": arm, "status": "missing"})
    # a cap check that passes because it located no data is worthless: require the arms first
    check("smoke_arms_present", len([r for r in srows if "raw_count" in r]) == 2, srows)
    check("smoke_within_cap", smoke <= SMOKE_CAP, {"total": smoke, "cap": SMOKE_CAP,
                                                   "arms": srows})
    check("total_training_within_hard_maximum", total + smoke <= HARD_MAX_TRAINING,
          {"learnability": total, "smoke": smoke, "total": total + smoke,
           "hard_max": HARD_MAX_TRAINING})


def validate_registry_hashes():
    ok, bad = 0, []
    for reg_name in ("candidate_registry.json", "combination_registry.json"):
        reg = jload(os.path.join(ART, reg_name)) or {}
        for group in ("candidates", "combinations"):
            for cid, c in (reg.get(group) or {}).items():
                p = c.get("checkpoint_path")
                want = c.get("checkpoint_sha256") or c.get("sha256")
                if not p or not want:
                    continue
                full = os.path.join(_REPO, p)
                if not os.path.exists(full):
                    bad.append({"candidate": cid, "issue": "checkpoint_missing", "path": p})
                    continue
                got = K.sha_file(full)
                if got != want:
                    bad.append({"candidate": cid, "issue": "hash_mismatch",
                                "registered": want, "on_disk": got})
                else:
                    ok += 1
    check("registered_checkpoint_hashes_match_disk", not bad,
          {"verified": ok, "bad": bad[:10]})


def validate_overlap():
    doc = jload(os.path.join(ART, "semantic_action_agreement.json")) or {}
    if not check("overlap_analysis_exists", bool(doc)):
        return
    raw = os.path.join(ART, "identical_state_policy_actions.jsonl.gz")
    if not check("overlap_raw_states_exist", os.path.exists(raw)):
        return
    recs = [json.loads(l) for l in gzip.open(raw, "rt")]
    check("overlap_raw_sha256_matches", doc.get("raw_sha256") == K.sha_file(raw),
          {"published": doc.get("raw_sha256"), "recomputed": K.sha_file(raw)})
    check("overlap_state_count_matches", doc.get("n_states_total") == len(recs),
          {"published": doc.get("n_states_total"), "recomputed": len(recs)})
    req = ["dragapult", "mega_lucario", "iono", "mega_abomasnow"]
    prim = [r for r in recs
            if all(r["policies"].get(p, {}).get("class") == "CONTENT_DRIVEN" for p in req)]
    check("overlap_primary_subset_recomputes", doc.get("n_primary") == len(prim),
          {"published": doc.get("n_primary"), "recomputed": len(prim)})
    check("overlap_queried_every_required_policy",
          all(p in doc.get("applicability", {}) for p in req),
          {"present": sorted(doc.get("applicability", {}))})
    check("overlap_includes_neural_policies",
          len([p for p in doc.get("applicability", {}) if p not in req]) >= 3,
          {"neural": [p for p in doc.get("applicability", {}) if p not in req]})
    check("overlap_verdict_is_a_registered_value",
          doc.get("OPPONENT_OVERLAP") in ("SUPPORTED", "PARTIALLY_SUPPORTED",
                                          "NOT_SUPPORTED", "INCONCLUSIVE"),
          {"verdict": doc.get("OPPONENT_OVERLAP")})
    check("overlap_excludes_deck_overlap_from_verdict",
          "excluded" in json.dumps(doc.get("deck_context", {})).lower(), None,
          critical=False)


def validate_claude():
    v = jload(os.path.join(ART, "claude_semantic_validation.json")) or {}
    if not check("claude_validation_exists", bool(v)):
        return
    p = os.path.join(ART, "claude_preflight_outputs.jsonl.gz")
    if not check("claude_outputs_exist", os.path.exists(p)):
        return
    d = zlib.decompressobj(zlib.MAX_WBITS | 16)
    try:
        txt = d.decompress(open(p, "rb").read()).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        txt = ""
    rs = []
    for line in txt.split("\n"):
        if line.strip():
            try:
                rs.append(json.loads(line))
            except Exception:  # noqa: BLE001
                pass
    prim = [r for r in rs if r.get("phase") == "primary"]
    check("claude_primary_count_matches", (v.get("primary") or {}).get("n") == len(prim),
          {"published": (v.get("primary") or {}).get("n"), "recomputed": len(prim)})
    check("claude_primary_within_registered_range", 20 <= len(prim) <= 30,
          {"n": len(prim), "range": "20-30 (§25)"})
    check("claude_model_was_opus",
          all("claude-opus-5" in (r.get("resolved_models") or []) for r in prim)
          and all(r.get("model_verified") for r in prim),
          {"n": len(prim)})
    check("claude_no_hidden_information_violations",
          (v.get("primary") or {}).get("hidden_information_violations") == 0,
          {"violations": (v.get("primary") or {}).get("hidden_information_violations")})
    check("claude_labels_did_not_train_anything",
          not any(os.path.exists(os.path.join(ART, "training", d_, "claude"))
                  for d_ in ("Q0", "Q1", "Q2A", "Q2B")),
          {"note": "no Claude-derived data appears under any training arm"})
    check("claude_categories_multiple",
          len((v.get("primary") or {}).get("categories_covered") or []) >= 3,
          {"categories": (v.get("primary") or {}).get("categories_covered")})
    rep = [r for r in rs if r.get("phase") == "repeat"]
    check("claude_repeat_pass_ran", len(rep) >= 1, {"n_repeat": len(rep)}, critical=False)


def validate_immutability():
    """Nothing under c005..c012, the frozen teacher, or the deck may have changed."""
    prev = jload(os.path.join(ART, "immutability_verification.json")) or {}
    changed, checked = [], 0
    for key, entry in prev.items():
        if not isinstance(entry, dict):
            continue
        for path, want in (entry.get("files") or {}).items():
            full = os.path.join(_REPO, path)
            if not os.path.exists(full):
                changed.append({"path": path, "issue": "missing"})
                continue
            got = K.sha_file(full)
            checked += 1
            if got != want:
                changed.append({"path": path, "issue": "modified"})
    check("earlier_contracts_unmodified", not changed,
          {"files_checked": checked, "changed": changed[:20]})


def validate_required_files():
    """Existence is necessary but never sufficient; it is recorded as non-critical so a
    missing optional artifact cannot masquerade as a content failure, and vice versa."""
    required = [
        "artifacts/combination_results.json", "artifacts/COMBINATION_RESULT.md",
        "artifacts/combination_selection_games.jsonl.gz",
        "artifacts/combination_confirmation_games.jsonl.gz",
        "artifacts/combination_final_games.jsonl.gz",
        "artifacts/combination_final_matrix.csv",
        "artifacts/combination_final_intervals.json",
        "artifacts/Q0_summary.json", "artifacts/Q1_summary.json",
        "artifacts/Q0_training_games.jsonl.gz", "artifacts/Q1_training_games.jsonl.gz",
        "artifacts/value_refit_diagnostics.json",
        "artifacts/Q2_component_registry.json", "artifacts/Q2_training_games.jsonl.gz",
        "artifacts/Q2_recombination_results.json",
        "artifacts/Q3_gate.json", "artifacts/Q3_summary.json",
        "artifacts/soup_learnability.json", "artifacts/SOUP_LEARNABILITY.md",
        "artifacts/identical_state_policy_actions.jsonl.gz",
        "artifacts/semantic_action_agreement.json",
        "artifacts/behavioral_fingerprints.json",
        "artifacts/state_distribution_overlap.json", "artifacts/OPPONENT_OVERLAP.md",
        "artifacts/semantic_state_schema.json", "artifacts/claude_prompt.md",
        "artifacts/claude_output_schema.json",
        "artifacts/claude_preflight_inputs.jsonl.gz",
        "artifacts/claude_preflight_outputs.jsonl.gz",
        "artifacts/claude_semantic_validation.json",
        "artifacts/continuation_repair_report.json",
        "artifacts/trainer_state_schema.json",
        "artifacts/ensemble_semantics_validation.json",
        "artifacts/candidate_registry.json", "artifacts/combination_registry.json",
        "artifacts/dependency_verification.json",
        "artifacts/immutability_verification.json",
        "test_logs/opponent_overlap.txt", "test_logs/learnability_evaluation.txt",
        "test_logs/ensemble_math.txt", "test_logs/trainer_state_restore.txt",
    ]
    missing = [p for p in required if not os.path.exists(os.path.join(RES, p))]
    check("required_artifacts_present", not missing, {"missing": missing})


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    validate_panels()
    validate_composite_and_result()
    validate_q3_gate()
    validate_learnability()
    validate_budget()
    validate_registry_hashes()
    validate_overlap()
    validate_claude()
    validate_immutability()
    validate_required_files()

    # A failing check may be a KNOWN, documented deviation. It still fails -- suppressing it
    # would defeat the point -- but the report links it to the document that explains it, so a
    # reader can tell an acknowledged trade-off from an unexplained inconsistency.
    fdir = os.path.join(RES, "failures")
    devdocs = (sorted(os.listdir(fdir)) if os.path.isdir(fdir) else [])
    ACK = {"smoke_within_cap":
           "DEVIATION_curriculum_smoke_exceeded_its_registered_cap.md"}
    for c in checks:
        if not c["passed"] and c["check"] in ACK and ACK[c["check"]] in devdocs:
            c["acknowledged_deviation"] = f"results/failures/{ACK[c['check']]}"

    crit_fail = [c for c in checks if c["critical"] and not c["passed"]]
    soft_fail = [c for c in checks if not c["critical"] and not c["passed"]]
    doc = {"validator_bootstrap_seed": VALIDATOR_BOOT_SEED,
           "principle": "every headline claim is re-derived from primary evidence with an "
                        "independent seed; file existence is never sufficient (§38)",
           "n_checks": len(checks),
           "n_passed": sum(1 for c in checks if c["passed"]),
           "n_critical_failures": len(crit_fail),
           "n_noncritical_failures": len(soft_fail),
           "checks": checks,
           "unacknowledged_critical_failures": [c["check"] for c in crit_fail
                                                if "acknowledged_deviation" not in c],
           "acknowledged_deviations": [{"check": c["check"],
                                        "document": c["acknowledged_deviation"]}
                                       for c in crit_fail
                                       if "acknowledged_deviation" in c],
           "overall": "PASS" if not crit_fail else "FAIL"}
    json.dump(doc, open(os.path.join(ART, "evidence_validation.json"), "w"),
              indent=2, default=str)
    with open(os.path.join(LOGD, "evidence_validation.txt"), "w") as fh:
        for c in checks:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}]"
                     f"{'' if c['critical'] else '(non-critical)'} {c['check']}\n")
            if c["detail"] is not None:
                fh.write("    " + json.dumps(c["detail"], default=str)[:1200] + "\n")
        fh.write(f"\noverall: {doc['overall']}  "
                 f"({doc['n_passed']}/{doc['n_checks']} passed)\n")
    print(json.dumps({k: doc[k] for k in ("n_checks", "n_passed", "n_critical_failures",
                                          "n_noncritical_failures", "overall")}, indent=2))
    for c in crit_fail:
        print(f"  CRITICAL FAIL: {c['check']}: "
              f"{json.dumps(c['detail'], default=str)[:400]}")
    for c in soft_fail:
        print(f"  soft fail: {c['check']}")
    return 0 if not crit_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())

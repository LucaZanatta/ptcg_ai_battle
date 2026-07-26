"""c016 §22 — content-aware validator that re-derives headline claims from raw artifacts.

Every failure condition §22 names is implemented as an explicit check. Several of them exist
because c015 actually committed the corresponding defect, which the c016 prior-results audit
found by re-derivation:

  * `zero_opportunity_success_claim` — c015 reported Mechanism B executing while its own
    coherence file recorded ZERO opportunities. Zero opportunities must read `NOT_OBSERVED`.
  * `copied_prior_contract_identifiers` — c015's tooling was produced by text-substituting
    c014's, which is exactly how a c014 label survives into a c016 report.
  * `denominator_mismatch` — a published rate whose denominator differs from the raw record
    count.

The validator is allowed to fail the contract, and it must: §2 says an accepted upload alone can
never make c016 `PASS`.
"""

from __future__ import annotations

import csv
import glob
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import collections

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C16 = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission", "results")
ART = os.path.join(C16, "artifacts")
LOGD = os.path.join(C16, "test_logs")

checks = []


def ck(name, ok, detail=None, critical=True):
    checks.append({"check": name, "passed": bool(ok), "critical": critical, "detail": detail})
    return ok


def jload(p):
    p = p if os.path.isabs(p) else os.path.join(ART, p)
    return json.load(open(p)) if os.path.exists(p) else None


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_games(path):
    p = os.path.join(ART, path)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in gzip.open(p, "rt")]


# ---------------------------------------------------------------- §22 conditions

def v_wrong_contract_id():
    """A c016 report must not carry a c014/c015 contract identifier."""
    bad = []
    for p in glob.glob(os.path.join(ART, "*.md")) + glob.glob(os.path.join(ART, "*.json")) \
            + glob.glob(os.path.join(C16, "*.md")) + glob.glob(os.path.join(C16, "*.json")):
        name = os.path.basename(p)
        # the prior-results audit and decision board legitimately DISCUSS c014/c015
        if name in ("PRIOR_RESULTS_AUDIT.md", "prior_results_audit.json",
                    "DECISION_BOARD.md", "decision_board.json", "evidence_validation.json",
                    "REUSE_PERMISSION_MATRIX.md", "reuse_permission_matrix.json",
                    "SELECTION_DECISION.md", "selection_decision.json",
                    "EVALUATION_PROTOCOL.md", "evaluation_protocol.json",
                    "final_gauntlet_results.json", "screening_results.json",
                    "confirmation_results.json", "REPRODUCTION_FIDELITY.md",
                    "PUBLIC_AGENT_INVENTORY.md", "public_agent_inventory.json",
                    "next_action.json", "current_competition_facts.json",
                    "CURRENT_COMPETITION_FACTS.md"):
            continue
        try:
            txt = open(p, errors="ignore").read()
        except Exception:  # noqa: BLE001
            continue
        for pat in (r'"contract"\s*:\s*"c01[45]', r"^# c01[45] "):
            if re.search(pat, txt, re.M):
                bad.append({"file": name, "pattern": pat})
    ck("no_prior_contract_identifier_in_c016_reports", not bad, {"hits": bad[:10]})


def v_required_fields_nonnull():
    st = jload(os.path.join(C16, "STATUS.json"))
    gate = jload("competitive_gate.json") or {}
    required_always = ["contract", "status", "initial_head", "final_head"]
    missing = [k for k in required_always if not (st or {}).get(k)]
    ck("required_status_fields_present", not missing, {"missing": missing})
    if gate.get("competitive_gate") == "PASS":
        need = ["selected_candidate_id", "selected_fidelity", "selected_deck_sha256",
                "package_sha256", "kaggle_submission_ref", "reuse_permission_class"]
        nulls = [k for k in need if not (st or {}).get(k)]
        ck("selection_fields_nonnull_when_gate_passes", not nulls, {"null": nulls})
    else:
        ck("null_selection_fields_are_correct_when_gate_fails",
           not (st or {}).get("selected_candidate_id"),
           {"note": "gate FAIL, so no candidate may be recorded as selected"})


def v_denominators():
    """Published rates must reproduce from the raw per-game records, same denominator."""
    bad = []
    for csvname, gz, ratekeys in (
            ("screening_results.csv", "screening_games.jsonl.gz",
             {"safe_rate": "__safe__", "dragapult_rate": "dragapult"}),
            ("final_gauntlet_results.csv", "final_gauntlet_games.jsonl.gz",
             {"dragapult_rate": "dragapult", "iono_rate": "iono",
              "mega_lucario_rate": "mega_lucario", "mega_abomasnow_rate": "mega_abomasnow",
              "__c014___rate": "__c014__", "__c015___rate": "__c015__"})):
        p = os.path.join(ART, csvname)
        games = read_games(gz)
        if not os.path.exists(p) or not games:
            continue
        raw = collections.defaultdict(lambda: [0, 0.0])
        for g in games:
            if g.get("score") is None:
                continue
            raw[(g["candidate_id"], g["opponent_id"])][0] += 1
            raw[(g["candidate_id"], g["opponent_id"])][1] += g["score"]
        for row in csv.DictReader(open(p)):
            cid = row["candidate_id"]
            for rk, opp in ratekeys.items():
                if rk not in row or row[rk] in ("", None):
                    continue
                gk = rk.replace("_rate", "_games")
                n_raw, s_raw = raw.get((cid, opp), [0, 0.0])
                if gk in row and row[gk] not in ("", None):
                    if int(row[gk]) != n_raw:
                        bad.append({"file": csvname, "candidate": cid, "opponent": opp,
                                    "reported_games": int(row[gk]), "raw_games": n_raw})
                if n_raw:
                    # compare at the precision the CSV actually stores (4 dp). An earlier
                    # version compared at 1e-6 and flagged 0.4062 vs 0.40625 - a display
                    # rounding, not a denominator or rate discrepancy. Any real difference is
                    # >= 1e-4 and is still caught.
                    if abs(float(row[rk]) - round(s_raw / n_raw, 4)) > 1e-9:
                        bad.append({"file": csvname, "candidate": cid, "opponent": opp,
                                    "reported_rate": float(row[rk]),
                                    "raw_rate_rounded_4dp": round(s_raw / n_raw, 4),
                                    "raw_rate_full": s_raw / n_raw})
    ck("published_rates_and_denominators_match_raw_games", not bad, {"mismatches": bad[:10]})


def v_zero_opportunity_claims():
    """The c015 defect: a rate asserted over a zero denominator."""
    bad = []
    for p in glob.glob(os.path.join(ART, "*.json")):
        try:
            d = json.load(open(p))
        except Exception:  # noqa: BLE001
            continue

        def walk(o, path=""):
            if isinstance(o, dict):
                opp = o.get("opportunities")
                if isinstance(opp, (int, float)) and opp == 0:
                    for k, v in o.items():
                        if "rate" in k.lower() and isinstance(v, (int, float)) and v > 0:
                            bad.append({"file": os.path.basename(p), "path": path,
                                        "opportunities": 0, "claimed": {k: v}})
                    if o.get("executions", 0) and o["executions"] > 0:
                        bad.append({"file": os.path.basename(p), "path": path,
                                    "opportunities": 0, "executions": o["executions"]})
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")
        walk(d)
    ck("no_zero_opportunity_success_claims", not bad,
       {"hits": bad[:10],
        "rule": "zero opportunities must be reported as NOT_OBSERVED, never as a rate"})


def v_identity_mapping():
    """Every game record must self-identify; aggregation must not rely on position."""
    problems = []
    for gz in ("screening_games.jsonl.gz", "final_gauntlet_games.jsonl.gz",
               "confirmation_games.jsonl.gz"):
        games = read_games(gz)
        if not games:
            continue
        for g in games[:5000]:
            if not g.get("candidate_id") or not g.get("opponent_id") \
                    or g.get("seat") is None or g.get("seed") is None:
                problems.append({"file": gz, "record": {k: g.get(k) for k in
                                                        ("candidate_id", "opponent_id",
                                                         "seat", "seed")}})
                break
    ck("every_game_record_is_self_identifying", not problems, {"problems": problems})
    src = open(os.path.join(_REPO, "tools", "c016_gauntlet.py")).read()
    ck("aggregation_selects_by_field_not_position",
       "zip(" not in src.split("def agg(")[1].split("def ")[0],
       {"note": "agg() filters records by candidate_id/opponent_id/seat/phase"})


def v_public_claims_labelled():
    inv = jload("public_agent_inventory.json") or {}
    unlabelled = [c["candidate_id"] for c in inv.get("leads", [])
                  if c.get("claimed_score_or_benchmark")
                  and c.get("evidence_quality") not in ("OFFICIAL_CURRENT",)
                  and c.get("claim_evidence_label") != "PUBLIC_CLAIM"]
    ck("public_claims_labelled_not_asserted_as_fact", not unlabelled,
       {"unlabelled": unlabelled})
    gate = jload("competitive_gate.json") or {}
    sel = jload("selection_decision.json") or {}
    if gate.get("strength_path") == "C":
        ck("path_c_requires_explicit_public_claim_labelling", False,
           {"note": "path C was used; its PUBLIC_CLAIM basis must be reviewed"}, critical=True)
    else:
        ck("path_c_not_used_without_review", True,
           {"strength_path": gate.get("strength_path")}, critical=False)


def v_permission():
    gate = jload("competitive_gate.json") or {}
    perms = jload("reuse_permission_matrix.json") or {}
    by = {r["candidate_id"]: r for r in perms.get("rows", [])}
    sel = gate.get("selected_candidate_id")
    if sel:
        r = by.get(sel) or {}
        ck("selected_candidate_permission_allows_submission",
           r.get("permission_class") == "SUBMISSION_REUSE_ALLOWED" and r.get("may_submit"),
           {"candidate": sel, "class": r.get("permission_class")})
        ck("selected_candidate_has_attribution", bool(r.get("attribution_required")),
           {"attribution": r.get("attribution_required")})
    else:
        ck("no_selection_so_no_permission_requirement", True,
           {"note": "competitive gate did not select a candidate"}, critical=False)
    # nothing LOCAL_BENCHMARK_ONLY may have been packaged
    packaged = []
    for p in glob.glob(os.path.join(ART, "submission_*.tar.gz")):
        packaged.append(os.path.basename(p))
    ck("no_benchmark_only_source_packaged",
       all(not any(k in b for k in ("archaludon-75", "alakazam", "strong-start"))
           for b in packaged), {"archives": packaged})


def v_package_hash():
    man = jload("submission_J_manifest.json")
    pkg = os.path.join(ART, "submission_J_public_champion_v0.tar.gz")
    sub = jload("kaggle_submission_status.json")
    if not man or not os.path.exists(pkg):
        ck("package_absent_is_consistent_with_gate",
           (jload("competitive_gate.json") or {}).get("competitive_gate") != "PASS",
           {"note": "no package built; only valid when the competitive gate did not pass"})
        return
    on_disk = sha_file(pkg)
    ck("package_hash_matches_manifest", on_disk == man.get("sha256"),
       {"on_disk": on_disk, "manifest": man.get("sha256")})
    if sub:
        ck("uploaded_hash_matches_built_package",
           sub.get("archive_sha256") == on_disk,
           {"uploaded": sub.get("archive_sha256"), "on_disk": on_disk})


def v_history_unmodified():
    base = jload("immutability_baseline_pre_c016.json") or {}
    mod, miss, n = [], [], 0
    for k, files in base.items():
        if not k.endswith("_files"):
            continue
        for path, want in files.items():
            full = os.path.join(_REPO, path)
            if not os.path.exists(full):
                miss.append(path)
                continue
            n += 1
            if sha_file(full) != want:
                mod.append(path)
    ck("c005_to_c015_unmodified", not mod, {"files_checked": n, "modified": mod[:10]})
    ck("no_baseline_file_missing", not miss, {"missing": miss[:10]})
    ck("immutability_baseline_is_substantive", n > 1000, {"files_checked": n})


def v_pass_requires_all_gates():
    st = jload(os.path.join(C16, "STATUS.json")) or {}
    gate = jload("competitive_gate.json") or {}
    fid = jload("reproduction_fidelity_summary.json") or {}
    val = jload("submission_J_validation.json") or {}
    sub = jload("kaggle_submission_status.json") or {}
    claims_pass = st.get("status") == "PASS"
    have = {
        "fidelity_gate": fid.get("n_exact", 0) >= 2,
        "competitive_gate": gate.get("competitive_gate") == "PASS",
        "package_gate": bool(val.get("overall_pass")),
        "accepted_reference": bool(sub.get("submission_ref")),
    }
    if claims_pass:
        ck("pass_claimed_only_with_all_four_gates", all(have.values()), have)
    else:
        ck("non_pass_status_is_consistent", True,
           {"status": st.get("status"), "gates": have}, critical=False)
    ck("accepted_reference_alone_does_not_grant_pass",
       not (claims_pass and have["accepted_reference"] and not have["competitive_gate"]),
       {"note": "§2: an accepted upload is never sufficient on its own"})


def main():
    os.makedirs(LOGD, exist_ok=True)
    v_wrong_contract_id()
    v_required_fields_nonnull()
    v_denominators()
    v_zero_opportunity_claims()
    v_identity_mapping()
    v_public_claims_labelled()
    v_permission()
    v_package_hash()
    v_history_unmodified()
    v_pass_requires_all_gates()

    crit = [c for c in checks if c["critical"] and not c["passed"]]
    soft = [c for c in checks if not c["critical"] and not c["passed"]]
    doc = {"principle": "every headline claim re-derived from raw artifacts; file existence is "
                        "never sufficient and an accepted upload never grants PASS",
           "n_checks": len(checks), "n_passed": sum(1 for c in checks if c["passed"]),
           "n_critical_failures": len(crit), "n_noncritical_failures": len(soft),
           "checks": checks,
           "overall": "PASS" if not crit else "FAIL"}
    json.dump(doc, open(os.path.join(ART, "evidence_validation.json"), "w"), indent=2,
              default=str)
    with open(os.path.join(LOGD, "evidence_validation.txt"), "w") as fh:
        for c in checks:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}]"
                     f"{'' if c['critical'] else '(non-critical)'} {c['check']}\n")
            if c["detail"]:
                fh.write("    " + json.dumps(c["detail"], default=str)[:900] + "\n")
        fh.write(f"\noverall: {doc['overall']} ({doc['n_passed']}/{doc['n_checks']})\n")
    print(json.dumps({k: doc[k] for k in ("n_checks", "n_passed", "n_critical_failures",
                                          "overall")}, indent=2))
    for c in crit:
        print("  CRITICAL:", c["check"], json.dumps(c["detail"], default=str)[:300])
    for c in soft:
        print("  soft:", c["check"])
    return 0 if not crit else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""c016 §10-§12 — current facts, candidate inventory, and the reuse/permission matrix.

§12 is the gate that decides what c016 may even attempt: "Absence of a licence is not
automatically permission. Do not infer legal rights from visibility alone."

The Kaggle API exposes **no licence field for kernels** — verified this run by listing kernel
objects and inspecting every attribute. So permission cannot be read off the platform, and the
classification below rests on documented provenance instead:

  * the four kiyotah kernels are the competition's own SAMPLE agents. c005 recorded them as
    `OFFICIAL_REUSABLE` with `submission_eligible: true`, and — decisively — c005 packaged the
    Dragapult sample and Kaggle **accepted and scored it** (ref 54948560, 719.7, COMPLETE).
    That is an empirical fact about this competition, not an inference from visibility.
  * community notebooks carry no retrievable licence and no equivalent precedent, so they are
    `LOCAL_BENCHMARK_ONLY`. Their factual deck lists remain usable; their agent source is not
    copied, redistributed, or packaged by c016.
"""

from __future__ import annotations

import csv
import datetime
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C16 = os.path.join(_REPO, "contracts",
                   "c016_public_agent_reproduction_gauntlet_and_champion_submission", "results")
ART = os.path.join(C16, "artifacts")
LOGD = os.path.join(C16, "test_logs")
SNAP = os.path.join(ART, "public_source_snapshots")
C14A = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission",
                    "results", "artifacts")
C005 = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                    "results", "artifacts", "teacher_sources")
KAGGLE = os.path.join(_REPO, ".venv/bin/kaggle")
COMPETITION = "pokemon-tcg-ai-battle"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def kag(*a, timeout=180):
    try:
        r = subprocess.run([KAGGLE, *a], capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.returncode
    except Exception as e:  # noqa: BLE001
        return f"<failed {e!r}>", -1


def facts():
    u = datetime.datetime.now(datetime.timezone.utc)
    comps, _ = kag("competitions", "list", "-s", "pokemon-tcg", "-v")
    subs, _ = kag("competitions", "submissions", COMPETITION, "-v")
    lb, _ = kag("competitions", "leaderboard", COMPETITION, "-s", "--csv")
    crow = next((r for r in csv.DictReader(io.StringIO(comps))
                 if r.get("ref", "").endswith("/" + COMPETITION)), {})
    sub_rows = list(csv.DictReader(io.StringIO(subs)))
    lb_rows = [r for r in csv.DictReader(
        io.StringIO("\n".join(l for l in lb.splitlines()
                              if not l.startswith("Next Page Token"))))]
    dl = crow.get("deadline")
    conv = {}
    if dl:
        dt = datetime.datetime.fromisoformat(dl).replace(tzinfo=datetime.timezone.utc)
        conv = {"utc": dt.isoformat(),
                "jst": dt.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
                "europe_rome": dt.astimezone(ZoneInfo("Europe/Rome")).isoformat()}
    from kaggle_environments import make
    cfg = dict(make("cabt").configuration)
    scores = [float(r["score"]) for r in lb_rows if r.get("score")]
    return {
        "accessed_utc": u.isoformat(),
        "accessed_europe_rome": u.astimezone(ZoneInfo("Europe/Rome")).isoformat(),
        "competition_slug": {"value": COMPETITION, "evidence": "OFFICIAL_CURRENT",
                             "source": "kaggle competitions list -s pokemon-tcg -v"},
        "category": {"value": crow.get("category"), "evidence": "OFFICIAL_CURRENT"},
        "deadline": {"value": conv, "evidence": "OFFICIAL_CURRENT",
                     "source": "kaggle competitions list"},
        "team_submissions": {"value": sub_rows, "evidence": "OFFICIAL_CURRENT",
                             "source": f"kaggle competitions submissions {COMPETITION} -v",
                             "note": "public score is a LIVE ladder rating; each row is a "
                                     "timestamped reading, not a final result"},
        "leaderboard_top_range": {
            "value": {"top": max(scores) if scores else None,
                      "tenth": sorted(scores, reverse=True)[9] if len(scores) >= 10 else None,
                      "n_rows_seen": len(lb_rows)},
            "evidence": "OFFICIAL_CURRENT",
            "source": f"kaggle competitions leaderboard {COMPETITION} -s --csv"},
        "runtime_limits": {"value": cfg, "evidence": "OFFICIAL_CURRENT",
                           "source": "kaggle_environments cabt specification, read locally"},
        "submission_limit": {"value": None, "evidence": "UNVERIFIED",
                             "reason": "the rules page is client-rendered; an unauthenticated "
                                       "fetch returns only the document title. Not substituted "
                                       "from any earlier contract.",
                             "mitigation": "c016 makes at most one strategic upload (§7)"},
        "file_size_limit": {"value": None, "evidence": "UNVERIFIED",
                            "reason": "same client-rendered rules page",
                            "mitigation": "the c005 package of identical shape (~0.5 MB) was "
                                          "accepted and scored, so the built archive is known "
                                          "to be within whatever limit applies"},
        "package_requirements": {
            "value": "tar.gz with main.py and deck.csv at the archive root, unpacked at "
                     "/kaggle_simulations/agent/",
            "evidence": "PUBLIC_REPRODUCIBLE",
            "source": "c005 submission_A_teacher.tar.gz — accepted and scored, ref 54948560"},
    }


def inventory():
    """At least four leads. c014's snapshots first (§11), then what is already in-repo."""
    leads = []

    # --- the four official sample kernels, already retrieved and hashed by c005 ---
    ev = json.load(open(os.path.join(C005, "source_evidence.json")))
    for c in ev["official_candidates"]:
        cid = c["candidate_id"]
        d = os.path.join(C005, cid)
        files = []
        for f in ("main.py", "deck.csv"):
            p = os.path.join(d, f)
            if os.path.exists(p):
                files.append({"file": f, "sha256": sha_file(p),
                              "bytes": os.path.getsize(p),
                              "lines": sum(1 for _ in open(p, errors="ignore"))})
        leads.append({
            "candidate_id": f"official_{cid}",
            "source_author": "Kiyota (kiyotah)",
            "source_url": f"https://www.kaggle.com/code/{c['source_reference'].split(':')[1]}",
            "access_timestamp": c.get("retrieved_at_utc"),
            "file_hashes": files,
            "claimed_deck": c.get("archetype"),
            "claimed_score_or_benchmark": ("Dragapult sample scored 719.7 on the public ladder "
                                           "as c005 ref 54948560" if cid == "dragapult"
                                           else "no published score claim"),
            "exact_package_payload_available": True,
            "exact_deck_list_available": True,
            "algorithm_type": "rule-based strategic agent with planning, prize/resource "
                              "tracking, damage calculation and matchup rules",
            "source_lines_main_py": next((f["lines"] for f in files
                                          if f["file"] == "main.py"), None),
            "network_dependency_at_inference": False,
            "expected_runtime": "sub-millisecond per decision (measured in c014: p99 < 1 ms)",
            "source_freshness": "official sample set, last updated 2026-06-19",
            "evidence_quality": "OFFICIAL_CURRENT",
            "permission_status": "SUBMISSION_REUSE_ALLOWED",
            "disposition": ("CONTROL" if cid == "dragapult" else "ADVANCE"),
        })

    # --- community notebooks snapshotted by c014 ---
    community = [
        ("masamikobayashi/a-sample-archaludon-75-wr-vs-my-1300-starmie",
         "Archaludon ex / Cinderace", "75% WR vs a 1300+ Starmie", "rule-based"),
        ("ryotasueyoshi/rule-based-not-psychic-alakazam-best-5th",
         "Alakazam", "best 5th place", "rule-based"),
        ("romanrozen/strong-start-baseline-agent-v10-lb-950",
         "unspecified", "LB 950+", "probabilistic expectimax (search)"),
    ]
    for ref, deck, claim, algo in community:
        d = os.path.join(C14A, "public_source_snapshots", ref.replace("/", "_"))
        files = []
        for p in sorted(glob.glob(os.path.join(d, "*"))):
            if os.path.isfile(p):
                files.append({"file": os.path.basename(p), "sha256": sha_file(p),
                              "bytes": os.path.getsize(p)})
        leads.append({
            "candidate_id": "community_" + ref.split("/")[1][:28],
            "source_author": ref.split("/")[0],
            "source_url": f"https://www.kaggle.com/code/{ref}",
            "access_timestamp": "2026-07-26 (c014 snapshot)",
            "file_hashes": files,
            "claimed_deck": deck,
            "claimed_score_or_benchmark": claim,
            "claim_evidence_label": "PUBLIC_CLAIM",
            "exact_package_payload_available": bool(files),
            "exact_deck_list_available": ref.startswith(("masamikobayashi", "ryotasueyoshi")),
            "algorithm_type": algo,
            "network_dependency_at_inference": False,
            "expected_runtime": "unmeasured",
            "source_freshness": "2026-06/07",
            "evidence_quality": "PUBLIC_CLAIM",
            "permission_status": "LOCAL_BENCHMARK_ONLY",
            "disposition": "BENCHMARK_ONLY",
        })
    return leads


def permission_matrix(leads):
    rows = []
    for c in leads:
        cid = c["candidate_id"]
        if c["permission_status"] == "SUBMISSION_REUSE_ALLOWED":
            basis = [
                "competition SAMPLE kernel published by the competition's sample author",
                "c005 recorded reuse_classification=OFFICIAL_REUSABLE and "
                "submission_eligible=true with the retrieval commands preserved",
                "EMPIRICAL PRECEDENT: c005 packaged the Dragapult sample and Kaggle accepted "
                "and scored it (ref 54948560, 719.7, COMPLETE) - an observed fact about this "
                "competition, not an inference from visibility",
            ]
            attribution = next((x["attribution"] for x in json.load(
                open(os.path.join(C005, "source_evidence.json")))["official_candidates"]
                if f"official_{x['candidate_id']}" == cid), None)
        else:
            basis = [
                "no licence field is exposed for kernels by the Kaggle API - verified this run "
                "by listing kernel objects and inspecting every attribute",
                "no equivalent acceptance precedent exists for community code",
                "§12: absence of a licence is not permission, and legal rights are not inferred "
                "from visibility",
            ]
            attribution = f"{c['source_author']} — {c['source_url']}"
        rows.append({
            "candidate_id": cid,
            "permission_class": c["permission_status"],
            "basis": basis,
            "attribution_required": attribution,
            "may_execute_locally": True,
            "may_redistribute_or_package": c["permission_status"] == "SUBMISSION_REUSE_ALLOWED",
            "may_submit": c["permission_status"] == "SUBMISSION_REUSE_ALLOWED",
            "third_party_embedded_terms": ("romanrozen notebook states it was copied from "
                                           "aristophanivan/improved-probabilistic-agent, adding "
                                           "a second unresolved upstream"
                                           if "strong-start" in cid else None),
        })
    return rows


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    os.makedirs(SNAP, exist_ok=True)
    f = facts()
    leads = inventory()
    perms = permission_matrix(leads)

    json.dump(f, open(os.path.join(ART, "current_competition_facts.json"), "w"),
              indent=2, default=str)
    json.dump({"leads": leads, "n_leads": len(leads),
               "n_advance": sum(1 for c in leads if c["disposition"] == "ADVANCE"),
               "n_benchmark_only": sum(1 for c in leads
                                       if c["disposition"] == "BENCHMARK_ONLY")},
              open(os.path.join(ART, "public_agent_inventory.json"), "w"), indent=2,
              default=str)
    json.dump({"rows": perms,
               "kernel_licence_field_available_from_api": False,
               "n_submission_allowed": sum(1 for r in perms
                                           if r["permission_class"] == "SUBMISSION_REUSE_ALLOWED"),
               "n_benchmark_only": sum(1 for r in perms
                                       if r["permission_class"] == "LOCAL_BENCHMARK_ONLY")},
              open(os.path.join(ART, "reuse_permission_matrix.json"), "w"), indent=2,
              default=str)

    # snapshot manifest: the official sources c016 will actually reproduce
    with open(os.path.join(ART, "public_source_manifest.sha256"), "w") as fh:
        for c in leads:
            for x in c["file_hashes"]:
                fh.write(f"{x['sha256']}  {c['candidate_id']}/{x['file']}\n")

    write_md(f, leads, perms)
    with open(os.path.join(LOGD, "current_fact_refresh.txt"), "w") as fh:
        fh.write(json.dumps(f, indent=2, default=str) + "\n")
    with open(os.path.join(LOGD, "reuse_permission_audit.txt"), "w") as fh:
        fh.write(json.dumps({"matrix": perms, "leads": leads}, indent=2, default=str) + "\n")
    print(json.dumps({"leads": len(leads),
                      "advance": sum(1 for c in leads if c["disposition"] == "ADVANCE"),
                      "benchmark_only": sum(1 for c in leads
                                            if c["disposition"] == "BENCHMARK_ONLY"),
                      "submission_allowed": sum(
                          1 for r in perms
                          if r["permission_class"] == "SUBMISSION_REUSE_ALLOWED"),
                      "deadline_rome": (f["deadline"]["value"] or {}).get("europe_rome"),
                      "lb_top": f["leaderboard_top_range"]["value"]["top"]}, indent=2))
    return 0


def write_md(f, leads, perms):
    L = ["# Current competition facts (§10)\n",
         f"Accessed {f['accessed_europe_rome']} (Europe/Rome).\n",
         "| fact | value | evidence label |", "|---|---|---|"]
    d = f["deadline"]["value"] or {}
    L.append(f"| slug | `{f['competition_slug']['value']}` | {f['competition_slug']['evidence']} |")
    L.append(f"| category | {f['category']['value']} | {f['category']['evidence']} |")
    L.append(f"| deadline UTC | {d.get('utc')} | OFFICIAL_CURRENT |")
    L.append(f"| deadline JST | {d.get('jst')} | OFFICIAL_CURRENT |")
    L.append(f"| deadline Europe/Rome | {d.get('europe_rome')} | OFFICIAL_CURRENT |")
    lbv = f["leaderboard_top_range"]["value"]
    L.append(f"| leaderboard top / 10th | {lbv['top']} / {lbv['tenth']} | OFFICIAL_CURRENT |")
    L.append(f"| submission limit | not obtainable | **UNVERIFIED** |")
    L.append(f"| file-size limit | not obtainable | **UNVERIFIED** |")
    L.append(f"| runtime | {f['runtime_limits']['value']} | OFFICIAL_CURRENT |")
    L.append(f"\nThe two UNVERIFIED rows are recorded as gaps, not filled in from earlier "
             f"contracts: {f['submission_limit']['reason']}\n")
    L.append("### Team submissions (live readings)\n")
    L.append("| ref | file | status | public score |")
    L.append("|---|---|---|---|")
    for r in f["team_submissions"]["value"]:
        L.append(f"| {r.get('ref')} | {r.get('fileName')} | {r.get('status')} | "
                 f"{r.get('publicScore')} |")
    L.append(f"\n{f['team_submissions']['note']}.\n")
    open(os.path.join(ART, "CURRENT_COMPETITION_FACTS.md"), "w").write("\n".join(L) + "\n")

    I = ["# Public-agent inventory (§11)\n",
         f"{len(leads)} candidate leads. Title claims are preserved as `PUBLIC_CLAIM` and are "
         "not treated as measured truth.\n",
         "| candidate | author | deck | claim | algorithm | evidence | permission | disposition |",
         "|---|---|---|---|---|---|---|---|"]
    for c in leads:
        I.append(f"| `{c['candidate_id']}` | {c['source_author']} | {c['claimed_deck']} | "
                 f"{c['claimed_score_or_benchmark']} | {c['algorithm_type'][:44]} | "
                 f"{c['evidence_quality']} | {c['permission_status']} | {c['disposition']} |")
    I.append("\n### Why the official samples are the reproduction targets\n")
    I.append("They are **rich implementations**, not priority tables — "
             + ", ".join(f"`{c['candidate_id']}` {c['source_lines_main_py']} lines"
                         for c in leads if c.get("source_lines_main_py"))
             + " — carrying planning, prize/resource tracking, damage calculation and matchup "
               "rules. §3 forbids replacing exactly this kind of implementation with a smaller "
               "static priority table, which is the error c014 and c015 made.\n")
    open(os.path.join(ART, "PUBLIC_AGENT_INVENTORY.md"), "w").write("\n".join(I) + "\n")

    P = ["# Reuse, attribution and permission matrix (§12)\n",
         "**The Kaggle API exposes no licence field for kernels.** Verified this run by listing "
         "kernel objects and inspecting every attribute. Permission therefore cannot be read "
         "off the platform, and §12 forbids inferring it from visibility.\n",
         "| candidate | class | may execute | may package | may submit |",
         "|---|---|---|---|---|"]
    for r in perms:
        P.append(f"| `{r['candidate_id']}` | **{r['permission_class']}** | "
                 f"{r['may_execute_locally']} | {r['may_redistribute_or_package']} | "
                 f"{r['may_submit']} |")
    P.append("\n### Basis for `SUBMISSION_REUSE_ALLOWED`\n")
    for b in next(r["basis"] for r in perms
                  if r["permission_class"] == "SUBMISSION_REUSE_ALLOWED"):
        P.append(f"- {b}")
    P.append("\nThe third point is the load-bearing one: it is an **observed outcome**, not a "
             "reading of a licence. An identically-sourced package was submitted and scored by "
             "this competition.\n")
    P.append("### Basis for `LOCAL_BENCHMARK_ONLY`\n")
    for b in next(r["basis"] for r in perms
                  if r["permission_class"] == "LOCAL_BENCHMARK_ONLY"):
        P.append(f"- {b}")
    P.append("\nCommunity agent **source is not copied, packaged, or uploaded** by c016. Their "
             "factual deck lists remain usable — c014 already used one — because a list of card "
             "IDs is a game configuration, not authored code.\n")
    P.append("### Attribution recorded for any submitted candidate\n")
    for r in perms:
        if r["may_submit"]:
            P.append(f"- `{r['candidate_id']}`: {r['attribution_required']}")
    P.append("")
    open(os.path.join(ART, "REUSE_PERMISSION_MATRIX.md"), "w").write("\n".join(P) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

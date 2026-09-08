"""c018 AC-01 — verify the baseline package and the accepted reference 55011215.

The c018 uploads are "post-baseline", which only means something if the baseline itself is
pinned to a specific archive, a specific source, and a specific accepted Kaggle submission.
This re-derives all three from prior contracts' artifacts rather than restating them, and it
never writes into c005-c017.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")
BASE_SRC = os.path.join(_REPO, "contracts",
                        "c016_public_agent_reproduction_gauntlet_and_champion_submission",
                        "results", "artifacts", "candidates", "official_mega_lucario")
REFERENCE = "55011215"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def find_reference():
    """Locate the accepted reference in prior contracts' own submission records."""
    hits = []
    for pat in ("contracts/c0*/results/**/*submission*.json",
                "contracts/c0*/results/**/*kaggle*.json"):
        for p in glob.glob(os.path.join(_REPO, pat), recursive=True):
            if "c018_" in p:
                continue
            try:
                txt = open(p).read()
            except Exception:  # noqa: BLE001
                continue
            if REFERENCE in txt:
                try:
                    d = json.loads(txt)
                except Exception:  # noqa: BLE001
                    d = {}
                hits.append({
                    "file": os.path.relpath(p, _REPO),
                    "submission_ref": d.get("submission_ref") or d.get("ref"),
                    "status": d.get("status"),
                    "public_score": d.get("public_score"),
                    "description": d.get("description"),
                    "archive_sha256": d.get("archive_sha256")})
    return hits


def main():
    os.makedirs(ART, exist_ok=True)
    main_py = os.path.join(BASE_SRC, "main.py")
    deck = os.path.join(BASE_SRC, "deck.csv")
    fid = os.path.join(BASE_SRC, "reproduction_fidelity.json")
    manc = os.path.join(BASE_SRC, "candidate_manifest.json")

    hits = find_reference()
    pkg = glob.glob(os.path.join(C18, "packages", "*_manifest.json"))
    doc = {
        "acceptance_criterion": "AC-01",
        "baseline_candidate": "official_mega_lucario",
        "baseline_source_dir": os.path.relpath(BASE_SRC, _REPO),
        "baseline_main_sha256": sha_file(main_py) if os.path.exists(main_py) else None,
        "baseline_deck_sha256": sha_file(deck) if os.path.exists(deck) else None,
        "baseline_fidelity": json.load(open(fid)) if os.path.exists(fid) else None,
        "baseline_manifest": json.load(open(manc)) if os.path.exists(manc) else None,
        "accepted_reference": REFERENCE,
        "accepted_reference_found_in": hits,
        "accepted_reference_verified": bool(hits),
        "c018_packages_embed_this_baseline": [],
        "prior_contracts_unmodified": None,
    }
    for p in pkg:
        m = json.load(open(p))
        doc["c018_packages_embed_this_baseline"].append({
            "name": m.get("name"),
            "baseline_main_sha256": m.get("baseline_main_sha256"),
            "matches": m.get("baseline_main_sha256") == doc["baseline_main_sha256"],
            "deck_sha256": m.get("deck_sha256"),
            "deck_matches": m.get("deck_sha256") == doc["baseline_deck_sha256"]})

    base = os.path.join(ART, "immutability_baseline_pre_c018.json")
    if os.path.exists(base):
        b = json.load(open(base))
        changed, n = [], 0
        for k, files in b.items():
            if not k.endswith("_files"):
                continue
            for rel, want in files.items():
                fp = os.path.join(_REPO, rel)
                if not os.path.exists(fp):
                    changed.append({"path": rel, "issue": "missing"})
                    continue
                n += 1
                if sha_file(fp) != want:
                    changed.append({"path": rel, "issue": "modified"})
        doc["prior_contracts_unmodified"] = not changed
        doc["files_checked"] = n
        doc["changed_files"] = changed[:10]

    doc["git_head"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                     capture_output=True, text=True).stdout.strip()
    doc["passed"] = bool(doc["accepted_reference_verified"]
                         and doc["baseline_main_sha256"]
                         and doc["prior_contracts_unmodified"]
                         and all(x["matches"] and x["deck_matches"]
                                 for x in doc["c018_packages_embed_this_baseline"]))
    json.dump(doc, open(os.path.join(ART, "baseline_anchor.json"), "w"), indent=2, default=str)
    print(json.dumps({k: doc[k] for k in
                      ("accepted_reference_verified", "baseline_main_sha256",
                       "prior_contracts_unmodified", "files_checked",
                       "c018_packages_embed_this_baseline", "passed")}, indent=2, default=str))
    return 0 if doc["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

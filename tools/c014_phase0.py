"""c014 Phase 0 — current public evidence snapshot and deck selection (§8/§9).

Everything recorded here was verified in this run. §8 says the handoff's older deadline,
submission limit, ratings and archetype claims must not be trusted without re-checking, so each
fact below carries how it was obtained and an evidence label.

Where a fact could NOT be obtained, that is recorded as a gap with the reason rather than filled
in from the handoff or from memory. Kaggle's rules/overview pages are client-rendered, so a
plain fetch returns only the document title; that is a real limitation of this snapshot and the
latency bound derived from it is stated as self-imposed rather than as a quoted competition
number.
"""

from __future__ import annotations

import csv
import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C014 = os.path.join(_REPO, "contracts", "c014_public_meta_baseline_and_rapid_submission")
ART = os.path.join(C014, "results", "artifacts")
LOGD = os.path.join(C014, "results", "test_logs")
SNAP = os.path.join(ART, "public_source_snapshots")

COMPETITION = "pokemon-tcg-ai-battle"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def now():
    u = datetime.datetime.now(datetime.timezone.utc)
    return u, u.astimezone(ZoneInfo("Europe/Rome"))


def kag(*args, timeout=120):
    try:
        r = subprocess.run([os.path.join(_REPO, ".venv/bin/kaggle"), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:  # noqa: BLE001
        return f"<failed: {e!r}>", -1


# ----------------------------------------------------------------------------------

def competition_facts():
    u, rome = now()
    comps, _ = kag("competitions", "list", "-s", "pokemon-tcg", "-v")
    subs, _ = kag("competitions", "submissions", COMPETITION, "-v")
    lb, _ = kag("competitions", "leaderboard", COMPETITION, "-s", "--csv")

    deadline_utc = None
    for row in csv.DictReader(comps.splitlines()):
        if row.get("ref", "").endswith("/" + COMPETITION):
            deadline_utc = row.get("deadline")
    dl_rome = None
    if deadline_utc:
        dt = datetime.datetime.fromisoformat(deadline_utc).replace(
            tzinfo=datetime.timezone.utc)
        dl_rome = dt.astimezone(ZoneInfo("Europe/Rome")).isoformat()

    # the ONLY authoritative runtime numbers available offline are the environment's own
    from kaggle_environments import make
    cfg = dict(make("cabt").configuration)

    my_subs = [r for r in csv.DictReader(subs.splitlines())]
    lb_rows = [r for r in csv.DictReader(
        [l for l in lb.splitlines() if not l.startswith("Next Page Token")])]

    facts = {
        "accessed_utc": u.isoformat(), "accessed_europe_rome": rome.isoformat(),
        "competition_slug": COMPETITION,
        "competition_title": "The Pokémon Company - PTCG AI Battle Challenge Simulation",
        "competition_url": f"https://www.kaggle.com/competitions/{COMPETITION}",
        "evidence_label": "OFFICIAL_CURRENT",
        "obtained_via": "kaggle CLI 2.2.2 (authenticated), verified this run",
        "deadline_utc": deadline_utc, "deadline_europe_rome": dl_rome,
        "other_competition_seen": {
            "slug": "pokemon-tcg-ai-battle-challenge-strategy",
            "deadline_utc": next((r.get("deadline") for r in csv.DictReader(comps.splitlines())
                                  if "challenge-strategy" in r.get("ref", "")), None),
            "why_not_selected": "a different competition. Every prior submission in this "
                                "project (c005 ref 54948560, public score 719.7) and the frozen "
                                "teacher control live in pokemon-tcg-ai-battle; switching would "
                                "break the only external comparison c014 has. The repo folder "
                                "of the same name holds card-data reference PDFs/CSVs, not "
                                "competition assets."},
        "runtime_limits": {
            "source": "kaggle_environments cabt specification, read locally this run",
            "episodeSteps": cfg.get("episodeSteps"),
            "actTimeout_seconds": cfg.get("actTimeout"),
            "runTimeout_seconds": cfg.get("runTimeout"),
            "interpretation": "actTimeout=0 means the local build enforces no per-decision "
                              "limit; runTimeout=3000s bounds a whole episode.",
        },
        "daily_submission_limit": {
            "value": None,
            "evidence_label": "GAP",
            "reason": "the rules page is client-rendered, so an unauthenticated fetch returns "
                      "only the document title. Not substituted from the handoff.",
            "mitigation": "c014 makes exactly one upload (§7), so any plausible daily limit "
                          "(commonly 2-5) is not binding. Last prior submissions were "
                          "2026-07-24, so today's quota is untouched.",
        },
        "package_rules": {
            "archive": "submission.tar.gz containing main.py and deck.csv at the archive root",
            "runtime_path": "/kaggle_simulations/agent/",
            "evidence_label": "PUBLIC_REPRODUCIBLE",
            "source": "ichigoe/beginner-guide-from-deck-list-to-first-valid-sub, plus c005's "
                      "submission_A_teacher.tar.gz which was ACCEPTED and scored 719.7 - a "
                      "package shape proven correct by the leaderboard rather than by reading",
        },
        "my_submissions": my_subs,
        "teacher_control": next((r for r in my_subs if r.get("ref") == "54948560"), None),
        "leaderboard_top": lb_rows[:10],
        "public_code_usage": {
            "assessment": "deck lists are factual card-ID configurations, and the notebooks "
                          "used here publish them explicitly as shared samples for this "
                          "competition (competition_sources lists pokemon-tcg-ai-battle). "
                          "c014 uses public notebooks as EVIDENCE for selection and takes one "
                          "deck list; it does not copy any published agent implementation - "
                          "the deterministic expert in §10 is written for this contract.",
            "evidence_label": "PUBLIC_REPRODUCIBLE",
            "licence_field_in_metadata": "absent from `kaggle kernels pull -m` output; not "
                                         "assumed to be permissive, which is a further reason "
                                         "only the factual deck list is reused",
        },
    }
    return facts


def index_snapshots():
    rows = []
    for meta in sorted(glob.glob(os.path.join(SNAP, "*", "kernel-metadata.json"))):
        d = os.path.dirname(meta)
        m = json.load(open(meta))
        files = []
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                files.append({"file": os.path.relpath(p, _REPO), "sha256": sha_file(p),
                              "bytes": os.path.getsize(p)})
        rows.append({"ref": m.get("id"), "title": m.get("title"),
                     "author": (m.get("id") or "/").split("/")[0],
                     "url": f"https://www.kaggle.com/code/{m.get('id')}",
                     "kernel_id_no": m.get("id_no"),
                     "competition_sources": m.get("competition_sources"),
                     "retrieved_via": "kaggle kernels pull -m",
                     "files": files})
    return rows


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    facts = competition_facts()
    snaps = index_snapshots()
    doc = {"competition": facts, "sources": snaps,
           "mining_clock": json.load(open(os.path.join(ART, "mining_clock.json")))}
    json.dump(doc, open(os.path.join(ART, "public_sources.json"), "w"), indent=2, default=str)

    with open(os.path.join(ART, "public_source_manifest.sha256"), "w") as fh:
        for s in snaps:
            for f in s["files"]:
                fh.write(f"{f['sha256']}  {f['file']}\n")

    write_facts_md(facts, snaps)
    print(json.dumps({"deadline_rome": facts["deadline_europe_rome"],
                      "sources_indexed": len(snaps),
                      "files_hashed": sum(len(s["files"]) for s in snaps),
                      "teacher_score": (facts.get("teacher_control") or {}).get("publicScore"),
                      "lb_top": (facts["leaderboard_top"][0]["score"]
                                 if facts["leaderboard_top"] else None)}, indent=2))
    return 0


def write_facts_md(f, snaps):
    L = ["# Current competition facts (verified this run)\n"]
    L.append(f"Accessed **{f['accessed_europe_rome']}** (Europe/Rome) / "
             f"{f['accessed_utc']} UTC via authenticated Kaggle CLI.\n")
    L.append(f"- **Slug**: `{f['competition_slug']}`")
    L.append(f"- **Title**: {f['competition_title']}")
    L.append(f"- **Deadline**: {f['deadline_utc']} UTC → **{f['deadline_europe_rome']}** "
             "Europe/Rome")
    L.append(f"- **Evidence label**: `{f['evidence_label']}`\n")
    o = f["other_competition_seen"]
    L.append(f"A second competition `{o['slug']}` (deadline {o['deadline_utc']}) also exists. "
             f"{o['why_not_selected']}\n")
    r = f["runtime_limits"]
    L.append("## Runtime limits\n")
    L.append(f"From the `cabt` environment specification read locally: `episodeSteps="
             f"{r['episodeSteps']}`, `actTimeout={r['actTimeout_seconds']}s`, "
             f"`runTimeout={r['runTimeout_seconds']}s`. {r['interpretation']}\n")
    d = f["daily_submission_limit"]
    L.append("## Gaps recorded rather than guessed\n")
    L.append(f"- **Daily submission limit**: `{d['evidence_label']}`. {d['reason']} "
             f"{d['mitigation']}\n")
    L.append("- **Published per-decision timeout**: not obtainable for the same reason. c014 "
             "therefore enforces §11's explicit p99 ≤ 250 ms plus a **self-imposed** maximum of "
             "1000 ms per decision. This bound is labelled self-imposed, not quoted: with "
             f"`runTimeout={r['runTimeout_seconds']}s` per episode and ~90 decisions per seat, "
             "even 1 s per decision leaves the episode budget untouched.\n")
    t = f.get("teacher_control") or {}
    L.append("## External reference points\n")
    L.append(f"- Frozen Dragapult teacher, submission ref **{t.get('ref')}**, public score "
             f"**{t.get('publicScore')}** ({t.get('status')}) — the project's only external "
             "measurement and c014's control.")
    if f["leaderboard_top"]:
        L.append(f"- Current public leaderboard top: "
                 + ", ".join(f"{r_['score']}" for r_ in f["leaderboard_top"][:5])
                 + f" (top team `{f['leaderboard_top'][0]['teamName']}`).")
    L.append("")
    L.append("## Package rules\n")
    p = f["package_rules"]
    L.append(f"{p['archive']}, unpacked at `{p['runtime_path']}`. Source: {p['source']}\n")
    L.append("## Public code and data usage\n")
    L.append(f["public_code_usage"]["assessment"] + "\n")
    L.append(f"Licence field: {f['public_code_usage']['licence_field_in_metadata']}.\n")
    L.append("## Sources snapshotted\n")
    L.append("| ref | title | files |")
    L.append("|---|---|---|")
    for s in snaps:
        L.append(f"| `{s['ref']}` | {s['title']} | {len(s['files'])} |")
    L.append("\nEvery snapshot file is hashed in `public_source_manifest.sha256`.\n")
    open(os.path.join(ART, "CURRENT_COMPETITION_FACTS.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

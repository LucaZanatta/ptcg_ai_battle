"""c005 Phase D: freeze the selected teacher and build/validate Submission A.

Creates results/artifacts/frozen_teacher/ (main.py, deck.csv, cg/, SOURCE.json,
FREEZE.json), builds submission_A_teacher.tar.gz in the competition structure,
and validates it by EXTRACTING to a clean temp dir and running >=20 strategic
smoke games from the extracted archive (its own bundled cg/ + deck.csv), checking
zero invalid actions/errors/timeouts. Produces the submission decision and the
exact (un-run) Kaggle submit command.

Usage: .venv/bin/python tools/build_submission.py --primary <id> --sources <src> --out-dir <artifacts>
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_schema import canonical_deck, sha256_file
from cg.teachers import TEACHERS, make_fresh

_SIZE_LIMIT_BYTES = 100 * 1024 * 1024  # conservative; exact competition limit not machine-retrievable
_load = [0]


def _load_dir_agent(tdir):
    """Fresh instance of an agent from a bare submission dir (main.py+deck.csv+cg/)."""
    _load[0] += 1
    tdir = os.path.abspath(tdir)
    old = os.getcwd()
    os.chdir(tdir)
    sys.path.insert(0, tdir)  # prefer the archive's own bundled cg
    try:
        spec = importlib.util.spec_from_file_location(f"extracted_{_load[0]}", os.path.join(tdir, "main.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old)
        if tdir in sys.path:
            sys.path.remove(tdir)
    return mod.agent


def build(primary_id, sources_dir, out_dir, evidence):
    tdir = os.path.join(sources_dir, TEACHERS[primary_id]["dir"])
    frozen = os.path.join(out_dir, "frozen_teacher")
    if os.path.isdir(frozen):
        shutil.rmtree(frozen)
    os.makedirs(frozen)
    # copy exact teacher files (behaviour-preserving; no strategy/deck change)
    for item in ("main.py", "deck.csv", "cg"):
        src = os.path.join(tdir, item)
        dst = os.path.join(frozen, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    with open(os.path.join(tdir, "deck.csv")) as fh:
        deck = [int(x) for x in fh if x.strip()]
    deck_rec = canonical_deck(deck, source_path=os.path.join(tdir, "deck.csv"), repo_root=_REPO_ROOT)
    source_json = {
        "teacher_id": primary_id, "display_name": TEACHERS[primary_id]["display_name"],
        "archetype": TEACHERS[primary_id]["archetype"], "source_type": TEACHERS[primary_id]["source_type"],
        "source_reference": TEACHERS[primary_id]["source_reference"],
        "reuse_classification": TEACHERS[primary_id]["reuse_classification"],
        "attribution": f"Official Kaggle sample kernel {TEACHERS[primary_id]['source_reference']} (Kiyota).",
        "retrieved_evidence": evidence,
    }
    json.dump(source_json, open(os.path.join(frozen, "SOURCE.json"), "w"), indent=2)
    freeze_json = {
        "teacher_id": primary_id,
        "main_sha256": sha256_file(os.path.join(frozen, "main.py")),
        "deck_sha256": sha256_file(os.path.join(frozen, "deck.csv")),
        "deck_id": deck_rec["deck_id"], "deck_card_count": deck_rec["card_count"],
        "deck_cards": deck_rec["cards"], "agent_version": TEACHERS[primary_id]["source_reference"],
        "policy_type": TEACHERS[primary_id]["policy_type"], "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    json.dump(freeze_json, open(os.path.join(frozen, "FREEZE.json"), "w"), indent=2)

    # build tar (competition structure: main.py, deck.csv, cg/) — SOURCE/FREEZE excluded
    tar_path = os.path.join(out_dir, "submission_A_teacher.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tf:
        for item in ("main.py", "deck.csv", "cg"):
            tf.add(os.path.join(frozen, item), arcname=item)
    manifest = {"teacher_id": primary_id, "frozen_deck_id": deck_rec["deck_id"],
                "main_sha256": freeze_json["main_sha256"], "deck_sha256": freeze_json["deck_sha256"],
                "archive": os.path.relpath(tar_path, _REPO_ROOT),
                "archive_size_bytes": os.path.getsize(tar_path),
                "reuse_classification": TEACHERS[primary_id]["reuse_classification"], "source": source_json}
    json.dump(manifest, open(os.path.join(out_dir, "frozen_teacher_manifest.json"), "w"), indent=2)
    return tar_path, deck_rec, freeze_json


def validate(tar_path, primary_id, sources_dir, out_dir):
    from kaggle_environments import make
    report = {"archive": os.path.relpath(tar_path, _REPO_ROOT),
              "size_bytes": os.path.getsize(tar_path), "size_limit_bytes": _SIZE_LIMIT_BYTES,
              "checks": {}, "smoke": {}}
    report["checks"]["size_under_limit"] = report["size_bytes"] < _SIZE_LIMIT_BYTES
    tmp = tempfile.mkdtemp(prefix="subA_")
    log = []
    try:
        with tarfile.open(tar_path) as tf:
            names = tf.getnames()
            try:
                tf.extractall(tmp, filter="data")  # py>=3.12 safe extraction
            except TypeError:
                tf.extractall(tmp)
        report["archive_paths"] = sorted(names)
        report["checks"]["has_main"] = any(n.endswith("main.py") for n in names)
        report["checks"]["has_deck"] = any(n.endswith("deck.csv") for n in names)
        report["checks"]["has_cg"] = any("cg/" in n or n == "cg" for n in names)
        report["checks"]["no_secrets"] = not any(
            k in n.lower() for n in names for k in ("kaggle.json", "token", ".env", "credential"))
        report["checks"]["no_training_data"] = not any(
            n.endswith((".jsonl", ".jsonl.gz")) or "dataset" in n.lower() for n in names)
        report["checks"]["clean_extraction"] = os.path.isfile(os.path.join(tmp, "main.py"))

        # >=20 strategic smoke games from the EXTRACTED archive vs other teachers, both seats
        opponents = [c for c in TEACHERS if c != primary_id]
        total = 0; invalid = 0; defects = 0; latencies = []
        plan = []
        for seat in (0, 1):
            for i in range(10):
                plan.append((seat, opponents[i % len(opponents)]))
        for seat, opp in plan:
            prim = _load_dir_agent(tmp)                       # extracted archive agent
            other = make_fresh(opp, sources_dir)              # opponent from sources
            inv = [0]; lat = []

            def wrap(ag, track):
                def w(obs):
                    t0 = time.perf_counter_ns(); r = ag(obs); dt = time.perf_counter_ns() - t0
                    sel = obs["select"]
                    if track and sel is not None:
                        lat.append(dt)
                        from cg.safe_policy import validate_selection, MalformedSelection
                        try:
                            validate_selection(list(r), len(sel["option"]), sel["minCount"], sel["maxCount"])
                        except MalformedSelection:
                            inv[0] += 1
                    return r
                return w
            players = [wrap(prim, True), wrap(other, False)] if seat == 0 else [wrap(other, False), wrap(prim, True)]
            env = make("cabt"); env.run(players)
            last = env.steps[-1]
            st = [last[0]["status"], last[1]["status"]]
            total += 1
            latencies.extend(lat)
            if st != ["DONE", "DONE"]:
                defects += 1
            invalid += inv[0]
            log.append(f"game {total}: seat{seat} vs {opp} -> {st[0]}/{st[1]} invalid={inv[0]}")
        latencies.sort()
        p99 = latencies[min(len(latencies) - 1, int(0.99 * len(latencies)))] / 1e6 if latencies else 0.0
        report["smoke"] = {"games": total, "invalid_selections": invalid, "non_terminal_games": defects,
                           "p99_latency_ms": round(p99, 5), "max_latency_ms": round(latencies[-1] / 1e6, 5) if latencies else 0.0,
                           "opponents": sorted(set(opponents))}
        report["checks"]["smoke_20_games"] = total >= 20
        report["checks"]["smoke_zero_invalid"] = invalid == 0
        report["checks"]["smoke_all_terminal"] = defects == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report["all_checks_pass"] = all(report["checks"].values())
    json.dump(report, open(os.path.join(out_dir, "submission_A_validation.json"), "w"), indent=2)
    with open(os.path.join(out_dir, "submission_A_smoke.txt"), "w") as fh:
        fh.write("\n".join(log) + f"\n\ngames={report['smoke']['games']} invalid={report['smoke']['invalid_selections']} "
                 f"non_terminal={report['smoke']['non_terminal_games']} p99_ms={report['smoke']['p99_latency_ms']}\n")
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--primary", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args(argv)
    tar_path, deck_rec, freeze = build(a.primary, a.sources, a.out_dir, {"note": "see source_evidence.json"})
    report = validate(tar_path, a.primary, a.sources, a.out_dir)
    decision = "SUBMIT" if report["all_checks_pass"] else "DO_NOT_SUBMIT"
    print(json.dumps({"primary": a.primary, "deck_id": deck_rec["deck_id"],
                      "archive_size_bytes": report["size_bytes"], "all_checks_pass": report["all_checks_pass"],
                      "smoke": report["smoke"], "decision": decision}, indent=2))
    # emit decision + command files
    with open(os.path.join(a.out_dir, "SUBMISSION_A_DECISION.md"), "w") as fh:
        fh.write(_decision_md(a.primary, deck_rec, report, decision))
    cmd = (f"kaggle competitions submit -c pokemon-tcg-ai-battle "
           f"-f contracts/c005_teacher_import_submission_and_dataset/results/artifacts/submission_A_teacher.tar.gz "
           f'-m "c005 Submission A: frozen teacher {a.primary} ({deck_rec["deck_id"][:20]})"')
    with open(os.path.join(a.out_dir, "KAGGLE_SUBMIT_COMMAND.txt"), "w") as fh:
        fh.write(cmd + "\n")
    return 0


def _decision_md(primary, deck_rec, report, decision):
    c = report["checks"]
    return f"""# Submission A Decision

**Decision: {decision}**

- Teacher: `{primary}` ({TEACHERS[primary]['display_name']}), archetype {TEACHERS[primary]['archetype']}.
- Frozen deck id: `{deck_rec['deck_id']}` (60 cards).
- Reuse: {TEACHERS[primary]['reuse_classification']} (official Kaggle sample; submission-eligible).
- Archive: `submission_A_teacher.tar.gz`, {report['size_bytes']} bytes (< {report['size_limit_bytes']} limit).

## Packaging + reliability gates (all must pass for SUBMIT)
| check | pass |
|---|---|
| size under limit | {c.get('size_under_limit')} |
| main.py / deck.csv / cg/ present | {c.get('has_main')} / {c.get('has_deck')} / {c.get('has_cg')} |
| no secrets / no training data | {c.get('no_secrets')} / {c.get('no_training_data')} |
| clean extraction | {c.get('clean_extraction')} |
| >=20 extracted smoke games | {c.get('smoke_20_games')} |
| zero invalid selections | {c.get('smoke_zero_invalid')} |
| all games terminal | {c.get('smoke_all_terminal')} |

Extracted-archive smoke: {report['smoke']['games']} games vs {report['smoke']['opponents']},
invalid={report['smoke']['invalid_selections']}, non-terminal={report['smoke']['non_terminal_games']},
P99 latency {report['smoke']['p99_latency_ms']} ms.

## Upload
Actual upload is gated behind `PTCG_ALLOW_KAGGLE_SUBMIT=1` (see AC-08). The flag is
absent by default -> **not uploaded**; the exact command is in
`KAGGLE_SUBMIT_COMMAND.txt`. Caveat: the full competition rules text was not
machine-retrievable (JS-rendered page); reuse basis is the teacher's official-sample
provenance (`rules_and_reuse_audit.md`).
"""


if __name__ == "__main__":
    sys.exit(main())

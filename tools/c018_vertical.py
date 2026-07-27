"""c018 Pass A — the thin end-to-end vertical (P30).

Runs every stage of the pipeline at deliberately small scale with REAL outputs, in one pass, in
order. The point is not performance: it is to make interface defects surface while they are
still cheap. A report-schema mismatch discovered after a multi-hour training run costs that
whole run.

Nothing here is optimised and nothing here is promoted. Each stage records the concrete artifact
it produced so `real_output` is a fact about a file on disk, not a claim.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

C18 = os.path.join(_REPO, "contracts",
                   "c018_complete_integrated_search_learning_curriculum_campaign", "results")
ART = os.path.join(C18, "artifacts")
PY = os.path.join(_REPO, ".venv", "bin", "python")

DEFECTS = [
    "search_begin rejected under-length hidden-card predictions (2 begin + 49 step errors); "
    "the determinizer now tops short pools up with a legal card id and predicts a Pokemon for "
    "a face-down opponent Active",
    "kaggle_environments errors out the seat when handed the official teacher callable "
    "directly, which silently scored the baseline panel candidate 0 for 0",
    "clean-extraction validation could not import cg.teachers for its opponents, because the "
    "package's own cg correctly shadows the repo's; opponents now load by file path",
    "NpzFile decompresses on every key access, so reading opt_dense inside a 12k-row generator "
    "made P07 spin for five minutes",
    "the evidence validator returned PASS with every training milestone absent -- absence is "
    "now a critical failure in --final mode rather than a free pass",
]


def run(cmd, tag):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True, timeout=7200)
    return {"tag": tag, "cmd": " ".join(cmd[1:]), "returncode": p.returncode,
            "seconds": round(time.time() - t0, 1),
            "stdout_tail": p.stdout[-1200:], "stderr_tail": p.stderr[-800:]}


def jload(p):
    p = p if os.path.isabs(p) else os.path.join(C18, p)
    return json.load(open(p)) if os.path.exists(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--nproc", type=int, default=4)
    a = ap.parse_args(argv)
    os.makedirs(ART, exist_ok=True)
    stages, logs = [], []

    # 1-3: official search root -> multi-step successor trace -> real search trajectory
    logs.append(run([PY, "tools/c018_trajectories.py", "--games", "6", "--prefix", "vertical"],
                    "search+trajectory"))
    s = jload("search/vertical_search_summary.json") or {}
    c = s.get("real_search_counters") or {}
    stages.append({"stage": "official search root", "real_output":
                   (c.get("begin_ok") or 0) > 0,
                   "evidence": f"{c.get('begin_ok', 0)} real search_begin roots"})
    stages.append({"stage": "multi-step successor trace", "real_output":
                   (c.get("step_ok") or 0) > 0 and (c.get("max_depth_reached") or 0) >= 2,
                   "evidence": f"{c.get('step_ok', 0)} search_step calls, depth "
                               f"{c.get('max_depth_reached', 0)}, "
                               f"{c.get('distinct_successors', 0)} distinct successors"})
    stages.append({"stage": "real search trajectory", "real_output":
                   (s.get("trusted_decisions") or 0) > 0,
                   "evidence": f"{s.get('trusted_decisions', 0)} trusted decisions in "
                               f"{s.get('trajectory_file')}"})

    # 4: supervised optimizer step
    logs.append(run([PY, "tools/c018_distill.py", "--prefix", "vertical", "--epochs", "2",
                     "--tag", "vertical_distill"], "distill"))
    d = jload("training/vertical_distill_distillation_report.json") or {}
    stages.append({"stage": "supervised optimizer step", "real_output":
                   (d.get("optimizer_steps") or 0) > 0 and bool(d.get("checkpoint_changed")),
                   "evidence": f"{d.get('optimizer_steps', 0)} steps on {d.get('device')}, "
                               f"checkpoint hash changed: {d.get('checkpoint_changed')}"})

    # 5: actual PPO game and optimizer step
    logs.append(run([PY, "tools/c018_curriculum.py", "--init",
                     os.path.join(C18, "checkpoints", "vertical_distill.pt"),
                     "--blocks", "2", "--games-per-block", "100", "--nproc", str(a.nproc),
                     "--tag", "vertical_curric", "--self-play-schedule", "0,0.3"], "curriculum"))
    cu = jload("training/vertical_curric_curriculum_report.json") or {}
    stages.append({"stage": "actual PPO game and optimizer step", "real_output":
                   (cu.get("actual_simulator_games") or 0) > 0
                   and (cu.get("optimizer_steps") or 0) > 0,
                   "evidence": f"{cu.get('actual_simulator_games', 0)} real games, "
                               f"{cu.get('optimizer_steps', 0)} optimizer steps, "
                               f"{cu.get('distinct_checkpoint_hashes', 0)} distinct hashes"})

    # 6: guided-search inference
    logs.append(run([PY, "tools/c018_diagnostics.py", "--policy",
                     os.path.join(C18, "checkpoints", "vertical_curric.npz"),
                     "--games", "4", "--out-prefix", "vertical_"], "guided"))
    g = jload("artifacts/vertical_guided_latency.json") or {}
    comp = jload("artifacts/vertical_guidance_comparison.json") or {}
    stages.append({"stage": "guided-search inference", "real_output":
                   bool((g.get("guided") or {}).get("n")) and (comp.get("roots") or 0) > 0,
                   "evidence": f"guided p90 {(g.get('guided') or {}).get('p90')} ms vs "
                               f"unguided {(g.get('unguided') or {}).get('p90')} ms; "
                               f"{comp.get('roots', 0)} shared roots compared"})

    # 7: evaluator
    logs.append(run([PY, "tools/c018_panel.py", "--games-per-pair", "2", "--nproc",
                     str(a.nproc), "--candidates",
                     "official_mega_lucario,m01_heuristic_search",
                     "--out-prefix", "vertical_"], "panel"))
    pm = jload("final_panel/vertical_panel_meta.json") or {}
    stages.append({"stage": "evaluator", "real_output":
                   (pm.get("scored_games") or 0) > 0,
                   "evidence": f"{pm.get('scored_games', 0)}/{pm.get('planned_games', 0)} "
                               f"panel games scored from raw identity-carrying rows"})

    # 8: package smoke
    logs.append(run([PY, "tools/c018_package.py", "--name", "vertical_package_smoke",
                     "--games", "4"], "package"))
    pv = jload("packages/vertical_package_smoke_clean_validation.json") or {}
    stages.append({"stage": "package smoke", "real_output":
                   bool(pv.get("clean_extraction_ok")),
                   "evidence": f"{pv.get('games_completed', 0)}/{pv.get('games_played', 0)} "
                               f"games from a clean extraction with the repo off sys.path"})

    doc = {"probe_id": "P30", "pass": "A",
           "purpose": ("execute every interface with small real outputs before scaling, so "
                       "interface defects surface while they are still cheap"),
           "stages": stages, "defects": DEFECTS,
           "all_stages_real": all(s["real_output"] for s in stages),
           "logs": logs,
           "wall_clock_s": round(sum(l["seconds"] for l in logs), 1)}
    json.dump(doc, open(os.path.join(ART, "thin_vertical.json"), "w"), indent=2, default=str)
    for s in stages:
        print(f"  {'OK ' if s['real_output'] else 'NO '} {s['stage']:34s} {s['evidence']}")
    print(f"all_stages_real={doc['all_stages_real']} in {doc['wall_clock_s']}s")
    return 0 if doc["all_stages_real"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

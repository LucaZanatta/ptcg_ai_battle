"""c022 — freeze the exact identities and hashes of every control named in CONTRACT.md §2.

`CONTRACT.md §2` names seven controls. A control that is only named is not frozen: c021's own
manifest carried `CHAMPION_C005_DRAGAPULT` with `"dir": null` and `"files_sha256": {}`, so the
"externally confirmed champion" was in fact pinned to nothing at all and could have been edited
under the campaign without any check noticing. Every control here resolves to real files on disk
and every file is hashed, or the control is written with an explicit `resolution_error` and the
manifest reports `complete: false`.

The c021 fixed-deck B2 checkpoints are frozen as CONTROLS AND TRANSFER COMPARATORS ONLY
(`CONTRACT.md §2`): they must not be continued and must not initialize the faithful recurrent
ByteRL model. That prohibition is recorded in each entry as `must_not_initialize_c022`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C021 = os.path.join(_REPO, "contracts",
                    "c021_source_faithful_mcgs_and_byterl_transfer_campaign", "results")
C020 = os.path.join(_REPO, "contracts",
                    "c020_forced_method_correction_and_hybrid_integration_campaign", "results")
C005 = os.path.join(_REPO, "contracts",
                    "c005_teacher_import_submission_and_dataset", "results")
OUT = os.path.join(_REPO, "contracts",
                   "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                   "results", "controls")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: str, skip_pycache: bool = True) -> dict:
    """Hash every file under `root`, keyed by path relative to `root`.

    `__pycache__` is skipped by default: c021's baseline entry hashed
    `__pycache__/main.cpython-313.pyc`, which is a build artifact of whichever interpreter last
    imported the module. Pinning it makes the control spuriously "change" on a Python upgrade
    while saying nothing about the agent.
    """
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if skip_pycache:
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            out[os.path.relpath(p, root)] = sha256_file(p)
    return dict(sorted(out.items()))


def rel(path: str) -> str:
    return os.path.relpath(path, _REPO)


def _entry(role: str, **kw) -> dict:
    d = {"role": role}
    d.update(kw)
    return d


def _resolve_dir(entry: dict, path: str) -> dict:
    if not os.path.isdir(path):
        entry["resolution_error"] = f"not a directory: {rel(path)}"
        entry["files_sha256"] = {}
        return entry
    entry["dir"] = rel(path)
    entry["files_sha256"] = hash_tree(path)
    entry["n_files"] = len(entry["files_sha256"])
    return entry


def _resolve_file(entry: dict, path: str, key: str = "file") -> dict:
    if not os.path.isfile(path):
        entry["resolution_error"] = f"not a file: {rel(path)}"
        return entry
    entry[key] = rel(path)
    entry[key + "_sha256"] = sha256_file(path)
    entry[key + "_bytes"] = os.path.getsize(path)
    return entry


def _load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def build() -> dict:
    c021_manifest = _load(os.path.join(C021, "controls", "control_manifest.json")) or {}
    prior = c021_manifest.get("controls", {})
    controls = {}

    # ---------------------------------------------------------------- 1. official baseline
    e = _entry("frozen official baseline; the competitive bar for MCGS_COMPETITIVE",
               carried_from="c021 control_manifest.json",
               c020_panel_field=(prior.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {})
               .get("c020_panel_field"),
               c020_panel_ci=(prior.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {})
               .get("c020_panel_ci"),
               live_ladder_score_observed=(prior.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {})
               .get("live_ladder_score_observed"),
               kaggle_submission_ref=(prior.get("BASELINE_OFFICIAL_MEGA_LUCARIO") or {})
               .get("kaggle_submission_ref"))
    controls["BASELINE_OFFICIAL_MEGA_LUCARIO"] = _resolve_dir(
        e, os.path.join(C020, "controls", "baseline_package"))

    # ---------------------------------------------------------------- 2. champion
    # c021 left this one unpinned. It resolves to the c005 teacher source tree that
    # `c009_eval.SOURCES` points every panel run at, so it is the artifact actually executed.
    e = _entry("externally confirmed champion; panel opponent and role-board reference",
               live_ladder_score_observed=(prior.get("CHAMPION_C005_DRAGAPULT") or {})
               .get("live_ladder_score_observed"),
               note="c021 recorded this control with dir=null and no hashes, so it was named "
                    "but not frozen. Resolved here to the teacher source tree that "
                    "c009_eval.SOURCES resolves to at run time.",
               loaded_by="cg.teachers.make_fresh('dragapult', cg.c009_eval.SOURCES)")
    controls["CHAMPION_C005_DRAGAPULT"] = _resolve_dir(
        e, os.path.join(C005, "artifacts", "teacher_sources", "dragapult"))

    # ---------------------------------------------------------------- 3. c020 H1 hybrid
    e = _entry("c020's best candidate: corrected ByteRL priors + tactical heuristic",
               carried_from="c021 control_manifest.json",
               c020_panel_field=(prior.get("C020_H1_PRIOR_HYBRID_CONTROL") or {})
               .get("c020_panel_field"),
               c020_panel_ci=(prior.get("C020_H1_PRIOR_HYBRID_CONTROL") or {})
               .get("c020_panel_ci"),
               promotable_in_c020=False,
               why_not=(prior.get("C020_H1_PRIOR_HYBRID_CONTROL") or {}).get("why_not"),
               note="the one prior signal that a learned prior can help a search; c022 transfer "
                    "arms must verify runtime call counts, not the label")
    src = {}
    for f in ("starter_kit/c020_hybrid.py", "starter_kit/c020_ismcts.py",
              "starter_kit/c020_byterl_model.py", "starter_kit/c020_byterl_encode.py",
              "starter_kit/c020_tactical_leaf.py", "starter_kit/c020_override.py"):
        p = os.path.join(_REPO, f)
        if os.path.isfile(p):
            src[f] = sha256_file(p)
    e["source_sha256"] = src
    controls["C020_H1_PRIOR_HYBRID_CONTROL"] = e

    # ---------------------------------------------------------------- 4. c021 MCGS K1 control
    # The c022 K1 arm must reproduce THIS run (probe M04). It is the T0 arm of the c021 transfer
    # lab: MCGS_2019_OFFICIAL_SOURCE_PORT with determinizations_per_decision = 1, no prior, no
    # rollout policy -- i.e. exactly K=1 with no ByteRL component attached.
    t0p = os.path.join(C021, "transfer", "prior_only", "t2_T0_control_summary.json")
    t0 = _load(t0p) or {}
    e = _entry("the c021 single-determinization MCGS run c022's K=1 arm must reproduce",
               summary_file=rel(t0p),
               branch=t0.get("branch"),
               config=t0.get("config"),
               games=t0.get("games"), completed=t0.get("completed"),
               abandoned=t0.get("abandoned"),
               field_score=t0.get("field_score"),
               sims_per_decision=t0.get("sims_per_decision"),
               searched_decisions=t0.get("searched_decisions"),
               term_root_win=t0.get("term_root_win"),
               term_root_loss=t0.get("term_root_loss"),
               term_undecided=t0.get("term_undecided"),
               determinizations_per_decision=1)
    if os.path.isfile(t0p):
        e["summary_sha256"] = sha256_file(t0p)
    else:
        e["resolution_error"] = f"missing: {rel(t0p)}"
    src = {}
    for f in ("starter_kit/c021_mcgs.py", "starter_kit/c021_mcgs_graph.py",
              "starter_kit/c021_mcgs_agent.py", "starter_kit/c021_mcgs_abstraction.py",
              "starter_kit/c021_mcgs_legal.py", "starter_kit/c020_determinize.py"):
        p = os.path.join(_REPO, f)
        if os.path.isfile(p):
            src[f] = sha256_file(p)
    e["source_sha256"] = src
    controls["C021_MCGS_K1_CONTROL"] = e

    # ---------------------------------------------------------------- 5/6. c021 fixed-deck B2
    ck = os.path.join(C021, "byterl", "checkpoints")
    e = _entry("c021 fixed-deck B2 final weights: transfer comparator and improvement bar",
               must_not_initialize_c022=True,
               must_not_be_continued=True,
               why="CONTRACT.md §2 -- a control and transfer comparator only. c022's faithful "
                   "recurrent ByteRL trains from fresh random weights.",
               architecture="feed-forward (c021 c021_byterl_model.ByteRLNet); NOT the published "
                            "LSTM-256 recurrent system c022 implements")
    controls["C021_FIXED_DECK_B2_FINAL"] = _resolve_file(
        e, os.path.join(ck, "big_ctrl_b2_final.pt"), "checkpoint")

    e = _entry("the checkpoint c021's preregistered external-panel selector chose",
               must_not_initialize_c022=True,
               must_not_be_continued=True,
               note="c021 recorded that this selection was subject to the winner's curse: chosen "
                    "at 0.3594 on a 121-candidate x 64-game panel, it measured 0.1953 out of "
                    "sample while the final checkpoint measured 0.2578. c022 reconciles both "
                    "numbers from raw data before using either.",
               used_by_c021_transfer_arms=True)
    controls["C021_FIXED_DECK_B2_SELECTED_IT0160"] = _resolve_file(
        e, os.path.join(ck, "intermediate", "big_ctrl_b2_it0160.pt"), "checkpoint")

    # ---------------------------------------------------------------- 7. random floor
    #
    # This entry was "named but pinned to nothing" until the floor was measured -- exactly the
    # defect this same file criticises c021 for shipping with CHAMPION_C005_DRAGAPULT. The
    # validator's V13 check found it, and it is now pinned to the artifacts that measured it.
    e = _entry("the fresh-random-weights floor every ByteRL learning claim is measured against",
               definition="the c022 ByteRL network at FRESH RANDOM WEIGHTS, playing the same "
                          "four-archetype panel with the same evaluator as every trained "
                          "checkpoint. Not a hand-written uniform-random agent: the comparator "
                          "for 'did training help' must be the SAME system before training, or "
                          "the difference measures the architecture as well as the learning.",
               why_measured_externally="c021 measured its floor inside the training loop, on the "
                                       "very games that produced the gradient. DECISION_RULES §3 "
                                       "requires a credible improvement over the floor, so the "
                                       "floor has to be measured the same way the improvement "
                                       "is.")
    fl = {}
    for arm, tag in (("FIXED_DECK", "floor_fixed_deck"), ("END_TO_END", "floor_end_to_end")):
        p = os.path.join(_REPO, "contracts",
                         "c022_mcgs_multideterminization_and_faithful_byterl_reproduction",
                         "results", "byterl", "external_evaluations", f"{tag}_eval.json")
        if not os.path.isfile(p):
            continue
        d = _load(p) or {}
        fl[arm] = {
            "eval_file": rel(p), "eval_sha256": sha256_file(p),
            "games": d.get("games"), "completed": d.get("completed"),
            "field_score": d.get("field_score"), "wilson95": d.get("wilson95"),
            "deck_legal_rate": d.get("deck_legal_rate"),
            "distinct_decks": d.get("distinct_decks"),
            "value_beats_constant": (d.get("value_calibration") or {}).get(
                "beats_constant_predictor"),
        }
    e["measured"] = fl
    if not fl:
        e["resolution_error"] = "the floor has not been measured yet; run " \
                                "tools/c022_byterl_campaign.sh floor"
    else:
        e["note"] = ("the two arms have DIFFERENT floors -- end-to-end scores above fixed-deck "
                     "at random initialization -- so neither arm's improvement may be measured "
                     "against the other's floor.")
    controls["C021_RANDOM_FLOOR"] = e

    complete = all("resolution_error" not in v for v in controls.values())
    return {
        "contract": "c022",
        "frozen_at_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True,
            text=True).stdout.strip(),
        "controls_required_by_contract": [
            "BASELINE_OFFICIAL_MEGA_LUCARIO", "CHAMPION_C005_DRAGAPULT",
            "C020_H1_PRIOR_HYBRID_CONTROL", "C021_MCGS_K1_CONTROL",
            "C021_FIXED_DECK_B2_FINAL", "C021_FIXED_DECK_B2_SELECTED_IT0160",
            "C021_RANDOM_FLOOR"],
        "complete": complete,
        "unresolved": [k for k, v in controls.items() if "resolution_error" in v],
        "opponent_panel": ["dragapult", "mega_lucario", "iono", "mega_abomasnow"],
        "opponent_panel_source": "cg.c009_eval.SOURCES -> "
                                 + rel(os.path.join(C005, "artifacts", "teacher_sources")),
        "controls": controls,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "control_manifest.json"))
    a = ap.parse_args(argv)
    m = build()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
    print(f"wrote {a.out}")
    print(f"complete={m['complete']} unresolved={m['unresolved']}")
    for k, v in m["controls"].items():
        n = v.get("n_files")
        tag = (v.get("checkpoint_sha256") or v.get("summary_sha256") or "")[:12]
        print(f"  {k:42s} files={n if n is not None else '-':>4} {tag}"
              + (f"  ERROR {v['resolution_error']}" if "resolution_error" in v else ""))
    return 0 if m["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

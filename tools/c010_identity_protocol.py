"""c010 AC-05: record the identity-safe evaluation protocol and its live evidence.

c010 reuses the c009 protocol verbatim -- the repair that closed c008's unordered-result
identity defect. The protocol's defining property is that identity travels *with* each
result: every worker returns the immutable job fields it was given, re-hashes the checkpoint
it actually loaded and fingerprints the deck it actually played, so results are matched by
job_id and never by completion position. `imap_unordered` output is therefore safe.

This tool emits the protocol description plus the identity reports produced by the batches
that have actually run, so the artifact is evidence rather than a description of intent.
"""

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from cg import c009_eval as ce  # noqa: E402

C010 = os.path.join(_REPO, "contracts", "c010_fixed_deck_rl_loop_v2")
ART = os.path.join(C010, "results", "artifacts")

ASSERTIONS = [
    "submitted job_ids are unique",
    "returned job_ids are unique",
    "the submitted job_id set equals the returned job_id set (no missing, no extra)",
    "every returned candidate_id exists in the frozen candidate registry",
    "the checkpoint hash matches the registry AND the hash the worker recomputed after load",
    "every identity field round-trips unchanged from the submitted job",
    "the per candidate/opponent/seat count is exactly the frozen panel size",
    "no unexpected candidate or opponent appears",
    "every game is terminal or explicitly classified as a defect",
]


def main(argv=None):
    argparse.ArgumentParser().parse_args(argv)
    man = {}
    mp = os.path.join(ART, "evaluation_game_manifest.json")
    if os.path.exists(mp):
        man = json.load(open(mp))
    reports = man.get("identity_reports", [])
    reg_p = os.path.join(ART, "experiment_registry.json")
    reg = json.load(open(reg_p)) if os.path.exists(reg_p) else {}

    out = {
        "contract": "c010",
        "protocol_source": "cg/c009_eval.py (reused verbatim; c010 adds no reattachment step)",
        "identity_fields_returned_by_every_worker": list(ce.IDENTITY_FIELDS),
        "job_id_format": "phase::candidate_id::opponent_id::s{seat}::r{replicate}",
        "worker_self_verification": [
            "re-hashes the checkpoint file it loaded and returns verified_checkpoint_sha256",
            "fingerprints the deck it actually played and returns deck_fingerprint",
            "classifies any non-terminal game with an explicit defect string",
        ],
        "assertions": ASSERTIONS,
        "n_assertions": len(ASSERTIONS),
        "ordering_guarantee": (
            "Results are matched to jobs by job_id only. No positional reattachment is "
            "performed anywhere in c010, which is what made the c008 defect possible: there, "
            "unordered results were zipped back onto an ordered job list, so a reordering "
            "that crossed an arm boundary relabelled games onto the wrong candidate."),
        "frozen_panels": reg.get("panels"),
        "expected_deck_fingerprint": reg.get("frozen_deck_fingerprint"),
        "batches_executed": [
            {"phase": r.get("phase"), "candidates": len(r.get("candidates", [])),
             "results": r.get("n_results"), "terminal": r.get("terminal"),
             "defects": r.get("defects"), "ok": r.get("ok"),
             "wall_seconds": r.get("wall_seconds")}
            for r in reports],
        "n_batches": len(reports),
        "all_batches_identity_ok": bool(reports) and all(r.get("ok") for r in reports),
        "total_evaluation_games": man.get("total_games"),
        "seat_balance_ok": man.get("seat_balance_ok"),
        "total_defects": man.get("defects"),
    }
    json.dump(out, open(os.path.join(ART, "evaluation_identity_protocol.json"), "w"), indent=2)
    print(json.dumps({k: out[k] for k in
                      ("n_assertions", "n_batches", "all_batches_identity_ok",
                       "total_evaluation_games", "seat_balance_ok", "total_defects")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

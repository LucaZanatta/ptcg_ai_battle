"""c007 AC-03: emit the State Encoder v2 schema, the c006->v2 feature diff, and run
determinism + completeness tests over the existing 19,050 stored decisions.

Outputs:
  results/artifacts/state_encoder_v2_schema.json
  results/artifacts/c006_vs_v2_feature_diff.json
  results/test_logs/state_encoder_v2_tests.txt
(state_encoder_v2_audit.md is authored alongside using these outputs.)
"""

import argparse
import gzip
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402
from cg import state_encoder_v2 as enc  # noqa: E402
from cg import policy_features as pf  # noqa: E402

C006_SEQ = os.path.join(_REPO, "contracts", "c006_distilled_policy_baseline",
                        "results", "artifacts", "sequence_dataset")


def schema():
    dims = enc.feature_dims()
    return {
        "contract": "c007",
        "name": "state_encoder_v2",
        "consumes": "raw cabt observation dict (identical offline and at runtime)",
        "dims": dims,
        "board": {
            "n_slots": enc.N_BOARD,
            "slot_order": ["self_active"] + [f"self_bench_{k}" for k in range(enc.N_SELF_BENCH)]
                          + ["opp_active"] + [f"opp_bench_{k}" for k in range(enc.N_OPP_BENCH)],
            "per_slot": {"card_row": "int -> card encoder (semantic + zero-init id residual)",
                         "slot_dyn_dim": enc.SLOT_DYN,
                         "slot_dyn_fields": {k: v for k, v in enc._S.items()}},
            "no_averaging": True,
        },
        "hand": {"n_slots": enc.N_HAND, "per_slot": ["card_row", "dup_count_norm", "playable"],
                 "mask": True, "encoder": "DeepSets masked mean+max"},
        "discard": {"n_slots": enc.N_DISCARD, "window": "most recent N cards",
                    "summary_tail": "per-card-type counts in global (self+opp)",
                    "encoder": "DeepSets masked mean+max"},
        "options": {"per_option_dense_dim": enc.OPT_DENSE, "referenced_card_rows": enc.OPT_ROWS,
                    "encoder": "cross-option DeepSets (each score depends on the option set)"},
        "global_dim": enc.GLOBAL,
        "history": {"fields": ["previous_context", "previous_action_type",
                               "previous_card_identity(52-d semantics)", "previous_attack_phantom/has",
                               "previous_selected_count", "present"],
                    "reset_at_game_start": True,
                    "note": "actual previous SELECTED option identity (c006 gap fixed)"},
        "card_semantics": {"feat_dim": enc.CARD_FEAT,
                           "unseen_cards": "deterministic 52-d features + ZERO-init id residual "
                                           "(no random untrained id embeddings) [7.6]"},
        "hidden_information": {
            "opponent_hand": "count only (never card ids)",
            "prizes": "counts only (face-down identities never revealed)",
            "own_deck_order": "not represented (hidden); deck composition inference is a "
                              "teacher-privileged LABEL, never a runtime input",
        },
    }


def feature_diff():
    """§7.7 completeness audit: classify each observed source field."""
    R = "represented_directly"
    T = "deterministically_transformed"
    O = "intentionally_omitted"
    U = "unavailable_hidden_or_privileged"
    fields = {
        # global game state
        "current.turn": (R, "global turn_norm"),
        "current.turnActionCount": (R, "global"),
        "current.yourIndex(seat)": (R, "global seat"),
        "current.firstPlayer": (R, "global first-player flag"),
        "current.supporterPlayed": (R, "global"),
        "current.stadiumPlayed": (R, "global"),
        "current.energyAttached": (R, "global"),
        "current.retreated": (R, "global"),
        "current.result": (O, "terminal outcome — excluded from inputs (label leakage); "
                              "used only as the value-head training target"),
        "current.stadium": (T, "presence flag in global; exact stadium card identity omitted "
                               "(rare; the one strategically relevant stadium is derivable from options)"),
        "current.looking": (T, "represented through LOOKING-area option cards when a look "
                               "decision is live; transient otherwise"),
        # in-play pokemon (both players, per slot)
        "players[].active": (R, "per-slot board (self/opp active)"),
        "players[].bench": (R, "per-slot board, 5 explicit slots each side, never averaged"),
        "players[].benchMax": (T, "bench occupancy encoded via slot presence + global bench counts"),
        "pokemon.id": (R, "card row -> semantic features + id embedding"),
        "pokemon.hp/maxHp": (R, "hp_norm, maxhp_norm, damage_norm, remaining_frac per slot"),
        "pokemon.appearThisTurn": (R, "per-slot flag"),
        "pokemon.energies": (R, "per-slot energy count + 12 energy-type counts"),
        "pokemon.energyCards": (T, "count per slot; exact special-energy card identities omitted "
                                   "(low leverage vs energy-type counts)"),
        "pokemon.tools": (T, "count + has_tool per slot; exact tool identity omitted (rare)"),
        "pokemon.preEvolution": (T, "evolution-stack depth per slot"),
        "player.status(poisoned/burned/asleep/paralyzed/confused)": (R, "5 flags on active slots"),
        # zones
        "players[me].hand": (R, "exact multiset (12-slot set encoder + dup counts + playable mask)"),
        "players[opp].hand": (U, "hidden — only handCount is used"),
        "players[].discard": (T, "most-recent-N set encoder + per-card-type count summary; "
                                 "full ordered history beyond window compressed to counts"),
        "players[].deckCount": (R, "global deck counts (both players)"),
        "deck_composition/order": (U, "hidden; teacher's remaining-count inference is a privileged label"),
        "players[].prize": (T, "prize COUNTS represented; face-down identities hidden"),
        # decision
        "select.context": (R, "global context one-hot"),
        "select.minCount/maxCount": (R, "global"),
        "select.remainDamageCounter/remainEnergyCost": (R, "global"),
        "select.option": (R, "per-option dense features + 2 referenced card rows + set encoder"),
        "select.deck": (R, "DECK-area options resolve to card rows"),
        "select.contextCard": (T, "reflected through option/context features"),
        "select.effect": (O, "effect card identity omitted from global (Crispin reverse-scoring "
                             "is captured through the option set); candidate future field"),
        "logs": (T, "compressed to the actual previous-action identity in history; full event "
                    "stream not sequence-encoded (stateless model; recurrence is future work)"),
        "search_begin_input": (O, "opaque engine-state blob; used only for the branch-and-rollout "
                                  "capability probe, never featurized as a model input"),
    }
    counts = {}
    for _f, (cls, _why) in fields.items():
        counts[cls] = counts.get(cls, 0) + 1
    return {
        "contract": "c007",
        "c006_encoder_dims": {"GDENSE": pf.GDENSE, "GROWS": pf.GROWS, "ODENSE": pf.ODENSE,
                              "OROWS": pf.OROWS, "PREV": pf.PREV, "card_feat": pf.CARD_FEAT},
        "v2_encoder_dims": enc.feature_dims(),
        "key_upgrades_over_c006": [
            "per-slot board (12 explicit slots) vs c006 averaged active + bag-mean bench",
            "exact hand & discard multisets (set encoders) vs c006 bag-mean vectors",
            "cross-option set encoder vs c006 independent per-option scoring",
            "actual previous selected-option identity in history vs c006 index-only prev",
            "richer per-slot dynamics: HP/energy-type/status/KO-range/evolution-stack/prize-yield",
            "zero-init id embedding residual for unseen legal cards vs c006 shared vocab embedding",
        ],
        "classification_counts": counts,
        "fields": {k: {"class": v[0], "justification": v[1]} for k, v in fields.items()},
    }


def run_tests():
    """Determinism + completeness + validity over all stored decisions."""
    tot = det_ok = err = nonfinite = mask_bad = 0
    for sp in ("train", "validation", "test"):
        games = {}
        with gzip.open(os.path.join(C006_SEQ, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                r = json.loads(line)
                games.setdefault(r["game_id"], []).append(r)
        for gid, rs in games.items():
            rs.sort(key=lambda r: r["decision_index"])
            prev = enc.initial_prev_state()
            for r in rs:
                try:
                    f1 = enc.encode(r["observation"], prev)
                    f2 = enc.encode(r["observation"], prev)
                    prev = enc.derive_prev_state(r["observation"], r["teacher_action_indices"])
                except Exception:  # noqa: BLE001
                    err += 1
                    continue
                tot += 1
                if all(np.array_equal(f1[k], f2[k]) for k in
                       ("board_rows", "board_dyn", "hand_rows", "hand_dyn", "hand_mask",
                        "disc_rows", "disc_mask", "global", "opt_dense", "opt_rows")):
                    det_ok += 1
                for k in ("board_dyn", "global", "opt_dense", "hand_dyn"):
                    if not np.isfinite(f1[k]).all():
                        nonfinite += 1
                        break
                if f1["opt_dense"].shape[0] != max(f1["n_options"], 1):
                    mask_bad += 1
    return {"decisions": tot, "deterministic": det_ok, "errors": err,
            "nonfinite": nonfinite, "shape_mismatch": mask_bad,
            "all_pass": err == 0 and det_ok == tot and nonfinite == 0 and mask_bad == 0}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    p.add_argument("--log-dir", required=True)
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.log_dir, exist_ok=True)
    sc = schema()
    fd = feature_diff()
    json.dump(sc, open(os.path.join(a.out_dir, "state_encoder_v2_schema.json"), "w"), indent=2)
    json.dump(fd, open(os.path.join(a.out_dir, "c006_vs_v2_feature_diff.json"), "w"), indent=2)
    tests = run_tests()
    lines = [
        "c007 AC-03 State Encoder v2 tests", "=" * 50,
        f"dims: {enc.feature_dims()}",
        f"decisions tested: {tests['decisions']}",
        f"deterministic (encode twice identical): {tests['deterministic']}/{tests['decisions']}",
        f"errors: {tests['errors']}   nonfinite: {tests['nonfinite']}   shape_mismatch: {tests['shape_mismatch']}",
        f"feature classification: {fd['classification_counts']}",
        f"ALL_PASS = {tests['all_pass']}",
    ]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(a.log_dir, "state_encoder_v2_tests.txt"), "w").write(txt)
    print(txt)
    return 0 if tests["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""c006 AC-04: build + validate the full legal-card vocabulary artifacts."""

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.card_vocab import (MAX_CARD_ID, MIN_CARD_ID, UNKNOWN_INVALID_ID,
                           build_vocab, dump_artifacts, row_for_id, validate_decks)


def run(args):
    os.makedirs(args.out_dir, exist_ok=True)
    meta = dump_artifacts(os.path.join(args.out_dir, "card_vocabulary.json"),
                          os.path.join(args.out_dir, "card_feature_schema.json"))
    v = build_vocab()
    checks = []

    def chk(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # determinism: hash stable across a fresh rebuild
    import cg.card_vocab as cv
    cv._CACHE.clear()
    v2 = cv.build_vocab()
    chk("source_hash_deterministic", v["source_hash"] == v2["source_hash"], v["source_hash"][:16])

    # every legal card id maps to a UNIQUE, non-reserved row (no <UNK> collapse)
    rows = [row_for_id(cid) for cid in range(MIN_CARD_ID, MAX_CARD_ID + 1)]
    chk("all_legal_ids_distinct_rows", len(set(rows)) == (MAX_CARD_ID - MIN_CARD_ID + 1)
        and UNKNOWN_INVALID_ID not in rows, f"{len(set(rows))} distinct rows")
    chk("vocab_size", v["vocab_size"] == 3 + (MAX_CARD_ID - MIN_CARD_ID + 1), v["vocab_size"])

    # invalid ids route to UNKNOWN_INVALID_ID (technical reserve), NOT a legal-card collapse
    chk("invalid_id_reserved", row_for_id(999999) == UNKNOWN_INVALID_ID
        and row_for_id("x") == UNKNOWN_INVALID_ID, "ok")

    # every teacher/opponent deck card present
    src = os.path.join(_REPO, "contracts", "c005_teacher_import_submission_and_dataset",
                       "results", "artifacts", "teacher_sources")
    deck_results = {}
    all_present = True
    for t in ("dragapult", "mega_lucario", "mega_abomasnow", "iono"):
        with open(os.path.join(src, t, "deck.csv")) as fh:
            ids = [int(x) for x in fh if x.strip()]
        r = validate_decks(ids)
        deck_results[t] = r
        all_present = all_present and r["all_present"]
    chk("all_deck_cards_present", all_present, deck_results)

    ok = all(c[1] for c in checks)
    print("=== card vocabulary ===")
    print(json.dumps(meta, indent=2))
    print("=== checks ===")
    for name, passed, detail in checks:
        print(f"  [{'OK ' if passed else 'FAIL'}] {name}: {detail}")
    print(f"ALL_OK={ok}")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

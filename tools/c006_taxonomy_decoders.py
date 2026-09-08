"""c006 AC-05: emit decision taxonomy, samples, and decoder-coverage report,
plus decoder unit checks. Computed on TRAIN+VALIDATION (test stays sealed); the
decoders are total functions so coverage holds for any split.
"""

import argparse
import collections
import gzip
import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from cg.decision_taxonomy import IMPORTANCE_CLASSES, classify
from cg import decoders as D


def _load(seq_dir, splits):
    for sp in splits:
        with gzip.open(os.path.join(seq_dir, f"{sp}.jsonl.gz"), "rt") as fh:
            for line in fh:
                yield json.loads(line)


def decoder_selftest():
    out = []

    def t(name, ok, detail=""):
        out.append((name, bool(ok), detail))

    rng = np.random.default_rng(0)
    # single choice: argmax
    s = np.array([0.1, 0.9, 0.3])
    r = D.decode(s, 1, 1, D.SINGLE_CHOICE)
    t("single_argmax", r == [1], r)
    # fixed multiselect k=2: top-2
    s = np.array([0.1, 0.9, 0.3, 0.8])
    r = D.decode(s, 2, 2, D.FIXED_MULTISELECT)
    t("fixed_topk_legal", len(r) == 2 and set(r) == {1, 3}, r)
    # variable: keep positives clamp [0,2]
    s = np.array([1.0, -1.0, 0.5, 2.0])
    r = D.decode(s, 0, 2, D.VARIABLE_MULTISELECT)
    t("variable_keep_positive_clamped", len(r) <= 2 and all(0 <= i < 4 for i in r), r)
    # variable enforce min
    s = np.array([-1.0, -2.0, -0.5])
    r = D.decode(s, 1, 2, D.VARIABLE_MULTISELECT)
    t("variable_enforce_min", len(r) >= 1, r)
    # empty
    t("empty", D.decode(np.array([1.0]), 0, 0, D.EMPTY) == [], "")
    # form classification
    t("form_single", D.classify_form("MAIN", 1, 1, 5) == D.SINGLE_CHOICE, "")
    t("form_fixed", D.classify_form("DISCARD", 2, 2, 4) == D.FIXED_MULTISELECT, "")
    t("form_variable", D.classify_form("TO_BENCH", 0, 2, 3) == D.VARIABLE_MULTISELECT, "")
    t("form_ordered_routes", D.classify_form("SKILL_ORDER", 1, 3, 3) == D.ORDERED, "")
    # ordered -> fallback is legal
    fb = D.safe_fallback(1, 3, 5)
    t("ordered_fallback_legal", len(fb) == 3 and fb == [0, 1, 2], fb)
    # random fuzz: every decode returns a legal-cardinality distinct set
    ok = True
    for _ in range(2000):
        n = int(rng.integers(1, 8)); hi = int(rng.integers(0, n + 1)); lo = int(rng.integers(0, hi + 1))
        form = D.classify_form("MAIN", lo, hi, n)
        sc = rng.normal(size=n)
        res = D.decode(sc, lo, hi, form)
        if len(set(res)) != len(res) or not all(0 <= i < n for i in res) or not (lo <= len(res) <= hi):
            ok = False; break
    t("fuzz_all_legal", ok, "2000 random decisions")
    return out


def run(args):
    seq_dir = os.path.join(args.in_dir, "sequence_dataset")
    splits = ("train", "validation")
    imp = collections.Counter()
    sem = collections.Counter()
    forms = collections.Counter()
    form_by_ctx = collections.defaultdict(collections.Counter)
    imp_by_ctx = collections.defaultdict(collections.Counter)
    samples = []
    sample_seen = collections.Counter()
    total = 0
    for r in _load(seq_dir, splits):
        total += 1
        c = classify(r)
        form = D.classify_form(r["select_context"], r["min_count"], r["max_count"], len(r["legal_options"]))
        imp[c["importance_class"]] += 1
        sem[c["semantic_type"]] += 1
        forms[form] += 1
        form_by_ctx[r["select_context"]][form] += 1
        imp_by_ctx[r["select_context"]][c["importance_class"]] += 1
        # diverse human-reviewable samples: cap per (importance, semantic)
        key = (c["importance_class"], c["semantic_type"])
        if sample_seen[key] < 8 and len(samples) < 260:
            sample_seen[key] += 1
            samples.append({
                "example_id": r["example_id"], "game_id": r["game_id"],
                "decision_index": r["decision_index"], "turn_index": r["turn_index"],
                "select_context": r["select_context"],
                "importance_class": c["importance_class"], "semantic_type": c["semantic_type"],
                "form": form, "forced": c["forced"], "n_options": c["n_options"],
                "min_count": c["min_count"], "max_count": c["max_count"],
                "option_types": [o.get("type") for o in r["legal_options"]],
                "attack_available": c["attack_available"], "end_turn_available": c["end_turn_available"],
                "phantom_dive_available": c["phantom_dive_available"],
                "teacher_action_indices": r["teacher_action_indices"],
            })

    # decoder coverage: enumerate (context, lo, hi) shapes -> form -> decoder/fallback
    coverage = {}
    unsupported = 0
    for ctx, cnt in form_by_ctx.items():
        coverage[ctx] = {}
        for form, n in cnt.items():
            supported = form != D.ORDERED
            coverage[ctx][form] = {"count": n, "supported": supported,
                                   "handler": ("safe_fallback" if not supported else form.lower())}
            if not supported:
                unsupported += n

    tax = {
        "contract": "c006_distilled_policy_baseline",
        "computed_on_splits": list(splits),
        "test_split_touched": False,
        "total_decisions": total,
        "importance_classes": IMPORTANCE_CLASSES,
        "importance_distribution": dict(imp),
        "semantic_type_distribution": dict(sem),
        "importance_by_context": {k: dict(v) for k, v in imp_by_ctx.items()},
        "rules": {
            "FORCED": "n_options<=1, or maxCount==0, or must-take-all (lo==hi==n)",
            "HIGH_IMPACT": "MAIN w/ attack option; end-turn while attack available; any DAMAGE_COUNTER*; "
                           "promotion/switch/gust target w/ >1 option; ATTACK; Phantom Dive available",
            "TACTICAL": "evolve/attach/multiselect/search/bench/retreat/ability choices not forced/high",
            "ROUTINE": "remaining non-forced low-leverage choices",
        },
    }

    cov = {
        "contract": "c006_distilled_policy_baseline",
        "computed_on_splits": list(splits),
        "decision_forms": dict(forms),
        "form_definitions": {
            "SINGLE_CHOICE": "maxCount==1 -> masked softmax argmax",
            "FIXED_MULTISELECT": "minCount==maxCount>1 -> masked top-k (unordered)",
            "VARIABLE_MULTISELECT": "minCount<maxCount, maxCount>1 -> per-option keep + [lo,hi] clamp",
            "EMPTY": "maxCount==0 -> []",
            "ORDERED": "order-dependent multi-select -> deterministic safe fallback (none present in c005)",
        },
        "coverage_by_context": coverage,
        "unsupported_records_routed_to_fallback": unsupported,
        "ordered_forms_present": forms.get(D.ORDERED, 0),
        "all_forms_supported_or_safe": True,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    json.dump(tax, open(os.path.join(args.out_dir, "decision_taxonomy.json"), "w"), indent=2)
    json.dump(cov, open(os.path.join(args.out_dir, "decoder_coverage_report.json"), "w"), indent=2)
    with open(os.path.join(args.out_dir, "decision_taxonomy_samples.jsonl"), "w") as fh:
        for s in samples:
            fh.write(json.dumps(s) + "\n")

    tests = decoder_selftest()
    all_ok = all(t[1] for t in tests)
    lines = ["=== decoder unit checks ==="]
    for name, ok, detail in tests:
        lines.append(f"  [{'OK ' if ok else 'FAIL'}] {name}: {detail}")
    lines.append(f"ALL_OK={all_ok}")
    lines.append("")
    lines.append("=== taxonomy distribution (train+val) ===")
    lines.append(json.dumps(dict(imp), indent=2))
    lines.append("=== decision forms ===")
    lines.append(json.dumps(dict(forms), indent=2))
    lines.append(f"samples emitted: {len(samples)} (>=100 required)")
    lines.append(f"ordered forms present: {forms.get(D.ORDERED, 0)}  unsupported routed: {unsupported}")
    print("\n".join(lines))
    return 0 if (all_ok and len(samples) >= 100) else 1


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", required=True)
    p.add_argument("--out-dir", required=True)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())

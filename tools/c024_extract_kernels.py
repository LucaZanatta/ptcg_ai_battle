"""c024 — flatten and extract the top-rated public kernels, without executing any of them.

`tools/c023_extract_kernels.py` already knows how a PTCG submission-generator kernel hides its
payload — a `MAIN_SOURCE` string literal, a `%%writefile main.py` cell, a base64 `PAYLOADS`
dict, or a base64 tarball — and reads each one as *data*. Its `auto` mode tries all four.

What it does not have is the flattening step (notebook JSON to a single `.py`), which was done
by hand for the c023 set. This adds it and re-points the c023 extractor at the c024 tree, so the
twelve kernels that advertise a ladder rating in their titles become runnable
`(main.py, deck.csv)` pairs under the same no-execution guarantee.

Reuse classification stays `LOCAL_BENCHMARK_ONLY`: the Kaggle API exposes no licence field for
notebooks (verified on a fresh `kernels_pull` — `kernel-metadata.json` has no `licenseName`, and
neither `kernels_list` nor the pull response carries one). These are opponents and sources of
*technique*, never a submission base.
"""

from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "tools"))

KROOT = os.path.join(_REPO, "external_refs", "c024_public_kernels")
FLAT = os.path.join(KROOT, "_flat")
OUT = os.path.join(KROOT, "_extracted")


CELL = "\n\n#%%CELL%%\n\n"


def flatten(path: str) -> str:
    """Notebook JSON to one source string. Cells joined in order, nothing evaluated.

    The separator is not cosmetic. `c023_extract_kernels._writefile_cell` splits on exactly
    this marker to recover cell boundaries, and returns *everything after* the magic line in
    the cell it matched. Join with a bare blank line and the whole notebook becomes one cell,
    so `%%writefile deck.csv` hands back the entire remaining notebook -- which parses as a
    deck only when the deck happens to be the last cell. That silently cost four extractions.
    """
    nb = json.load(open(path, encoding="utf-8", errors="replace"))
    parts = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source")
        parts.append("".join(src) if isinstance(src, list) else str(src))
    return CELL.join(parts)


def _patch(X) -> None:
    """Two emission shapes the c023 set never used, added without touching the frozen tool.

    Both are still read as *data*: a notebook magic cell's literal body, and a base64 blob
    decoded by `base64.b64decode`. Nothing from a kernel is executed or imported.
    """
    import re

    _b64 = X._b64_payloads

    def b64_payloads(src: str):
        out = _b64(src)
        if out:
            return out
        # `PAYLOAD_B64 = {'main.py': '<b64>', ...}` -- singular, and the dict is not anchored
        # to the start of a line in every kernel.
        m = re.search(r"PAYLOAD_B64\s*=\s*(\{.*?\})\s*\n", src, re.S)
        if not m:
            return out
        try:
            import ast as _ast
            import base64 as _b
            d = _ast.literal_eval(m.group(1))
        except Exception:  # noqa: BLE001
            return out
        for k, v in d.items():
            if isinstance(v, str):
                try:
                    out[k] = _b.b64decode(v).decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    pass
        return out

    _deck_from_list = X._deck_from_list

    def deck_from_list(src: str, var: str = "DECK"):
        # A `%%writefile deck.csv` cell is the commonest shape in the rating-advertising set,
        # and c023's chain never looked for one -- it only ever read a DECK list literal, a
        # DECK_SOURCE string or a payload entry. Try the cell first, then fall through.
        cell = X._writefile_cell(src, "deck.csv")
        if cell:
            d = X._deck_from_text(cell)
            if d:
                return d
        return _deck_from_list(src, var)

    X._b64_payloads = b64_payloads
    X._deck_from_list = deck_from_list


def main() -> int:
    os.makedirs(FLAT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    kernels = []
    for name in sorted(os.listdir(KROOT)):
        d = os.path.join(KROOT, name)
        if not os.path.isdir(d) or name.startswith("_"):
            continue
        nb = next((f for f in sorted(os.listdir(d)) if f.endswith(".ipynb")), None)
        if nb is None:
            print(f"MISS  {name}: no notebook")
            continue
        with open(os.path.join(FLAT, name + ".py"), "w", encoding="utf-8") as fh:
            fh.write(flatten(os.path.join(d, nb)))
        kernels.append(name)

    import c023_extract_kernels as X
    X.KROOT, X.FLAT, X.OUT = KROOT, FLAT, OUT
    _patch(X)

    results = []
    for k in kernels:
        r = X.extract(k)
        if r is None:
            print(f"MISS  {k}: no main source found by any mode")
            results.append({"kernel": k, "error": "no_main_source"})
        elif "error" in r:
            print(f"PART  {k}: {r['error']}")
            results.append(r)
        else:
            r["reuse_classification"] = "LOCAL_BENCHMARK_ONLY"
            with open(os.path.join(OUT, k, "PROVENANCE.json"), "w") as fh:
                json.dump(r, fh, indent=2)
            n = len(open(os.path.join(OUT, k, "main.py")).read())
            print(f"OK    {k}  main={n}B deck={r['deck_sha256'][:12]} "
                  f"uniq={len(r['deck_unique_ids'])}")
            results.append(r)

    with open(os.path.join(OUT, "EXTRACTION.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    ok = sum(1 for r in results if "error" not in r)
    print(f"\n{ok}/{len(results)} extracted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

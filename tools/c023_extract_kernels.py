"""c023 — extract runnable (main.py, deck.csv) pairs from pulled public Kaggle kernels.

Every kernel here is a *submission generator*: it emits `main.py` + `deck.csv` + the official
`cg` SDK into a tarball. This tool reproduces the emission WITHOUT executing kernel code —
each source is read as data (string literal, notebook magic cell, or base64 payload) so a
kernel cannot run arbitrary code in this repository.

Output: external_refs/c023_public_kernels/_extracted/<kernel>/{main.py,deck.csv,PROVENANCE.json}
laid out exactly like the c005 teacher_sources tree, so `cg.teachers.make_fresh`-style loading
works unchanged.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import os
import re
import sys
import tarfile
from typing import Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KROOT = os.path.join(_REPO, "external_refs", "c023_public_kernels")
FLAT = os.path.join(KROOT, "_flat")
OUT = os.path.join(KROOT, "_extracted")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _literals(src: str) -> Dict[str, str]:
    """Top-level `NAME = '''...'''` string constants, parsed (never executed)."""
    out: Dict[str, str] = {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                out[node.targets[0].id] = node.value.value
    return out


def _b64_payloads(src: str) -> Dict[str, str]:
    """`PAYLOADS = {"main.py": "<b64>", ...}` decoded as data."""
    out: Dict[str, str] = {}
    m = re.search(r"^PAYLOADS\s*=\s*(\{.*?\})\s*$", src, re.M | re.S)
    if not m:
        return out
    try:
        d = ast.literal_eval(m.group(1))
    except Exception:
        return out
    for k, v in d.items():
        try:
            out[k] = base64.b64decode(v).decode("utf-8")
        except Exception:
            pass
    return out


def _asset_tar(src: str) -> Dict[str, bytes]:
    """`ASSET_B64 = '<b64 of a .tar.gz>'` — members returned as bytes, extraction is in-memory."""
    m = re.search(r"^ASSET_B64\s*=\s*'([^']+)'", src, re.M)
    if not m:
        return {}
    raw = base64.b64decode(m.group(1))
    out: Dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for mem in tf.getmembers():
            if not mem.isfile():
                continue
            f = tf.extractfile(mem)
            if f is not None:
                out[mem.name] = f.read()
    return out


def _writefile_cell(src: str, name: str) -> Optional[str]:
    """Text of a `%%writefile <name>` notebook cell (cells joined by the flattener marker)."""
    for cell in src.split("\n\n#%%CELL%%\n\n"):
        lines = cell.split("\n")
        for i, ln in enumerate(lines):
            if ln.strip().startswith("%%writefile") and ln.strip().endswith(name):
                return "\n".join(lines[i + 1:])
    return None


def _deck_from_list(src: str, var: str = "DECK") -> Optional[List[int]]:
    m = re.search(r"^%s\s*=\s*(\[[^\]]*\])" % var, src, re.M | re.S)
    if not m:
        return None
    try:
        v = ast.literal_eval(m.group(1))
    except Exception:
        return None
    return [int(x) for x in v] if len(v) == 60 else None


def _deck_from_text(txt: str) -> Optional[List[int]]:
    vals = [int(x) for x in txt.split() if x.strip().isdigit()]
    return vals if len(vals) == 60 else None


EXTRACTORS: Dict[str, str] = {
    "jazivxt_codex-sol-eclipse-alakazam": "literal",
    "jazivxt_a-better-hand-alakazam-rising-tide-v21": "writefile",
    "raunakdey07_pok-mon-tcg-advanced-heuristic-agent": "writefile",
    "prvsiyan_ptcg-ai-battle-search-audited-alakazam-v12": "payloads",
    "tetsutani_grimmsnarl-ex-damage-transfer-control": "asset",
    "makthanithin_pokemon-tcg-ai-battle-1084-5-baseline": "writefile",
}


def extract(kernel: str) -> Optional[Dict[str, object]]:
    path = os.path.join(FLAT, kernel + ".py")
    if not os.path.exists(path):
        return None
    src = open(path, encoding="utf-8", errors="replace").read()
    mode = EXTRACTORS.get(kernel, "auto")
    main_src: Optional[str] = None
    deck: Optional[List[int]] = None

    if mode in ("literal", "auto"):
        lit = _literals(src)
        main_src = lit.get("MAIN_SOURCE") or main_src
        if lit.get("DECK_SOURCE"):
            deck = _deck_from_text(lit["DECK_SOURCE"]) or deck
    if main_src is None and mode in ("payloads", "auto"):
        pay = _b64_payloads(src)
        main_src = pay.get("main.py") or main_src
        if pay.get("deck.csv"):
            deck = _deck_from_text(pay["deck.csv"]) or deck
    if main_src is None and mode in ("asset", "auto"):
        members = _asset_tar(src)
        # An asset kernel ships a whole package tree, not one file. Write the entire tree so
        # relative imports resolve, and take the TOP-LEVEL main.py / deck.csv as the entry point.
        d = os.path.join(OUT, kernel)
        for name, blob in members.items():
            if os.path.isabs(name) or ".." in name.split("/"):
                continue
            p = os.path.join(d, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(blob)
        if "main.py" in members:
            main_src = members["main.py"].decode("utf-8", "replace")
        if "deck.csv" in members and deck is None:
            deck = _deck_from_text(members["deck.csv"].decode("utf-8", "replace"))
    if main_src is None and mode in ("writefile", "auto"):
        main_src = _writefile_cell(src, "main.py")

    if main_src is None:
        return None
    if deck is None:
        deck = _deck_from_list(main_src) or _deck_from_list(src)
    if deck is None:
        # last resort: a 60-line integer block written to deck.csv in the generator
        m = re.search(r"deck\.csv['\"]\)\.write_text\(\s*['\"]([\d\s\\n]+)['\"]", src)
        if m:
            deck = _deck_from_text(m.group(1).replace("\\n", "\n"))
    if deck is None:
        m = re.search(r"\.write_text\(\s*r?'''\s*([\d\s]+?)'''", src, re.S)
        if m:
            deck = _deck_from_text(m.group(1))
    if deck is None:
        return {"kernel": kernel, "error": "deck_not_found", "main_bytes": len(main_src)}

    d = os.path.join(OUT, kernel)
    os.makedirs(d, exist_ok=True)
    mb = main_src.encode("utf-8")
    db = ("\n".join(str(c) for c in deck) + "\n").encode("utf-8")
    with open(os.path.join(d, "main.py"), "wb") as fh:
        fh.write(mb)
    with open(os.path.join(d, "deck.csv"), "wb") as fh:
        fh.write(db)
    meta_path = os.path.join(KROOT, kernel, "kernel-metadata.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    prov = {
        "kernel_ref": meta.get("id", kernel),
        "title": meta.get("title"),
        "extraction_mode": mode,
        "extracted_from": os.path.relpath(path, _REPO),
        "main_sha256": sha256_bytes(mb),
        "deck_sha256": sha256_bytes(db),
        "deck": deck,
        "deck_unique_ids": sorted(set(deck)),
        "executed_kernel_code": False,
        "reuse_classification": "PENDING_LICENSE_REVIEW",
    }
    with open(os.path.join(d, "PROVENANCE.json"), "w") as fh:
        json.dump(prov, fh, indent=2)
    return prov


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    results = []
    names = sorted(EXTRACTORS) if len(sys.argv) < 2 else sys.argv[1:]
    for k in names:
        r = extract(k)
        if r is None:
            print(f"MISS  {k}")
            results.append({"kernel": k, "error": "no_main_source"})
        elif "error" in r:
            print(f"PART  {k}: {r['error']}")
            results.append(r)
        else:
            print(f"OK    {k}  main={len(open(os.path.join(OUT, k, 'main.py')).read())}B "
                  f"deck={r['deck_sha256'][:12]} uniq={len(r['deck_unique_ids'])}")
            results.append(r)
    with open(os.path.join(OUT, "EXTRACTION.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

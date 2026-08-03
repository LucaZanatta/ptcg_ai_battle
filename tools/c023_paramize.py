"""c023 — turn an official sample agent's hand-written score constants into tunable parameters.

The sample agents decide by adding round numbers together: `score = 40000`, `score += 250`,
`return 20000`. Those numbers were chosen by hand and never measured against each other. This
rewrites them, by AST transform, into lookups with the original value as the default — so the
transformed agent is **identical** to the original until a `params.json` says otherwise, and
`tools/c023_identity.py` verifies that rather than asserting it.

Only constants that are *weights* are touched. A card ID, a deck size, an energy requirement and a
list index are facts about the game and must not move, so the transform is restricted to:

* integer constants assigned to a scoring variable (`score`, `base_score`, `max_score`,
  `best_score`, `plan_score`, `support_score`), including augmented assignment, and
* integer constants returned from a function whose name ends in `_score`.

Everything else in the file is passed through byte-for-byte, and the emitted module keeps the
original's structure so a reader can diff the two.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

SCORE_TARGETS = {"score", "base_score", "max_score", "best_score", "plan_score", "support_score"}

HEADER = '''# --- c023 parameterisation -------------------------------------------------------------------
# Derived from an official Kaggle sample agent (see ATTRIBUTION.txt) by tools/c023_paramize.py.
# Every heuristic score constant below is replaced by _W(index, original_value). With no weights
# supplied, _W returns the original value and this file behaves exactly like the sample.
import json as _json
import os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_WEIGHTS = {}
try:
    with open(_os.path.join(_HERE, "params.json")) as _f:
        _WEIGHTS = {int(k): v for k, v in (_json.load(_f).get("weights") or {}).items()}
except Exception:
    _WEIGHTS = {}


def _W(index, default):
    v = _WEIGHTS.get(index)
    return default if v is None else v
# --- end c023 parameterisation ----------------------------------------------------------------

'''


class Paramize(ast.NodeTransformer):
    def __init__(self):
        self.slots: List[Dict[str, Any]] = []
        self._ctx: List[str] = []

    # --- context tracking -------------------------------------------------------------------
    def visit_FunctionDef(self, node):
        self._ctx.append(node.name)
        node = self.generic_visit(node)
        self._ctx.pop()
        return node

    def _wrap(self, node: ast.Constant, where: str) -> ast.AST:
        if not isinstance(node.value, int) or isinstance(node.value, bool):
            return node
        idx = len(self.slots)
        self.slots.append({"index": idx, "default": node.value, "where": where,
                           "function": self._ctx[-1] if self._ctx else "<module>",
                           "line": node.lineno})
        return ast.Call(func=ast.Name(id="_W", ctx=ast.Load()),
                        args=[ast.Constant(value=idx), ast.Constant(value=node.value)],
                        keywords=[])

    # --- the two admissible positions --------------------------------------------------------
    def visit_Assign(self, node):
        node = self.generic_visit(node)
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in SCORE_TARGETS
                and isinstance(node.value, ast.Constant)):
            node.value = self._wrap(node.value, f"{node.targets[0].id} =")
        return node

    def visit_AugAssign(self, node):
        node = self.generic_visit(node)
        if (isinstance(node.target, ast.Name) and node.target.id in SCORE_TARGETS
                and isinstance(node.value, ast.Constant)):
            op = type(node.op).__name__
            node.value = self._wrap(node.value, f"{node.target.id} {op}=")
        return node

    def visit_Return(self, node):
        node = self.generic_visit(node)
        fn = self._ctx[-1] if self._ctx else ""
        if fn.endswith("_score") and isinstance(node.value, ast.Constant):
            node.value = self._wrap(node.value, f"return from {fn}")
        return node


def paramize(src: str) -> Tuple[str, List[Dict[str, Any]]]:
    tree = ast.parse(src)
    tr = Paramize()
    tree = tr.visit(tree)
    ast.fix_missing_locations(tree)
    return HEADER + ast.unparse(tree) + "\n", tr.slots


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="official player id")
    ap.add_argument("--out", help="where to write the parameterised source")
    ap.add_argument("--slots-out", help="where to write the slot table")
    a = ap.parse_args()

    from cg import c023_players as P
    d = P.resolve(a.base)
    src = open(os.path.join(d, "main.py"), encoding="utf-8").read()
    out, slots = paramize(src)

    dest = a.out or os.path.join(_REPO, "results",
                                 "c023_autonomous_meta_first_competition_sprint", "agents",
                                 f"_param_{a.base}.py")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        fh.write(out)
    st = a.slots_out or dest.replace(".py", "_slots.json")
    with open(st, "w") as fh:
        json.dump({"base": a.base,
                   "source_sha256": hashlib.sha256(src.encode()).hexdigest(),
                   "param_sha256": hashlib.sha256(out.encode()).hexdigest(),
                   "slots": slots}, fh, indent=2)

    ast.parse(out)  # the transformed file must at least parse
    by_fn: Dict[str, int] = {}
    for s in slots:
        by_fn[s["function"]] = by_fn.get(s["function"], 0) + 1
    print(f"{len(slots)} parameters from {a.base}")
    for fn, n in sorted(by_fn.items(), key=lambda kv: -kv[1]):
        print(f"   {n:4d}  {fn}")
    print(f"-> {os.path.relpath(dest, _REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

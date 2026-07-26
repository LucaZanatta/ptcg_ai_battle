"""c012 §26 / AC-15 — the mandatory Python source bundle.

Intended for external debugging and audit, so it must be self-sufficient: every tracked
repository *.py at final HEAD (enumerated from Git, not from a hand-maintained list, per
§26.1), every c011 Python file actually used, all c011 tests, every entrypoint invoked in
COMMANDS_RUN.md, a SHA-256 manifest, dependency and machine snapshots, the Git patch, and
import/entrypoint inventories.

Excluded (§26.2): virtualenvs and site-packages, __pycache__, .pyc, credentials/tokens/env
files, model checkpoints and large datasets, and raw game records that already live
elsewhere in results/.

Validation (§26.3) extracts into a clean temporary directory, verifies every manifest hash,
verifies every tracked file and every executed entrypoint is represented, verifies no
forbidden secret-pattern filename slipped in, and verifies the archive's own SHA-256.
"""

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C012 = os.path.join(_REPO, "contracts", "c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification")
ART = os.path.join(C012, "results", "artifacts")
LOGD = os.path.join(C012, "results", "test_logs")
BUNDLE = os.path.join(ART, "c012_python_source_bundle.zip")
MANIFEST = os.path.join(ART, "c012_python_source_manifest.csv")
SHAFILE = os.path.join(ART, "c012_python_source_bundle.sha256")
ENTRYPOINTS = os.path.join(ART, "c012_python_entrypoints.json")

SECRET_PATTERNS = ("kaggle.json", ".env", "credential", "secret", "token", "cookie",
                   ".netrc", "id_rsa", ".pem", ".key")
EXCLUDE_DIRS = (".venv", "site-packages", "__pycache__", ".git", "node_modules")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def git(*a):
    return subprocess.run(["git", "-C", _REPO, *a], capture_output=True, text=True).stdout


def tracked_python_files():
    """Every tracked *.py at HEAD, from Git itself (§26.1 item 1)."""
    out = git("ls-tree", "-r", "--name-only", "HEAD")
    return sorted(f for f in out.splitlines()
                  if f.endswith(".py") and not any(d in f for d in EXCLUDE_DIRS))


def untracked_c011_python():
    """§26.1 item 2 — untracked/generated Python actually used during execution.

    Deliberately NOT every untracked *.py in the tree: earlier contracts store
    `results/artifacts/source_snapshot/` copies of their own source, which would add ~240
    duplicate files that §26.2 already excludes as "raw ... already stored elsewhere in
    results". Only real working-tree source directories are included.
    """
    out = git("ls-files", "--others", "--exclude-standard")
    keep_roots = ("tools/", "starter_kit/", "tests/", "cg/")
    res = []
    for f in out.splitlines():
        if not f.endswith(".py") or any(d in f for d in EXCLUDE_DIRS):
            continue
        if "/results/" in f:                       # another contract's snapshot copy
            continue
        if f.startswith(keep_roots) or "/" not in f:
            res.append(f)
    return sorted(res)


def entrypoints_from_commands():
    """Python files named by commands in COMMANDS_RUN.md (§26.1 item 4)."""
    p = os.path.join(C012, "results", "COMMANDS_RUN.md")
    found = {}
    if os.path.exists(p):
        for ln in open(p):
            for tok in ln.replace("`", " ").split():
                if tok.endswith(".py"):
                    tok = tok.lstrip("$").strip("'\"")
                    if os.path.exists(os.path.join(_REPO, tok)):
                        found.setdefault(tok, []).append(ln.strip())
    return found


def import_inventory(paths):
    """Static import graph for the c011 entrypoints (§26.1 item 9)."""
    graph = {}
    for rel in paths:
        ap = os.path.join(_REPO, rel)
        if not os.path.exists(ap):
            continue
        try:
            tree = ast.parse(open(ap, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            graph[rel] = {"error": "unparseable"}
            continue
        imps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imps.update(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imps.add(node.module)
        graph[rel] = sorted(imps)
    return graph


def build():
    os.makedirs(ART, exist_ok=True); os.makedirs(LOGD, exist_ok=True)
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    head = git("rev-parse", "HEAD").strip()

    tracked = tracked_python_files()
    untracked = [f for f in untracked_c011_python()]
    eps = entrypoints_from_commands()
    c011_files = sorted({f for f in tracked + untracked
                         if os.path.basename(f).startswith(("c012_", "test_c011_"))})
    members = sorted(set(tracked) | set(untracked) | set(eps))

    rows = []
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in members:
            ap = os.path.join(_REPO, rel)
            if not os.path.exists(ap):
                continue
            if any(pat in rel.lower() for pat in SECRET_PATTERNS):
                continue
            arc = os.path.join("source", rel)
            data = open(ap, "rb").read()
            z.writestr(arc, data)
            rows.append({"original_path": rel, "archive_path": arc,
                         "bytes": len(data),
                         "git_status": ("tracked" if rel in tracked else "untracked"),
                         "sha256": sha_bytes(data)})

        # contract, command, inputs, references (§26.1 item 11)
        for sub in ("CONTRACT.md", "CLAUDE_COMMAND.txt"):
            p = os.path.join(C012, sub)
            if os.path.exists(p):
                z.write(p, os.path.join("contract", sub))
        for sub in ("inputs", "references"):
            d = os.path.join(C012, sub)
            for dp, _dn, fns in os.walk(d):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    z.write(fp, os.path.join("contract", sub, os.path.relpath(fp, d)))

        # §51: prompts, schemas and SANITIZED Claude inputs/outputs
        for extra in ("claude_prompt.md", "claude_label_schema.json", "claude_preflight.json",
                      "hard_state_manifest.json", "curriculum_registry.json",
                      "curriculum_registry.sha256"):
            ep = os.path.join(ART, extra)
            if os.path.exists(ep):
                z.write(ep, os.path.join("claude", extra))
        for gzf in ("claude_inputs.jsonl.gz", "claude_outputs.jsonl.gz"):
            gp = os.path.join(ART, gzf)
            if os.path.exists(gp):
                import gzip as _gz
                rows = []
                for ln in _gz.open(gp, "rt"):
                    r = json.loads(ln)
                    r.pop("session_id", None)          # sanitised: no session identifiers
                    rows.append(r)
                z.writestr(os.path.join("claude", gzf.replace(".gz", "")),
                           "\n".join(json.dumps(r) for r in rows))

        # environment + git (§26.1 items 6-8)
        pipfreeze = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                                   capture_output=True, text=True).stdout
        z.writestr("environment/pip_freeze.txt", pipfreeze)
        hw = {}
        hp = os.path.join(ART, "hardware_environment.json")
        if os.path.exists(hp):
            hw = json.load(open(hp))
        z.writestr("environment/machine.json", json.dumps(hw, indent=2))
        z.writestr("git/branch_head.json", json.dumps(
            {"branch": branch, "initial_head_c010": git("rev-parse", "HEAD~99").strip() or None,
             "final_head": head}, indent=2))
        z.writestr("git/c012.patch", git("diff", "a3dcdd6456f54717d0b6a5d40d1e659f9b214d35..HEAD"))
        z.writestr("git/status_short.txt", git("status", "--short"))

        graph = import_inventory(c011_files)
        z.writestr("inventory/import_graph.json", json.dumps(graph, indent=2))
        z.writestr("inventory/entrypoints.json", json.dumps(
            {"from_commands_run": eps, "c012_python_files": c011_files}, indent=2))
        z.writestr("inventory/manifest.csv", _manifest_csv(rows))
        z.writestr("README.txt",
                   "c012 Python source bundle\n"
                   "=========================\n\n"
                   f"branch: {branch}\nfinal HEAD: {head}\n\n"
                   "source/       every tracked *.py at final HEAD + every untracked c011 *.py\n"
                   "contract/     the exact contract, command, inputs and references\n"
                   "environment/  pip freeze + machine/CUDA snapshot\n"
                   "git/          branch/HEAD, c011 patch, working-tree status\n"
                   "inventory/    SHA-256 manifest, import graph, entrypoint list\n\n"
                   "Excluded by §26.2: .venv/site-packages, __pycache__, .pyc, credentials,\n"
                   "checkpoints, datasets, and raw game records stored elsewhere in results/.\n")

    with open(MANIFEST, "w", newline="") as fh:
        fh.write(_manifest_csv(rows))
    bsha = sha_file(BUNDLE)
    open(SHAFILE, "w").write(f"{bsha}  {os.path.basename(BUNDLE)}\n")
    json.dump({"from_commands_run": eps, "c012_python_files": c011_files,
               "import_graph": graph,
               "n_tracked_python": len(tracked), "n_untracked_python": len(untracked),
               "n_members": len(rows)},
              open(ENTRYPOINTS, "w"), indent=2)
    return {"bundle": BUNDLE, "sha256": bsha, "members": len(rows),
            "tracked": len(tracked), "untracked": len(untracked), "entrypoints": len(eps)}


def _manifest_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["original_path", "archive_path", "bytes",
                                        "git_status", "sha256"])
    w.writeheader()
    for r in sorted(rows, key=lambda x: x["original_path"]):
        w.writerow(r)
    return buf.getvalue()


def validate():
    """§26.3 — clean extraction, hash verification, coverage and secret checks."""
    checks = []

    def rec(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    rec("bundle_exists", os.path.exists(BUNDLE))
    if not os.path.exists(BUNDLE):
        return _finish(checks)
    declared = open(SHAFILE).read().split()[0] if os.path.exists(SHAFILE) else None
    rec("archive_sha256_matches_recorded", declared == sha_file(BUNDLE), declared)

    tmp = tempfile.mkdtemp(prefix="c012bundle_")
    try:
        with zipfile.ZipFile(BUNDLE) as z:
            bad = z.testzip()
            rec("archive_not_corrupt", bad is None, bad or "")
            z.extractall(tmp)
        rows = list(csv.DictReader(open(MANIFEST)))
        rec("manifest_non_empty", len(rows) > 0, len(rows))
        mismatched = []
        for r in rows:
            ap = os.path.join(tmp, r["archive_path"])
            if not os.path.exists(ap) or sha_file(ap) != r["sha256"]:
                mismatched.append(r["original_path"])
        rec("every_manifest_hash_verifies_after_extraction", not mismatched, mismatched[:5])

        present = {r["original_path"] for r in rows}
        missing_tracked = [f for f in tracked_python_files() if f not in present]
        rec("all_tracked_python_files_present", not missing_tracked, missing_tracked[:5])
        eps = entrypoints_from_commands()
        missing_eps = [f for f in eps if f not in present]
        rec("all_executed_entrypoints_present", not missing_eps, missing_eps[:5])
        c011_tests = [f for f in tracked_python_files() + untracked_c011_python()
                      if os.path.basename(f).startswith("test_c011_")]
        rec("all_c011_tests_present", all(f in present for f in c011_tests),
            f"{len(c011_tests)} tests")

        names = [n for n in zipfile.ZipFile(BUNDLE).namelist()]
        leaked = [n for n in names if any(p in n.lower() for p in SECRET_PATTERNS)]
        rec("no_forbidden_secret_filenames", not leaked, leaked[:5])
        excluded = [n for n in names if any(d in n for d in ("__pycache__", ".venv",
                                                             "site-packages"))
                    or n.endswith(".pyc")]
        rec("no_excluded_artifacts", not excluded, excluded[:5])
        heavy = [n for n in names if n.endswith((".npz", ".pt", ".jsonl.gz", ".tar.gz"))]
        rec("no_checkpoints_or_datasets", not heavy, heavy[:5])
        for req in ("environment/pip_freeze.txt", "environment/machine.json",
                    "git/c012.patch", "inventory/import_graph.json",
                    "inventory/entrypoints.json", "inventory/manifest.csv",
                    "contract/CONTRACT.md"):
            rec(f"contains_{req.replace('/', '_')}", req in names)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _finish(checks)


def _finish(checks):
    ok = all(c["ok"] for c in checks)
    inv = {"all_ok": ok, "n_checks": len(checks),
           "n_failed": sum(1 for c in checks if not c["ok"]),
           "bundle": os.path.relpath(BUNDLE, _REPO),
           "sha256": sha_file(BUNDLE) if os.path.exists(BUNDLE) else None,
           "checks": checks}
    with open(os.path.join(LOGD, "python_source_bundle_validation.txt"), "w") as fh:
        fh.write("c012 AC-15 Python source bundle validation (§26.3)\n\n")
        for c in checks:
            fh.write(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['check']}  {c['detail']}\n")
        fh.write(f"\nALL_OK = {ok}\n")
        if os.path.exists(MANIFEST):
            rows = list(csv.DictReader(open(MANIFEST)))
            fh.write(f"\nInventory: {len(rows)} Python files\n")
            for r in sorted(rows, key=lambda x: x["original_path"])[:400]:
                fh.write(f"  {r['git_status']:9s} {r['bytes']:>8s}B  {r['sha256'][:12]}  "
                         f"{r['original_path']}\n")
    json.dump(inv, open(os.path.join(ART, "python_source_bundle_validation.json"), "w"),
              indent=2)
    print(json.dumps({k: inv[k] for k in ("all_ok", "n_checks", "n_failed", "sha256")},
                     indent=2))
    return ok


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all", choices=["build", "validate", "all"])
    a = p.parse_args(argv)
    if a.stage in ("build", "all"):
        print(json.dumps(build(), indent=2))
    ok = True
    if a.stage in ("validate", "all"):
        ok = validate()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

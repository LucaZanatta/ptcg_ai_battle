"""Verify runtime assets declared in runtime_assets.json.

Validates presence, kind (file/dir/symlink/python_env), symlink targets, and
SHA-256 where supplied. Prints a concise PASS/FAIL table and exits 0 only when
every *required* asset passes.

Usage (from repo root):
  .venv/bin/python tools/verify_runtime_assets.py
  .venv/bin/python tools/verify_runtime_assets.py --manifest runtime_assets.json
  .venv/bin/python tools/verify_runtime_assets.py --json
"""

import argparse
import hashlib
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_python_env(spec):
    """spec like 'kaggle_environments:cabt' -> import module, check env registered."""
    module_name, _, env_name = spec.partition(":")
    try:
        mod = __import__(module_name)
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, f"import {module_name} failed: {exc!r}"
    if env_name:
        envs_dir = os.path.join(os.path.dirname(mod.__file__), "envs")
        try:
            registered = os.path.isdir(os.path.join(envs_dir, env_name))
        except Exception as exc:  # pragma: no cover
            return False, f"cannot list envs: {exc!r}"
        if not registered:
            return False, f"env '{env_name}' not registered under {envs_dir}"
        return True, f"import ok; env '{env_name}' registered"
    return True, "import ok"


def verify_asset(asset, repo_root):
    """Return (ok: bool, status: str, detail: str)."""
    kind = asset.get("kind")
    rel = asset["path"]
    abspath = os.path.join(repo_root, rel)

    if kind == "python_env":
        ok, detail = _check_python_env(rel)
        return ok, ("PASS" if ok else "FAIL"), detail

    if kind == "symlink":
        if not os.path.islink(abspath):
            return False, "FAIL", "not a symlink (or missing)"
        target = os.readlink(abspath)
        expected = asset.get("symlink_target")
        if expected is not None and target != expected:
            return False, "FAIL", f"symlink target {target!r} != expected {expected!r}"
        resolved = os.path.realpath(abspath)
        if not os.path.exists(resolved):
            return False, "FAIL", f"symlink target does not resolve: {target!r}"
        return True, "PASS", f"-> {target}"

    if kind == "dir":
        if not os.path.isdir(abspath):
            return False, "FAIL", "directory missing"
        return True, "PASS", "dir present"

    if kind == "file":
        if os.path.islink(abspath) or not os.path.isfile(abspath):
            return False, "FAIL", "file missing"
        detail_bits = []
        size = asset.get("size")
        if size is not None:
            actual = os.path.getsize(abspath)
            if actual != size:
                return False, "FAIL", f"size {actual} != expected {size}"
            detail_bits.append(f"size={actual}")
        sha = asset.get("sha256")
        if sha:
            actual = _sha256(abspath)
            if actual != sha:
                return False, "FAIL", f"sha256 mismatch ({actual[:12]}...)"
            detail_bits.append("sha256 ok")
        return True, "PASS", (", ".join(detail_bits) or "present")

    return False, "FAIL", f"unknown kind {kind!r}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify runtime assets")
    parser.add_argument("--manifest", default=os.path.join(_REPO_ROOT, "runtime_assets.json"))
    parser.add_argument("--repo-root", default=_REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    with open(args.manifest, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    results = []
    required_failures = 0
    for asset in manifest["assets"]:
        ok, status, detail = verify_asset(asset, args.repo_root)
        required = asset.get("required", True)
        if required and not ok:
            required_failures += 1
        results.append({
            "name": asset["name"], "path": asset["path"], "kind": asset.get("kind"),
            "asset_type": asset.get("asset_type"), "required": required,
            "must_be_tracked": asset.get("must_be_tracked"),
            "ok": ok, "status": status, "detail": detail,
        })

    exit_code = 1 if required_failures else 0

    if args.json:
        print(json.dumps({
            "manifest": os.path.relpath(args.manifest, args.repo_root),
            "total": len(results),
            "required_failures": required_failures,
            "exit_code": exit_code,
            "assets": results,
        }, indent=2))
        return exit_code

    # Human-readable table.
    name_w = max((len(r["name"]) for r in results), default=4)
    type_w = max((len(str(r["asset_type"])) for r in results), default=6)
    print(f"{'STATUS':6}  {'NAME':{name_w}}  {'TYPE':{type_w}}  {'REQ':3}  {'TRACKED':7}  DETAIL")
    for r in results:
        print(f"{r['status']:6}  {r['name']:{name_w}}  {str(r['asset_type']):{type_w}}  "
              f"{'yes' if r['required'] else 'no ':3}  "
              f"{('yes' if r['must_be_tracked'] else 'ext'):7}  {r['detail']}")
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    print(f"\n{passed}/{total} assets passed; required failures: {required_failures}")
    print("RESULT:", "PASS" if exit_code == 0 else "FAIL")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""c013 AC-15 — the source bundle, and a validation that opens it again.

The command requires a zip containing "every Python source, test, executed entrypoint,
ensemble/soup implementation, semantic serializer, Claude prompt/schema, sanitized
inputs/outputs, dependency/machine snapshots, Git patch, manifest, contract, command, inputs,
and references".

Building a zip is easy; proving it is the right zip is the part that matters. So after writing
the archive this module REOPENS it and checks, against the archive's own bytes:

  * every manifest entry is present in the archive and its SHA-256 inside the archive equals
    the SHA-256 recorded for the file on disk;
  * every required category is non-empty -- a bundle missing all tests should fail loudly rather
    than pass because the zip exists;
  * every Python member compiles;
  * no credential-shaped content is present. c012's command and this one both say "do not
    expose credentials", and a bundle is exactly where a stray token would travel.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from typing import Any, Dict, List

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

C013 = os.path.join(_REPO, "contracts",
                    "c013_fixed_deck_policy_combination_and_learnability")
RES = os.path.join(C013, "results")
ART = os.path.join(RES, "artifacts")
LOGD = os.path.join(RES, "test_logs")
ZIP = os.path.join(ART, "c013_python_source_bundle.zip")

CRED = re.compile(
    r"(kaggle\.json|KAGGLE_KEY|api[_-]?token|BEGIN [A-Z ]*PRIVATE KEY|"
    r"sk-ant-[A-Za-z0-9\-_]{8,}|AKIA[0-9A-Z]{16}|\"key\"\s*:\s*\"[A-Za-z0-9]{20,}\")",
    re.IGNORECASE)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def collect() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def add(path: str, arc: str, category: str):
        if os.path.exists(path) and os.path.isfile(path):
            items.append({"original_path": os.path.relpath(path, _REPO),
                          "archive_path": arc, "category": category,
                          "sha256": sha_file(path), "bytes": os.path.getsize(path)})

    # c013 python sources + the shared modules they execute against
    for f in sorted(os.listdir(os.path.join(_REPO, "tools"))):
        if f.startswith("c013_") and f.endswith(".py"):
            add(os.path.join(_REPO, "tools", f), f"source/tools/{f}", "c013_source")
    for f in sorted(os.listdir(os.path.join(_REPO, "tests"))):
        if f.startswith("test_c013") and f.endswith(".py"):
            add(os.path.join(_REPO, "tests", f), f"source/tests/{f}", "test")
    for f in ("c013_eval_core.py", "c009_eval.py", "c011_eval_core.py", "rl_policy.py",
              "rl_env.py", "policy_features.py", "policy_data_v2.py", "teachers.py",
              "student_agent.py", "gameplay.py", "safe_policy.py", "noninf_stats.py"):
        add(os.path.join(_REPO, "cg", f), f"source/cg/{f}", "supporting_source")

    # contract, command, inputs, references
    add(os.path.join(C013, "CONTRACT.md"), "contract/CONTRACT.md", "contract")
    add(os.path.join(C013, "CLAUDE_COMMAND.txt"), "contract/CLAUDE_COMMAND.txt", "command")
    for sub, cat in (("inputs", "inputs"), ("references", "references")):
        d = os.path.join(C013, sub)
        if os.path.isdir(d):
            for root, _, fs in os.walk(d):
                for f in fs:
                    p = os.path.join(root, f)
                    add(p, f"contract/{sub}/{os.path.relpath(p, d)}", cat)

    # claude prompt/schema and sanitized inputs/outputs
    for f, cat in (("claude_prompt.md", "claude_prompt"),
                   ("claude_output_schema.json", "claude_schema"),
                   ("semantic_state_schema.json", "claude_schema"),
                   ("claude_preflight_inputs.jsonl.gz", "claude_io"),
                   ("claude_preflight_outputs.jsonl.gz", "claude_io"),
                   ("claude_semantic_validation.json", "claude_io"),
                   ("semantic_state_benchmark.jsonl.gz", "claude_io")):
        add(os.path.join(ART, f), f"claude/{f}", cat)

    # decision artifacts and reports
    for f in sorted(os.listdir(ART)):
        p = os.path.join(ART, f)
        if os.path.isfile(p) and (f.endswith(".md") or f.endswith(".json")) \
                and not f.startswith("claude_"):
            add(p, f"decisions/{f}", "decision")

    # dependency / machine snapshots
    for f in ("dependency_verification.json", "machine_snapshot.json"):
        add(os.path.join(ART, f), f"env/{f}", "environment")

    # git patch
    add(os.path.join(ART, "c013.patch"), "git/c013.patch", "git_patch")
    return items


def write_env_snapshot():
    import platform
    snap = {"python": sys.version, "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count()}
    try:
        snap["pip_freeze"] = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True,
            timeout=120).stdout.splitlines()
    except Exception as e:  # noqa: BLE001
        snap["pip_freeze_error"] = repr(e)
    try:
        import torch
        snap["torch"] = {"version": torch.__version__,
                         "cuda_available": torch.cuda.is_available(),
                         "cuda_version": getattr(torch.version, "cuda", None),
                         "device": (torch.cuda.get_device_name(0)
                                    if torch.cuda.is_available() else None)}
    except Exception as e:  # noqa: BLE001
        snap["torch_error"] = repr(e)
    json.dump(snap, open(os.path.join(ART, "machine_snapshot.json"), "w"),
              indent=2, default=str)


def write_git_patch():
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "main"], cwd=_REPO,
                              capture_output=True, text=True).stdout.strip() or "main"
        patch = subprocess.run(["git", "diff", f"{base}...HEAD"], cwd=_REPO,
                               capture_output=True, text=True).stdout
        open(os.path.join(ART, "c013.patch"), "w").write(patch)
    except Exception as e:  # noqa: BLE001
        open(os.path.join(ART, "c013.patch"), "w").write(f"# patch unavailable: {e!r}\n")


def build() -> Dict[str, Any]:
    write_env_snapshot()
    write_git_patch()
    items = collect()
    manifest = {"bundle": os.path.relpath(ZIP, _REPO), "n_files": len(items),
                "files": items,
                "categories": sorted({i["category"] for i in items})}
    mpath = os.path.join(ART, "c013_python_source_manifest.json")
    json.dump(manifest, open(mpath, "w"), indent=2, default=str)

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for i in items:
            z.write(os.path.join(_REPO, i["original_path"]), i["archive_path"])
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=2, default=str))
    return manifest


def validate(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Reopen the archive and check it against its own bytes."""
    checks: List[Dict[str, Any]] = []

    def ck(name, ok, detail=None):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        return ok

    ck("bundle_exists", os.path.exists(ZIP), {"path": os.path.relpath(ZIP, _REPO)})
    if not os.path.exists(ZIP):
        return {"overall": "FAIL", "checks": checks}

    with zipfile.ZipFile(ZIP) as z:
        names = set(z.namelist())
        ck("manifest_inside_archive", "MANIFEST.json" in names)

        missing, mismatched = [], []
        for i in manifest["files"]:
            if i["archive_path"] not in names:
                missing.append(i["archive_path"])
                continue
            if sha_bytes(z.read(i["archive_path"])) != i["sha256"]:
                mismatched.append(i["archive_path"])
        ck("every_manifest_entry_present", not missing, {"missing": missing[:20]})
        ck("archive_bytes_match_manifest_hashes", not mismatched,
           {"mismatched": mismatched[:20]})

        for cat in ("c013_source", "test", "supporting_source", "contract", "command",
                    "claude_prompt", "claude_schema", "claude_io", "decision",
                    "environment", "git_patch"):
            n = sum(1 for i in manifest["files"] if i["category"] == cat)
            ck(f"category_nonempty:{cat}", n > 0, {"n": n})

        bad_py = []
        for n in names:
            if n.endswith(".py"):
                try:
                    ast.parse(z.read(n).decode("utf-8", "ignore"))
                except SyntaxError as e:
                    bad_py.append({"member": n, "error": str(e)})
        ck("every_python_member_compiles", not bad_py, {"bad": bad_py[:10]})

        leaks = []
        for n in names:
            if n.endswith((".png", ".npz", ".so")):
                continue
            try:
                if n.endswith(".gz"):
                    data = gzip.decompress(z.read(n)).decode("utf-8", "ignore")
                else:
                    data = z.read(n).decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            m = CRED.search(data)
            if m:
                leaks.append({"member": n, "pattern": m.group(0)[:24]})
        ck("no_credential_shaped_content", not leaks, {"hits": leaks[:10]})

        entry = [i for i in manifest["files"]
                 if i["archive_path"].startswith("source/tools/c013_")]
        ck("executed_entrypoints_bundled", len(entry) >= 8, {"n": len(entry)})
        ck("ensemble_and_soup_implementation_bundled",
           "source/tools/c013_ensemble_policy.py" in names)
        ck("semantic_serializer_bundled",
           "source/tools/c013_semantic_serializer.py" in names)

    failed = [c for c in checks if not c["passed"]]
    return {"overall": "PASS" if not failed else "FAIL", "n_checks": len(checks),
            "n_passed": len(checks) - len(failed), "checks": checks}


def main():
    os.makedirs(ART, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    manifest = build()
    res = validate(manifest)
    with open(os.path.join(LOGD, "source_bundle_validation.txt"), "w") as fh:
        for c in res["checks"]:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['check']}\n")
            if c["detail"]:
                fh.write("    " + json.dumps(c["detail"], default=str)[:800] + "\n")
        fh.write(f"\noverall: {res['overall']} "
                 f"({res['n_passed']}/{res['n_checks']})\n")
    print(json.dumps({"n_files": manifest["n_files"],
                      "categories": manifest["categories"],
                      "validation": {k: res[k] for k in ("overall", "n_checks", "n_passed")}},
                     indent=2))
    for c in res["checks"]:
        if not c["passed"]:
            print(f"  FAIL {c['check']}: {json.dumps(c['detail'], default=str)[:300]}")
    return 0 if res["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

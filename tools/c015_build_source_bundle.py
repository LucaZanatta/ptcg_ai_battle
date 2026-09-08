"""c014 source bundle — built, then reopened and validated against its own bytes.

Credential-shaped content is detected by VALUE, not by name: matching identifiers like
`kaggle.json` fires on any file that merely discusses credentials — including this scanner —
and a check whose hits are all false positives gets ignored, which is worse than no check.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C014 = os.path.join(_REPO, "contracts", "c015_anti_meta_deck_agent_v0")
RES = os.path.join(C014, "results")
ART = os.path.join(RES, "artifacts")
LOGD = os.path.join(RES, "test_logs")
ZIP = os.path.join(ART, "c015_python_source_bundle.zip")

CRED = re.compile(
    r"(BEGIN [A-Z ]*PRIVATE KEY|sk-ant-[A-Za-z0-9\-_]{16,}|AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|\"key\"\s*:\s*\"[A-Za-z0-9/+=_-]{20,}\""
    r"|(?:password|passwd|secret|api[_-]?token)\s*[:=]\s*[\"'][^\"'\s]{12,}[\"'])")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def collect():
    items = []

    def add(path, arc, cat):
        if os.path.isfile(path):
            items.append({"original_path": os.path.relpath(path, _REPO), "archive_path": arc,
                          "category": cat, "sha256": sha_file(path),
                          "bytes": os.path.getsize(path)})

    for f in sorted(os.listdir(os.path.join(_REPO, "tools"))):
        if f.startswith("c015_") and f.endswith(".py"):
            add(os.path.join(_REPO, "tools", f), f"source/tools/{f}", "c014_source")
    for f in sorted(os.listdir(os.path.join(_REPO, "tests"))):
        if f.startswith("test_c015") and f.endswith(".py"):
            add(os.path.join(_REPO, "tests", f), f"source/tests/{f}", "test")
    for f in ("gameplay.py", "safe_policy.py", "teachers.py", "api.py", "main.py"):
        add(os.path.join(_REPO, "cg", f), f"source/cg/{f}", "supporting_source")

    add(os.path.join(C014, "CONTRACT.md"), "contract/CONTRACT.md", "contract")
    add(os.path.join(C014, "CLAUDE_COMMAND.txt"), "contract/CLAUDE_COMMAND.txt", "command")
    for sub, cat in (("inputs", "inputs"), ("references", "references")):
        d = os.path.join(C014, sub)
        if os.path.isdir(d):
            for root, _, fs in os.walk(d):
                for f in fs:
                    p = os.path.join(root, f)
                    add(p, f"contract/{sub}/{os.path.relpath(p, d)}", cat)

    add(os.path.join(ART, "anti_meta_deck.csv"), "deck/anti_meta_deck.csv", "deck")
    add(os.path.join(ART, "anti_meta_deck.sha256"), "deck/anti_meta_deck.sha256", "deck")

    for f in sorted(os.listdir(ART)):
        p = os.path.join(ART, f)
        if os.path.isfile(p) and (f.endswith(".md") or f.endswith(".json")
                                  or f.endswith(".csv") or f.endswith(".sha256")) \
                and f != "c015_python_source_manifest.json":
            add(p, f"reports/{f}", "report")
    for f in sorted(os.listdir(RES)):
        p = os.path.join(RES, f)
        if os.path.isfile(p):
            add(p, f"reports/top/{f}", "report")
    for f in sorted(os.listdir(LOGD)) if os.path.isdir(LOGD) else []:
        add(os.path.join(LOGD, f), f"logs/{f}", "log")

    # c015 does not re-mine (§8/§9): its public-evidence record is the bounded delta check
    # plus a pointer to c014's hashed snapshot manifest, which stays in c014 untouched (§5).
    for f in ("public_delta_sources.json", "public_delta.json", "PUBLIC_DELTA_CHECK.md"):
        add(os.path.join(ART, f), f"public_evidence/{f}", "public_evidence")
    c14a = os.path.join(_REPO, "contracts",
                        "c014_public_meta_baseline_and_rapid_submission", "results",
                        "artifacts")
    for f in ("public_sources.json", "public_source_manifest.sha256"):
        add(os.path.join(c14a, f), f"public_evidence/from_c014/{f}", "public_evidence")

    add(os.path.join(ART, "c015.patch"), "git/c015.patch", "git_patch")
    add(os.path.join(ART, "machine_snapshot.json"), "env/machine_snapshot.json",
        "environment")
    return items


def env_and_patch():
    import platform
    snap = {"python": sys.version, "platform": platform.platform(),
            "cpu_count": os.cpu_count()}
    try:
        snap["pip_freeze"] = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True,
            timeout=180).stdout.splitlines()
    except Exception as e:  # noqa: BLE001
        snap["pip_freeze_error"] = repr(e)
    snap["git"] = {
        "initial_head": "7edfb81929100d80c1bf3f74d48b45de966b050d",
        "final_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "branch": subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=_REPO,
                                 capture_output=True, text=True).stdout.strip(),
        "status": subprocess.run(["git", "status", "--short"], cwd=_REPO,
                                 capture_output=True, text=True).stdout,
        "commits": subprocess.run(["git", "log", "--oneline", "-10"], cwd=_REPO,
                                  capture_output=True, text=True).stdout,
    }
    json.dump(snap, open(os.path.join(ART, "machine_snapshot.json"), "w"), indent=2,
              default=str)
    patch = subprocess.run(
        ["git", "diff", "7edfb81929100d80c1bf3f74d48b45de966b050d...HEAD"],
        cwd=_REPO, capture_output=True, text=True).stdout
    open(os.path.join(ART, "c015.patch"), "w").write(patch)


def main():
    env_and_patch()
    items = collect()
    man = {"bundle": os.path.relpath(ZIP, _REPO), "n_files": len(items), "files": items,
           "categories": sorted({i["category"] for i in items})}
    json.dump(man, open(os.path.join(ART, "c015_python_source_manifest.json"), "w"),
              indent=2, default=str)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for i in items:
            z.write(os.path.join(_REPO, i["original_path"]), i["archive_path"])
        z.writestr("MANIFEST.json", json.dumps(man, indent=2, default=str))

    checks = []

    def ck(n, ok, d=None):
        checks.append({"check": n, "passed": bool(ok), "detail": d})

    with zipfile.ZipFile(ZIP) as z:
        names = set(z.namelist())
        ck("manifest_inside", "MANIFEST.json" in names)
        bad = [i["archive_path"] for i in items
               if i["archive_path"] not in names
               or hashlib.sha256(z.read(i["archive_path"])).hexdigest() != i["sha256"]]
        ck("archive_bytes_match_manifest", not bad, {"bad": bad[:10]})
        for cat in ("c014_source", "test", "supporting_source", "contract", "command",
                    "deck", "report", "log", "public_evidence", "environment", "git_patch"):
            n = sum(1 for i in items if i["category"] == cat)
            ck(f"category_nonempty:{cat}", n > 0, {"n": n})
        badpy = []
        for n in names:
            if n.endswith(".py"):
                try:
                    # utf-8-sig: the official cg/api.py carries a UTF-8 BOM. It is valid
                    # Python (CPython strips the BOM when importing); decoding as plain
                    # utf-8 leaves U+FEFF in the text and only the PARSER fails.
                    ast.parse(z.read(n).decode("utf-8-sig", "ignore"))
                except SyntaxError as e:
                    badpy.append({"member": n, "error": str(e)})
        ck("python_members_compile", not badpy, {"bad": badpy[:5]})
        leaks = []
        for n in names:
            if n.endswith((".so", ".png", ".npz", ".pdf")):
                continue
            try:
                data = (gzip.decompress(z.read(n)) if n.endswith(".gz")
                        else z.read(n)).decode("utf-8", "ignore")
            except Exception:  # noqa: BLE001
                continue
            m = CRED.search(data)
            if m:
                leaks.append({"member": n, "pattern": m.group(0)[:20]})
        ck("no_credential_material", not leaks, {"hits": leaks[:5]})
        ck("expert_bundled", "source/tools/c015_iono_expert.py" in names)
        ck("package_builder_bundled", "source/tools/c015_package.py" in names)
        ck("submit_wrapper_bundled", "source/tools/c015_submit.py" in names)
        ck("deck_bundled", "deck/anti_meta_deck.csv" in names)
        ck("no_submission_archive_inside",
           not any(n.endswith(".tar.gz") for n in names))

    failed = [c for c in checks if not c["passed"]]
    res = {"overall": "PASS" if not failed else "FAIL", "n_checks": len(checks),
           "n_passed": len(checks) - len(failed), "checks": checks}
    with open(os.path.join(LOGD, "source_bundle_validation.txt"), "w") as fh:
        for c in checks:
            fh.write(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['check']}\n")
            if c["detail"]:
                fh.write("    " + json.dumps(c["detail"], default=str)[:600] + "\n")
        fh.write(f"\noverall: {res['overall']} ({res['n_passed']}/{res['n_checks']})\n")
    print(json.dumps({"n_files": man["n_files"], "categories": man["categories"],
                      "validation": {k: res[k] for k in ("overall", "n_checks", "n_passed")}},
                     indent=2))
    for c in failed:
        print("  FAIL", c["check"], json.dumps(c["detail"], default=str)[:200])
    return 0 if res["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

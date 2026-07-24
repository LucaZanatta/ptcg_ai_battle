"""Runtime/environment verification with a machine-readable report (§7.12).

Checks Python version, kaggle-environments version, platform/machine, the engine
(path/sha256/size), and required runtime assets (via the c002 manifest). Validates
deck.csv *syntax* and records its canonical identity separately — it does NOT
require the mutable deck to match a historical fixed hash.

Usage (from repo root):
  .venv/bin/python tools/environment_report.py                 # human summary
  .venv/bin/python tools/environment_report.py --json out.json # machine-readable
"""

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cg.episode_schema import canonical_deck, collect_engine_info, collect_environment
from cg.safe_policy import MalformedDeck, default_deck_path, load_deck
import tools.verify_runtime_assets as vra


def build_report(repo_root):
    env = collect_environment()
    engine = collect_engine_info(os.path.join(repo_root, "starter_kit", "libcg.so"), repo_root)

    deck_path = default_deck_path()
    deck_syntax_ok = True
    deck_canonical = None
    deck_error = None
    try:
        deck = load_deck()
        deck_canonical = canonical_deck(deck, source_path=deck_path, repo_root=repo_root)
    except (MalformedDeck, OSError) as exc:
        deck_syntax_ok = False
        deck_error = str(exc)

    # Required assets via the c002 manifest verifier.
    manifest = os.path.join(repo_root, "runtime_assets.json")
    assets_failures = None
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as fh:
            man = json.load(fh)
        assets_failures = sum(
            1 for a in man["assets"]
            if a.get("required", True) and not vra.verify_asset(a, repo_root)[0])

    checks = {
        "python_ok": env["python_version"] is not None,
        "kaggle_environments_present": env["kaggle_environments_version"] is not None,
        "engine_present": engine["sha256"] is not None,
        "deck_syntax_ok": deck_syntax_ok,
        "required_assets_ok": (assets_failures == 0) if assets_failures is not None else None,
    }
    all_ok = all(v for v in checks.values() if v is not None) and deck_syntax_ok

    return {
        "environment": env,
        "engine": engine,
        "deck": {
            "path": os.path.relpath(deck_path, repo_root) if deck_path.startswith(repo_root) else deck_path,
            "syntax_ok": deck_syntax_ok,
            "error": deck_error,
            "canonical": deck_canonical,
        },
        "required_assets_failures": assets_failures,
        "checks": checks,
        "all_ok": bool(all_ok),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Environment report")
    parser.add_argument("--json", default=None)
    parser.add_argument("--repo-root", default=_REPO_ROOT)
    args = parser.parse_args(argv)

    report = build_report(args.repo_root)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    env = report["environment"]
    print(f"python: {env['python_version']} ({env['python_implementation']})")
    print(f"platform: {env['platform']} | machine: {env['machine']}")
    print(f"kaggle-environments: {env['kaggle_environments_version']}")
    print(f"engine: {report['engine']['path']} sha256={str(report['engine']['sha256'])[:12]}... "
          f"size={report['engine']['size_bytes']}")
    if report["deck"]["canonical"]:
        print(f"deck: syntax_ok={report['deck']['syntax_ok']} "
              f"deck_id={report['deck']['canonical']['deck_id'][:20]}...")
    print(f"checks: {report['checks']}")
    print("RESULT:", "PASS" if report["all_ok"] else "FAIL")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

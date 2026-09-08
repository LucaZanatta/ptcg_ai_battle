"""Tests for the runtime asset manifest and verifier (stdlib unittest).

Run: .venv/bin/python -m unittest tests.test_runtime_assets -v
"""

import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import tools.verify_runtime_assets as vra  # noqa: E402

_MANIFEST = os.path.join(_REPO_ROOT, "runtime_assets.json")


class TestManifestLoading(unittest.TestCase):
    def test_manifest_loads_and_has_required_keys(self):
        with open(_MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertIn("assets", manifest)
        self.assertGreater(len(manifest["assets"]), 0)
        for a in manifest["assets"]:
            for key in ("name", "path", "required", "asset_type", "kind", "must_be_tracked"):
                self.assertIn(key, a, f"asset {a.get('name')} missing {key}")


class TestVerifierCurrentEnv(unittest.TestCase):
    def test_all_required_assets_pass(self):
        with open(_MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
        failures = []
        for asset in manifest["assets"]:
            ok, _status, detail = vra.verify_asset(asset, _REPO_ROOT)
            if asset.get("required", True) and not ok:
                failures.append((asset["name"], detail))
        self.assertEqual(failures, [], f"required assets failed: {failures}")

    def test_verifier_exit_zero_current_env(self):
        code = vra.main(["--manifest", _MANIFEST, "--repo-root", _REPO_ROOT, "--json"])
        self.assertEqual(code, 0)


class TestVerifierNegative(unittest.TestCase):
    def test_missing_required_asset_nonzero_exit(self):
        bogus = {
            "manifest_version": 1,
            "assets": [{
                "name": "definitely_missing", "path": "no/such/file_xyz.bin",
                "required": True, "asset_type": "source", "kind": "file",
                "size": None, "sha256": None, "symlink_target": None,
                "must_be_tracked": True, "acquisition": "n/a",
            }],
        }
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(bogus, fh)
        try:
            code = vra.main(["--manifest", path, "--repo-root", _REPO_ROOT, "--json"])
            self.assertNotEqual(code, 0)
        finally:
            os.unlink(path)


class TestSymlinkValidation(unittest.TestCase):
    def test_symlink_target_ok_and_mismatch(self):
        tmp = tempfile.mkdtemp()
        try:
            realdir = os.path.join(tmp, "target_dir")
            os.mkdir(realdir)
            link = os.path.join(tmp, "link")
            os.symlink("target_dir", link)
            good = {"name": "lnk", "path": "link", "kind": "symlink",
                    "symlink_target": "target_dir", "required": True}
            ok, _s, _d = vra.verify_asset(good, tmp)
            self.assertTrue(ok)
            bad = dict(good, symlink_target="wrong_target")
            ok2, _s2, _d2 = vra.verify_asset(bad, tmp)
            self.assertFalse(ok2)
        finally:
            import shutil
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()

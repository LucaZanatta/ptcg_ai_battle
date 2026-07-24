"""AC-07: gzip/jsonl streaming equivalence (stdlib unittest)."""

import gzip
import hashlib
import json
import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import tools.validate_episodes_v2 as v2
from cg.episode_capture_v2 import RunWriter
from tests._v2_helpers import (
    decision_record, game_start_record, run_metadata_record, terminal_record,
)


def _records():
    return [
        run_metadata_record(),
        game_start_record(seq=1),
        decision_record(4, 1, 2, 0, [0, 1], decision_index=0, seq=2),
        decision_record(4, 1, 1, 0, [0], decision_index=1, seq=3),
        terminal_record(seq=4, decisions_by_player={"0": 2}),
    ]


class TestCompression(unittest.TestCase):
    def test_jsonl_and_gzip_equivalent(self):
        with tempfile.TemporaryDirectory() as td:
            jsonl = os.path.join(td, "e.jsonl")
            gz = os.path.join(td, "e.jsonl.gz")
            writer = RunWriter(jsonl, gz)
            for r in _records():
                writer.write(r)
            writer.close()

            # 1) decompressed gz content is byte-identical to the plain jsonl.
            with open(jsonl, "rb") as fh:
                plain = fh.read()
            with gzip.open(gz, "rb") as fh:
                decompressed = fh.read()
            self.assertEqual(hashlib.sha256(plain).hexdigest(),
                             hashlib.sha256(decompressed).hexdigest())

            # 2) semantic validation yields equivalent results for both.
            r_plain = v2.validate(jsonl)
            r_gz = v2.validate(gz)
            self.assertTrue(r_plain["ok"])
            self.assertTrue(r_gz["ok"])
            self.assertEqual(r_plain["validation"]["decisions"], r_gz["validation"]["decisions"])
            self.assertEqual(r_plain["semantic"]["matches"], r_gz["semantic"]["matches"])
            self.assertEqual(r_plain["validation"]["games"], r_gz["validation"]["games"])


if __name__ == "__main__":
    unittest.main()

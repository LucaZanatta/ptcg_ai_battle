"""Schema-aware streaming reader for episode captures (v1 and v2, .jsonl/.jsonl.gz).

- Detects `schema_version` per record (never inferred from file extension, §7.1).
- Streams records without loading the whole file.
- Reads schema v1 (c002) and schema v2 (c003).
- Rejects unsupported versions with a clear error.
- For schema-v1 data, marks v2-only provenance fields explicitly
  ``legacy_unavailable`` rather than inventing them.
"""

from __future__ import annotations

import gzip
import json
from typing import Any, Dict, Iterator, Tuple

from cg.episode_schema import SUPPORTED_SCHEMA_VERSIONS

LEGACY_UNAVAILABLE = "legacy_unavailable"

# v2-only provenance fields that a schema-v1 decision record does not carry.
V2_ONLY_DECISION_FIELDS = ("record_id", "run_id", "agent_id", "decision_source",
                           "fallback_reason", "select_context")
# v1 `used_fallback` exists but was seat/identity-based (not a true provenance
# signal), so it is surfaced as legacy and not trusted as v2 provenance.
V1_UNTRUSTED_FIELDS = ("used_fallback", "game_seed")


class UnsupportedSchemaVersion(ValueError):
    """Raised when a record declares a schema version outside the supported set."""


def open_text(path: str):
    """Open a .jsonl or .jsonl.gz path as a UTF-8 text stream (by extension)."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def stream_raw(path: str) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with open_text(path) as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            yield line_no, json.loads(line)


def detect_schema_version(record: Dict[str, Any]) -> Any:
    return record.get("schema_version")


def read_records(path: str, *, allow_versions=SUPPORTED_SCHEMA_VERSIONS
                 ) -> Iterator[Tuple[int, Any, Dict[str, Any]]]:
    """Yield ``(line_no, schema_version, record)``; raise on unsupported versions."""
    for line_no, rec in stream_raw(path):
        v = detect_schema_version(rec)
        if v not in allow_versions:
            raise UnsupportedSchemaVersion(
                f"line {line_no}: unsupported schema_version {v!r} "
                f"(supported: {sorted(allow_versions)})")
        yield line_no, v, rec


def legacy_availability(record: Dict[str, Any]) -> Dict[str, str]:
    """For a schema-v1 record, report which v2 provenance fields are unavailable.

    Never invents values; each missing v2-only field maps to ``legacy_unavailable``.
    """
    avail: Dict[str, str] = {}
    for field in V2_ONLY_DECISION_FIELDS:
        if field not in record:
            avail[field] = LEGACY_UNAVAILABLE
    for field in V1_UNTRUSTED_FIELDS:
        if field in record:
            avail[field] = "legacy_present_untrusted"
    return avail


def summarize_file(path: str) -> Dict[str, Any]:
    """Structural summary + version detection for a capture file (v1 or v2)."""
    versions: Dict[str, int] = {}
    record_types: Dict[str, int] = {}
    decisions = 0
    v2_only_unavailable = set()
    for _ln, v, rec in read_records(path):
        versions[str(v)] = versions.get(str(v), 0) + 1
        rt = rec.get("record_type", "unknown")
        record_types[rt] = record_types.get(rt, 0) + 1
        if rt == "decision":
            decisions += 1
            if v == 1:
                for k in legacy_availability(rec):
                    v2_only_unavailable.add(k)
    return {
        "path": path,
        "schema_versions": versions,
        "record_types": record_types,
        "decisions": decisions,
        "detected_schema": (1 if versions == {"1": versions.get("1", 0)} and "1" in versions
                            else (2 if set(versions) == {"2"} else "mixed")),
        "v2_only_fields_legacy_unavailable": sorted(v2_only_unavailable),
    }

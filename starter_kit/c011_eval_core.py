"""c011 §17 evaluation core: the c009 identity protocol, extended so the FROZEN TEACHER can
be evaluated as a candidate.

c010 never ran the teacher as a candidate -- it was excluded from every panel -- so the gap
below was never exercised. c009's `run_job` skips checkpoint hashing when
`candidate_kind == "frozen_teacher"`, leaving `verified_checkpoint_sha256 = None`, while
`assert_identity` requires `verified_checkpoint_sha256 == checkpoint_sha256`. A teacher
candidate would therefore fail identity on every game.

The fix does NOT weaken the assertion. The teacher is a real file
(`teacher_sources/dragapult/main.py`, the module `cg.teachers.make_fresh` actually executes),
so the worker re-hashes that file and returns it, exactly as it does for a policy checkpoint.
Registry and worker hashes must still agree. c009/c010 tools are not modified (§6).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from cg import c009_eval as ce

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The teacher module that make_fresh() actually imports and runs.
TEACHER_MAIN = os.path.join(ce.SOURCES, "dragapult", "main.py")


def teacher_source_sha256() -> str:
    return ce.sha256_file(TEACHER_MAIN)


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """c009 run_job, plus genuine hash verification for the frozen-teacher candidate."""
    rec = ce.run_job(job)
    if job.get("candidate_kind") == "frozen_teacher" and rec.get("verified_checkpoint_sha256") is None:
        try:
            rec["verified_checkpoint_sha256"] = teacher_source_sha256()
        except OSError as e:  # noqa: BLE001
            rec["defect"] = rec.get("defect") or f"teacher_source_unreadable:{e}"
    return rec


def run_jobs(jobs: List[Dict[str, Any]], nproc: int) -> List[Dict[str, Any]]:
    """Unordered pool over c011 run_job. Results carry their own identity; they are never
    reattached by position (that was the c008 defect c009 repaired)."""
    import multiprocessing as mp
    if nproc <= 1:
        return [run_job(j) for j in jobs]
    ctx = mp.get_context("spawn")
    out = []
    with ctx.Pool(processes=nproc) as pool:
        for r in pool.imap_unordered(run_job, jobs, chunksize=1):
            out.append(r)
    return out

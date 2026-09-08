#!/bin/bash
# c023 — the close. Regenerates every report from raw data, validates, captures source, archives.
# Safe to re-run: everything it writes is derived from artifacts on disk.
set -u
cd /home/luca/kaggle/ptcg_ai_battle
R=results/c023_autonomous_meta_first_competition_sprint
PY=.venv/bin/python

CHALLENGER="${1:-}"          # candidate id, or empty if nothing was promoted
OUTCOME="${2:-RESEARCH_SUCCESS}"
FINAL_TAG="${3:-final_panel}"

echo "=== 1. matchup matrix and champion, recomputed from raw games ==="
$PY tools/c023_matrix.py --tags rr_v1,rr_v1b,rr_v1c \
    --eligible official_dragapult,official_mega_lucario,official_iono,official_mega_abomasnow \
    --quiet

echo "=== 2. candidate history ==="
$PY tools/c023_history.py

echo "=== 3. validator, with injections ==="
$PY tools/c023_validate.py --injections

echo "=== 4. status, decision board, acceptance checklist ==="
if [ -n "$CHALLENGER" ]; then
  $PY tools/c023_reports.py --outcome "$OUTCOME" --challenger "$CHALLENGER" --final-tag "$FINAL_TAG"
else
  $PY tools/c023_reports.py --outcome "$OUTCOME" --final-tag "$FINAL_TAG"
fi

echo "=== 5. source and git capture, results archive ==="
$PY tools/c023_capture.py --archive

echo "=== 6. re-validate after regeneration ==="
$PY tools/c023_validate.py

echo "=== done ==="

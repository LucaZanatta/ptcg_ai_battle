#!/bin/bash
# c010 post-training pipeline. Runs in the registered order; each stage's output feeds the
# next, so it is deliberately sequential and fails fast. Evaluation stages must never run
# concurrently -- they rewrite the same evidence file.
set -euo pipefail
cd /home/luca/kaggle/ptcg_ai_battle
OUT=contracts/c010_fixed_deck_rl_loop_v2/results
PY=.venv/bin/python
step() { echo; echo "===== $* ====="; }

step "AC-07/08/09 consolidate all arms"
$PY tools/c010_consolidate.py --arms A,B,C

step "AC-10 screen every new checkpoint (Arm C)"
$PY tools/c010_eval.py --panel screen --candidates ALL_NEW --nproc 12 2>&1 | grep -v INFO | tail -5

step "AC-10 apply the Sec.17 nomination rule across all branches"
$PY tools/c010_screen.py --stage nominate

step "AC-10 confirmation panels for nominations that do not yet have one"
NEW=$($PY - <<'PYEOF'
import gzip, json
ART = "contracts/c010_fixed_deck_rl_loop_v2/results/artifacts"
noms = json.load(open(f"{ART}/screening_nominations.json"))["nominated"]
done = {json.loads(l)["candidate_id"] for l in gzip.open(f"{ART}/evaluation_games.jsonl.gz", "rt")
        if json.loads(l)["phase"] == "confirmation"}
print(",".join(c for c in noms if c not in done))
PYEOF
)
if [ -n "$NEW" ]; then
  echo "new nominations: $NEW"
  $PY tools/c010_eval.py --panel confirmation --candidates "$NEW" --nproc 12 2>&1 | grep -v INFO | tail -5
else
  echo "no new nominations require a confirmation panel"
fi
$PY tools/c010_screen.py --stage confirm

step "AC-11/12/13 aggregate (selects finalists from confirmation evidence)"
$PY tools/c010_aggregate.py --stage all | tail -15

step "AC-13 final panel for any finalist lacking one"
FIN=$($PY - <<'PYEOF'
import gzip, json
ART = "contracts/c010_fixed_deck_rl_loop_v2/results/artifacts"
fin = json.load(open(f"{ART}/final_panel_candidates.json"))["finalists"]
done = {json.loads(l)["candidate_id"] for l in gzip.open(f"{ART}/evaluation_games.jsonl.gz", "rt")
        if json.loads(l)["phase"] == "final"}
print(",".join(c for c in fin if c not in done))
PYEOF
)
if [ -n "$FIN" ]; then
  echo "finalists needing a final panel: $FIN"
  $PY tools/c010_eval.py --panel final --candidates "$FIN" --nproc 12 2>&1 | grep -v INFO | tail -5
  $PY tools/c010_aggregate.py --stage all | tail -15
else
  echo "every finalist already has a final panel"
fi

step "Sec.16 teacher extension, if any finalist is still plausibly non-inferior"
EXT=$($PY - <<'PYEOF'
import json
ART = "contracts/c010_fixed_deck_rl_loop_v2/results/artifacts"
d = json.load(open(f"{ART}/teacher_extension_assessment.json"))
print(",".join(c for c, v in d["finalists"].items() if v["extension_required"]))
PYEOF
)
if [ -n "$EXT" ]; then
  echo "extending teacher head-to-head to 800 games for: $EXT"
  $PY tools/c010_eval.py --panel final --candidates "$EXT" --teacher-extension --nproc 12 2>&1 | grep -v INFO | tail -5
  $PY tools/c010_aggregate.py --stage all | tail -15
else
  echo "no finalist is plausibly teacher-non-inferior; no extension required"
fi

step "AC-05 identity protocol"
$PY tools/c010_identity_protocol.py

step "AC-15 submission gate, conditional Kaggle workflow, next step"
$PY tools/c010_finalize.py

step "AC-14 content-aware evidence validation"
$PY tools/c010_validate_evidence.py --art-dir $OUT/artifacts --log-dir $OUT/test_logs --quiet | tail -3
$PY -c "import json;d=json.load(open('$OUT/artifacts/evidence_validation.json'));print('checks',d['n_checks'],'failed',d['n_failed'],'ALL_OK',d['all_ok'])"

step "AC-14 content-validation tests (must RUN, not skip)"
$PY -m unittest tests.test_c010_content_validation 2>&1 | tail -3

step "unit suites"
for t in arm_registration promotion_rules identity_safe_eval incumbent_protection; do
  printf "%-22s " "$t"; $PY -m unittest tests.test_c010_$t 2>&1 | tail -1
done

step "AC-16 reports, status, checklist, git report"
$PY tools/c010_reports.py
echo; echo "===== c010_finish complete ====="

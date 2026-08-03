# ACCEPTANCE_CHECKLIST

Generated from artifacts by `tools/c023_reports.py`. A criterion whose evidence is missing reads `NO_DATA`, never `PASS`.

| criterion | status | evidence |
|---|---|---|
| champion established by measurement, not by label | **PASS** | `champion.json`: official_dragapult at 0.4653 off-mirror over 720 games; the panel leader pub_jazivxt_rising_tide_v21 is recorded separately as ineligible |
| champion reproduced locally on both seats | **PASS** | seat0 0.4625, seat1 0.4725 |
| evaluation noise measured, not assumed | **PASS** | two identical policies measured 0.4850 and 0.5166 on the same dev panel in two runs -> a 3.2-point floor, applied to every comparison |
| dev / validation opponent split registered before tuning | **PASS** | `PANEL_SPLIT.json`, registered before any candidate was built |
| wrapper action-identical to its base with no rules enabled | **PASS** | chal_dp_base: 0 mismatches over 941 decisions; chal_dp_base2: 0 mismatches over 792 decisions; chal_dp_base4: 0 mismatches over 456 decisions; chal_dp_param0: 0 mismatches over 1263 decisions |
| no rule is inert (every enabled rule was measured firing) | **FAIL** | `raw_evaluations/rule_fires/rule_fires.json` |
| zero illegal selections, exceptions and timeouts | **FAIL** | 1 errors and 0 engine process deaths across 60292 games |
| every candidate carries parent, hashes, protocol, seats and counts | **PASS** | `CANDIDATE_HISTORY.jsonl`: 59 candidates |
| packages built and clean-validated by execution | **PASS** | c023_champion_dragapult.tar.gz valid |
| frozen champion package never overwritten | **PASS** | `--freeze` refuses to replace an existing archive |
| validator run with injections | **FAIL** | 10/11 checks pass, 0/0 injections detected |
| all required files and directories present | **FAIL** | 14/15 files, 7/7 directories |
| no upload performed without authorization | **PASS** | `LEADERBOARD_SUBMISSION_PLAN.md`: no authorization exists in the repository; kaggle_upload = NOT_PERFORMED |
| honest competitive decision recorded | **PASS** | `EXECUTIVE_DECISION.md`, outcome RESEARCH_SUCCESS |

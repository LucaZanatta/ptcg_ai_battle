# ACCEPTANCE_CHECKLIST

Generated from artifacts by `tools/c023_reports.py`. A criterion whose evidence is missing reads `NO_DATA`, never `PASS`.

| criterion | status | evidence |
|---|---|---|
| champion established by measurement, not by label | **PASS** | `champion.json`: official_dragapult at 0.4653 off-mirror over 720 games; the panel leader pub_jazivxt_rising_tide_v21 is recorded separately as ineligible |
| champion reproduced locally on both seats | **PASS** | seat0 0.4625, seat1 0.4725 |
| evaluation noise measured, not assumed | **PASS** | chal_dp_base3 -- ONE candidate, three separate 1,200-game runs -- measured 0.5042, 0.5125 and 0.5279: a 2.4-point range on an unchanged policy. Corroborated by two further identical-policy pairs (0.4850/0.5166 at 400-600 games, and chal_dp_bench2/chal_dp_base3 at 0.5142/0.5042 once the firing probe proved bench2's rule was inert). Applied to every comparison in the campaign. |
| dev / validation opponent split registered before tuning | **PASS** | `PANEL_SPLIT.json`, registered before any candidate was built |
| wrapper action-identical to its base with no rules enabled | **PASS** | chal_dp_base: 0 mismatches over 941 decisions; chal_dp_base2: 0 mismatches over 792 decisions; chal_dp_base4: 0 mismatches over 456 decisions; chal_dp_param0: 0 mismatches over 1263 decisions |
| every enabled rule's firing rate was measured, and inert rules were caught | **PASS** | measured for 2 candidates; INERT found and superseded: chal_dp_benchline:bench_discipline_vs_spread (most recent probe; earlier probes in git history) |
| zero illegal selections, exceptions or timeouts from any c023 candidate | **PASS** | 3 non-completed game(s) in 392792, of which 0 belong to a c023 candidate. The remainder: ab_ctrl vs pub_prvsiyan_lucario_v12 (status=['DONE', 'INVALID']); official_dragapult vs pub_prvsiyan_lucario_v12 (status=['INVALID', 'DONE']); pub_prvsiyan_lucario_v12 vs official_mega_lucario (status=['INVALID', 'DONE']) |
| every candidate carries parent, hashes, protocol, seats and counts | **PASS** | `CANDIDATE_HISTORY.jsonl`: 359 candidates |
| packages built and clean-validated by execution | **PASS** | c023_champion_dragapult.tar.gz valid |
| frozen champion package never overwritten | **PASS** | `--freeze` refuses to replace an existing archive |
| validator run with injections | **FAIL** | 11/11 checks pass, 0/0 injections detected |
| all required files and directories present | **PASS** | 15/15 files, 7/7 directories |
| no upload performed without authorization | **PASS** | `LEADERBOARD_SUBMISSION_PLAN.md`: no authorization exists in the repository; kaggle_upload = NOT_PERFORMED |
| honest competitive decision recorded | **PASS** | `EXECUTIVE_DECISION.md`, outcome RESEARCH_SUCCESS |

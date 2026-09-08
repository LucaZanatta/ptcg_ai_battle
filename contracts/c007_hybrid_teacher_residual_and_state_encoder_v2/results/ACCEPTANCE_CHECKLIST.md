# Acceptance Checklist (c007)

Status: **PASS** (16/16 evidence present; substantive assertions 16/16)

| AC | evidence | assertion (verified condition) | verified |
|---|---|---|---|
| AC-01 | present | dependency+immutability all_ok | YES |
| AC-02 | present | model in registered param band | YES |
| AC-03 | present | state encoder v2 accepted (deterministic, audited) | YES |
| AC-04 | present | instrumentation behavior-equivalent (parity overall_valid) | YES |
| AC-05 | present | >=600 games & >=50k decisions (720g/61312d) | YES |
| AC-06 | present | V2 trained & evaluated (V2_B params 538770) | YES |
| AC-07 | present | admitted contexts = ['dragapult_damage_counter'] | YES |
| AC-08 | present | outcome-backed labels; admitted_variant=None, labels=0 | YES |
| AC-09 | present | one on-policy iteration; new_labels=0, final H2 frozen | YES |
| AC-10 | present | H0 parity_pass=True (0 mismatch) & reliability zero-defects | YES |
| AC-11 | present | H2 vs teacher LB 0.4625 (action-identical=True); experiment completed | YES |
| AC-12 | present | improvement=[], regression=[] | YES |
| AC-13 | present | BEST_HYBRID=NONE, SUBMISSION_C=DO_NOT_SUBMIT | YES |
| AC-14 | present | package_validation=True, kaggle=SKIPPED_BY_GATE | YES |
| AC-15 | present | RESIDUAL_RL_READINESS=NOT_READY | YES |
| AC-16 | present | immutability preserved=True, final_head captured | YES |

# Acceptance Checklist (c010)

Status: **PASS** (16/16)

Each criterion requires its evidence files **and** a substantive assertion drawn from their contents. File existence alone never marks a criterion passed (§29).

| AC | evidence | assertion (verified) | passed |
|---|---|---|---|
| AC-01 | present | c005-c009 hashes verified and c009 raw games re-derive B0/I0 scores | YES |
| AC-02 | present | B0/I0/T registered, hashed and marked protected | YES |
| AC-03 | present | A/B equal exact R1; C changes exactly the three registered values | YES |
| AC-04 | present | toy positive control learns; masking exact; B0 initialisation fidelity guarded | YES |
| AC-05 | present | identity assertions pass on every evaluation batch | YES |
| AC-06 | present | per-arm probes measured and full run projected against the hard cap | YES |
| AC-07 | present | all three Arm A seeds executed ([311, 322, 333], 36330 games) | YES |
| AC-08 | present | all three Arm B seeds executed ([411, 422, 433], 22572 games) | YES |
| AC-09 | present | all three Arm C seeds executed ([511, 522, 533], 60464 games) | YES |
| AC-10 | present | screen and confirmation panels executed with exact counts | YES |
| AC-11 | present | held-out value calibration/EV reported per game phase | YES |
| AC-12 | present | three arm decisions follow the registered rules | YES |
| AC-13 | present | final panel run and best agent selected with the incumbent protected | YES |
| AC-14 | present | 118 content checks, 0 failed | YES |
| AC-15 | present | submission gate applied and exactly one next step + blocker stated | YES |
| AC-16 | present | c010 source committed; c005-c009 unchanged; no protected checkpoint altered | YES |

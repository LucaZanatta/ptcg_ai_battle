# c012 Acceptance Checklist

Each criterion needs its evidence AND a substantive assertion from its contents (§52: a PASS requires content validation, not file existence).

| AC | area | assertion (verified) | passed |
|---|---|---|---|
| AC-01 | deps/immutability | 16 checks; 62 c011 checkpoints hash-verified | YES |
| AC-02 | c011 repair | C011_REPAIR=COMPLETE; 5 defects addressed | YES |
| AC-03 | c011 confirmation | 62 candidates registered, 9 newly confirmed | YES |
| AC-04 | ensembles/soups | 4 soups + 4 ensembles, all validated | YES |
| AC-05 | incumbent/elite pool | TRAINING_INCUMBENT=SOUP_622+633, pool=4 | YES |
| AC-06 | overlap analysis | OPPONENT_OVERLAP=SUPPORTED (mean top-1 0.8433862433862435) | YES |
| AC-07 | curriculum lock | registry hash-locked and verified by the trainer at startup | YES |
| AC-08 | P0 control | ['P0_711', 'P0_722', 'P0_733'] | YES |
| AC-09 | P1 adaptive | ['P1_811', 'P1_822', 'P1_833'] | YES |
| AC-10 | curriculum decisions | CURRICULUM_RESULT=TIED, SELF_PLAY_LOOP=NOT_EXTENDED | YES |
| AC-11 | hard-state benchmark | 240 primary + 48 repeat, 240/240 hidden-info clean | YES |
| AC-12 | Claude preflight/labeling | opus verified=True, 17 labels, schema 1.0 | YES |
| AC-13 | branching/qualification | CLAUDE_BRANCHING=INCONCLUSIVE, STATUS=REJECTED | YES |
| AC-14 | best agent/submission | BEST_AGENT=TRUE_INCUMBENT, SUBMISSION_F=DO_NOT_SUBMIT | YES |
| AC-15 | validation/bundle | 91 content checks 0 failed; bundle 0 failed | YES |
| AC-16 | next step/git | NEXT_STEP=REDESIGN_FIXED_DECK_AGENT, 9 commits | YES |

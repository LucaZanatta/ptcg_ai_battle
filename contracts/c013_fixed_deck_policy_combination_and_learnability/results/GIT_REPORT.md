# c013 git report

Branch: `contract/c013_fixed_deck_policy_combination_and_learnability`  
HEAD: `a7d78dd56b7d4a9b75c5e5fa2e6828fc3bdfb477`

## Commits
```text
a7d78dd c013: evaluate all seven section 30 conditions and use an independent immutability baseline
652088a c013: final reports, source bundle, and multi-member gzip reads
455d65b c013: curriculum smoke evaluation flush, backfill, report, and decisions
e0bb445 c013: content-aware validator that re-derives every headline claim
5c02ca1 c013: learnability verdict, repair evidence, and carried-forward repair tests
23fe9d1 c013: combination panels recomputed from raw games, plus Q3 gate
61455bf c013: pair overlap series jointly and add exact-choice identity
10fcbd2 c013: repair-aware label scoring and tolerant output reading
efbb9b5 c013: decode options via engine OptionType and split clean/probe instances
0543b8e c013: opponent overlap on identical states via shadow-query loop
79e361f c013: semantic claude preflight with decoded cards and typed actions
1f95c94 c013: semantic serializer and adaptive-curriculum smoke harness
0ba73d1 c013: soup learnability trainer (Q0 direct, Q1 value refit, Q2 component continue)
8112dcd c013: registries, online ensemble implementation and identity-safe ensemble evaluation
12a091d c012: consolidate arm and confirmation artifacts into required names
c528bdb c012: qualify claude offline teacher and build source bundle
4efbdf7 c012: summary generator and corrected Claude rate accounting
fef18b2 c012: content validator, source bundle, reports and c011 repair report
ce62495 c012: crash-safe Claude labeling and card-content state serialization
2c3137b c012: fix stale checkpoint-hash cache that emptied in-run evaluations
19ff437 c012: overlap analysis and hash-locked curriculum registry
d3f4cdd c012: elite combinations and frozen incumbent
4f5cd07 c012: repair c011 continuation (active Generator, live-RNG permutations, true continuation test)
a3dcdd6 c011: consolidate per-seed training output into required artifact names
38f1f1e c011: reports, summary and command record
c054049 c011: scale results, decisions, content validator and governance repair
7bc7865 c011: mandatory python source bundle with clean-extraction validation
a87e96c c011: add parity-validated pytorch cuda backend, benchmarks and scale trainer
dd273c7 c011: repair c010 checkpoint evidence and add the parity-validated torch model
6530fe8 c010: guard the threshold-tie defect in content validation, not only unit tests
```

## Working tree at completion
```text
?? cg
?? check.py
?? contracts/c002_reproducible_episode_capture/
?? contracts/c003_episode_lineage_and_semantic_replay/
?? contracts/c004_competitive_baseline_gauntlet/
?? contracts/c005_teacher_import_submission_and_dataset/
?? contracts/c006_distilled_policy_baseline/
?? contracts/c007_hybrid_teacher_residual_and_state_encoder_v2/
?? contracts/c008_fixed_deck_teacher_anchored_rl/
?? contracts/c009_amendment_c008/
?? contracts/c010_fixed_deck_rl_loop_v2/
?? contracts/c011_fixed_deck_cuda_ppo_scale/
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/CLAUDE_COMMAND.txt
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/CONTRACT.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/inputs/
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/references/
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results.zip
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/ACCEPTANCE_CHECKLIST.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/COMMANDS_RUN.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/FILES_CHANGED.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/GIT_REPORT.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/STATUS.json
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/SUMMARY.md
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/artifacts/
?? contracts/c012_fixed_deck_selfplay_curriculum_and_claude_teacher_qualification/results/test_logs/
?? contracts/c013_fixed_deck_policy_combination_and_learnability/
?? pokemon-tcg-ai-battle-challenge-strategy/
?? tmp.txt
```

`results/` is intentionally uncommitted, per the contract execution protocol: source is committed with a `c013:` prefix, evidence stays on disk.


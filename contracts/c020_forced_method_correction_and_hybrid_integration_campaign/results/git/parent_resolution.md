# Parent resolution

## Expected vs actual

`inputs/PROJECT_GROUND_TRUTH.md` and `CONTRACT.md §1` name the expected c019 final commit:

```text
55c14c83e8bddc0bd40f510605538735790ae20c
```

The actual branch tip of `contract/c019_dual_method_campaign_ptcg_mcts_and_byterl` is one commit later:

```text
a1d322e291e51b86aa308410b96a7b19748060f0
c019: correct the hybrid narrative to match its own ablation
```

## Resolution: parent is a1d322e

`CONTRACT.md §1` permits selecting a later c019 descendant "only when it is a legitimate c019 correction". `a1d322e` qualifies, and is result-generating rather than cosmetic:

1. `SUMMARY.md §6` still carried a pre-ablation conclusion — that the hybrid evidence "points at the search" — which the c019 adapter ablation contradicts. The ablation shows the priors cost −28.7 field points against pure MCTS while the calibrated leaf value costs −2.5. §6 now carries the ablation table and the correct attribution.
2. `DECISION_BOARD.json` listed `ptcg_byterl_v0` with basis `"see panel"`, a placeholder from before the ByteRL gate decision existed. It now carries the measured verdict.
3. `STATUS.json` `git_commit` was one commit stale, so the recorded commit did not match the tree it described.

All three are corrections to c019's own reported evidence, made within c019's scope, with no method or measurement change. `55c14c8` is the commit at which every c019 measurement was complete; `a1d322e` is the commit at which c019's report agrees with those measurements. c020 must start from evidence that is internally consistent, so the later commit is the correct parent.

Both commits are recorded here so the c019→c020 boundary is auditable in either direction.

## Verification at branch time

```text
git status --short (tracked)   0 modified
git branch --show-current      contract/c019_dual_method_campaign_ptcg_mcts_and_byterl
git rev-parse HEAD             a1d322e291e51b86aa308410b96a7b19748060f0
```

The c019 working tree was clean at branch time, so no uncommitted c019 work is carried into c020 implicitly.

## Immutability commitment

c020 creates `cg/c020_*.py`, `starter_kit/c020_*.py`, `tools/c020_*.py`, `tests/test_c020_*.py` and writes only under
`contracts/c020_forced_method_correction_and_hybrid_integration_campaign/results/`.

No c005–c019 file is modified. The c019 MCTS, ByteRL and hybrid modules are retained unchanged as the named controls
`C019_PIMC_PUCT_CONTROL`, `C019_BYTERL_CONTROL`, `C019_HYBRID_CONTROL` (`CONTRACT.md §2`). Untracked user files are left alone;
no history rewrite, reset, rebase, force-push, or clean is performed.

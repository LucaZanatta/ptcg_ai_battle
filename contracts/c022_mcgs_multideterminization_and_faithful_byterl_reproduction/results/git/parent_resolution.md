# Parent resolution

`CONTRACT.md §1` names `cdbd4438496c905eaf38ee257abfe0c822c588f4` as the expected c021 final
*result-generation* commit and requires me to resolve the actual latest legitimate c021
descendant. It differs, so this document records why the difference is legitimate and which
commit c022 branches from.

## What I found

```text
expected parent  cdbd4438496c905eaf38ee257abfe0c822c588f4
actual branch    contract/c021_source_faithful_mcgs_and_byterl_transfer_campaign
actual tip       7be9e04b316d79022fb10856de7f92d90555abdd
relationship     7be9e04 is the direct child of cdbd4438
```

`git log` at the tip:

```text
7be9e04 c021: canonical source archive at the final commit -- contract closed
cdbd443 c021: final results -- 47/49 probes PASS, 101 tests, 18/18 injection-detecting checks
```

## Why 7be9e04 is legitimate, and why it is the one c022 branches from

The contract's phrase is "final **result-generation** commit". `cdbd443` is exactly that: it is
the commit that c021's own `results/source/` archive was cut from, and c021's `SOURCE_FIDELITY`
proof is anchored to it. `7be9e04` adds only the archive of that tree.

The full diff between them is ten files, all under
`contracts/c021_source_faithful_mcgs_and_byterl_transfer_campaign/results/`:

```text
M results/DECISION_BOARD.json
M results/git/final_head.txt
M results/git/log.txt
M results/git/status.txt
M results/source/c021_focused_source.zip
M results/source/git_diff.patch
M results/source/hashes.sha256
M results/source/plain_inspection/c021_report.py
M results/source/plain_inspection/c021_select.py
M results/source/source_manifest.json
```

Verified properties:

- **No code changed.** Nothing under `starter_kit/`, `tools/`, `tests/` or `external_refs/`
  appears in the diff, so every algorithm, checkpoint-producing script and evaluation tool at
  `7be9e04` is byte-identical to `cdbd443`.
- **No c021 measurement changed.** No file under `results/mcgs/`, `results/byterl/`,
  `results/transfer/`, `results/final_panel/` or `results/probes/` appears in the diff, so every
  raw number c022 must reconcile is the number `cdbd443` produced.
- **The changes are self-describing archive artifacts.** `git_diff.patch`, `hashes.sha256`,
  `source_manifest.json`, the focused zip and the plain-inspection exports are the F05 source
  capture; `git/final_head.txt` and `git/log.txt` are the commit record of the capture itself.
  They can only change when the archive is cut, which is a post-results operation by
  construction.

So `7be9e04` is `cdbd443` plus its own provenance record. Branching from `cdbd443` would discard
c021's source archive from c022's history for no benefit; branching from `7be9e04` preserves the
whole of c021 including the proof that its source was captured.

## Decision

```text
c022 branch     contract/c022_mcgs_multideterminization_and_faithful_byterl_reproduction
branched from   7be9e04b316d79022fb10856de7f92d90555abdd
```

`results/git/initial_head.txt` records the branch point. The commit named in the contract,
`cdbd443`, remains the reference for **c021 raw evidence**: every number reconciled in
`results/references/c021_audit_reconciliation.md` is read from artifacts whose content is
identical at both commits, and any file I have to recover from an earlier c021 commit (the
pre-extension training curves, overwritten during c021's four-hour extension) is cited by its own
commit hash at the point of use.

## Preservation

c005–c021 and unrelated user work are preserved immutably: c022 creates only
`contracts/c022_.../`, new `starter_kit/c022_*.py`, `tools/c022_*.py` and `tests/**/c022_*`
files. No c021-or-earlier tracked file is modified. The 135 untracked entries recorded in
`results/git/status.txt` (older contract folders c002–c016, the `cg` symlink, `check.py`,
scratch files) are left exactly as they are — they are not c022's to commit or clean.

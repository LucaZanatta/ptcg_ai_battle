# Teacher Research — c005 (dated 2026-07-24)

Evidence is separated by class, per the research brief. Author-reported ratings
are **not** treated as independently verified.

## Verified facts (this contract, with hashes/commands)
- Four official Kaggle sample kernels by `kiyotah` were retrieved anonymously via
  `kaggle kernels output` (packaged `submission.tar.gz`) + `kaggle kernels pull`
  (notebook source). SHA-256 and retrieval timestamps in `source_evidence.json`.
  | candidate | archetype | main.py | deck (distinct) | ref |
  |---|---|---|---|---|
  | dragapult | Dragapult ex | 853 lines | 22 | kiyotah/a-sample-rule-based-agent-dragapult-ex-deck |
  | mega_lucario | Mega Lucario ex | 508 lines | 17 | kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck |
  | mega_abomasnow | Mega Abomasnow ex | 267 lines | 9 | kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck |
  | iono | Iono's deck | 415 lines | 15 | kiyotah/a-sample-rule-based-agent-iono-s-deck |
- Each bundles a `cg/` SDK whose `libcg.so` and `api.py` are **byte-identical**
  (sha256 `75d7d619…`, `593f1298…`) to this repo's starter kit — the agents run
  unmodified against the local cabt engine.
- Each is a genuine rule-based **strategic** policy (module-level `AttackPlan`,
  turn tracking, evolution/attach/attack scoring) — not a positional/random control.
- All four run locally and beat the random control in preliminary checks; they
  play each other with their own decks (verified two-teacher isolation).
- The public repo `github.com/wmh/ptcg-abc` was cloned at commit `1b31d39a…`;
  it contains 20+ agent directories (bellibolt, alakazam, dragapult, …) and has
  **no license file** (`license NONE`).

## Author-reported (NOT independently verified)
- `wmh/ptcg-abc` reports Bellibolt as its best ladder result at **Elo 836**
  (repo/brief). This is an author claim; c005 does not treat it as verified and
  Bellibolt is LOCAL_BENCHMARK_ONLY (see reuse audit).

## Official benchmark evidence (reported)
- The research brief / competition discussion places **Dragapult** and **Mega
  Lucario** in the top official-sample tier; Mega Lucario is noted as more linear.
  Treated as reported prior, confirmed or overridden by the c005 local gauntlet.

## Local c005 results
- The strategic gauntlet ranking, worst-matchups, reliability, and latency are
  produced in Phase C and recorded in `strategic_ranking.json` /
  `strategic_bootstrap.json` / `strategic_worst_matchups.json`; the teacher
  selection in `teacher_selection.json`. This research file's prior does not
  override the computed local result.

## Recency & source quality
- Kernels last run 2026-06; repo commit recent (2026). Official Kaggle samples are
  the highest-provenance source (competition-provided baselines); the public repo
  is medium quality and, lacking a license, is local-benchmark-only.

## Unverified claims (excluded from selection evidence)
- Any exact current-ladder standing or Elo not reproduced here. External-evidence
  scoring uses only the predefined tiers with a per-candidate justification in
  `teacher_scorecard.csv`.

# Current competition facts (verified this run)

Accessed **2026-07-26T17:00:57.090076+02:00** (Europe/Rome) / 2026-07-26T15:00:57.090076+00:00 UTC via authenticated Kaggle CLI.

- **Slug**: `pokemon-tcg-ai-battle`
- **Title**: The Pokémon Company - PTCG AI Battle Challenge Simulation
- **Deadline**: 2026-08-16 23:59:00 UTC → **2026-08-17T01:59:00+02:00** Europe/Rome
- **Evidence label**: `OFFICIAL_CURRENT`

A second competition `pokemon-tcg-ai-battle-challenge-strategy` (deadline 2026-09-13 23:59:00) also exists. a different competition. Every prior submission in this project (c005 ref 54948560, public score 719.7) and the frozen teacher control live in pokemon-tcg-ai-battle; switching would break the only external comparison c014 has. The repo folder of the same name holds card-data reference PDFs/CSVs, not competition assets.

## Runtime limits

From the `cabt` environment specification read locally: `episodeSteps=10000`, `actTimeout=0s`, `runTimeout=3000s`. actTimeout=0 means the local build enforces no per-decision limit; runTimeout=3000s bounds a whole episode.

## Gaps recorded rather than guessed

- **Daily submission limit**: `GAP`. the rules page is client-rendered, so an unauthenticated fetch returns only the document title. Not substituted from the handoff. c014 makes exactly one upload (§7), so any plausible daily limit (commonly 2-5) is not binding. Last prior submissions were 2026-07-24, so today's quota is untouched.

- **Published per-decision timeout**: not obtainable for the same reason. c014 therefore enforces §11's explicit p99 ≤ 250 ms plus a **self-imposed** maximum of 1000 ms per decision. This bound is labelled self-imposed, not quoted: with `runTimeout=3000s` per episode and ~90 decisions per seat, even 1 s per decision leaves the episode budget untouched.

## External reference points

- Frozen Dragapult teacher, submission ref **54948560**, public score **719.7** (SubmissionStatus.COMPLETE) — the project's only external measurement and c014's control.
- Current public leaderboard top: 1192.4, 1162.3, 1155.1, 1148.3, 1140.0 (top team `James Cox`).

## Package rules

submission.tar.gz containing main.py and deck.csv at the archive root, unpacked at `/kaggle_simulations/agent/`. Source: ichigoe/beginner-guide-from-deck-list-to-first-valid-sub, plus c005's submission_A_teacher.tar.gz which was ACCEPTED and scored 719.7 - a package shape proven correct by the leaderboard rather than by reading

## Public code and data usage

deck lists are factual card-ID configurations, and the notebooks used here publish them explicitly as shared samples for this competition (competition_sources lists pokemon-tcg-ai-battle). c014 uses public notebooks as EVIDENCE for selection and takes one deck list; it does not copy any published agent implementation - the deterministic expert in §10 is written for this contract.

Licence field: absent from `kaggle kernels pull -m` output; not assumed to be permissive, which is a further reason only the factual deck list is reused.

## Sources snapshotted

| ref | title | files |
|---|---|---|
| `ichigoe/beginner-guide-from-deck-list-to-first-valid-sub` | [Beginner Guide] From Deck List to First Valid Sub | 2 |
| `makthanithin/pok-mon-tcg-ai-battle-meta-snapshot-06-29` | ⚡ Pokémon TCG AI Battle: Meta Snapshot: 06-29 | 2 |
| `masamikobayashi/a-sample-archaludon-75-wr-vs-my-1300-starmie` | A Sample Archaludon: 75% WR vs my 1300+ Starmie | 2 |
| `pilkwang/pok-mon-tcg-ai-battle-meta-snapshot-18-july` | ⚡ Pokémon TCG AI Battle: Meta Snapshot: 18 July | 2 |
| `romanrozen/strong-start-baseline-agent-v10-lb-950` | [STRONG START]: Baseline Agent V10 | LB 950+ | 2 |
| `ryotasueyoshi/rule-based-not-psychic-alakazam-best-5th` | 🤖 Rule-based, not psychic: Alakazam (Best: 5th) | 2 |
| `smallpond/en-replay-archetype-analysis` | [日本語/EN] Replay Archetype Analysis(環境デッキ分析) | 2 |

Every snapshot file is hashed in `public_source_manifest.sha256`.


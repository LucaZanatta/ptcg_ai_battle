# Teacher Research Brief — 2026-07-24

## Provisional recommendation

**Primary prior:** Official Dragapult sample.

Why:

- Official sample benchmarking places Dragapult and Mega Lucario in the top tier.
- Dragapult offers richer strategic supervision than a purely linear deck.
- The exact official Kaggle kernel and matched deck/agent output are publicly retrievable.
- Official sample provenance is the lowest-risk path for Submission A.

**Mandatory challenger:** wmh/ptcg-abc Bellibolt.

Why:

- Its repository reports Bellibolt as its best ladder result at Elo 836.
- The policy/deck pair is complete and intentionally simple.
- Author-reported ladder performance is useful but not independently verified.
- No explicit repository license was visible during research; treat it as local benchmark only unless reuse rights are established.

**Mandatory official benchmark:** Mega Lucario.

Why:

- It is reported in the same top official-sample tier.
- It is more linear and may be easier to distill.

## Exact sources

Official sample retrieval guide and kernel identifiers:

- https://zenn.dev/redzonegen/articles/redzonegen-kaggle-ptcg-local-env?locale=en
- https://note.com/rii_pokeka/n/n7586e5cf20a3

Official sample benchmark discussion:

- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/708617

Public benchmark repository:

- https://github.com/wmh/ptcg-abc

Current public roster/discovery:

- https://www.kaggle.com/code/makimakiai/ptcg-public-27-plus-sample-4-roster-update
- https://www.kaggle.com/code/prvsiyan/ptcg-ai-battle-field-audited-alakazam-v8
- https://www.kaggle.com/code/llccqq624/ptcg-meta-a-stable-submit

## Evidence discipline

The c005 result must separate:

- official benchmark evidence
- author-reported ladder evidence
- public local benchmark evidence
- c005 local gauntlet evidence
- actual Kaggle submission evidence

Do not select a teacher solely from an author-reported rating.

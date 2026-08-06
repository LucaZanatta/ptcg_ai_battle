# Reuse, attribution and permission matrix (§12)

**The Kaggle API exposes no licence field for kernels.** Verified this run by listing kernel objects and inspecting every attribute. Permission therefore cannot be read off the platform, and §12 forbids inferring it from visibility.

| candidate | class | may execute | may package | may submit |
|---|---|---|---|---|
| `official_dragapult` | **SUBMISSION_REUSE_ALLOWED** | True | True | True |
| `official_mega_lucario` | **SUBMISSION_REUSE_ALLOWED** | True | True | True |
| `official_mega_abomasnow` | **SUBMISSION_REUSE_ALLOWED** | True | True | True |
| `official_iono` | **SUBMISSION_REUSE_ALLOWED** | True | True | True |
| `community_a-sample-archaludon-75-wr-vs` | **LOCAL_BENCHMARK_ONLY** | True | False | False |
| `community_rule-based-not-psychic-alaka` | **LOCAL_BENCHMARK_ONLY** | True | False | False |
| `community_strong-start-baseline-agent-` | **LOCAL_BENCHMARK_ONLY** | True | False | False |

### Basis for `SUBMISSION_REUSE_ALLOWED`

- competition SAMPLE kernel published by the competition's sample author
- c005 recorded reuse_classification=OFFICIAL_REUSABLE and submission_eligible=true with the retrieval commands preserved
- EMPIRICAL PRECEDENT: c005 packaged the Dragapult sample and Kaggle accepted and scored it (ref 54948560, 719.7, COMPLETE) - an observed fact about this competition, not an inference from visibility

The third point is the load-bearing one: it is an **observed outcome**, not a reading of a licence. An identically-sourced package was submitted and scored by this competition.

### Basis for `LOCAL_BENCHMARK_ONLY`

- no licence field is exposed for kernels by the Kaggle API - verified this run by listing kernel objects and inspecting every attribute
- no equivalent acceptance precedent exists for community code
- §12: absence of a licence is not permission, and legal rights are not inferred from visibility

Community agent **source is not copied, packaged, or uploaded** by c016. Their factual deck lists remain usable — c014 already used one — because a list of card IDs is a game configuration, not authored code.

### Attribution recorded for any submitted candidate

- `official_dragapult`: Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-dragapult-ex-deck (Kiyota)
- `official_mega_lucario`: Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-mega-lucario-ex-deck (Kiyota)
- `official_mega_abomasnow`: Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-mega-abomasnow-ex-deck (Kiyota)
- `official_iono`: Official Kaggle sample kernel kiyotah/a-sample-rule-based-agent-iono-s-deck (Kiyota)


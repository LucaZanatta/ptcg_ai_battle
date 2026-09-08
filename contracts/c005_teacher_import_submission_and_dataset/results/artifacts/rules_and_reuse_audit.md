# Rules and Reuse Audit — c005

## Competition rules retrieval
- Rules URL (precise reference): `https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules`
- Competition: `pokemon-tcg-ai-battle` (category **Knowledge**, deadline 2026-08-16),
  confirmed via `kaggle competitions list`.
- **Retrieval limitation (recorded honestly):** the rules page is a JavaScript-
  rendered single-page app; an unauthenticated plain HTTP fetch returns only a
  ~5.7 KB shell with **no machine-extractable rules text**. The full rules text
  could not be archived verbatim without an authenticated/browser session, which
  is not available here. This is a known limitation, not a claim that rules were
  read. See the submission decision for how this is handled conservatively.

## Reuse classification (per candidate)
| candidate | source | classification | submission-eligible | basis |
|---|---|---|---|---|
| dragapult | official kiyotah kernel | **OFFICIAL_REUSABLE** | yes | Competition-provided official sample agent (public kernel, retrievable anonymously). Official samples are the intended baseline starting point for a first submission. |
| mega_lucario | official kiyotah kernel | **OFFICIAL_REUSABLE** | yes | as above |
| mega_abomasnow | official kiyotah kernel | **OFFICIAL_REUSABLE** | yes | as above |
| iono | official kiyotah kernel | **OFFICIAL_REUSABLE** | yes | as above |
| bellibolt (wmh/ptcg-abc) | public GitHub repo, **no license** | **LOCAL_BENCHMARK_ONLY** | **no** | No explicit license → no reuse rights established. Used only as a locally-executed benchmark **if** admitted; never submitted and never copied into training artifacts. |

## Attribution requirements
- Official samples: attribute to the Kaggle author (Kiyota) and the exact kernel
  reference + version (recorded in `frozen_teacher_manifest.json` / `SOURCE.json`).
- Bellibolt: attribute to `wmh/ptcg-abc` @ commit if used as a local benchmark; it
  is excluded from Submission A and from the training dataset.

## Handling given the retrieval limitation (conservative)
- **Only** OFFICIAL_REUSABLE official samples are considered for Submission A; the
  no-license public repo is excluded from submission and from training data.
- Because the full rules text could not be archived verbatim, the submission
  decision additionally requires the packaging + reliability gates, and the actual
  upload stays gated behind `PTCG_ALLOW_KAGGLE_SUBMIT=1` (absent → no upload). No
  third-party non-official code is placed in the submission.

## Git handling
- Raw third-party downloads (official kernels + the public repo) live under this
  contract's `results/` (uncommitted); they are **not** committed to the project
  git history. Only c005's own scripts are committed. The frozen teacher directory
  (an official reusable sample) is kept under `results/` as review evidence, not
  committed, consistent with the conservative reuse posture.

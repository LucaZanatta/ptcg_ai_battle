# Required c014 inputs

c015 must locate and ingest the completed c014 result directory:

```text
contracts/c014_public_meta_baseline_and_rapid_submission/results/
```

Minimum required evidence:

- `STATUS.json`;
- `artifacts/meta_selection.json`;
- `artifacts/META_SELECTION.md`;
- `artifacts/selected_deck.csv`;
- `artifacts/selected_deck.sha256`;
- `artifacts/ANTI_META_PROVISIONAL.md`;
- `artifacts/matchup_matrix.csv`;
- `artifacts/strategy_coherence.json`;
- `artifacts/next_loss_mode.json`;
- `artifacts/submission_H_public_meta_v0.tar.gz`;
- `artifacts/submission_H_manifest.json`;
- `artifacts/submission_H_validation.json`;
- `artifacts/kaggle_submission_status.json`;
- `artifacts/public_sources.json`;
- `artifacts/CURRENT_COMPETITION_FACTS.md`;
- `artifacts/decision_board.json`.

Hard start gate:

- c014 validated package exists and its recorded SHA-256 matches;
- c014 package validation hard gates passed;
- c014 has a non-null accepted Kaggle submission reference;
- c014 score may be `PENDING`.

If the hard start gate fails, write a concise blocking report and stop. Do not implement or submit c015 from an unvalidated or unsubmitted c014 state.

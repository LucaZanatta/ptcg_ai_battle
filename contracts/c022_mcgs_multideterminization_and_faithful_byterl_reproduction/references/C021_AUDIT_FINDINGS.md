# c021 Audit Findings to Reconcile

Expected raw-artifact findings:

- Final c021 commit: `cdbd4438496c905eaf38ee257abfe0c822c588f4`.
- MCGS rollout estimates were severely overconfident under one determinization.
- The official source's private-information restoration/re-determinization was not fully ported.
- c021 fixed-deck B2 final external performance was reported around 24–26%, after roughly 76,800 games.
- c021 fixed-deck learning was materially above the random floor.
- c021 model was feed-forward rather than LSTM recurrent.
- c021 stage names did not match published Hearthstone b0→b3 meanings.
- c021 B3/OSFP evidence was defective or insufficient.
- c021 transfer point estimates were positive for prior/rollout arms but below measured run-to-run noise.

Do not trust prose alone. Recompute all values from c021 raw files and record discrepancies.

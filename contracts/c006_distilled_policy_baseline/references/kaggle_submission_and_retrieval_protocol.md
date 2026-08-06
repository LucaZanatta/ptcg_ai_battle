# Kaggle Submission and Retrieval Protocol

## Authorization

For c006, the user explicitly authorizes Claude Code to upload the student when,
and only when, the contract's local Submission B gate returns `SUBMIT`.

No environment-variable opt-in is required for that gated upload.

## Competition

```text
pokemon-tcg-ai-battle
```

## Immutable teacher reference

```text
submission ref: 54948560
recorded public score: 617.8
recorded status: SubmissionStatus.COMPLETE
```

This reference belongs in c006 evidence. Do not edit c005.

## Required workflow

```text
validate archive
→ guard against duplicates
→ submit
→ retrieve submission row
→ record submission ref
→ poll bounded status
→ record public score snapshot
→ retrieve teacher snapshot
→ compare and decide promote/keep/wait
```

## Evidence rules

- Preserve raw CLI stdout/stderr.
- Preserve verbose submissions CSV.
- Store each polling snapshot as one JSONL record.
- Never store credentials.
- Never invent a score or terminal status.
- Public score is a timestamped ladder snapshot, not a permanent ground truth.

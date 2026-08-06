# Results and source bundle specification

The user must be able to upload the results ZIP to ChatGPT and have the implementation audited without access to the live repository.

## Required code bundles

### complete_repository_source.zip

Full repository source at final HEAD, excluding `.git`, virtual environments, caches, secrets, and unrelated large generated datasets.

### c017_competition_source_bundle.zip

Focused runnable source for:

- baseline;
- search/simulator adapter;
- state/action representation;
- trajectory pipeline;
- policy/value model;
- supervised and PPO trainers;
- curriculum;
- evaluation;
- packages/submission;
- tests and probes;
- all configs and deck files.

### Milestone snapshots

Preserve exact source/config hashes for baseline submission, first full smoke, post-repair, best scaled checkpoint, final candidates, and submitted packages.

## Required evidence

- raw game records;
- sampled search-node traces;
- trajectory schema/manifests/samples;
- complete training logs;
- curriculum history and actual opponent mix;
- checkpoint hashes and resume evidence;
- clean package validation logs;
- Kaggle responses and rating snapshots;
- all probe inputs/outputs;
- exceptions, timeouts, hidden-info, identity, and taint records;
- Git patch/status/log.

No summary may replace the raw evidence used to support it.

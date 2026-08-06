# Results and Source Bundle Specification

The c018 results must include the implementation as well as reports.

Required source artifacts:

- `results/source/complete_repository_source.zip`
- `results/source/competition_source_bundle.zip`
- `results/source/git_diff.patch`
- `results/source/source_manifest.json`
- `results/source/hashes.sha256`
- `results/source/environment.txt`
- `results/source/dependency_lock.txt`
- milestone snapshots for baseline verification, real heuristic search, training start, curriculum final, guided search, and every submitted package.

Required raw evidence includes:

- simulator-generated search traces and search-state lifecycle logs;
- real game-level and action-level records;
- trajectory manifests, schemas, and representative/full data where feasible;
- policy/value losses, optimizer-step counts, gradient statistics, checkpoint hashes, and curriculum histories;
- actual opponent identities and completed-game counts;
- package validation and submission responses;
- all failed probe inputs, outputs, exceptions, and timeouts;
- Git initial/final HEAD, status, log, and patch.

The package source must be traceable to the exact evaluated milestone snapshot and hashes. Reports alone are insufficient.

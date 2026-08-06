# Provenance of these snapshots

§11 directs c016 to "use c014's existing snapshots first". These files are **copies** of the
snapshots c014 retrieved via `kaggle kernels pull -m`, reproduced here so c016's evidence tree is
self-contained. The c014 originals are untouched (§6), and every file is hashed in
`../public_source_manifest.sha256`.

Community notebooks among these are classified `LOCAL_BENCHMARK_ONLY` in
`../REUSE_PERMISSION_MATRIX.md`: they may be read and executed locally, and their **source is
never copied into a package or uploaded**. Only the official sample agents — separately
classified `SUBMISSION_REUSE_ALLOWED` — were advanced as candidates.

# Why this branch has no history

The main repository is **19.58 GiB** and cannot be pushed to GitHub. The cause is in history, so
deleting files could not fix it:

| blob | size |
|---|---:|
| `c021/results/source/final_git_archive.tar.gz` | **5.7 GB** (and a second copy at 4.3 GB) |
| `c020/results/source/complete_repository_source.zip` | **1.9 GB** (and 1.8 GB) |
| `c023/git/diff_vs_main.patch` | **1.2 GB** (and 469 MB) |
| `results.z01`–`z07` across c018–c022 | ~25 × 400 MB |

A `git archive` of the repository was committed **into** the repository, twice, alongside a zip of
its own source. GitHub hard-blocks any file over 100 MB and any push over 2 GB, so no push of the
existing history can ever succeed.

This branch is therefore a **curated snapshot of the current working tree** — all source, all
reports, no archives — with no ancestry. 15 MB, 1,121 files.

## What is here

- `tools/`, `starter_kit/`, `tests/` — every Python source file, plus the engine `libcg.so`
- `results/c024_final_sprint/` — the c024 reports, including `RETROSPECTIVE.md`
- `results/c023.../` — top-level reports and manifests only (its `raw_evaluations/` is ~400k games
  of JSONL and is not source)
- `contracts/**/*.md` — all 556 contract documents

## What is not here, and where it is

Raw evaluation records, replay caches, packaged submission archives and the `.venv`. All of it
remains in the local repository at `/home/luca/kaggle/ptcg_ai_battle`; none of it is source, and
all of it is regenerable by the tools in `tools/`.

## To recover full history later

`git filter-repo --strip-blobs-bigger-than 50M` on a clone, then force-push. That rewrites every
commit hash and is destructive, which is why it was not done unilaterally.

# License and clean-room policy

## Hearthstone repository

The `peter1591/hearthstone-ai` repository declares GPL licensing. Do not copy GPL source files or translated line-by-line code into a competition package without an explicit compatibility decision documented by the user and competition rules.

Default requirement:

- inspect repository structure and algorithms;
- write an original clean-room PTCG implementation;
- preserve citations and retrieval hashes;
- do not vendor the Hearthstone engine or source.

## ByteRL

No verified public official ByteRL implementation repository was identified in the source papers/competition materials. The published competition slides describe a proprietary RL framework. Therefore:

- implement from the papers and pseudocode;
- do not hallucinate a repository;
- do not label generic PPO code as ByteRL;
- document every PTCG-specific adaptation.

## PTCG/public agents

Use only competition-permitted code and data. Preserve exact source, URL, author, date, hash, license/permission status, and attribution. If permission is unclear, use the material for local benchmarking only and do not include it in submission archives.

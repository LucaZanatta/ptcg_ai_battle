# Optimizer states

Not preserved. The PPO trainer creates its AdamW optimizer per run from `PPO_CFG` and does not checkpoint optimizer moments; P13's continuation check therefore verifies that a reloaded *model* checkpoint continues training and performs real updates, not that Adam moments round-trip. Recorded as a known limitation rather than left as an unexplained empty directory.

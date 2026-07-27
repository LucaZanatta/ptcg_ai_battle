# F03 — Method-fidelity validator

52/63 checks. Written before the runs it judges, and every check re-derives from raw artifacts rather than reading a summary that asserts the number.

It has already earned that design: it caught a defect where the ByteRL summary reported 20,000 games and 2,500 optimizer steps while the raw rows showed 12,000 games with zero completed and 0.8 steps each.

**Status: PASS.**

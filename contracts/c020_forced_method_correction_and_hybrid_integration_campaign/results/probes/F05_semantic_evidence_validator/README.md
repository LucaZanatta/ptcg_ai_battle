# F05 — Semantic evidence validator

37/41 checks with **34 carrying a negative control** and 0 broken.

Audit findings #16/#17 are the reason for that middle number: the c019 validator passed while every semantic defect was live, because it checked that methods existed. Here each semantic check injects the c019 behaviour as a fixture and must reject it. A check whose injection does not trip it is reported BROKEN rather than passing — a check that cannot fail is not evidence.

# Failures and deviations

1. **Forward simulation impossible** — `env.clone()` shares native `libcg.so` state; advancing a clone core-dumps the process. Recorded as probe P10. This removed real lookahead from the campaign permanently.

2. **Reduced campaign scale** — roughly 1-5% of §6's caps, registered in advance in `artifacts/REGISTERED_MODE_AND_SCALE.md`. Every training result is underpowered and is labelled DIAGNOSTIC.

3. **Distilled policy weaker than its teacher's baseline** — 0.526 top-1 agreement against a 0.909 copy-the-baseline rate. Reported rather than buried.

4. **Zero performance promotions** in the curriculum. Both transitions were `FALLBACK_SCHEDULE`, which §26 says is not evidence of success.

5. **Six integration defects** found by the thin smoke, ranked in `integration/FIRST_PASS_DEFECT_RANKING.md`. Three were invisible as errors; one was in the error handling itself and destroyed evidence.

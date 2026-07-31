# T04 value-only transfer — not run, precondition unmet

This directory is empty of arms on purpose, and the reason is a gate rather than a shortage of
time. An empty directory with no explanation would read as an oversight.

## The gate

`PROBE_MATRIX T04`: *"Runs only after value admission."*

`transfer/registered_protocol.json`, written before any transfer arm ran, states the admission
condition:

> Admission requires the value head to beat a **CONSTANT predictor at the observed base rate** on
> held-out games (`results/byterl/external_evaluations/*_eval.json`,
> `value_calibration.beats_constant_predictor`).

## The measurement

The value heads do not clear it:

| checkpoint | value skill vs a constant predictor at the base rate |
|---|---:|
| `floor_fixed_deck` | **−0.06** |
| `floor_end_to_end` | **−0.10** |

Both negative. A head that cannot beat "always predict the base rate" has learned nothing about
which positions are good, however small its mean-squared error looks in absolute terms — which is
what probe `B23` asserts and why the comparison is made against a constant predictor rather than
against zero.

## Why the gate was not waived

Transferring a value that has not earned admission would put a component into corrected MCGS on
the strength of its label rather than its measured quality. That is precisely the failure c021's
transfer arms are recorded as here — `UNTESTED`, because the checkpoint they queried was
statistically indistinguishable from an untrained floor, so the arm compared
MCGS-with-a-random-prior against MCGS-with-uniform-random and answered nothing.

Running T04 anyway would have produced a third arm, a third field score and a third row in a
table, and none of it would have meant anything. `ACCEPTANCE_CHECKLIST.md` records T04 as
`NOT_RUN` with this reason rather than as a gap.

## What would change this

A value head admitted on held-out calibration — positive skill against the constant predictor.
The extension arm `br3_fixed_deck_long` reached 73% of the matched budget and its *policy*
separates from the random floor; its value head has not been evaluated for admission, and that is
the cheap next measurement if T04 is ever wanted.

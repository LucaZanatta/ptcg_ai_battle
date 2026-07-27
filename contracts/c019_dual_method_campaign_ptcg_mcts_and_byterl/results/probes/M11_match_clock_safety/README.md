# M11 — Match-clock safety

At the registered configuration (48 simulations x 3 determinizations) search costs a mean of 31.2s and a maximum of 45.7s per match, with 6259 decisions hitting the per-decision budget. That is not shippable next to a baseline whose whole game takes ~1.2s.

A calibration sweep produced a package configuration (12 simulations x 1 determinization) at 4.6s mean / 7.7s max. The submitted package uses that config, and the gate panel evaluated the config that would actually ship rather than a faster-than-shipped or slower-than-shipped variant.

**Status: WARN** — safe at the package config, unsafe at the registered config, and both numbers are reported.

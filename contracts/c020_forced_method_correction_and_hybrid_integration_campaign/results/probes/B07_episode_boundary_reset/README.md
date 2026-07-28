# B07 — Episode boundary reset

**15520 of 15520** mid-game unrolls carry non-default stored state; only true episode-start unrolls begin at zero.

The requirement cuts both ways, and the packaged agent violated the other direction: it reset NEVER, carrying state across games. Fixed and recorded in `failures/package_failures/`.

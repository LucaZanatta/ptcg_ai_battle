# B07 — Queue and sample reuse

A bounded FIFO deque (capacity 8,192 unrolls), not an uncontrolled replay ring. Sample reuse 2 is implemented as *each collected sample consumed twice on average*: the number of minibatches scales with how much new experience arrived.

A defect was fixed here — a fixed two minibatches per round gave each sample well under one use, which is not sample reuse 2 in any sense.

**Status: PASS.**

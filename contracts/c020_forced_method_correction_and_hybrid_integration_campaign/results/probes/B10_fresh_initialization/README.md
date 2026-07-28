# B10 — Fresh initialization and optimizer

Corrected ByteRL starts from fresh random weights and a fresh optimizer, with the initial parameter hash recorded at launch. `CONTRACT §2` forbids initializing it from c019 because the observation, action and recurrent semantics all changed; the c019 checkpoint is a control only.

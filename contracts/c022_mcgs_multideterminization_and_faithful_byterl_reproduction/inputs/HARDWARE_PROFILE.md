# Hardware Profile

```text
OS: Ubuntu 24.04.4 LTS
CPU: AMD Ryzen 9 7900X, 12 physical / 24 logical cores
RAM: 61 GiB usable, approximately 39 GiB available at measurement
GPU: NVIDIA GeForce RTX 5070, approximately 11.5 GiB VRAM
CUDA driver/toolkit: functional
PyTorch: CUDA available
Root storage free at measurement: approximately 172 GiB
Additional disks: two 1.8 TB ext4 devices available but not shown mounted
```

Operational guidance:

- MCGS decisive runs receive full physical CPU.
- Start ByteRL actor scaling at 4/8/12 actors; use >12 only when measured waiting makes it beneficial.
- Keep training resident in physical RAM; active swap is a failure condition.
- Use a dedicated Python 3.11/3.12 environment if Python 3.13 dependency issues arise.
- Store checkpoints/traces on a large mounted data disk when available; do not fill the root volume.

#!/usr/bin/env python3
"""Hunt the EDC_VALUE companion of EDC_LIMIT (0x0FC=180A) and list every float
that saturates near 100 under load (=> percent fields, not temperatures).

Run: python3 research/recheck_edc.py
"""

import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"


def avg(n=20, gap=0.15):
    acc = None
    for _ in range(n):
        with open(PM, "rb") as f:
            d = f.read()
        pm = struct.unpack(f"<{len(d) // 4}f", d)
        acc = list(pm) if acc is None else [a + b for a, b in zip(acc, pm)]
        time.sleep(gap)
    return [v / n for v in acc]


print("IDLE 25s ...")
time.sleep(25)
idle = avg()

p = subprocess.Popen(
    ["stress-ng", "--cpu", "16", "--timeout", "60"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print("LOAD 45s ...")
time.sleep(45)
load = avg()
p.wait()

print("\n=== EDC_VALUE candidates: idle<40, load in [90,182] ===")
for idx, (i, lo) in enumerate(zip(idle, load)):
    if i < 40 and 90 <= lo <= 182 and lo - i > 40:
        print(f"0x{idx * 4:03X} d[{idx:3d}] {i:9.3f} -> {lo:9.3f}")

print("\n=== Saturating / near-100 under load (percent fields) ===")
for idx, (i, lo) in enumerate(zip(idle, load)):
    if 95 <= lo <= 100.5 and i < 90:
        print(f"0x{idx * 4:03X} d[{idx:3d}] {i:9.3f} -> {lo:9.3f}")

print("\n=== Biggest absolute movers (top 25) ===")
mov = sorted(
    ((abs(lo - i), idx, i, lo) for idx, (i, lo) in enumerate(zip(idle, load))),
    reverse=True,
)
for d, idx, i, lo in mov[:25]:
    print(f"0x{idx * 4:03X} d[{idx:3d}] {i:12.3f} -> {lo:12.3f}  (delta {lo - i:+.3f})")

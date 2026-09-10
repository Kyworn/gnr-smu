#!/usr/bin/env python3
"""Full-table sweep: classify every float by how it behaves between idle and a
long steady-state all-core load, using k10temp as the only degC ground truth.

Answers two questions the current PM_TABLE_MAP.md gets wrong:
  1. which offsets are *really* degC (slope ~1.0 vs Tctl AND absolute match)
  2. which "thermal metrics" are actually W / A / % (the map calls them
     "non-linearly encoded temperatures")

Run: python3 research/recheck_sweep.py
"""

import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
TCTL = "/sys/class/hwmon/hwmon3/temp1_input"
TCCD = "/sys/class/hwmon/hwmon3/temp3_input"


def sample():
    with open(PM, "rb") as f:
        d = f.read()
    return (
        struct.unpack(f"<{len(d) // 4}f", d),
        int(open(TCTL).read()) / 1000.0,
        int(open(TCCD).read()) / 1000.0,
    )


def settle(seconds, label):
    """Settle, then average over 3s — Tctl on Zen 5 is spiky, a single read lies."""
    print(f"{label}: settling {seconds}s ...")
    time.sleep(seconds)
    acc, n = None, 20
    for _ in range(n):
        pm, tctl, tccd = sample()
        if acc is None:
            acc = [list(pm), tctl, tccd]
        else:
            acc[0] = [a + b for a, b in zip(acc[0], pm)]
            acc[1] += tctl
            acc[2] += tccd
        time.sleep(0.15)
    pm = [v / n for v in acc[0]]
    tctl, tccd = acc[1] / n, acc[2] / n
    core = pm[317:325]
    print(f"  Tctl={tctl:.2f} Tccd1={tccd:.2f} coreavg={sum(core) / 8:.2f} "
          f"coremax={max(core):.2f} coremin={min(core):.2f}")
    return pm, tctl, tccd, core


i_pm, i_tctl, i_tccd, i_core = settle(30, "IDLE")

p = subprocess.Popen(
    ["stress-ng", "--cpu", "16", "--timeout", "70"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
l_pm, l_tctl, l_tccd, l_core = settle(60, "LOAD (steady state)")
p.wait()

dt = l_tctl - i_tctl
print(f"\nTctl {i_tctl:.2f} -> {l_tctl:.2f} (delta {dt:+.2f})")

print("\n=== ZONE 0x000-0x034 : (LIMIT, VALUE) pair hypothesis ===")
print(f"{'off':>6} {'idx':>4} {'idle':>10} {'load':>10} {'delta':>9}")
for off in range(0x000, 0x038, 4):
    i, lo = i_pm[off // 4], l_pm[off // 4]
    print(f"0x{off:03X} {off // 4:4d} {i:10.3f} {lo:10.3f} {lo - i:+9.3f}")

print("\n=== REAL degC CANDIDATES (|val-Tctl|<6 at BOTH points, slope 0.8-1.2) ===")
hits = []
for idx, (i, lo) in enumerate(zip(i_pm, l_pm)):
    if i == lo:
        continue
    slope = (lo - i) / dt
    if 0.8 <= slope <= 1.25 and abs(i - i_tctl) < 6 and abs(lo - l_tctl) < 6:
        hits.append((idx, i, lo, slope))
for idx, i, lo, s in hits:
    print(f"0x{idx * 4:03X} d[{idx:3d}] {i:8.2f} -> {lo:8.2f}  slope={s:.2f}")
if not hits:
    print("  (none)")

print("\n=== degC-LIKE but offset from Tctl (slope 0.8-1.25, any absolute) ===")
for idx, (i, lo) in enumerate(zip(i_pm, l_pm)):
    if i == lo:
        continue
    slope = (lo - i) / dt
    if 0.8 <= slope <= 1.25 and not any(h[0] == idx for h in hits):
        print(f"0x{idx * 4:03X} d[{idx:3d}] {i:8.2f} -> {lo:8.2f}  slope={slope:.2f} "
              f"(delta to Tctl: idle {i - i_tctl:+.1f}, load {lo - l_tctl:+.1f})")

print("\n=== SATURATED AT 100 UNDER LOAD (=> percent, not degC) ===")
for idx, (i, lo) in enumerate(zip(i_pm, l_pm)):
    if abs(lo - 100.0) < 0.01 and i < 99.0:
        print(f"0x{idx * 4:03X} d[{idx:3d}] {i:8.2f} -> {lo:8.2f}")

print("\n=== DOC'D 'thermal metrics' RE-CHECKED ===")
for off, doc in [
    (0x00C, "Package Thermal Metric"),
    (0x024, "SoC Temperature Metric"),
    (0x02C, "VRM/Hotspot Temp"),
    (0x100, "Thermal Metric"),
    (0x348, "CCD Thermal Metric"),
    (0x2E8, "GFX Thermal Metric"),
    (0x438, "TDC Current Value"),
    (0x458, "PPT Current Value"),
    (0x4A8, "L3/V-Cache Temp 0"),
    (0x4AC, "L3/V-Cache Temp 1"),
    (0x700, "Average Core Temp"),
    (0x704, "Min Core Temp"),
    (0x720, "Ambient/Board Temp"),
]:
    i, lo = i_pm[off // 4], l_pm[off // 4]
    print(f"0x{off:03X} {i:9.3f} -> {lo:9.3f} (slope vs Tctl {(lo - i) / dt:5.2f})  {doc}")

print(f"\n0x00C - 0x050 : idle {i_pm[3] - i_pm[20]:+.3f}  load {l_pm[3] - l_pm[20]:+.3f}"
      "   (constant => 0x00C = 0x050 + SoC/uncore, i.e. both are WATTS)")
print(f"0x4A8 - 0x720 : idle {i_pm[298] - i_pm[456]:+.3f}  load {l_pm[298] - l_pm[456]:+.3f}")
print(f"core avg vs 0x700: load coreavg={sum(l_core) / 8:.2f} vs 0x700={l_pm[448]:.2f}")
print(f"core min vs 0x704: load coremin={min(l_core):.2f} vs 0x704={l_pm[449]:.2f}")
print(f"PPT limit 0x008={l_pm[2]:.1f}  PPT value 0x00C={l_pm[3]:.1f}")
print(f"TDC limit 0x020={l_pm[8]:.1f}  TDC value 0x024={l_pm[9]:.1f}")
print(f"THM limit 0x028={l_pm[10]:.1f}  THM value 0x02C={l_pm[11]:.1f}")
print(f"EDC max  0x0FC={l_pm[63]:.1f}")

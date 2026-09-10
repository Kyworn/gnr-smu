#!/usr/bin/env python3
"""Re-verify the zone 0x000 labels in PM_TABLE_MAP.md against hard ground truth.

Ground truth: RAPL package energy (W), k10temp Tctl/Tccd1 (degC).
Hypothesis under test: zone 0x000 is the classic Zen (LIMIT, VALUE) pair layout
  0x008/0x00C = PPT_LIMIT / PPT_VALUE (W)
  0x020/0x024 = TDC_LIMIT / TDC_VALUE (A)
  0x028/0x02C = THM_LIMIT / THM_VALUE (degC)
...not the "encoded non-linear temperature" the map claims.

Run: sudo python3 research/recheck_zone0.py
"""

import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
RAPL = "/sys/class/powercap/intel-rapl:0/energy_uj"
TCTL = "/sys/class/hwmon/hwmon3/temp1_input"
TCCD = "/sys/class/hwmon/hwmon3/temp3_input"

# offsets we care about -> current doc label
WATCH = {
    0x00C: "Package Thermal Metric (doc)",
    0x024: "SoC Temperature Metric (doc)",
    0x02C: "VRM/Hotspot Temp (doc)",
    0x050: "Package Power (doc)",
    0x054: "SoC Power (doc)",
    0x100: "Thermal Metric (doc)",
    0x348: "CCD Thermal Metric (doc)",
    0x2E8: "GFX Thermal Metric (doc)",
    0x2EC: "GFX Thermal Headroom (doc)",
    0x438: "TDC Current Value (doc)",
    0x458: "PPT Current Value (doc)",
    0x4A8: "L3/V-Cache Temp 0 (doc)",
    0x700: "Average Core Temp (doc)",
    0x720: "Ambient/Board Temp (doc)",
}


def read_int(path):
    with open(path) as f:
        return int(f.read().strip())


def read_energy():
    # ponytail: RAPL needs root; None means "power ground truth unavailable"
    try:
        return read_int(RAPL)
    except PermissionError:
        return None


def sample():
    with open(PM, "rb") as f:
        data = f.read()
    floats = struct.unpack(f"<{len(data) // 4}f", data)
    return {
        "pm": floats,
        "energy": read_energy(),
        "t": time.monotonic(),
        "tctl": read_int(TCTL) / 1000.0,
        "tccd": read_int(TCCD) / 1000.0,
        "core_temps": floats[317:325],
    }


def rapl_watts(a, b):
    if a["energy"] is None or b["energy"] is None:
        return float("nan")
    # energy_uj wraps; 32-bit-ish counter, max_energy_range_uj not needed at this scale
    d = b["energy"] - a["energy"]
    return (d / 1e6) / (b["t"] - a["t"])


def phase(label, seconds, proc=None):
    a = sample()
    time.sleep(seconds)
    b = sample()
    b["watts"] = rapl_watts(a, b)
    print(f"\n=== {label} ===")
    print(f"RAPL package : {b['watts']:7.2f} W")
    print(f"k10temp Tctl : {b['tctl']:7.2f} degC   Tccd1: {b['tccd']:.2f} degC")
    print(f"core temps   : {' '.join(f'{v:.1f}' for v in b['core_temps'])}")
    for off, name in WATCH.items():
        print(f"  0x{off:03X} = {b['pm'][off // 4]:10.3f}   <- {name}")
    return b


idle = phase("IDLE (8s)", 8)

print("\n>>> stress-ng --cpu 16 for 20s ...")
p = subprocess.Popen(
    ["stress-ng", "--cpu", "16", "--timeout", "24"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(6)  # let it ramp
load = phase("LOAD (8s)", 8)
p.wait()

print("\n\n================ DELTA ANALYSIS ================")
print(f"RAPL package power : {idle['watts']:.2f} -> {load['watts']:.2f} W")
print(f"k10temp Tctl       : {idle['tctl']:.2f} -> {load['tctl']:.2f} degC")
print(f"k10temp Tccd1      : {idle['tccd']:.2f} -> {load['tccd']:.2f} degC")
print()
print(f"{'off':>6} {'idle':>10} {'load':>10} {'delta':>9}  {'vs W':>8} {'vs Tctl':>8}")
dw = load["watts"] - idle["watts"]
dt = load["tctl"] - idle["tctl"]
for off in WATCH:
    i, lo = idle["pm"][off // 4], load["pm"][off // 4]
    d = lo - i
    rw = d / dw if abs(dw) > 1 else float("nan")
    rt = d / dt if abs(dt) > 1 else float("nan")
    print(f"0x{off:03X} {i:10.3f} {lo:10.3f} {d:+9.3f}  {rw:8.2f} {rt:8.2f}")

print("\nRatio ~1.00 in 'vs W' column => that offset IS watts (tracks RAPL 1:1).")
print("Ratio ~1.00 in 'vs Tctl'      => that offset IS degC (tracks k10temp 1:1).")
print(f"\nSanity: 0x2E8 + 0x2EC = {load['pm'][0x2E8 // 4] + load['pm'][0x2EC // 4]:.3f}")

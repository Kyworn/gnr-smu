#!/usr/bin/env python3
"""Test whether d[595]/d[596] and d[611]/d[612] are actually coupled to L3
cache traffic, or just to general CCD0 core power/temperature.

Previous test (recheck_l3.py) only proved CCD-affinity using stress-ng --cpu
(ackermann-like ALU load, tiny working set, low L3 traffic). That does not
distinguish "L3 sensor" from "any CCD0 sensor" (core hotspot, package point,
etc).

This test pins two different CCD0-only workloads with similar core utilization
but very different L3 traffic, and compares how much each candidate lane rises
relative to core-avg and to socket power:

  A) --cpu-method ackermann   -- branchy/ALU, tiny footprint, minimal L3 traffic
  B) --cache --cache-level 3  -- deliberately thrashes the L3 cache

If a lane's rise (relative to core-avg / socket power) is materially larger in
B than in A, that supports L3-traffic coupling. If both loads produce the same
lane response for similar core power, the lane is not L3-specific -- it is
just a general CCD/package temperature sensor and the "L3" label is unproven.

Run: python3 research/l3_specificity.py
"""

import glob
import statistics
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from hwgate import get_hardware_profile  # noqa: E402

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
WATCH = [595, 596, 611, 612]


def physical_core_cpus():
    cores = {}
    for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*"):
        cpu = int(Path(path).name[3:])
        topology = Path(path) / "topology"
        try:
            package = int((topology / "physical_package_id").read_text())
            core = int((topology / "core_id").read_text())
        except OSError:
            continue
        cores[(package, core)] = min(cpu, cores.get((package, core), cpu))
    return [cores[key] for key in sorted(cores)]


def read_pm(profile):
    with open(PM, "rb") as f:
        return struct.unpack(f"<{profile.float_count}f", f.read(profile.table_size))


def sample(profile, seconds, hz=8):
    rows = []
    n = int(seconds * hz)
    for _ in range(n):
        rows.append(read_pm(profile))
        time.sleep(1 / hz)
    return rows


def medians(rows):
    return [statistics.median(v) for v in zip(*rows)]


def run_workload(cpus, args, seconds):
    cpu_list = ",".join(str(c) for c in cpus)
    proc = subprocess.Popen(
        ["taskset", "-c", cpu_list, "stress-ng", *args, "--timeout", f"{seconds}s"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def report(label, med, profile):
    core_avg_ccd0 = statistics.mean(med[profile.core_temp + i] for i in range(8))
    socket_power = med[26] if profile.pm_version == 0x620205 else med[20]
    print(f"\n[{label}] Tctl={med[11]:.2f}  CCD0-avg={core_avg_ccd0:.2f}  "
          f"socket_power={socket_power:.2f} W")
    for idx in WATCH:
        print(f"  d[{idx}] = {med[idx]:8.3f}   (CCD0-avg + {med[idx] - core_avg_ccd0:+.2f})")


def main():
    profile, why = get_hardware_profile()
    if profile is None:
        print(f"Unsupported hardware for this research script: {why}")
        return
    print(f"{profile.name}: PM table 0x{profile.pm_version:X}, {profile.table_size} bytes")

    cores = physical_core_cpus()
    ccd0_cpus = cores[:8]

    print("\nbaseline 10s (keep desktop idle) ...")
    time.sleep(10)
    base = medians(sample(profile, 5))
    report("BASELINE", base, profile)

    print(f"\nA) ALU-only load on CCD0 (cpus {ccd0_cpus}), 20s ...")
    p = run_workload(ccd0_cpus, ["--cpu", str(len(ccd0_cpus)), "--cpu-method", "ackermann"], 25)
    time.sleep(5)
    a = medians(sample(profile, 15))
    p.wait()
    report("A: ALU (ackermann, low L3 traffic)", a, profile)

    print("\ncool-down 15s ...")
    time.sleep(15)

    print(f"\nB) L3 cache-thrash load on CCD0 (cpus {ccd0_cpus}), 20s ...")
    p = run_workload(ccd0_cpus, ["--cache", str(len(ccd0_cpus)), "--cache-level", "3"], 25)
    time.sleep(5)
    b = medians(sample(profile, 15))
    p.wait()
    report("B: L3 cache-thrash", b, profile)

    print("\n=== Comparison (delta over baseline, relative to CCD0-avg rise) ===")
    core_avg = lambda med: statistics.mean(med[profile.core_temp + i] for i in range(8))
    d_core_a = core_avg(a) - core_avg(base)
    d_core_b = core_avg(b) - core_avg(base)
    print(f"CCD0-avg core temp rise:  A={d_core_a:+.2f} K   B={d_core_b:+.2f} K")
    for idx in WATCH:
        d_a = a[idx] - base[idx]
        d_b = b[idx] - base[idx]
        ratio_a = d_a / d_core_a if d_core_a else float("nan")
        ratio_b = d_b / d_core_b if d_core_b else float("nan")
        print(f"  d[{idx}]: rise A={d_a:+.2f} K (x{ratio_a:.2f} of core rise)   "
              f"rise B={d_b:+.2f} K (x{ratio_b:.2f} of core rise)")

    print("\nInterpretation: if x-ratios for B are materially higher than for A,")
    print("the lane tracks L3 traffic beyond what core temp/power explains.")
    print("If A and B ratios are similar, the lane is just a general CCD/package")
    print("sensor and is NOT proven to be L3-specific.")


if __name__ == "__main__":
    main()

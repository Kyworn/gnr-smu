#!/usr/bin/env python3
"""Controlled re-test of L3-cache specificity, matched for core temperature.

l3_specificity.py showed a promising signal (cache-thrash load moved the
candidate lanes 3-6x more per K of core-temp rise than ALU load), but that
comparison was confounded: the ALU run reached far higher absolute core
temperatures (~69 degC) than the cache run (~41 degC), and a non-linear sensor
response could produce the same-looking ratio difference without any real L3
coupling.

This script removes that confound. It:
  1) runs the L3 cache-thrash load unrestricted on CCD0 and records its
     natural CCD0-avg core-temp rise (R_cache),
  2) throttles an ALU-only load (via --cpu-load duty cycling) on CCD0 until
     its CCD0-avg core-temp rise matches R_cache within ~1 K,
  3) compares the candidate lanes (d[595]/d[596]/d[611]/d[612]) between the
     two workloads *at matched core-temp rise* -- if the cache-thrash load
     still moves them further, that is not explained by core heating and is
     real evidence of L3 coupling. If they match, the "L3" identity remains
     unsupported.

Run: python3 research/l3_specificity_controlled.py
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
LOAD_SECONDS = 22
SAMPLE_SECONDS = 12
COOLDOWN_SECONDS = 20


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
    for _ in range(int(seconds * hz)):
        rows.append(read_pm(profile))
        time.sleep(1 / hz)
    return rows


def medians(rows):
    return [statistics.median(v) for v in zip(*rows)]


def core_avg(profile, med, cpus_range=range(8)):
    return statistics.mean(med[profile.core_temp + i] for i in cpus_range)


def run_workload(cpus, args, seconds):
    cpu_list = ",".join(str(c) for c in cpus)
    return subprocess.Popen(
        ["taskset", "-c", cpu_list, "stress-ng", *args, "--timeout", f"{seconds}s"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def measure(profile, cpus, args, label):
    p = run_workload(cpus, args, LOAD_SECONDS)
    time.sleep(LOAD_SECONDS - SAMPLE_SECONDS)
    med = medians(sample(profile, SAMPLE_SECONDS))
    p.wait()
    print(f"  [{label}] CCD0-avg={core_avg(profile, med):.2f}  Tctl={med[11]:.2f}")
    return med


def main():
    profile, why = get_hardware_profile()
    if profile is None:
        print(f"Unsupported hardware: {why}")
        return
    print(f"{profile.name}: PM table 0x{profile.pm_version:X}, {profile.table_size} bytes")

    ccd0_cpus = physical_core_cpus()[:8]

    print("\nbaseline 10s (keep desktop idle) ...")
    time.sleep(10)
    base = medians(sample(profile, 6))
    base_core = core_avg(profile, base)
    print(f"  [BASELINE] CCD0-avg={base_core:.2f}  Tctl={base[11]:.2f}")

    print(f"\ncache-thrash load on CCD0 (cpus {ccd0_cpus}), unrestricted ...")
    cache_med = measure(profile, ccd0_cpus, ["--cache", "8", "--cache-level", "3"], "CACHE")
    r_cache = core_avg(profile, cache_med) - base_core
    print(f"  -> natural core-temp rise R_cache = {r_cache:+.2f} K")

    print(f"\ncool-down {COOLDOWN_SECONDS}s ...")
    time.sleep(COOLDOWN_SECONDS)

    print("\nsearching ALU duty cycle that matches R_cache ...")
    duty = 25
    alu_med = None
    r_alu = None
    for attempt in range(4):
        print(f"\n  trying --cpu-load {duty} ...")
        alu_med = measure(
            profile, ccd0_cpus,
            ["--cpu", "8", "--cpu-method", "ackermann", "--cpu-load", str(duty)],
            f"ALU @{duty}%",
        )
        r_alu = core_avg(profile, alu_med) - base_core
        print(f"  -> core-temp rise = {r_alu:+.2f} K (target {r_cache:+.2f} K)")
        if abs(r_alu - r_cache) <= 1.0:
            print("  matched within 1 K, stopping search.")
            break
        # simple proportional adjustment toward target
        if r_alu <= 0:
            duty = min(95, duty + 20)
        else:
            duty = max(5, min(95, round(duty * r_cache / r_alu)))
        print(f"\n  cool-down {COOLDOWN_SECONDS}s before retry ...")
        time.sleep(COOLDOWN_SECONDS)

    print("\n=== Matched-temperature comparison ===")
    print(f"R_cache={r_cache:+.2f} K   R_alu={r_alu:+.2f} K "
          f"(diff {r_alu - r_cache:+.2f} K)")
    for idx in WATCH:
        d_cache = cache_med[idx] - base[idx]
        d_alu = alu_med[idx] - base[idx]
        print(f"  d[{idx}]: cache-thrash rise={d_cache:+.2f} K   "
              f"ALU rise={d_alu:+.2f} K   (extra from cache = {d_cache - d_alu:+.2f} K)")

    print("\nInterpretation: with core-temp rise matched between the two loads,")
    print("a materially larger cache-thrash delta on a lane is evidence of real")
    print("L3-traffic coupling for that lane. A similar delta means the lane is")
    print("just tracking general CCD0 heating, not L3 activity specifically.")


if __name__ == "__main__":
    main()

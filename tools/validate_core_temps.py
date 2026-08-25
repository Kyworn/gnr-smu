#!/usr/bin/env python3
"""Validate per-core PM temperature lanes with a pinned single-core workload.

Defaults to the first core on each half of the package (core 0 and core N/2), which
selects one core from each CCD on the 9950X3D. This is read-only: the workload is a
userspace busy loop and no SMU command is sent.

Run: python3 tools/validate_core_temps.py
"""

import argparse
import glob
import os
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from hwgate import get_hardware_profile  # noqa: E402

PM = "/sys/kernel/ryzen_smu_drv/pm_table"


def physical_core_cpus():
    """Return logical CPUs ordered by (package, physical core), one SMT sibling each."""
    cores = {}
    for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*"):
        cpu = int(os.path.basename(path)[3:])
        topology = Path(path) / "topology"
        try:
            package = int((topology / "physical_package_id").read_text())
            core = int((topology / "core_id").read_text())
        except OSError:
            continue
        cores[(package, core)] = min(cpu, cores.get((package, core), cpu))
    return [cores[key] for key in sorted(cores)]


def find_k10temp():
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if Path(path, "name").read_text().strip() == "k10temp":
                return Path(path)
        except OSError:
            pass
    return None


def k10temps(hwmon):
    if hwmon is None:
        return {}
    values = {}
    for label_path in hwmon.glob("temp*_label"):
        stem = label_path.name.removesuffix("_label")
        try:
            label = label_path.read_text().strip()
            values[label] = int((hwmon / f"{stem}_input").read_text()) / 1000
        except OSError:
            pass
    return values


def table(profile):
    with open(PM, "rb") as f:
        data = f.read(profile.table_size)
    if len(data) != profile.table_size:
        raise RuntimeError(f"short PM-table read: {len(data)}/{profile.table_size}")
    return struct.unpack(f"<{profile.float_count}f", data)


def sample(profile, seconds, hwmon):
    rows, sensors = [], []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        sensors.append(k10temps(hwmon))  # external sensor first; see audit_map.py
        rows.append(table(profile))
        time.sleep(0.2)
    return rows, sensors


def lane_medians(rows, start, count):
    return [statistics.median(row[start + core] for row in rows)
            for core in range(count)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cores", type=int, nargs="*",
                        help="physical core numbers to load (default: one per CCD)")
    parser.add_argument("--seconds", type=float, default=10,
                        help="load duration per core (default: 10)")
    args = parser.parse_args()

    profile, why = get_hardware_profile()
    if profile is None:
        raise SystemExit(f"refusing to interpret PM table: {why}")
    cpu_for_core = physical_core_cpus()
    if len(cpu_for_core) != profile.cores:
        raise SystemExit(f"topology reports {len(cpu_for_core)} cores, expected "
                         f"{profile.cores}")
    cores = args.cores if args.cores is not None else [0, profile.cores // 2]
    if any(core < 0 or core >= profile.cores for core in cores):
        raise SystemExit(f"core must be in range 0..{profile.cores - 1}")

    print(why)
    hwmon = find_k10temp()
    failures = 0
    for core in cores:
        idle, _ = sample(profile, 2, hwmon)
        worker = subprocess.Popen(
            ["taskset", "-c", str(cpu_for_core[core]), sys.executable, "-c",
             "while True: pass"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            loaded, sensors = sample(profile, args.seconds, hwmon)
        finally:
            worker.terminate()
            worker.wait()

        baseline = lane_medians(idle, profile.core_temp, profile.cores)
        hot = lane_medians(loaded[-20:], profile.core_temp, profile.cores)
        delta = [b - a for a, b in zip(baseline, hot)]
        hottest_lane = max(range(profile.cores), key=delta.__getitem__)
        sensor_text = ""
        if sensors and sensors[-1]:
            sensor_text = "; " + ", ".join(
                f"{name}={statistics.median(s[name] for s in sensors[-20:]):.1f} °C"
                for name in sensors[-1]
            )
        ok = hottest_lane == core and delta[core] >= 5
        print(f"{'PASS' if ok else 'FAIL'} core {core} on logical CPU "
              f"{cpu_for_core[core]}: lane {hottest_lane} rose most "
              f"({delta[hottest_lane]:+.1f} °C), now {hot[hottest_lane]:.1f} °C"
              f"{sensor_text}")
        failures += not ok
        time.sleep(3)

    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

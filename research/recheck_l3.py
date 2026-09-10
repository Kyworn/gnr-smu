#!/usr/bin/env python3
"""Per-CCD load differential for the L3 temperature candidates on 9950X3D.

The current profile maps L3 temps to d[595]/d[596]. The dump also shows a second
temperature-like pair at d[611]/d[612] (~6-7 °C above the core temps). To find
which pair HWiNFO calls "L3 Cache (CCDx)", load each CCD separately and watch
which lanes rise selectively with that CCD, and how each lane relates to the
per-core temps d[333..348] and k10temp Tccd1/Tccd2.

HWiNFO L3 behaviour (from reference screenshot, idle-ish desktop):
  * two per-CCD values
  * each sits slightly *above* its CCD's average core temp (+1.7/+2.0 °C)
  * clearly *below* the CCD Tdie hotspot (Tdie - 2.6 / -6.2 °C)
  * moves a few °C with load

Run: python3 research/recheck_l3.py
"""

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
WATCH = list(range(589, 613))  # whole per-CCD L3 block


def physical_core_cpus():
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
    values = {}
    if hwmon is None:
        return values
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
        sensors.append(k10temps(hwmon))
        rows.append(table(profile))
        time.sleep(0.2)
    return rows, sensors


def medians(rows, count):
    return [statistics.median(row[i] for row in rows) for i in range(count)]


def k10_med(sensors, name):
    vals = [s[name] for s in sensors if name in s]
    return statistics.median(vals) if vals else float("nan")


def load_cpus(cpus):
    return [subprocess.Popen(
        ["taskset", "-c", str(cpu), sys.executable, "-c", "while True: pass"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for cpu in cpus]


def stop(workers):
    for w in workers:
        w.terminate()
    for w in workers:
        w.wait()


def report(tag, med, sens, profile):
    ct = [med[profile.core_temp + c] for c in range(profile.cores)]
    ccd0_avg = statistics.mean(ct[:8])
    ccd1_avg = statistics.mean(ct[8:])
    t1, t2 = k10_med(sens, "Tccd1"), k10_med(sens, "Tccd2")
    print(f"\n[{tag}]  Tctl={med[11]:.2f}  k10temp Tccd1={t1:.2f} Tccd2={t2:.2f}")
    print(f"  core-temp avg: CCD0(cores0-7)={ccd0_avg:.2f}  CCD1(cores8-15)={ccd1_avg:.2f}")
    print("  lane     value   d(CCD0avg)")
    for i in WATCH:
        v = med[i]
        if v == 0.0:
            continue
        rel = v - ccd0_avg
        print(f"  d[{i:3d}] {v:10.4f}  {rel:+9.2f}")
    return ccd0_avg, ccd1_avg


def main():
    profile, why = get_hardware_profile()
    if profile is None:
        raise SystemExit(f"refusing to interpret PM table: {why}")
    print(why)
    cpu_for_core = physical_core_cpus()
    hwmon = find_k10temp()

    print("baseline 5 s (keep the desktop idle) ...")
    base_rows, base_sens = sample(profile, 5, hwmon)
    base = medians(base_rows, profile.float_count)
    report("BASELINE", base, base_sens[-15:], profile)

    ccd0_cpus = [cpu_for_core[c] for c in range(8)]
    print(f"\nloading CCD0 (cores 0-7, cpus {ccd0_cpus}) 12 s ...")
    w = load_cpus(ccd0_cpus)
    try:
        r, s = sample(profile, 12, hwmon)
    finally:
        stop(w)
    med = medians(r[-25:], profile.float_count)
    report("CCD0 LOAD", med, s[-25:], profile)

    print("\ncool-down 10 s ...")
    time.sleep(10)

    ccd1_cpus = [cpu_for_core[c] for c in range(8, 16)]
    print(f"loading CCD1 (cores 8-15, cpus {ccd1_cpus}) 12 s ...")
    w = load_cpus(ccd1_cpus)
    try:
        r, s = sample(profile, 12, hwmon)
    finally:
        stop(w)
    med = medians(r[-25:], profile.float_count)
    report("CCD1 LOAD", med, s[-25:], profile)

    print("\nInterpretation hints:")
    print("  * true per-CCD L3 lane rises selectively when ITS CCD is loaded")
    print("  * HWiNFO L3 sits slightly above avg core temp, below Tdie")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Paired transient logger for Vermeer global-telemetry validation.

Captures, at ~5 Hz and with monotonic timestamps, the full PM table plus
independent Linux references (k10temp, RAPL package/core energy, cpufreq)
across idle / load / cooldown phases with several workload types.

Read-only towards the firmware: the only sysfs writes in this tool are none
(the PM table, hwmon, powercap and cpufreq are all read).  Load comes from
userspace stress-ng workers, terminated after each phase.

Run on the target host, e.g.:
  python3 research/vermeer/transient/vermeer_transient.py --out /tmp/vermeer_run1.jsonl
Analyse offline with research/vermeer/transient/vermeer_track.py.

Phase plan (single run, ~7 min):
  idle 30s, matrix-1core 30s, cooldown 40s, matrix-3core 30s, cooldown 40s,
  matrix-12thr 30s, cooldown 40s, int64-6core 25s, cooldown 30s,
  cache-6core 25s, cooldown 30s
"""
import argparse
import glob
import json
import struct
import subprocess
import sys
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
PM_SIZE = 1488
NFLOAT = PM_SIZE // 4

PHASES = [
    ("idle", 30, None),
    ("matrix-1", 30, ["taskset", "-c", "0", "stress-ng", "--cpu", "1",
                      "--cpu-method", "matrixprod", "--timeout", "35s",
                      "--metrics-brief"]),
    ("cooldown", 40, None),
    ("matrix-3", 30, ["taskset", "-c", "0-2", "stress-ng", "--cpu", "3",
                      "--cpu-method", "matrixprod", "--timeout", "35s",
                      "--metrics-brief"]),
    ("cooldown", 40, None),
    ("matrix-12", 30, ["stress-ng", "--cpu", "12",
                       "--cpu-method", "matrixprod", "--timeout", "35s",
                       "--metrics-brief"]),
    ("cooldown", 40, None),
    ("int64-6", 25, ["taskset", "-c", "0-5", "stress-ng", "--cpu", "6",
                     "--cpu-method", "int64", "--timeout", "30s",
                     "--metrics-brief"]),
    ("cooldown", 30, None),
    ("cache-6", 25, ["taskset", "-c", "0-5", "stress-ng", "--cache", "6",
                     "--cache-level", "3", "--timeout", "30s",
                     "--metrics-brief"]),
    ("cooldown", 30, None),
]


def find_k10temp():
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(f"{path}/name") as f:
                if f.read().strip() == "k10temp":
                    return path
        except OSError:
            pass
    return None


def read_k10temp(hwmon):
    out = {}
    for lp in glob.glob(f"{hwmon}/temp*_label"):
        stem = lp.removesuffix("_label")
        try:
            with open(lp) as f:
                label = f.read().strip()
            with open(f"{stem}_input") as f:
                out[label] = int(f.read()) / 1000.0
        except OSError:
            pass
    return out


def find_rapl():
    found = {}
    for path in glob.glob("/sys/class/powercap/intel-rapl:*"):
        try:
            with open(f"{path}/name") as f:
                name = f.read().strip()
            with open(f"{path}/energy_uj") as f:
                f.read()
            found[name] = path
        except OSError:
            pass
    return found


def read_rapl(rapl):
    out = {}
    for name, path in rapl.items():
        try:
            with open(f"{path}/energy_uj") as f:
                out[name] = int(f.read())
        except OSError:
            pass
    return out


def read_pm():
    with open(PM, "rb") as f:
        data = f.read(PM_SIZE)
    if len(data) != PM_SIZE:
        raise RuntimeError(f"short PM-table read: {len(data)}")
    return struct.unpack(f"<{NFLOAT}f", data)


def read_cpufreq(ncpu=12):
    out = []
    for cpu in range(ncpu):
        try:
            with open(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/"
                      f"scaling_cur_freq") as f:
                out.append(int(f.read()) / 1000.0)
        except OSError:
            out.append(None)
    return out


def sample(hwmon, rapl):
    return {
        "t": time.monotonic(),
        "wall": time.time(),
        "k10": read_k10temp(hwmon),
        "rapl": read_rapl(rapl),
        "freq": read_cpufreq(),
        "pm": list(read_pm()),
    }


def run_phase(label, seconds, cmd, hz, fh):
    worker = None
    if cmd is not None:
        worker = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        if worker.poll() is not None:
            print(f"workload failed to start: {cmd}", file=sys.stderr)
            worker = None
    hwmon = find_k10temp()
    rapl = find_rapl()
    if hwmon is None:
        raise SystemExit("k10temp hwmon not found")
    print(f"[{time.strftime('%H:%M:%S')}] phase {label} {seconds}s "
          f"(k10temp={hwmon}, rapl={sorted(rapl)})", flush=True)
    deadline = time.monotonic() + seconds
    n = 0
    try:
        while time.monotonic() < deadline:
            row = sample(hwmon, rapl)
            row["phase"] = label
            fh.write(json.dumps(row) + "\n")
            n += 1
            time.sleep(1.0 / hz)
    finally:
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
    print(f"  {n} samples", flush=True)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--phases", default="",
                    help="comma list of phase labels to run (default: all)")
    args = ap.parse_args()
    wanted = [p.strip() for p in args.phases.split(",") if p.strip()]
    total = 0
    with open(args.out, "w") as fh:
        fh.write(json.dumps({"info": "vermeer transient run",
                             "phases": [p[0] for p in PHASES]}) + "\n")
        for label, seconds, cmd in PHASES:
            if wanted and label not in wanted:
                continue
            total += run_phase(label, seconds, cmd, args.hz, fh)
    print(f"wrote {total} samples to {args.out}")


if __name__ == "__main__":
    main()

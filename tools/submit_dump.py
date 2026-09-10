#!/usr/bin/env python3
"""Build a standardized PM-table dump bundle for community validation.

Run on the contributor's machine (needs the `ryzen_smu` driver loaded):

  sudo python3 tools/submit_dump.py --out ./my_5600x
  sudo python3 tools/submit_dump.py --out ./my_5600x --with-load

Captures an idle snapshot always, plus one all-core snapshot with
`--with-load` (skipped with a note when stress-ng is unavailable).
Attach the resulting directory to a GitHub issue.

Read-only towards the firmware: the only sysfs access in this tool is
reading pm_table / pm_table_version / pm_table_size and informational
files (cpuinfo, kernel release, driver version strings).  The only writes
are the bundle files under --out.  No SMU command is ever sent.

Privacy: the bundle contains the CPU model string, core/thread counts, the
logical-CPU topology, kernel release, driver/SMU version strings and the raw
PM-table snapshots.  It deliberately excludes hostnames, dmesg, serial
numbers, MAC/IP addresses and anything under /sys/kernel/ryzen_smu_drv
other than the read-only telemetry files listed above.
"""

import argparse
import datetime
import json
import os
import struct
import subprocess
import sys
import time

SYSFS = "/sys/kernel/ryzen_smu_drv"


def read_bytes(path, n):
    with open(path, "rb") as f:
        data = f.read(n)
    if len(data) != n:
        raise RuntimeError(f"short read on {path}: {len(data)}/{n}")
    return data


def read_text(path):
    with open(path, "r") as f:
        return f.read().strip()


def pm_meta():
    version = struct.unpack("<I", read_bytes(f"{SYSFS}/pm_table_version", 4))[0]
    size_raw = read_bytes(f"{SYSFS}/pm_table_size", 8)
    size = struct.unpack("<I", size_raw[:4])[0]
    if size % 4:
        raise RuntimeError(f"PM table size {size} is not float32-aligned")
    return version, size


def cpu_model():
    for line in open("/proc/cpuinfo", encoding="utf-8"):
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def topology():
    """{logical_cpu: core_id} for online CPUs, via sysfs (no lscpu needed)."""
    topo = {}
    base = "/sys/devices/system/cpu"
    for entry in sorted(os.listdir(base)):
        if not entry.startswith("cpu") or not entry[3:].isdigit():
            continue
        try:
            with open(os.path.join(base, entry, "online")) as f:
                if f.read().strip() == "0":
                    continue
        except OSError:
            pass  # cpu0 has no online file; it is always online
        try:
            with open(os.path.join(base, entry, "topology", "core_id")) as f:
                topo[int(entry[3:])] = int(f.read().strip())
        except OSError:
            pass
    return topo


def physical_cores(topo):
    return len(set(topo.values()))


def driver_info():
    info = {}
    for name in ("drv_version", "version", "mp1_if_version", "codename"):
        try:
            info[name] = read_text(f"{SYSFS}/{name}")
        except OSError as e:
            info[name] = f"unreadable ({e})"
    return info


def capture_pm(size, settle=3):
    time.sleep(settle)
    return read_bytes(f"{SYSFS}/pm_table", size)


def run_load(seconds):
    """Start a brief all-core userspace load; return Popen or None."""
    ncpu = os.cpu_count() or 1
    cmds = [
        ["stress-ng", "--cpu", str(ncpu), "--cpu-method", "matrixprod",
         "--timeout", f"{seconds + 5}s", "--metrics-brief"],
    ]
    for cmd in cmds:
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="bundle directory to create")
    ap.add_argument("--with-load", action="store_true",
                    help="also capture one all-core snapshot (~15 s settle)")
    args = ap.parse_args()

    version, size = pm_meta()
    model = cpu_model()
    topo = topology()
    if not topo:
        sys.exit("no online CPUs found in sysfs topology")
    drv = driver_info()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    outdir = os.path.abspath(args.out)
    os.makedirs(outdir, exist_ok=False)

    meta = {
        "tool": "gnr-smu submit_dump.py",
        "timestamp_utc": stamp,
        "cpu_model": model,
        "threads": len(topo),
        "physical_cores": physical_cores(topo),
        "topology_logical_to_core_id": {str(k): v for k, v in sorted(topo.items())},
        "kernel_release": os.uname().release,
        "ryzen_smu_drv_version": drv.get("drv_version"),
        "smu_fw_version": drv.get("version"),
        "mp1_if_version": drv.get("mp1_if_version"),
        "codename_raw": drv.get("codename"),
        "pm_table_version": f"0x{version:x}",
        "pm_table_size": size,
        "pm_floats": size // 4,
        "snapshots": ["pm_table_idle.bin"],
    }

    worker = None
    try:
        with open(os.path.join(outdir, "pm_table_idle.bin"), "wb") as f:
            f.write(capture_pm(size))
        if args.with_load:
            worker = run_load(seconds=15)
            if worker is None:
                meta["load_note"] = ("stress-ng not found; load snapshot "
                                     "skipped (idle only)")
                print("stress-ng not found; capturing idle only")
            else:
                with open(os.path.join(outdir, "pm_table_load.bin"), "wb") as f:
                    f.write(capture_pm(size, settle=15))
                meta["snapshots"].append("pm_table_load.bin")
    finally:
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()

    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"bundle written to {outdir}: "
          f"{model}, PM table {meta['pm_table_version']} "
          f"({size} bytes), snapshots {meta['snapshots']}")


if __name__ == "__main__":
    main()

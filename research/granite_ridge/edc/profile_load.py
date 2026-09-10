#!/usr/bin/env python3
"""Phases 1b + 2 — profile candidate fields across load levels.

Two questions, one sweep (each load point costs ~50 s, so they share it):

1b. EDC_VALUE is absent from the table. Is it *derivable*? Zen's EDC is peak
    current across the VRM, and the table does carry per-core IDD at d[301-308].
    If sum(IDD) tracks the TDC value at a constant ratio, the GUI can compute an
    EDC reading instead of showing a limit with no value under it.

2.  d[212], d[397-404] and d[453] are confirmed *not* accumulators (they plateau
    under steady load). Test whether they are proportional to instantaneous power:
    a constant ratio against d[20] Package Power across four load levels would
    identify the unit.

Run: python3 research/profile_load.py
"""

import statistics
import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
N = 457
LEVELS = [0, 1, 4, 8, 16]


def table():
    with open(PM, "rb") as f:
        return struct.unpack(f"<{N}f", f.read(N * 4))


def med(samples, fn):
    return statistics.median([fn(v) for v in samples])


def measure(threads):
    if threads == 0:
        print("  idle (50 s settle) ...")
        time.sleep(50)
        p = None
    else:
        print(f"  stress-ng --matrix {threads} (25 s settle) ...")
        p = subprocess.Popen(["stress-ng", "--matrix", str(threads), "--timeout", "45"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(25)
    s = [table() for _ in range(20) if not time.sleep(0.25)]
    if p:
        p.wait()
        time.sleep(30)  # cool down so the next level starts from a comparable place
    return s


rows = []
for n in LEVELS:
    s = measure(n)
    rows.append({
        "n": n,
        "pkg_w": med(s, lambda v: v[20]),
        "core_w": med(s, lambda v: v[17]),
        "tdc": med(s, lambda v: v[9]),
        "idd": med(s, lambda v: sum(v[301:309])),
        "soc_a": med(s, lambda v: v[57]),
        "d212": med(s, lambda v: v[212]),
        "d397": med(s, lambda v: sum(v[397:405])),
        "d453": med(s, lambda v: v[453]),
        "tctl": med(s, lambda v: v[11]),
    })

print(f"\n{'thr':>4} {'pkgW':>8} {'coreW':>8} {'TDC_A':>8} {'sumIDD':>8} "
      f"{'IDD/TDC':>8} {'Tctl':>6} {'d212':>9} {'d212/W':>8} {'sum397':>9} "
      f"{'d453':>8} {'453/W':>7}")
for r in rows:
    print(f"{r['n']:>4} {r['pkg_w']:>8.2f} {r['core_w']:>8.2f} {r['tdc']:>8.2f} "
          f"{r['idd']:>8.2f} {r['idd'] / max(r['tdc'], 1e-3):>8.3f} {r['tctl']:>6.1f} "
          f"{r['d212']:>9.0f} {r['d212'] / max(r['pkg_w'], 1e-3):>8.1f} "
          f"{r['d397']:>9.0f} {r['d453']:>8.0f} "
          f"{r['d453'] / max(r['pkg_w'], 1e-3):>7.1f}")


def verdict(name, ratios, tol=0.15):
    """A constant ratio across load levels means the two fields carry the same
    quantity in different units. A drifting ratio means they don't."""
    lo, hi = min(ratios), max(ratios)
    spread = (hi - lo) / max(statistics.mean(ratios), 1e-9)
    ok = spread < tol
    print(f"  {'CONSTANT' if ok else 'drifts  '} {name}: "
          f"{lo:.3f}..{hi:.3f} (spread {spread:.1%})")
    return ok


print("\n== ratios across load levels (idle excluded — division by ~0) ==")
loaded = [r for r in rows if r["n"] > 0]
verdict("sum(IDD) / TDC value", [r["idd"] / r["tdc"] for r in loaded])
verdict("d[212] / package W", [r["d212"] / r["pkg_w"] for r in loaded])
verdict("sum d[397-404] / core W", [r["d397"] / r["core_w"] for r in loaded])
verdict("d[453] / package W", [r["d453"] / r["pkg_w"] for r in loaded])
verdict("d[212] / sum d[397-404]", [r["d212"] / r["d397"] for r in loaded])

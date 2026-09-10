#!/usr/bin/env python3
"""Phase 3 — classify the 90 float indices that have no row in PM_TABLE_MAP.md.

Not an attempt to decode them. The point is coverage honesty: every index gets a
row, even if that row says "unknown". A field classified as a permanent zero or a
constant is cheap to document and removes it from the search space; only the
dynamic ones are worth chasing.

Classes:
  ZERO      reads 0.0 at every load level
  CONST     one distinct value across all load levels
  DYNAMIC   moves with load — the only ones worth decoding

For DYNAMIC fields, also report the correlation against the known axes (package
power, TDC current, Tctl, core frequency, C6 residency) so the row can at least
name the domain.

Emits ready-to-paste markdown rows on stdout.

Run: python3 research/classify_unknown.py
"""

import re
import statistics
import struct
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "PM_TABLE_MAP.md"
PM = "/sys/kernel/ryzen_smu_drv/pm_table"
N = 457

ROW = re.compile(r"^\|\s*0x[0-9A-Fa-f]+(?:-0x[0-9A-Fa-f]+)?\s*\|\s*([0-9]+(?:-[0-9]+)?)\s*\|")

AXES = {
    "pkg_W": 20, "TDC_A": 9, "Tctl": 11, "coreGHz": 451, "C6%": 349,
}


def documented():
    out = set()
    for line in MAP.read_text().splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        idx = m.group(1)
        if "-" in idx:
            a, b = idx.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(idx))
    return out


def table():
    with open(PM, "rb") as f:
        return struct.unpack(f"<{N}f", f.read(N * 4))


def measure(threads):
    if threads == 0:
        time.sleep(50)
        p = None
    else:
        p = subprocess.Popen(["stress-ng", "--matrix", str(threads), "--timeout", "45"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(25)
    s = [table() for _ in range(20) if not time.sleep(0.25)]
    if p:
        p.wait()
        time.sleep(30)
    return s


def pearson(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


unknown = sorted(set(range(N)) - documented())
print(f"{len(unknown)} undocumented indices\n")

levels = [0, 1, 8, 16]
snaps = []
for n in levels:
    print(f"  sampling {n} threads ...")
    s = measure(n)
    snaps.append([statistics.median([v[i] for v in s]) for i in range(N)])

print()
zero, const, dyn = [], [], []
for i in unknown:
    vals = [snap[i] for snap in snaps]
    if all(abs(v) < 1e-9 for v in vals):
        zero.append(i)
    elif max(vals) - min(vals) <= max(abs(statistics.mean(vals)) * 0.01, 1e-6):
        const.append((i, vals[0]))
    else:
        dyn.append((i, vals))

print(f"ZERO    {len(zero):>3}")
print(f"CONST   {len(const):>3}")
print(f"DYNAMIC {len(dyn):>3}\n")


def ranges(idxs):
    """Collapse a sorted index list into contiguous runs, for compact rows."""
    out, start = [], None
    for k, i in enumerate(idxs):
        if start is None:
            start = i
        if k + 1 == len(idxs) or idxs[k + 1] != i + 1:
            out.append((start, i))
            start = None
    return out


print("== paste-ready rows: permanent zeros ==")
for a, b in ranges(zero):
    off = f"0x{a * 4:03X}" if a == b else f"0x{a * 4:03X}-0x{b * 4:03X}"
    idx = f"{a}" if a == b else f"{a}-{b}"
    print(f"| {off} | {idx} | 0 | Y | Reserved — reads 0 at idle, 1, 8 and 16 "
          f"threads | HIGH |")

print("\n== paste-ready rows: constants ==")
for i, v in const:
    print(f"| 0x{i * 4:03X} | {i} | {v:g} | Y | Unidentified constant — unchanged "
          f"across idle, 1, 8 and 16 threads | LOW |")

print("\n== dynamic fields: correlation against known axes ==")
print(f"{'idx':>4} {'off':>6} " + " ".join(f"{n:>9}" for n in levels) +
      "   best axis (Pearson)")
for i, vals in dyn:
    best, bestr = None, 0.0
    for name, j in AXES.items():
        r = pearson(vals, [snap[j] for snap in snaps])
        if abs(r) > abs(bestr):
            best, bestr = name, r
    print(f"{i:>4} 0x{i * 4:04X} " + " ".join(f"{v:>9.2f}" for v in vals) +
          f"   {best} r={bestr:+.3f}")

#!/usr/bin/env python3
"""Phase 1 — find EDC_VALUE.

d[63] holds the EDC *limit* (180 A) but no companion live-value float has been
identified. The earlier sweep used `stress-ng --cpu`, an integer load, which does
not pull enough current to separate an EDC field from a plain power field.

Three load points — idle, integer, AVX-512 — and score every float against the
signature EDC_VALUE must have:
  - low at idle
  - rises with load
  - rises MORE under the heavy load than the light one (that is the whole point of
    a current limit: some work draws current that other work does not)

Load choice matters and is not obvious. Benchmarked by peak TDC value:
  --matrix 16      103.4 A / 131.6 W  <- heaviest, used as HEAVY
  --cpu-method float128  91.8 A / 116.8 W
  --vecfp 16        89.9 A / 105.9 W  <- AVX-512 but LIGHTER than plain --cpu
  --cpu 16          87.7 A / 112.4 W  <- used as LIGHT
  --vecshuf 16      64.7 A /  82.6 W
"AVX-512" alone is not the answer: --vecfp pulls less package power than the
integer path. --matrix is what actually loads the current rails.
  - never exceeds the 180 A limit

Run: python3 research/hunt_edc.py
"""

import statistics
import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
N = 457
EDC_LIMIT = 180.0

# Already identified — a hit here is a known field, not a discovery.
KNOWN = {
    0: "STAPM limit", 1: "STAPM value", 2: "PPT limit", 3: "PPT value",
    8: "TDC limit", 9: "TDC value", 10: "THM limit", 11: "Tctl",
    17: "Core power", 20: "Package power", 21: "SoC power", 62: "SoC power limit",
    63: "EDC limit", 212: "pkg power credit", 270: "Hotspot", 453: "power credit",
}


def table():
    with open(PM, "rb") as f:
        return struct.unpack(f"<{N}f", f.read(N * 4))


def sample(seconds, n=30):
    """Median over a window, plus the per-field max seen (EDC is a peak metric,
    so the max matters as much as the median)."""
    cols = [[] for _ in range(N)]
    deadline = time.time() + seconds
    while time.time() < deadline and len(cols[0]) < n:
        for i, x in enumerate(table()):
            cols[i].append(x)
        time.sleep(seconds / n)
    return ([statistics.median(c) for c in cols], [max(c) for c in cols])


def run(args, settle, window):
    p = subprocess.Popen(["stress-ng", *args, "--timeout", str(settle + window + 5)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(settle)
    out = sample(window)
    p.wait()
    return out


print("idle (45 s settle) ...")
time.sleep(45)
idle, idle_max = sample(8)

print("light load: stress-ng --cpu 16 ...")
intg, intg_max = run(["--cpu", "16"], 25, 12)

print("cooldown 45 s ...")
time.sleep(45)

print("heavy load: stress-ng --matrix 16 ...")
avx, avx_max = run(["--matrix", "16"], 25, 12)

print(f"\nTctl idle {idle[11]:.1f} -> int {intg[11]:.1f} -> avx {avx[11]:.1f} C")
print(f"Pkg power {idle[20]:.1f} -> {intg[20]:.1f} -> {avx[20]:.1f} W")
print(f"TDC value {idle[9]:.1f} -> {intg[9]:.1f} -> {avx[9]:.1f} A "
      f"(limit {idle[8]:.0f})\n")

cands = []
for i in range(N):
    lo, hi_i, hi_a = idle[i], intg[i], avx[i]
    peak = avx_max[i]
    if not (0 <= lo < 30):                       # must start low
        continue
    if hi_a <= lo + 5:                           # must rise with load
        continue
    if peak > EDC_LIMIT:                         # must respect its own limit
        continue
    if hi_a <= hi_i:                             # AVX must beat integer
        continue
    # how much harder AVX pushes it than integer does — EDC should be the field
    # where this ratio is largest
    heavy_bias = (hi_a - lo) / max(hi_i - lo, 1e-3)
    cands.append((heavy_bias, i, lo, hi_i, hi_a, peak))

cands.sort(reverse=True)
print("== Candidates: low at idle, rise under load, heavy > light, peak <= 180 ==")
print(f"{'idx':>4} {'off':>6} {'idle':>8} {'int':>8} {'heavy':>8} {'peak':>8} "
      f"{'ratio':>8}  note")
for bias, i, lo, hi_i, hi_a, peak in cands[:25]:
    note = KNOWN.get(i, "")
    print(f"{i:>4} 0x{i * 4:04X} {lo:>8.2f} {hi_i:>8.2f} {hi_a:>8.2f} {peak:>8.2f} "
          f"{bias:>8.2f}  {note}")

print(f"\n{len(cands)} candidates, {sum(1 for c in cands if c[1] not in KNOWN)} unknown")

# A real EDC_VALUE should also exceed TDC_VALUE — EDC is the peak-current limit and
# is always the higher of the two on Zen.
print("\n== of those, the ones reading above TDC value under heavy load ==")
hits = [c for c in cands if c[4] > avx[9] and c[1] not in KNOWN]
if not hits:
    print(f"  none. No unknown field exceeds TDC value ({avx[9]:.1f} A) under the heaviest load available.")
else:
    for bias, i, lo, hi_i, hi_a, peak in hits:
        print(f"  d[{i}] (0x{i * 4:04X}) {lo:.2f} -> {hi_a:.2f} (peak {peak:.2f})")

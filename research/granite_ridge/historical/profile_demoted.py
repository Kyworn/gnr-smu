#!/usr/bin/env python3
"""Phase 4 — find the domain of the offsets that were demoted but not re-identified.

These fields are all confirmed *not* to be what the map used to claim. This does not
try to name them outright; it asks a narrower and answerable question: which known
axis do they actually live on?

Method: sample a time series across several load types and levels, then regress each
target against every known axis over the *pooled* series. Level medians alone give
only 4-5 points and let anything monotonic look correlated; the within-run variation
is what separates "tracks power" from "tracks temperature", since power moves fast
and temperature lags.

Reported per target: best axis, r^2, slope, and whether a linear fit actually holds
(r^2 > 0.9) or the field merely trends in the same direction (0.5-0.9) or neither.

Run: python3 research/profile_demoted.py
"""

import statistics
import struct
import subprocess
import time
from pathlib import Path

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
N = 457

# The open questions, with what each is already known NOT to be.
TARGETS = {
    64:  "0x100 quantized utilization (not Tctl)",
    210: "0x348 saturates at 100 (not a temperature)",
    220: "0x370 ~200, drifts (not Min-DPM 400 MHz)",
    278: "0x458 (not PPT current value)",
    298: "0x4A8 slow thermal, domain unconfirmed",
    299: "0x4AC tracks d[298] at +9.39",
    448: "0x700 filtered thermal (not core temp average)",
    449: "0x704 filtered thermal (not core temp min)",
    452: "0x710 countdown/credit",
    17:  "0x044 (not core power aggregate)",
    212: "0x350 saturates from one busy thread",
    453: "0x714 near-power-proportional",
    16:  "0x040 energy budget countdown",
}

# Known-good reference axes, each cross-validated against a system sensor or pinned
# by a stock spec.
AXES = {
    "pkg_W":    lambda v: v[20],
    "TDC_A":    lambda v: v[9],
    "PPT_W":    lambda v: v[3],
    "Tctl_C":   lambda v: v[11],
    "hotspot":  lambda v: v[270],
    "coreGHz":  lambda v: v[451],
    "C6_pct":   lambda v: statistics.mean(v[349:357]),
    "C0_frac":  lambda v: statistics.mean(v[413:421]),
    "FIT_pct":  lambda v: statistics.mean(v[341:349]),
    "corePwr":  lambda v: sum(v[333:341]),
    "IDD_A":    lambda v: sum(v[301:309]),
    "Vcore_V":  lambda v: v[19],
}

# Load points chosen to decorrelate the axes from each other: single-thread keeps
# frequency high while power stays low, --vecshuf is low-power-high-activity, and
# the idle tail after a load separates temperature (lags) from power (drops at once).
PHASES = [
    ("idle",        None,                    40),
    ("1 thread",    ["--matrix", "1"],       35),
    ("4 matrix",    ["--matrix", "4"],       35),
    ("16 matrix",   ["--matrix", "16"],      35),
    ("16 vecshuf",  ["--vecshuf", "16"],     35),
    ("16 cpu",      ["--cpu", "16"],         35),
    ("cooldown",    None,                    40),
]


def table():
    with open(PM, "rb") as f:
        return struct.unpack(f"<{N}f", f.read(N * 4))


def collect(args, seconds):
    p = None
    if args:
        # timeout must outlast settle + window, or the load ends mid-recording and the
        # tail of the phase is silently idle — which is what made the first run's
        # "cooldown" phase useless for timing the load-release transient.
        p = subprocess.Popen(["stress-ng", *args, "--timeout", str(seconds + 20)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)  # let the load ramp before recording
    out = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        out.append(table())
        time.sleep(0.4)
    if p:
        p.wait()
    return out


def fit(xs, ys):
    """Least squares y = a*x + b. Returns (r2, a, b)."""
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0.0, 0.0, my
    a = sxy / sxx
    return (sxy ** 2) / (sxx * syy), a, my - a * mx


# Cache the sweep: it costs ~4.5 min of wall clock and the analysis below gets
# revisited far more often than the measurement needs redoing. Delete the file to
# force a fresh run.
CACHE = Path(__file__).resolve().parent / "demoted_series.bin"
if CACHE.exists():
    raw = CACHE.read_bytes()
    series = [struct.unpack(f"<{N}f", raw[k:k + N * 4])
              for k in range(0, len(raw), N * 4)]
    print(f"reusing cached sweep ({len(series)} samples) — delete "
          f"{CACHE.name} to re-measure")
else:
    series = []
    for name, args, secs in PHASES:
        print(f"  {name} ...")
        series.extend(collect(args, secs))
    CACHE.write_bytes(b"".join(struct.pack(f"<{N}f", *v) for v in series))
print(f"\n{len(series)} pooled samples\n")

axis_vals = {k: [f(v) for v in series] for k, f in AXES.items()}
print("axis ranges over the pooled series:")
for k, vs in axis_vals.items():
    print(f"  {k:>8}: {min(vs):9.2f} .. {max(vs):9.2f}")

print(f"\n{'idx':>4} {'range':>19}  {'best axis':>9} {'r2':>6} {'slope':>10}  verdict")
for i, note in TARGETS.items():
    ys = [v[i] for v in series]
    ranked = sorted(((fit(axis_vals[k], ys), k) for k in AXES),
                    key=lambda t: -t[0][0])
    (r2, a, b), k = ranked[0]
    (r2b, _, _), kb = ranked[1]
    if r2 > 0.9:
        # A single high r2 means little when every axis rises together under load.
        # Require a clear margin over the runner-up before claiming an axis.
        verdict = (f"LINEAR in {k}" if r2 - r2b > 0.03
                   else f"LINEAR but {k}/{kb} indistinguishable ({r2:.3f}/{r2b:.3f})")
    elif r2 > 0.5:
        verdict = f"trends with {k}, not linear"
    else:
        verdict = "no known axis explains it"
    print(f"{i:>4} {min(ys):8.2f}..{max(ys):-9.2f}  {k:>9} {r2:6.3f} "
          f"y={a:.4g}*x{b:+.4g}  {verdict}")
    print(f"     {note}")
    print("     ranking: " + "  ".join(f"{kk}={rr[0]:.3f}" for rr, kk in ranked[:5]))

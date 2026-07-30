#!/usr/bin/env python3
"""Phase 4b — separate the demoted offsets by their response time, not their level.

Phase 4 regressed each target against every known axis and got nowhere useful: under
load every axis rises together, so r^2 = 0.97 against TDC current is also r^2 = 0.97
against package power and Tctl. Level correlation cannot tell them apart.

The load-release transient can. When the load stops, power and current collapse in
one or two samples; die temperature decays over tens of seconds; a filtered or
accumulated quantity decays somewhere in between with its own constant. So the decay
half-life *is* the domain signature, and it is independent of scale and offset.

Phase 4's own cooldown tail could not be used for this: stress-ng's --timeout expired
before the sampling window closed, so the "cooldown" samples were already idle and
the transition itself was never recorded. Here the load is killed explicitly, at a
known sample index, with the clock still running.

Run: python3 research/transient_demoted.py
"""

import statistics
import struct
import subprocess
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
N = 457
DT = 0.2          # sample period; the power rails settle in ~1 s, so this resolves them
LOAD_S = 45       # long enough for the die to reach thermal steady state
POST_S = 75       # long enough for Tctl to come most of the way back down

TARGETS = {
    64: "0x100", 210: "0x348", 220: "0x370", 278: "0x458", 298: "0x4A8",
    299: "0x4AC", 448: "0x700", 449: "0x704", 452: "0x710", 17: "0x044",
    212: "0x350", 453: "0x714", 16: "0x040",
}

# Two reference groups with known, very different response times. Anything that
# decays like the first group is a power/current-domain field; anything that decays
# like the second is thermal.
FAST = {"pkg_W": 20, "TDC_A": 9, "PPT_W": 3}
SLOW = {"Tctl": 11, "hotspot": 270}


def table():
    with open(PM, "rb") as f:
        return struct.unpack(f"<{N}f", f.read(N * 4))


def sample(seconds, mark=None):
    out = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        out.append(table())
        time.sleep(DT)
    return out


print(f"load: stress-ng --matrix 16 for {LOAD_S} s ...")
p = subprocess.Popen(["stress-ng", "--matrix", "16", "--timeout", str(LOAD_S + 120)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(LOAD_S - 8)
hot = sample(8)                      # steady-state hot reference
p.terminate()
p.wait()
print(f"released — recording {POST_S} s of decay ...")
post = sample(POST_S)
cold = post[-25:]                    # settled reference at the end of the window

print(f"\n{len(hot)} hot samples, {len(post)} decay samples at {DT} s\n")


def tau(i):
    """Time for the field to fall (or rise) 63 % of the way from its hot value to its
    settled value. Reported as None when the total swing is too small to time."""
    a = statistics.median([v[i] for v in hot])
    b = statistics.median([v[i] for v in cold])
    swing = b - a
    noise = statistics.pstdev([v[i] for v in cold]) or 1e-9
    if abs(swing) < max(3 * noise, 1e-6):
        return a, b, None
    target = a + swing * 0.632
    for k, v in enumerate(post):
        y = v[i]
        if (swing < 0 and y <= target) or (swing > 0 and y >= target):
            return a, b, k * DT
    return a, b, float("inf")


print(f"{'name':>10} {'hot':>10} {'settled':>10} {'tau63':>8}")
print("-- fast references (power / current domain) --")
for n, i in FAST.items():
    a, b, t = tau(i)
    print(f"{n:>10} {a:10.2f} {b:10.2f} {t if t is None else f'{t:8.1f}':>8}")
print("-- slow references (thermal domain) --")
for n, i in SLOW.items():
    a, b, t = tau(i)
    print(f"{n:>10} {a:10.2f} {b:10.2f} {t if t is None else f'{t:8.1f}':>8}")

print("\n-- targets --")
for i, off in TARGETS.items():
    a, b, t = tau(i)
    ts = "flat" if t is None else f"{t:.1f}"
    print(f"d[{i:>3}] {off:>6} {a:10.2f} {b:10.2f} {ts:>8}")

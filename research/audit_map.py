#!/usr/bin/env python3
"""Audit PM_TABLE_MAP.md against live hardware. Parses the map itself, so every
claim it makes is tested — no hand-picked subset.

Tests:
  STATIC   every row marked "Static: Y" must not move between idle and load
  ZERO     every row documented as Reserved/0 must actually read 0
  MIRROR   the "Perfect Mirrors" pairs must hold
  SUM      d[186] + d[187] == 100
  XVAL     cross-validation vs k10temp / amdgpu / cpufreq / dmidecode
  COUNT    the summary statistics (457 floats, static counts)

Run: python3 research/audit_map.py
Exit code 1 if any claim fails.
"""

import re
import struct
import subprocess
import time
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "PM_TABLE_MAP.md"
PM = "/sys/kernel/ryzen_smu_drv/pm_table"
K10 = "/sys/class/hwmon/hwmon3"
AMDGPU = "/sys/class/hwmon/hwmon7"

fails, warns = [], []


def fail(tag, msg):
    fails.append(f"[{tag}] {msg}")
    print(f"  FAIL [{tag}] {msg}")


def warn(tag, msg):
    warns.append(f"[{tag}] {msg}")
    print(f"  WARN [{tag}] {msg}")


def rd(p):
    return open(p).read().strip()


def avg_table(n=25, gap=0.12):
    """Median snapshot, plus the k10temp median over the *same* window.

    Median, not mean: the sysfs read occasionally returns a garbage sample, and a
    mean smears that into every field. k10temp is sampled inside the same loop
    because a single reading taken before or after the window is a different
    moment on a thermal transient, which reads as a mismatch that isn't one.
    """
    cols = [[] for _ in range(457)]
    k10 = []
    for _ in range(n):
        with open(PM, "rb") as f:
            v = struct.unpack("<457f", f.read(1828))
        for i, x in enumerate(v):
            cols[i].append(x)
        k10.append(float(rd(f"{K10}/temp1_input")) / 1000)
        time.sleep(gap)
    return [statistics.median(c) for c in cols], statistics.median(k10)


def raw_table():
    with open(PM, "rb") as f:
        return struct.unpack("<457f", f.read(1828))


# ---------------------------------------------------------------- parse the map
ROW = re.compile(
    r"^\|\s*(0x[0-9A-Fa-f]+(?:-0x[0-9A-Fa-f]+)?)\s*\|\s*([0-9]+(?:-[0-9]+)?)\s*\|"
    r"([^|]*)\|\s*([YN])\s*\|([^|]*)\|"
)


def parse_rows():
    """-> list of (idx_list, typical_text, static_flag, meaning_text)"""
    out = []
    for line in MAP.read_text().splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        idx_s, typical, static, meaning = m.group(2), m.group(3), m.group(4), m.group(5)
        if "-" in idx_s:
            a, b = idx_s.split("-")
            idxs = list(range(int(a), int(b) + 1))
        else:
            idxs = [int(idx_s)]
        out.append((idxs, typical.strip(), static, meaning.strip()))
    return out


rows = parse_rows()
print(f"Parsed {len(rows)} documented rows from PM_TABLE_MAP.md "
      f"covering {len({i for r in rows for i in r[0]})} float indices\n")

# ---------------------------------------------------------------- measure
def wait_cool(max_wait=420, window=30, tol=0.5, max_load=1.0):
    """Block until the machine is genuinely idle: Tctl stable AND load average low.

    Two conditions, because either alone is not enough. A fixed sleep is not enough
    (the die sheds heat for minutes after a stress run). Temperature stability alone
    is not enough either — during a transient, d[11] and k10temp disagree by up to
    8 C simply because they respond at different rates, which reads as a mismatch
    that is really just "you measured during cooldown".
    """
    deadline = time.time() + max_wait
    prev = float(rd(f"{K10}/temp1_input")) / 1000
    while time.time() < deadline:
        time.sleep(window)
        cur = float(rd(f"{K10}/temp1_input")) / 1000
        load1 = float(rd("/proc/loadavg").split()[0].replace(",", "."))
        if abs(prev - cur) < tol and load1 < max_load:
            return cur, load1
        prev = cur
    return prev, load1


print("Sampling IDLE (waiting for Tctl to settle) ...")
cool_t, cool_l = wait_cool()
print(f"  settled at {cool_t:.1f} C, load average {cool_l:.2f}")
# amdgpu rails move with load, so they must be read in the same window as the PM
# samples they are compared against — not once at the end of the script.
idle_vddgfx = float(rd(f"{AMDGPU}/in0_input")) / 1000
idle_vddnb = float(rd(f"{AMDGPU}/in1_input")) / 1000
idle_sclk = float(rd(f"{AMDGPU}/freq1_input")) / 1e6
idle, idle_k10 = avg_table()
idle_raws = [raw_table() for _ in range(5)]

print("Sampling LOAD (stress-ng --cpu 16, 45 s settle) ...")
p = subprocess.Popen(
    ["stress-ng", "--cpu", "16", "--timeout", "75"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(45)
load, load_k10 = avg_table()
p.wait()
print(f"  Tctl {idle_k10:.1f} -> {load_k10:.1f} C\n")

# ---------------------------------------------------------------- STATIC claims
print("== STATIC: rows marked 'Static: Y' must not move under load ==")
static_checked = 0
for idxs, typical, static, meaning in rows:
    if static != "Y":
        continue
    for i in idxs:
        static_checked += 1
        d = abs(load[i] - idle[i])
        rel = d / max(abs(idle[i]), 1e-6)
        if d > 0.05 and rel > 0.01:
            fail("STATIC", f"d[{i}] (0x{i * 4:03X}) '{meaning[:44]}' moved "
                           f"{idle[i]:.3f} -> {load[i]:.3f}")
print(f"  checked {static_checked} static-marked indices\n")

# ---------------------------------------------------------------- ZERO claims
print("== ZERO: rows documented Reserved / typical 0 must read 0 ==")
zero_checked = 0
for idxs, typical, static, meaning in rows:
    if typical.strip() != "0" and "Reserved" not in meaning:
        continue
    for i in idxs:
        zero_checked += 1
        # 1e-4, not 1e-6: several "reserved" fields rest at a ~2e-05 floor rather
        # than a true zero, and reporting those as "is not zero: idle=0.0000" is
        # noise that hides real failures.
        if abs(idle[i]) > 1e-4 or abs(load[i]) > 1e-4:
            fail("ZERO", f"d[{i}] (0x{i * 4:03X}) '{meaning[:44]}' is not zero: "
                         f"idle={idle[i]:.6g} load={load[i]:.6g}")
print(f"  checked {zero_checked} zero-marked indices\n")

# ---------------------------------------------------------------- MIRRORS / SUM
print("== MIRROR / SUM: documented couplings ==")
# Only pairs documented as *exact* mirrors. Compared inside one snapshot, never
# across medians — two near-copies with different averaging windows would differ
# for reasons that have nothing to do with the claim being tested.
for a, b in [(20, 51), (21, 56), (58, 59), (43, 44), (27, 274)]:
    for v in idle_raws:
        if v[a] != v[b]:
            fail("MIRROR", f"d[{a}] != d[{b}] in a single snapshot: "
                           f"{v[a]:.5f} vs {v[b]:.5f}")
            break
# Documented as near-copies, NOT identical: assert they really are distinct, so the
# doc does not silently drift back to claiming a perfect mirror.
for a, b in [(3, 26), (3, 277), (9, 50)]:
    if all(v[a] == v[b] for v in idle_raws):
        warn("MIRROR", f"d[{a}] == d[{b}] in every snapshot — documented as a "
                       "near-copy with a non-zero delta")
for tag, t in (("idle", idle), ("load", load)):
    s = t[186] + t[187]
    if abs(s - 100.0) > 0.01:
        fail("SUM", f"d[186]+d[187] = {s:.4f} at {tag}, documented 100.000")
print()

# ---------------------------------------------------------------- XVAL
print("== XVAL: cross-validation against system sensors ==")


def xval(tag, name, got, want, tol, unit=""):
    ok = abs(got - want) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: PM={got:.3f}{unit} "
          f"sys={want:.3f}{unit} (tol {tol}{unit})")
    if not ok:
        fail(tag, f"{name}: PM={got:.3f} vs system={want:.3f}")


# Vcore and vddgfx are sampled by different hardware at different instants and both
# swing ~200 mV at idle, so only their means over a window are comparable.
pm_v, sys_v = [], []
for _ in range(40):
    pm_v.append(raw_table()[49])
    sys_v.append(float(rd(f"{AMDGPU}/in0_input")) / 1000)
    time.sleep(0.15)
xval("XVAL", "d[49] Vcore P1 vs amdgpu vddgfx (40-sample means)",
     statistics.mean(pm_v), statistics.mean(sys_v), 0.02, "V")
xval("XVAL", "d[53] VDDCR_SoC vs amdgpu vddnb", idle[53], idle_vddnb, 0.02, "V")
xval("XVAL", "d[58] VDDIO_MEM vs DDR5 nominal", idle[58], 1.1, 0.05, "V")
xval("XVAL", "d[108] iGPU sclk vs amdgpu freq1", idle[108], idle_sclk, 60, "MHz")
xval("XVAL", "d[11] Tctl vs k10temp (idle)", idle[11], idle_k10, 3.0, "C")
xval("XVAL", "d[11] Tctl vs k10temp (load)", load[11], load_k10, 3.0, "C")

core_t = [load[317 + i] for i in range(8)]
xval("XVAL", "d[317-324] core temp max vs k10temp Tctl (load)",
     max(core_t), load_k10, 8.0, "C")

# per-core frequency vs cpufreq
cur = []
for c in range(16):
    try:
        cur.append(float(rd(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq")) / 1e6)
    except OSError:
        pass
if cur:
    pm_f = [load[325 + i] for i in range(8)]
    xval("XVAL", "d[325-332] core freq max vs cpufreq max (load)",
         max(pm_f), max(cur), 0.6, "GHz")

maxf = float(rd("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")) / 1e6
xval("XVAL", "d[373-380] boost limit vs cpuinfo_max_freq",
     max(load[373 + i] for i in range(8)), maxf, 0.15, "GHz")

# C6 residency should be high at idle, collapse under load
c6_idle = statistics.mean(idle[349 + i] for i in range(8))
c6_load = statistics.mean(load[349 + i] for i in range(8))
print(f"  {'ok  ' if c6_idle > 50 and c6_load < 10 else 'FAIL'} "
      f"d[349-356] C6 residency: idle {c6_idle:.1f}% -> load {c6_load:.1f}%")
if not (c6_idle > 50 and c6_load < 10):
    fail("XVAL", f"C6 residency idle {c6_idle:.1f}% load {c6_load:.1f}% "
                 "does not match documented 84-93 -> 0.5")

# d[212] is documented as a load-proportional rate that PLATEAUS under steady load,
# not as a running total. Test that: under constant load it must not climb.
p2 = subprocess.Popen(["stress-ng", "--cpu", "16", "--timeout", "40"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(18)
series = []
for _ in range(6):
    series.append(raw_table()[212])
    time.sleep(3)
p2.wait()
drift = (series[-1] - series[0]) / max(series[0], 1)
plateau = abs(drift) < 0.10
print(f"  {'ok  ' if plateau else 'FAIL'} d[212] over 15 s of steady load: "
      f"{series[0]:.0f} -> {series[-1]:.0f} ({drift:+.1%}) — documented as a "
      "plateauing rate, not an accumulator")
if not plateau:
    fail("XVAL", f"d[212] moved {drift:+.1%} under steady load; documented as a "
                 "plateauing rate")

# d[263]/d[264] read 32/16 on an 8C/16T part, so they are NOT this SKU's counts. The
# map is required to keep saying so — this guards against the old label creeping back.
ncpu = len([x for x in Path("/sys/devices/system/cpu").glob("cpu[0-9]*")
            if (x / "cpufreq").exists()])
map_text = MAP.read_text()
print(f"  d[263]={idle[263]:.0f} d[264]={idle[264]:.0f}  system reports {ncpu} threads, "
      f"{ncpu // 2} cores")
if abs(idle[263] - ncpu) > 0.5 and "the 9800X3D has 16 threads" not in map_text:
    fail("XVAL", f"d[263]={idle[263]:.0f} != {ncpu} threads and the map does not "
                 "flag it as mislabeled")
if abs(idle[264] - ncpu / 2) > 0.5 and "the 9800X3D has 8 cores" not in map_text:
    fail("XVAL", f"d[264]={idle[264]:.0f} != {ncpu // 2} cores and the map does not "
                 "flag it as mislabeled")

# limits must equal 9800X3D stock spec
for i, name, want in [(2, "PPT limit", 162.0), (8, "TDC limit", 120.0),
                      (63, "EDC limit", 180.0)]:
    xval("XVAL", f"d[{i}] {name}", idle[i], want, 0.01)
print()

# ---------------------------------------------------------------- spiky fields
print("== NOISE: fields too spiky to trust from a single read ==")
for i in (11, 270, 9, 3):
    vals = [r[i] for r in idle_raws]
    sd = statistics.pstdev(vals)
    print(f"  d[{i}] (0x{i * 4:03X}) idle raw spread "
          f"{min(vals):.2f}..{max(vals):.2f} (pstdev {sd:.2f})")
print()

# ---------------------------------------------------------------- COUNT claims
print("== COUNT: summary statistics ==")
nz_static = sum(1 for i in range(457)
                if abs(load[i] - idle[i]) < 0.05 and abs(idle[i]) > 1e-6)
z_static = sum(1 for i in range(457) if abs(idle[i]) < 1e-6 and abs(load[i]) < 1e-6)
print(f"  non-zero statics: measured {nz_static}, documented ~200-215")
print(f"  zero statics    : measured {z_static}, documented ~105-110")
if not 190 <= nz_static <= 225:
    warn("COUNT", f"non-zero static count {nz_static} outside the documented "
                 "200-215 range — background CPU activity?")
if not 95 <= z_static <= 120:
    warn("COUNT", f"zero static count {z_static} outside the documented range")

# Every index must have a well-formed row. A row missing its Static column parses
# as prose and silently drops its indices from STATIC and ZERO — that is exactly how
# 88 indices went untested for months.
undocumented = sorted({i for i in range(457)} - {i for r in rows for i in r[0]})
print(f"  indices with no parseable row: {len(undocumented)}")
if undocumented:
    fail("COUNT", f"{len(undocumented)} indices have no parseable row "
                  f"(first: {undocumented[:8]}) — likely a malformed table row")
print()

print("=" * 60)
print(f"FAILURES: {len(fails)}    WARNINGS: {len(warns)}")
for f_ in fails:
    print("  " + f_)
for w in warns:
    print("  " + w)
raise SystemExit(1 if fails else 0)

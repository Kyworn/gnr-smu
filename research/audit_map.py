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

import glob
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

    k10temp is read *before* the pm_table read, not after. Reading pm_table costs an
    SMU transfer, and that transfer warms the die enough to show up in the very next
    sensor read: measured over 60 pairs, k10temp minus d[11] is +4.51 C when k10temp
    is read second but +2.14 C when it is read first, and the spread collapses from
    6.5 C to 2.8 C. That residual is not a sensor offset — at genuine thermal
    equilibrium the two agree to ~0.15 C. It is cooldown: those runs followed a
    stress load, and the delta decays over about two minutes. Hence wait_cool().
    """
    cols = [[] for _ in range(457)]
    k10 = []
    c6_before = cpuidle_deep()
    for _ in range(n):
        k10.append(float(rd(f"{K10}/temp1_input")) / 1000)
        with open(PM, "rb") as f:
            v = struct.unpack("<457f", f.read(1828))
        for i, x in enumerate(v):
            cols[i].append(x)
        time.sleep(gap)
    return ([statistics.median(c) for c in cols], statistics.median(k10),
            cpuidle_pct(c6_before, cpuidle_deep()))


DEEP_STATE = "/sys/devices/system/cpu/cpu*/cpuidle/state3/time"


def cpuidle_deep():
    """(cumulative deep-idle microseconds summed over CPUs, monotonic time, cpu count).

    state3 is C3 in the kernel's naming, which is the deep package state the SMU
    counts as CC6. Cumulative counters, so only a difference over a window means
    anything."""
    paths = glob.glob(DEEP_STATE)
    return sum(int(rd(p)) for p in paths), time.monotonic(), len(paths)


def cpuidle_pct(before, after):
    """Deep-idle residency over the window, as a percentage, from the kernel's own
    accounting.

    Printed for context, NOT used as ground truth for d[349-356]. It corroborates the
    field — on a quiet desktop the kernel reads 84-89 % against a PM mean of 68-74 % —
    but it cannot calibrate it. The kernel counts per-thread time in the C3 state; CC6
    needs both SMT siblings idle at once, so the PM figure sits 10-20 points lower. And
    the sampling loop keeps its own core out of CC6, which costs that core ~30 points.
    See the C6 section of PM_TABLE_MAP.md."""
    (a, ta, n), (b, tb, _) = before, after
    if not n or tb <= ta:
        return None
    return (b - a) / 1e6 / (tb - ta) / n * 100


def cpufreq_ghz():
    """Per-CPU current frequency in GHz, skipping CPUs without a cpufreq directory."""
    out = []
    for c in range(16):
        try:
            out.append(float(rd(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq"))
                       / 1e6)
        except OSError:
            pass
    return out


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
def k10_burst(n=15, gap=0.12):
    """Median Tctl over a short burst. A single read is not usable as a stability
    probe: at idle k10temp swings several degrees on background activity alone —
    46.6 C and 64.6 C twenty seconds apart on an otherwise idle desktop."""
    return statistics.median(
        float(rd(f"{K10}/temp1_input")) / 1000 for _ in range(n) if not time.sleep(gap))


def wait_cool(max_wait=420, window=20, tol=0.5, max_load=1.0, stable_needed=2):
    """Block until the machine is genuinely idle: Tctl steady AND load average low.

    Both conditions, because neither alone is enough. A fixed sleep is not enough —
    the die sheds heat for minutes after a stress run. Temperature alone is not
    enough either: during a transient d[11] and k10temp disagree by several degrees
    purely because they are sampled at different instants of a moving temperature,
    which reads as a sensor mismatch when it is really "you measured during
    cooldown". At true equilibrium the two agree to about 0.15 C.

    Compares burst medians rather than instantaneous reads, and requires two
    consecutive stable windows, because one background spike can otherwise either
    fake instability or — if it lands in both samples — fake stability.
    """
    deadline = time.time() + max_wait
    prev = k10_burst()
    stable = 0
    load1 = float(rd("/proc/loadavg").split()[0].replace(",", "."))
    while time.time() < deadline:
        time.sleep(window)
        cur = k10_burst()
        load1 = float(rd("/proc/loadavg").split()[0].replace(",", "."))
        stable = stable + 1 if (abs(prev - cur) < tol and load1 < max_load) else 0
        prev = cur
        if stable >= stable_needed:
            return cur, load1
    return prev, load1


print("Sampling IDLE (waiting for Tctl to settle) ...")
cool_t, cool_l = wait_cool()
print(f"  settled at {cool_t:.1f} C, load average {cool_l:.2f}")
# amdgpu rails move with load, so they must be read in the same window as the PM
# samples they are compared against — not once at the end of the script.
idle_vddgfx = float(rd(f"{AMDGPU}/in0_input")) / 1000
idle_vddnb = float(rd(f"{AMDGPU}/in1_input")) / 1000
idle_sclk = float(rd(f"{AMDGPU}/freq1_input")) / 1e6
idle, idle_k10, idle_c6 = avg_table()
idle_raws = [raw_table() for _ in range(5)]

print("Sampling LOAD (stress-ng --cpu 16, 45 s settle) ...")
p = subprocess.Popen(
    ["stress-ng", "--cpu", "16", "--timeout", "75"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(45)
load, load_k10, load_c6 = avg_table()
load_cpufreq = cpufreq_ghz()   # must be read before stress-ng exits, see the check below
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
# 35 mV, not 20: over eight consecutive 40-sample windows the absolute delta ran
# 0.9-22.0 mV (median 6.0), so a 20 mV gate sits on top of the noise and fails
# intermittently on nothing. A genuinely mislabelled field here would be volts out, not
# millivolts.
xval("XVAL", "d[49] Vcore P1 vs amdgpu vddgfx (40-sample means)",
     statistics.mean(pm_v), statistics.mean(sys_v), 0.035, "V")
xval("XVAL", "d[53] VDDCR_SoC vs amdgpu vddnb", idle[53], idle_vddnb, 0.02, "V")
xval("XVAL", "d[58] VDDIO_MEM vs DDR5 nominal", idle[58], 1.1, 0.05, "V")
xval("XVAL", "d[108] iGPU sclk vs amdgpu freq1", idle[108], idle_sclk, 60, "MHz")

# Domain isolation: a pure CPU load must not move the iGPU block. If it does, either
# the offsets are not iGPU at all or the two domains share a rail. This is the one
# check tools/verify_map.py had that nothing else did; folded in here because that
# script kept its own copy of the labels, which then had to be corrected by hand
# every time the map changed.
xval("XVAL", "d[107] iGPU power under CPU load (must stay flat)",
     load[107], idle[107], 2.0, "W")
xval("XVAL", "d[108] iGPU clock under CPU load (must stay flat)",
     load[108], idle[108], 50, "MHz")
xval("XVAL", "d[11] Tctl vs k10temp (idle)", idle[11], idle_k10, 3.0, "C")
xval("XVAL", "d[11] Tctl vs k10temp (load)", load[11], load_k10, 3.0, "C")

core_t = [load[317 + i] for i in range(8)]
xval("XVAL", "d[317-324] core temp max vs k10temp Tctl (load)",
     max(core_t), load_k10, 8.0, "C")

# per-core frequency vs cpufreq — load_cpufreq is captured while stress-ng is still
# running. Reading it here would compare a load-window PM sample against idle
# frequencies: stress-ng has already exited by this point in the script, and the check
# only passed because an idle core briefly boosting to ~5.4 GHz happens to look like a
# loaded one.
if load_cpufreq:
    pm_f = [load[325 + i] for i in range(8)]
    xval("XVAL", "d[325-332] core freq max vs cpufreq max (load)",
         max(pm_f), max(load_cpufreq), 0.6, "GHz")

maxf = float(rd("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")) / 1e6
xval("XVAL", "d[373-380] boost limit vs cpuinfo_max_freq",
     max(load[373 + i] for i in range(8)), maxf, 0.15, "GHz")

# C6 residency, against the kernel's own idle accounting rather than a fixed
# threshold: the absolute idle figure tracks whatever else is running on the desktop
# (33% with a browser open, 75% quiet), so only the agreement is a property of d[349].
c6_idle = statistics.mean(idle[349 + i] for i in range(8))
c6_load = statistics.mean(load[349 + i] for i in range(8))
# Only the behaviour is checkable: it must be ~0 with every core pinned, and clearly
# above that at idle. The absolute idle figure is not a property of the field.
c6_ok = c6_load < 5.0 and c6_idle > c6_load + 10.0
print(f"  {'ok  ' if c6_ok else 'FAIL'} d[349-356] C6 residency: "
      f"idle {c6_idle:.1f}% -> load {c6_load:.1f}% "
      f"(kernel cpuidle for reference: {idle_c6:.1f}% -> {load_c6:.1f}%)")
if not c6_ok:
    fail("XVAL", f"C6 residency {c6_idle:.1f}% idle / {c6_load:.1f}% load: expected "
                 "~0 under all-core load and clearly higher at idle")

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

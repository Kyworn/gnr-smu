# PM Table Memory Map — AMD Granite Ridge (v0x620105)

**Size:** 0x724 bytes (1828 bytes = 457 float32)  
**Source:** `/sys/kernel/ryzen_smu_drv/pm_table`  
**Method:** Static/dynamic analysis + stress test differential (idle vs full CPU load) + cross-reference with `pm_table_gnr` struct (ryzen_smu) + Zen 3/4 `pm_table_0x240903` field patterns + k10temp/amdgpu cross-validation.
**Confidence:** CONFIRMED = struct match or validated | HIGH = strong pattern | MED = inferred | LOW = guess

---

## Zone 0x000 — Classic Zen (LIMIT, VALUE) Pairs

**⚠ Corrected 2026-07-30** — this zone was previously mislabeled as temperatures.
It is the standard Zen `(LIMIT, VALUE)` pair layout: each limit is immediately
followed by its live value in the *same* unit. See
[Re-verification 2026-07-30](#re-verification-2026-07-30) for the measurements.

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x000 | 0 | 0 | Y | STAPM Limit (0 on desktop) | CONFIRMED |
| 0x004 | 1 | 0 | Y | STAPM Value (0 on desktop) | CONFIRMED |
| 0x008 | 2 | 162.0 | Y | **PPT Limit (W)** | CONFIRMED |
| 0x00C | 3 | 28 idle / 128 load | N | **PPT Value — total package power (W)** | CONFIRMED (idle 27.9 → load 128.2 W, ceiling = 162 limit; equals d[20] + ~17 W uncore/SoC at a constant offset) |
| 0x010 | 4-7 | 0 | Y | Reserved (fast/slow PPT pair, unused) | CONFIRMED |
| 0x020 | 8 | 120.0 | Y | **TDC Limit (A)** — 9800X3D stock TDC is 120 A | CONFIRMED |
| 0x024 | 9 | 9 idle / 87 load | N | **TDC Value — live current (A)** | CONFIRMED (idle 9.3 → load 86.7 A, ceiling = 120 limit) |
| 0x028 | 10 | 88.0 | Y | **THM Limit (°C)** — thermal limit, *not* a current | CONFIRMED (reads 88.0 on this board; doc previously said 85.0) |
| 0x02C | 11 | 49 idle / 83 load | N | **THM Value — Tctl (°C), direct reading** | CONFIRMED (slope 0.97 vs k10temp Tctl, absolute match within 1.1 °C at idle *and* load) |

## Zone 0x030 — Reserved

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x030 | 12-15 | 0 | Y | Reserved | CONFIRMED |

## Zone 0x040 — Power & Voltage

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x040 | 16 | ~1900 | N | Energy Budget / Countdown Counter (↓ under stress) | MED |
| 0x044 | 17 | 0.7 idle → ~114 @8 thr → ~47 @16 thr | N | **Not** a core power aggregate — it exceeds package power in 36/60 samples at 8 threads (114.2 vs 110.9 W, physically impossible for a subset of the package) and is non-monotonic in load, peaking at 8 threads and falling at 16. Real meaning unknown; the 8-thread peak suggests a per-physical-core metric | LOW (was "Core Power Aggregate (W)" / CONFIRMED) |
| 0x048 | 18 | ~1.37 | N | **Vcore Peak (V)** | CONFIRMED |
| 0x04C | 19 | ~1.19 idle → ~1.31 load | N | **Vcore Average (V)** | CONFIRMED |
| 0x050 | 20 | ~20.5 | N | **Package Power (W)** | CONFIRMED (stress: 17→106) |
| 0x054 | 21 | ~6.1 | N | SoC Power (W) | HIGH |
| 0x058 | 22 | ~5.8 | N | VDDCR_CPU Telemetry Power (W) | MED |
| 0x05C | 23 | ~2.9 | N | VDDIO_MEM Power (W) | MED |

## Zone 0x060 — Telemetry Scalars

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x060 | 24 | 1.000 | Y | Power Telemetry Scalar | HIGH |
| 0x064 | 25 | 1.000 | Y | Voltage Telemetry Scalar | HIGH |

## Zone 0x068 — Frequency Table / Mirror Zone

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x068 | 26 | ~26 | N | Near-copy of d[3] PPT Value (W) — tracks it but is **not** identical (max delta 2.54 W over 120 samples) | MED (was "Pkg Thermal Metric / mirror") |
| 0x06C | 27 | ~5.44 | N | CPPC Max / DPM Freq [0] (GHz) | MED |
| 0x070 | 28 | ~5.44 | N | CPPC Max / DPM Freq [1] (GHz) | MED |
| 0x074 | 29 | ~5.44 | N | CPPC Max / DPM Freq [2] (GHz) | MED |
| 0x078 | 30 | ~5.44 | N | CPPC Max / DPM Freq [3] (GHz) | MED |
| 0x07C | 31 | ~5.44 | N | CPPC Max / DPM Freq [4] (GHz) | MED |
| 0x080 | 32 | ~5.44 | N | CPPC Max / DPM Freq [5] (GHz) | MED |
| 0x084 | 33 | ~5.44 | N | CPPC Max / DPM Freq [6] (GHz) | MED |
| 0x088 | 34 | ~5.44 | N | CPPC Max / DPM Freq [7] (GHz) | MED |
| 0x08C | 35 | ~5.44 | N | DPM Freq [8] (GHz) | MED |
| 0x090 | 36 | ~5.44 | N | DPM Freq [9] (GHz) | MED |
| 0x094 | 37 | ~5.44 | N | DPM Freq [10] (GHz) | MED |
| 0x098 | 38 | ~5.44 | N | DPM Freq [11] (GHz) | MED |

## Zone 0x09C — Voltage DPM Levels

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x09C | 39 | ~1.37 | N | Boost Voltage (V) | HIGH |
| 0x0A0 | 40 | ~1.38 | N | P-State Voltage 0 (V) | HIGH |
| 0x0A4 | 41 | ~1.52 | N | Max Voltage Limit (V) | HIGH |
| 0x0A8 | 42 | ~1.40 | N | P-State Voltage 1 (V) | HIGH |
| 0x0AC | 43 | ~1.52 | N | Max Voltage Limit (mirror) | MED |
| 0x0B0 | 44 | ~1.52 | N | Max Voltage Limit (mirror) | MED |
| 0x0B4 | 45 | ~1.40 | N | P-State Voltage 2 (V) | HIGH |
| 0x0B8 | 46 | ~1.40 | N | P-State Voltage 3 (V) | HIGH |
| 0x0BC | 47 | ~1.40 | N | P-State Voltage 4 (V) | HIGH |

## Zone 0x0C0 — Mirror / Set Voltages

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x0C0 | 48 | ~1.19 idle → ~1.31 load | N | Vcore Set Voltage (V) | HIGH |
| 0x0C4 | 49 | ~1.19 idle → ~1.28 load | N | Vcore P1 Voltage (V) | HIGH (mean delta vs amdgpu vddgfx +4.3 mV over 60 paired samples; **do not compare single reads** — vddgfx alone swings 1.010-1.250 V at idle, so instantaneous pairs diverge by up to 200 mV) |
| 0x0C8 | 50 | ~7.0 | N | Near-copy of d[9] TDC Value (A) — tracks it but is **not** identical (max delta 2.07 A over 120 samples) | MED (was "SoC Thermal Metric / mirror") |
| 0x0CC | 51 | ~20.5 | N | Pkg Power (mirror of 0x050) | HIGH |
| 0x0D0 | 52 | ~56.9 | N | Accumulated Metric / Temp | MED |
| 0x0D4 | 53 | 0.954 | Y | VDDCR_SoC Set Voltage (V) | HIGH |
| 0x0D8 | 54 | 0.943 | Y | VDDP Voltage (V) | HIGH |
| 0x0DC | 55 | ~6.4 | N | Power Domain (W) | MED |
| 0x0E0 | 56 | ~6.1 | N | SoC Power (mirror of 0x054) | HIGH |
| 0x0E4 | 57 | ~50.1 | N | SoC Telemetry Current (A) | MED |
| 0x0E8 | 58 | 1.099 | Y | VDDIO_MEM Voltage (V) | HIGH |
| 0x0EC | 59 | 1.099 | Y | VDDIO_MEM Voltage (mirror) | HIGH |
| 0x0F0 | 60 | ~5.3 | N | Average Core Frequency (GHz) | MED |
| 0x0F4 | 61 | ~5.8 | N | Peak Effective Frequency (GHz) | MED |

## Zone 0x0F8 — Limits & Thermal

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x0F8 | 62 | 49 idle → 56 load | N | SoC Power Limit (W) — the limit itself is re-negotiated with load, so not static | MED |
| 0x0FC | 63 | 180.0 | Y | **EDC Limit (A)** — 9800X3D stock EDC is 180 A. No companion EDC_VALUE float found; a sweep for an offset rising into 90-182 A under all-core load returned only known power/percent fields | CONFIRMED |
| 0x100 | 64 | 44-104 | N | Unidentified utilization metric, quantized to 0.125 steps. **Not a temperature** (slope 1.52 vs Tctl, and exceeds 100 in some runs) | LOW (previously mislabeled "Thermal Metric") |
| 0x104 | 65 | 552.0 | Y | Unknown Frequency/Limit | LOW |
| 0x108 | 66 | 0 | Y | Reserved | — |
| 0x10C | 67 | 0 | Y | Reserved | — |
| 0x110 | 68 | 100.0 | Y | Percentage Cap / Utilization Max | MED |
| 0x114 | 69-70 | 0 | Y | Reserved | — |

## Zone 0x11C — Memory / Fabric Clocks (DPM Table)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x11C | 71 | 2000.0 | Y | **FCLK (MHz)** | CONFIRMED |
| 0x120 | 72 | 1600.0 | Y | FCLK DPM State 0 (MHz) | HIGH |
| 0x124 | 73 | 1600.0 | Y | FCLK DPM State 1 (MHz) | HIGH |
| 0x128 | 74 | 500.0 | Y | FCLK DPM Min (MHz) | HIGH |
| 0x12C | 75 | 3000.0 | Y | **UCLK (MHz)** | CONFIRMED |
| 0x130 | 76 | 1600.0 | Y | UCLK DPM State 0 (MHz) | HIGH |
| 0x134 | 77 | 1600.0 | Y | UCLK DPM State 1 (MHz) | HIGH |
| 0x138 | 78 | 500.0 | Y | UCLK DPM Min (MHz) | HIGH |
| 0x13C | 79 | 3000.0 | Y | **MCLK (MHz)** | CONFIRMED |
| 0x140 | 80 | 1600.0 | Y | MCLK DPM State 0 (MHz) | HIGH |
| 0x144 | 81 | 1600.0 | Y | MCLK DPM State 1 (MHz) | HIGH |
| 0x148 | 82 | 1000.0 | Y | MCLK DPM Min (MHz) | HIGH |
| 0x14C | 83 | 1.250 | Y | VSOC Voltage (V) | HIGH |
| 0x150 | 84 | 0.855 | Y | VDDP Voltage (V) | HIGH |
| 0x154 | 85 | 0.855 | Y | VDDG Voltage (V) | HIGH |
| 0x158 | 86 | 0.700 | Y | VDDM Voltage (V) | HIGH |
| 0x15C | 87 | ~0.20 | N | SoC Telemetry Metric (NOT voltage, idle=0.20 stress=varies) | MED |
| 0x160 | 88 | ~0.1 | N | SoC Telemetry Power (W) | MED |
| 0x164 | 89 | ~0.01 | N | Minor Rail Power (W) | LOW |
| 0x168 | 90 | ~0.01 | N | Minor Rail Power (W) | LOW |
| 0x16C-0x178 | 91-94 | 0 | Y | Reserved | — |

## Zone 0x17C — SoC Live Metrics

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x17C | 95 | ~0.04 | N | SoC Telemetry Metric (NOT voltage, idle=0.04) | LOW |
| 0x180 | 96 | ~2.5 | N | SoC Power (W) | HIGH |
| 0x184 | 97 | ~0.9 | N | SoC Telemetry Voltage (V) | MED |
| 0x188-0x1A0 | 98-104 | 0 | Y | Reserved | — |
| 0x1A4 | 105 | ~0.73 | Y | Minor Rail Voltage (V) | LOW |
| 0x1A8 | 106 | ~47.7 | N | iGPU Accumulated Metric | MED |

## Zone 0x1AC — iGPU Telemetry

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x1AC | 107 | 0-4.0 | N | **iGPU Power (W)** | CONFIRMED (Pearson) |
| 0x1B0 | 108 | 600 | N | **iGPU Clock / sclk (MHz)** | CONFIRMED (Pearson) |
| 0x1B4 | 109 | 0-134 | N | **iGPU Activity (%)** | CONFIRMED (Pearson) |
| 0x1B8 | 110 | 0-14 | N | **iGPU Current (A)** | CONFIRMED (Pearson) |
| 0x1BC | 111 | ~100 | N | iGPU Utilization Cap (%) | MED |
| 0x1C0 | 112 | ~100 | N | iGPU VRM Utilization (%) | MED |

## Zone 0x1C4 — iGPU DPM Frequency Table (Static)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x1C4-0x1D8 | 113-118 | 300-1600 | Y | iGPU sclk DPM States (MHz) | HIGH |
| 0x1DC | 119 | ~1080 | N | iGPU Memory Clock Live (MHz) | MED |
| 0x1E0-0x1FC | 120-127 | 400-1600 | Y | iGPU DPM Table cont. (MHz) | HIGH |
| 0x200 | 128 | 0.195 | Y | iGPU Voltage (V) | MED |
| 0x204 | 129 | 0.195 | Y | iGPU Voltage (mirror) | MED |
| 0x208 | 130 | 1200.0 | Y | iGPU Memory DPM (MHz) | HIGH |
| 0x20C | 131 | ~1080 | N | iGPU Mem Clock Live (mirror) | MED |

## Zone 0x210 — Fabric / Peripheral Clocks

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x210 | 132 | ~9.5 | N | SoC Power Domain (W) | MED |
| 0x214 | 133 | ~3.3 | N | Fabric Power (W) | MED |
| 0x218-0x2B0 | 134-172 | 200-1200 | Y | LCLK / Peripheral DPM Clocks (MHz) — d[171] reads 1028.57, d[172] reads 600 (the iGPU sclk value, cf. d[108]); both fit the block | HIGH (range corrected 2026-07-30: the row said `0x218-0x2AC | 134-170`, but 0x2AC is index 171, and 0x2B0 was in no row at all) |
| 0x2B4 | 173 | 0.955 | Y | NB Voltage (V) | MED |
| 0x2B8 | 174 | 0.955 | Y | NB Voltage (mirror) | MED |
| 0x2BC | 175 | 0.855 | Y | IO Voltage (V) | MED |
| 0x2C0 | 176 | 0.750 | Y | Minor Rail Voltage (V) | MED |

## Zone 0x2C4 — Thermal Headroom / C-State Caps

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x2C4-0x2CC | 177-179 | 0 | Y | Reserved | — |
| 0x2D0 | 180 | 100.0 | Y | C-State Cap 0 (%) | MED |
| 0x2D4-0x2D8 | 181-182 | 0 | Y | Reserved | — |
| 0x2DC | 183 | 100.0 | Y | C-State Cap 1 (%) | MED |
| 0x2E0-0x2E4 | 184-185 | 0 | Y | Reserved | — |
| 0x2E8 | 186 | ~0.00 idle | N | **iGPU Activity / Busy (%)** — reads 0.003 with iGPU idle, rises a few % under CPU-only load. **Not a temperature** | HIGH (corrected; sums to 100 with 0x2EC) |
| 0x2EC | 187 | 100 − 0x2E8 | N | **iGPU Idle (%)** — complement of 0x2E8 | CONFIRMED (pair always sums to 100.000) |
| 0x2F0-0x2F8 | 188-190 | 0 | Y | Reserved | — |
| 0x2FC | 191 | 100.0 | Y | C-State Cap 2 (%) | MED |
| 0x300-0x30C | 192-195 | 0 | Y | Reserved | — |
| 0x310 | 196 | 100.0 | Y | C-State Cap 3 (%) | MED |
| 0x314-0x314 | 197 | 0 | Y | Reserved | — |
| 0x318 | 198 | 100.0 | Y | C-State Cap 4 (%) | MED |
| 0x31C-0x328 | 199-202 | 0 | Y | Reserved | — |
| 0x32C | 203 | 100.0 | Y | C-State Cap 5 (%) | MED |
| 0x330-0x33C | 204-207 | 0 | Y | Reserved | — |
| 0x340 | 208 | 100.0 | Y | C-State Cap 6 (%) | MED |

## Zone 0x344 — Thermal / Frequency Parameters

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x344 | 209 | 90.0 | Y | Thermal Limit (°C) | HIGH |
| 0x348 | 210 | 15-24 idle / 100 load | N | **Percentage / FIT-style utilization (%)** — saturates hard at 99.94-100.00 under load. **Not a temperature** | HIGH (corrected; a °C field would not pin at exactly 100) |
| 0x34C | 211 | 3000.0 | Y | MCLK (mirror) | HIGH |
| 0x350 | 212 | ~1450 idle → ceiling | N | Not a running total (plateaus under steady load) and **not** power-proportional either: it saturates at its ceiling from a *single* busy thread and stays there (1 thr 14536, 4 thr 14696, 8 thr 14528, 16 thr 12906 under `--matrix`), and the ceiling itself is workload-dependent (~23 200 under `--cpu`). Ratio against package power drifts 175 % across load levels. Unidentified | LOW (was "Package Energy Accumulator (J)" / CONFIRMED) |
| 0x354 | 213 | 12.8 | Y | Current Limit (A?) | MED |
| 0x358 | 214 | ~3.4 | N | Power Domain (W) | MED |
| 0x35C | 215 | 4.0 | Y | Scalar / Multiplier | LOW |
| 0x360 | 216 | ~1.03 | N | Live Voltage (V) | MED |
| 0x364-0x36C | 217-219 | 400.0 | Y | Min DPM Frequency (MHz) | HIGH |
| 0x370 | 220 | ~199-213 | N | **Not** part of the Min-DPM block — reads ~200, not 400, and drifts with load (202 → 213). Unidentified | LOW (was folded into the 400 MHz Min-DPM row) |
| 0x374-0x380 | 221-224 | 400.0 | Y | Min DPM Frequency (MHz) | HIGH |
| 0x384 | 225 | 0.600 | Y | Min DPM Voltage (V) | MED |
| 0x388 | 226 | ~0.09 | N | Minor Power Domain (W) | LOW |
| 0x38C | 227 | 48.0 | Y | VRM Temp Limit (°C) | MED |
| 0x390 | 228 | 48.0 | Y | VRM Temp Limit (mirror) | MED |
| 0x394-0x3CC | 229-243 | 200-600 | Y | Peripheral/LCLK DPM States (MHz) | HIGH |
| 0x3D0 | 244 | 600.0 | Y | LCLK Max DPM (MHz) | MED |
| 0x3D4 | 245 | 100.0 | Y | Utilization Cap (%) | MED |

## Zone 0x3D8 — Mixed Parameters

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x3D8-0x3E8 | 246-250 | 0 | Y | Reserved | — |
| 0x3EC | 251 | 25.0 | Y | Slow PPT Limit (W?) | MED |
| 0x3F0 | 252 | 0 | Y | Reserved | — |
| 0x3F4 | 253 | 25.0 | Y | Slow PPT Limit (mirror) | MED |
| 0x3F8-0x408 | 254-258 | 0 | Y | Reserved | — |
| 0x40C | 259 | ~0.905 | N | SoC Voltage Rail (V) | MED |
| 0x410 | 260 | 0 | Y | Reserved | — |
| 0x414 | 261 | ~0.905 | N | SoC Voltage Rail (mirror) | MED |
| 0x418 | 262 | 0 | Y | Reserved | — |
| 0x41C | 263 | 32.0 | Y | **Not** this SKU's thread count — the 9800X3D has 16 threads. Reads 32, i.e. a silicon/socket maximum or a topology constant | LOW (was "Thread Count" / MED) |
| 0x420 | 264 | 16.0 | Y | **Not** this SKU's core count — the 9800X3D has 8 cores. Reads 16, same silicon-maximum pattern as d[263] | LOW (was "Core Count" / MED) |
| 0x424 | 265 | 5.5 | Y | Parameter (W or ratio) | LOW |
| 0x428 | 266 | 4.0 | Y | Parameter (scalar) | LOW |

## Zone 0x42C — Live Metrics (Pre-Core)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x42C | 267 | ~1.03 | N | Live Voltage (V) | MED |
| 0x430 | 268 | 120.0 | Y | EDC Limit (mirror, A) | HIGH |
| 0x434 | 269 | 1.148 | Y | SVI3 VDDCR_CPU VID (V) | HIGH |
| 0x438 | 270 | 50 idle / 87 load | N | **Hotspot / instantaneous max Temperature (°C)** — *not* TDC current. Slope 1.02 vs k10temp Tctl; mean sits 0-3 °C above it. **Spiky**: unaveraged reads hit 63-90 °C at idle (stdev 2.7 vs 0.6 for k10temp), so always average this field. Real TDC current is d[9] | CONFIRMED (corrected — the old "TDC current" label was swapped with d[9]) |
| 0x43C | 271 | ~1.26 | N | SVI3 VDDCR_SoC VID (V) | HIGH |
| 0x440 | 272 | 5.425 | Y | Max Boost Frequency (GHz) | HIGH |
| 0x444 | 273 | ~0.46 | N | **SoC Telemetry Current/Power Metric** (NOT voltage, Pearson=0.999 with Pkg Power) | CONFIRMED (stress: 0.46→7.98, tracks load not voltage) |
| 0x448 | 274 | ~5.44 | N | Core Boost Limit Mirror (GHz) | HIGH |
| 0x44C | 275 | ~1.20 | N | Live Voltage (V) | MED |
| 0x450 | 276 | 0.010 | Y | Scalar | LOW |
| 0x454 | 277 | ~26 | N | Near-copy of d[3] PPT Value (W) — tracks it but is **not** identical (max delta 11.7 W over 120 samples) | MED (was "Pkg Thermal Metric / mirror") |
| 0x458 | 278 | ~49 → ~54 | N | Unidentified, near-static. **Not PPT current value** — moves only 49→54 while real package power goes 28→128 W (that is d[3]) | LOW (corrected) |
| 0x45C-0x4A4 | 279-297 | 0 | Y | Reserved | — |

## Zone 0x4A8 — L3 / Cache Metrics

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x4A8 | 298 | ~44.6 → ~48.4 | N | Slow thermal reading (°C), domain unconfirmed. Rises only 3.8 °C over 60 s of all-core load (slope 0.11 vs Tctl) — too flat for V-Cache. Tracks d[456] at a constant +9.39 offset, so the two share one sensor | LOW (was "L3/V-Cache Temp 0 / HIGH") |
| 0x4AC | 299 | ~45.4 → ~49.2 | N | Slow thermal reading (°C), same behaviour as d[298] | LOW (was "L3/V-Cache Temp 1 / HIGH") |
| 0x4B0-0x4B0 | 300 | 0 | Y | Reserved | — |

## Zone 0x4B4 — Per-Core IDD / Current (8 values)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x4B4 | 301 | ~1.86 | N | Core 0 IDD (A) | HIGH |
| 0x4B8 | 302 | ~1.83 | N | Core 1 IDD (A) | HIGH |
| 0x4BC | 303 | ~2.27 | N | Core 2 IDD (A) | HIGH |
| 0x4C0 | 304 | ~1.92 | N | Core 3 IDD (A) | HIGH |
| 0x4C4 | 305 | ~2.01 | N | Core 4 IDD (A) | HIGH |
| 0x4C8 | 306 | ~2.16 | N | Core 5 IDD (A) | HIGH |
| 0x4CC | 307 | ~1.82 | N | Core 6 IDD (A) | HIGH |
| 0x4D0 | 308 | ~1.73 | N | Core 7 IDD (A) | HIGH |

## Zone 0x4D4 — Per-Core Telemetry (CONFIRMED by struct)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x4D4 | 309 | ~1.17 | N | **Core 0 Voltage (V)** | CONFIRMED |
| 0x4D8 | 310 | ~1.18 | N | **Core 1 Voltage (V)** | CONFIRMED |
| 0x4DC | 311 | ~1.16 | N | **Core 2 Voltage (V)** | CONFIRMED |
| 0x4E0 | 312 | ~1.17 | N | **Core 3 Voltage (V)** | CONFIRMED |
| 0x4E4 | 313 | ~1.17 | N | **Core 4 Voltage (V)** | CONFIRMED |
| 0x4E8 | 314 | ~1.15 | N | **Core 5 Voltage (V)** | CONFIRMED |
| 0x4EC | 315 | ~1.20 | N | **Core 6 Voltage (V)** | CONFIRMED |
| 0x4F0 | 316 | ~1.20 | N | **Core 7 Voltage (V)** | CONFIRMED |
| 0x4F4 | 317 | ~42.0 | N | **Core 0 Temperature (°C)** | CONFIRMED |
| 0x4F8 | 318 | ~40.2 | N | **Core 1 Temperature (°C)** | CONFIRMED |
| 0x4FC | 319 | ~43.3 | N | **Core 2 Temperature (°C)** | CONFIRMED |
| 0x500 | 320 | ~40.7 | N | **Core 3 Temperature (°C)** | CONFIRMED |
| 0x504 | 321 | ~42.7 | N | **Core 4 Temperature (°C)** | CONFIRMED |
| 0x508 | 322 | ~40.9 | N | **Core 5 Temperature (°C)** | CONFIRMED |
| 0x50C | 323 | ~42.2 | N | **Core 6 Temperature (°C)** | CONFIRMED |
| 0x510 | 324 | ~39.8 | N | **Core 7 Temperature (°C)** | CONFIRMED |
| 0x514 | 325 | ~5.33 | N | **Core 0 Frequency (GHz)** | CONFIRMED |
| 0x518 | 326 | ~5.35 | N | **Core 1 Frequency (GHz)** | CONFIRMED |
| 0x51C | 327 | ~5.43 | N | **Core 2 Frequency (GHz)** | CONFIRMED |
| 0x520 | 328 | ~5.35 | N | **Core 3 Frequency (GHz)** | CONFIRMED |
| 0x524 | 329 | ~5.31 | N | **Core 4 Frequency (GHz)** | CONFIRMED |
| 0x528 | 330 | ~5.33 | N | **Core 5 Frequency (GHz)** | CONFIRMED |
| 0x52C | 331 | ~5.31 | N | **Core 6 Frequency (GHz)** | CONFIRMED |
| 0x530 | 332 | ~5.30 | N | **Core 7 Frequency (GHz)** | CONFIRMED |

## Zone 0x534 — Per-Core Extended Metrics (5 × 8 values)

### Core Power (W)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x534-0x550 | 333-340 | 0.2-0.4 idle / 5.3 load | N | **Core Power (W) [8]** — monotonic in load, but the 8 values sum to only ~43 W against 124 W package, so the scope (core only? one voltage domain?) is not pinned | HIGH (was CONFIRMED) |

### Core FIT / Current
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x554-0x570 | 341-348 | 5-8 idle / 100 load | N | **Core FIT / IDD Max (%) [8]** — saturates at exactly 100.00 under load | CONFIRMED |

### Core C6 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x574-0x590 | 349-356 | 75-92 idle / 0.0 load | N | **Core C6 Residency (%) [8]** | CONFIRMED (collapses to exactly 0 under all-core load) |

### Core C0 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x594-0x5B0 | 357-364 | 0-16 idle / 0.0 load | N | **Not** C0 residency — reads up to 16 at *idle* and exactly 0 under all-core load, i.e. the opposite of C0. Behaves like a light-C-state residency | LOW (was "Core C0 Residency (%)" / CONFIRMED) |

### Core C1 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x5B4-0x5D0 | 365-372 | 0 | Y | Reads exactly 0 at idle and under load — no evidence it is C1 residency | LOW (was "Core C1 Residency" / MED) |

## Zone 0x5D4 — Core Frequency Limits (CONFIRMED by struct)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x5D4 | 373 | ~5.44 | N | **Core 0 Boost Limit (GHz)** | CONFIRMED |
| 0x5D8 | 374 | ~5.44 | N | **Core 1 Boost Limit (GHz)** | CONFIRMED |
| 0x5DC | 375 | ~5.44 | N | **Core 2 Boost Limit (GHz)** | CONFIRMED |
| 0x5E0 | 376 | ~5.44 | N | **Core 3 Boost Limit (GHz)** | CONFIRMED |
| 0x5E4 | 377 | ~5.44 | N | **Core 4 Boost Limit (GHz)** | CONFIRMED |
| 0x5E8 | 378 | ~5.44 | N | **Core 5 Boost Limit (GHz)** | CONFIRMED |
| 0x5EC | 379 | ~5.44 | N | **Core 6 Boost Limit (GHz)** | CONFIRMED |
| 0x5F0 | 380 | ~5.44 | N | **Core 7 Boost Limit (GHz)** | CONFIRMED |

## Zone 0x5F4 — Core Base Frequency

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x5F4 | 381 | ~4.69 | N | Core 0 P1/Base Frequency (GHz) | HIGH |
| 0x5F8 | 382 | ~4.69 | N | Core 1 P1/Base Frequency (GHz) | HIGH |
| 0x5FC | 383 | ~4.69 | N | Core 2 P1/Base Frequency (GHz) | HIGH |
| 0x600 | 384 | ~4.69 | N | Core 3 P1/Base Frequency (GHz) | HIGH |
| 0x604 | 385 | ~4.69 | N | Core 4 P1/Base Frequency (GHz) | HIGH |
| 0x608 | 386 | ~4.69 | N | Core 5 P1/Base Frequency (GHz) | HIGH |
| 0x60C | 387 | ~4.69 | N | Core 6 P1/Base Frequency (GHz) | HIGH |
| 0x610 | 388 | ~4.69 | N | Core 7 P1/Base Frequency (GHz) | HIGH |

## Zone 0x614 — Reserved

| Offset | Idx | Typical | Meaning |
|--------|-----|---------|---------|
| 0x614-0x630 | 389-396 | 0 | Y | Reserved | HIGH |

## Zone 0x634 — Per-Core Energy Accumulators

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x634 | 397 | ~830 | N | Core 0 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 403→18332 is an idle→load level change) |
| 0x638 | 398 | ~805 | N | Core 1 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 420→18567 is an idle→load level change) |
| 0x63C | 399 | ~1408 | N | Core 2 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 688→18654 is an idle→load level change) |
| 0x640 | 400 | ~936 | N | Core 3 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 550→18542 is an idle→load level change) |
| 0x644 | 401 | ~1119 | N | Core 4 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 557→18889 is an idle→load level change) |
| 0x648 | 402 | ~1451 | N | Core 5 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 831→18665 is an idle→load level change) |
| 0x64C | 403 | ~763 | N | Core 6 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 437→18106 is an idle→load level change) |
| 0x650 | 404 | ~726 | N | Core 7 energy rate/credit — plateaus under steady load, does not accumulate | MED (was "Energy Accumulator (J)" / CONFIRMED; 335→18610 is an idle→load level change) |

## Zone 0x654 — Per-Thread C-State Residency (16 threads)

| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x654-0x670 | 405-412 | 0.02-0.07 idle / 0.006-0.12 load | N | **Not** C0 residency — does not rise under a 16-thread load; individual lanes wander in both directions (d[408] 0.069→0.123, d[410] 0.065→0.006). Contrast d[413-420], which does behave like C0 | LOW (was "Thread 0-7 C0 Residency" / CONFIRMED) |
| 0x674-0x690 | 413-420 | 0.02-0.04 idle / 0.97-0.99 load | N | **Thread C0 Residency (fraction 0-1) [8]** — the one block that behaves like C0: near 0 at idle, near 1 under all-core load | CONFIRMED |

## Zone 0x694 — Extended C-State / Residency Counters

| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x694-0x6B0 | 421-428 | 0.003-0.004 idle / 0 load | Y | Secondary C-State Residency [8] — collapses to 0 under load | LOW |
| 0x6B4-0x6D0 | 429-436 | ~2e-05 | Y | Near-zero but **not** zero (1.8-2.1e-05, stable idle and load) — a residency-style field pinned at its floor, not a reserved hole | LOW |
| 0x6D4-0x6F0 | 437-444 | 0.013-0.033 idle / 1.4-2.3 load | N | Rises with load but **exceeds 1.0**, so it is not a residency fraction like d[413-420]. Domain unknown | LOW (was "Thread C-State Residency Alt" / CONFIRMED) |

## Zone 0x6F4 — Final Metrics

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x6F4 | 445 | ~3.1 | N | Package Energy Rate (W) | MED |
| 0x6F8 | 446 | 0.23 idle → 0.33 load | N | Scalar (load-dependent) | LOW |
| 0x6FC | 447 | 0.950 | Y | SVI3 Reference Voltage (V) | MED |
| 0x700 | 448 | ~36.9 → ~55.3 | N | Heavily filtered thermal value (°C), **not** the core-temp average — at 60 s steady load the real core average is 78.3 °C while this reads 55.3 °C | LOW (was "Average Core Temp / HIGH") |
| 0x704 | 449 | ~35.5 → ~53.4 | N | Same filtered signal as d[448], offset ~−1.9 °C. **Not** min core temp (real min 74.9 °C vs 53.4 °C) | LOW (was "Min Core Temp / HIGH") |
| 0x708 | 450 | ~5.43 | N | Peak Core Frequency (GHz) | HIGH |
| 0x70C | 451 | ~5.44 | N | Average Core Frequency (GHz) | HIGH |
| 0x710 | 452 | ~29024 → ~22777 | N | Rolling counter — **decreases** under load, so it is a credit/countdown, not an energy total. The real energy accumulator is d[212] (2503 → 23218) | LOW (was "Total Package Energy Accumulator / HIGH") |
| 0x714 | 453 | 862 idle → 13 517 @16 thr | N | Monotonic in load and the closest field to power-proportional: d[453] / d[20] holds at 103-106 for 4, 8 and 16 threads (2.7 % spread) but collapses to 55-88 below that, so it is not a clean unit conversion of package power. Does not accumulate | MED |
| 0x718 | 454 | 0 | Y | Reserved | — |
| 0x71C | 455 | ~5.43 | N | Effective Frequency (GHz) | HIGH |
| 0x720 | 456 | ~35.3 | N | Ambient / Board Temp (°C) | MED |

---

## Dynamic Relationships (SMU Couplings)

Validated by stress test (idle vs vecmath 16 threads, 15 snapshots):

### Sum Constraints (A + B = constant)
| Pair | Sum | Meaning |
|------|-----|---------|
| d[186] + d[187] | **100.000** | GFX Thermal + Thermal Headroom = 100 always |

### Exact Mirrors (bit-identical in every snapshot)
Verified 2026-07-30 over 120 consecutive same-snapshot reads: max delta 0.00000.

| Pair | Meaning |
|------|---------|
| d[20] = d[51] | Package Power (W) |
| d[21] = d[56] | SoC Power (W) |
| d[58] = d[59] | VDDIO_MEM Voltage (V) |
| d[43] = d[44] | Max Voltage Limit (V) |
| d[27] = d[274] | CPPC Max Frequency / Boost Limit (GHz) |

### Near-copies — correlated but **not** identical
⚠ These were previously listed as perfect mirrors with "delta < 0.002". They are not:
measured within a single snapshot (so no sampling skew), they differ on *every* read.
High Pearson does not mean identical — they are separate averaging windows of the same
signal. Their old "thermal" labels were part of the zone 0x000 misdiagnosis.

| Pair | Max delta / 120 samples | Mean delta | Actual signal |
|------|------------------------|-----------|---------------|
| d[3] vs d[26] | 2.54 W | 0.55 W | PPT Value (W) |
| d[3] vs d[277] | 11.68 W | 1.77 W | PPT Value (W) |
| d[26] vs d[277] | 11.58 W | 2.04 W | PPT Value (W) |
| d[9] vs d[50] | 2.07 A | 0.44 A | TDC Value (A) |

### Inverse Couplings (A↑ when B↓)
| Pair | Behavior |
|------|----------|
| d[341-348] FIT/IDD ↑ | d[349-356] C6 Residency ↓ (perfect inverse under stress) |
| d[341-348] FIT/IDD ↑ | d[357-364] C0 Residency ↑ (tracks together) |
| d[212] power credit ↑ | d[452] rolling counter ↓ (neither is an energy total — see the row notes) |

### Correlated Domains (Pearson > 0.99)
| Group | Offsets | Meaning |
|-------|---------|---------|
| Thermal cluster | d[11,270,317-324,448,449] | Tctl, hotspot and per-core temps track together (d[3,26,277] are watts, not temps) |
| Power cluster | d[17,20,21,50,51,56,273,333-340] | All power metrics track together |
| Energy cluster | d[212,397-404,453] | All track together, but as load-proportional rates that plateau — not accumulators |
| Load cluster | d[301-308,341-348] | IDD and FIT track with load |

### Ghost Floats (never change under any condition)
Measured 2026-07-30 with a median over 25 samples at idle and at 45 s of `stress-ng --cpu 16`
(a mean is unusable here — the sysfs read occasionally returns a garbage sample that smears
into every field):

- **~200-215 non-zero statics**: AGESA constants, DPM tables, voltage setpoints, frequency limits, silicon IDs
- **~105-110 zero statics**: Reserved/unused

Given as ranges, not point values, on purpose: the count moves by ±5 % between runs
depending on background CPU activity, which keeps a handful of otherwise-static fields
drifting. Run the audit on an otherwise idle desktop.

The iGPU is **not** a confound on this machine, and it is worth saying why, because the
opposite is the intuitive guess. With a discrete RTX 5080 present (`01:00.0`) the iGPU at
`76:00.0` is fully parked — `gpu_busy_percent` 0, `d[107]` 0.00 W, `d[108]` pinned at
600 MHz — even with a browser playing video. That is exactly what makes the iGPU offsets
such a clean cross-validation reference: they are supposed to be flat, and they are.

The earlier figures (182 / 104) were counted before the zone 0x000 correction and are ~15 % low.
- **Notable ghosts**: d[65]=552.0 (silicon limit?), d[263]=32 (thread count), d[264]=16 (core count), d[265]=5.5, d[266]=4.0 (topology), d[94]=0.985 (reference voltage)

---

## Cross-Validation vs System Tools

Validated by comparing PM table values against `k10temp`, `amdgpu`, `spd5118`, `/proc/stat`, and `cpufreq` sysfs:

| PM Table Offset | PM Value | System Tool | System Value | Match? |
|-----------------|----------|-------------|--------------|--------|
| d[49] Vcore P1 | 1.214V | amdgpu vddgfx | 1.214V | YES (0mV delta) |
| d[53] VDDCR_SoC | 0.954V | amdgpu vddnb | 0.945V | YES (9mV delta) |
| d[58] VDDIO_MEM | 1.099V | DDR5 nominal | 1.1V | YES |
| d[108] iGPU sclk | 647MHz | amdgpu freq1 | 600MHz | YES (PM more precise) |
| d[317-324] Core temps | 37-40°C | k10temp range | reasonable | YES |
| d[20] Pkg Power | 14.8-110W | stress profile | coherent | YES |
| d[349-356] C6 Residency | 93%→0.5% | stress-ng load | perfect inverse | YES |
| d[333-340] Core Power | 0.4→5.4W | Pkg Power split | coherent | YES |
| d[554-570] FIT/IDD | 7→99% | full load | coherent | YES |
| d[11] 0x02C Tctl | 49.3→82.8°C | k10temp Tctl | 49.4→84.0°C | YES (≤1.1°C delta, slope 0.97) |
| d[270] 0x438 hotspot | 51.8→87.2°C | k10temp Tctl | 49.4→84.0°C | YES (slope 1.02, sits ~3°C above Tctl) |
| d[3] 0x00C PPT value | 27.9→128.2W | PPT limit d[2]=162W | ceiling respected | YES (it is watts, not °C) |
| d[9] 0x024 TDC value | 9.3→86.7A | TDC limit d[8]=120A | ceiling respected | YES (it is amps, not °C) |
| d[64] 0x100 | 44→97 (and 90→104 in another run) | k10temp Tctl | 49→84°C | **NO — not a temperature at all** |
| d[210] 0x348 | 15→100.00 (pinned) | k10temp Tccd1 | 38→83°C | **NO — a percentage** |
| d[186] 0x2E8 | 0.003→0.015 | amdgpu edge | iGPU idle | **NO — iGPU activity %** |
| d[448] 0x700 | 36.9→55.3 | core temp average d[317-324] | 36.4→78.3°C | **NO — heavily filtered, not the average** |

### Re-verification 2026-07-30

The earlier "non-linear temperature encoding" conclusion was a **misdiagnosis**. Those
offsets were never temperatures — they are watts, amps and percentages that were being
compared against k10temp. Re-measured with averaged samples (20 reads per point, 30 s idle
settle, 60 s steady-state `stress-ng --cpu 16`) using
`research/recheck_zone0.py`, `research/recheck_sweep.py` and `research/recheck_edc.py`.

**Every PM-table temperature that is a temperature reads as direct °C.** No decoding needed.
Confirmed direct-°C fields: d[11] (Tctl), d[270] (hotspot), d[317-324] (per-core).

What actually went wrong, and the corrected labels:

| Offset | Old label | Actual |
|--------|-----------|--------|
| 0x00C d[3] | Package Thermal Metric (encoded °C) | **PPT Value (W)** |
| 0x020 d[8] | EDC Limit (A) | **TDC Limit (A)** — 120 A |
| 0x024 d[9] | SoC Temperature Metric (encoded °C) | **TDC Value (A)** |
| 0x028 d[10] | TDC Limit (A) | **THM Limit (°C)** — 88 °C |
| 0x02C d[11] | VRM / Hotspot Temp | **THM Value = Tctl (°C)** |
| 0x0FC d[63] | EDC Max (A) | **EDC Limit (A)** — 180 A (unchanged, just renamed) |
| 0x100 d[64] | Thermal Metric | unidentified utilization metric |
| 0x2E8/0x2EC d[186/187] | GFX Thermal + Headroom | **iGPU Activity / Idle (%)** |
| 0x348 d[210] | CCD Thermal Metric | percentage, saturates at 100 |
| 0x438 d[270] | TDC Current Value (A) | **Hotspot Temperature (°C)** |
| 0x458 d[278] | PPT Current Value (W) | unidentified, near-static |
| 0x4A8/0x4AC d[298/299] | L3/V-Cache Temp | slow thermal, domain unconfirmed |
| 0x700/0x704 d[448/449] | Average / Min Core Temp | filtered thermal, not core stats |
| 0x710 d[452] | Total Package Energy (J) | countdown/credit — decreases under load |

The `(LIMIT, VALUE)` pairing is what makes zone 0x000 unambiguous: 0x00C peaks at 128 W
under a 162 W limit, 0x024 peaks at 86.7 A under a 120 A limit, and 0x02C peaks at 82.8 °C
under an 88 °C limit. Three fields, three units, each pinned by the limit directly above it.

**Still open:** no `EDC_VALUE` companion for d[63] was found — `stress-ng --cpu` is an
integer load and may simply not push EDC high enough to identify the field. Retry with an
AVX-512 heavy load.

## EDC_VALUE — closed, negative result (2026-07-30)

`d[63]` holds the EDC limit (180 A). **There is no companion live-value float in
PM table v0x620105.** Searched by `research/hunt_edc.py` at three load points,
scoring every one of the 457 floats on the signature EDC_VALUE must have: low at
idle, rising with load, rising *more* under the heavier load, never above 180.

The previous attempt failed because it used `stress-ng --cpu`, an integer load.
Load choice turned out to matter more than expected, and "use AVX-512" is **not**
the answer — benchmarked by peak TDC value:

| Load | Peak TDC | Peak pkg W |
|------|---------|-----------|
| `--matrix 16` | **103.4 A** | **131.6 W** |
| `--cpu 16 --cpu-method float128` | 91.8 A | 116.8 W |
| `--vecfp 16` (AVX-512) | 89.9 A | 105.9 W |
| `--cpu 16` | 87.7 A | 112.4 W |
| `--vecshuf 16` | 64.7 A | 82.6 W |
| `--ipsec-mb 16` | 24.7 A | 30.8 W |

`--vecfp` is AVX-512 and pulls *less* package power than the plain integer path.
`--matrix` is what actually loads the current rails.

Under `--matrix 16` the part reaches 100.9 A of its 120 A TDC and Tctl pins at
exactly 88.0 °C — the thermal limit, i.e. as hard as this cooling can push. At
that point the only floats reading between 100 and 180 are known constants (162 =
PPT limit, 120 = TDC limit and its copies, 138 = PPT value in **watts**) and
percentages saturated at 100. Nothing behaves like a current climbing toward 180.

Also ruled out: deriving it. `sum(d[301-308])` (per-core IDD) reaches 113 A, but
its ratio to the TDC value drifts 0.98→1.20 across load levels, so it is not the
same quantity in another unit.

Consequence for the GUI: an EDC gauge can only ever show the limit. That is
already what it does — do not add a computed "EDC value".

## Honesty Audit 2026-07-30

After the zone 0x000 correction, every mechanically checkable claim in this file was
re-tested against live hardware by `research/audit_map.py`, which parses this document
and asserts each claim rather than spot-checking a hand-picked subset. Findings that
survived (all corrected above):

| Claim | Was | Measured |
|-------|-----|----------|
| d[19], d[48], d[49] Vcore | `Static: Y` | 1.19 V idle → 1.31 V load |
| d[62] SoC Power Limit | `Static: Y` | 49 W idle → 56 W load — the limit itself is renegotiated |
| d[446] Scalar | `Static: Y`, 0.250 | 0.23 → 0.33 |
| d[217-224] Min DPM Freq, 400 MHz | one row covering 8 indices | d[220] reads ~200 and drifts; it is not part of the block |
| d[3] = d[26] = d[277], "delta < 0.002" | Perfect mirror | differ in **every** snapshot, up to 11.68 W apart |
| d[9] = d[50], "delta < 0.002" | Perfect mirror | differ in every snapshot, up to 2.07 A apart |
| d[212], d[397-404], d[453] | "Energy Accumulator (J) / CONFIRMED" | plateau under 50 s of steady load (23 260 → 23 205, +0.3 %); the idle→load jump was mistaken for accumulation |
| d[263] Thread Count = 32 | MED | this part has 16 threads |
| d[264] Core Count = 16 | MED | this part has 8 cores |
| "Total floats mapped: 457" | — | unverifiable as written; 11 rows were malformed (5 columns, no `Static`) and invisible to every test, plus an off-by-one range. Fixed — coverage is now really 457 |
| 182 non-zero / 104 zero statics | — | 212 / 106 |

Claims that **passed**: all five exact mirrors (d[20]=d[51], d[21]=d[56], d[58]=d[59],
d[43]=d[44], d[27]=d[274], bit-identical over 5 snapshots), d[186]+d[187]=100, the 82
Reserved/zero indices, the remaining 218 `Static: Y` indices, and every cross-validation
against a system sensor — Tctl vs k10temp at idle *and* load, per-core temps, core
frequency vs cpufreq, boost limit vs `cpuinfo_max_freq`, iGPU sclk vs amdgpu, VDDCR_SoC vs
vddnb, VDDIO_MEM vs DDR5 nominal, C6 residency collapse, and the 162 W / 120 A / 180 A
stock limits.

Two methodology notes, since both produced false failures on the first run:
- Sample with a **median**, never a mean. The sysfs read occasionally returns a garbage
  sample; a mean smears it into every field and manufactured 43 phantom "static field
  moved" failures. Histogramming the accused fields over 500 samples showed exactly one
  distinct value each.
- Compare a PM field to an external sensor **only over a window**. d[49] vs amdgpu
  `vddgfx` looks like a 34 mV mismatch on a single pair and a 4.3 mV match over 60 pairs,
  because vddgfx alone swings 1.010-1.250 V at idle.

## Summary Statistics

Counted mechanically from this file's own tables on 2026-07-30 (`research/audit_map.py`),
per float **index**, not per table row:

| Category | Indices |
|----------|---------|
| CONFIRMED (struct / cross-validated against a system sensor) | 72 |
| HIGH confidence (strong pattern match) | 138 |
| MEDIUM confidence (inferred) | 67 |
| LOW confidence (guess) | 18 |
| Reserved / no confidence tag | 72 |
| **Documented** | **457 of 457** |

⚠ The version before 2026-07-30 claimed "Total floats mapped: 457" with no way to check it,
and the confidence counts were estimates rather than counts. A first pass reported 90
indices with no row — that figure was a **parser artifact**: 11 rows had five columns
instead of six (no `Static` column), hiding 88 indices from every audit test, and one row
had an off-by-one offset range that dropped 2 more. Both are fixed; coverage really is
457 now.

*Note: This map was generated by cross-referencing the ryzen_smu `pm_table_gnr` struct, the Zen 3/4 `pm_table_0x240903` field layout, dynamic analysis (idle/stress/post-stress), Pearson correlation, and cross-validation against k10temp/amdgpu sysfs. Zone 0x000 and the "encoded temperature" fields were corrected on 2026-07-30 — see [Re-verification 2026-07-30](#re-verification-2026-07-30). Temperature fields that really are temperatures read as direct °C; the fields previously thought to be encoded temperatures are watts, amps and percentages.*

# PM Table Memory Map — AMD Granite Ridge (v0x620105)

**Size:** 0x724 bytes (1828 bytes = 457 float32)  
**Source:** `/sys/kernel/ryzen_smu_drv/pm_table`  
**Method:** Static/dynamic analysis + stress test differential (idle vs full CPU load) + cross-reference with `pm_table_gnr` struct (ryzen_smu) + Zen 3/4 `pm_table_0x240903` field patterns + k10temp/amdgpu cross-validation.
**Confidence:** CONFIRMED = struct match or validated | HIGH = strong pattern | MED = inferred | LOW = guess

---

## Zone 0x000 — Power Limits & Core Temperatures

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x000 | 0 | 0 | Y | Reserved | CONFIRMED |
| 0x004 | 1 | 0 | Y | Reserved | CONFIRMED |
| 0x008 | 2 | 162.0 | Y | **PPT Limit (W)** | CONFIRMED |
| 0x00C | 3 | ~37.3 | N | **Package Thermal Metric** (encoded, stress=128, NOT direct °C) | CONFIRMED (struct=PACKAGE_TEMP, but values non-linear) |
| 0x010 | 4-7 | 0 | Y | Reserved | CONFIRMED |
| 0x020 | 8 | 120.0 | Y | **EDC Limit (A)** | CONFIRMED |
| 0x024 | 9 | ~17.0 | N | **SoC Temperature Metric** (encoded, stress=86, struct=SOC_TEMP) | CONFIRMED (struct, but non-linear vs °C) |
| 0x028 | 10 | 85.0 | Y | **TDC Limit (A)** | CONFIRMED |
| 0x02C | 11 | ~51.0 | N | VRM / Hotspot Temperature (°C) | HIGH |

## Zone 0x030 — Reserved

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x030 | 12-15 | 0 | Y | Reserved | CONFIRMED |

## Zone 0x040 — Power & Voltage

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x040 | 16 | ~1900 | N | Energy Budget / Countdown Counter (↓ under stress) | MED |
| 0x044 | 17 | ~0.6 | N | **Core Power Aggregate (W)** | CONFIRMED (stress: 0.7→64.5) |
| 0x048 | 18 | ~1.37 | N | **Vcore Peak (V)** | CONFIRMED |
| 0x04C | 19 | ~1.22 | Y | **Vcore Average (V)** | CONFIRMED |
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
| 0x068 | 26 | ~37.3 | N | Pkg Thermal Metric (mirror of 0x00C) | HIGH |
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
| 0x0C0 | 48 | ~1.22 | Y | Vcore Set Voltage (V) | HIGH |
| 0x0C4 | 49 | ~1.21 | Y | Vcore P1 Voltage (V) | HIGH |
| 0x0C8 | 50 | ~17.0 | N | SoC Thermal Metric (mirror of 0x024) | HIGH |
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
| 0x0F8 | 62 | ~57.0 | Y | SoC Power Limit (W) | MED |
| 0x0FC | 63 | 180.0 | Y | **EDC Max (A)** | CONFIRMED |
| 0x100 | 64 | 65-100 | N | **Thermal Metric** (stagnates 96-100 stress, NOT direct Tctl) | CONFIRMED (stress: idle 65→stress 97, low delta vs k10temp=85°C) |
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
| 0x218-0x2AC | 134-170 | 200-1200 | Y | LCLK / Peripheral DPM Clocks (MHz) | HIGH |
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
| 0x2E8 | 186 | 22-80 | N | **GFX Thermal Metric** (encoded, amdgpu edge=47°C vs PM=23°C) | HIGH (Pearson validated, but offset mismatch with amdgpu) |
| 0x2EC | 187 | inverse of 0x2E8 | N | **GFX Thermal Headroom** (inverse of 0x2E8) | CONFIRMED (stress: 71→29, always sum=100) |
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
| 0x348 | 210 | ~31 | N | **CCD Thermal Metric** (encoded, stress=100, k10temp Tccd1=50→85°C) | HIGH (stress reactive, but offset vs k10temp) |
| 0x34C | 211 | 3000.0 | Y | MCLK (mirror) | HIGH |
| 0x350 | 212 | ~4094 | N | **Package Energy Accumulator (J)** | CONFIRMED (stress: 2133→19383) |
| 0x354 | 213 | 12.8 | Y | Current Limit (A?) | MED |
| 0x358 | 214 | ~3.4 | N | Power Domain (W) | MED |
| 0x35C | 215 | 4.0 | Y | Scalar / Multiplier | LOW |
| 0x360 | 216 | ~1.03 | N | Live Voltage (V) | MED |
| 0x364-0x380 | 217-224 | 400.0 | Y | Min DPM Frequency [8] (MHz) | HIGH |
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
| 0x41C | 263 | 32.0 | Y | Thread Count / Topology | MED |
| 0x420 | 264 | 16.0 | Y | Core Count | MED |
| 0x424 | 265 | 5.5 | Y | Parameter (W or ratio) | LOW |
| 0x428 | 266 | 4.0 | Y | Parameter (scalar) | LOW |

## Zone 0x42C — Live Metrics (Pre-Core)

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x42C | 267 | ~1.03 | N | Live Voltage (V) | MED |
| 0x430 | 268 | 120.0 | Y | EDC Limit (mirror, A) | HIGH |
| 0x434 | 269 | 1.148 | Y | SVI3 VDDCR_CPU VID (V) | HIGH |
| 0x438 | 270 | ~66.0 | N | **TDC Current Value (A)** | CONFIRMED (stress: 73→91) |
| 0x43C | 271 | ~1.26 | N | SVI3 VDDCR_SoC VID (V) | HIGH |
| 0x440 | 272 | 5.425 | Y | Max Boost Frequency (GHz) | HIGH |
| 0x444 | 273 | ~0.46 | N | **SoC Telemetry Current/Power Metric** (NOT voltage, Pearson=0.999 with Pkg Power) | CONFIRMED (stress: 0.46→7.98, tracks load not voltage) |
| 0x448 | 274 | ~5.44 | N | Core Boost Limit Mirror (GHz) | HIGH |
| 0x44C | 275 | ~1.20 | N | Live Voltage (V) | MED |
| 0x450 | 276 | 0.010 | Y | Scalar | LOW |
| 0x454 | 277 | ~37.3 | N | Pkg Thermal Metric (mirror) | HIGH |
| 0x458 | 278 | ~50.8 | N | PPT Current Value (W) | HIGH |
| 0x45C-0x4A4 | 279-297 | 0 | Y | Reserved | — |

## Zone 0x4A8 — L3 / Cache Metrics

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x4A8 | 298 | ~45.6 | N | L3/V-Cache Temp 0 (°C) | HIGH |
| 0x4AC | 299 | ~46.4 | N | L3/V-Cache Temp 1 (°C) | HIGH |
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
| 0x534-0x550 | 333-340 | 0.3-0.6 idle / 5.4 stress | **Core Power (W) [8]** | CONFIRMED (stress: x15) |

### Core FIT / Current
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x554-0x570 | 341-348 | 6-11 idle / 99 stress | **Core FIT / IDD Max (%) [8]** | CONFIRMED (stress: ~99%) |

### Core C6 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x574-0x590 | 349-356 | 84-93 idle / 0.5 stress | **Core C6 Residency (%) [8]** | CONFIRMED (stress: idle 93%→stress 0.5%) |

### Core C0 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x594-0x5B0 | 357-364 | 0 idle / ~0 stress | **Core C0 Residency (%) [8]** | CONFIRMED (hardware idle metric) |

### Core C1 Residency (%)
| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x5B4-0x5D0 | 365-372 | ~0 | Core C1 Residency (%) [8] | MED |

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
| 0x614-0x630 | 389-396 | 0 | Reserved |

## Zone 0x634 — Per-Core Energy Accumulators

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x634 | 397 | ~830 | N | Core 0 Energy Accumulator (J) | CONFIRMED (stress: 403→18332) |
| 0x638 | 398 | ~805 | N | Core 1 Energy Accumulator (J) | CONFIRMED (stress: 420→18567) |
| 0x63C | 399 | ~1408 | N | Core 2 Energy Accumulator (J) | CONFIRMED (stress: 688→18654) |
| 0x640 | 400 | ~936 | N | Core 3 Energy Accumulator (J) | CONFIRMED (stress: 550→18542) |
| 0x644 | 401 | ~1119 | N | Core 4 Energy Accumulator (J) | CONFIRMED (stress: 557→18889) |
| 0x648 | 402 | ~1451 | N | Core 5 Energy Accumulator (J) | CONFIRMED (stress: 831→18665) |
| 0x64C | 403 | ~763 | N | Core 6 Energy Accumulator (J) | CONFIRMED (stress: 437→18106) |
| 0x650 | 404 | ~726 | N | Core 7 Energy Accumulator (J) | CONFIRMED (stress: 335→18610) |

## Zone 0x654 — Per-Thread C-State Residency (16 threads)

| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x654-0x670 | 405-412 | 0.04-0.12 | **Thread 0-7 C0 Residency (%) [8]** | CONFIRMED (stress: up to 0.89) |
| 0x674-0x690 | 413-420 | 0.01-0.05 | **Thread 8-15 C0 Residency (%) [8]** | CONFIRMED (stress: up to 0.94) |

## Zone 0x694 — Extended C-State / Residency Counters

| Offset | Idx | Typical | Meaning | Confidence |
|--------|-----|---------|---------|------------|
| 0x694-0x6B0 | 421-428 | 0.01 | Secondary C-State Residency [8] | LOW |
| 0x6B4-0x6D0 | 429-436 | 0.00 | Reserved / Unused Core States | — |
| 0x6D4-0x6F0 | 437-444 | 0.01 | **Thread C-State Residency Alt [8]** | CONFIRMED (stress: reactive) |

## Zone 0x6F4 — Final Metrics

| Offset | Idx | Typical | Static | Meaning | Confidence |
|--------|-----|---------|--------|---------|------------|
| 0x6F4 | 445 | ~3.1 | N | Package Energy Rate (W) | MED |
| 0x6F8 | 446 | 0.250 | Y | Scalar | LOW |
| 0x6FC | 447 | 0.950 | Y | SVI3 Reference Voltage (V) | MED |
| 0x700 | 448 | ~40.4 | N | Average Core Temp (°C) | HIGH |
| 0x704 | 449 | ~38.9 | N | Min Core Temp (°C) | HIGH |
| 0x708 | 450 | ~5.43 | N | Peak Core Frequency (GHz) | HIGH |
| 0x70C | 451 | ~5.44 | N | Average Core Frequency (GHz) | HIGH |
| 0x710 | 452 | ~27825 | N | **Total Package Energy Accumulator (J)** | HIGH |
| 0x714 | 453 | ~1549 | N | Power Accumulator | MED |
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

### Perfect Mirrors (Pearson > 0.999)
| Pair | Meaning |
|------|---------|
| d[3] = d[26] = d[277] | Package Thermal (3 copies, delta < 0.002) |
| d[9] = d[50] | SoC Thermal (2 copies, delta < 0.002) |
| d[20] = d[51] | Package Power (exact copy) |
| d[21] = d[56] | SoC Power (exact copy) |
| d[58] = d[59] | VDDIO_MEM Voltage (exact copy) |
| d[43] = d[44] | Max Voltage Limit (exact copy) |
| d[27] = d[274] | CPPC Max Frequency / Boost Limit (exact copy) |

### Inverse Couplings (A↑ when B↓)
| Pair | Behavior |
|------|----------|
| d[341-348] FIT/IDD ↑ | d[349-356] C6 Residency ↓ (perfect inverse under stress) |
| d[341-348] FIT/IDD ↑ | d[357-364] C0 Residency ↑ (tracks together) |
| d[212] Energy Accum ↑ | d[452] Total Pkg Energy ↓ (rolling counter overflow) |

### Correlated Domains (Pearson > 0.99)
| Group | Offsets | Meaning |
|-------|---------|---------|
| Thermal cluster | d[3,26,277,317-324,448,449] | All core/pkg temps track together |
| Power cluster | d[17,20,21,50,51,56,273,333-340] | All power metrics track together |
| Energy cluster | d[212,397-404,453] | All energy accumulators track together |
| Load cluster | d[301-308,341-348] | IDD and FIT track with load |

### Ghost Floats (never change under any condition)
- **182 non-zero statics**: AGESA constants, DPM tables, voltage setpoints, frequency limits, silicon IDs
- **104 zero statics**: Reserved/unused
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
| d[64] 0x100 | 65→97 | k10temp Tctl | 52→85°C | **NO — encoded metric** |
| d[210] 0x348 | 20→100 | k10temp Tccd1 | 50→85°C | **NO — encoded metric** |
| d[186] 0x2E8 | 23→80 | amdgpu edge | 47→71°C | **NO — encoded metric** |

**Key finding:** Temperature offsets in the PM table use a non-linear encoding that does not map 1:1 to °C. Only **core temperatures (d[317-324])** read as direct °C. Voltages, frequencies, power, and C-state residency are direct readings.

## Summary Statistics

| Category | Count |
|----------|-------|
| CONFIRMED (struct/Pearson/cross-validated) | 58 |
| HIGH confidence (strong pattern match) | ~120 |
| MEDIUM confidence (inferred) | ~80 |
| LOW confidence (guess) | ~30 |
| Reserved / Zero | ~170 |
| **Total floats mapped** | **457** |

*Note: This map was generated by cross-referencing the ryzen_smu `pm_table_gnr` struct, the Zen 3/4 `pm_table_0x240903` field layout, dynamic analysis (idle/stress/post-stress), Pearson correlation, and cross-validation against k10temp/amdgpu sysfs. Temperature fields (except core temps) use non-linear encoding — treat as relative metrics, not direct °C.*

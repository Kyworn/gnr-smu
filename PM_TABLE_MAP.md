# PM Table Memory Map — AMD Granite Ridge (v0x620105)

Based on the raw float32 sysfs dump (April 11, 2026).

| Offset (Hex) | Typical Value | Probable Meaning |
|--------------|----------------|-------------------------|
| 0x008        | 162.0          | **PPT Limit (W)**       |
| 0x00C        | 35.8           | Package Temperature (°C)|
| 0x020        | 120.0          | **EDC Limit (A)**       |
| 0x024        | 17.2           | SoC Temperature (°C)    |
| 0x028        | 85.0           | **TDC Limit (A)**       |
| 0x048        | 1.37           | Vcore Peak (V)          |
| 0x04C        | 1.21           | Vcore Average (V)       |
| 0x050        | 20.8           | Package Power (W)       |
| 0x0FC        | 180.0          | EDC Max ?               |
| 0x100        | 35.0 - 56.0    | **SoC / iGPU Temp (°C)**|
| 0x11C        | 2000.0         | **FCLK (Fabric Clock)** |
| 0x12C        | 3000.0         | **UCLK (Memory Ctrl)**  |
| 0x13C        | 3000.0         | **MCLK (Memory Clock)** |
| 0x1AC        | ~ 4.09         | **iGPU Power (W)**      |
| 0x1B0        | 600.0          | **iGPU Clock (sclk)**   |
| 0x1B4        | ~ 142.9        | **iGPU Load / VRAM ?**  |
| 0x1B8        | ~ 17.8         | **iGPU Amperage ? (A)** |
| 0x2E8        | 43.5 - 68.1    | **GFX Junction Temp (°C)** |
| 0x560        | ~20 - 100+     | *Unk / CPU Core Power ?* |
| 0x568        | ~10 - 45+      | *Unk / CPU Metric ?* |

### Per-Core Data (8 Cor​​es Detected) :

- **Core Temperatures:** Starts at **0x4F4**
  - C0: 39.3°C, C1: 36.3°C, C2: 46.4°C, C3: 37.5°C...
- **Core Voltages:** Starts at **0x4D4** (around 1.17V - 1.20V)
- **Core Frequencies (Boost):** Starts at **0x514** (5.16 GHz, 5.05 GHz...)

*Note: This memory mapping table is the primary key for real-time telemetry monitoring without relying on proprietary tools.*

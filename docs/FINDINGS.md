# Reverse Engineering SMU Granite Ridge — Findings

**Platform:** AMD Ryzen 7 9800X3D (Zen 5, family 0x1A model 0x44)  
**Kernel:** 6.19.11-1-cachyos | **SMU version:** 98.75.0

---

## 1. Mailbox — Addresses (Source: SSDT1)

| Mailbox | MSG (Cmd) | RSP (Status) | ARG0 (Data) | Usage |
|---------|-----------|--------------|----------------|-------|
| **MP1** | 0x3B10530 | 0x3B1057C    | 0x3B109C4      | Power Limits (PPT, TDC, EDC) |
| **RSMU**| 0x3B10524 | 0x3B10570    | 0x3B10A40      | Tables & Telemetry |

---

## 2. Telemetry Access (`ryzen_smu`)

We migrated completely to the official [ryzen_smu](https://github.com/amkillam/ryzen_smu) kernel driver, deprecating our temporary custom module.
- Hardware boundaries are applied by pushing unsigned 32-bit payloads to `/sys/kernel/ryzen_smu_drv/smu_args` followed by the MSG ID to `mp1_smu_cmd`.
- Telemetry table is polled natively from `/sys/kernel/ryzen_smu_drv/pm_table`.

---

## 3. PM Table — Map (v0x620105)

Full size: `0x724` bytes. Fetched continuously alongside core metrics.
For a complete variable-to-byte mapping, reference **[PM_TABLE_MAP.md](../PM_TABLE_MAP.md)**.

*Notable discoveries via Pearson Correlation + cross-validation:*
- **iGPU Clock (sclk):** Offset `0x1B0` — validated vs amdgpu freq1_input.
- **iGPU Power (W):** Offset `0x1AC`.
- **Core Temperatures (°C):** Offsets `0x4F4-0x510` — only direct °C readings validated in the entire table.
- **VDDCR_SoC:** Offset `0x0D4` (0.954V) — matches amdgpu vddnb (0.945V, 9mV delta).
- **Vcore P1:** Offset `0x0C4` (1.213V) — matches amdgpu vddgfx (1.220V).
- **VDDIO_MEM:** Offset `0x0E8` (1.099V) — matches DDR5 1.1V nominal.

**⚠ Temperature encoding caveat:** Offsets `0x00C`, `0x024`, `0x100`, `0x2E8`, `0x348` are thermal *metrics* with non-linear encoding — they do NOT map 1:1 to °C. Only core temps (`0x4F4-0x510`) are direct °C. Cross-validated against k10temp and amdgpu sysfs.

---

## 4. Message IDs — Command Table

### 4a. Power Limits (MP1)
- **0x3E:** Set PPT Limit (mW)
- **0x3C:** Set EDC Limit (mA)
- **0x3D:** Set TDC Limit (mA)  *(Note: Hardlocked by firmware limits on 9800X3D to prevent thermocollapse)*

### 4b. Curve Optimizer (MP1)
- **0x50 to 0x57:** Per-core optimization (C0 to C7).
- **ARG0 Format:** Signed 32-bit integer (e.g., -30 = `0xFFFFFFE2`). Write-only, requires local JSON caching for GUI persistence.

---

## 5. ⚠ Documented Traps

1.  **MSG 0x10 (MP1):** Causes an **immediate loss of display output** (GPU Power Gate / Crash).
2.  **`monitor_cpu -f`:** Completely incompatible with Granite Ridge architecture. Triggers an instantaneous Green/Black screen crash.
3.  **Blind DMA Probing:** Never randomly poke IDs 0x03-0x0D on MP1. High risk of bus halting.
# AMD Granite Ridge (Zen 5) SMU & Telemetry Tools

This repository contains tools and findings from reverse engineering the System Management Unit (SMU) of the **AMD Ryzen 9 9800X3D** (Granite Ridge, Family 0x1A, Model 0x44).

## 🚀 Key Discoveries

- **Mailboxes identified:**
  - **MP1 (Power/Limits):** `0x3B10530`
  - **RSMU (Tables/Telemetry):** `0x3B10524`
- **PM Table (Telemetry):** Full mapping of the 0x724 byte structure (v0x620105).
- **Curve Optimizer:** Confirmed Message IDs `0x50` to `0x57` for per-core undervolting.
- **Power Limits:** Validated IDs for PPT, TDC, EDC, and TjMax.

## 🛠 Tools Included

- `gnr_monitor`: A native C monitor that reads real-time telemetry (V, W, °C, MHz) via the `ryzen_smu` driver.
- `smu_advanced.py`: Python utility to send commands to both MP1 and RSMU mailboxes.
- `PM_TABLE_MAP.md`: Detailed documentation of the telemetry table offsets.

## 📋 Requirements

- **Linux Kernel** (Tested on 6.19-cachyos).
- **[ryzen_smu](https://github.com/amkillam/ryzen_smu)** driver must be loaded.
- `setpci` (pciutils) for raw SMN access.

## ⚠ Safety Warning

**Use at your own risk.** Probing unknown SMU IDs can cause system instability or immediate display loss (e.g., ID `0x10` on MP1). Refer to `FINDINGS.md` for known traps.

---
*Reverse engineered by Zorko & Gemini CLI - April 2026*

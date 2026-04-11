# GNR-SMU : Granite Ridge SMU Control

Tools and kernel driver for AMD Granite Ridge (Zen 5) SMU management.

## 🚀 Key Discoveries

- **Dual Mailbox Architecture:**
  - **MP1 (Power/Limits):** `0x3B10530` - Used for global power management.
  - **RSMU (Tables/Telemetry):** `0x3B10524` - Used for telemetry and data tables.
- **PM Table Mapping:** Complete mapping of the `0x724` byte structure (version `0x620105`).
- **Curve Optimizer (CO):** Confirmed Message IDs `0x50` to `0x57` for per-core undervolting (32-bit signed integer format).
- **Power Limits:** Validated IDs for PPT, TDC, EDC, and TjMax.
- **Driver:** Custom kernel driver `gnr_smu` allows direct SMN access and exclusive messaging.

## 🛠 Tools

### 1. `gnr_monitor` (Native C)
A fast, reliable telemetry reader.
- **Usage:** `sudo ./gnr_monitor`

### 2. `smu_advanced.py` (Python)
Raw message mailbox utility.
- **Usage:** `sudo python3 smu_advanced.py ppt 85`

### 3. `gnr_smu` (Kernel Driver)
- **Usage:** `echo "MSG_ID ARG0" > /dev/gnr_smu`
- **Location:** `/driver/gnr_smu.c`

## 📖 Research Files
- [FINDINGS.md](./docs/FINDINGS.md): Exhaustive log of Message IDs, protocol details, and known safety traps.
- [PM_TABLE_MAP.md](./docs/PM_TABLE_MAP.md): Detailed byte-by-byte layout of the telemetry table.
- [TOFIX.md](./docs/TOFIX.md): Roadmap for remaining issues and enhancements.

## 📋 Prerequisites
- **Linux Kernel:** 6.10+
- **Driver:** Requires `ryzen_smu` for telemetry exposure.

---
*Reverse engineered by **Zorko** & **Gemini CLI** - April 2026*

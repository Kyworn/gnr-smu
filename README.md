# GNR-SMU : Granite Ridge SMU Control

Tools and kernel driver for AMD Granite Ridge (Zen 5) SMU management.

## 🚀 Key Discoveries

- **Dual Mailbox Architecture:**
  - **MP1 (Power/Limits):** `0x3B10530` - Used for global power management.
  - **RSMU (Tables/Telemetry):** `0x3B10524` - Used for telemetry and data tables.
- **PM Table Mapping:** Complete mapping of the `0x724` byte structure (version `0x620105`).
- **Curve Optimizer (CO):** Confirmed Message IDs `0x50` to `0x57` for per-core undervolting (32-bit signed integer format).
- **Power Limits:** Validated IDs for PPT, TDC, EDC, and TjMax.
- **Driver:** Custom kernel driver `gnr_smu` (Safe, Exclusive, Native Telemetry Reading).

## 🛠 Tools

### 1. `gnr_monitor` (Native C)
A fast, reliable telemetry reader using the custom driver.
- **Usage:** `sudo ./tools/gnr_monitor`

### 2. `smu_advanced.py` (Python)
Raw message mailbox utility.
- **Usage:** `sudo python3 tools/smu_advanced.py ppt 85` (Set PPT to 85W)

### 3. `gnr_smu` (Kernel Driver)
Custom kernel driver providing exclusive and safe access to the SMU via `/dev/gnr_smu`.
- **Read:** `hexdump -C /dev/gnr_smu` (Automatically triggers table refresh)
- **Write:** `echo "MSG_ID ARG0" > /dev/gnr_smu`
- **Location:** `/driver/gnr_smu.c`

## 📖 Research Files
- [FINDINGS.md](./docs/FINDINGS.md): Exhaustive log of Message IDs, protocol details, and known safety traps.
- [PM_TABLE_MAP.md](./docs/PM_TABLE_MAP.md): Detailed byte-by-byte layout of the telemetry table.
- [TOFIX.md](./docs/TOFIX.md): Roadmap for remaining issues.

## 📋 Prerequisites
- **Linux Kernel:** 6.10+ (Tested on 6.19-cachyos).
- **Tools:** `gcc`, `make` (kernel headers required).

## ⚠ Safety & Disclaimer
**This is experimental software.**
- **Known Trap:** Sending MSG `0x10` to MP1 causes immediate display loss.
- Using `gnr_smu` driver is safer than manual `setpci` as it implements mutex locking and message whitelisting.

---
*Reverse engineered by **Zorko** & **Gemini CLI** - April 2026*

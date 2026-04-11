# GNR-SMU : Granite Ridge SMU Control

Tools and kernel driver for AMD Granite Ridge (Zen 5) SMU management.

## 🚀 Key Discoveries

- **Dual Mailbox Architecture:**
  - **MP1 (Power/Limits):** `0x3B10530` - Used for global power management.
  - **RSMU (Tables/Telemetry):** `0x3B10524` - Used for telemetry and data tables.
- **PM Table Mapping:** Complete mapping of the `0x724` byte structure (version `0x620105`).
- **Curve Optimizer (CO):** Confirmed Message IDs `0x50` to `0x57` for per-core undervolting (32-bit signed integer format).
- **Power Limits:** Validated IDs for PPT, TDC, EDC, and TjMax.
- **Driver Development:** Custom kernel driver `gnr_smu` created for safe, exclusive access to SMU mailboxes.

## 🛠 Tools

### 1. `gnr_monitor` (Native C)
A lightweight, fast monitor that reads real-time telemetry directly from the SMU PM Table.
- **Features:** Per-core Voltage, Temperature, Clock Speed, and Power Limits.
- **Compilation:** `gcc -O2 tools/gnr_monitor.c -o tools/gnr_monitor`
- **Usage:** `sudo ./tools/gnr_monitor`

### 2. `smu_advanced.py` (Python)
A versatile script to send raw messages to both MP1 and RSMU mailboxes.
- **Usage:** `sudo python3 tools/smu_advanced.py ppt 85` (Set PPT to 85W)
- **Curve Optimizer:** `sudo python3 tools/smu_advanced.py raw --mb mp1 --msg 0x50 --arg 0xFFFFFFE2` (-30 CO on Core 0)

### 3. `gnr_smu` (Kernel Driver)
Custom kernel driver providing exclusive and safe access to the SMU via `/dev/gnr_smu`.
- **Interface:** Writes `MSG_ID ARG0` to `/dev/gnr_smu`.
- **Safety:** Implements mutex locking to prevent concurrent access and system crashes.

## 📖 Research Files
- [FINDINGS.md](./docs/FINDINGS.md): Exhaustive log of Message IDs, protocol details, and known safety traps.
- [PM_TABLE_MAP.md](./docs/PM_TABLE_MAP.md): Detailed byte-by-byte layout of the telemetry table.

## 📋 Prerequisites
- **Linux Kernel:** 6.10+ (Tested on 6.19-cachyos).
- **Tools:** `pciutils` (for `setpci`), `gcc`, `make` (kernel headers required).

## ⚠ Safety & Disclaimer
**This is experimental software.** Manipulating SMU registers can cause:
- Immediate system crash.
- Permanent hardware damage if unsafe voltages are applied.
- **Known Trap:** Sending MSG `0x10` to MP1 causes immediate display loss.

---
*Reverse engineered by **Zorko** & **Gemini CLI** - April 2026*

# GNR-SMU : Granite Ridge SMU Control

Tools and kernel driver for AMD Granite Ridge (Zen 5) SMU management.

## 🚀 Key Discoveries

- **Dual Mailbox Architecture:**
  - **MP1 (Power/Limits):** `0x3B10530` - Global power management (PPT/TDC/EDC).
  - **RSMU (Tables/Telemetry):** `0x3B10524` - Telemetry table transfer and CPU base address.
- **PM Table Mapping:** Successfully mapped the `0x724` byte telemetry table (version `0x620105`).
- **Telemetry Access:** Real-time data is natively exposed by the `ryzen_smu` driver at `/sys/kernel/ryzen_smu_drv/pm_table`.

## 🛠 Tools

### 1. `gnr_monitor` (Native C)
A fast, reliable telemetry reader. Reads the PM table directly from the driver exposed sysfs file.
- **Compilation:** `gcc -O2 tools/gnr_monitor.c -o tools/gnr_monitor`
- **Usage:** `sudo ./tools/gnr_monitor`

### 2. `monitor_gui.py` (GUI)
A lightweight Tkinter-based graphical interface for real-time telemetry.
- **Usage:** `sudo python3 tools/gui/monitor_gui.py`

### 3. `gnr_smu` (Kernel Driver)
Custom kernel driver providing exclusive and safe mailbox access.
- **Interface:** Write `MSG_ID ARG0` to `/dev/gnr_smu`.
- **Note:** The driver provides safe locking mechanisms to prevent system crashes (unlike raw `setpci` usage).

## 📖 Research Files
- [FINDINGS.md](./docs/FINDINGS.md): Exhaustive log of Message IDs, protocol details, and safety traps.
- [PM_TABLE_MAP.md](./docs/PM_TABLE_MAP.md): Detailed byte-by-byte layout of the telemetry table.
- [TOFIX.md](./docs/TOFIX.md): Roadmap for remaining issues.

## 📋 Prerequisites
- **Linux Kernel:** 6.10+
- **Driver:** [ryzen_smu](https://github.com/amkillam/ryzen_smu) driver must be loaded.
- **Dependencies:** `python-tk`, `gcc`, `make`.

## ⚠ Safety & Disclaimer
**This is experimental software.**
- **Known Trap:** Sending MSG `0x10` to MP1 causes immediate display loss.
- Always prefer reading telemetry via sysfs rather than triggering raw mailbox transfers.

---
*Reverse engineered by **Zorko** & **Gemini CLI** - April 2026*

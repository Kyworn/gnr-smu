# Remaining Tasks — GNR-SMU

## Resolved Issues

- [x] **Curve Optimizer (0x50-0x57)** — Validated format: Signed 32-bit int (e.g., -30 = `0xFFFFFFE2`). Successfully integrated into both CLI and GUI.
- [x] **EDC / TDC Reversal bug** — Validated via fuzzing that on Zen 5, `0x3C` is EDC and `0x3D` is TDC. GUI sliders swapped and fixed.
- [x] **Driver Transition** — Replaced the obsolete custom `gnr_smu` driver in favor of the official `ryzen_smu` endpoints (`/sys/kernel/ryzen_smu_drv/`).
- [x] **Frequency Mapping** — Confirmed that PM table offsets `0x514` provide direct GHz floats per core.
- [x] **iGPU Telemetry** — Isolated `0x1AC` (iGPU Power Wattage) and `0x1B0` (iGPU Clock) via Pearson Correlation modeling.

## Open Research (Low Priority)

- [ ] **IDs 0x58-0x5D** — Identify what these 6 sequential MSG IDs do after the 8 cores' Curve Optimizer arrays.
- [ ] **HSMP** — Explore if the Host System Management Port (HSMP) ACPI interface provides cleaner standard data for power limits than the direct mailbox polling.
- [ ] **Unidentified Floats** — Fully decode the remaining ~180 floats in the `0x724` telemetry block (e.g. C-state residencies).

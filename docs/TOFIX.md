# Remaining Tasks — GNR-SMU

## Resolved Issues

- [x] **Zone 0x000 mislabeled as temperatures (2026-07-30)** — the "non-linear temperature encoding" theory was a misdiagnosis. Zone `0x000` is the classic Zen `(LIMIT, VALUE)` pair layout: PPT `0x008`/`0x00C` (W), TDC `0x020`/`0x024` (A), THM `0x028`/`0x02C` (°C), EDC limit `0x0FC`. The limits read 162 W / 120 A / 180 A — exactly 9800X3D stock spec, which pins the identification. Consequence: the GUI was showing the thermal limit (88 °C) as "TDC 88 A" and the TDC limit (120 A) as "EDC 120 A", and pre-filling the MP1 write dialog with those wrong values. Fixed in `tools/gui/gnr_master.py`, `tools/export_telemetry.py`, `tools/verify_map.py`. Also corrected: `0x438` is a hotspot temperature, not TDC current; `0x348`/`0x100`/`0x2E8` are percentages, not thermal metrics. Evidence: `research/recheck_zone0.py`, `research/recheck_sweep.py`, `research/recheck_edc.py`.

- [x] **Curve Optimizer (0x50-0x57)** — Validated format: Signed 32-bit int (e.g., -30 = `0xFFFFFFE2`). Successfully integrated into both CLI and GUI.
- [x] **EDC / TDC Reversal bug** — Validated via fuzzing that on Zen 5, `0x3C` is EDC and `0x3D` is TDC. GUI sliders swapped and fixed.
- [x] **Driver Transition** — Replaced the obsolete custom `gnr_smu` driver in favor of the official `ryzen_smu` endpoints (`/sys/kernel/ryzen_smu_drv/`).
- [x] **Frequency Mapping** — Confirmed that PM table offsets `0x514` provide direct GHz floats per core.
- [x] **iGPU Telemetry** — Isolated `0x1AC` (iGPU Power Wattage) and `0x1B0` (iGPU Clock) via Pearson Correlation modeling.

## Open Research (Low Priority)

- [ ] **IDs 0x58-0x5D** — Identify what these 6 sequential MSG IDs do after the 8 cores' Curve Optimizer arrays.
- [ ] **HSMP** — Explore if the Host System Management Port (HSMP) ACPI interface provides cleaner standard data for power limits than the direct mailbox polling.
- [ ] **Unidentified Floats** — Fully decode the remaining ~180 floats in the `0x724` telemetry block (e.g. C-state residencies).
- [ ] **EDC_VALUE** — `0x0FC` holds the EDC *limit* (180 A) but no companion live-value float was found. A sweep for an offset climbing into 90-182 A under `stress-ng --cpu 16` turned up only known power/percent fields. Retry with an AVX-512 heavy load, which pushes current far harder than integer work.
- [ ] **Re-identify the demoted offsets** — `0x100`, `0x348`, `0x458`, `0x4A8`/`0x4AC`, `0x700`/`0x704`, `0x710` are confirmed *not* to be what the map used to claim, but their real meaning is still open.

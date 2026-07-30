# GNR-SMU

Telemetry map and SMU control tools for AMD Granite Ridge (Zen 5) under Linux.

![GNR-SMU Dashboard](assets/screenshot.png)

The `ryzen_smu` driver exposes a 1828-byte PM table at
`/sys/kernel/ryzen_smu_drv/pm_table` — 457 little-endian float32 values with no
published layout. This repo is the layout, worked out by measurement, plus the tools
that read and write it.

## Read this before running it on your machine

**Every offset here was measured on exactly one machine:** a Ryzen 7 9800X3D,
8 cores / 1 CCD, PM table version `0x620105`. Nothing is validated anywhere else.

That matters more than it sounds, because the failure mode is silent. A different
table version moves every offset, but the bytes still parse as 457 floats — so the
GUI shows plausible watts and degrees that are simply the wrong fields. A different
core count changes the per-core array widths; `d[317-324]` is 8 wide here, and on a
16-core part everything after it shifts.

So the tools check first ([`tools/hwgate.py`](tools/hwgate.py)) and refuse rather than
guess:

| | Validated hardware | Anything else |
|---|---|---|
| Telemetry display | full | stops, with the reason |
| CSV/JSON export | full | exits, does not write a file |
| SMU writes (limits, Curve Optimizer) | allowed | blocked |

If you have other Granite Ridge hardware, the useful contribution is a `pm_table`
dump plus your CPU model — not loosening the gate.

## What is actually known

All 457 indices have a row in [PM_TABLE_MAP.md](PM_TABLE_MAP.md), but the rows carry
very different weight, and the confidence column says which is which:

- **Cross-validated (strongest).** 14 automated checks compare PM fields against
  independent sensors — `k10temp`, `amdgpu`, `cpufreq`, DDR5 nominal — or against
  stock spec. Tctl, per-core temperatures, per-core frequency, boost limit, Vcore,
  VDDCR_SoC, VDDIO_MEM, iGPU clock, C6 residency, and the PPT/TDC/EDC limits
  (162 W / 120 A / 180 A, exact) are in this group.
- **Structural.** Zone `0x000` is the classic Zen `(LIMIT, VALUE)` pair layout: PPT
  `0x008`/`0x00C` in watts, TDC `0x020`/`0x024` in amps, thermal `0x028`/`0x02C` in
  °C, EDC limit at `0x0FC`. Every real temperature in the table is direct °C — there
  is no encoding to undo.
- **Inferred.** Correlation and load response only. Treat as a hypothesis.
- **Known wrong, and left in the map as such.** Several fields once marked CONFIRMED
  were disproved; the rows now say what they are *not*. See
  [the honesty audit](PM_TABLE_MAP.md#honesty-audit-2026-07-30).

Open questions are in [docs/TOFIX.md](docs/TOFIX.md). The short version: there is no
live EDC value anywhere in this table version (searched exhaustively — see
[the negative result](PM_TABLE_MAP.md#edc_value--closed-negative-result-2026-07-30)),
and thirteen fields have their domain narrowed but no identification.

## Verifying the map

The map is not trusted on its word. [`research/audit_map.py`](research/audit_map.py)
parses `PM_TABLE_MAP.md` itself and asserts every mechanically checkable claim against
live hardware — static fields must not move under load, fields documented as zero must
read zero, documented mirrors must be bit-identical, and cross-validated fields must
match their system sensor within tolerance. It exits non-zero on any failure.

```bash
sudo python3 research/audit_map.py
```

It runs a stress load and takes a few minutes. Its first run found 11 genuine
documentation errors, including three "perfect mirrors" that differ on every read and
nine fields labelled energy accumulators that do not accumulate.

Two measurement lessons from building it are worth stealing if you write your own:

- **Read the external sensor before `pm_table`, not after.** The PM table read costs
  an SMU transfer that warms the die enough to show in the next sensor read — a
  +2.4 °C bias, larger than most things you would be validating.
- **Use medians over a window, and compare sensors sampled in the *same* window.**
  Occasional garbage sysfs reads wreck a mean, and a reading taken before or after the
  window is a different point on a thermal transient.
- **Wait for equilibrium, and prove it with two stable windows, not one.** A sensor
  disagreement of a few degrees is almost always cooldown, not calibration: after a
  stress load the `k10temp` − `d[11]` delta decays +7.3 → +1.0 °C over a couple of
  minutes and only then settles at +0.15 °C. Single instantaneous reads cannot tell
  that apart from noise — at idle `k10temp` alone swings 46.6 → 64.6 °C on background
  activity.

## Tools

All of them need the `ryzen_smu` driver loaded, and root.

```bash
sudo python3 tools/gui/gnr_master.py      # PyQt6 dashboard: per-core clocks, power, CO
sudo python3 tools/gnr_master.py          # menu-driven CLI for limits and Curve Optimizer
sudo python3 tools/export_telemetry.py    # 5 JSON snapshots
sudo python3 tools/export_telemetry.py --csv
sudo python3 tools/export_telemetry.py --live 2   # append a CSV row every 2 s
sudo python3 tools/dump_table_full.py      # all 457 floats, labelled from the map
```

SMU control uses MP1 mailbox **message IDs** (not table offsets): `0x3E` PPT,
`0x3D` TDC, `0x3C` EDC, `0x50`-`0x57` per-core Curve Optimizer as a signed 32-bit
value. On Zen 5 the TDC and EDC IDs are the reverse of what Zen 4 documentation
implies, which is why they are commented at every call site. Curve Optimizer is
write-only — the SMU will not read the offsets back, so the tools cache them locally
in `$XDG_CONFIG_HOME/gnr_master.json` to keep the display honest.

`research/` holds the measurement scripts, one per question asked: `audit_map.py`
(the map's regression gate), `recheck_zone0.py` / `recheck_sweep.py` / `recheck_edc.py`
(the zone 0x000 correction), `hunt_edc.py` (the exhaustive EDC search),
`classify_unknown.py`, `profile_load.py`, `profile_demoted.py` and
`transient_demoted.py`. `smu_send.py` and `smu_advanced.py` are standalone MP1/RSMU
mailbox tools.

`dump_table_full.py` prints the whole table with each field's documented meaning and
confidence, read from `PM_TABLE_MAP.md` itself. On unvalidated hardware it drops the
labels and prints raw values — that dump, plus your CPU model, is exactly what the map
needs to grow past one machine.

## Requirements

- Linux 6.10+
- The [`ryzen_smu`](https://github.com/amkillam/ryzen_smu) kernel module, loaded
- `python3-pyqt6` and `pyqtgraph`, for the GUI only

## Safety

Writing to the SMU mailbox can destabilise or damage hardware. Specifics that matter:

- **A wrong offset is worse than a missing one.** Reading the wrong field shows a
  wrong number; writing a limit *derived* from a wrong field pushes it into the SMU.
  That has already happened here once — the thermal limit (88 °C) was read as TDC and
  pre-filled the write dialog as 88 A. Hence the hardware gate.
- **Both front-ends block message IDs `0x03`-`0x0D` and `0x10`** outright, and that
  should stay. `0x58`-`0x5D` freeze MP1 on this part; do not probe them.
- Stock limits for the 9800X3D are 162 W PPT / 120 A TDC / 180 A EDC. The reset paths
  send exactly those.
- 3D V-Cache runs under a tighter thermal ceiling than the rest of the die. The
  thermal limit in the table reads 88 °C.
- SMU settings are volatile — a reboot reverts everything to BIOS constraints. That is
  also your recovery path.

## License

MIT — see [LICENSE](LICENSE).

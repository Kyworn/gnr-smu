# Ryzen 5 5600X / Vermeer — PM table 0x380905 (1488 bytes, 372 floats)

Read-only support. **No SMU write is validated on this part**: Curve Optimizer,
PPT/TDC/EDC, voltage, frequency, PBO, MP1/RSMU probing and even
conceptually-read-only RSMU queries (they write `smu_args`/`rsmu_cmd`) are all
blocked (`allow_smu_writes = False`). See Phase 7 rationale below.

## Hardware

- CPU: AMD Ryzen 5 5600X 6-Core Processor (Zen 3, 1 CCD, 6C/12T)
- SMU firmware 56.70.0, MP1 IF 2, `ryzen_smu` 0.1.7, kernel 7.0.14-14-pve
- PM table version `0x380905`, size 1488 bytes = 372 float32 LE
  (matches the `ryzen_smu` table: Vermeer `0x380905` → `0x5D0`)
- Driver codename sysfs reads `12` = `CODENAME_VERMEER` in the driver enum;
  dmesg confirms `Family Codename: Vermeer`
- Dataset: 15 snapshots (idle×3, single-core×3, all-core×3, per-core×6),
  captured 2026-09-10; fixtures in `tests/fixtures/vermeer/`
- Analysis script: `research/vermeer_380905.py`

## Linux core → SMU slot mapping (measured, not assumed)

Per-core blocks are 8 SMU slots wide. Slots 2–3 are fused off on the 5600X:

```
SMU slot:      0  1  2  3  4  5  6  7
Linux core:    0  1  -  -  2  3  4  5
```

Method: for each of the 6 per-core captures (load pinned to one logical CPU,
first thread of each physical core per `lscpu -e`), the temperature lane with
the largest rise over the idle median is that core's slot. All 6 agree, and
live re-validation (2026-09-10, pinned `stress-ng` on CPU 0) put d[188] at
62.63 °C against k10temp Tccd1 62.75 °C while the other lanes stayed ~39–41 °C.

Portability limit: this tuple is one machine's layout. A 5600X is a binned
part (down-binned dies; dual-CCD SKUs with a whole deactivated CCD exist in
the wild), so which two cores are fused off is not guaranteed identical on
every chip — and projects like ZenStates-Core read the core-disable fuse map
dynamically instead of assuming it. No risky SMN read is added to resolve
this; instead the tuple is verified against read-only data at detection time
(`_fused_layout_matches` in `tools/hwgate.py`): in the per-core frequency
block the fused slots must read exactly 0.0 and every mapped slot a real
frequency. Any other layout refuses the profile with an explicit reason
rather than mislabelling cores. Support is therefore conservative by design:
correct on the validated machine, refusal elsewhere.

Represented as `core_slots=(0, 1, 4, 5, 6, 7)` on the profile; every
`base + core` site goes through `profile.slot()` / `profile.lane()`.
Fused slots read `0.0` in every per-core block except CC6, where they
consistently report `100.0`. This appears to be the firmware representation
for inactive/non-present core slots and is not interpreted as an actual
sleeping physical core.

## Validated per-core blocks (offsets are block bases, + slot)

| Block base | Meaning | Confidence | Evidence |
|---|---|---|---|
| d[172] | Per-core power (W) | HIGH | 6/6 slot-selective; 0.5–1.2 W idle → 9–11 W loaded; first group of the canonical Zen per-core order (same order as Matisse `0x240903` in `ryzen_smu` `monitor_cpu.c`: POWER, VOLTAGE, TEMP, FIT, IDDMAX, FREQ, FREQEFF, C0, CC1, CC6). No independent watt reference exists on this platform (no RAPL), so not CONFIRMED. |
| d[180] | Per-core voltage (V) | HIGH | 6/6 slot-selective (small deltas, +0.2 V); 0.94 V idle → 1.12–1.18 V loaded. No SVI cross-check done yet. |
| d[188] | Per-core temperature (°C) | CONFIRMED | 6/6 slot-selective; 38–40 °C idle → 55–72 °C loaded; live k10temp agreement (d[188]=62.63 vs Tccd1=62.75 under pinned load). Lanes d[190]/d[191] (fused slots) are live but follow no single core — never exposed as core temps. |
| d[212] | Per-core frequency (GHz) | CONFIRMED | 6/6 slot-selective; 3.7 idle → 4.3–4.55 loaded; live cpufreq agreement (d[212]=4.545 GHz vs cpu0 `scaling_cur_freq` 4541 MHz under pinned load). |
| d[220] | Per-core effective frequency (GHz) | CONFIRMED | 6/6 slot-selective; ~0.2 idle → ~3.7–4.5 on the loaded lane; equals the actual frequency on a fully-active core (4.544 vs 4.545), ~0 on sleeping cores; all lanes 4.31 under full load. Behavioral semantics are textbook. |
| d[228] | C0 residency (%) | CONFIRMED | 6/6 slot-selective; 2–9 % idle → 70–100 % loaded lane, 100 % all lanes under full load. |
| d[236] | CC1 residency (%) | CONFIRMED | 6/6 slot-selective; ~22–36 % idle → ~0 on the loaded lane, 0 everywhere under full load. |
| d[244] | CC6 residency (%) | CONFIRMED | 6/6 slot-selective; ~55–75 % idle → ~10–23 % loaded lane, 0 everywhere under full load; fused slots read 100. |

## Deliberately unmapped (measured but not identified, or unconfirmed)

- d[196:204] — core-selective (slots 0,1,4,5,6,7 → d[196,197,200,201,202,203]),
  spikes to 7–30 under single-core load. Position matches CORE_FIT in the
  canonical order, but units/meaning are unknown. Candidate only.
- d[204:212] — weak selectivity with a shared floor (+2 on every lane for any
  single-core load). Position matches CORE_IDDMAX. Candidate only.
- d[316:324], d[332:340] — core-selective with the fused-slot pattern, values
  ~0.5/13.7 and ~0.5/6.1 idle/load. Current-related candidates, unidentified.
- d[268:276] — rises toward 100 under load but not cleanly core-selective
  (residual-heat confound). Unidentified.
- d[1] (+mirrors d[13]/d[29]/d[150]) — 27 W idle → 79.5 W full load, plausible
  package power, but no independent reference and no confirmed limit pairing.
  Candidate only.
- d[140] — 52–70 idle (varies between idle states) → ~64 under load, near
  Tctl under load but not at idle. Hotspot-like, not validated as Tctl.
- d[127] — 42 idle → 48.5 full load; tracks package heat weakly, not Tctl
  (moves +1 °C for +15 °C of Tctl under single-core load).
- d[144]/d[145]/d[358] — heat-tracking but inconsistent baselines; unidentified.
- PPT/TDC/EDC limits and values — the constant pool (90/75/95/115) does not
  pin to 5600X stock spec without a write-back test, which is forbidden here.
  Not exposed.
- FCLK/UCLK/MCLK, VDDCR_SOC, VDDG CCD/IOD, VDDP, VID, boost limit — no
  validated mapping. Not exposed (GUI shows "--").
- d[284:292] (8× 4.75 const), d[292:300] (6× 3.691 + 2× 0.55), d[48:52]/d[74:82]
  (1800/1600 consts) — static, plausible clock/Boost tables, unidentified.

## What the GUI/exporter show on this profile

Per-core temperature, power, voltage, frequency, effective frequency,
C0/CC1/CC6 (+ CCD averages). Everything else is "--" / omitted, including
Tctl, package power, limits and all rails. The Curve Optimizer group is hidden
and both control dialogs refuse to open (`smu_writes_supported() == False`).

Confidence is visible, not just documented: temperature, frequency, effective
frequency and residency are confirmed, while core power and voltage are
`provisional_blocks` (HIGH — load response + canonical layout order, no
independent watt/volt reference on this platform) and carry a
"high-confidence, not cross-validated" tooltip in the GUI. See the table
above for the per-block level.

## Why writes stay off (Phase 7)

No MP1/RSMU message ID is validated on Vermeer in this project. External
tables (e.g. Matisse/Vermeer RSMU PPT/TDC/EDC examples in `ryzen_smu` docs)
are not activated on sight: enabling them is a separate step requiring its own
read-back validation on this exact firmware (56.70.0). `smu_message_supported()`
returns False for the whole profile, `curve_optimizer_command()` has no
`"unsupported"` construction path, and `read_curve_optimizer_offsets()` refuses
write-blocked profiles because the query itself writes sysfs.

## Open items

- SVI/RAPL-style cross-check of per-core voltage/power (would promote HIGH →
  CONFIRMED). No such interface is available in-kernel on this box.
- Tctl / package-power identification needs a paired transient against k10temp
  across several load levels; single-point checks ruled out d[127]/d[140]/
  d[144]/d[145]/d[358] as Tctl (see validation notes above).
- The `research/vermeer_380905.py` analyzer and `tests/fixtures/vermeer/`
  snapshots are kept so any new claim can be re-checked offline.

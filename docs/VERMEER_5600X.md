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
(`_fused_layout_matches` in `tools/hwgate.py`): in the per-core
power/voltage/frequency blocks the fused slots must read exactly 0.0 and
every mapped slot a real value (verified exact-zero/non-zero across 15
snapshots plus 1746 transient samples at all load levels). The temperature
block is excluded on purpose (fused temp lanes report live die temperatures)
as is effective frequency (a sleeping present core legitimately reads 0.0).
Any other layout refuses the profile with an explicit reason
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
| d[172] | Per-core power (W) | HIGH | 6/6 slot-selective; 0.5–1.2 W idle → 9–11 W loaded; first group of the canonical Zen per-core order (same order as Matisse `0x240903` in `ryzen_smu` `monitor_cpu.c`: POWER, VOLTAGE, TEMP, FIT, IDDMAX, FREQ, FREQEFF, C0, CC1, CC6). Corroborated at package level: sum of the 6 lanes tracks RAPL `package-0` with gain 1.10 and a constant ~25.5 W uncore offset — close but not 1:1, and there is no per-core watt reference, so not CONFIRMED. |
| d[180] | Per-core voltage (V) | HIGH | 6/6 slot-selective (small deltas, +0.2 V); 0.94 V idle → 1.12–1.18 V loaded. No SVI cross-check done yet. |
| d[188] | Per-core temperature (°C) | CONFIRMED | 6/6 slot-selective; 38–40 °C idle → 55–72 °C loaded; live k10temp agreement (d[188]=62.63 vs Tccd1=62.75 under pinned load). Lanes d[190]/d[191] (fused slots) are live but follow no single core — never exposed as core temps. |
| d[212] | Per-core frequency (GHz) | CONFIRMED | 6/6 slot-selective; 3.7 idle → 4.3–4.55 loaded; live cpufreq agreement (d[212]=4.545 GHz vs cpu0 `scaling_cur_freq` 4541 MHz under pinned load). |
| d[220] | Per-core effective frequency (GHz) | CONFIRMED | 6/6 slot-selective; ~0.2 idle → ~3.7–4.5 on the loaded lane; equals the actual frequency on a fully-active core (4.544 vs 4.545), ~0 on sleeping cores; all lanes 4.31 under full load. Behavioral semantics are textbook. |
| d[228] | C0 residency (%) | CONFIRMED | 6/6 slot-selective; 2–9 % idle → 70–100 % loaded lane, 100 % all lanes under full load. |
| d[236] | CC1 residency (%) | CONFIRMED | 6/6 slot-selective; ~22–36 % idle → ~0 on the loaded lane, 0 everywhere under full load. |
| d[244] | CC6 residency (%) | CONFIRMED | 6/6 slot-selective; ~55–75 % idle → ~10–23 % loaded lane, 0 everywhere under full load; fused slots read 100. |

## Phase 2 globals (clocks, rails, socket power)

| Byte offset | Index | Meaning | Unit | Confidence | External source | Hardware proof | Limits |
|---|---|---|---|---|---|---|---|
| 0x0C0 | d[48] | FCLK | MHz | HIGH | ZenStates-Core `PowerTable.cs`, row `0x380905 / 0x5D0` (exact version) | Bit-constant 1800 across 15 snapshots + 1746 transient samples; DDR4-3200 box (MCLK/UCLK lock at 1600 as expected, FCLK 1800 = plausible BIOS setting) | No independent FCLK readout on Linux; constant so no load dynamics to check |
| 0x0C8 | d[50] | UCLK | MHz | HIGH | Same row | Bit-constant 1600; equals MCLK (coupled 1:1, expected for DDR4-3200) | Same as FCLK |
| 0x0CC | d[51] | MCLK | MHz | HIGH | Same row | Bit-constant 1600; exactly DDR4-3200/2 per `dmidecode` | Same as FCLK |
| 0x0B4 | d[45] | VDDCR_SOC | V | HIGH | Same row | Bit-constant 1.1875; in-range SoC voltage | No VRM/SVI readout in-kernel on this box |
| 0x224 | d[137] | CLDO_VDDP | V | HIGH | Same row | Bit-constant 0.9002; canonical 0.90 V VDDP | Same as VDDCR_SOC |
| 0x228 | d[138] | CLDO_VDDG_IOD | V | HIGH | Same row | Bit-constant 0.9976; in-range VDDG | Same as VDDCR_SOC |
| 0x22C | d[139] | CLDO_VDDG_CCD | V | HIGH | Same row | Bit-constant 0.9976; in-range VDDG | Same as VDDCR_SOC |
| — | d[1] | Socket (package) power | W | CONFIRMED | None needed (measured) | RAPL `package-0` on-die energy accounting over 1746 samples, 7 phase groups, 3 workload types (matrix/int64/cache): Pearson +0.9996, gain +0.977, offset +0.04 W, RMSE 0.51 W, MAE 0.25 W. Confirmed against AMD RAPL socket accounting, not against an external electrical power meter. d[13]/d[29] track d[1] to ~1e-3 (same reading); only d[1] mapped. d[150] close second (RMSE 1.91), left unmapped. | RAPL "core" domain on this AMD box behaves oddly (non-monotonic vs threads) and was not used; package domain only |

Provenance note on ZenStates-Core: all Zen3 rows (`0x380005`–`0x380905`)
share identical clock/rail offsets, so this is one family-level source, not
one confirmation per version. It counts as the published-for-exact-version
axis; coherence with hardware is the second axis; both together clear HIGH,
not CONFIRMED. The independently reverse-engineered `CORE_POWER = 0x2B0 =
d[172]` match is genuine coherence between the two axes. `VDD_MISC` is `-1`
(unmapped) in that row too.

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
- d[1] — now mapped as socket power (CONFIRMED, see Phase 2 table above).
  d[13]/d[29] are the same reading to ~1e-3; d[150] is a close second
  (RMSE 1.91 vs RAPL). Only d[1] is exposed.
- d[140] — hotspot/peak candidate, NOT Tctl. Median aligns with Tctl under
  sustained load (±2 °C over 7 phase groups), but 40% of 5 Hz samples deviate
  >5 °C with sample-to-sample jumps up to ~15 °C while k10temp never jumps;
  it reads at or above the hottest core lane in 95% of samples (median +6.1)
  yet also drops below Tctl in cooldown (−3.0). Consistent with an
  instantaneous package-hotspot max under different smoothing than k10temp,
  inconsistent with a Tctl identity. Median agreement alone would have
  mislabelled it — this is why sample-level coherence is required.
- d[127] — 42 idle → 48.5 full load; tracks package heat weakly, not Tctl
  (gain 0.18 vs Tctl over the transient run).
- d[144]/d[145]/d[358] — heat-tracking but nonlinear (flat at low
  temperature, steep at high; gains 0.43–0.64 where measurable). d[358] has
  the best raw Pearson vs Tctl (+0.91) yet a gain of only 0.43 — rejected as
  Tctl. All unidentified.
- PPT/TDC/EDC limits and values — the constant pool (90/75/95/115) does not
  pin to 5600X stock spec without a write-back test, which is forbidden here.
  Not exposed. (`ryzen_smu` docs show Matisse/Vermeer RSMU power commands;
  documented only, never executed.)
- FCLK/UCLK/MCLK, VDDCR_SOC, VDDG CCD/IOD, VDDP — now mapped HIGH (see Phase 2
  table). VID, VDD_MISC, boost limit — still no validated mapping ("--").
- d[284:292] (8× 4.75 const), d[292:300] (6× 3.691 + 2× 0.55), d[48:52]/d[74:82]
  (1800/1600 consts) — static, plausible clock/Boost tables, unidentified.
  (d[48]/d[50]/d[51] of that range are now the mapped clocks above.)

## What the GUI/exporter show on this profile

Per-core temperature, power, voltage, frequency, effective frequency,
C0/CC1/CC6 (+ CCD averages), plus FCLK/UCLK/MCLK, VDDCR_SOC, VDDG CCD/IOD,
VDDP and socket power. Everything else is "--" / omitted, including Tctl,
limits, VID/VDD_MISC and boost. The Curve Optimizer group is hidden
and both control dialogs refuse to open (`smu_writes_supported() == False`).

Confidence is visible, not just documented: temperature, frequency, effective
frequency, residency and socket power are confirmed, while core power,
core voltage, the three clocks and the four rails are HIGH (explicitly
published offsets with coherent values, but no independent Linux reference)
and carry a "high-confidence, not cross-validated" tooltip in the GUI.

## Why writes stay off (Phase 7)

No MP1/RSMU message ID is validated on Vermeer in this project. External
tables (e.g. Matisse/Vermeer RSMU PPT/TDC/EDC examples in `ryzen_smu` docs)
are not activated on sight: enabling them is a separate step requiring its own
read-back validation on this exact firmware (56.70.0). `smu_message_supported()`
returns False for the whole profile, `curve_optimizer_command()` has no
`"unsupported"` construction path, and `read_curve_optimizer_offsets()` refuses
write-blocked profiles because the query itself writes sysfs.

## Open items

- Per-core voltage/power promotion (HIGH → CONFIRMED) needs an SVI-style
  per-core reference. RAPL package corroborates the sum (gain ~1.1, constant
  uncore offset) but is not per-core. No such interface in-kernel on this box.
- Tctl: negative result. No PM field shows sample-level coherence with
  k10temp Tctl across the 1746-sample transient run (see d[140] analysis
  above). Revisit only with new evidence, not by relabelling medians.
- The `research/vermeer_380905.py` analyzer, `research/vermeer_transient.py`
  logger, `research/vermeer_track.py` analysis and `tests/fixtures/vermeer/`
  snapshots are kept so any new claim can be re-checked offline.

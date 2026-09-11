# GNR-SMU

Reverse-engineered AMD Ryzen SMU telemetry and control tools for Linux.

GNR-SMU maps undocumented Ryzen PM tables using real hardware measurements,
cross-validation against independent Linux sensors, reproducible research
fixtures and fail-closed hardware profiles.

Currently supported:
- Ryzen 7 9800X3D / Granite Ridge — telemetry + validated SMU controls
- Ryzen 9 9950X3D / Granite Ridge — telemetry + validated SMU controls
- Ryzen 5 5600X / Vermeer — read-only telemetry

### Mapping philosophy

```text
measured > documented > assumed
```

Every exposed field carries a confidence level:

- **CONFIRMED** — real measurement plus a reliable independent reference
  and/or very strong multi-axis behavioral validation.
- **HIGH** — explicitly published for exactly this PM-table version in
  credible technical evidence, with coherent hardware behavior, but no
  independent measurement available.
- **CANDIDATE** — plausible correlation, position or value, but insufficient
  identification. Never presented as established telemetry; may only be
  surfaced when explicitly labelled as a candidate/experimental field.
- **UNKNOWN** — not enough evidence. Left unmapped.

External projects such as ZenStates-Core and `ryzen_smu` are used as
technical evidence, never blindly copied: a shared family-level table counts
as one source, not one confirmation per version. Unsupported layouts fail
closed, because plausible-looking floats at wrong offsets are worse than
missing telemetry.

> [!NOTE]
> **Project status and thanks.** Maintenance is currently slower than usual because
> the maintainer is dealing with health issues. Replies and reviews may therefore
> take some time; the reduced activity does not mean that contributions are being
> ignored or taken for granted.
>
> Special thanks to [Thomas Pöchtrager (@tpoechtrager)](https://github.com/tpoechtrager),
> whose measurements, Ryzen 9 9950X3D implementation, hardware validation and
> HWiNFO-style dashboard substantially expanded and improved this project. His work
> is now part of the main branch. See [Credits](#credits) for the details.

Telemetry and controls are supported on the Ryzen 7 9800X3D and Ryzen 9 9950X3D.
The 9950X3D profile includes all 16 per-core temperatures and a model-specific SMU
command allowlist; see [`docs/architectures/granite_ridge/9950X3D.md`](docs/architectures/granite_ridge/9950X3D.md).

Read-only telemetry is also supported on the Ryzen 5 5600X / Vermeer
(PM table `0x380905`, 1488 bytes / 372 floats, SMU firmware tested: 56.70.0).
CONFIRMED via independent references or very strong multi-axis validation:
per-core temperature, per-core frequency, effective frequency, C0/CC1/CC6
residency, and socket/package power `d[1]` (cross-validated against AMD RAPL
package accounting). HIGH confidence (explicitly published offsets with
coherent values, not independently cross-validated, tooltip-marked in the
GUI): per-core power and voltage, FCLK, UCLK, MCLK, VDDCR_SOC, CLDO_VDDP,
CLDO_VDDG_IOD and CLDO_VDDG_CCD. The fused-core layout (SMU slots 2–3 off on
the validated machine) is verified fail-closed at detection time rather than
assumed universal. No SMU write is validated there, so limits, Curve
Optimizer and both control dialogs stay disabled; see
[`docs/architectures/vermeer/VERMEER_5600X.md`](docs/architectures/vermeer/VERMEER_5600X.md).

Vermeer Tctl remains intentionally unmapped: a plausible Tctl candidate was
rejected after a 351-second / 1746-sample transient comparison against
k10temp showed inconsistent instantaneous behavior. Unknown fields remain
unknown rather than being labelled from plausibility alone.

On the 9950X3D, no PM-table block is currently established as live per-core
frequency. The GUI uses Linux `cpufreq` for that value and keeps the mapped PM
blocks labelled as Power, FIT, Activity, C0, CC1 and CC6 instead of guessing.

![GNR-SMU Dashboard](assets/screenshot.png)

The `ryzen_smu` driver exposes a model-specific PM table at
`/sys/kernel/ryzen_smu_drv/pm_table`, with no complete official public layout. The 9800X3D table is
1828 bytes / 457 float32 values; the 9950X3D table is 2452 bytes / 613 values. This
repo contains the measured layouts and tools that select the correct profile.

## Current interfaces

- `tools/gui/gnr_master.py` provides a sensor dashboard with current, minimum,
  maximum and average values plus profile-gated controls.
- `tools/gnr_master.py` provides the command-line control workflow.
- `tools/export_telemetry.py` exports profile-specific named JSON or CSV; raw
  JSON snapshots retain every anonymous float separately.
- `tools/dump_table_full.py` prints the complete table and applies documentary
  labels only when the exact 9800X3D layout is detected.
- `tools/submit_dump.py` creates a read-only community comparison bundle.

## Wanted: Ryzen hardware dumps for validation

This is the one thing that would move the project forward, and it takes about ten
seconds. Additional physical CPUs are useful for distinguishing model-specific
mappings, PM-table-version-specific mappings, fused-core layouts, CCD topology
and generation-wide layouts. Priority hardware, wanted for research/validation
(not claimed as supported):

```text
Zen 3 / Vermeer: 5700X, 5800X, 5900X, 5950X, other 5600X samples
Zen 4 / Raphael: 7600X, 7700X, 7900X, 7950X
Zen 5 / Granite Ridge: 9600X, 9700X, 9900X, 9950X, other PM-table variants
```

```bash
sudo python3 tools/submit_dump.py --out ./my_5700x   # standardized bundle (preferred)
sudo python3 tools/dump_table_full.py > my_dump.txt  # raw text fallback
```

Open an issue with that file and your exact CPU model. The dump tool works on
unvalidated hardware on purpose: it drops the labels and prints raw values, which is
exactly what is needed to compare layouts. See
[`docs/community/COMMUNITY_DUMPS.md`](docs/community/COMMUNITY_DUMPS.md) for what a bundle contains
(and what it deliberately excludes), plus how maintainers compare submissions
with `tools/compare_tables.py`.

[@tpoechtrager](https://github.com/tpoechtrager) sent the first one, from a 9950X3D —
see [Credits](#credits).

Why it matters: a layout from one machine cannot distinguish "this is where AMD puts
Tctl" from "this is where Tctl landed on my 9800X3D". The 9950X3D settles that for the
per-core arrays, and establishes how the 16-wide ones shift. But the complete labelled
map is still the 9800X3D's: most of the 9950X3D's 613 floats remain unidentified.

The other open questions need a different lever rather than more data. Thirteen fields
have a narrowed domain but no identification, because under load every axis rises at
once and none of them separates cleanly; on Zen 5 the die's thermal constant is
sub-second, so decay timing cannot separate the power and thermal domains either. That
needs frequency varied at constant power, or fixed power at two ambient temperatures.
And there is no live EDC value anywhere in this table version — that one is closed, and
the search is written up as a negative result.

## Read this before running it on your machine

**The complete map was measured on exactly one machine:** a Ryzen 7 9800X3D,
8 cores / 1 CCD, PM table version `0x620105`. The 9950X3D has a separate 613-float
profile, and its 16-lane per-core temperature block was independently validated on
both CCDs. It does not claim that the complete 9800X3D map applies.

That matters more than it sounds, because the failure mode is silent. A different
table version moves offsets, but the bytes still parse as floats — so a GUI can show
plausible watts and degrees that are simply the wrong fields. A different core count
also changes the width and starting index of later per-core arrays.

So the tools check first ([`gnr_smu/`](gnr_smu/)) and refuse rather than
guess:

| | Validated hardware | Anything else |
|---|---|---|
| Telemetry display | profile-specific | stops, with the reason |
| CSV/JSON export | profile-specific | exits, does not write a file |
| SMU writes (limits, Curve Optimizer) | profile allowlist only | blocked |

If you hit the gate, send a dump rather than loosening it — the offsets would be wrong,
not missing.

## What is actually known

For the 9800X3D `0x620105` table, all 457 indices have a row in [9800X3D_PM_TABLE_0x620105.md](docs/architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md), but the rows carry
very different weight, and the confidence column says which is which:

- **Cross-validated (strongest).** Automated checks compare PM fields against
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
  [the honesty audit](docs/architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md#honesty-audit-2026-07-30).

### 9800X3D named telemetry

The normal GUI and named CSV schema expose only CONFIRMED/HIGH identities. The
evidence map also records MED/LOW hypotheses and negative results for research,
but those rows are not established runtime telemetry.

The named schema contains 86 columns. Established global identities include
`pkg_power`, `vcore_telemetry_peak`, `vcore_telemetry_average`,
`vddio_mem_voltage`, and `vddcr_cpu_vid`; the calculated `vcore_peak` and
`vcore_avg` columns come from the confirmed per-core voltage block. Raw JSON
snapshots retain all 457 floats without attaching names to unknown values.

Open questions are tracked in [docs/RESEARCH_BACKLOG.md](docs/RESEARCH_BACKLOG.md); the EDC search is written
up as
[a negative result](docs/architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md#edcvalue-closed-negative-result-2026-07-30).

## Verifying the map

The map is not trusted on its word. [`research/granite_ridge/mapping/audit_map.py`](research/granite_ridge/mapping/audit_map.py)
parses `9800X3D_PM_TABLE_0x620105.md` itself and asserts every mechanically checkable claim against
live hardware — static fields must not move under load, fields documented as zero must
read zero, documented mirrors must be bit-identical, and cross-validated fields must
match their system sensor within tolerance. It exits non-zero on any failure.

```bash
sudo python3 research/granite_ridge/mapping/audit_map.py
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
sudo python3 tools/gui/gnr_master.py      # HWiNFO-style table: current/min/max/avg, cores, rails, L3
sudo python3 tools/gnr_master.py          # menu-driven CLI for limits and Curve Optimizer
sudo python3 tools/export_telemetry.py    # 5 JSON snapshots
sudo python3 tools/export_telemetry.py --csv
sudo python3 tools/export_telemetry.py --live 2   # append a CSV row every 2 s
sudo python3 tools/export_telemetry.py --temps    # all per-core temperatures once
sudo python3 tools/dump_table_full.py      # complete table; labels where mapped
```

SMU control uses profile-specific MP1 mailbox **message IDs** (not table offsets).
Power limits are the same on both Granite Ridge parts — `0x3E` PPT, `0x3C` TDC, `0x3D` EDC. This repo
asserted `0x3D` TDC / `0x3C` EDC until 2026-08-26, on the strength of a note that named
no measurement; `research/dangerous/probe_tdc_edc.py` settles it by writing a value and reading
back which limit moved.

Curve Optimizer differs: `0x50`-`0x57` per core on the 9800X3D, as a signed 32-bit
value, against `0x35` on the 9950X3D with the CCD and core encoded into the argument.
The active offset is read back on both parts with RSMU `0xD5`
(`GetDldoPsmMargin`), using the CCD/core mask in argument 0. This was verified on a
9800X3D with BIOS `-30`: every core returned `RSP=1` and `arg0=0xFFFFFFE2`. The GUI
therefore shows live SMU values rather than a local cache and verifies every CO write
by reading it back. Its sensor-table column order, column widths, refresh interval and
window size remain stored in `$XDG_CONFIG_HOME/gnr_master.json`.

`research/` holds the measurement scripts, one per question asked, grouped by
architecture (`granite_ridge/`, `vermeer/`) with superseded passes under
`granite_ridge/historical/`: `audit_map.py` (the map's regression gate),
`recheck_zone0.py` / `recheck_sweep.py` / `recheck_edc.py` (the zone 0x000
correction), `hunt_edc.py` (the exhaustive EDC search), `classify_unknown.py`,
`profile_load.py`, `profile_demoted.py` and `transient_demoted.py`.
`smu_send.py`, `smu_advanced.py` and `probe_tdc_edc.py` live under
`research/dangerous/` — they are the only scripts that can send SMU/SMN
writes. See `research/README.md`.

`dump_table_full.py` prints the whole table with each field's documented meaning and
confidence, read from `9800X3D_PM_TABLE_0x620105.md` itself.

## Tests

```bash
python3 -m unittest discover -s tests
python3 tools/hwgate.py                 # hardware-gate self-test (refuses on unvalidated HW)
```

The suite covers the Granite Ridge map regression, profile schemas, research
execution guards, real Vermeer PM-table fixtures, the SMU write blockade,
documentation integrity and community dump tooling without requiring the
validated hardware to be present.

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
- **Every send path blocks message IDs `0x03`-`0x0D`, `0x10` and `0x58`-`0x6F`**
  outright, and that should stay. The `0x58`-`0x6F` range freezes MP1 on this part —
  no response, reboot to recover — and it is the range `docs/architectures/granite_ridge/FINDINGS.md` actually
  tested, so do not narrow it. The block is MP1-specific: RSMU is a separate mailbox
  with its own ID namespace, and `0x04`/`0x05` there are the ordinary PM-table read.
- Stock limits are 162 W PPT / 120 A TDC / 180 A EDC on the 9800X3D and 200 W /
  160 A / 225 A on the 9950X3D. The reset paths select the matching profile.
- 3D V-Cache runs under a tighter thermal ceiling than the rest of the die. The
  table reports 88 °C on the tested 9800X3D and 95 °C on the tested 9950X3D.
- SMU settings are volatile — a reboot reverts everything to BIOS constraints. That is
  also your recovery path.

## Credits

### Thomas Pöchtrager — 9950X3D support and dashboard

This project owes a major part of its current scope and interface to
[Thomas Pöchtrager (@tpoechtrager)](https://github.com/tpoechtrager). He contributed:

- the first PM-table dump from a second Granite Ridge part: a Ryzen 9 9950X3D with
  table version `0x620205` and 613 floats;
- the 9950X3D hardware profile and its 16-core telemetry mapping, validated across
  both CCDs against `Tccd1` and `Tccd2`;
- real-machine validation of PPT, TDC, EDC and per-core Curve Optimizer writes on
  both CCDs;
- the dense HWiNFO-style dashboard with current, minimum, maximum and average sensor
  columns, persistent layout and clearer telemetry grouping;
- additional experiments that separated evidence-backed L3/CCD telemetry from
  speculative labels.

His original work arrived in [PR #1](https://github.com/Kyworn/gnr-smu/pull/1) and
the reviewed integration landed through [PR #2](https://github.com/Kyworn/gnr-smu/pull/2),
with his individual commits and authorship preserved in the project history.

His contribution also exposed a long-standing TDC/EDC command-order error in this
repository. Follow-up measurements confirmed that `0x3C` controls TDC and `0x3D`
controls EDC. The correction and its evidence are documented in
[docs/architectures/granite_ridge/FINDINGS.md](docs/architectures/granite_ridge/FINDINGS.md#4a-power-limits-mp1).

Thank you, Thomas, for the amount of research, testing and care you put into making
GNR-SMU useful beyond a single machine.

## License

MIT — see [LICENSE](LICENSE).

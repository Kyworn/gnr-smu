# Reverse Engineering SMU Granite Ridge — Findings

**Platform:** AMD Ryzen 7 9800X3D (Zen 5, family 0x1A model 0x44)  
**Kernel:** 6.19.11-1-cachyos | **SMU version:** 98.75.0

---

## 1. Mailbox — Addresses (Source: SSDT1)

| Mailbox | MSG (Cmd) | RSP (Status) | ARG0 (Data) | Usage |
|---------|-----------|--------------|----------------|-------|
| **MP1** | 0x3B10530 | 0x3B1057C    | 0x3B109C4      | Power Limits (PPT, TDC, EDC) |
| **RSMU**| 0x3B10524 | 0x3B10570    | 0x3B10A40      | Tables & Telemetry |

---

## 2. Telemetry Access (`ryzen_smu`)

We migrated completely to the official [ryzen_smu](https://github.com/amkillam/ryzen_smu) kernel driver, deprecating our temporary custom module.
- Hardware boundaries are applied by pushing unsigned 32-bit payloads to `/sys/kernel/ryzen_smu_drv/smu_args` followed by the MSG ID to `mp1_smu_cmd`.
- Telemetry table is polled natively from `/sys/kernel/ryzen_smu_drv/pm_table`.

---

## 3. PM Table — Map (v0x620105)

Full size: `0x724` bytes. Fetched continuously alongside core metrics.
For a complete variable-to-byte mapping, reference **[PM_TABLE_MAP.md](../PM_TABLE_MAP.md)**.

*Notable discoveries via Pearson Correlation + cross-validation:*
- **iGPU Clock (sclk):** Offset `0x1B0` — validated vs amdgpu freq1_input.
- **iGPU Power (W):** Offset `0x1AC`.
- **Core Temperatures (°C):** Offsets `0x4F4-0x510` — direct °C, validated vs k10temp.
- **Tctl (°C):** Offset `0x02C` — direct °C, matches k10temp Tctl within 1.1 °C at idle and at load. Its thermal limit sits at `0x028` (88 °C).
- **Hotspot (°C):** Offset `0x438` — direct °C, 0-3 °C above Tctl on average, but very spiky (single reads hit +14 °C at idle). Average it. Previously mislabeled "TDC current".
- **VDDCR_SoC:** Offset `0x0D4` (0.954V) — matches amdgpu vddnb (0.945V, 9mV delta).
- **Vcore P1:** Offset `0x0C4` (1.213V) — matches amdgpu vddgfx (1.220V).
- **VDDIO_MEM:** Offset `0x0E8` (1.099V) — matches DDR5 1.1V nominal.

**⚠ Corrected 2026-07-30 — there is no "temperature encoding".** Offsets `0x00C`, `0x024`,
`0x100`, `0x2E8`, `0x348` were previously written up as non-linearly encoded temperatures.
They are not temperatures at all:

| Offset | Actual |
|--------|--------|
| `0x00C` | PPT Value — total package power (W), 28 → 128 W under a 162 W limit |
| `0x024` | TDC Value — live current (A), 9 → 87 A under a 120 A limit |
| `0x100` | unidentified utilization metric, quantized to 0.125 steps |
| `0x2E8` | iGPU activity (%), complement at `0x2EC` (pair sums to 100) |
| `0x348` | percentage, saturates at exactly 100 under load |

Zone `0x000` is the standard Zen `(LIMIT, VALUE)` pair layout — `0x008`/`0x00C` = PPT,
`0x020`/`0x024` = TDC, `0x028`/`0x02C` = THM. Each value shares the unit of the limit above
it, which is what pins the identification. Every field in the table that *is* a temperature
reads as direct °C; no decoding is required. Full measurements and the before/after label
table are in [PM_TABLE_MAP.md](../PM_TABLE_MAP.md#re-verification-2026-07-30).

---

## 4. Message IDs — Command Table

### 4a. Power Limits (MP1)
- **0x3E:** Set PPT Limit (mW)
- **0x3C:** Set TDC Limit (mA)
- **0x3D:** Set EDC Limit (mA)

**⚠ Corrected 2026-08-26 — these two were the wrong way round here.** The claim rested
on a "validated via fuzzing" line in TOFIX.md that named no script and recorded no
number, and on a table in BASELINE_SNAPSHOT.md whose only evidence was `RSP=0x01` — the
SMU accepting a message, which says nothing about which limit it moved. Both limits are
readable in the PM table, so it is directly observable. `research/probe_tdc_edc.py`
writes a distinctive value and reads back which one changed:

| Sent | PM table field that moved |
|---|---|
| `0x3E` <- 151 W | `d[2]` PPT — the uncontested control, run first to validate the method |
| `0x3D` <- 111 A | `d[63]` **EDC** |
| `0x3C` <- 111 A | `d[8]` **TDC** |

This matches ZenStates-Core. The "hardlocked by firmware" note was also wrong: both
writes returned `RSP=1` and both took effect. The consequence was not cosmetic — the
CLI's reset-to-stock sent 180 A to a TDC whose stock limit is 120 A.

Surfaced by @tpoechtrager: his 9950X3D profile in PR #1 used the ZenStates order, and
checking why it disagreed with ours is what exposed that ours had never been measured.

### 4b. Curve Optimizer (MP1)
- **0x50 to 0x57:** Per-core optimization (C0 to C7).
- **ARG0 Format:** Signed 32-bit integer (e.g., -30 = `0xFFFFFFE2`). Write-only, requires local JSON caching for GUI persistence.

### 4c. MSG IDs 0x58–0x6F — Exploration Result

**Conclusion: dead zone on 9800X3D firmware (SMU 98.75.0)**

Both MP1 and RSMU endpoints were probed via `stress-ng` differential + direct write:

| Endpoint | IDs tested | Result |
|----------|-----------|--------|
| **MP1** (`mp1_smu_cmd`) | 0x58–0x6F | SMU **freezes** on first write — no response, timeout required |
| **RSMU** (`rsmu_smu_cmd`) | 0x58–0x6F | `Permission denied` — driver guardrails block all IDs in this range |

These 24 MSG IDs are either unmapped, firmware-reserved, or behind a privilege wall not exposed
by `ryzen_smu`. The CO range ends at 0x57 (C7). Nothing useful lives above it on this platform.

**HSMP** (`hsmp_smu_cmd`) was also tested — all commands return errors. Root cause: HSMP requires
BIOS activation (`Advanced > AMD CBS > NBIO > SMU Common Options > HSMP Support`), which is
`Auto (Disabled)` on consumer AM5 boards. The `amd_hsmp` driver is EPYC/server only.

---

## 5. ⚠ Documented Traps

1.  **MSG 0x10 (MP1):** Causes an **immediate loss of display output** (GPU Power Gate / Crash).
2.  **`monitor_cpu -f`:** Completely incompatible with Granite Ridge architecture. Triggers an instantaneous Green/Black screen crash.
3.  **Blind DMA Probing:** Never randomly poke IDs 0x03-0x0D on MP1. High risk of bus halting.
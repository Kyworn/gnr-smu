# Community dumps: contributing and comparing PM tables

One machine cannot tell "this is where AMD puts a field" apart from "this is
where it landed on my CPU". Dumps from other physical Ryzen chips are how
layouts get confirmed as generation-wide instead of machine-specific. This
document covers both sides: submitting a dump and comparing submitted dumps.

## Submitting a dump

On the contributor machine (needs the `ryzen_smu` driver loaded, nothing else):

```bash
sudo python3 tools/submit_dump.py --out ./my_5700x
sudo python3 tools/submit_dump.py --out ./my_5700x --with-load
```

The default capture is one idle snapshot (~3 s settle). `--with-load` adds
one all-core snapshot (~15 s settle via `stress-ng`); when `stress-ng` is not
installed the load snapshot is skipped with a note instead of failing.

The tool only **reads** sysfs (`pm_table`, `pm_table_version`,
`pm_table_size`, cpuinfo/topology, kernel and driver version strings). The
only writes are the bundle files under `--out`. No SMU command is ever sent.

Attach the resulting directory to a GitHub issue with the exact CPU model.

### Privacy: what a bundle contains

- `meta.json`: CPU model string, thread/core counts, the logical-CPU to
  core-id topology map, kernel release, `ryzen_smu` driver version, SMU
  firmware version, MP1 interface version, numeric codename, PM table
  version/size, UTC timestamp, snapshot list
- `pm_table_idle.bin` (+ `pm_table_load.bin`): raw PM-table snapshots,
  exact-size float32 arrays, nothing else

Deliberately excluded: hostnames, dmesg (which can carry USB/GPU serial
numbers), MAC/IP addresses, usernames/home paths, and every
`/sys/kernel/ryzen_smu_drv` interface except the read-only telemetry files
above. Snapshot files contain only the raw PM-table bytes returned by the
driver. They are not sanitized or semantically labelled; contributors should
still review the bundle before publishing it.

## Comparing dumps (maintainers)

```bash
python3 tools/compare_tables.py bundleA bundleB [bundleC ...]
python3 tools/compare_tables.py --block 172 --block 180 --block 212 bundleA bundleB
```

Comparison is only meaningful within one `(pm_version, size)`; mixed tables
are reported per bundle but never compared index-wise.

Bundles are untrusted input. The comparison tool requires `meta.json` to be a
JSON object with a hexadecimal PM-table version, a positive float32-aligned
size, a positive physical-core count, and at least one unique non-empty
snapshot path. Absolute paths, `..` components, symlinks escaping the bundle,
missing files, and size mismatches are rejected before snapshot loading. These
checks protect the maintainer's filesystem; they do not authenticate the
submitter or prove that the metadata describes the attached hardware.

Per bundle the tool reports:

1. **Detected active SMU slots**, derived from zero-signature per-core
   blocks via `hwgate.detect_active_slots()` — no assumed tuple. Block bases
   default to the locally validated profile for that table (Vermeer
   `0x380905` today); `--block` overrides them for unmapped tables. Only
   zero-signature blocks are valid inputs: a present core must never
   legitimately read exactly 0.0 there, which excludes temperature (fused
   lanes report live die temperatures) and effective frequency (a sleeping
   present core reads 0.0).
2. **Topology consistency**: physical core count from the bundle meta against
   the detected slot count.
3. **Profile verdict**: whether the detected layout matches the locally
   validated tuple — i.e. what `_fused_layout_matches()` would decide.
   A foreign layout is REFUSED fail-closed; that is the expected outcome for
   a differently-binned chip, not an error.

Across same-table bundles it reports bit-identical indices (layout-common
candidates such as clocks, rails and limits) versus differing indices
(machine- or load-specific), with the widest spreads listed first. Identity is
tested on each original four-byte float32 lane, so signed zero and distinct NaN
payloads are not collapsed by Python float comparison.

### Reading a comparison

- Indices identical across machines *and* load states are the only ones that
  can be layout-common. Identical across machines but at one load state may
  still be coincidence — check the spread under load.
- A differing fused-slot layout between two same-model samples confirms the
  layout is per-chip (binning), not per-model. Do not "fix" the profile to
  the new layout; the profile keeps refusing it.
- A new (version, size) pair is a new mapping task, not an extension of an
  existing profile.

## Tooling map

| Tool | Side | Purpose |
|---|---|---|
| `tools/submit_dump.py` | contributor | standardized read-only bundle |
| `tools/compare_tables.py` | maintainer | layout + index comparison |
| `hwgate.detect_active_slots()` | shared | zero-signature slot derivation |
| `hwgate._fused_layout_matches()` | guard | fail-closed profile acceptance |
| `tests/test_community.py` | tests | detector, comparison, bundle schema |

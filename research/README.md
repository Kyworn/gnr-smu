# Research scripts

Measurement scripts, one per question asked. Grouped by architecture, then by
topic. Filenames are preserved from the original flat `research/` directory;
only the grouping is new.

```text
research/
├── granite_ridge/        # Ryzen 7 9800X3D / Ryzen 9 9950X3D (Zen 5)
│   ├── mapping/          # PM-table layout: audit_map (the map's regression
│   │                     #   gate), zone-0x000 correction, coverage
│   ├── edc/              # EDC value search (closed: no live EDC value)
│   ├── l3/               # per-CCD load tests, L3-traffic coupling evidence
│   ├── historical/       # superseded profiling passes, kept as evidence
│   └── PLAN.md           # original Granite Ridge decoding plan (French)
├── vermeer/              # Ryzen 5 5600X (Zen 3), read-only
│   ├── mapping/          # offline analysis of the captured snapshots
│   ├── transient/        # paired transient logger + offline analysis
│   └── topology/         # core-disable fuse cross-check (SMN *read* only)
├── dangerous/            # MAY PERFORM SMU/SMN WRITES — see README there
└── compare_tables.py     # compat wrapper, canonical: tools/compare_tables.py
```

Current experiment vs historical investigation vs dangerous experiment is the
distinction that matters here: `historical/` holds passes that concluded
without identifying their targets (kept because they record what was ruled
out), `dangerous/` holds the only scripts that can send mailbox commands.

Nothing under `research/` is imported by the runtime package (`gnr_smu/`)
or by the tools in normal use.

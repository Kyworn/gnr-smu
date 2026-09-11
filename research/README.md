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
│   └── historical/       # superseded profiling passes, kept as evidence
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

Active and historical scripts are inert when imported. Live experiments use
the canonical hardware detector and require the exact profile their offsets
and topology were measured on before creating workloads or output files.
Vermeer experiments also retain the runtime's fused-layout validation.
Hardware-monitor inputs are discovered by device name and exact channel label;
missing or ambiguous devices fail before the experiment starts.

The current research backlog is maintained in
[`docs/RESEARCH_BACKLOG.md`](../docs/RESEARCH_BACKLOG.md). Completed plans are
not retained separately when their results and negative evidence already live
in the architecture documents and scripts.

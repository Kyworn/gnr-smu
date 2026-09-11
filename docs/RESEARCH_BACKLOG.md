# Research backlog

This file contains only unresolved research questions. Completed work and
negative results belong in the architecture evidence documents, principally
[the 9800X3D PM-table map](architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md)
and [Granite Ridge safety findings](architectures/granite_ridge/FINDINGS.md).

## Open Granite Ridge research

- [ ] **IDs 0x58-0x6F** — Identify what these MSG IDs do after the 8 cores' Curve Optimizer arrays. Not by sending them: `docs/architectures/granite_ridge/FINDINGS.md` records the whole range freezing MP1 on first write, and they are on the never-send list for that reason. This needs a firmware dump or another implementation to read, not a probe.
- [ ] **HSMP** — Explore if the Host System Management Port (HSMP) ACPI interface provides cleaner standard data for power limits than the direct mailbox polling.
- [ ] **Unidentified floats** — Continue identifying the unlabelled or
  low-confidence values in the 457-float `0x620105` table. Do not promote a
  field without an independent discriminator; complete index coverage does
  not mean complete semantic identification.


- [ ] **Demoted offsets — domains narrowed, still unidentified** — thirteen fields are confirmed *not* to be what the map claimed; two profiling passes narrowed them without naming any. Full write-up in [9800X3D_PM_TABLE_0x620105.md](architectures/granite_ridge/9800X3D_PM_TABLE_0x620105.md#demoted-offsets-domains-narrowed-not-identified-2026-07-30). What is left open:
  - **d[16]/d[452] and d[212]/d[453]** — four bounded counters in two opposed pairs (the first drains under load and refills to a hard ceiling, the second does the reverse; anti-correlated down to r = −0.96). Consistent with a consumed/remaining budget pair, but the unit is unknown and no system sensor exposes anything to check it against. Evidence: `research/granite_ridge/historical/profile_demoted.py`, `research/granite_ridge/historical/transient_demoted.py`.
  - **d[448]/d[449]** — fit load linearly at r² ≈ 0.97, but TDC current, package power, PPT and Tctl are mutually indistinguishable at that level. Needs a load that decouples them.
  - **d[220], d[298]/d[299]** — do not respond to a 120 W → 15 W step at all, which rules out every load-coupled domain. d[298]/d[299]/d[456] are a locked triple off one sensor that is thermally decoupled from the die.
  - **d[17], d[64], d[210], d[278]** — only trend (r² 0.56-0.77); no known axis explains them. d[17] was "Core Power Aggregate (W) / CONFIRMED" and is disproved (exceeds package power at 8 threads, non-monotonic in load). `sum(d[333-340])` is monotonic and the better aggregate candidate, but sums to only ~34 % of package power, so its scope is unverified too.
- [ ] **A load point that varies frequency at constant power** — the blocker for all of the above. Every stressor tried pushes power, current, temperature and utilisation up together, so regression cannot separate them, and response time cannot either: Tctl falls 86 → 52 °C inside one 0.2 s sample, so the die's thermal constant is below the table's update rate. Candidate levers: locked-frequency runs at two different core counts, or a fixed draw at two ambient temperatures.

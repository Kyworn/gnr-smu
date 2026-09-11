# Dangerous research scripts — read before running anything here

Every script in this directory can perform hardware writes:

| script | what it can send |
|---|---|
| `smu_send.py` | MP1 mailbox commands through raw SMN (`setpci`), including PPT/TDC/EDC limits |
| `smu_advanced.py` | MP1 and RSMU mailbox commands through raw SMN, plus `/dev/mem` reads |
| `probe_tdc_edc.py` | PPT/TDC/EDC limit writes through the driver mailbox (below stock, volatile) |

Rules:

- Do not run these casually. Do not run them on unvalidated hardware.
- They refuse via the `gnr_smu` safety gates: live-profile detection,
  `smu_writes_supported()`, and complete message-plus-payload validation through
  `smu_command_allowed()`. Power limits are confined to evidence-backed profile
  ranges and Curve Optimizer payloads must match the canonical encoder; an allowlisted
  message ID alone is not authorization. The TDC/EDC probe additionally requires the
  exact validated 9800X3D profile before any transaction. Do not loosen those gates
  to make a run succeed.
- They are never imported by runtime code (`gnr_smu/`) or user tools
  (`tools/`). Tests may import them only under mocks that make any workload
  or hardware transaction fail immediately.
- They are compiled and import-checked, but nothing outside the isolated
  safety tests may depend on them.

`research/vermeer/topology/vermeer_fuse_check.py` is deliberately NOT here:
it only performs the driver's established 4-byte SMN *read* protocol (write
size asserted) against a hardcoded address list.

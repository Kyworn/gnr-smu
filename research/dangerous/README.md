# Dangerous research scripts — read before running anything here

Every script in this directory can perform hardware writes:

| script | what it can send |
|---|---|
| `smu_send.py` | MP1 mailbox commands through raw SMN (`setpci`), including PPT/TDC/EDC limits |
| `smu_advanced.py` | MP1 and RSMU mailbox commands through raw SMN, plus `/dev/mem` reads |
| `probe_tdc_edc.py` | PPT/TDC/EDC limit writes through the driver mailbox (below stock, volatile) |

Rules:

- Do not run these casually. Do not run them on unvalidated hardware.
- They refuse via the `gnr_smu` safety gates (`smu_writes_supported()`,
  `msg_id_blocked()`) — do not loosen those gates to make a run succeed.
- They are never imported by runtime code (`gnr_smu/`), user tools
  (`tools/`) or tests. Keep it that way.
- They are excluded from compile-and-import checks only in the sense that
  nothing may depend on them; they must still compile.

`research/vermeer/topology/vermeer_fuse_check.py` is deliberately NOT here:
it only performs the driver's established 4-byte SMN *read* protocol (write
size asserted) against a hardcoded address list.

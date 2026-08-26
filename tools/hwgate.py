#!/usr/bin/env python3
"""Refuse to interpret the PM table on hardware it was never measured on.

Every offset in PM_TABLE_MAP.md comes from exactly one machine: a Ryzen 7 9800X3D,
8 cores / 1 CCD, PM table v0x620105. None of it is validated anywhere else. Two ways
that goes wrong on someone else's box:

  - A different table version moves every offset. The bytes still parse as 457 floats,
    so the tools show plausible numbers that are simply the wrong fields. A silently
    wrong reading is worse than an error, because nothing looks broken.
  - A different core count changes the per-core array widths. d[317-324] is 8 wide
    here; on a 16-core part everything from there on shifts.

Reading the wrong field displays a wrong number. *Writing* a limit derived from a
wrong field pushes it into the SMU. That already happened once on validated hardware:
the thermal limit (88 °C) was read as TDC and pre-filled the write dialog as 88 A.

Shared by the GUI and the telemetry exporter so the rule cannot drift between them.

Self-check: python3 tools/hwgate.py
"""

import struct

VERSION_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_version"
EXPECTED_PM_VERSION = 0x620105
EXPECTED_CORES = 8

# MP1 message IDs that must never be sent, wherever the send happens. This lived as a
# set literal in the CLI and as two separate ifs in the GUI, and the research tools had
# no equivalent at all — the same three-copies-of-one-rule shape that let the TDC/EDC
# mapping stay wrong in one copy for months.
#
#   0x03-0x0D, 0x10   dangerous MP1 IDs (docs/FINDINGS.md)
#   0x58-0x5D         freeze MP1 on this part: no response, recovery needs a reboot
BLOCKED_MSG_IDS = {0x10} | set(range(0x03, 0x0E)) | set(range(0x58, 0x5E))


def msg_id_blocked(msg_id):
    """(blocked, reason). Reason is None when the ID is allowed."""
    if 0x58 <= msg_id <= 0x5D:
        return True, (f"MSG 0x{msg_id:02x} freezes MP1 on Granite Ridge — no response, "
                      "recovery needs a reboot")
    if msg_id in BLOCKED_MSG_IDS:
        return True, f"MSG 0x{msg_id:02x} is on the never-send list"
    return False, None


_cached = None


def _core_count(cpuinfo="/proc/cpuinfo"):
    """Physical cores, from the distinct 'core id' values. 0 if unreadable — an
    unknown core count is not treated as a mismatch, since the version check is the
    load-bearing one and /proc/cpuinfo formats vary."""
    try:
        with open(cpuinfo) as f:
            return len({l.split(":", 1)[1].strip()
                        for l in f if l.startswith("core id")})
    except Exception:
        return 0


def hardware_supported():
    """(ok, reason). Cached: the answer cannot change while the process runs."""
    global _cached
    if _cached is not None:
        return _cached

    try:
        with open(VERSION_PATH, "rb") as f:
            ver = struct.unpack("<I", f.read(4))[0]
    except Exception as e:
        _cached = (False, f"cannot read pm_table_version ({e}) — is ryzen_smu loaded?")
        return _cached

    if ver != EXPECTED_PM_VERSION:
        _cached = (False, f"PM table {hex(ver)}, but every offset in this tool was "
                          f"measured on {hex(EXPECTED_PM_VERSION)}")
        return _cached

    cores = _core_count()
    if cores and cores != EXPECTED_CORES:
        _cached = (False, f"{cores} physical cores — the per-core offsets are mapped "
                          f"{EXPECTED_CORES} wide and shift on any other count")
        return _cached

    _cached = (True, f"PM table {hex(ver)}, {cores or 'unknown'} cores")
    return _cached


if __name__ == "__main__":
    import tempfile

    # The parser is the only part worth checking without the hardware present.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("processor\t: 0\ncore id\t\t: 0\nprocessor\t: 1\ncore id\t\t: 0\n"
                "processor\t: 2\ncore id\t\t: 1\n")
        two_cores = f.name
    assert _core_count(two_cores) == 2, "two distinct core ids, four processor lines"
    assert _core_count("/nonexistent") == 0, "unreadable cpuinfo must not claim a count"

    for blocked_id in (0x03, 0x0D, 0x10, 0x58, 0x5D):
        assert msg_id_blocked(blocked_id)[0], f"0x{blocked_id:02x} must be blocked"
    for allowed_id in (0x02, 0x0E, 0x3C, 0x3D, 0x3E, 0x50, 0x57, 0x5E):
        assert not msg_id_blocked(allowed_id)[0], f"0x{allowed_id:02x} must be allowed"

    ok, why = hardware_supported()
    print(f"{'SUPPORTED' if ok else 'REFUSED'}: {why}")
    print(f"this machine reports {_core_count()} physical cores")
    print(f"never-send list: {len(BLOCKED_MSG_IDS)} message IDs")

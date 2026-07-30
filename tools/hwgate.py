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

    ok, why = hardware_supported()
    print(f"{'SUPPORTED' if ok else 'REFUSED'}: {why}")
    print(f"this machine reports {_core_count()} physical cores")

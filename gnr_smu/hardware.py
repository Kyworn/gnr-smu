#!/usr/bin/env python3
"""Hardware detection and slot topology for GNR-SMU telemetry tools.

Resolves the live machine to a HardwareProfile (fail-closed) and owns
the SMU-slot topology helpers. Extracted verbatim from tools/hwgate.py;
only the module header and imports changed.
"""

import struct

from .profiles import PROFILES


VERSION_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_version"
SIZE_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_size"
PM_TABLE_PATH = "/sys/kernel/ryzen_smu_drv/pm_table"


_cached = None


def _core_count(cpuinfo="/proc/cpuinfo"):
    """Return physical cores from distinct (package, core-id) pairs."""
    try:
        pairs = set()
        package = "0"
        core = None
        with open(cpuinfo) as f:
            for line in f:
                if not line.strip():
                    if core is not None:
                        pairs.add((package, core))
                    package, core = "0", None
                elif line.startswith("physical id"):
                    package = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core = line.split(":", 1)[1].strip()
        if core is not None:
            pairs.add((package, core))
        return len(pairs)
    except Exception:
        return 0


def _read_uint(path):
    with open(path, "rb") as f:
        data = f.read(8)
    if len(data) < 4:
        raise ValueError(f"short read ({len(data)} bytes)")
    return struct.unpack("<I", data[:4])[0]


def _cpu_model(cpuinfo="/proc/cpuinfo"):
    try:
        with open(cpuinfo) as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


def detect_active_slots(values, bases, width=8):
    """Derive the active SMU slot set from zero-signature per-core blocks.

    A slot counts as active when it reads non-zero in ANY of the given
    block bases.  Callers must only pass blocks where a present core can
    never legitimately read exactly 0.0 (power/voltage/frequency — never
    temperature, whose fused lanes report live die temperatures, nor
    effective frequency, where a deeply sleeping present core reads 0.0).
    Returns a sorted tuple of slot indices.  Read-only over `values`.
    """
    active = set()
    for base in bases:
        for s in range(width):
            if values[base + s] != 0.0:
                active.add(s)
    return tuple(sorted(active))


def _fused_layout_matches(profile, pm_path=None):
    """Check the profile's fused-slot layout against the live PM table.

    The 5600X tuple was measured on one physical CPU, and which CCD cores a
    5600X fuses off depends on binning (down-binned dies, even dual-CCD
    SKUs exist) — it is not guaranteed identical on every chip.  Rather
    than trust the tuple blindly, verify it against read-only data: in the
    zero-signature per-core blocks (power/voltage/frequency) the fused slots
    read exactly 0.0 on the validated machine while every mapped slot reads
    a real value.
    Anything else means a different layout, and the profile refuses instead
    of mislabelling cores.  Fails closed in both directions.

    Several independent blocks carry the same signature (verified exact-zero
    / non-zero across thousands of samples at all load levels), so all of
    them are checked via detect_active_slots().  The temperature block is
    excluded on purpose: fused temp lanes report live die temperatures, not
    zero.  So is the effective-frequency block: a deeply sleeping present
    core legitimately reads 0.0 there.
    """
    if pm_path is None:
        pm_path = PM_TABLE_PATH
    try:
        with open(pm_path, "rb") as f:
            data = f.read(profile.table_size)
        if len(data) != profile.table_size:
            return False, (f"{profile.name}: cannot validate the fused-core "
                           f"layout (short PM-table read)")
        values = struct.unpack(f"<{profile.float_count}f", data)
    except Exception as e:
        return False, (f"{profile.name}: cannot validate the fused-core "
                       f"layout ({e})")
    bad, dead = [], []
    expected = set(profile.core_slots)
    per_block = {}
    for base in (profile.core_power, profile.core_voltage,
                 profile.core_frequency):
        got = set(detect_active_slots(values, (base,)))
        per_block[base] = sorted(got)
        bad += sorted(got - expected)
        dead += sorted(expected - got)
    if bad or dead:
        return False, (
            f"{profile.name}: PM-table fused-core layout differs from the "
            f"validated machine "
            f"(slots unexpectedly live: {sorted(set(bad))}, "
            f"mapped lanes reading 0.0: {sorted(set(dead))}); "
            f"per-block detection: "
            + ", ".join(f"d[{b}]={per_block[b]}"
                        for b in sorted(per_block))
            + "; refusing instead of mislabelling cores")
    return True, ""


def get_hardware_profile():
    """Return ``(profile_or_none, reason)``; cached for the process lifetime."""
    global _cached
    if _cached is not None:
        return _cached
    try:
        version = _read_uint(VERSION_PATH)
        table_size = _read_uint(SIZE_PATH)
    except Exception as e:
        _cached = (None, f"cannot read PM-table metadata ({e}) — is ryzen_smu loaded?")
        return _cached

    cores = _core_count()
    profile = PROFILES.get((version, table_size, cores))
    cpu_model = _cpu_model()
    if profile is not None and profile.cpu_model not in cpu_model:
        profile = None
    if profile is not None and profile.core_slots:
        # One machine's fused-off slots are not every machine's: verify the
        # layout against the live table before trusting the tuple.
        ok, slot_why = _fused_layout_matches(profile)
        if not ok:
            _cached = (None, slot_why)
            return _cached
    if profile is None:
        _cached = (
            None,
            f"unsupported PM table {hex(version)}, {table_size} bytes, "
            f"{cores or 'unknown'} physical cores, CPU {cpu_model or 'unknown'}",
        )
        return _cached
    _cached = (
        profile,
        f"{profile.name}: PM table {hex(version)}, {table_size} bytes, {cores} cores",
    )
    return _cached


def hardware_supported():
    """Compatibility API used by telemetry callers: ``(ok, reason)``."""
    profile, why = get_hardware_profile()
    return profile is not None, why


def map_labels_supported():
    """The full PM_TABLE_MAP.md is currently the 9800X3D/457-float map."""
    profile, _ = get_hardware_profile()
    return profile is not None and profile.pm_version == 0x620105

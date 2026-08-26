#!/usr/bin/env python3
"""Hardware profiles and safety gates for Granite Ridge PM-table tools.

Telemetry layouts are keyed by PM-table version, byte size and physical core count.
SMU writes have a separate, stricter gate: validating read-only telemetry on a CPU
does not establish that mailbox commands or Curve Optimizer IDs are safe on it.
"""

from dataclasses import dataclass
import struct

VERSION_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_version"
SIZE_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_size"


@dataclass(frozen=True)
class HardwareProfile:
    name: str
    cpu_model: str
    pm_version: int
    table_size: int
    cores: int
    core_voltage: int
    core_temp: int
    core_freq: int
    core_power: int
    core_c6: int
    core_light_cstate: int
    core_boost_limit: int
    ppt_msg: int
    tdc_msg: int
    edc_msg: int
    stock_ppt: int
    stock_tdc: int
    stock_edc: int
    co_mode: str
    co_msg: int = 0
    allow_smu_writes: bool = False

    @property
    def float_count(self):
        return self.table_size // 4


PROFILES = {
    (0x620105, 1828, 8): HardwareProfile(
        "AMD Ryzen 7 9800X3D", "AMD Ryzen 7 9800X3D", 0x620105, 1828, 8,
        core_voltage=309, core_temp=317, core_freq=325, core_power=333,
        core_c6=349, core_light_cstate=357, core_boost_limit=373,
        ppt_msg=0x3E, tdc_msg=0x3D, edc_msg=0x3C,
        stock_ppt=162, stock_tdc=120, stock_edc=180,
        co_mode="legacy_per_message",
        allow_smu_writes=True,
    ),
    (0x620205, 2452, 16): HardwareProfile(
        "AMD Ryzen 9 9950X3D", "AMD Ryzen 9 9950X3D", 0x620205, 2452, 16,
        core_voltage=317, core_temp=333, core_freq=349, core_power=365,
        core_c6=397, core_light_cstate=413, core_boost_limit=445,
        # ZenStates-Core's Granite Ridge profile inherits the Zen 4 MP1 command
        # table: Fast/PPT=0x3E, TDC=0x3C, EDC=0x3D, per-core DLDO margin=0x35.
        ppt_msg=0x3E, tdc_msg=0x3C, edc_msg=0x3D,
        stock_ppt=200, stock_tdc=160, stock_edc=225,
        co_mode="packed_core_mask", co_msg=0x35,
        allow_smu_writes=True,
    ),
}

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


def smu_writes_supported():
    """Keep telemetry validation and mailbox-command validation separate."""
    profile, why = get_hardware_profile()
    if profile is None:
        return False, why
    if not profile.allow_smu_writes:
        return False, f"SMU writes are not validated on {profile.name}"
    return True, why


def smu_message_supported(profile, msg_id):
    """Only allow message IDs explicitly present in the selected profile."""
    allowed = {profile.ppt_msg, profile.tdc_msg, profile.edc_msg}
    if profile.co_mode == "legacy_per_message":
        allowed.update(range(0x50, 0x50 + profile.cores))
    elif profile.co_mode == "packed_core_mask":
        allowed.add(profile.co_msg)
    return msg_id in allowed


def curve_optimizer_command(profile, core, margin):
    """Return the profile-specific ``(MP1 message, arg0)`` for one physical core."""
    if not 0 <= core < profile.cores:
        raise ValueError(f"core {core} outside 0..{profile.cores - 1}")
    if not -50 <= margin <= 20:
        raise ValueError("Curve Optimizer margin must be between -50 and 20")
    if profile.co_mode == "legacy_per_message":
        return 0x50 + core, margin & 0xFFFFFFFF
    if profile.co_mode == "packed_core_mask":
        # Zen 3+: [31:28] CCD, [23:20] core-within-CCD, [15:0] signed margin.
        core_mask = (core // 8) << 28 | (core % 8) << 20
        return profile.co_msg, core_mask | (margin & 0xFFFF)
    raise ValueError(f"unsupported CO command mode: {profile.co_mode}")


def map_labels_supported():
    """The full PM_TABLE_MAP.md is currently the 9800X3D/457-float map."""
    profile, _ = get_hardware_profile()
    return profile is not None and profile.pm_version == 0x620105


if __name__ == "__main__":
    import tempfile

    def _cpuinfo(*blocks):
        """Real /proc/cpuinfo shape: blank-line-separated blocks, which is what the
        parser keys on."""
        return "\n\n".join(blocks) + "\n"

    # The parser is the only part worth checking without the hardware present, and it
    # got more complex when it started tracking (package, core id) pairs rather than
    # core ids alone. That is the reason to keep these, not to drop them.
    def _count(text):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
            path = f.name
        # outside the with: the file has to be flushed before it is read back
        return _core_count(path)

    one_socket = _cpuinfo(
        "processor\t: 0\nphysical id\t: 0\ncore id\t\t: 0",
        "processor\t: 1\nphysical id\t: 0\ncore id\t\t: 0",
        "processor\t: 2\nphysical id\t: 0\ncore id\t\t: 1",
    )
    assert _count(one_socket) == 2, "two distinct core ids, three processor blocks"

    # The whole point of keying on (package, core): core id 0 appears in both sockets
    # and must count twice. The previous set-of-core-ids parser returned 1 here.
    two_sockets = _cpuinfo(
        "processor\t: 0\nphysical id\t: 0\ncore id\t\t: 0",
        "processor\t: 1\nphysical id\t: 1\ncore id\t\t: 0",
    )
    assert _count(two_sockets) == 2, "same core id on two packages is two cores"

    # No trailing blank line after the last block — the parser has to flush it.
    assert _count("processor\t: 0\nphysical id\t: 0\ncore id\t\t: 0") == 1

    assert _core_count("/nonexistent") == 0, "unreadable cpuinfo must not claim a count"

    # An allowlist and a never-send list are different things and both have to hold:
    # smu_message_supported() says what a profile is known to accept, msg_id_blocked()
    # says what nothing may send on any part.
    for blocked_id in (0x03, 0x0D, 0x10, 0x58, 0x5D):
        assert msg_id_blocked(blocked_id)[0], f"0x{blocked_id:02x} must be blocked"
    for allowed_id in (0x02, 0x0E, 0x3C, 0x3D, 0x3E, 0x50, 0x57, 0x5E):
        assert not msg_id_blocked(allowed_id)[0], f"0x{allowed_id:02x} must be allowed"

    profile, why = get_hardware_profile()
    print(f"{'SUPPORTED' if profile else 'REFUSED'}: {why}")
    print(f"this machine reports {_core_count()} physical cores")
    print(f"never-send list: {len(BLOCKED_MSG_IDS)} message IDs")
    if profile:
        print(f"per-core temperatures: d[{profile.core_temp}.."
              f"{profile.core_temp + profile.cores - 1}]")
        writes, write_why = smu_writes_supported()
        print(f"SMU writes: {'enabled' if writes else 'blocked'} ({write_why})")

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
    # Ceilings for the three power limits, in the same units as stock_*. These are the
    # maxima the front-ends already offered, not a validated safe envelope: above
    # stock is PBO territory and nothing here has measured where it stops being safe.
    # They exist so the *argument* is bounded somewhere other than a spinbox.
    # Raw SMN mailbox addresses, for the research tools that drive the mailbox through
    # setpci instead of the driver. Measured on the 9800X3D; a profile that leaves them
    # empty makes those tools refuse rather than poke the same registers on a part
    # where they may be something else entirely.
    #   (MSG, RSP, ARG0)
    mp1_smn: tuple = ()
    rsmu_smn: tuple = ()
    max_ppt: int = 0
    max_tdc: int = 0
    max_edc: int = 0
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
        # Measured by read-back, not assumed: research/probe_tdc_edc.py writes a
        # distinctive value and reports which PM field moved. 0x3C moves d[8] (TDC),
        # 0x3D moves d[63] (EDC). The reverse order was this repo's for months.
        ppt_msg=0x3E, tdc_msg=0x3C, edc_msg=0x3D,
        stock_ppt=162, stock_tdc=120, stock_edc=180,
        mp1_smn=(0x3B10530, 0x3B1057C, 0x3B109C4),
        rsmu_smn=(0x3B10524, 0x3B10570, 0x3B10A40),
        max_ppt=250, max_tdc=200, max_edc=250,
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
        max_ppt=300, max_tdc=250, max_edc=300,
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
#   0x58-0x6F         freeze MP1 on this part: no response, recovery needs a reboot
#
# The freeze range is the one docs/FINDINGS.md actually tested. This list said
# 0x58-0x5D for a while, which is narrower than the measurement for no stated reason
# and left 0x5E-0x6F reachable from the research tools.
BLOCKED_MP1_IDS = frozenset({0x10} | set(range(0x03, 0x0E)) | set(range(0x58, 0x70)))

# RSMU is the other mailbox, and "not on the MP1 list" is not the same statement as
# "safe on RSMU". Only the two table commands are established here — 0x04 returns the
# PM table's DRAM address and 0x05 triggers the transfer — so RSMU runs as an
# allowlist rather than a blocklist. docs/FINDINGS.md records the driver itself
# rejecting the 0x58-0x6F range on this endpoint.
RSMU_ALLOWED_IDS = frozenset({0x04, 0x05})

MAILBOXES = ("mp1", "rsmu")


def msg_id_blocked(msg_id, mailbox="mp1"):
    """(blocked, reason). Reason is None when the ID is allowed.

    The mailbox matters. MP1 and RSMU are separate endpoints with separate ID
    namespaces, so an MP1 never-send list says nothing about the RSMU ID that
    happens to share its number: RSMU 0x04/0x05 are the ordinary read-the-PM-table
    pair, while MP1 0x04/0x05 are on the dangerous list. Applying one list to the
    other blocks a harmless read and would tell you nothing about a harmful write.
    """
    if mailbox not in MAILBOXES:
        # Fail closed. A typo would otherwise mean "not MP1, therefore allowed", and
        # the caller most likely also resolved it to some default endpoint.
        return True, (f"unknown mailbox {mailbox!r} — refusing rather than guessing "
                      f"which never-send list applies (known: {', '.join(MAILBOXES)})")
    if mailbox == "rsmu":
        if msg_id in RSMU_ALLOWED_IDS:
            return False, None
        return True, (f"RSMU 0x{msg_id:02x} is not one of the established table "
                      f"commands ({', '.join(f'0x{i:02x}' for i in sorted(RSMU_ALLOWED_IDS))})")
    if 0x58 <= msg_id <= 0x6F:
        return True, (f"MSG 0x{msg_id:02x} freezes MP1 on Granite Ridge — no response, "
                      "recovery needs a reboot")
    if msg_id in BLOCKED_MP1_IDS:
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


def payload_allowed(profile, msg_id, arg0):
    """(ok, reason) for the *argument* of a power-limit write.

    Nothing checked this before: both front-ends bounded the number in their own
    spinbox and then handed an unchecked arg0 to the sender, so any direct caller —
    or a GUI field converted through ``arg0 & 0xFFFFFFFF`` — reached the mailbox with
    whatever it liked. BASELINE_SNAPSHOT.md records ``ppt 0`` locking the CPU to
    606 MHz, which is the concrete reason a floor exists at all.

    Message IDs that are not power limits pass through: Curve Optimizer arguments are
    built and range-checked by curve_optimizer_command().
    """
    bounds = {profile.ppt_msg: ("PPT", "W", profile.stock_ppt, profile.max_ppt),
              profile.tdc_msg: ("TDC", "A", profile.stock_tdc, profile.max_tdc),
              profile.edc_msg: ("EDC", "A", profile.stock_edc, profile.max_edc)}
    if msg_id not in bounds:
        return True, None
    name, unit, stock, ceiling = bounds[msg_id]
    if not isinstance(arg0, int) or arg0 < 0:
        return False, f"{name} argument {arg0!r} is not a non-negative integer"
    value = arg0 / 1000.0
    if value <= 0:
        return False, (f"{name} 0 {unit} is a total throttle, not a limit — the CPU "
                       "locks to its minimum multiplier until reboot")
    if value > ceiling:
        return False, (f"{name} {value:g} {unit} is above the {ceiling} {unit} ceiling "
                       f"for {profile.name} (stock is {stock} {unit})")
    return True, None


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
    # The power-limit mapping is the same on every Granite Ridge part, and getting it
    # backwards writes the TDC box into EDC. It was wrong here once; assert it rather
    # than trust the next person editing the table above.
    for key, prof in PROFILES.items():
        assert (prof.ppt_msg, prof.tdc_msg, prof.edc_msg) == (0x3E, 0x3C, 0x3D), \
            f"{prof.name}: power-limit message IDs must be PPT 0x3E, TDC 0x3C, EDC 0x3D"

    # 0x5E and 0x6F are in here because the self-test used to assert 0x5E was ALLOWED,
    # while docs/FINDINGS.md records the whole 0x58-0x6F range freezing MP1.
    for blocked_id in (0x03, 0x0D, 0x10, 0x58, 0x5D, 0x5E, 0x6F):
        assert msg_id_blocked(blocked_id)[0], f"0x{blocked_id:02x} must be blocked"
    for allowed_id in (0x02, 0x0E, 0x3C, 0x3D, 0x3E, 0x50, 0x57, 0x70):
        assert not msg_id_blocked(allowed_id)[0], f"0x{allowed_id:02x} must be allowed"

    # A different mailbox is a different ID namespace: RSMU 0x04/0x05 read the PM
    # table and must not inherit the MP1 list. But RSMU is an allowlist, so an ID that
    # merely escapes the MP1 list does not get through either.
    for rsmu_id in (0x04, 0x05):
        assert not msg_id_blocked(rsmu_id, mailbox="rsmu")[0], \
            f"RSMU 0x{rsmu_id:02x} is an established table command"
    for rsmu_id in (0x3C, 0x5D, 0x00, 0x70):
        assert msg_id_blocked(rsmu_id, mailbox="rsmu")[0], \
            f"RSMU 0x{rsmu_id:02x} is not established and must not pass"

    probe_profile = PROFILES[(0x620105, 1828, 8)]
    assert payload_allowed(probe_profile, 0x3E, 162_000)[0], "stock PPT must pass"
    assert payload_allowed(probe_profile, 0x3E, 250_000)[0], "the ceiling itself passes"
    assert not payload_allowed(probe_profile, 0x3E, 0)[0], "PPT 0 W locks the CPU"
    assert not payload_allowed(probe_profile, 0x3E, 250_001)[0], "above the ceiling"
    assert not payload_allowed(probe_profile, 0x3C, -1)[0], "negative is not a limit"
    assert payload_allowed(probe_profile, 0x50, 0)[0], "CO is bounded elsewhere"

    # An unrecognised mailbox must fail closed, not fall through to "allowed".
    for junk in ("MP1", "rsmu ", "", None):
        assert msg_id_blocked(0x02, mailbox=junk)[0], \
            f"mailbox {junk!r} must be refused, not treated as non-MP1"

    profile, why = get_hardware_profile()
    print(f"{'SUPPORTED' if profile else 'REFUSED'}: {why}")
    print(f"this machine reports {_core_count()} physical cores")
    print(f"never-send list: {len(BLOCKED_MP1_IDS)} MP1 message IDs; "
          f"RSMU allowlist: {len(RSMU_ALLOWED_IDS)}")
    if profile:
        print(f"per-core temperatures: d[{profile.core_temp}.."
              f"{profile.core_temp + profile.cores - 1}]")
        writes, write_why = smu_writes_supported()
        print(f"SMU writes: {'enabled' if writes else 'blocked'} ({write_why})")

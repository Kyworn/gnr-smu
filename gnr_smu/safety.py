#!/usr/bin/env python3
"""Safety gates for SMU mailbox access (Granite Ridge).

Extracted verbatim from tools/hwgate.py; only the module header and the
import of get_hardware_profile changed.
"""

import struct

from .hardware import get_hardware_profile


# MP1 message IDs that must never be sent, wherever the send happens. This lived as a
# set literal in the CLI and as two separate ifs in the GUI, and the research tools had
# no equivalent at all — the same three-copies-of-one-rule shape that let the TDC/EDC
# mapping stay wrong in one copy for months.
#
#   0x03-0x0D, 0x10   dangerous MP1 IDs (docs/architectures/granite_ridge/FINDINGS.md)
#   0x58-0x6F         freeze MP1 on this part: no response, recovery needs a reboot
#
# The freeze range is the one docs/architectures/granite_ridge/FINDINGS.md actually tested. This list said
# 0x58-0x5D for a while, which is narrower than the measurement for no stated reason
# and left 0x5E-0x6F reachable from the research tools.
BLOCKED_MP1_IDS = frozenset({0x10} | set(range(0x03, 0x0E)) | set(range(0x58, 0x70)))

# RSMU is the other mailbox, and "not on the MP1 list" is not the same statement as
# "safe on RSMU". RSMU therefore runs as an allowlist rather than a blocklist.
# docs/architectures/granite_ridge/FINDINGS.md records the driver itself rejecting the 0x58-0x6F range on
# this endpoint.
# 0x04/0x05 transfer the PM table. 0xD5 is GetDldoPsmMargin, the read-only
# Curve Optimizer query used by ZenStates-Core on Zen 4/5 desktop parts.
RSMU_ALLOWED_IDS = frozenset({0x04, 0x05, 0xD5})

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
        return True, (f"RSMU 0x{msg_id:02x} is not one of the established read-only "
                      f"commands ({', '.join(f'0x{i:02x}' for i in sorted(RSMU_ALLOWED_IDS))})")
    if 0x58 <= msg_id <= 0x6F:
        return True, (f"MSG 0x{msg_id:02x} freezes MP1 on Granite Ridge — no response, "
                      "recovery needs a reboot")
    if msg_id in BLOCKED_MP1_IDS:
        return True, f"MSG 0x{msg_id:02x} is on the never-send list"
    return False, None

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
    if not profile.allow_smu_writes:
        # Defense in depth: the callers check smu_writes_supported() first,
        # but a profile with no validated command must never allowlist one.
        return False
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
    raise ValueError(f"unsupported CO command mode: {profile.co_mode} "
                     f"(no Curve Optimizer write is mapped for {profile.name})")


def curve_optimizer_read_command(profile, core):
    """Return the read-only RSMU ``(message, arg0)`` for one physical core."""
    if not 0 <= core < profile.cores:
        raise ValueError(f"core {core} outside 0..{profile.cores - 1}")
    if not profile.co_get_msg:
        raise ValueError(f"Curve Optimizer readback is not mapped for {profile.name}")
    # Zen 3+: [31:28] CCD, [23:20] core-within-CCD. The low 16 bits are zero
    # for a query and are replaced by the signed margin in the response.
    core_mask = (core // 8) << 28 | (core % 8) << 20
    return profile.co_get_msg, core_mask


def decode_curve_optimizer_response(value):
    """Decode the signed Curve Optimizer margin returned in RSMU arg0."""
    raw = value & 0xFFFF
    return raw if raw < 0x8000 else raw - 0x10000


def read_curve_optimizer_offsets(profile, sysfs_base="/sys/kernel/ryzen_smu_drv"):
    """Read every active per-core CO margin through RSMU GetDldoPsmMargin.

    Although the operation is read-only at the firmware level, the ryzen_smu
    protocol writes the query argument and command ID to sysfs first, so this
    normally requires root. Any rejected/truncated response fails closed.
    Profiles without validated SMU commands are refused outright: even a
    conceptually read-only query performs a sysfs write on this path.
    """
    if not profile.allow_smu_writes:
        raise RuntimeError(
            f"SMU queries are not validated on {profile.name}")
    args_path = f"{sysfs_base}/smu_args"
    cmd_path = f"{sysfs_base}/rsmu_cmd"
    offsets = []
    for core in range(profile.cores):
        msg_id, arg0 = curve_optimizer_read_command(profile, core)
        blocked, reason = msg_id_blocked(msg_id, mailbox="rsmu")
        if blocked:
            raise RuntimeError(reason)
        with open(args_path, "wb") as f:
            f.write(struct.pack("<6I", arg0, 0, 0, 0, 0, 0))
        with open(cmd_path, "wb") as f:
            f.write(struct.pack("<I", msg_id))
        with open(cmd_path, "rb") as f:
            response = f.read(4)
        with open(args_path, "rb") as f:
            response_args = f.read(24)
        if len(response) != 4 or len(response_args) != 24:
            raise RuntimeError(f"truncated Curve Optimizer response for core {core}")
        status = struct.unpack("<I", response)[0]
        if status != 1:
            raise RuntimeError(
                f"Curve Optimizer read rejected for core {core}: RSMU status 0x{status:02X}"
            )
        returned_arg0 = struct.unpack("<6I", response_args)[0]
        offsets.append(decode_curve_optimizer_response(returned_arg0))
    return offsets

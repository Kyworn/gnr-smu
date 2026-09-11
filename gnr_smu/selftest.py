#!/usr/bin/env python3
"""Hardware-gate self-test: profiles, safety lists and slot topology.

Moved verbatim from the `__main__` block of tools/hwgate.py; the body
now runs as main() so both `python3 -m gnr_smu.selftest` and the
`tools/hwgate.py` compatibility wrapper execute it.
"""

from gnr_smu.hardware import (
    _core_count,
    _fused_layout_matches,
    detect_active_slots,
    get_hardware_profile,
    hardware_supported,  # noqa: F401 (imported for API parity checks)
    map_labels_supported,  # noqa: F401
)
from gnr_smu.profiles import PROFILES, validate_profile_globals
from gnr_smu.safety import (
    BLOCKED_MP1_IDS,
    RSMU_ALLOWED_IDS,
    curve_optimizer_command,
    curve_optimizer_read_command,
    decode_curve_optimizer_response,
    msg_id_blocked,
    payload_allowed,
    read_curve_optimizer_offsets,
    smu_message_supported,
    smu_writes_supported,
)


def main():
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
        if not prof.allow_smu_writes:
            continue
        assert (prof.ppt_msg, prof.tdc_msg, prof.edc_msg) == (0x3E, 0x3C, 0x3D), \
            f"{prof.name}: power-limit message IDs must be PPT 0x3E, TDC 0x3C, EDC 0x3D"

    # 0x5E and 0x6F are in here because the self-test used to assert 0x5E was ALLOWED,
    # while docs/architectures/granite_ridge/FINDINGS.md records the whole 0x58-0x6F range freezing MP1.
    for blocked_id in (0x03, 0x0D, 0x10, 0x58, 0x5D, 0x5E, 0x6F):
        assert msg_id_blocked(blocked_id)[0], f"0x{blocked_id:02x} must be blocked"
    for allowed_id in (0x02, 0x0E, 0x3C, 0x3D, 0x3E, 0x50, 0x57, 0x70):
        assert not msg_id_blocked(allowed_id)[0], f"0x{allowed_id:02x} must be allowed"

    # A different mailbox is a different ID namespace: RSMU 0x04/0x05 read the PM
    # table and 0xD5 reads Curve Optimizer. They must not inherit the MP1 list. But
    # RSMU is an allowlist, so an ID that merely escapes the MP1 list does not pass.
    for rsmu_id in (0x04, 0x05, 0xD5):
        assert not msg_id_blocked(rsmu_id, mailbox="rsmu")[0], \
            f"RSMU 0x{rsmu_id:02x} is an established read-only command"
    for rsmu_id in (0x3C, 0x5D, 0x00, 0x70):
        assert msg_id_blocked(rsmu_id, mailbox="rsmu")[0], \
            f"RSMU 0x{rsmu_id:02x} is not established and must not pass"

    probe_profile = PROFILES[(0x620105, 1828, 8)]
    assert (probe_profile.core_c0, probe_profile.core_cc1,
            probe_profile.core_cc6) == (341, 349, 357), \
        "9800X3D must expose the three measured C-state blocks directly"
    assert probe_profile.core_fit is None and probe_profile.core_activity is None, \
        "9800X3D C-state lanes must not also be presented as FIT/activity"
    # Identity slot mapping: lane() must equal the old base + core arithmetic
    # on Granite Ridge, or every front-end silently misreads Vermeer-style parts.
    assert probe_profile.slot(3) == 3 and probe_profile.lane(317, 3) == 320
    assert probe_profile.lane_values(list(range(500)), 333) == list(range(333, 341))
    assert probe_profile.gidx("ppt_limit") == 2
    assert probe_profile.gidx("tctl") == 11
    assert probe_profile.gidx("pkg_power") == 20
    assert probe_profile.gidx("socket_power") is None
    assert probe_profile.gidx("no_such_field") is None
    other = PROFILES[(0x620205, 2452, 16)]
    assert other.gidx("socket_power") == 26, \
        "9950X3D socket power moved to d[26]; the map must say so, not a branch"
    assert other.gidx("ppt_limit") == 2 and other.slot(15) == 15

    # Vermeer: fused-off slots 2-3, writes closed at every layer.
    vermeer = PROFILES[(0x380905, 1488, 6)]
    assert vermeer.float_count == 372
    assert [vermeer.slot(c) for c in range(6)] == [0, 1, 4, 5, 6, 7]
    assert vermeer.lane(188, 2) == 192, \
        "Linux core 2 is SMU slot 4: base + core would read a fused-off lane"
    assert vermeer.lane_values(list(range(500)), 172) == [172, 173, 176, 177, 178, 179]
    assert vermeer.gidx("ppt_limit") is None
    assert vermeer.gidx("tctl") is None
    assert not vermeer.allow_smu_writes
    for _id in (0x3E, 0x3C, 0x3D, 0x35, 0x50, 0xD5):
        assert not smu_message_supported(vermeer, _id), \
            f"0x{_id:02x} must not pass on Vermeer"
    try:
        curve_optimizer_command(vermeer, 0, -30)
    except ValueError:
        pass
    else:
        raise AssertionError("CO write must be unconstructible on Vermeer")
    try:
        read_curve_optimizer_offsets(vermeer)
    except RuntimeError:
        pass
    else:
        raise AssertionError("RSMU CO readback must refuse on Vermeer")
    try:
        vermeer.slot(6)
    except ValueError:
        pass
    else:
        raise AssertionError("slot() must range-check the Linux core index")
    assert vermeer.confidence("core_power") == "high"
    assert vermeer.confidence("core_voltage") == "high"
    assert vermeer.confidence("core_temp") == "confirmed"
    assert probe_profile.confidence("core_power") == "high"
    # Every map key must be a canonical name: anything else is a typo that
    # would otherwise hide as "unsupported".
    for key, prof in PROFILES.items():
        unknown = validate_profile_globals(prof)
        assert not unknown, f"{prof.name}: unknown global names {unknown}"
    assert curve_optimizer_read_command(probe_profile, 0) == (0xD5, 0)
    assert curve_optimizer_read_command(probe_profile, 7) == (0xD5, 7 << 20)
    assert decode_curve_optimizer_response(0xFFFFFFE2) == -30
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
        lanes = [profile.lane(profile.core_temp, c) for c in range(profile.cores)]
        print(f"per-core temperatures: {', '.join(f'd[{i}]' for i in lanes)}")
        writes, write_why = smu_writes_supported()
        print(f"SMU writes: {'enabled' if writes else 'blocked'} ({write_why})")


if __name__ == "__main__":
    main()

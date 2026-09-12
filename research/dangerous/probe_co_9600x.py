#!/usr/bin/env python3
"""Does a per-core Curve Optimizer write land on the right SMU slot on the 9600X?

gnr_smu/safety.py's curve_optimizer_command()/curve_optimizer_read_command() used to
index MP1 message IDs and the RSMU core mask by raw Linux core index, never through
profile.slot(). Harmless on the 9800X3D/9950X3D (identity mapping), but on the 9600X
Linux cores 4 and 5 live on SMU slots 6 and 7 (core_slots=(0,1,2,3,6,7) in
gnr_smu/profiles.py) — the unfixed code would have sent 0x50+4/0x50+5, targeting the
two *fused-off* slots instead. 2026-09-12 fixed both functions to go through
profile.slot() first.

Read-back alone (sudo python3 -c "...read_curve_optimizer_offsets...") already showed
plausible existing values across all six cores. This probe closes the last gap: does a
*write* actually move the core it claims to, and only that one?

Method: pick one core, write a value one lower than its current margin, verify via
RSMU 0xD5 that exactly that core's readback changed and every other core did not, then
restore the original value and confirm the restore too.

Curve Optimizer, unlike PPT/TDC/EDC, is not volatile the same way — it is written back
to whatever the BIOS applies on the next boot, but a reboot is still the recovery path
if this leaves anything in an unexpected state.

    sudo python3 research/dangerous/probe_co_9600x.py [core]
"""

import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from gnr_smu.hardware import get_hardware_profile  # noqa: E402
from gnr_smu.profiles import PROFILES  # noqa: E402
from gnr_smu.safety import (curve_optimizer_command,  # noqa: E402
                            read_curve_optimizer_offsets,
                            smu_command_allowed,
                            smu_writes_supported)

ARGS = "/sys/kernel/ryzen_smu_drv/smu_args"
MP1 = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

EXPECTED_PROFILE = PROFILES[(0x620105, 1828, 6)]
SETTLE = 0.3


def require_probe_profile():
    profile, why = get_hardware_profile()
    if profile != EXPECTED_PROFILE:
        raise RuntimeError(f"probe requires the live-detected AMD Ryzen 5 9600X profile: {why}")
    ok, reason = smu_writes_supported()
    if not ok:
        raise RuntimeError(reason)
    return profile


def send_co(profile, core, margin):
    msg_id, arg0 = curve_optimizer_command(profile, core, margin)
    ok, reason = smu_command_allowed(profile, "mp1", msg_id, arg0)
    if not ok:
        raise RuntimeError(reason)
    with open(ARGS, "wb") as f:
        f.write(struct.pack("<6I", arg0, 0, 0, 0, 0, 0))
    with open(MP1, "wb") as f:
        f.write(struct.pack("<I", msg_id))
    with open(MP1, "rb") as f:
        rsp = struct.unpack("<I", f.read(4))[0]
    time.sleep(SETTLE)
    return rsp


def main():
    profile = require_probe_profile()
    core = int(sys.argv[1]) if len(sys.argv) > 1 else 4  # slot 6 by default: the
    # most interesting case, since it is the first core past the fused gap.
    if not 0 <= core < profile.cores:
        sys.exit(f"core must be 0..{profile.cores - 1}")

    baseline = read_curve_optimizer_offsets(profile)
    print(f"baseline CO offsets: {baseline}")
    print(f"targeting Linux core {core} (SMU slot {profile.slot(core)})")

    target_margin = baseline[core] - 1
    if not -50 <= target_margin <= 20:
        target_margin = baseline[core] + 1
    if not -50 <= target_margin <= 20:
        sys.exit(f"core {core}'s baseline margin ({baseline[core]}) leaves no room "
                 "to probe within -50..20")

    print(f"writing margin {target_margin:+d} to core {core}...")
    rsp = send_co(profile, core, target_margin)
    print(f"RSP={rsp}")
    if rsp != 1:
        sys.exit(f"SMU refused the write (RSP={rsp}); nothing to conclude from it.")

    after = read_curve_optimizer_offsets(profile)
    print(f"after write:  {after}")

    moved = [i for i in range(profile.cores) if after[i] != baseline[i]]
    ok = True
    if moved != [core]:
        print(f"FAIL: expected only core {core} to move, but {moved} changed")
        ok = False
    elif after[core] != target_margin:
        print(f"FAIL: core {core} moved to {after[core]:+d}, not the requested "
              f"{target_margin:+d}")
        ok = False
    else:
        print(f"OK: only core {core} moved, landed exactly on {target_margin:+d}")

    print(f"restoring core {core} to {baseline[core]:+d}...")
    rsp = send_co(profile, core, baseline[core])
    print(f"RSP={rsp}")
    final = read_curve_optimizer_offsets(profile)
    print(f"final: {final}")
    if final != baseline:
        print(f"WARNING: final state {final} does not match baseline {baseline} — "
              "reboot to be sure.")
        ok = False
    else:
        print("restored cleanly.")

    print("\nverdict:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

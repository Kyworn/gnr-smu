#!/usr/bin/env python3
"""Which MP1 message is TDC and which is EDC — by read-back, not by fuzzing.

Result on the 9800X3D (v0x620105), 2026-08-26: **0x3C is TDC, 0x3D is EDC.**

    0x3E <- 151 W   moved d[2]  PPT     method validated on the uncontested control
    0x3D <- 111 A   moved d[63] EDC
    0x3C <- 111 A   moved d[8]  TDC

The repo claimed both answers at once before this ran. tools/gnr_master.py and the GUI
sent 0x3D as TDC and 0x3C as EDC; research/smu_send.py sent the reverse, which is also
what ZenStates-Core says and what PR #1 assumes for the 9950X3D. docs/TOFIX.md called the
question closed "via fuzzing" but named no script and recorded no number, and
BASELINE_SNAPSHOT.md only recorded RSP=0x01 — the SMU accepting a message says nothing
about which limit it moved. The tools have since been corrected to match the read-back.

Kept as a regression check: rerun it after any change to the MP1 command mapping, and on
any new part before enabling SMU writes there.

It is directly observable. Zone 0x000 exposes both limits as floats in amps:
d[8] is the TDC limit and d[63] the EDC limit (PM_TABLE_MAP.md, corrected 2026-07-30).
Write a distinctive value on one message ID and read back which one moved.

Two safety properties make this cheap to run:

  - The probe value is below *both* stock limits, so it is a valid reduction under
    either interpretation. The worst case is a mildly throttled CPU for the duration.
  - SMU limits are volatile. A reboot restores the BIOS values no matter what happens.

Step 0 validates the read-back itself against PPT (0x3E), which nothing disputes. If
d[2] does not follow a PPT write, then d[8]/d[63] would not follow either and the
whole method is void — better to find that out before drawing a conclusion from it.

    sudo python3 research/probe_tdc_edc.py
"""

import struct
import sys
import time

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
VERSION_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_version"
MP1 = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"
ARGS = "/sys/kernel/ryzen_smu_drv/smu_args"

EXPECTED_PM_VERSION = 0x620105

MSG_PPT = 0x3E
STOCK_PPT_W, STOCK_TDC_A, STOCK_EDC_A = 162, 120, 180

# Below stock TDC (120 A) and stock EDC (180 A) both, so it is a reduction whichever
# limit it lands on. Distinctive enough not to be confused with a stock value.
PROBE_A = 111
PROBE_PPT_W = 151

I_PPT, I_TDC, I_EDC = 2, 8, 63

SETTLE = 0.5


def read_limits():
    with open(PM, "rb") as f:
        d = struct.unpack("<457f", f.read(1828))
    return d[I_PPT], d[I_TDC], d[I_EDC]


def send(msg_id, arg0):
    """Returns the SMU response byte. 1 is OK; anything else means the write did not
    take, which is itself an answer worth printing rather than swallowing."""
    with open(ARGS, "wb") as f:
        f.write(struct.pack("<6I", arg0, 0, 0, 0, 0, 0))
    with open(MP1, "wb") as f:
        f.write(struct.pack("<I", msg_id))
    time.sleep(SETTLE)
    with open(MP1, "rb") as f:
        return struct.unpack("<I", f.read(4))[0]


def probe(msg_id, arg0, label, unit, baseline):
    rsp = send(msg_id, arg0)
    after = read_limits()
    moved = [name for name, b, a in zip(("PPT", "TDC", "EDC"), baseline, after)
             if abs(a - b) > 0.5]
    print(f"  0x{msg_id:02X} <- {label}: RSP={rsp} "
          f"PPT {baseline[0]:.1f}->{after[0]:.1f} W  "
          f"TDC {baseline[1]:.1f}->{after[1]:.1f} A  "
          f"EDC {baseline[2]:.1f}->{after[2]:.1f} A")
    if rsp != 1:
        print(f"       SMU refused the write (RSP={rsp}); nothing to conclude from it.")
    elif not moved:
        print("       accepted but no limit moved — either the field is not one of "
              "these three, or firmware clamped the value.")
    else:
        print(f"       moved: {', '.join(moved)}")
    return after, moved


def main():
    try:
        with open(VERSION_PATH, "rb") as f:
            ver = struct.unpack("<I", f.read(4))[0]
    except OSError as e:
        sys.exit(f"cannot read pm_table_version ({e}) — is ryzen_smu loaded?")
    if ver != EXPECTED_PM_VERSION:
        sys.exit(f"PM table {hex(ver)}: d[8]/d[63] are the 9800X3D offsets, and this "
                 f"probe writes SMU limits. Refusing.")

    base = read_limits()
    print(f"baseline: PPT {base[0]:.1f} W  TDC {base[1]:.1f} A  EDC {base[2]:.1f} A")
    if abs(base[1] - STOCK_TDC_A) > 0.5 or abs(base[2] - STOCK_EDC_A) > 0.5:
        print("  note: not at stock — the reset at the end restores stock, not this.")

    print(f"\nstep 0 — does the read-back work at all? PPT is not in dispute.")
    after, moved = probe(MSG_PPT, PROBE_PPT_W * 1000, f"{PROBE_PPT_W} W", "W", base)
    if moved != ["PPT"]:
        send(MSG_PPT, STOCK_PPT_W * 1000)
        sys.exit("d[2] did not follow an uncontested PPT write. The read-back method "
                 "is void here, so d[8]/d[63] would prove nothing either. Stopping.")
    send(MSG_PPT, STOCK_PPT_W * 1000)
    time.sleep(SETTLE)
    base = read_limits()
    print("  read-back confirmed; PPT restored.")

    verdict = {}
    for msg_id in (0x3D, 0x3C):
        print(f"\nstep — 0x{msg_id:02X}")
        after, moved = probe(msg_id, PROBE_A * 1000, f"{PROBE_A} A", "A", base)
        verdict[msg_id] = moved
        # Restore before testing the other ID, so the second result is read against a
        # known baseline rather than against whatever the first one left behind.
        send(0x3D, (STOCK_TDC_A if moved == ["TDC"] else STOCK_EDC_A) * 1000)
        send(0x3C, (STOCK_EDC_A if moved == ["TDC"] else STOCK_TDC_A) * 1000)
        time.sleep(SETTLE)
        base = read_limits()

    print("\n--- restoring stock ---")
    send(MSG_PPT, STOCK_PPT_W * 1000)
    if verdict.get(0x3D) == ["TDC"]:
        send(0x3D, STOCK_TDC_A * 1000)
        send(0x3C, STOCK_EDC_A * 1000)
    elif verdict.get(0x3C) == ["TDC"]:
        send(0x3C, STOCK_TDC_A * 1000)
        send(0x3D, STOCK_EDC_A * 1000)
    else:
        # Unresolved: send the lower stock value on both, which is the safe direction
        # under either mapping.
        send(0x3C, STOCK_TDC_A * 1000)
        send(0x3D, STOCK_TDC_A * 1000)
        print("  mapping unresolved — sent the lower stock value (TDC's) on both IDs. "
              "Reboot to get the BIOS values back.")
    time.sleep(SETTLE)
    final = read_limits()
    print(f"final: PPT {final[0]:.1f} W  TDC {final[1]:.1f} A  EDC {final[2]:.1f} A")

    print("\n--- verdict ---")
    for msg_id, moved in verdict.items():
        name = moved[0] if len(moved) == 1 else (moved or ["nothing"])
        print(f"  0x{msg_id:02X} = {name}")
    print("A reboot restores the BIOS limits regardless of what this printed.")


if __name__ == "__main__":
    main()

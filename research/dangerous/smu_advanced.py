#!/usr/bin/env python3
"""
SMU Tool — AMD Granite Ridge (9800X3D)
Support for MP1 (Power) and RSMU (Tables) mailboxes.
"""

import subprocess
import time
import argparse

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools"))
from hwgate import (get_hardware_profile, msg_id_blocked,
                    smu_writes_supported)  # noqa: E402


def guard(msg_id, mailbox="mp1"):
    """Refuse the send, or return None. Both checks matter here and neither existed
    before: these tools reach the mailbox through raw setpci/SMN, so they bypass the
    ryzen_smu driver's own guardrails as well as the front-ends'. The SMN mailbox
    addresses below are also this-part-specific — on another CPU they are just some
    other register."""
    ok, why = smu_writes_supported()
    if not ok:
        sys.exit(f"REFUSED: {why}")
    blocked, reason = msg_id_blocked(msg_id, mailbox)
    if blocked:
        sys.exit(f"REFUSED: {reason}")



PCI_DEV  = "00:00.0"

def mailbox_addrs(mb_type):
    """(MSG, RSP, ARG0) for one mailbox on the running part.

    Measured on the 9800X3D and carried on its hardware profile. A part whose raw SMN
    addresses were never measured has none, and this refuses rather than writing to
    the same register numbers on silicon where they may mean something else.
    """
    profile, why = get_hardware_profile()
    if profile is None:
        sys.exit(f"REFUSED: {why}")
    addrs = profile.mp1_smn if mb_type == "mp1" else profile.rsmu_smn
    if not addrs:
        sys.exit(f"REFUSED: no measured raw {mb_type.upper()} mailbox address for "
                 f"{profile.name}. This tool writes SMN registers directly.")
    return addrs

def setpci(offset, value=None):
    if value is None:
        return int(subprocess.check_output(["setpci", "-s", PCI_DEV, f"{offset:02X}.L"]).strip(), 16)
    else:
        subprocess.run(["setpci", "-s", PCI_DEV, f"{offset:02X}.L={value:08X}"])

def smn_read(addr):
    setpci(0xB8, addr)
    return setpci(0xBC)

def smn_write(addr, value):
    setpci(0xB8, addr)
    setpci(0xBC, value)

def smu_send(mb_type, msg_id, arg0=0, timeout=1.0):
    # The mailbox has to reach the guard: the never-send list is MP1's, and the
    # pmtable path below rides RSMU 0x04/0x05, which collide with dangerous MP1 IDs.
    guard(msg_id, mb_type)
    # Explicit, because the old `else` meant an unrecognised name silently selected
    # RSMU — the same typo that would have slipped past the guard above.
    if mb_type not in ("mp1", "rsmu"):
        sys.exit(f"REFUSED: unknown mailbox {mb_type!r}")
    m, r, a = mailbox_addrs(mb_type)
    
    smn_write(r, 0)
    smn_write(a, arg0)
    smn_write(m, msg_id)
    
    deadline = time.time() + timeout
    while time.time() < deadline:
        rsp = smn_read(r)
        if rsp != 0:
            return rsp, smn_read(a), smn_read(a + 4)
        time.sleep(0.001)
    return 0, 0, 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["test", "pmtable", "ppt", "raw"])
    parser.add_argument("--mb", choices=["mp1", "rsmu"], default="mp1")
    parser.add_argument("--msg", type=lambda x: int(x, 0))
    parser.add_argument("--arg", type=lambda x: int(x, 0), default=0)
    parser.add_argument("--val", type=float)
    args = parser.parse_args()

    if args.cmd == "test":
        rsp, r0, r1 = smu_send(args.mb, 0x01)
        print(f"Test on {args.mb}: RSP=0x{rsp:02X} R0=0x{r0:08X}")

    elif args.cmd == "ppt":
        mw = int(args.val * 1000)
        rsp, r0, r1 = smu_send("mp1", 0x3E, mw)
        print(f"PPT {args.val}W: RSP=0x{rsp:02X}")

    elif args.cmd == "pmtable":
        # 1. Get Base Address from RSMU MSG 0x04
        print("Requesting PM Table address...")
        rsp, r0, r1 = smu_send("rsmu", 0x04, 1) # Arg=1 for Table 1?
        if rsp != 1:
            print(f"Failed to get address (RSP=0x{rsp:02X})")
            return
        base_addr = r0 | (r1 << 32)
        print(f"DRAM Base Address: 0x{base_addr:016X}")

        # 2. Trigger Transfer from RSMU MSG 0x05
        print("Triggering transfer...")
        rsp, r0, r1 = smu_send("rsmu", 0x05, 0)
        if rsp != 1:
            print(f"Transfer failed (RSP=0x{rsp:02X})")
            return
        version = r0
        print(f"Table Version: 0x{version:08X}")

        # 3. Read from /dev/mem (requires sudo)
        # On va juste afficher les premiers octets pour valider
        print(f"Reading 64 bytes from 0x{base_addr:016X}...")
        try:
            with open("/dev/mem", "rb") as f:
                f.seek(base_addr)
                data = f.read(64)
                print(data.hex(" "))
        except Exception as e:
            print(f"Error reading /dev/mem: {e} (Are you sudo? Is CONFIG_STRICT_DEVMEM enabled?)")

    elif args.cmd == "raw":
        rsp, r0, r1 = smu_send(args.mb, args.msg, args.arg)
        print(f"RAW: RSP=0x{rsp:02X} R0=0x{r0:08X} R1=0x{r1:08X}")

if __name__ == "__main__":
    main()

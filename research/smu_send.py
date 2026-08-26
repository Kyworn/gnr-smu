#!/usr/bin/env python3
"""
SMU MP1 mailbox tool — AMD Granite Ridge (Ryzen 9000 desktop / 9800X3D)
"""

import subprocess
import time
import argparse

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools"))
from hwgate import hardware_supported, msg_id_blocked  # noqa: E402


def guard(msg_id):
    """Refuse the send, or return None. Both checks matter here and neither existed
    before: these tools reach the mailbox through raw setpci/SMN, so they bypass the
    ryzen_smu driver's own guardrails as well as the front-ends'. The SMN mailbox
    addresses below are also this-part-specific — on another CPU they are just some
    other register."""
    ok, why = hardware_supported()
    if not ok:
        sys.exit(f"REFUSED: {why}")
    blocked, reason = msg_id_blocked(msg_id)
    if blocked:
        sys.exit(f"REFUSED: {reason}")



PCI_DEV  = "00:00.0"
MSG_ADDR = 0x3B10530
RSP_ADDR = 0x3B1057C
ARG0_ADDR = 0x3B109C4
ARG1_ADDR = 0x3B109C8

# Stock 9800X3D, read back from the PM table limits d[2]/d[8]/d[63]. These were 160 A
# and 220 A, which are PBO figures, not stock — "reset" raised TDC and EDC instead of
# restoring them. Same class of bug as the one tools/gnr_master.py had.
DEFAULT_PPT_W = 162
DEFAULT_TDC_A = 120
DEFAULT_EDC_A = 180

# 0x3C is TDC and 0x3D is EDC, confirmed by read-back in research/probe_tdc_edc.py.
# This file already had them this way round while the GUI and CLI had them reversed;
# the measurement is what settles it, not the majority.
MSG_PPT, MSG_TDC, MSG_EDC = 0x3E, 0x3C, 0x3D


def setpci(offset: int, value: int | None = None) -> int | None:
    if value is None:
        r = subprocess.run(
            ["setpci", "-s", PCI_DEV, f"{offset:02X}.L"],
            capture_output=True, text=True, check=True)
        return int(r.stdout.strip(), 16)
    else:
        subprocess.run(
            ["setpci", "-s", PCI_DEV, f"{offset:02X}.L={value:08X}"],
            capture_output=True, text=True, check=True)


def smn_read(addr: int) -> int:
    setpci(0xB8, addr)
    return setpci(0xBC)


def smn_write(addr: int, value: int):
    setpci(0xB8, addr)
    setpci(0xBC, value)


def smu_send(msg_id: int, arg0: int = 0, timeout: float = 1.0) -> tuple[int, int, int]:
    guard(msg_id)
    smn_write(RSP_ADDR, 0)
    smn_write(ARG0_ADDR, arg0)
    smn_write(MSG_ADDR, msg_id)
    deadline = time.time() + timeout
    rsp = 0
    while time.time() < deadline:
        rsp = smn_read(RSP_ADDR)
        if rsp != 0:
            break
        time.sleep(0.001)
    return rsp, smn_read(ARG0_ADDR), smn_read(ARG1_ADDR)


def main():
    parser = argparse.ArgumentParser(description="SMU MP1 tool")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("test", help="0x01")
    sub.add_parser("version", help="0x02")
    sub.add_parser("reset")

    p = sub.add_parser("ppt")
    p.add_argument("watts", type=float)

    p = sub.add_parser("tdc")
    p.add_argument("amps", type=float)

    p = sub.add_parser("edc")
    p.add_argument("amps", type=float)

    p = sub.add_parser("send")
    p.add_argument("msg_id", type=lambda x: int(x, 0))
    p.add_argument("arg0",   type=lambda x: int(x, 0), nargs="?", default=0)

    args = parser.parse_args()

    if args.cmd == "test":
        rsp, r0, r1 = smu_send(0x01)
        print(f"RSP=0x{rsp:02X} R0=0x{r0:08X}")

    elif args.cmd == "version":
        rsp, r0, r1 = smu_send(0x02)
        print(f"Version: 0x{r0:08X}")

    elif args.cmd == "send":
        rsp, r0, r1 = smu_send(args.msg_id, args.arg0)
        print(f"MSG=0x{args.msg_id:02X} ARG0=0x{args.arg0:08X} → RSP=0x{rsp:02X} R0=0x{r0:08X} R1=0x{r1:08X}")

    elif args.cmd == "reset":
        smu_send(MSG_PPT, DEFAULT_PPT_W * 1000)
        smu_send(MSG_TDC, DEFAULT_TDC_A * 1000)
        smu_send(MSG_EDC, DEFAULT_EDC_A * 1000)
        print("Reset OK")

    elif args.cmd == "ppt":
        rsp, r0, r1 = smu_send(MSG_PPT, int(args.watts * 1000))
        print(f"PPT {args.watts}W: RSP=0x{rsp:02X}")

    elif args.cmd == "tdc":
        rsp, r0, r1 = smu_send(MSG_TDC, int(args.amps * 1000))
        print(f"TDC {args.amps}A: RSP=0x{rsp:02X}")

    elif args.cmd == "edc":
        rsp, r0, r1 = smu_send(MSG_EDC, int(args.amps * 1000))
        print(f"EDC {args.amps}A: RSP=0x{rsp:02X}")

if __name__ == "__main__":
    main()

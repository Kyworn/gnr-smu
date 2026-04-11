#!/usr/bin/env python3
"""
SMU MP1 mailbox tool — AMD Granite Ridge (Ryzen 9000 desktop / 9800X3D)
"""

import subprocess
import time
import sys
import argparse

PCI_DEV  = "00:00.0"
MSG_ADDR = 0x3B10530
RSP_ADDR = 0x3B1057C
ARG0_ADDR = 0x3B109C4
ARG1_ADDR = 0x3B109C8

# Valeurs par défaut estimées pour le 9800X3D
DEFAULT_PPT_W = 162
DEFAULT_TDC_A = 160
DEFAULT_EDC_A = 220


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

    p = sub.add_parser("tjmax")
    p.add_argument("temp", type=float)

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
        smu_send(0x3E, DEFAULT_PPT_W * 1000)
        smu_send(0x3C, DEFAULT_TDC_A * 1000)
        smu_send(0x3D, DEFAULT_EDC_A * 1000)
        print("Reset OK")

    elif args.cmd == "ppt":
        rsp, r0, r1 = smu_send(0x3E, int(args.watts * 1000))
        print(f"PPT {args.watts}W: RSP=0x{rsp:02X}")

if __name__ == "__main__":
    main()

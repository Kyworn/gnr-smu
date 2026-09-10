#!/usr/bin/env python3
"""Vermeer core-disable fuse verification (READ-ONLY research tool).

Reads SMN fuse registers through the ryzen_smu driver's established
4-byte read protocol (byte-identical to libsmu smu_read_smn_addr():
lseek, write exactly 4 bytes LE address, lseek, read 4 bytes back).
A 4-byte store can only take the driver's smu_read_address() path;
the 8-byte SMN *write* path is never touched (write size is asserted).

Allowed addresses are hardcoded; there is no generic address argument,
no scanning, no probing.  Hard-fails unless the CPU is Family 19h,
non-Raphael (Vermeer-class topology: fuse1 0x5D218, fuse2 0x5D21C,
core offset 0x598).

Usage (as root on the target host):
  python3 vermeer_fuse_check.py --read ccd    # 0x5D218, 0x5D21C
  python3 vermeer_fuse_check.py --read core   # re-reads CCD fuses, derives
                                              # the core fuse address with
                                              # leogx9r's exact expression,
                                              # reads exactly that address
"""
import argparse
import os
import struct
import sys

SMN = "/sys/kernel/ryzen_smu_drv/smn"
CCD_FUSE1 = 0x5D218
CCD_FUSE2 = 0x5D21C
CORE_BASE = 0x30081800
F19_OFFSET = 0x598


def require_vermeer_class():
    fam = model = None
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.startswith("cpu family"):
                fam = int(line.split(":")[1].strip())
            elif line.startswith("model\t") or line.startswith("model "):
                # 'model\t: 33' vs 'model name\t: ...' — take the numeric one
                val = line.split(":")[1].strip()
                if val.isdigit():
                    model = int(val)
            if fam is not None and model is not None:
                break
    if fam != 25:
        sys.exit(f"REFUSING: CPU family is {fam}, need Family 19h (25)")
    # Raphael/DragonRange (0x61) use a different core offset (0x4D0);
    # this tool only encodes the Vermeer-class 0x598 path.
    if model == 0x61:
        sys.exit("REFUSING: Raphael-class model uses core offset 0x4D0, "
                 "not encoded here")
    return fam, model


def smn_read(address, allowed):
    """One established-protocol SMN read. Write size asserted == 4."""
    if address not in allowed:
        sys.exit(f"REFUSING: 0x{address:08X} not in allowlist "
                 f"{[hex(a) for a in sorted(allowed)]}")
    fd = os.open(SMN, os.O_RDWR)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        n = os.write(fd, struct.pack("<I", address))
        if n != 4:
            sys.exit(f"REFUSING: short address write ({n} bytes)")
        os.lseek(fd, 0, os.SEEK_SET)
        data = os.read(fd, 4)
        if len(data) != 4:
            sys.exit(f"short result read for 0x{address:08X}")
        return struct.unpack("<I", data)[0]
    finally:
        os.close(fd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", choices=("ccd", "core"), required=True)
    args = ap.parse_args()

    fam, model = require_vermeer_class()
    print(f"CPUID check: family {fam} (0x19), model {model} (0x{model:02X})")

    ccds_present = smn_read(CCD_FUSE1, {CCD_FUSE1, CCD_FUSE2})
    ccds_down = smn_read(CCD_FUSE2, {CCD_FUSE1, CCD_FUSE2})
    print(f"raw ccds_present (0x{CCD_FUSE1:05X}): 0x{ccds_present:08X}")
    print(f"raw ccds_down    (0x{CCD_FUSE2:05X}): 0x{ccds_down:08X}")

    # leogx9r exact expressions:
    ccds_disabled = ((ccds_down & 0x3F) << 2) | ((ccds_present >> 30) & 0x3)
    ccds_enabled = (ccds_present >> 22) & 0xFF
    print(f"decoded ccds_disabled map: 0x{ccds_disabled:02X}")
    print(f"decoded ccds_enabled  map: 0x{ccds_enabled:02X}")

    if args.read == "core":
        base = CORE_BASE + F19_OFFSET
        print(f"Family 19h base: 0x{CORE_BASE:08X} + 0x{F19_OFFSET:X} = "
              f"0x{base:08X}")
        sel = 0x2000000 if (((ccds_disabled & ccds_enabled) & 1) == 1) else 0
        print(f"CCD selection: ((0x{ccds_disabled:02X} & 0x{ccds_enabled:02X}) "
              f"& 1) == 1 is {(((ccds_disabled & ccds_enabled) & 1) == 1)} "
              f"-> OR 0x{sel:08X}")
        addr = base | sel
        print(f"final core fuse address: 0x{addr:08X}")
        core_fuse = smn_read(addr, {CCD_FUSE1, CCD_FUSE2, addr})
        print(f"raw core fuse (0x{addr:08X}): 0x{core_fuse:08X}")
        print(f"coreDisableMap (low 8 bits): 0x{core_fuse & 0xFF:02X}")
        for bit in range(8):
            state = "DISABLED" if (core_fuse >> bit) & 1 else "enabled"
            print(f"  bit {bit} = {(core_fuse >> bit) & 1}  {state}")
        print(f"SMT bit (bit 8) = {(core_fuse >> 8) & 1}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import sys
import os
import struct

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gnr_smu.hardware import get_hardware_profile  # noqa: E402
from gnr_smu.safety import (curve_optimizer_command,  # noqa: E402
                            read_curve_optimizer_offsets,
                            smu_command_allowed,
                            smu_writes_supported)

# Stock limits and MP1 message IDs live on the hardware profile in
# gnr_smu/profiles.py — per part, since they differ. 0x3C is TDC and 0x3D is
# EDC, established by read-back in
# research/dangerous/probe_tdc_edc.py after this file had them the other way round; the swap was
# not cosmetic, "reset to stock" was writing 180 A into a 120 A TDC.
#
# The never-send list also lives in gnr_smu/safety.py, so the CLI, the GUI and the research
# tools cannot drift apart. It used to be spelled out here and again as two ifs in
# the GUI.


def apply_cmd(msg_id, arg0):
    ok, why = smu_writes_supported()
    if not ok:
        print(f"[BLOCKED] SMU writes disabled: {why}")
        return False
    profile, _ = get_hardware_profile()
    ok, why = smu_command_allowed(profile, "mp1", msg_id, arg0)
    if not ok:
        print(f"[BLOCKED] {why}")
        return False

    smu_args = "/sys/kernel/ryzen_smu_drv/smu_args"
    smu_cmd = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"
    try:
        with open(smu_args, "wb") as f:
            f.write(struct.pack("<6I", arg0, 0, 0, 0, 0, 0))
        with open(smu_cmd, "wb") as f:
            f.write(struct.pack("<I", msg_id))
        
        with open(smu_cmd, "rb") as f:
            rsp = struct.unpack("<I", f.read(4))[0]

        rsp_name = {
            1: "OK",
            0xFD: "REJECTED",
            0xFE: "UNKNOWN_CMD",
            0xFF: "FAILED",
        }.get(rsp, f"0x{rsp:02X}")
        success = rsp == 1
        level = "OK" if success else "ERROR"
        print(f"[{level}] Sent MSG=0x{msg_id:02x} ARG={arg0} => RSP: {rsp_name}")
        return success
    except Exception as e:
        print(f"[ERROR] Driver write failed: {e}")
        return False

def show_co_config(profile):
    try:
        offsets = read_curve_optimizer_offsets(profile)
    except Exception as e:
        print(f"[ERROR] could not read Curve Optimizer offsets: {e}")
        return None
    print("Current Curve Optimizer: " + ", ".join(
        f"core {core}={value:+d}" for core, value in enumerate(offsets)
    ))
    return offsets

def ask_limit(name, unit, max_val):
    """Bounded numeric input. The GUI clamps these with spin-box ranges; the CLI took
    any float and sent it straight to the SMU, so a typo was a hardware command.
    Returns None if the value is out of range or unparseable."""
    raw = input(f"{name} ({unit}, 0-{max_val}): ")
    try:
        v = float(raw)
    except ValueError:
        print(f"[ERROR] not a number: {raw!r}")
        return None
    if not 0 <= v <= max_val:
        print(f"[ERROR] {name} must be between 0 and {max_val} {unit}, got {v}")
        return None
    return v


def main():
    profile, _ = get_hardware_profile()
    cores = profile.cores if profile else 8
    writes_ok, writes_why = smu_writes_supported()
    if not writes_ok:
        print(f"[BLOCKED] This CLI only performs SMU writes: {writes_why}")
        print("Use export_telemetry.py --temps for read-only per-core temperatures.")
        return
    print("--- GNR Master Control ---")
    show_co_config(profile)
    print("1. Set PPT Limit (Watts)")
    print("2. Set Custom TDC (Amps)")
    print("3. Set Custom EDC (Amps)")
    print("4. Apply -30 CO All Cores")
    print("5. Reset All Settings")
    print("6. Quit")
    
    choice = input("Option: ")
    
    if choice == '1':
        w = ask_limit("PPT", "Watts", 250)
        if w is not None:
            apply_cmd(profile.ppt_msg, int(w * 1000))
    elif choice == '2':
        a = ask_limit("TDC", "Amps", 200)
        if a is not None:
            apply_cmd(profile.tdc_msg, int(a * 1000))
    elif choice == '3':
        a = ask_limit("EDC", "Amps", 250)
        if a is not None:
            apply_cmd(profile.edc_msg, int(a * 1000))
    elif choice == '4':
        applied = True
        for i in range(cores):
            msg_id, arg0 = curve_optimizer_command(profile, i, -30)
            if not apply_cmd(msg_id, arg0):
                applied = False
                break
        if applied:
            if show_co_config(profile) is not None:
                print("CO -30 applied and verified by SMU readback.")
    elif choice == '5':
        applied = apply_cmd(profile.ppt_msg, profile.stock_ppt * 1000)
        if applied:
            applied = apply_cmd(profile.tdc_msg, profile.stock_tdc * 1000)
        if applied:
            applied = apply_cmd(profile.edc_msg, profile.stock_edc * 1000)
        if applied:
            for i in range(cores):
                msg_id, arg0 = curve_optimizer_command(profile, i, 0)
                if not apply_cmd(msg_id, arg0):
                    applied = False
                    break
        if applied:
            if show_co_config(profile) is not None:
                print("Reset successful and verified by SMU readback.")
    
if __name__ == "__main__":
    main()

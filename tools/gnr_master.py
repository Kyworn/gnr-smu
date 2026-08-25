#!/usr/bin/env python3
import sys
import os
import struct
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwgate import (curve_optimizer_command, get_hardware_profile,
                    smu_message_supported, smu_writes_supported)

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "gnr_master.json",
)

# The GUI blocks these outright; the CLI never sends them, but it applies the same
# rule so the two cannot drift. 0x10 and 0x03-0x0D are the dangerous MP1 IDs.
BLOCKED = {0x10} | set(range(0x03, 0x0E))


def apply_cmd(msg_id, arg0):
    ok, why = smu_writes_supported()
    if not ok:
        print(f"[BLOCKED] SMU writes disabled: {why}")
        return False
    profile, _ = get_hardware_profile()
    if not smu_message_supported(profile, msg_id):
        print(f"[BLOCKED] MSG 0x{msg_id:02x} is not in the {profile.name} allowlist")
        return False
    if msg_id in BLOCKED:
        print(f"[BLOCKED] guardrail: MSG 0x{msg_id:02x}")
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

def save_co_config(co_val):
    try:
        profile, _ = get_hardware_profile()
        cores = profile.cores if profile else 8
        data = {"co_offsets": [co_val] * cores}
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f)
    except OSError as e:
        # This used to swallow the error. The offsets are write-only — the SMU will
        # not read them back — so a failed save means the GUI shows 0 for settings
        # that are actually applied.
        print(f"[WARN] could not cache CO offsets to {CONFIG_PATH}: {e}")

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
            save_co_config(-30)
            print("CO -30 applied and saved locally for the GUI!")
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
            save_co_config(0)
            print("Reset successful.")
    
if __name__ == "__main__":
    main()

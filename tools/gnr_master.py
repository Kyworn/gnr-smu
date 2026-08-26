#!/usr/bin/env python3
import sys
import os
import struct
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwgate import hardware_supported, msg_id_blocked

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "gnr_master.json",
)

# Stock 9800X3D, read back from the PM table limits d[2]/d[8]/d[63] and matching AMD
# spec. The reset option used to send 85 A TDC and 120 A EDC, which is not stock: it
# clamped both below what the part ships with, so "reset" quietly throttled the CPU.
STOCK_PPT_W, STOCK_TDC_A, STOCK_EDC_A = 162, 120, 180
CORES = 8

# MP1 message IDs. Corrected 2026-08-26: this file had 0x3D as TDC and 0x3C as EDC,
# on the strength of a "validated via fuzzing" note in docs/TOFIX.md that named no
# script and recorded no number. research/probe_tdc_edc.py settles it by read-back —
# write a distinctive value, see which limit in the PM table moves:
#
#   0x3E <- 151 W   moved PPT (d[2])     read-back method validated first
#   0x3D <- 111 A   moved EDC (d[63])
#   0x3C <- 111 A   moved TDC (d[8])
#
# So 0x3C is TDC and 0x3D is EDC, matching ZenStates-Core, not the note. The swap was
# not merely cosmetic: "reset to stock" sent STOCK_EDC_A on 0x3C, which set TDC to
# 180 A against a 120 A stock limit, and the EDC menu accepted up to 250 A of TDC.
MSG_PPT, MSG_TDC, MSG_EDC = 0x3E, 0x3C, 0x3D

# The never-send list lives in hwgate.py so the CLI, the GUI and the research tools
# cannot drift apart. It used to be spelled out here and again as two ifs in the GUI.


def apply_cmd(msg_id, arg0):
    ok, why = hardware_supported()
    if not ok:
        print(f"[BLOCKED] SMU writes disabled: {why}")
        return False
    blocked, reason = msg_id_blocked(msg_id)
    if blocked:
        print(f"[BLOCKED] guardrail: {reason}")
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
            
        print(f"[OK] Sent MSG=0x{msg_id:02x} ARG={arg0} => RSP: {'OK' if rsp == 1 else rsp}")
        return True
    except Exception as e:
        print(f"[ERROR] Driver write failed: {e}")
        return False

def save_co_config(co_val):
    try:
        data = {"co_offsets": [co_val] * CORES}
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
            apply_cmd(0x3E, int(w * 1000))
    elif choice == '2':
        a = ask_limit("TDC", "Amps", 200)
        if a is not None:
            apply_cmd(MSG_TDC, int(a * 1000))
    elif choice == '3':
        a = ask_limit("EDC", "Amps", 250)
        if a is not None:
            apply_cmd(MSG_EDC, int(a * 1000))
    elif choice == '4':
        val = 0xFFFFFFE2 # -30 as 32-bit unsigned
        for i in range(CORES):
            apply_cmd(0x50 + i, val)
        save_co_config(-30)
        print("CO -30 saved locally for the GUI!")
    elif choice == '5':
        # Reset to stock
        apply_cmd(MSG_PPT, STOCK_PPT_W * 1000)
        apply_cmd(MSG_TDC, STOCK_TDC_A * 1000)
        apply_cmd(MSG_EDC, STOCK_EDC_A * 1000)
        save_co_config(0)
        for i in range(CORES): apply_cmd(0x50 + i, 0)
        print("Reset successful.")
    
if __name__ == "__main__":
    main()

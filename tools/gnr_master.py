#!/usr/bin/env python3
import sys
import os
import struct
import json

CONFIG_PATH = "/home/zorko/.config/gnr_master.json"

def apply_cmd(msg_id, arg0):
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
        data = {"co_offsets": [co_val] * 8}
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

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
        w = float(input("PPT (Watts): "))
        apply_cmd(0x3E, int(w * 1000))
    elif choice == '2':
        a = float(input("TDC (Amps): "))
        # 0x3D is the real TDC limit on Granite Ridge
        apply_cmd(0x3D, int(a * 1000))
    elif choice == '3':
        a = float(input("EDC (Amps): "))
        # 0x3C is the real EDC limit on Granite Ridge
        apply_cmd(0x3C, int(a * 1000))
    elif choice == '4':
        val = 0xFFFFFFE2 # -30 as 32-bit unsigned
        for i in range(8):
            apply_cmd(0x50 + i, val)
        save_co_config(-30)
        print("CO -30 saved locally for the GUI!")
    elif choice == '5':
        # Reset defaults (162W PPT, 85A TDC, 120A EDC)
        apply_cmd(0x3E, 162000)
        apply_cmd(0x3D, 85000)
        apply_cmd(0x3C, 120000)
        save_co_config(0)
        for i in range(8): apply_cmd(0x50 + i, 0)
        print("Reset successful.")
    
if __name__ == "__main__":
    main()

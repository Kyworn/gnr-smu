#!/usr/bin/env python3
import struct

def parse_pm_table(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        
        print(f"Parsing PM Table ({len(data)} bytes)...")
        # On parse par blocs de 4 octets (float32)
        count = len(data) // 4
        floats = struct.unpack(f"<{count}f", data[:count*4])
        
        for i, val in enumerate(floats):
            # On n'affiche que les valeurs qui "ressemblent" à de la télémétrie
            # (températures entre 20 et 100, tensions entre 0 et 2, puissance > 0)
            if 0.1 < val < 5000.0:
                print(f"Offset 0x{i*4:03X} [{i}]: {val:.4f}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parse_pm_table("/sys/kernel/ryzen_smu_drv/pm_table")

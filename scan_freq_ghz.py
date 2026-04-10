#!/usr/bin/env python3
import struct
import time
import subprocess

def scan_freq_ghz():
    print("Launching stress test...")
    stress = subprocess.Popen(["7z", "b"], stdout=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
            data = f.read()
        
        count = len(data) // 4
        floats = struct.unpack(f"<{count}f", data[:count*4])
        
        print("Searching for values between 4.0 and 6.0 (GHz)...")
        for i, val in enumerate(floats):
            if 4.0 < val < 6.0:
                print(f"Offset 0x{i*4:03X}: {val:.4f}")
                
    finally:
        stress.kill()

if __name__ == "__main__":
    scan_freq_ghz()

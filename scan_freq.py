#!/usr/bin/env python3
import struct
import time
import subprocess

def scan_freq():
    print("Launching stress test...")
    stress = subprocess.Popen(["7z", "b"], stdout=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
            data = f.read()
        
        count = len(data) // 4
        floats = struct.unpack(f"<{count}f", data[:count*4])
        
        print("Searching for values between 5000 and 5500 (MHz)...")
        for i, val in enumerate(floats):
            if 5000.0 < val < 5500.0:
                print(f"Offset 0x{i*4:03X}: {val:.2f} MHz")
                
    finally:
        stress.kill()

if __name__ == "__main__":
    scan_freq()

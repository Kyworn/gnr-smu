import struct
import time
import subprocess
import sys

def read_package_power():
    try:
        with open("/dev/gnr_smu", "rb") as f:
            data = f.read(0x724)
            if len(data) < 0x54: return None
            val = struct.unpack("<f", data[0x50:0x54])[0]
            return val
    except Exception as e:
        return None

def trigger_transfer():
    try:
        with open("/dev/gnr_smu", "wb") as f:
            f.write(b"05 0")
    except Exception as e:
        pass

print("Starting live monitor (Ctrl+C to stop)...")
last_power = -1.0

try:
    while True:
        trigger_transfer()
        time.sleep(0.05)
        power = read_package_power()
        
        if power is not None and abs(power - last_power) > 0.1:
            print(f"[{time.strftime('%H:%M:%S')}] Power: {power:.2f} W")
            last_power = power
        
        time.sleep(0.4)
except KeyboardInterrupt:
    print("\nStopped.")

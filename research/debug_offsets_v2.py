import struct
import subprocess
import time

p = subprocess.Popen(["7z", "b"], stdout=subprocess.DEVNULL)
time.sleep(1)

with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    raw = f.read(4096)
    data = struct.unpack("<1024f", raw)
    print("--- DUMP OFFSETS (Valeurs 3000-5500) ---")
    for i, val in enumerate(data):
        if 3000.0 < val < 5500.0:
            print(f"Index {i} (Offset 0x{i*4:03X}): {val:.2f}")

p.kill()

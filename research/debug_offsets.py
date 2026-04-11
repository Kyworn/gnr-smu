import struct
import time
import subprocess

# Lancer une charge en arrière-plan
p = subprocess.Popen(["7z", "b"], stdout=subprocess.DEVNULL)
time.sleep(1)

with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    # On lit le dump complet
    data = struct.unpack("<466f", f.read(1864))
    print("--- SCAN OFFSET (Recherche des fréquences MHz) ---")
    for i, val in enumerate(data):
        # Chercher des valeurs typiques de fréquence CPU (3000-5500 MHz)
        if 3000.0 < val < 5500.0:
            print(f"Index {i} (Offset 0x{i*4:03X}): {val:.2f}")

p.kill()

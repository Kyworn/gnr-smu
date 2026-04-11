import struct
import time
import subprocess
import os

# Adresses fraîchement cartographiées
OFFSETS = {
    0x050: ("Package Power", "W"),
    0x100: ("SoC/iGPU Temp", "°C"),
    0x14C: ("VSOC Voltage", "V"),
    0x1B0: ("iGPU Clock", "MHz"),
    0x2E8: ("GFX Junction Temp", "°C"),
    0x560: ("iGPU Metric A", "Unk"),
    0x568: ("iGPU Metric B", "Unk"),
}

def get_vals():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    floats = struct.unpack(f"<{len(data)//4}f", data)
    res = {}
    for off in OFFSETS.keys():
        res[off] = floats[off // 4]
    return res

print("1. Lecture de la ligne de base (IDLE) - Attend 3s...")
time.sleep(3)
idle = get_vals()

print("2. Lancement du Stress Test *Exclusivement CPU/RAM* (stress-ng)")
print("   (L'iGPU n'est PAS sollicité, ses valeurs doivent rester froides/plates !)")
p = subprocess.Popen(["stress-ng", "--vecmath", "16", "--timeout", "7"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(5) # Attend le pic du stress
load_cpu = get_vals()
p.wait()

print("\n================ VÉRIFICATION AUTOMATIQUE ================")
cpu_power_spike = load_cpu[0x050] - idle[0x050]
print(f"-> Package Power (CPU) a pris {cpu_power_spike:+.2f} W (Doit être énorme)")

igpu_clock_spike = load_cpu[0x1B0] - idle[0x1B0]
print(f"-> iGPU Clock a pris {igpu_clock_spike:+.2f} MHz (Doit être proche de 0)")

igpu_a_spike = load_cpu[0x560] - idle[0x560]
igpu_b_spike = load_cpu[0x568] - idle[0x568]
print(f"-> iGPU Metric A a pris {igpu_a_spike:+.2f} (Doit être proche de 0)")
print(f"-> iGPU Metric B a pris {igpu_b_spike:+.2f} (Doit être proche de 0)")

temp_soc = load_cpu[0x100] - idle[0x100]
print(f"-> SoC Temp a pris {temp_soc:+.2f} °C (Va monter un peu car le CPU chauffe la puce entière)")
temp_gfx = load_cpu[0x2E8] - idle[0x2E8]
print(f"-> GFX Junction a pris {temp_gfx:+.2f} °C (Va monter un peu par inertie thermique)")

print("\n=== RÉSULTAT DU TEST ===")
if cpu_power_spike > 20 and abs(igpu_clock_spike) < 50 and abs(igpu_a_spike) < 3:
    print("[SUCCESS] Isolations parfaites confirmées ! Les offsets GFX/iGPU n'ont pas réagi au test CPU massif.")
else:
    print("[WARNING] Croisement détecté ! Les valeurs de l'iGPU ont explosé sans raison graphique, l'offset est peut-être mixte.")

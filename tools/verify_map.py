import struct
import time
import subprocess
import os

# Labels corrected 2026-07-30 — see PM_TABLE_MAP.md "Re-verification 2026-07-30".
# 0x100 is NOT Tctl (real Tctl is 0x02C) and 0x2E8 is iGPU activity %, not a temp.
OFFSETS = {
    0x00C: ("PPT Value / Package Power", "W"),
    0x02C: ("Tctl (direct °C)", "°C"),
    0x050: ("CPU Domain Power", "W"),
    0x0F8: ("SoC Power Limit", "W"),
    0x100: ("Unidentified utilization metric", "?"),
    0x14C: ("VSOC Voltage", "V"),
    0x1AC: ("iGPU Power", "W"),
    0x1B0: ("iGPU Clock", "MHz"),
    0x1B4: ("iGPU Activity", "%"),
    0x2E8: ("iGPU Activity", "%"),
    0x438: ("Hotspot Temp (direct °C)", "°C"),
    0x560: ("Core FIT / IDD Max", "%"),
    0x568: ("Core FIT / IDD Max", "%"),
}


def get_vals():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    floats = struct.unpack(f"<{len(data) // 4}f", data)
    res = {}
    for off in OFFSETS.keys():
        res[off] = floats[off // 4]
    return res


print("1. Lecture de la ligne de base (IDLE) - Attend 3s...")
time.sleep(3)
idle = get_vals()

print("2. Lancement du Stress Test *Exclusivement CPU/RAM* (stress-ng)")
print("   (L'iGPU n'est PAS sollicité, ses valeurs doivent rester froides/plates !)")
p = subprocess.Popen(
    ["stress-ng", "--vecmath", "16", "--timeout", "7"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

time.sleep(5)  # Attend le pic du stress
load_cpu = get_vals()
p.wait()

print("\n================ VÉRIFICATION AUTOMATIQUE ================")
cpu_power_spike = load_cpu[0x050] - idle[0x050]
ppt_spike = load_cpu[0x00C] - idle[0x00C]
print(f"-> CPU Domain Power a pris {cpu_power_spike:+.2f} W (Doit être énorme)")
print(f"-> PPT Value (0x00C) a pris {ppt_spike:+.2f} W (Doit suivre, ~+17 W au-dessus)")

tctl_spike = load_cpu[0x02C] - idle[0x02C]
hotspot_spike = load_cpu[0x438] - idle[0x438]
print(f"-> Tctl (0x02C) a pris {tctl_spike:+.2f} °C (Doit monter fort)")
print(
    f"-> Hotspot (0x438) a pris {hotspot_spike:+.2f} °C "
    "(lecture unique, très bruitée : peut sortir négatif — moyenner pour comparer)"
)

# Ces trois offsets sont le vrai bloc iGPU. Sur une charge CPU pure ils doivent
# rester plats. Les anciens "iGPU Metric A/B" (0x560/0x568) étaient en réalité
# du FIT par cœur : ils saturent à 100 % sous charge CPU, donc le test échouait
# toujours. Corrigé le 2026-07-30.
igpu_clock_spike = load_cpu[0x1B0] - idle[0x1B0]
igpu_pwr_spike = load_cpu[0x1AC] - idle[0x1AC]
igpu_act_spike = load_cpu[0x1B4] - idle[0x1B4]
print(f"-> iGPU Clock (0x1B0) a pris {igpu_clock_spike:+.2f} MHz (Doit être ~0)")
print(f"-> iGPU Power (0x1AC) a pris {igpu_pwr_spike:+.2f} W (Doit être ~0)")
print(f"-> iGPU Activity (0x1B4) a pris {igpu_act_spike:+.2f} % (Doit être ~0)")

fit_spike = load_cpu[0x560] - idle[0x560]
print(f"-> Core FIT (0x560) a pris {fit_spike:+.2f} % (Doit saturer vers 100)")

print("\n=== RÉSULTAT DU TEST ===")
ok_cpu = cpu_power_spike > 20 and tctl_spike > 5
ok_igpu = abs(igpu_clock_spike) < 50 and abs(igpu_pwr_spike) < 2
if ok_cpu and ok_igpu:
    print("[SUCCESS] Le CPU réagit, l'iGPU reste plat : les domaines sont bien isolés.")
elif not ok_cpu:
    print("[WARNING] Le CPU n'a pas réagi — stress-ng a-t-il vraiment tourné ?")
else:
    print("[WARNING] Les offsets iGPU ont bougé sous une charge CPU pure — domaine mixte ?")

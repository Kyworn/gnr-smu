import struct
import time
import math
import subprocess

KNOWN = {2, 3, 8, 10, 18, 19, 20}
for i in range(8):
    KNOWN.update([309+i, 317+i, 325+i, 373+i])

def get_floats():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    return list(struct.unpack(f"<{len(data)//4}f", data))

print("=== CHASSEUR DE PUISSANCE iGPU 2.0 (100% Automatique) ===")

print("1. Capture de la ligne de base (repos)...")
time.sleep(2)

print("2. Lancement magique du stress test iGPU (glxgears) ! NE TOUCHE A RIEN !")
gpu_proc = subprocess.Popen(["glxgears"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

history = []
try:
    for i in range(40):
        history.append(get_floats())
        time.sleep(0.4)
finally:
    gpu_proc.terminate()
    print("3. Cible abattue. Fermeture du test 3D.")

print("\nAnalyse mathématique en cours de 40 échantillons...")

igpu_clocks = [frame[108] for frame in history]

if max(igpu_clocks) - min(igpu_clocks) < 100:
    print(f"ÉCHEC: Ton iGPU est resté endormi (min {min(igpu_clocks):.0f} / max {max(igpu_clocks):.0f} MHz).")
    exit()

def pearson(x, y):
    n = len(x)
    dx = [a - sum(x)/n for a in x]
    dy = [b - sum(y)/n for b in y]
    num = sum(a*b for a, b in zip(dx, dy))
    den = math.sqrt(sum(a**2 for a in dx) * sum(b**2 for b in dy))
    return num / den if den != 0 else 0

print(f"✅ iGPU Clock a bien pulsé : {min(igpu_clocks):.0f} MHz -> {max(igpu_clocks):.0f} MHz")

found = False
for index in range(len(history[0])):
    if index in KNOWN or index == 108: continue
    
    curve = [frame[index] for frame in history]
    if max(curve) == min(curve): continue
    
    corr = pearson(igpu_clocks, curve)
    
    if corr > 0.88:
        mi, ma = min(curve), max(curve)
        if 0 < ma < 150: # Règle pour du courant ou de la conso iGPU plausible
            found = True
            print(f"🔎 CORRÉLATION {corr*100:.1f}% SUR L'ADRESSE d[{index:3}] (0x{index*4:03X})")
            print(f"   Repos = {mi:.2f} | En charge = {ma:.2f}\n")

if not found:
    print("Échec: Aucune métrique n'a suivi rigoureusement l'horloge iGPU.")

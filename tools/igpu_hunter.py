import struct
import time
import math

# Offsets connus qu'on ignore
KNOWN = {2, 3, 8, 10, 18, 19, 20} # Limites CPU
for i in range(8):
    KNOWN.update([309+i, 317+i, 325+i, 373+i]) # Core vols/temps/freq

def get_floats():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    return list(struct.unpack(f"<{len(data)//4}f", data))

print("=== CHASSEUR DE PUISSANCE iGPU ===")
print("Pendant les 15 prochaines secondes, lance un gros jeu 3D ou bouge sauvagement une fenêtre lourde !")
print("Le script va capturer 30 images de la table et chercher ce qui évolue *exactement* en même temps que l'horloge iGPU.")

history = []
for i in range(30):
    history.append(get_floats())
    time.sleep(0.5)

print("\nAnalyse mathématique en cours...")

# Extraction de la courbe de l'horloge iGPU (0x1B0 = index 108)
igpu_clocks = [frame[108] for frame in history]

# Si l'horloge n'a pas bougé, c'est mort
if max(igpu_clocks) - min(igpu_clocks) < 200:
    print(f"ÉCHEC: Ton iGPU est resté endormi (min {min(igpu_clocks):.0f} / max {max(igpu_clocks):.0f} MHz).")
    print("Le test 3D n'était pas assez fort pour le réveiller !")
    exit()

def pearson(x, y):
    n = len(x)
    mean_x, mean_y = sum(x)/n, sum(y)/n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mean_x)**2 for a in x) * sum((b - mean_y)**2 for b in y))
    return num / den if den != 0 else 0

print(f"✅ iGPU Clock a bougé : {min(igpu_clocks):.0f} MHz -> {max(igpu_clocks):.0f} MHz")
print("Recherche de valeurs corrélées à plus de 85% avec l'horloge iGPU...\n")

found = False
for index in range(len(history[0])):
    if index in KNOWN or index == 108: continue
    
    curve = [frame[index] for frame in history]
    # On ignore les valeurs mortes ou fixes
    if max(curve) == min(curve): continue
    
    # On calcule la corrélation avec l'horloge iGPU
    corr = pearson(igpu_clocks, curve)
    
    if corr > 0.85:
        mi = min(curve)
        ma = max(curve)
        
        # Filtre anti-bruit pour des valeurs aberrantes
        if 0 < ma < 1000:
            found = True
            print(f"🔎 CORRÉLATION TROUVÉE ({corr*100:.1f}%) sur d[{index:3}] (0x{index*4:03X})")
            print(f"   Valeurs: {mi:.2f} -> {ma:.2f}")

if not found:
    print("Rien de probant trouvé. AMD cache peut-être la conso iGPU sur Granite Ridge, ou elle est fusionnée à la conso SoC.")

import struct
import time
import sys

def get_floats():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    return list(struct.unpack(f"<{len(data)//4}f", data))

print("Capture du repos... Veille à ne rien faire graphiquement.")
time.sleep(2)
idle = get_floats()

print("\n!!! LANCE UN TRUC GRAPHIQUE LOURD MAINTENANT !!!")
print("(Ex: Bouge une fenêtre très vite, lance une vidéo 4K, ou glxgears)")
for i in range(5, 0, -1):
    print(f"Mesure dans {i}s...")
    time.sleep(1)

load = get_floats()

print("\n--- DIFFÉRENCE (iGPU cibles potentielles) ---")
for i in range(len(idle)):
    diff = load[i] - idle[i]
    
    # Si ça ressemble à une horloge (était ~600, est monté au dessus de 1000)
    if 500 < idle[i] < 700 and load[i] > 800:
        print(f"HORLOGE TROUVÉE ? d[{i:3}] (0x{i*4:03X}) : repos={idle[i]:.0f} MHz -> charge={load[i]:.0f} MHz")
        
    # Si ça ressemble à une puissance/courant (était < 5, est monté > 10)
    elif 0 <= idle[i] < 10 and load[i] > 10 and diff > 5:
        print(f"PUISSANCE/COURANT TROUVÉ ? d[{i:3}] (0x{i*4:03X}) : repos={idle[i]:.2f} -> charge={load[i]:.2f} (+ {diff:.2f})")
        
    # Si temp: (était ~40, est monté ~50)
    elif 30 < idle[i] < 60 and diff > 4:
        print(f"TEMPÉRATURE TROUVÉE ? d[{i:3}] (0x{i*4:03X}) : repos={idle[i]:.1f}°C -> charge={load[i]:.1f}°C (+ {diff:.1f}°C)")

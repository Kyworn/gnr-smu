import tkinter as tk
from tkinter import ttk
import struct
import threading
import time

# Structure de la table pour GNR
# Offset 0x050: Package Power, 0x4D4: VCORE, 0x4F4: TEMP, 0x514: FREQ
class GNRMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GNR-SMU Control Center")
        self.running = True
        
        self.create_widgets()
        self.update_loop()

    def create_widgets(self):
        self.power_label = ttk.Label(self.root, text="Package Power: 0.0 W", font=("Arial", 14))
        self.power_label.pack(pady=10)
        
        self.tree = ttk.Treeview(self.root, columns=("Core", "Freq", "Volt", "Temp"), show='headings')
        for col in ("Core", "Freq", "Volt", "Temp"):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80)
        self.tree.pack(pady=10)

    def read_pm_table(self):
        try:
            with open("/dev/gnr_smu", "rb") as f:
                data1 = f.read(0x724)
                time.sleep(0.01) # Petit délai pour le double read
                data2 = f.read(0x724)
                
                # Vérification simple (double read)
                if data1 == data2:
                    return struct.unpack("<466f", data1[:1864])
        except Exception:
            return None
        return None

    def update_loop(self):
        if not self.running: return
        
        data = self.read_pm_table()
        if data:
            # Offset 0x50 / 4 = 20 (Power)
            power = data[20]
            self.power_label.config(text=f"Package Power: {power:.2f} W")
            
            # Mise à jour treeview
            for i in range(8):
                freq = data[325 + i] * 1000 # 0x514 = 1300 bytes / 4
                volt = data[309 + i] # 0x4D4 = 1236 bytes / 4
                temp = data[317 + i] # 0x4F4 = 1268 bytes / 4
                
                item = f"Core {i}"
                if self.tree.exists(item):
                    self.tree.item(item, values=(i, f"{freq:.0f}", f"{volt:.3f}", f"{temp:.2f}"))
                else:
                    self.tree.insert("", "end", iid=item, values=(i, f"{freq:.0f}", f"{volt:.3f}", f"{temp:.2f}"))
        
        self.root.after(500, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = GNRMonitorGUI(root)
    root.mainloop()
EOF
,file_path:
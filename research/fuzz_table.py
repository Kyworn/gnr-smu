import subprocess
import time

def smu_send(msg_id, arg0):
    # Utilise smu_send.py pour envoyer la commande
    # On fait un appel système pour éviter de réécrire la logique
    res = subprocess.check_output(["sudo", "-S", "python3", "/home/zorko/gnr-smu/smu_send.py", "send", hex(msg_id), hex(arg0)], input="6139\n", text=True)
    return res

print("Fuzzing Table IDs (0x6B)...")
for i in range(16):
    res = smu_send(0x6B, i)
    print(f"ID={i}: {res.strip()}")

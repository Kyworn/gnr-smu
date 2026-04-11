import subprocess

def smu_send(msg_id, arg0):
    try:
        # On passe le mot de passe via l'argument input si besoin, ou on utilise le script directement
        # pour éviter d'appeler sudo à chaque fois si le script est déjà lancé avec les bonnes perms.
        # Ici on appelle smu_send.py qui gère déjà setpci
        res = subprocess.check_output(["sudo", "-S", "python3", "/home/zorko/gnr-smu/smu_send.py", "send", hex(msg_id), hex(arg0)], input="6139\n", text=True)
        return res.strip()
    except Exception as e:
        return f"Error: {e}"

print("Probing SMU IDs (0x00 - 0x20)...")
for i in range(0x21):
    res = smu_send(i, 0)
    # Parsing rapide pour extraire RSP
    # Format attendu: MSG=... RSP=... ARG0_ret=...
    print(f"ID={hex(i)}: {res}")

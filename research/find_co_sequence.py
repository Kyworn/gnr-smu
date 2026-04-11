import struct
import time

def get_table():
    with open("/dev/gnr_smu", "rb") as f:
        return f.read(0x724)

data = get_table()
# On cherche la séquence -1, -2, -3, -4, -5, -6, -7, -8 (en octets non-signés)
sequence = bytes([0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xF9, 0xF8])

idx = data.find(sequence)
if idx != -1:
    print(f"CO sequence found at offset 0x{idx:03X} !!")
else:
    print("Sequence not found. Trying reverse order or different mapping...")
    # Essayons de chercher juste -1 et -2 à la suite
    idx2 = data.find(bytes([0xFF, 0xFE]))
    if idx2 != -1:
        print(f"Potential start at 0x{idx2:03X}")

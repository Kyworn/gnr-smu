import struct
import time
import os

def set_co(core, val):
    with open("/dev/gnr_smu", "w") as f:
        f.write(f"{hex(0x50 + core)} {hex(val & 0xFFFFFFFF)}")

def get_table():
    with open("/dev/gnr_smu", "rb") as f:
        return f.read(0x724)

print("Setting unique CO values...")
for i in range(8):
    set_co(i, -(i + 1)) # Core 0 = -1, Core 1 = -2...

time.sleep(1)
data = get_table()

print("Searching for values -1 to -8 (as 32-bit ints or bytes)...")
# On cherche les valeurs -(i+1) dans la table
for i in range(8):
    target = -(i + 1)
    target_32 = struct.pack("<i", target)
    target_8 = struct.pack("b", target)
    
    idx_32 = data.find(target_32)
    if idx_32 != -1:
        print(f"Core {i} (-{i+1}) found at offset 0x{idx_32:03X} (int32)")
    
    # On cherche aussi en tant qu'octets isolés (très probable)
    # Mais il peut y avoir des faux positifs, donc on cherche une séquence

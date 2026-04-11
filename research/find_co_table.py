import struct

with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    data = f.read()
    # On unpack tout en float32
    count = len(data) // 4
    floats = struct.unpack(f"<{count}f", data[:count*4])

# On cherche 8 valeurs identiques consécutives
print("Scanning for 8-core CO sequence...")
for i in range(len(floats) - 8):
    chunk = floats[i:i+8]
    # On ignore les zéros et on cherche des valeurs cohérentes avec un CO
    if len(set(chunk)) == 1 and chunk[0] != 0.0 and abs(chunk[0]) < 100:
        print(f"Sequence found at offset 0x{i*4:03X} : {chunk[0]} (x8)")

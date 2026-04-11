import struct
import time

SMU_ARGS  = "/sys/kernel/ryzen_smu_drv/smu_args"
SMU_CMD   = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

def set_smu(msg, arg):
    try:
        with open(SMU_ARGS, "wb") as f:
            f.write(struct.pack("<6I", arg, 0, 0, 0, 0, 0))
        with open(SMU_CMD, "wb") as f:
            f.write(struct.pack("<I", msg))
        with open(SMU_CMD, "rb") as f:
            return struct.unpack("<I", f.read(4))[0]
    except:
        return 0

def get_table():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        return f.read(1828)

print("Applying CO pattern: -10, -11, -12, -13, -14, -15, -16, -17...")
for i in range(8):
    val = (-(10 + i)) & 0xFFFFFFFF
    set_smu(0x50 + i, val)

time.sleep(1)
data = get_table()

print("Scanning for byte sequences and ints...")
# Look for 32-bit ints
ints = struct.unpack("<457i", data)
found = False
for i in range(len(ints) - 7):
    # check if we see -10, -11, -12 in order roughly
    if ints[i] == -10:
        found = True
        print(f"FOUND -10 at float/int index {i} (offset 0x{i*4:X})")
        for j in range(8):
            print(f"  Core {j} CO: {ints[i+j]}")
if not found:
    print("Could not find -10 as a standard 32-bit int.")

print("Restoring CO to -30 (0xFFFFFFE2)...")
for i in range(8):
    set_smu(0x50 + i, 0xFFFFFFE2)

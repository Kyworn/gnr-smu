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
        d = struct.unpack("<457f", f.read(1828))
        return d[2], d[10], d[8] # PPT, TDC, EDC

# Reset first
set_smu(0x3B, 85000); set_smu(0x3C, 85000); set_smu(0x3D, 85000); set_smu(0x3E, 162000)
time.sleep(1)

print("Starting Mapping Test...")
vals = {0x3B: 41000, 0x3C: 42000, 0x3D: 43000, 0x3E: 44000, 0x3F: 45000}

for msg, v in vals.items():
    print(f"\nSending MSG {hex(msg)} with arg {v}...")
    rsp = set_smu(msg, v)
    time.sleep(0.5)
    p, t, e = get_table()
    print(f"RSP={rsp} | PPT={p:.1f}W | TDC={t:.1f}A | EDC={e:.1f}A")

# Revert  
set_smu(0x3B, 85000); set_smu(0x3C, 85000); set_smu(0x3D, 85000); set_smu(0x3E, 162000)

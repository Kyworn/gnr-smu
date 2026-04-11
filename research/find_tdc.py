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

print("Testing more MSG IDs for TDC...")
vals = [0x32, 0x33, 0x38, 0x39, 0x3A, 0x4B, 0x4C, 0x35]
for msg in vals:
    rsp = set_smu(msg, 38000) # try to set to 38A
    time.sleep(0.3)
    p, t, e = get_table()
    if t < 84.0 or rsp == 1:
        print(f"MSG {hex(msg)} -> RSP {rsp} | PPT={p:.1f}W | TDC={t:.1f}A | EDC={e:.1f}A")

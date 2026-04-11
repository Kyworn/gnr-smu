import struct
import time

SMU_ARGS  = "/sys/kernel/ryzen_smu_drv/smu_args"
SMU_CMD   = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

def set_smu(msg, arg):
    open(SMU_ARGS, "wb").write(struct.pack("<6I", arg, 0, 0, 0, 0, 0))
    open(SMU_CMD, "wb").write(struct.pack("<I", msg))
    rsp = struct.unpack("<I", open(SMU_CMD, "rb").read(4))[0]
    return rsp

with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    d = struct.unpack("<457f", f.read(1828))
    print(f"INITIAL - TDC (d[10]): {d[10]:.2f}, EDC (d[8]): {d[8]:.2f}")

print("Setting MSG 0x3C to 60A...")
rsp = set_smu(0x3C, 60000)
print(f"RSP: {rsp}")
time.sleep(0.5)
with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    d = struct.unpack("<457f", f.read(1828))
    print(f"AFTER 0x3C - TDC: {d[10]:.2f}, EDC: {d[8]:.2f}")

print("Setting MSG 0x3D to 60A...")
rsp_edc = set_smu(0x3D, 60000)
print(f"RSP: {rsp_edc}")
time.sleep(0.5)
with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
    d = struct.unpack("<457f", f.read(1828))
    print(f"AFTER 0x3D - TDC: {d[10]:.2f}, EDC: {d[8]:.2f}")

# Revert to 85A
set_smu(0x3C, 85000)
set_smu(0x3D, 85000)

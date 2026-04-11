import struct
import time
import sys

SMU_ARGS  = "/sys/kernel/ryzen_smu_drv/smu_args"
SMU_CMD   = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

def set_smu(msg, arg):
    try:
        with open(SMU_ARGS, "wb") as f:
            f.write(struct.pack("<6I", arg, 0, 0, 0, 0, 0))
        with open(SMU_CMD, "wb") as f:
            f.write(struct.pack("<I", msg))
        with open(SMU_CMD, "rb") as f:
            rsp = struct.unpack("<I", f.read(4))[0]
        return rsp
    except Exception as e:
        print(f"Error: {e}")
        return 0

def read_limits():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        d = struct.unpack("<457f", f.read(1828))
        return d[2], d[10], d[8] # PPT, TDC, EDC

ppt, tdc, edc = read_limits()
print(f"INITIAL: PPT={ppt:.2f} W, TDC={tdc:.2f} A, EDC={edc:.2f} A")

# Test TDC reduction (to 50 A)
print("\nTesting TDC reduction to 50A (0x3C, arg: 50000)...")
rsp = set_smu(0x3C, 50000)
print(f"Response: {rsp} (1=OK)")
time.sleep(0.5)
ppt, tdc, edc = read_limits()
print(f"CURRENT: TDC={tdc:.2f} A, EDC={edc:.2f} A")

# Test EDC reduction (to 70 A)
print("\nTesting EDC reduction to 70A (0x3D, arg: 70000)...")
rsp = set_smu(0x3D, 70000)
print(f"Response: {rsp} (1=OK)")
time.sleep(0.5)
ppt, tdc, edc = read_limits()
print(f"CURRENT: TDC={tdc:.2f} A, EDC={edc:.2f} A")

# Revert
set_smu(0x3C, 85000)
set_smu(0x3D, 85000)

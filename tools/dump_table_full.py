import struct

def parse_pm_table():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)
    
    floats = struct.unpack(f"<{len(data)//4}f", data)
    
    known = {
        2: "PPT Limit (W)", 3: "Pkg Temp (°C)", 8: "EDC Limit (A)", 
        10: "TDC Limit (A)", 18: "Vcore Peak (V)", 19: "Vcore Avg (V)", 
        20: "Pkg Power (W)", 63: "EDC Max?", 64: "TjMax Limit (°C)"
    }
    
    # Add per core
    for i in range(8):
        known[309+i] = f"Core {i} Volt (V)"
        known[317+i] = f"Core {i} Temp (°C)"
        known[325+i] = f"Core {i} Freq (GHz)"
        known[373+i] = f"Core {i} Max Freq (GHz)"
        
    print("--- DUMP PM TABLE (Valeurs remarquables) ---")
    for i, v in enumerate(floats):
        # Ignore close to 0 or weird NaNs/huge values unless it's a known offset
        if i in known:
            print(f"d[{i:3}] (0x{i*4:03X}) = {v:8.3f}  <- {known[i]}")
        elif abs(v) > 0.1 and abs(v) < 10000:
            # We filter out likely junk
            print(f"d[{i:3}] (0x{i*4:03X}) = {v:8.3f}")

if __name__ == "__main__":
    parse_pm_table()

import struct


def parse_pm_table():
    with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
        data = f.read(1828)

    floats = struct.unpack(f"<{len(data) // 4}f", data)

    KNOWN = {
        2: "PPT Limit (W)",
        3: "Package Temp (°C)",
        8: "EDC Limit (A)",
        9: "SoC Temp (°C)",
        10: "TDC Limit (A)",
        11: "VRM/Hotspot Temp (°C)",
        16: "Energy Accumulator (J?)",
        17: "Telemetry Ratio",
        18: "Vcore Peak (V)",
        19: "Vcore Avg (V)",
        20: "Package Power (W)",
        21: "SoC Power (W)",
        22: "VDDCR_CPU Power (W)",
        23: "VDDIO_MEM Power (W)",
        24: "Power Scalar",
        25: "Voltage Scalar",
        26: "Pkg Temp Mirror (°C)",
        48: "Vcore Set (V)",
        49: "Vcore P1 (V)",
        50: "SoC Temp Mirror (°C)",
        51: "Pkg Power Mirror (W)",
        53: "VDDCR_SoC Set (V)",
        54: "VDDP Voltage (V)",
        57: "SoC Telemetry Current (A)",
        58: "VDDIO_MEM Voltage (V)",
        59: "VDDIO_MEM Voltage (mirror)",
        62: "SoC Power Limit (W?)",
        63: "EDC Max (A)",
        64: "Tctl / CPU Die Temp (°C)",
        71: "FCLK (MHz)",
        75: "UCLK (MHz)",
        79: "MCLK (MHz)",
        83: "VSOC Voltage (V)",
        84: "VDDP (V)",
        85: "VDDG (V)",
        86: "VDDM (V)",
        87: "VDDCR_SoC Live (V)",
        95: "SoC Voltage Live (V)",
        96: "SoC Power Live (W)",
        106: "iGPU Accumulated Metric",
        107: "iGPU Power (W)",
        108: "iGPU Clock (MHz)",
        109: "iGPU Activity (%)",
        110: "iGPU Current (A)",
        186: "GFX Junction Temp (°C)",
        187: "GFX Thermal Headroom (°C)",
        209: "Thermal Limit (°C)",
        210: "CCD Temp (°C)",
        268: "EDC Limit Mirror (A)",
        269: "SVI3 VDDCR_CPU VID (V)",
        270: "TDC Current (A)",
        271: "SVI3 VDDCR_SoC VID (V)",
        272: "Max Boost Freq (GHz)",
        298: "L3/VCache Temp 0 (°C)",
        299: "L3/VCache Temp 1 (°C)",
        448: "Avg Core Temp (°C)",
        449: "Min Core Temp (°C)",
        450: "Peak Core Freq (GHz)",
        451: "Avg Core Freq (GHz)",
        452: "Total Pkg Energy Accumulator (J)",
        455: "Effective Freq (GHz)",
        456: "Ambient/Board Temp (°C)",
    }

    for i in range(8):
        KNOWN[301 + i] = f"Core {i} IDD (A)"
        KNOWN[309 + i] = f"Core {i} Voltage (V)"
        KNOWN[317 + i] = f"Core {i} Temp (°C)"
        KNOWN[325 + i] = f"Core {i} Freq (GHz)"
        KNOWN[333 + i] = f"Core {i} Power Idle (W)"
        KNOWN[341 + i] = f"Core {i} FIT/IDD Max"
        KNOWN[349 + i] = f"Core {i} C6 Residency (%)"
        KNOWN[357 + i] = f"Core {i} C0 Residency (%)"
        KNOWN[365 + i] = f"Core {i} C1 Residency (%)"
        KNOWN[373 + i] = f"Core {i} Boost Limit (GHz)"
        KNOWN[381 + i] = f"Core {i} P1/Base Freq (GHz)"
        KNOWN[397 + i] = f"Core {i} Energy Accumulator (J)"

    print("--- DUMP PM TABLE (457 floats) ---")
    for i, v in enumerate(floats):
        if i in KNOWN:
            print(f"d[{i:3}] (0x{i * 4:03X}) = {v:12.3f}  <- {KNOWN[i]}")
        elif abs(v) > 0.01 and abs(v) < 100000 and v == v:
            print(f"d[{i:3}] (0x{i * 4:03X}) = {v:12.3f}")


if __name__ == "__main__":
    parse_pm_table()

#!/usr/bin/env python3
import struct

with open('/sys/kernel/ryzen_smu_drv/pm_table', 'rb') as f:
    data = f.read()

print(f'Table size: {len(data)} bytes = {len(data)//4} floats')
d = struct.unpack(f'<{len(data)//4}f', data)

print(f'd[2]  (0x008) PPT Limit:  {d[2]:.2f} W')
print(f'd[3]  (0x00C) Pkg Temp:   {d[3]:.2f} C')
print(f'd[8]  (0x020) EDC Limit:  {d[8]:.2f} A')
print(f'd[10] (0x028) TDC Limit:  {d[10]:.2f} A')
print(f'd[20] (0x050) Pkg Power:  {d[20]:.2f} W')
print()
for i in range(8):
    print(f'Core {i}: freq={d[325+i]*1000:.0f}MHz volt={d[309+i]:.3f}V temp={d[317+i]:.1f}C')

#!/usr/bin/env python3
import subprocess
import time

PCI_DEV  = "00:00.0"
MSG_ADDR = 0x3B10530
RSP_ADDR = 0x3B1057C
ARG0_ADDR = 0x3B109C4

def setpci(offset, value=None):
    if value is None:
        return int(subprocess.check_output(["setpci", "-s", PCI_DEV, f"{offset:02X}.L"]).strip(), 16)
    else:
        subprocess.run(["setpci", "-s", PCI_DEV, f"{offset:02X}.L={value:08X}"])

def sniff():
    print("Sniffing SMU mailbox... (Ctrl+C to stop)")
    last_msg = 0
    while True:
        msg = setpci(0xBC) # Lecture simplifiée SMN Data
        # Pour sniffer réellement il faudrait relire le SMN ADDR 0xB8 régulièrement
        # mais on va juste poll les adresses de mailbox.
        # On va se concentrer sur ARG0 pour voir si une adresse y apparaît après 0x6B
        arg0 = smn_read_direct(ARG0_ADDR)
        rsp = smn_read_direct(RSP_ADDR)
        if rsp != 0:
            print(f"RSP: 0x{rsp:02X} | ARG0: 0x{arg0:08X}")
        time.sleep(0.5)

def smn_read_direct(addr):
    subprocess.run(["setpci", "-s", PCI_DEV, f"B8.L={addr:08X}"], capture_output=True)
    return int(subprocess.check_output(["setpci", "-s", PCI_DEV, "BC.L"]).strip(), 16)

if __name__ == "__main__":
    sniff()

import subprocess
import time

def probe_smu(msg_id):
    try:
        with open("/dev/gnr_smu", "w") as f:
            f.write(f"{hex(msg_id)} 0")
        time.sleep(0.1)
        res = subprocess.check_output(["dmesg"], text=True)
        lines = res.splitlines()
        for line in reversed(lines):
            if "Sent MSG" in line:
                return line
    except Exception as e:
        return f"Error: {e}"

print("Probing IDs 0x40 - 0x60...")
for i in range(0x40, 0x61):
    log = probe_smu(i)
    print(f"ID {hex(i)}: {log}")
